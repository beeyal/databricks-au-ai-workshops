# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 01 — BUILD: Your First MCP Agent (with Lakebase Memory)
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Session 4: Building AI Agents with MCP — Australian Energy Sector (Level 200)
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Lifecycle phase 1 of 5 &nbsp;•&nbsp; <strong>Build</strong> → Evaluate → Govern → Deploy → Improve
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>40 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Setup notebook run; PT endpoint READY
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All MCP + LLM: AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Model</strong><br>PT endpoint (in-region only)
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will build
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | MLflow experiment + MCP servers | Set up tracing, configure the 3 MCP servers | 8 min |
# MAGIC | 2 | LangGraph ReAct agent | `create_react_agent` + `ChatDatabricks` on the PT endpoint | 10 min |
# MAGIC | 3 | Run 3 AEMO questions | Genie, Vector Search, and UC Function routing | 10 min |
# MAGIC | 4 | Lakebase short-term memory | Store conversation turns in Lakebase Postgres | 8 min |
# MAGIC | 5 | Multi-turn follow-up | "...and what about NSW?" using memory | 4 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### The agent lifecycle
# MAGIC
# MAGIC This session follows one agent through five lifecycle phases, one lab each:
# MAGIC
# MAGIC ```
# MAGIC   Build  →  Evaluate  →  Govern  →  Deploy  →  Improve
# MAGIC   (here)     Lab 02      Lab 03    Lab 04     Lab 05  ──┐
# MAGIC     ▲                                                   │
# MAGIC     └────────────────── loop back ─────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### The ReAct pattern
# MAGIC
# MAGIC ```
# MAGIC User question → LLM reasons → picks a tool → calls it via MCP → observes result
# MAGIC     ↑___________________________ loop until enough info ______________________|
# MAGIC                        → final answer
# MAGIC ```
# MAGIC
# MAGIC `create_react_agent` from LangGraph builds this loop for you. All tool calls route through
# MAGIC `DatabricksMultiServerMCPClient`, which forwards each call to the correct Databricks MCP server.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #FF3621;">Residency rule (non-negotiable)</strong><br>
# MAGIC   The agent's LLM MUST be an in-region <strong>provisioned-throughput (PT) serving endpoint</strong>
# MAGIC   in <strong>Azure Australia East</strong> (default: <code>au_east_llm_inregion</code>).
# MAGIC   Pay-per-token / Foundation Model API endpoints are cross-geo and are <strong>forbidden</strong> for
# MAGIC   this workload — they route inference outside the region. This is the reason this workshop exists.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Install packages
# MAGIC If the workshop cluster does not already have these, install them (canonical Databricks form):

# COMMAND ----------

# MAGIC %pip install -q databricks-langchain "langgraph>=1.2" mlflow psycopg2-binary databricks-sdk nest_asyncio
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration
# MAGIC Set these widgets (they appear at the top after you run this cell), then re-run. The defaults
# MAGIC match the setup notebook, so usually you only touch two:
# MAGIC - **`pt_endpoint`** — your in-region provisioned-throughput endpoint from setup (default
# MAGIC   `au_east_llm_inregion`).
# MAGIC - **`genie_space_id`** — the AEMO Genie Space from Session 2. Find the ID in the Space's browser
# MAGIC   URL: `.../genie/spaces/<SPACE_ID>`. **Leave it blank** to run with just UC Functions + Vector
# MAGIC   Search — the agent still works, but the Genie question in Section 3 will be handled by another
# MAGIC   tool instead of Genie.

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo",    "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name (in-region)")
dbutils.widgets.text("vs_endpoint",    "workshop_vs",          "Vector Search endpoint")
dbutils.widgets.text("genie_space_id", "",                     "Genie Space ID (optional)")
dbutils.widgets.text("mlflow_experiment",
                     "/Shared/session4-aemo-agent",            "MLflow experiment path")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
VS_ENDPOINT    = dbutils.widgets.get("vs_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
MLFLOW_EXPERIMENT = dbutils.widgets.get("mlflow_experiment")

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

# MCP server URLs — all workspace-local, all AU East.
UC_MCP_URL    = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"
GENIE_MCP_URL = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}" if GENIE_SPACE_ID else None
VS_MCP_URL    = f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA_AEMO}/aemo_market_notices_index"

