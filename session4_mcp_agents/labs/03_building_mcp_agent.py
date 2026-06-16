# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">Lab 03: Building a RAG Agent</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Session 4: Building AI Agents with MCP · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 30 min core · +15 min Extension A · +20 min Extension B |
# MAGIC | **Prerequisites** | Labs 01 and 02 complete |
# MAGIC | **Role** | Data engineer / ML engineer |
# MAGIC
# MAGIC **By the end of the core lab you will have:**
# MAGIC - [ ] Understood the three-step RAG pattern (retrieve → augment → generate)
# MAGIC - [ ] Built a RAG agent that answers questions about AEMO market notices
# MAGIC - [ ] Seen how source chunks are passed to the LLM alongside the question
# MAGIC - [ ] Tested the agent against three real AEMO questions
# MAGIC
# MAGIC **Optional extensions (if time allows):**
# MAGIC - [ ] **Extension A** — add Genie as a second source for quantitative questions
# MAGIC - [ ] **Extension B** — upgrade to a LangGraph ReAct agent with all three MCP tools

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0: Setup

# COMMAND ----------

# NOTE: Run this — installs all required packages. Takes ~60 seconds.
%pip install databricks-mcp databricks-langchain langgraph langchain-core mlflow --quiet
dbutils.library.restartPython()

# COMMAND ----------

# NOTE: Run this — loads config saved by Lab 01. Fails fast if Lab 01 hasn't been run.
import json
from pathlib import Path

_config_path = Path("/tmp/workshop2c_config.json")
_saved = json.loads(_config_path.read_text()) if _config_path.exists() else {}

dbutils.widgets.text("catalog",            _saved.get("CATALOG",            "workshop_au"),                        "Catalog name")
dbutils.widgets.text("schema_aemo",        _saved.get("SCHEMA_AEMO",        "aemo"),                               "AEMO schema name")
dbutils.widgets.text("pt_endpoint",        _saved.get("PT_ENDPOINT",        "au_east_llm_inregion"),               "PT endpoint name")
dbutils.widgets.text("vs_index_name",      _saved.get("VS_INDEX_NAME",      ""),                                   "Vector Search index (catalog.schema.index)")
dbutils.widgets.text("genie_space_id",     _saved.get("GENIE_SPACE_ID",     ""),                                   "Genie Space ID (Extension A only)")
dbutils.widgets.text("mlflow_experiment",  _saved.get("MLFLOW_EXPERIMENT",  "/Shared/workshop2c-aemo-operations-agent"), "MLflow experiment path")

CATALOG            = dbutils.widgets.get("catalog")
SCHEMA_AEMO        = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT        = dbutils.widgets.get("pt_endpoint")
VS_INDEX_NAME      = dbutils.widgets.get("vs_index_name")
GENIE_SPACE_ID     = dbutils.widgets.get("genie_space_id").strip()
MLFLOW_EXPERIMENT  = dbutils.widgets.get("mlflow_experiment").strip()

ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST  = ctx.apiUrl().get()
TOKEN = ctx.apiToken().get()

print(f"Catalog         : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint     : {PT_ENDPOINT}")
print(f"VS index        : {VS_INDEX_NAME or '(not set — enter in widget above)'}")
print(f"Genie space     : {GENIE_SPACE_ID or '(not set — needed for Extension A only)'}")
print(f"MLflow experiment: {MLFLOW_EXPERIMENT}")

# Save all config values (including MLFLOW_EXPERIMENT) so downstream labs can read them.
import json as _json_cfg
from pathlib import Path as _Path_cfg

_config_path = _Path_cfg("/tmp/workshop2c_config.json")
_cfg = _json_cfg.loads(_config_path.read_text()) if _config_path.exists() else {}
_cfg.update({
    "CATALOG":           CATALOG,
    "SCHEMA_AEMO":       SCHEMA_AEMO,
    "PT_ENDPOINT":       PT_ENDPOINT,
    "GENIE_SPACE_ID":    GENIE_SPACE_ID,
    "VS_INDEX_NAME":     VS_INDEX_NAME,
    "MLFLOW_EXPERIMENT": MLFLOW_EXPERIMENT,
})
_config_path.write_text(_json_cfg.dumps(_cfg, indent=2))
print(f"Configuration updated: {_config_path}")