print("Configuration loaded.")
print(f"  HOST           : {HOST}")
print(f"  CATALOG.SCHEMA : {CATALOG}.{SCHEMA_AEMO}")
print(f"  PT_ENDPOINT    : {PT_ENDPOINT}  (must be in-region PT)")
print(f"  VS_ENDPOINT    : {VS_ENDPOINT}")
print(f"  GENIE_SPACE_ID : {GENIE_SPACE_ID or '(not set — agent runs UC + Vector Search only)'}")
print(f"  UC MCP URL     : {UC_MCP_URL}")
print(f"  VS MCP URL     : {VS_MCP_URL}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — MLflow experiment and the 3 MCP servers (8 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Enable MLflow tracing
# MAGIC `mlflow.langchain.autolog()` instruments LangGraph automatically: every LLM call, tool call,
# MAGIC and agent step is captured as a trace span you can inspect in the Experiments UI.

# COMMAND ----------

import mlflow

mlflow.langchain.autolog()
experiment = mlflow.set_experiment(MLFLOW_EXPERIMENT)

print("MLflow autologging enabled for LangChain/LangGraph.")
print(f"  Experiment : {experiment.name}")
print(f"  ID         : {experiment.experiment_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Configure the three MCP servers
# MAGIC All three are workspace-local Databricks MCP servers running in Australia East:
# MAGIC UC Functions (deterministic tools), Genie (NL-to-SQL), and Vector Search (semantic retrieval).

# COMMAND ----------

from databricks_langchain import DatabricksMCPServer, DatabricksMultiServerMCPClient

uc_server = DatabricksMCPServer(
    name="aemo-uc-tools",
    url=UC_MCP_URL,
    timeout=30.0,
    handle_tool_error=True,
)

vs_server = DatabricksMCPServer(
    name="aemo-market-notices",
    url=VS_MCP_URL,
    timeout=30.0,
    handle_tool_error=True,
)

genie_server = None
if GENIE_MCP_URL:
    genie_server = DatabricksMCPServer(
        name="aemo-nem-genie",
        url=GENIE_MCP_URL,
        timeout=60.0,
        handle_tool_error=True,
    )

all_servers = [uc_server, vs_server] + ([genie_server] if genie_server else [])

print(f"MCP servers configured ({len(all_servers)}):")
for s in all_servers:
    print(f"  {s.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Build the LangGraph ReAct agent (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — System prompt
# MAGIC The prompt grounds the agent in AEMO/NEM context, tells it which tool to use when, and
# MAGIC requires source citations. Tool descriptions (defined in Unity Catalog and Genie) do most of
# MAGIC the routing work — the prompt reinforces the conventions.

# COMMAND ----------

AEMO_SYSTEM_PROMPT = """You are the AEMO Operations Assistant, a technical AI agent for the
National Electricity Market (NEM) operated by the Australian Energy Market Operator (AEMO).

## Domain rules
- Always use NEM region codes with the '1' suffix: NSW1, VIC1, QLD1, SA1, TAS1
- Prices are in $/MWh; generation in MW; energy in MWh; settlement in AUD
- Market Price Cap = $15,300/MWh; price floor = -$1,000/MWh (negative = oversupply)
- "Price spike" = spot price (rrp) > $300/MWh
- LOR1 = reserve watch, LOR2 = shortfall threatened, LOR3 = imminent critical shortage

## Tool selection
- Genie tool: trends, averages, totals, "how many", "show me all..." over a time window
- UC Function tools (calculate_peak_demand, get_region_summary, lookup_duid_info):
  deterministic calculations and specific generator/region lookups
- Vector Search: market notices, LOR events, bulletins, "were there any notices about..."

## Citations
Cite every factual claim: "(Source: NEM data via Genie)", "(Source: <function> function)",
or "(Source: market notices)". Add: "Note: workshop dataset, not live NEM conditions."

## On failure
Explain what you tried and why it failed. Never invent or estimate numbers.
"""

print(f"System prompt ready ({len(AEMO_SYSTEM_PROMPT):,} characters).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Build and run helper
# MAGIC `ChatDatabricks(endpoint=PT_ENDPOINT)` points the agent at the **in-region PT endpoint**.
# MAGIC The `async with` block manages the MCP connection lifecycle (connections close on exit).

# COMMAND ----------

import asyncio
import nest_asyncio
nest_asyncio.apply()  # allow asyncio.run() inside the notebook's running event loop
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import ChatDatabricks

# In-region PT endpoint ONLY — never a pay-per-token / cross-geo model.
llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=4096)


async def run_agent(question: str, history: list | None = None, run_name: str = "agent_run") -> str:
    """Build the ReAct agent with all MCP servers and answer one question.

    `history` is an optional list of prior LangChain messages (HumanMessage/AIMessage)
    that is prepended so the agent has conversational context. Section 4 wires this to Lakebase.
    """
    messages = list(history or []) + [HumanMessage(content=question)]
    # langchain-mcp-adapters >=0.1.0 removed context-manager support on the client.
    multi_client = DatabricksMultiServerMCPClient(all_servers)
    tools = await multi_client.get_tools()
    agent = create_react_agent(model=llm, tools=tools, prompt=AEMO_SYSTEM_PROMPT)
    with mlflow.start_run(run_name=run_name, nested=True):
        result = await agent.ainvoke({"messages": messages})
    return result["messages"][-1].content


print("Agent helper ready. LLM endpoint:", PT_ENDPOINT)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Run 3 AEMO questions (10 min)
# MAGIC </div>
# MAGIC
# MAGIC | # | Question | Expected tool |
# MAGIC |---|----------|---------------|
# MAGIC | Q1 | Average spot price in VIC1 (aggregation) | Genie MCP |
# MAGIC | Q2 | Market notices about LOR events (semantic search) | Vector Search MCP |
# MAGIC | Q3 | Peak demand for QLD1 (deterministic calc) | UC Function MCP |

# COMMAND ----------

q1 = ("What was the average spot price in VIC1 for the most recent full day in the dataset? "
      "Express it in $/MWh.")
print(f"Q1: {q1}\nExpected: Genie\n")

with mlflow.start_run(run_name="lab01_q1_avg_price"):
    answer_q1 = asyncio.run(run_agent(q1, run_name="q1_avg_price"))

print("=" * 65)
print("AGENT ANSWER — Q1")
print("=" * 65)
print(answer_q1)

# COMMAND ----------

q2 = ("Search the market notices for any LOR2 or LOR3 events. Summarise the top notices — "
      "include the notice type and a short description of each.")
print(f"Q2: {q2[:70]}...\nExpected: Vector Search\n")

with mlflow.start_run(run_name="lab01_q2_lor_notices"):
    answer_q2 = asyncio.run(run_agent(q2, run_name="q2_lor_notices"))

print("=" * 65)
print("AGENT ANSWER — Q2")
print("=" * 65)
print(answer_q2)

# COMMAND ----------

q3 = "Calculate the peak demand for QLD1 across the dataset. Express it in MW."
print(f"Q3: {q3}\nExpected: UC Function (calculate_peak_demand)\n")

with mlflow.start_run(run_name="lab01_q3_peak_demand"):
    answer_q3 = asyncio.run(run_agent(q3, run_name="q3_peak_demand"))

print("=" * 65)
print("AGENT ANSWER — Q3")
print("=" * 65)
print(answer_q3)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Sections 1-3</strong><br>
# MAGIC   You have a working ReAct agent that routes questions to the correct MCP server, all running
# MAGIC   in AU East against the PT endpoint. Open <strong>Machine Learning → Experiments →
# MAGIC   /Shared/session4-aemo-agent → Traces</strong> to see each tool call. Next: give the agent memory.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Lakebase short-term (conversation) memory (8 min)
# MAGIC </div>
# MAGIC
# MAGIC The agent above is stateless — each question starts fresh. To handle follow-ups like
# MAGIC *"...and what about NSW?"* the agent needs **short-term memory**: the recent turns of the
# MAGIC current conversation.
# MAGIC
# MAGIC We store turns in **Lakebase** — Databricks-managed Postgres (OLTP) that lives in your
# MAGIC workspace region (AU East). Lakebase is the right home for low-latency conversational state:
# MAGIC single-row reads/writes per turn, keyed by `session_id`.
# MAGIC
# MAGIC > **Facilitator note / verify during integration:** the connection block below uses the
# MAGIC > Databricks SDK to generate a short-lived Postgres credential for a Lakebase database
# MAGIC > instance. Confirm the Lakebase instance name and that the workshop identity can generate a
# MAGIC > database credential in your environment. If Lakebase is not provisioned, the fallback cell
# MAGIC > (4.4) keeps memory in a Delta table so the lab still runs.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Connect to Lakebase Postgres

# COMMAND ----------

dbutils.widgets.text("lakebase_instance", "workshop-lakebase", "Lakebase instance name")
dbutils.widgets.text("lakebase_database", "databricks_postgres", "Lakebase database name")
LAKEBASE_INSTANCE = dbutils.widgets.get("lakebase_instance")
LAKEBASE_DATABASE = dbutils.widgets.get("lakebase_database")

USE_LAKEBASE = True
pg_conn = None
try:
    import psycopg2

    instance = ws.database.get_database_instance(name=LAKEBASE_INSTANCE)
    # Generate a short-lived Postgres OAuth credential (token) for this instance.
    cred = ws.database.generate_database_credential(
        instance_names=[LAKEBASE_INSTANCE],
        request_id="session4-lab01",
    )
    pg_conn = psycopg2.connect(
        host=instance.read_write_dns,
        port=5432,
        dbname=LAKEBASE_DATABASE,
        user=ws.current_user.me().user_name,
        password=cred.token,
        sslmode="require",
    )
    pg_conn.autocommit = True
    print(f"Connected to Lakebase instance '{LAKEBASE_INSTANCE}' (AU East, in-region).")
except Exception as e:
    USE_LAKEBASE = False
    print(f"Lakebase not available ({type(e).__name__}: {e}).")
    print("Falling back to a Delta table for memory — see cell 4.4. Lab still runs.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Create the memory table
# MAGIC `app_memory.conversation_turns(session_id, turn_index, role, content, ts)` — one row per
# MAGIC message (user or assistant), ordered within a session by `turn_index`.

# COMMAND ----------

if USE_LAKEBASE:
    with pg_conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS app_memory;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_memory.conversation_turns (
                session_id  TEXT        NOT NULL,
                turn_index  INTEGER     NOT NULL,
                role        TEXT        NOT NULL,
                content     TEXT        NOT NULL,
                ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (session_id, turn_index)
            );
        """)
    print("Lakebase table app_memory.conversation_turns is ready.")
else:
    print("Skipping Lakebase DDL — using Delta fallback (cell 4.4).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Memory helpers: load prior history, save a turn

# COMMAND ----------

def load_history_lakebase(session_id: str) -> list:
    """Return prior turns for a session as LangChain messages, oldest first."""
    msgs = []
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT role, content FROM app_memory.conversation_turns "
            "WHERE session_id = %s ORDER BY turn_index ASC;",
            (session_id,),
        )
        for role, content in cur.fetchall():
            msgs.append(HumanMessage(content=content) if role == "user"
                        else AIMessage(content=content))
    return msgs


def next_turn_index_lakebase(session_id: str) -> int:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(turn_index), -1) + 1 FROM app_memory.conversation_turns "
            "WHERE session_id = %s;",
            (session_id,),
        )
        return cur.fetchone()[0]


def save_turn_lakebase(session_id: str, turn_index: int, role: str, content: str) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO app_memory.conversation_turns (session_id, turn_index, role, content) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (session_id, turn_index) DO NOTHING;",
            (session_id, turn_index, role, content),
        )


print("Lakebase memory helpers defined." if USE_LAKEBASE else "Lakebase helpers defined (unused — fallback active).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Delta fallback (only used if Lakebase is unavailable)
# MAGIC Keeps the same interface so the rest of the lab is identical. In production you would always
# MAGIC use Lakebase for conversational state — Delta is analytical, not an OLTP store.

# COMMAND ----------

if not USE_LAKEBASE:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.app_memory")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.app_memory.conversation_turns (
            session_id STRING, turn_index INT, role STRING, content STRING, ts TIMESTAMP
        )
    """)

    def load_history_lakebase(session_id: str) -> list:
        rows = spark.sql(
            f"SELECT role, content FROM {CATALOG}.app_memory.conversation_turns "
            f"WHERE session_id = '{session_id}' ORDER BY turn_index ASC"
        ).collect()
        return [HumanMessage(content=r["content"]) if r["role"] == "user"
                else AIMessage(content=r["content"]) for r in rows]

    def next_turn_index_lakebase(session_id: str) -> int:
        row = spark.sql(
            f"SELECT COALESCE(MAX(turn_index), -1) + 1 AS n "
            f"FROM {CATALOG}.app_memory.conversation_turns WHERE session_id = '{session_id}'"
        ).collect()[0]
        return int(row["n"])

    def save_turn_lakebase(session_id: str, turn_index: int, role: str, content: str) -> None:
        safe = content.replace("'", "''")
        spark.sql(
            f"INSERT INTO {CATALOG}.app_memory.conversation_turns "
            f"VALUES ('{session_id}', {turn_index}, '{role}', '{safe}', current_timestamp())"
        )

    print("Delta fallback memory helpers active.")
else:
    print("Lakebase active — Delta fallback not used.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 — Wrap the agent so each turn loads then saves memory

# COMMAND ----------

async def chat(session_id: str, question: str, run_name: str = "memory_turn") -> str:
    """One conversational turn: load prior history → answer with context → persist both messages."""
    history = load_history_lakebase(session_id)
    answer = await run_agent(question, history=history, run_name=run_name)

    idx = next_turn_index_lakebase(session_id)
    save_turn_lakebase(session_id, idx, "user", question)
    save_turn_lakebase(session_id, idx + 1, "assistant", answer)
    return answer


print("Memory-wrapped chat() ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 5 — Multi-turn follow-up (4 min)
# MAGIC </div>
# MAGIC
# MAGIC Turn 1 establishes context (VIC1, a specific day). Turn 2 is a bare follow-up —
# MAGIC *"...and what about NSW?"* — that only resolves if the agent remembers turn 1.

# COMMAND ----------

import uuid
session_id = f"lab01-{uuid.uuid4().hex[:8]}"
print(f"Session: {session_id}\n")

# Turn 1 — establishes VIC1 + the day.
turn1 = "What was the average spot price in VIC1 for the most recent full day? In $/MWh."
print(f"[turn 1] user: {turn1}")
ans1 = asyncio.run(chat(session_id, turn1, run_name="lab01_mem_turn1"))
print(f"[turn 1] agent: {ans1}\n")

# COMMAND ----------

# Turn 2 — bare follow-up. Only works if the agent loaded turn 1 from memory.
turn2 = "...and what about NSW?"
print(f"[turn 2] user: {turn2}")
ans2 = asyncio.run(chat(session_id, turn2, run_name="lab01_mem_turn2"))
print(f"[turn 2] agent: {ans2}\n")
print("If turn 2 correctly answered for NSW1 for the SAME day as turn 1, memory works.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.1 — Inspect what was stored

# COMMAND ----------

if USE_LAKEBASE:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT turn_index, role, LEFT(content, 80) FROM app_memory.conversation_turns "
            "WHERE session_id = %s ORDER BY turn_index;",
            (session_id,),
        )
        rows = cur.fetchall()
    print(f"Stored turns for {session_id}:")
    for idx, role, content in rows:
        print(f"  [{idx}] {role:9s} {content}")
else:
    display(spark.sql(
        f"SELECT turn_index, role, LEFT(content, 80) AS content "
        f"FROM {CATALOG}.app_memory.conversation_turns "
        f"WHERE session_id = '{session_id}' ORDER BY turn_index"
    ))

# COMMAND ----------

if USE_LAKEBASE and pg_conn is not None:
    pg_conn.close()
    print("Lakebase connection closed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 01 complete — BUILD ✅</strong><br>
# MAGIC   You built a LangGraph ReAct agent on the in-region PT endpoint, wired in three Databricks MCP
# MAGIC   servers, and added Lakebase short-term memory so the agent handles multi-turn follow-ups.
# MAGIC   <br><br>
# MAGIC   <strong>Next — Lab 02 (EVALUATE):</strong> measure answer quality with LLM-judge metrics against
# MAGIC   a golden dataset, using the same in-region PT endpoint as the judge.
# MAGIC </div>