# COMMAND ----------

# NOTE: Verifies the PT endpoint is reachable. Stop here if this returns an error.
import requests

_resp = requests.get(
    f"{HOST}/api/2.0/serving-endpoints/{PT_ENDPOINT}",
    headers={"Authorization": f"Bearer {TOKEN}"},
    timeout=15
)
if _resp.status_code == 200:
    _state = _resp.json().get("state", {}).get("ready", "UNKNOWN")
    print(f"✅ PT endpoint '{PT_ENDPOINT}' — state: {_state}")
    if _state != "READY":
        print("   ⚠️  Wait for READY state before running Section 3.")
elif _resp.status_code == 404:
    raise RuntimeError(
        f"PT endpoint '{PT_ENDPOINT}' not found.\n"
        "Ask your facilitator to deploy it: Serving → Create endpoint → databricks-claude-haiku-4-5 (PT)"
    )
else:
    print(f"⚠️  HTTP {_resp.status_code} — {_resp.text[:200]}")

# COMMAND ----------

# NOTE: Imports used throughout the lab.
from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient
from openai import OpenAI

ws = WorkspaceClient(host=HOST, token=TOKEN)

llm = OpenAI(
    api_key=TOKEN,
    base_url=f"{HOST}/serving-endpoints/{PT_ENDPOINT}/v1",
)

print("WorkspaceClient and LLM client ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1: What is RAG? (~5 min)
# MAGIC
# MAGIC > *"A RAG agent doesn't know the answer. It knows where to look."*
# MAGIC
# MAGIC RAG stands for **Retrieval-Augmented Generation**. Instead of asking an LLM to answer from memory — which fails for recent events, private data, or domain-specific content — you first retrieve relevant documents and then give those documents to the LLM as context.
# MAGIC
# MAGIC The pattern is always three steps:
# MAGIC
# MAGIC ```
# MAGIC User question
# MAGIC     │
# MAGIC     ▼
# MAGIC  1. RETRIEVE   — search a vector index for the most relevant chunks
# MAGIC     │
# MAGIC     ▼
# MAGIC  2. AUGMENT    — add those chunks to the prompt as context
# MAGIC     │
# MAGIC     ▼
# MAGIC  3. GENERATE   — LLM answers using only the provided context
# MAGIC     │
# MAGIC     ▼
# MAGIC  Answer + source chunks shown to user
# MAGIC ```
# MAGIC
# MAGIC | | RAG agent (this lab) | LangGraph ReAct (Extension B) |
# MAGIC |---|---|---|
# MAGIC | **What the LLM decides** | Nothing — fixed pipeline | Which tool to call next |
# MAGIC | **Number of LLM calls** | 1 | 1 per reasoning step (often 3–5) |
# MAGIC | **Best for** | Document Q&A, policy lookup, known retrieval pattern | Multi-step reasoning across SQL + search + calculation |
# MAGIC | **Easier to debug?** | ✅ Yes — trace is always retrieve → answer | Harder — tool selection varies per question |
# MAGIC
# MAGIC For AEMO market notices and regulatory documents, RAG is the right default. The retrieval target is fixed, the pattern is predictable, and participants can see exactly which chunks the LLM used.
# MAGIC
# MAGIC ### 🖱️ UI: look at your Vector Search index
# MAGIC
# MAGIC 1. In the left sidebar, go to **Catalog**
# MAGIC 2. Expand `workshop_au` → `aemo`
# MAGIC 3. Find the index (it has a search-symbol icon — different from a table)
# MAGIC 4. Click it — you can see the source table, embedding model, and sync status
# MAGIC 5. **Sync status must be `ONLINE`** before running the code below. If it shows `SYNCING`, wait 2–3 minutes and refresh.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2: Retrieve — query Vector Search via MCP (~10 min)
# MAGIC
# MAGIC In Lab 02 you connected to the Vector Search MCP server and listed its tools. Here you use it to retrieve the most relevant market notice chunks for a given question.
# MAGIC
# MAGIC Each chunk in the result contains:
# MAGIC - The raw text of a market notice (the `reason` field)
# MAGIC - Metadata: `notice_id`, `notice_type`, `region_id`, `issue_time`
# MAGIC - A similarity score — higher means more relevant
# MAGIC
# MAGIC ### 🖱️ UI: find the MCP server in AI Gateway
# MAGIC
# MAGIC 1. Go to **Machine Learning** (left sidebar) → **AI Gateway**
# MAGIC 2. Click the **MCP Servers** tab (next to External Models)
# MAGIC 3. Find the entry for your Vector Search index
# MAGIC 4. Click it — the detail view shows the endpoint URL and the single search tool exposed by this server
# MAGIC
# MAGIC There is no UI for running a search query — that always goes through code or an agent.
# MAGIC
# MAGIC **⚡ Code:**

# COMMAND ----------

# NOTE: Connects to the Vector Search MCP server and runs a test search.
# This is step 1 (Retrieve) in isolation — Section 3 wraps it into the full pipeline.

if not VS_INDEX_NAME:
    raise ValueError(
        "VS index name not set.\n"
        "Enter it in the 'vs_index_name' widget above.\n"
        "Format: catalog.schema.index_name  e.g. workshop_au.aemo.market_notices_index"
    )

vs_parts   = VS_INDEX_NAME.split(".")
vs_mcp_url = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"

vs_client = DatabricksMCPClient(vs_mcp_url, ws)
vs_tools  = vs_client.list_tools()
VS_TOOL_NAME = vs_tools[0].name

print(f"Connected to: {vs_mcp_url}")
print(f"Search tool : {VS_TOOL_NAME}\n")

_test_query  = "LOR2 reserve shortfall Victoria"
_test_result = vs_client.call_tool(VS_TOOL_NAME, {"query": _test_query, "num_results": 3})

print(f"Test query: '{_test_query}'\n")
if _test_result and not _test_result.get("isError"):
    for item in _test_result.get("content", []):
        if item.get("type") == "text":
            print(item["text"][:800])
else:
    print(f"Error: {_test_result}")

# COMMAND ----------

# MAGIC %md
# MAGIC **What you're looking at:** each result is one market notice, ranked by similarity to your query. In Section 3 these chunks are passed directly into the LLM prompt — the LLM reads them before forming its answer.
# MAGIC
# MAGIC Notice the `score` field. Scores above 0.7 are reliably relevant; below 0.5 the chunk may be noise. The RAG function in Section 3 filters on this.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3: Build the RAG agent (~10 min)
# MAGIC
# MAGIC The `rag_answer` function below runs the full three-step pipeline in one call:
# MAGIC
# MAGIC - **Retrieve** — calls Vector Search MCP with the user's question, gets `top_k` chunks above a minimum similarity score
# MAGIC - **Augment** — formats those chunks into a numbered `Context:` block and appends the question
# MAGIC - **Generate** — sends the augmented prompt to the PT endpoint; the system prompt instructs the LLM to cite notice IDs
# MAGIC
# MAGIC The function returns both the answer text and the raw source chunks so you can verify which notices were used.

# COMMAND ----------

# NOTE: Defines retrieve_chunks(), format_context(), and rag_answer().
# Run this cell to register the functions — no API calls are made yet.
# Section 4 runs the test questions.

import json as _json

SYSTEM_PROMPT = """You are an AEMO market operations analyst assistant.

Answer questions using ONLY the market notices provided in the context below.
Do not draw on general knowledge or make up notice details.

Rules:
- Cite the notice_id for every claim (e.g. "Notice MN-2024-0042 reported...")
- If the context does not contain enough information, say so clearly
- Keep answers concise — 3–5 sentences unless more detail is needed
- Australian date format: DD/MM/YYYY
"""


def retrieve_chunks(question: str, top_k: int = 5, min_score: float = 0.5) -> list:
    """Call Vector Search MCP and return chunks above the minimum similarity score."""
    result = vs_client.call_tool(VS_TOOL_NAME, {"query": question, "num_results": top_k})

    if not result or result.get("isError"):
        return []

    raw = ""
    for item in result.get("content", []):
        if item.get("type") == "text":
            raw = item["text"]
            break

    chunks = []
    try:
        data = _json.loads(raw)
        chunks = data if isinstance(data, list) else data.get("result", [data])
    except Exception:
        for line in raw.strip().splitlines():
            try:
                chunks.append(_json.loads(line))
            except Exception:
                pass

    return [c for c in chunks if c.get("score", 1.0) >= min_score]


def format_context(chunks: list) -> str:
    """Format retrieved chunks into a numbered context block for the prompt."""
    if not chunks:
        return "(No relevant market notices found.)"

    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[{i}] Notice ID: {c.get('notice_id', 'unknown')}")
        lines.append(f"    Type    : {c.get('notice_type', '')}")
        lines.append(f"    Region  : {c.get('region_id', 'NEM-wide')}")
        lines.append(f"    Issued  : {c.get('issue_time', '')}")
        lines.append(f"    Text    : {c.get('reason', c.get('text', ''))[:400]}")
        lines.append("")
    return "\n".join(lines)


def rag_answer(question: str, top_k: int = 5) -> dict:
    """
    Three-step RAG pipeline over AEMO market notices.
    Returns: {"answer": str, "sources": list, "chunk_count": int}
    """
    chunks = retrieve_chunks(question, top_k=top_k)
    context = format_context(chunks)

    response = llm.chat.completions.create(
        model=PT_ENDPOINT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n\n{context}\n\nQuestion: {question}"},
        ],
        max_tokens=512,
        temperature=0.1,
    )

    return {
        "answer":      response.choices[0].message.content,
        "sources":     chunks,
        "chunk_count": len(chunks),
    }


print("Functions registered — run Section 4 to test.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4: Test with AEMO questions (~10 min)
# MAGIC
# MAGIC Three questions covering typical AEMO operations scenarios. After each answer, check the **Sources used** output — this shows what the LLM actually read. If an answer looks wrong, the source list tells you whether the problem is retrieval (wrong chunks fetched) or generation (LLM misread good chunks). That distinction matters: they require different fixes.

# COMMAND ----------

# NOTE: Question 1 — LOR event lookup. Tests retrieval of reserve shortfall notices
# and whether the LLM correctly identifies the region and timing from the notice text.

q1 = "Were there any LOR2 or LOR3 events in Victoria in the last quarter? What caused them?"

r1 = rag_answer(q1)

print(f"Question : {q1}")
print(f"Chunks   : {r1['chunk_count']} notices retrieved\n")
print("Answer:")
print(r1["answer"])
print("\nSources used:")
for i, c in enumerate(r1["sources"], 1):
    print(f"  [{i}] {c.get('notice_id','')} — {c.get('notice_type','')} — {c.get('region_id','NEM-wide')} — score: {c.get('score',0):.3f}")

# COMMAND ----------

# NOTE: Question 2 — system normal notice. Tests whether the agent finds the
# resolution notice (system normal), not just the original event declaration.

q2 = "Was the reserve shortfall in South Australia resolved? When did AEMO issue the all-clear?"

r2 = rag_answer(q2)

print(f"Question : {q2}")
print(f"Chunks   : {r2['chunk_count']} notices retrieved\n")
print("Answer:")
print(r2["answer"])
print("\nSources used:")
for i, c in enumerate(r2["sources"], 1):
    print(f"  [{i}] {c.get('notice_id','')} — {c.get('notice_type','')} — {c.get('region_id','NEM-wide')} — score: {c.get('score',0):.3f}")

# COMMAND ----------

# NOTE: Question 3 — tests graceful failure. If no relevant notices exist,
# the agent should say so clearly rather than hallucinating an answer.

q3 = "What market interventions affected the Queensland interconnector this week?"

r3 = rag_answer(q3)

print(f"Question : {q3}")
print(f"Chunks   : {r3['chunk_count']} notices retrieved\n")
print("Answer:")
print(r3["answer"])
if r3["chunk_count"] == 0:
    print("\n✅ Correct — no relevant chunks found, agent said so rather than guessing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### What to look for
# MAGIC
# MAGIC | Observation | What it means | Fix |
# MAGIC |---|---|---|
# MAGIC | Answer cites notice IDs | LLM followed system prompt correctly | — |
# MAGIC | Answer says "not enough information" | No relevant chunks retrieved — correct behaviour | — |
# MAGIC | Answer mentions something not in sources | Hallucination | Lower `temperature` or tighten system prompt |
# MAGIC | Chunk score below 0.5 in sources | Retrieval returned noise | Raise `min_score` in `retrieve_chunks()` |
# MAGIC | Chunk count = 0 for a question you expect to work | VS index may not be synced, or phrasing too different from notice text | Check index sync status; rephrase query |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Core complete.** If you have time, continue to the extensions below.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🔵 Extension A: Add Genie for quantitative questions (~15 min)
# MAGIC
# MAGIC The RAG agent searches document text. It cannot answer *"What was the average spot price in VIC1 during the LOR event?"* — that needs a SQL query against the `spot_prices` table.
# MAGIC
# MAGIC Extension A adds Genie as a second source. You make both calls — Vector Search for context, Genie for data — then pass both results to the LLM in a single prompt. The LLM synthesises the answer.
# MAGIC
# MAGIC This is still **not** a ReAct loop: you decide which tools to call, not the LLM.
# MAGIC
# MAGIC | | Core RAG | Extension A (hybrid) | Extension B (ReAct) |
# MAGIC |---|---|---|---|
# MAGIC | Tools called | Vector Search only | Both, always | LLM picks which ones, when |
# MAGIC | LLM calls | 1 | 1 | 2–4 |
# MAGIC | Latency | ~2 sec | ~4 sec | ~8–12 sec |
# MAGIC | Handles quantitative questions | ❌ | ✅ | ✅ |

# COMMAND ----------

# NOTE: Connects to Genie MCP. Requires GENIE_SPACE_ID widget to be filled in.
# Skip if you did not complete Session 2 and do not have a Genie Space available.

if not GENIE_SPACE_ID:
    raise ValueError(
        "Genie Space ID not set — enter it in the 'genie_space_id' widget above.\n"
        "Find it in the browser URL when you open your Genie Space: .../genie/spaces/{id}"
    )

genie_mcp_url = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
genie_client  = DatabricksMCPClient(genie_mcp_url, ws)
genie_tools   = genie_client.list_tools()
GENIE_TOOL    = genie_tools[0].name

print(f"Connected  : {genie_mcp_url}")
print(f"Genie tool : {GENIE_TOOL}")

# COMMAND ----------

# NOTE: Defines ask_genie() and hybrid_answer(). Run this cell, then the test cell below.

HYBRID_SYSTEM_PROMPT = """You are an AEMO market operations analyst assistant.

You will receive two types of context:
  NOTICES — relevant AEMO market notices retrieved from a document index
  DATA    — quantitative results from a SQL query against live market data

Combine both sources to answer the question. Cite notice IDs where relevant.
If one source is empty or irrelevant, use the other. Never invent data.
Australian date format: DD/MM/YYYY. Numbers: 2 decimal places.
"""


def ask_genie(question: str) -> str:
    """Send a natural-language question to Genie and return the answer text."""
    result = genie_client.call_tool(GENIE_TOOL, {"question": question})
    if not result or result.get("isError"):
        return "(Genie query failed)"
    for item in result.get("content", []):
        if item.get("type") == "text":
            return item["text"][:1000]
    return "(no text in Genie response)"


def hybrid_answer(question: str, top_k: int = 4) -> dict:
    """RAG + Genie — document context plus live SQL data, synthesised by the LLM."""
    chunks     = retrieve_chunks(question, top_k=top_k)
    genie_text = ask_genie(question)

    response = llm.chat.completions.create(
        model=PT_ENDPOINT,
        messages=[
            {"role": "system", "content": HYBRID_SYSTEM_PROMPT},
            {"role": "user",   "content": (
                f"NOTICES:\n{format_context(chunks)}\n\n"
                f"DATA (from Genie):\n{genie_text}\n\n"
                f"Question: {question}"
            )},
        ],
        max_tokens=600,
        temperature=0.1,
    )

    return {
        "answer":     response.choices[0].message.content,
        "sources":    chunks,
        "genie_data": genie_text,
    }

print("hybrid_answer() registered.")

# COMMAND ----------

# NOTE: Tests the hybrid agent with a question that needs both notice text and price data.

hq = "What LOR events happened in VIC1, and what was the average spot price during those periods?"
hr = hybrid_answer(hq)

print(f"Question: {hq}\n")
print("Notices retrieved:")
for i, c in enumerate(hr["sources"], 1):
    print(f"  [{i}] {c.get('notice_id','')} — {c.get('notice_type','')} — score: {c.get('score',0):.3f}")
print(f"\nGenie data preview:\n{hr['genie_data'][:400]}")
print(f"\nAnswer:\n{hr['answer']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Reflection
# MAGIC
# MAGIC | What you control in Extension A | What changes in Extension B |
# MAGIC |---|---|
# MAGIC | You decide which tools to call (both, always) | The LLM decides which tools to call, and in what order |
# MAGIC | 1 LLM call (synthesis only) | 1 LLM call per reasoning step |
# MAGIC | Both tools called even if one is irrelevant | LLM skips tools it doesn't need |
# MAGIC | Easy to trace | More powerful but harder to predict |
# MAGIC
# MAGIC Extension B hands the tool-selection decision to the LLM via a loop. This is the right pattern when the question type is unpredictable or when you have many tools.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🔵 Extension B: LangGraph ReAct agent (~20 min)
# MAGIC
# MAGIC > *"ReAct = Reason + Act. The LLM reasons about what to do, acts by calling a tool, reads the result, then reasons again — until it has enough to answer."*
# MAGIC
# MAGIC In Extensions A and the core lab, you wrote code that decides which tools to call. In a ReAct agent the LLM sees the available tools and their descriptions, picks one, calls it, reads the result, and decides what to do next. This loop runs until the LLM signals it has a final answer.
# MAGIC
# MAGIC ```
# MAGIC User question
# MAGIC     ↓
# MAGIC LLM: "I need to check the notices first" → calls search_market_notices
# MAGIC     ↓ result
# MAGIC LLM: "Now I need the spot price data for that period" → calls query_nem_data
# MAGIC     ↓ result
# MAGIC LLM: "I have enough to answer" → final answer
# MAGIC ```
# MAGIC
# MAGIC `create_react_agent` from LangGraph builds this loop automatically. You provide a model and a list of tools — LangGraph handles the rest.
# MAGIC
# MAGIC ### 🖱️ UI: look at a RAG trace before running the ReAct cells
# MAGIC
# MAGIC 1. Go to **Experiments** (left sidebar, Machine Learning section)
# MAGIC 2. Open the experiment from Lab 01 (or the auto-created one for this notebook)
# MAGIC 3. Find a run from Section 4 of this lab and click into the trace
# MAGIC 4. You will see: one `vector_search` span → one `chat.completions` span
# MAGIC 5. After running the ReAct cells below, come back and compare — the ReAct trace shows multiple alternating LLM + tool spans

# COMMAND ----------

# NOTE: Run this — installs LangGraph and the Databricks LangChain integration.
%pip install "langgraph>=0.2" "langchain-databricks>=0.3" --quiet

# COMMAND ----------

# NOTE: Wraps the RAG retrieval and Genie calls as LangChain @tools so LangGraph
# can discover and invoke them. The docstring is what the LLM reads to decide
# when to use each tool — keep it descriptive and accurate.

import mlflow
from langchain_core.tools import tool
from langchain_databricks import ChatDatabricks
from langgraph.prebuilt import create_react_agent

mlflow.langchain.autolog()


@tool
def search_market_notices(query: str) -> str:
    """
    Search AEMO market notices using semantic similarity.
    Use for questions about LOR events, reserve shortfalls, market interventions,
    system normal declarations, and anything described in free-text notice content.
    Returns the top relevant notices with notice ID, type, region, and text.
    """
    chunks = retrieve_chunks(query, top_k=5)
    if not chunks:
        return "No relevant market notices found for this query."
    return format_context(chunks)


@tool
def query_nem_data(question: str) -> str:
    """
    Query live AEMO NEM market data using natural language (via Genie SQL).
    Use for quantitative questions: spot prices, dispatch volumes, settlement amounts,
    generator output, regional comparisons, and time-series trends.
    Returns a table of results.
    """
    return ask_genie(question)


tools = [search_market_notices, query_nem_data]
print(f"Tools registered: {[t.name for t in tools]}")

# COMMAND ----------

# NOTE: Creates the ReAct agent. ChatDatabricks connects to your in-region PT endpoint.
# The state_modifier is the system prompt — it tells the LLM how to use the tools.

react_model = ChatDatabricks(
    endpoint=PT_ENDPOINT,
    temperature=0.1,
    max_tokens=1024,
)

react_agent = create_react_agent(
    model=react_model,
    tools=tools,
    state_modifier=(
        "You are an AEMO market operations analyst. "
        "Use search_market_notices for questions about events, notices, and interventions. "
        "Use query_nem_data for quantitative questions about prices, volumes, and dispatch. "
        "For hybrid questions, use both tools. Cite notice IDs where relevant. "
        "Australian date format DD/MM/YYYY. Numbers to 2 decimal places."
    ),
)

print("ReAct agent ready.")

# COMMAND ----------

# NOTE: Runs the same three questions from Section 4 through the ReAct agent.
# Watch the "Tool call:" lines — the agent picks tools based on the question type.
# Compare how tool selection differs across the three questions.

with mlflow.start_run(run_name="react_agent_test"):
    for question in [
        "Were there any LOR2 or LOR3 events in Victoria? What was the average spot price during those events?",
        "Was the reserve shortfall in South Australia resolved? When?",
        "What market interventions affected the Queensland interconnector this week?",
    ]:
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print('='*60)

        response = react_agent.invoke({"messages": [("human", question)]})

        for msg in response["messages"]:
            role = getattr(msg, "type", type(msg).__name__)
            if role == "ai":
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        arg_preview = tc["args"].get("query") or tc["args"].get("question", "")
                        print(f"\n  Tool call : {tc['name']}('{arg_preview[:60]}')")
                else:
                    print(f"\n  Answer    :\n  {msg.content}")
            elif role == "tool":
                print(f"  Tool result preview: {str(msg.content)[:120]}...")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Compare the traces
# MAGIC
# MAGIC Go back to **Experiments** and open the two most recent traces side by side.
# MAGIC
# MAGIC | | RAG agent (Section 4) | ReAct agent (above) |
# MAGIC |---|---|---|
# MAGIC | Trace shape | 1 `vector_search` → 1 `chat` | Multiple `chat` + `tool` spans, interleaved |
# MAGIC | Total LLM calls | 1 | 2–4 depending on question |
# MAGIC | Total latency | ~2–3 sec | ~8–12 sec |
# MAGIC | Handles hybrid questions natively? | ❌ (Extension A workaround) | ✅ — picks both tools when needed |
# MAGIC | Handles "no data" questions? | ✅ | ✅ |
# MAGIC
# MAGIC **Rule of thumb:** default to RAG for document Q&A. Reach for ReAct when the question type is unpredictable or requires combining multiple data sources in a single answer.
# MAGIC
# MAGIC **Next:** Lab 04 deploys your agent as a Databricks App so business users can access it without a notebook.
