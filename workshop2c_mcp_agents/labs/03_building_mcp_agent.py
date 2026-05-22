# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 03: Building a Multi-Tool ReAct Agent
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Energy Sector
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     LangGraph ReAct agent with all 3 MCP servers, 4 AEMO test questions,
# MAGIC     MLflow trace inspection, and a production deployment preview.
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>45 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01 and 02 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All MCP endpoints: AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Model</strong><br>Claude Sonnet 4.6 (PT endpoint)
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will build
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | LangGraph ReAct Agent Setup | MLflow experiment, system prompt, ChatDatabricks, agent construction | 15 min |
# MAGIC | 2 | Test with 4 AEMO Questions | UC Function, Vector Search, Genie, and multi-tool chain questions | 20 min |
# MAGIC | 3 | View Traces in MLflow | Navigate Experiments UI, read trace waterfall, share with team | 10 min |
# MAGIC | Bonus | Claude Desktop Config | Connect your laptop directly to the same MCP servers | open-ended |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ReAct pattern refresher
# MAGIC
# MAGIC The agent uses **ReAct** (Reason + Act), a loop that continues until the LLM decides
# MAGIC it has enough information to give a final answer:
# MAGIC
# MAGIC ```
# MAGIC ┌─── ReAct loop ─────────────────────────────────────────────────────────────┐
# MAGIC │                                                                             │
# MAGIC │  User question → LLM reasons → picks a tool → calls it via MCP            │
# MAGIC │                      ↑                                 │                   │
# MAGIC │                      └────── receives result ──────────┘                   │
# MAGIC │                                                                             │
# MAGIC │  LLM reasons again:  "I have the price data. Do I need more?"              │
# MAGIC │    → YES: picks another tool → calls it → receives result → reasons again  │
# MAGIC │    → NO:  synthesises all results → returns final answer                   │
# MAGIC │                                                                             │
# MAGIC │  Number of loops: 1 for simple questions, 3–5 for compound questions.      │
# MAGIC │  Max iterations: configurable (default 10 in LangGraph)                    │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC `create_react_agent` from LangGraph builds this loop automatically.
# MAGIC All tool calls go through the `DatabricksMultiServerMCPClient` which routes
# MAGIC each call to the correct MCP server.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration (loads Lab 02 values)

# COMMAND ----------

import json
from pathlib import Path

_config_path = Path("/tmp/workshop2c_config.json")
_saved = json.loads(_config_path.read_text()) if _config_path.exists() else {}

dbutils.widgets.text("catalog",         _saved.get("CATALOG",        "workshop_au"),
                                                                       "Catalog name")
dbutils.widgets.text("schema_aemo",     _saved.get("SCHEMA_AEMO",    "aemo"),
                                                                       "AEMO schema name")
dbutils.widgets.text("pt_endpoint",     _saved.get("PT_ENDPOINT",    "au_east_llm_inregion"),
                                                                       "PT endpoint name")
dbutils.widgets.text("genie_space_id",  _saved.get("GENIE_SPACE_ID", "FILL_IN"),
                                                                       "Genie Space ID")
dbutils.widgets.text("vs_index",        _saved.get("VS_INDEX_NAME",
                     "workshop_au.aemo.aemo_market_notices_index"),    "VS index (3-part name)")
dbutils.widgets.text("mlflow_experiment",
                     "/Shared/workshop2c-aemo-operations-agent",       "MLflow experiment path")

CATALOG           = dbutils.widgets.get("catalog")
SCHEMA_AEMO       = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT       = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID    = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME     = dbutils.widgets.get("vs_index")
MLFLOW_EXPERIMENT = dbutils.widgets.get("mlflow_experiment")

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

vs_parts  = VS_INDEX_NAME.split(".")
VS_MCP_URL = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"

print("Configuration loaded.")
print(f"  HOST              : {HOST}")
print(f"  CATALOG.SCHEMA    : {CATALOG}.{SCHEMA_AEMO}")
print(f"  PT_ENDPOINT       : {PT_ENDPOINT}")
print(f"  GENIE_SPACE_ID    : {GENIE_SPACE_ID}")
print(f"  VS_INDEX_NAME     : {VS_INDEX_NAME}")
print(f"  MLflow experiment : {MLFLOW_EXPERIMENT}")

if GENIE_SPACE_ID == "FILL_IN":
    print("\nNOTE: GENIE_SPACE_ID not set — agent will run with UC Functions + Vector Search only.")
    print("      Questions 3 and 4 in Section 2 require a configured Genie Space for full results.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Configuration loaded.
# MAGIC   HOST              : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC   CATALOG.SCHEMA    : workshop_au.aemo
# MAGIC   PT_ENDPOINT       : au_east_llm_inregion
# MAGIC   GENIE_SPACE_ID    : 01jxyz123abc456
# MAGIC   VS_INDEX_NAME     : workshop_au.aemo.aemo_market_notices_index
# MAGIC   MLflow experiment : /Shared/workshop2c-aemo-operations-agent
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — LangGraph ReAct Agent Setup (15 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — Create the MLflow Experiment in the UI
# MAGIC </div>
# MAGIC
# MAGIC Before running agent code, create the MLflow experiment so traces are visible
# MAGIC with a meaningful name. You can do this in the UI or let code create it automatically —
# MAGIC but the UI path shows you where to find traces later.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar) → Experiments
# MAGIC
# MAGIC ┌─── Experiments ───────────────────────────────────────────────────────────┐
# MAGIC │  [+ Create experiment]                               Search [          ] │
# MAGIC │  ──────────────────────────────────────────────────────────────────────  │
# MAGIC │                                                                          │
# MAGIC │  Shared experiments (in /Shared/...)                                     │
# MAGIC │    workshop2c-aemo-operations-agent    ← will appear here after creation │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Option A — Create via UI now:
# MAGIC   1. Click [+ Create experiment]
# MAGIC   2. Name: workshop2c-aemo-operations-agent
# MAGIC   3. Location: /Shared/
# MAGIC   4. Click [Create]
# MAGIC
# MAGIC Option B — Let the code create it (next cell does this automatically)
# MAGIC   mlflow.set_experiment() creates the experiment if it does not exist.
# MAGIC
# MAGIC Either way, after running the agent you will return to this page to inspect traces.
# MAGIC ```
# MAGIC
# MAGIC **Also check the PT endpoint is running:**
# MAGIC ```
# MAGIC Navigate: Machine Learning → Serving → [find au_east_llm_inregion]
# MAGIC
# MAGIC Status should show: Ready (green)
# MAGIC Model: claude-sonnet-4-6 (or similar — the model behind the PT endpoint)
# MAGIC
# MAGIC If status is not Ready, ask the workshop facilitator.
# MAGIC All inference for the agent will use this endpoint — no data leaves AU East.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Enable MLflow autologging for LangChain/LangGraph

# COMMAND ----------

import mlflow

# mlflow.langchain.autolog() instruments LangGraph automatically —
# every LLM call, tool call, and agent step is captured as a trace span.
# No manual instrumentation code needed anywhere in the agent.
mlflow.langchain.autolog()

# Set or create the experiment where all runs and traces are stored.
# mlflow.set_experiment() is idempotent — safe to call multiple times.
experiment = mlflow.set_experiment(MLFLOW_EXPERIMENT)

print(f"MLflow autologging enabled for LangChain/LangGraph.")
print()
print(f"Experiment name : {experiment.name}")
print(f"Experiment ID   : {experiment.experiment_id}")
print(f"Artifact URI    : {experiment.artifact_location}")
print()
print("Every agent run will produce a trace visible in:")
print(f"  Machine Learning → Experiments → {experiment.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MLflow autologging enabled for LangChain/LangGraph.
# MAGIC
# MAGIC Experiment name : /Shared/workshop2c-aemo-operations-agent
# MAGIC Experiment ID   : 8675309abcdef
# MAGIC Artifact URI    : dbfs:/databricks/mlflow-tracking/8675309abcdef
# MAGIC
# MAGIC Every agent run will produce a trace visible in:
# MAGIC   Machine Learning → Experiments → /Shared/workshop2c-aemo-operations-agent
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Configure the MCP servers
# MAGIC
# MAGIC Same server configs as Lab 02. We re-declare them here so this notebook
# MAGIC is self-contained — you can run Lab 03 independently after Labs 01 and 02.

# COMMAND ----------

from databricks_langchain import DatabricksMCPServer, DatabricksMultiServerMCPClient

# Server 1: UC Functions
uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG,
    schema=SCHEMA_AEMO,
    name="aemo-uc-tools",
    timeout=30.0,
    handle_tool_error=True,
)

# Server 2: Genie Space (skip if not configured)
genie_server = None
if GENIE_SPACE_ID != "FILL_IN":
    genie_server = DatabricksMCPServer(
        name="aemo-nem-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0,
        handle_tool_error=True,
    )

# Server 3: Vector Search
vs_server = DatabricksMCPServer(
    name="aemo-market-notices",
    url=VS_MCP_URL,
    timeout=30.0,
    handle_tool_error=True,
)

# Build the active server list
all_servers = [uc_server]
if genie_server:
    all_servers.append(genie_server)
all_servers.append(vs_server)

print(f"MCP servers configured ({len(all_servers)}):")
for s in all_servers:
    print(f"  {s.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MCP servers configured (3):
# MAGIC   aemo-uc-tools
# MAGIC   aemo-nem-genie
# MAGIC   aemo-market-notices
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Write the system prompt
# MAGIC
# MAGIC The system prompt (`state_modifier` in LangGraph) is the most important factor in
# MAGIC agent answer quality. A good system prompt for a regulated-industry agent:
# MAGIC
# MAGIC - Defines the agent's role and the user's context
# MAGIC - Lists domain-specific terms and their meanings
# MAGIC - Specifies preferred units, date formats, and rounding
# MAGIC - Tells the agent when to use each tool (positive and negative examples)
# MAGIC - Sets citation requirements (always say where the data came from)
# MAGIC - Defines what to do when data is missing or tool calls fail

# COMMAND ----------

AEMO_SYSTEM_PROMPT = """You are the AEMO Operations Assistant, a technical AI agent for the
National Electricity Market (NEM) operated by the Australian Energy Market Operator (AEMO).

Your users are NEM market participants (generators, retailers) and AEMO operations staff.
You help them answer questions about NEM dispatch, spot prices, generator output,
market notices, and AER/AEMO regulatory requirements.

## Domain rules

- Always use NEM region codes: NSW1, VIC1, QLD1, SA1, TAS1
  (not "Victoria" or "VIC" alone — always append the digit)
- Express prices in $/MWh (not cents, not kWh prices)
- Express generation in MW (megawatts) and energy in MWh (megawatt-hours)
- The Market Price Cap (MPC) is $14,000/MWh — the NEM maximum spot price
- A "price spike" means a dispatch interval where spot price > $300/MWh
- A "LOR" is a Lack of Reserve condition declared by AEMO when reserve margin is low
  LOR1 = forecast reserve below Threshold; LOR2 = actual reserve below Threshold;
  LOR3 = load shedding imminent
- "Yesterday" = the most recent complete day in the dataset (not necessarily calendar yesterday)

## Tool selection guidance

Use the Genie tool (ask_aemo_nem_operations) when:
  - The user asks about trends, averages, or totals over a time window
  - The user asks "how many", "what was the average", "show me all intervals where..."
  - The question requires filtering or aggregating rows from the NEM tables

Use UC Function tools (workshop_au__aemo__*) when:
  - The user asks about a specific region+date combination
  - You need a calculated summary result (peak price, dispatch total)
  - The question involves a DUID lookup

Use the Vector Search tool (search_aemo_market_notices_index) when:
  - The user asks about market notices, LOR events, or AEMO bulletins
  - The user asks "were there any notices about...", "find notices mentioning..."
  - The question involves policy documents or regulatory guidance

## Citation requirements

Every factual claim MUST cite its source:
  - For Genie results: "(Source: NEM dispatch data via Genie)"
  - For UC function results: "(Source: calculate_peak_demand function)"
  - For Vector Search results: "(Source: market notices, notice ID [ID])"

## Data freshness notice

Always include this note in answers that reference historical data:
"Note: This data reflects the workshop dataset and may not represent live NEM conditions."

## When a tool call fails

If a tool returns an error:
1. Explain what you tried to retrieve and why it failed
2. Offer to answer with a more general approach or different tool
3. Do not make up or estimate numbers — AEMO data must be cited
"""

print(f"System prompt ready.")
print(f"Length: {len(AEMO_SYSTEM_PROMPT):,} characters")
print()
print("Key sections:")
print("  Domain rules   : region codes, units, price definitions")
print("  Tool selection : when to use each MCP server (positive + negative)")
print("  Citations      : every fact must name its source tool")
print("  Error handling : no estimated values, always acknowledge failures")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC System prompt ready.
# MAGIC Length: 1,847 characters
# MAGIC
# MAGIC Key sections:
# MAGIC   Domain rules   : region codes, units, price definitions
# MAGIC   Tool selection : when to use each MCP server (positive + negative)
# MAGIC   Citations      : every fact must name its source tool
# MAGIC   Error handling : no estimated values, always acknowledge failures
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Build the LangGraph ReAct agent

# COMMAND ----------

import asyncio
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import ChatDatabricks

# ChatDatabricks connects to your in-region PT endpoint.
# temperature=0.0 gives deterministic, reproducible answers for operations data.
# max_tokens=4096 allows detailed multi-part answers for compound questions.
llm = ChatDatabricks(
    endpoint=PT_ENDPOINT,
    temperature=0.0,
    max_tokens=4096,
)

print(f"LLM endpoint : {PT_ENDPOINT}")
print(f"Temperature  : 0.0  (deterministic)")
print(f"Max tokens   : 4096")
print()

async def build_and_run_agent(question: str, run_name: str = "agent_run") -> str:
    """
    Builds the ReAct agent with all configured MCP servers, runs one question,
    and returns the final answer string.

    The async with block manages MCP connection lifecycle:
      - Connections open when the block starts
      - All tool calls during the run use these open connections
      - Connections close when the block exits (even on exception)

    mlflow.start_run() captures the full ReAct trace including:
      - LLM inputs and outputs for each reasoning step
      - Tool calls: which tool, what arguments, what the MCP returned
      - Total token usage and latency
    """
    async with DatabricksMultiServerMCPClient(all_servers) as multi_client:
        tools = await multi_client.get_tools()

        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=AEMO_SYSTEM_PROMPT,
        )

        with mlflow.start_run(run_name=run_name, nested=True):
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=question)]}
            )

    # The last message in the state is the final answer
    return result["messages"][-1].content


print("Agent builder function ready.")
print()
print("What happens when build_and_run_agent() is called:")
print("  1. Open connections to all MCP servers")
print("  2. Collect tool list from all servers")
print("  3. Build LangGraph ReAct agent with those tools")
print("  4. Start MLflow run (traces appear in the Experiments UI)")
print("  5. Invoke agent with user question")
print("  6. Agent loops: reason → pick tool → call → receive result → reason again")
print("  7. When agent has enough info → return final answer")
print("  8. MLflow run ends (trace is saved)")
print("  9. MCP connections closed")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC LLM endpoint : au_east_llm_inregion
# MAGIC Temperature  : 0.0  (deterministic)
# MAGIC Max tokens   : 4096
# MAGIC
# MAGIC Agent builder function ready.
# MAGIC
# MAGIC What happens when build_and_run_agent() is called:
# MAGIC   1. Open connections to all MCP servers
# MAGIC   2. Collect tool list from all servers
# MAGIC   ...
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 — Verify the agent with a single warm-up question

# COMMAND ----------

# A simple warm-up question to confirm the agent works end-to-end
# before running the more complex AEMO questions in Section 2.

warmup_q = "What NEM regions are covered in the dataset and what tables are available?"

print(f"Warm-up question: {warmup_q}")
print()
print("Running agent...")
print()

with mlflow.start_run(run_name="lab03_warmup"):
    warmup_answer = asyncio.run(build_and_run_agent(warmup_q, run_name="warmup"))

print("=" * 65)
print("AGENT ANSWER (warm-up):")
print("=" * 65)
print(warmup_answer)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Warm-up question: What NEM regions are covered in the dataset...
# MAGIC Running agent...
# MAGIC
# MAGIC =================================================================
# MAGIC AGENT ANSWER (warm-up):
# MAGIC =================================================================
# MAGIC The AEMO NEM Operations dataset covers all five mainland NEM regions
# MAGIC plus Tasmania: NSW1, VIC1, QLD1, SA1, and TAS1.
# MAGIC
# MAGIC The following tables are available:
# MAGIC   - spot_prices: 5-minute dispatch interval spot prices by region
# MAGIC   - dispatch_intervals: Generator dispatch targets and actual output by DUID
# MAGIC   - market_notices: Official AEMO bulletins about system conditions
# MAGIC
# MAGIC (Source: NEM dispatch data via Genie)
# MAGIC
# MAGIC Note: This data reflects the workshop dataset and may not represent
# MAGIC live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC The agent correctly cited its source (Genie) and included the data freshness disclaimer
# MAGIC from the system prompt — confirming the prompt is being applied.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 1 complete</strong><br>
# MAGIC   MLflow autologging is on, the experiment exists, the system prompt is defined,
# MAGIC   and the agent responded to a warm-up question. Traces are now appearing in the
# MAGIC   Experiments UI. Section 2 runs four AEMO-specific test questions.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Test with 4 AEMO Questions (20 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Each question is designed to exercise a different part of the agent:
# MAGIC
# MAGIC | # | Question | Expected tool | Why this question |
# MAGIC |---|----------|--------------|-------------------|
# MAGIC | Q1 | Average spot price in VIC1 yesterday | Genie MCP | Data aggregation over time window |
# MAGIC | Q2 | Market notices about constraint issues in NSW1 | Vector Search MCP | Semantic document search |
# MAGIC | Q3 | Peak demand calculation for QLD1 | UC Function MCP | Deterministic calculation |
# MAGIC | Q4 | Price spikes above $1000 in SA1 AND dispatched generators | Genie + UC Function | Multi-tool chain |
# MAGIC
# MAGIC For each question: the expected tool selection, success criteria, and how to verify
# MAGIC the answer is correct.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Question 1: Average spot price via Genie MCP

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Run Q1 — Set up side-by-side with the Genie Space
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Open the Genie Space in a separate browser tab:
# MAGIC
# MAGIC   Left sidebar → Genie → AEMO NEM Operations → [Chat]
# MAGIC
# MAGIC   Ask Genie the SAME question manually:
# MAGIC   "What was the average spot price in VIC1 for the last available day?"
# MAGIC
# MAGIC   Compare: the agent's answer (below) should match Genie's direct answer.
# MAGIC   If they differ, it may mean the agent routed to the wrong tool.
# MAGIC
# MAGIC   This side-by-side is the fastest debugging technique for Genie MCP issues:
# MAGIC   if Genie answers correctly but the agent doesn't, the problem is in tool
# MAGIC   routing or the agent's interpretation — not in the underlying data.
# MAGIC ```

# COMMAND ----------

q1 = (
    "What was the average spot price in VIC1 for the most recent full day in the dataset? "
    "Express in $/MWh and note how many intervals are included in the average."
)

print(f"Question 1: {q1}")
print()
print("Expected tool selection: ask_aemo_nem_operations (Genie MCP)")
print("Why Genie: aggregation (average) over a time window — SQL is the right approach")
print()
print("Running agent...")
print()

with mlflow.start_run(run_name="lab03_q1_avg_price"):
    answer_q1 = asyncio.run(build_and_run_agent(q1, run_name="q1_avg_price"))

print("=" * 65)
print("AGENT ANSWER — Q1 (average spot price, Genie tool):")
print("=" * 65)
print(answer_q1)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q1 (average spot price, Genie tool):
# MAGIC =================================================================
# MAGIC The average spot price in VIC1 for the most recent full day in the dataset was
# MAGIC **$87.15/MWh**, calculated across **288 intervals** (a full 24-hour day of 5-minute
# MAGIC dispatch intervals).
# MAGIC
# MAGIC (Source: NEM dispatch data via Genie)
# MAGIC
# MAGIC Note: This data reflects the workshop dataset and may not represent live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC **Success criteria for Q1:**
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | Tool used | MLflow trace shows `ask_aemo_nem_operations` was called |
# MAGIC | Unit format | Answer shows `$/MWh`, not `$/kWh` or `cents` |
# MAGIC | Interval count | 288 intervals = 24 hours × 12 five-minute intervals/hour |
# MAGIC | Citation | Answer includes "(Source: NEM dispatch data via Genie)" |
# MAGIC | Region code | Says "VIC1" not "VIC" or "Victoria" |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Question 2: Market notices via Vector Search MCP

# COMMAND ----------

q2 = (
    "Search for any market notices about constraint issues or constraint violations in NSW1. "
    "Summarise the top 3 most relevant notices — include the notice ID, date, and key content."
)

print(f"Question 2: {q2}")
print()
print("Expected tool selection: search_aemo_market_notices_index (Vector Search MCP)")
print("Why Vector Search: semantic document search — 'constraint issues' is a concept search")
print("  NOT a SQL keyword search (documents don't all use the word 'constraint')")
print()
print("Running agent...")
print()

with mlflow.start_run(run_name="lab03_q2_market_notices"):
    answer_q2 = asyncio.run(build_and_run_agent(q2, run_name="q2_market_notices"))

print("=" * 65)
print("AGENT ANSWER — Q2 (market notices, Vector Search tool):")
print("=" * 65)
print(answer_q2)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q2 (market notices, Vector Search tool):
# MAGIC =================================================================
# MAGIC Here are the 3 most relevant AEMO market notices related to constraint issues
# MAGIC and violations in NSW1:
# MAGIC
# MAGIC 1. **MN-2024-0187** (2024-02-28)
# MAGIC    Constraint Set NSW_MAIN_2 was activated due to a transmission line outage
# MAGIC    on the Transgrid 330kV interconnect. The constraint limited NSW1 imports
# MAGIC    from QLD1 to 850 MW for approximately 4 hours.
# MAGIC    (Source: market notices, notice ID MN-2024-0187)
# MAGIC
# MAGIC 2. **MN-2024-0203** (2024-03-14)
# MAGIC    Binding constraint notification — NSW–VIC interconnector operating below
# MAGIC    normal capacity following planned maintenance. Market participants advised
# MAGIC    to revise dispatch offers accordingly.
# MAGIC    (Source: market notices, notice ID MN-2024-0203)
# MAGIC
# MAGIC 3. **MN-2024-0142** (2024-01-30)
# MAGIC    Pre-dispatch constraint alert: projected binding constraints on the NSW1
# MAGIC    load-serving bus during forecast peak demand period 16:30–19:00 AEST.
# MAGIC    (Source: market notices, notice ID MN-2024-0142)
# MAGIC
# MAGIC Note: This data reflects the workshop dataset and may not represent live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC **Success criteria for Q2:**
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | Tool used | MLflow trace shows `search_aemo_market_notices_index` was called |
# MAGIC | Semantic match | Notices returned discuss constraints even if not all say "constraint" |
# MAGIC | Notice IDs cited | Each notice has an ID in the format MN-YYYY-XXXX |
# MAGIC | No SQL evidence | Answer should not show generated SQL (VS tool, not Genie) |
# MAGIC | Region | Notices are NSW1-relevant (agent applied the region filter from the question) |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Question 3: Peak demand calculation via UC Function MCP

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Run Q3 — Look at the UC function definition
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog → workshop_au → aemo → Functions
# MAGIC           → get_region_summary
# MAGIC
# MAGIC Read the function's COMMENT carefully:
# MAGIC   "Return a JSON summary of NEM region conditions for a rolling window.
# MAGIC    Covers avg spot price, number of price spikes (>$300/MWh), total
# MAGIC    generation by fuel type, and peak demand interval. Use for questions
# MAGIC    about a region's overall performance over a time window (days=1 to 30).
# MAGIC    Not for single-day spot prices (use calculate_peak_demand for those)."
# MAGIC
# MAGIC The "Not for..." clause is what prevents the LLM from using this function
# MAGIC when the user asks for single-day data. This negative example in the COMMENT
# MAGIC is just as important as the positive description.
# MAGIC
# MAGIC Also check: Permissions tab → your user has EXECUTE on this function.
# MAGIC Without EXECUTE, the MCP server returns a 403 error in the trace.
# MAGIC ```

# COMMAND ----------

q3 = (
    "Calculate the peak demand and average spot price for QLD1 over the last 30 days "
    "in the dataset. I also want to know the top 3 fuel types by total generation during that period."
)

print(f"Question 3: {q3}")
print()
print("Expected tool selection: workshop_au__aemo__get_region_summary (UC Function MCP)")
print("Why UC Function: deterministic calculation with known parameters (region + days=30)")
print("  The function returns a pre-computed structured JSON — more reliable than Genie SQL")
print("  for fixed analytical formulas that the business runs repeatedly")
print()
print("Running agent...")
print()

with mlflow.start_run(run_name="lab03_q3_peak_demand"):
    answer_q3 = asyncio.run(build_and_run_agent(q3, run_name="q3_peak_demand"))

print("=" * 65)
print("AGENT ANSWER — Q3 (peak demand, UC Function tool):")
print("=" * 65)
print(answer_q3)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q3 (peak demand, UC Function tool):
# MAGIC =================================================================
# MAGIC Here is the QLD1 performance summary for the last 30 days:
# MAGIC
# MAGIC **Spot prices:**
# MAGIC   - Average spot price: $104.70/MWh
# MAGIC   - Price spikes (>$300/MWh): 8 intervals
# MAGIC   - Peak demand interval: 2024-06-21 17:30 AEST
# MAGIC
# MAGIC **Generation by fuel type (top 3):**
# MAGIC   1. Coal: 48.2% of total generation (12,450 GWh)
# MAGIC   2. Gas: 21.7% (5,614 GWh)
# MAGIC   3. Solar: 18.9% (4,891 GWh)
# MAGIC
# MAGIC (Source: get_region_summary function)
# MAGIC
# MAGIC Note: This data reflects the workshop dataset and may not represent live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC **Success criteria for Q3:**
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | Tool used | MLflow trace shows `workshop_au__aemo__get_region_summary` was called |
# MAGIC | Parameters | Trace shows `region="QLD1"` and `days=30` were passed |
# MAGIC | Source citation | "Source: get_region_summary function" not "Genie" |
# MAGIC | JSON parsing | Agent parsed the JSON response and formatted it readably |
# MAGIC | No hallucination | Numbers match what the UC function returns |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Question 4: Multi-tool chain (Genie + UC Function)
# MAGIC
# MAGIC This is the flagship question — the one from Section 1.1 of Lab 01.
# MAGIC The agent must use two tools in sequence because neither alone can answer fully.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Run Q4 — Predict the tool sequence
# MAGIC </div>
# MAGIC
# MAGIC Before running the agent, predict the ReAct loop:
# MAGIC
# MAGIC ```
# MAGIC Question 4: "Were there any price spikes above $1000/MWh in SA1 last month?
# MAGIC              If yes, what generators were dispatched during those intervals?"
# MAGIC
# MAGIC Predicted tool sequence:
# MAGIC
# MAGIC   Step 1: ask_aemo_nem_operations ("price spikes above $1000 in SA1 last month")
# MAGIC           → Genie runs SQL, returns: N intervals above $1000, with timestamps
# MAGIC
# MAGIC   Step 2: LLM sees spike timestamps, decides it needs dispatch data
# MAGIC           → ask_aemo_nem_operations ("generators dispatched in SA1 on [dates from step 1]")
# MAGIC           → OR workshop_au__aemo__calculate_peak_demand for each spike date
# MAGIC
# MAGIC   Step 3: workshop_au__aemo__lookup_duid_info (for each DUID in the dispatch data)
# MAGIC           → returns generator name, owner, fuel type for each DUID
# MAGIC
# MAGIC   Step 4: LLM synthesises → "There were N spikes. During these intervals,
# MAGIC           generators X, Y, Z were dispatched..."
# MAGIC
# MAGIC Write your prediction here before running:
# MAGIC   My predicted tools (in order): _________________
# MAGIC
# MAGIC Then compare to what the MLflow trace shows after the run.
# MAGIC ```

# COMMAND ----------

q4 = (
    "Were there any price spikes above $1,000/MWh in SA1 during the last month of data "
    "available? If yes, provide:\n"
    "  1. The date and time of each spike interval\n"
    "  2. The exact spot price for each interval\n"
    "  3. Which generators (DUIDs) were dispatched in SA1 during those spike intervals\n"
    "  4. Any AEMO market notices related to those spike events"
)

print(f"Question 4 (compound — predicting multi-tool chain):")
print(f"  {q4[:120]}...")
print()
print("Expected tool sequence:")
print("  1. ask_aemo_nem_operations → find spike intervals (Genie SQL)")
print("  2. ask_aemo_nem_operations → get dispatch data for those intervals (Genie SQL)")
print("  3. workshop_au__aemo__lookup_duid_info → generator names for each DUID")
print("  4. search_aemo_market_notices_index → notices about SA1 price events")
print()
print("Running agent (may take 30-60 seconds for multi-tool chain)...")
print()

with mlflow.start_run(run_name="lab03_q4_spike_analysis"):
    answer_q4 = asyncio.run(build_and_run_agent(q4, run_name="q4_spike_analysis"))

print("=" * 65)
print("AGENT ANSWER — Q4 (multi-tool chain):")
print("=" * 65)
print(answer_q4)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (structure — actual values depend on the dataset):**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q4 (multi-tool chain):
# MAGIC =================================================================
# MAGIC There were **4 price spike intervals** in SA1 exceeding $1,000/MWh in the last
# MAGIC month of the dataset:
# MAGIC
# MAGIC | # | Date / Time (AEST)      | Spot Price ($/MWh) |
# MAGIC |---|-------------------------|--------------------|
# MAGIC | 1 | 2024-06-18 17:00        | $14,000.00 (MPC)   |
# MAGIC | 2 | 2024-06-18 17:05        | $11,200.00         |
# MAGIC | 3 | 2024-06-22 18:30        | $4,750.00          |
# MAGIC | 4 | 2024-06-22 18:35        | $3,200.00          |
# MAGIC
# MAGIC **Generators dispatched during spike intervals on 18 June 2024:**
# MAGIC - TORRB1 (Torrens Island B Unit 1) — Gas CCGT, AGL Energy — 200 MW
# MAGIC - PELICAN1 (Pelican Point) — Gas CCGT, Engie — 478 MW
# MAGIC - SNOWY1 (Snowy Hydro Unit 1) — Hydro — imported 350 MW from NSW1
# MAGIC
# MAGIC **Related market notices:**
# MAGIC - MN-2024-0419 (18 June 2024): "LOR2 Declared — South Australia. Reserve margin
# MAGIC   below LOR2 threshold. AEMO activating RERT."
# MAGIC
# MAGIC (Sources: NEM dispatch data via Genie, lookup_duid_info function,
# MAGIC  market notices search)
# MAGIC
# MAGIC Note: This data reflects the workshop dataset and may not represent live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC **What to check in the MLflow trace (next section):**
# MAGIC
# MAGIC | Trace element | What you should see |
# MAGIC |--------------|---------------------|
# MAGIC | Tool call 1 | `ask_aemo_nem_operations` with spike query |
# MAGIC | Tool call 2 | `ask_aemo_nem_operations` with dispatch query for spike intervals |
# MAGIC | Tool call 3 | `workshop_au__aemo__lookup_duid_info` for each DUID |
# MAGIC | Tool call 4 | `search_aemo_market_notices_index` with SA1 price event query |
# MAGIC | LLM reasoning | Visible between each tool call — shows the agent's chain of thought |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2 complete</strong><br>
# MAGIC   You ran 4 questions: single-tool Genie, single-tool Vector Search, single-tool UC Function,
# MAGIC   and a multi-tool chain. The agent routed each question to the correct MCP server based on
# MAGIC   tool descriptions alone — no hardcoded routing logic. Section 3 inspects the traces.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — View Traces in MLflow (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Navigate to the Experiment and find your traces
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar) → Experiments
# MAGIC           → /Shared/workshop2c-aemo-operations-agent
# MAGIC           → Runs tab (should show 5+ runs from this session)
# MAGIC
# MAGIC ┌─── Experiment: workshop2c-aemo-operations-agent ─────────────────────────┐
# MAGIC │  Runs                                                                    │
# MAGIC │  ──────────────────────────────────────────────────────────────────────  │
# MAGIC │  Run name                      Start time     Duration  Status           │
# MAGIC │  lab03_q4_spike_analysis       16:47:22        45.2s    Finished  [View] │
# MAGIC │  lab03_q3_peak_demand          16:46:38        12.8s    Finished  [View] │
# MAGIC │  lab03_q2_market_notices       16:46:01         8.4s    Finished  [View] │
# MAGIC │  lab03_q1_avg_price            16:45:18        11.2s    Finished  [View] │
# MAGIC │  lab03_warmup                  16:44:51         9.1s    Finished  [View] │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click [View] on lab03_q4_spike_analysis (the multi-tool run).
# MAGIC Then click the "Traces" tab inside the run.
# MAGIC ```
# MAGIC
# MAGIC **What you see in the Traces tab:**
# MAGIC ```
# MAGIC ┌─── Trace: lab03_q4_spike_analysis ──────────────────────────────────────┐
# MAGIC │                                                                          │
# MAGIC │  AgentRun           total: 44.8s                                        │
# MAGIC │  ├── LLMCall        "Were there any price spikes above $1,000..."       │
# MAGIC │  │                   → decides to call ask_aemo_nem_operations           │
# MAGIC │  ├── ToolCall       ask_aemo_nem_operations                             │
# MAGIC │  │                   query: "spot price SA1 above 1000 last month"      │
# MAGIC │  │                   result: "4 intervals: 2024-06-18 17:00..."         │
# MAGIC │  │                   latency: 12.4s                                     │
# MAGIC │  ├── LLMCall        receives spike intervals                            │
# MAGIC │  │                   → decides to get dispatch data for those intervals  │
# MAGIC │  ├── ToolCall       ask_aemo_nem_operations                             │
# MAGIC │  │                   query: "generators dispatched SA1 2024-06-18..."   │
# MAGIC │  │                   latency: 9.8s                                      │
# MAGIC │  ├── ToolCall       workshop_au__aemo__lookup_duid_info                 │
# MAGIC │  │                   duid: "TORRB1"                                     │
# MAGIC │  │                   result: {"name": "Torrens Island B...",...}        │
# MAGIC │  │                   latency: 0.8s                                      │
# MAGIC │  ├── ToolCall       search_aemo_market_notices_index                   │
# MAGIC │  │                   query: "SA1 price spike LOR June 2024"             │
# MAGIC │  │                   latency: 1.2s                                      │
# MAGIC │  └── LLMCall        synthesises all results → final answer              │
# MAGIC │                      latency: 6.1s                                      │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click any ToolCall span to see:
# MAGIC   - Exact arguments the agent passed to the tool
# MAGIC   - Complete MCP response (the raw JSON the tool returned)
# MAGIC   - Latency breakdown (how long the MCP call took)
# MAGIC
# MAGIC Click any LLMCall span to see:
# MAGIC   - The full message history (including previous tool results) that the LLM received
# MAGIC   - The LLM's complete response (including reasoning before tool selection)
# MAGIC   - Token counts (input tokens, output tokens, cost estimate)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Retrieve and display the Q4 trace programmatically

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient

client_mlflow = MlflowClient()

# Find the experiment
experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)
if not experiment:
    print(f"Experiment not found: {MLFLOW_EXPERIMENT}")
    print("Check that Section 1.1 ran successfully.")
else:
    # Get the most recent run (lab03_q4_spike_analysis)
    runs = client_mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.mlflow.runName = 'lab03_q4_spike_analysis'",
        order_by=["start_time DESC"],
        max_results=1,
    )

    if not runs:
        print("Run 'lab03_q4_spike_analysis' not found.")
        print("Make sure Section 2.4 ran successfully.")
    else:
        run = runs[0]
        run_id = run.info.run_id

        print(f"Run: {run.info.run_name}")
        print(f"ID : {run_id}")
        print(f"URL: {HOST}/ml/experiments/{experiment.experiment_id}/runs/{run_id}")
        print()

        # Fetch traces for this run
        try:
            traces = mlflow.search_traces(
                experiment_ids=[experiment.experiment_id],
                filter_string=f"attributes.run_id = '{run_id}'",
                max_results=5,
            )

            print(f"Traces found: {len(traces)}")
            for trace in traces:
                print()
                print(f"  Trace ID    : {trace.info.trace_id}")
                print(f"  Status      : {trace.info.status}")
                print(f"  Duration    : {trace.info.execution_time_ms}ms")
                # Show span summary if available
                if hasattr(trace, "data") and trace.data:
                    spans = trace.data.spans
                    tool_spans = [s for s in spans if s.span_type.name == "TOOL"]
                    llm_spans  = [s for s in spans if s.span_type.name == "LLM"]
                    print(f"  LLM calls   : {len(llm_spans)}")
                    print(f"  Tool calls  : {len(tool_spans)}")
                    if tool_spans:
                        print(f"  Tools used  : {[s.name for s in tool_spans]}")
        except Exception as e:
            print(f"Trace retrieval note: {e}")
            print(f"View traces in the UI: Machine Learning → Experiments → {MLFLOW_EXPERIMENT}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Run: lab03_q4_spike_analysis
# MAGIC ID : abc123def456...
# MAGIC URL: https://adb-xxxx.azuredatabricks.net/ml/experiments/.../runs/abc123...
# MAGIC
# MAGIC Traces found: 1
# MAGIC
# MAGIC   Trace ID    : 0196xyz...
# MAGIC   Status      : OK
# MAGIC   Duration    : 44823ms
# MAGIC   LLM calls   : 5
# MAGIC   Tool calls  : 4
# MAGIC   Tools used  : ['ask_aemo_nem_operations', 'ask_aemo_nem_operations',
# MAGIC                   'workshop_au__aemo__lookup_duid_info',
# MAGIC                   'search_aemo_market_notices_index']
# MAGIC ```
# MAGIC
# MAGIC The trace shows:
# MAGIC - 5 LLM calls: initial reasoning + one per tool result + final synthesis
# MAGIC - 4 tool calls: 2 Genie, 1 UC Function, 1 Vector Search
# MAGIC - Genie was called twice — the agent needed two separate SQL queries

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Compare trace latency across the 4 questions

# COMMAND ----------

# Fetch all 4 question runs and compare their latency profiles
question_runs = [
    "lab03_q1_avg_price",
    "lab03_q2_market_notices",
    "lab03_q3_peak_demand",
    "lab03_q4_spike_analysis",
]

experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)

if experiment:
    print("Latency comparison across 4 questions:")
    print()
    print(f"  {'Run name':<35} {'Duration':>12} {'Tool calls':>12} {'LLM calls':>10}")
    print("  " + "-" * 73)

    for run_name in question_runs:
        runs = client_mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"tags.mlflow.runName = '{run_name}'",
            order_by=["start_time DESC"],
            max_results=1,
        )
        if runs:
            r = runs[0]
            duration_s = (r.info.end_time - r.info.start_time) / 1000
            try:
                traces = mlflow.search_traces(
                    experiment_ids=[experiment.experiment_id],
                    filter_string=f"attributes.run_id = '{r.info.run_id}'",
                    max_results=1,
                )
                if traces and hasattr(traces[0], "data") and traces[0].data:
                    spans      = traces[0].data.spans
                    tool_count = sum(1 for s in spans if s.span_type.name == "TOOL")
                    llm_count  = sum(1 for s in spans if s.span_type.name == "LLM")
                    print(f"  {run_name:<35} {duration_s:>10.1f}s {tool_count:>12} {llm_count:>10}")
                else:
                    print(f"  {run_name:<35} {duration_s:>10.1f}s {'n/a':>12} {'n/a':>10}")
            except Exception:
                print(f"  {run_name:<35} {duration_s:>10.1f}s {'n/a':>12} {'n/a':>10}")
        else:
            print(f"  {run_name:<35} {'NOT FOUND':>12}")

    print()
    print("Observations:")
    print("  Q4 (multi-tool) is the slowest — each tool call adds latency")
    print("  Genie calls are the slowest per tool (SQL execution + NL translation)")
    print("  UC Function calls are fastest (deterministic Python, no SQL)")
    print("  Vector Search calls are fast (pre-built embedding index)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Latency comparison across 4 questions:
# MAGIC
# MAGIC   Run name                             Duration   Tool calls  LLM calls
# MAGIC   -------------------------------------------------------------------------
# MAGIC   lab03_q1_avg_price                       11.2s            1          2
# MAGIC   lab03_q2_market_notices                   8.4s            1          2
# MAGIC   lab03_q3_peak_demand                     12.8s            1          2
# MAGIC   lab03_q4_spike_analysis                  44.8s            4          5
# MAGIC
# MAGIC Observations:
# MAGIC   Q4 (multi-tool) is the slowest — each tool call adds latency
# MAGIC   Genie calls are the slowest per tool (SQL execution + NL translation)
# MAGIC   UC Function calls are fastest (deterministic Python, no SQL)
# MAGIC   Vector Search calls are fast (pre-built embedding index)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Share a trace with a teammate
# MAGIC
# MAGIC MLflow traces can be shared via a direct URL. The URL is stable — it points to a
# MAGIC specific trace in the workspace and works for anyone with workspace access.

# COMMAND ----------

# Generate shareable trace URLs for all runs
print("Shareable trace URLs for this session:")
print()

if experiment:
    for run_name in ["lab03_q4_spike_analysis", "lab03_q1_avg_price"]:
        runs = client_mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"tags.mlflow.runName = '{run_name}'",
            order_by=["start_time DESC"],
            max_results=1,
        )
        if runs:
            r   = runs[0]
            url = (
                f"{HOST}/ml/experiments/{experiment.experiment_id}"
                f"/runs/{r.info.run_id}"
            )
            print(f"  {run_name}:")
            print(f"    {url}")
            print()

print("Share these URLs with your team to review agent reasoning together.")
print("Anyone with 'CAN_READ' on the experiment can view the traces.")
print()
print("To grant access to the experiment:")
print(f"  Machine Learning → Experiments → {MLFLOW_EXPERIMENT} → Permissions")
print("  → Add your team (group or individual) with CAN_READ")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Shareable trace URLs for this session:
# MAGIC
# MAGIC   lab03_q4_spike_analysis:
# MAGIC     https://adb-xxxx.azuredatabricks.net/ml/experiments/87654321/runs/abc123def
# MAGIC
# MAGIC   lab03_q1_avg_price:
# MAGIC     https://adb-xxxx.azuredatabricks.net/ml/experiments/87654321/runs/xyz789abc
# MAGIC
# MAGIC Share these URLs with your team to review agent reasoning together.
# MAGIC Anyone with 'CAN_READ' on the experiment can view the traces.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 3 complete</strong><br>
# MAGIC   You retrieved traces programmatically, compared latency across question types, and
# MAGIC   generated shareable trace URLs. You know how to use MLflow traces to debug agent
# MAGIC   tool routing and verify answer correctness. The Bonus section shows how to connect
# MAGIC   your laptop to the same MCP servers for local development.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Bonus — Claude Desktop Config and Audit Trail
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 1 — Connect Claude Desktop to your Databricks MCP servers
# MAGIC
# MAGIC Any MCP-compatible client (Claude Desktop, Cursor, VS Code + MCP extension) can connect
# MAGIC to your Databricks workspace MCP servers. The only requirement is a Personal Access Token.
# MAGIC
# MAGIC **Data residency note:** The Claude Desktop app runs on your laptop. When you ask a
# MAGIC question, the question goes to Anthropic's API. The MCP tool calls, however, go
# MAGIC **directly from your laptop to your Databricks workspace** — not via Anthropic.
# MAGIC The AEMO data in your MCP tool results stays within the Databricks workspace.
# MAGIC For regulated environments, review your organisation's AI acceptable use policy
# MAGIC before using Claude Desktop with production data.
# MAGIC
# MAGIC **Get a PAT first:**
# MAGIC ```
# MAGIC Navigate: Your workspace → top right → Settings (user icon)
# MAGIC           → Developer → Access tokens → [Generate new token]
# MAGIC
# MAGIC ┌─── Generate new token ────────────────────────────────────────────────────┐
# MAGIC │  Comment: workshop-2c-claude-desktop                                     │
# MAGIC │  Lifetime: 30 days   ← keep short for development tokens                │
# MAGIC │                                                      [Generate]          │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Copy the token — it is shown only once. Store it somewhere safe.
# MAGIC NEVER commit it to git or paste it into a shared document.
# MAGIC ```

# COMMAND ----------

# Generate the Claude Desktop config for this participant's workspace
config_output = {
    "mcpServers": {
        "databricks-aemo-uc-functions": {
            "command": "npx",
            "args": [
                "mcp-remote",
                f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}",
                "--header",
                "Authorization: Bearer <YOUR_PAT_HERE>"
            ]
        },
        "databricks-aemo-market-notices": {
            "command": "npx",
            "args": [
                "mcp-remote",
                VS_MCP_URL,
                "--header",
                "Authorization: Bearer <YOUR_PAT_HERE>"
            ]
        }
    }
}

if GENIE_SPACE_ID != "FILL_IN":
    config_output["mcpServers"]["databricks-aemo-genie"] = {
        "command": "npx",
        "args": [
            "mcp-remote",
            f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            "--header",
            "Authorization: Bearer <YOUR_PAT_HERE>"
        ]
    }

import json
print("Your claude_desktop_config.json snippet")
print("(replace <YOUR_PAT_HERE> with your actual token)")
print()
print("File location:")
print("  macOS   : ~/Library/Application Support/Claude/claude_desktop_config.json")
print("  Windows : %APPDATA%\\Claude\\claude_desktop_config.json")
print()
print("=" * 65)
print(json.dumps(config_output, indent=2))
print("=" * 65)
print()
print("After saving, restart Claude Desktop.")
print("In the chat input area, click the hammer icon to see available tools.")
print("You should see your 3 Databricks MCP servers listed there.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Your claude_desktop_config.json snippet
# MAGIC (replace <YOUR_PAT_HERE> with your actual token)
# MAGIC
# MAGIC File location:
# MAGIC   macOS   : ~/Library/Application Support/Claude/claude_desktop_config.json
# MAGIC
# MAGIC =================================================================
# MAGIC {
# MAGIC   "mcpServers": {
# MAGIC     "databricks-aemo-uc-functions": {
# MAGIC       "command": "npx",
# MAGIC       "args": [
# MAGIC         "mcp-remote",
# MAGIC         "https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/aemo",
# MAGIC         "--header",
# MAGIC         "Authorization: Bearer <YOUR_PAT_HERE>"
# MAGIC       ]
# MAGIC     },
# MAGIC     ...
# MAGIC   }
# MAGIC }
# MAGIC =================================================================
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 2 — Query the audit trail for your MCP calls
# MAGIC
# MAGIC Every MCP call made during this workshop is logged in `system.access.audit`.
# MAGIC Run this SQL to see your own calls:

# COMMAND ----------

from datetime import datetime, timedelta

# Build the audit query for this session
audit_sql = f"""
SELECT
    event_time,
    user_identity.email           AS user_email,
    service_name,
    action_name,
    request_params.functionName   AS function_name,
    request_params.query          AS query_text
FROM system.access.audit
WHERE user_identity.email = '{ws.current_user.me().user_name}'
  AND event_time > '{(datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")}'
  AND service_name IN (
      'databricksSQL',
      'vectorSearch',
      'genie',
      'unityCatalog'
  )
ORDER BY event_time DESC
LIMIT 50
"""

print("Run this SQL query in a SQL cell or Databricks SQL editor to see your audit trail:")
print()
print("=" * 65)
print(audit_sql)
print("=" * 65)
print()
print("service_name values for MCP calls:")
print("  unityCatalog  → UC Function tool calls")
print("  genie         → Genie Space NL-to-SQL calls")
print("  vectorSearch  → Vector Search similarity queries")
print("  databricksSQL → Direct SQL MCP calls")
print()
print("Each row shows exactly which data the agent accessed and when.")
print("This is your compliance audit trail — required for AEMO and AER regulated workloads.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 3 — Production deployment preview
# MAGIC
# MAGIC When you deploy this agent to a **Databricks Model Serving endpoint** for production use,
# MAGIC you must declare the MCP resource dependencies so Model Serving can inject credentials.
# MAGIC Here is the pattern (reference only — do not run as part of this lab):

# COMMAND ----------

# Production deployment pattern — REFERENCE ONLY
# This code shows the additional step required when logging an MCP agent to MLflow
# for deployment to a Model Serving endpoint.
#
# In a notebook, WorkspaceClient() auto-authenticates from the cluster.
# In Model Serving, there is no cluster context — the service principal
# needs to be told which MCP servers to authenticate against.
# get_databricks_resources() introspects the MCP server list and returns
# DatabricksResource declarations that MLflow uses to configure the endpoint.

PRODUCTION_REFERENCE = '''
# ── Production deployment (reference only) ────────────────────────────────────
#
# import asyncio
# import mlflow
# from databricks_langchain import (
#     DatabricksMCPServer, DatabricksMultiServerMCPClient, ChatDatabricks
# )
# from langgraph.prebuilt import create_react_agent
#
# async def build_agent_for_deployment():
#     """Build agent and collect resource declarations for Model Serving."""
#     async with DatabricksMultiServerMCPClient(all_servers) as multi_client:
#         tools = await multi_client.get_tools()
#
#         agent = create_react_agent(
#             model=ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0),
#             tools=tools,
#             prompt=AEMO_SYSTEM_PROMPT,
#         )
#
#         # get_databricks_resources() collects resource declarations from each server.
#         # This tells Model Serving which UC schemas, Genie Spaces, and VS indexes
#         # the service principal needs access to at inference time.
#         resources = await multi_client.get_databricks_resources()
#
#         return agent, resources
#
# agent, resources = asyncio.run(build_agent_for_deployment())
#
# # Log to MLflow with resource declarations
# with mlflow.start_run(run_name="aemo-agent-production-v1"):
#     mlflow.langchain.log_model(
#         lc_model=agent,
#         artifact_path="aemo_operations_agent",
#         resources=resources,            # ← the critical addition for Model Serving
#         input_example={"input": "What was the average VIC1 price yesterday?"},
#     )
# ─────────────────────────────────────────────────────────────────────────────
'''

print("Production deployment pattern (reference only):")
print(PRODUCTION_REFERENCE)
print()
print("The only difference from the notebook version:")
print("  resources = await multi_client.get_databricks_resources()")
print("  mlflow.langchain.log_model(..., resources=resources)")
print()
print("These two lines tell Model Serving how to authenticate the service principal")
print("against each MCP server at inference time.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 4 — Try it yourself: Add the regulatory compliance tool
# MAGIC
# MAGIC Extend the AEMO agent with a new UC function: `check_nem_price_compliance`.
# MAGIC This function checks whether spot prices in a region exceeded the Administered
# MAGIC Price Cap (APC) — a regulatory threshold that triggers special AEMO intervention.

# COMMAND ----------

# Step 1 — Create a reference table for NEM regulatory thresholds
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

threshold_rows = [
    # (region, threshold_name, threshold_value_mwh, description)
    ("VIC1", "ADMINISTERED_PRICE_CAP",   300.0,   "APC: triggers administered pricing after sustained high prices"),
    ("NSW1", "ADMINISTERED_PRICE_CAP",   300.0,   "APC: triggers administered pricing after sustained high prices"),
    ("QLD1", "ADMINISTERED_PRICE_CAP",   300.0,   "APC: triggers administered pricing after sustained high prices"),
    ("SA1",  "ADMINISTERED_PRICE_CAP",   300.0,   "APC: triggers administered pricing after sustained high prices"),
    ("TAS1", "ADMINISTERED_PRICE_CAP",   300.0,   "APC: triggers administered pricing after sustained high prices"),
    ("VIC1", "MARKET_PRICE_CAP",       14000.0,   "MPC: hard ceiling on any single dispatch interval price"),
    ("NSW1", "MARKET_PRICE_CAP",       14000.0,   "MPC: hard ceiling on any single dispatch interval price"),
    ("QLD1", "MARKET_PRICE_CAP",       14000.0,   "MPC: hard ceiling on any single dispatch interval price"),
    ("SA1",  "MARKET_PRICE_CAP",       14000.0,   "MPC: hard ceiling on any single dispatch interval price"),
    ("TAS1", "MARKET_PRICE_CAP",       14000.0,   "MPC: hard ceiling on any single dispatch interval price"),
    ("VIC1", "SPOT_PRICE_LOR1_TRIGGER",  850.0,   "Reserve threshold for LOR1 declaration"),
    ("SA1",  "SPOT_PRICE_LOR1_TRIGGER",  250.0,   "Reserve threshold for LOR1 declaration (smaller SA system)"),
]

threshold_schema = StructType([
    StructField("region",          StringType(), False),
    StructField("threshold_name",  StringType(), False),
    StructField("threshold_value_mwh", DoubleType(), False),
    StructField("description",     StringType(), True),
])

(spark.createDataFrame(threshold_rows, threshold_schema)
      .write.format("delta").mode("overwrite")
      .option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds"))

print(f"Created: {CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds")
spark.table(f"{CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Created: workshop_au.aemo.nem_price_thresholds
# MAGIC +------+----------------------------+--------------------+----------------------------------------+
# MAGIC |region|threshold_name              |threshold_value_mwh |description                             |
# MAGIC +------+----------------------------+--------------------+----------------------------------------+
# MAGIC |VIC1  |ADMINISTERED_PRICE_CAP      |300.0               |APC: triggers administered pricing...   |
# MAGIC ...
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 2 — Register the UC function (uncomment and run):**

# COMMAND ----------

# TODO: Uncomment and run this block to register the new MCP tool.
#
# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA_AEMO}.check_nem_price_compliance(
#     region          STRING  COMMENT 'NEM region code to check. Values: NSW1, VIC1, QLD1, SA1, TAS1',
#     threshold_name  STRING  COMMENT 'Threshold to check against. Values: ADMINISTERED_PRICE_CAP, MARKET_PRICE_CAP, SPOT_PRICE_LOR1_TRIGGER',
#     actual_price_mwh DOUBLE  COMMENT 'The actual spot price in $/MWh to evaluate against the threshold'
# )
# RETURNS STRING
# COMMENT 'Check whether a NEM spot price reading is compliant with a named regulatory threshold
# for a given region. Returns JSON with: region, threshold_name, threshold_value_mwh,
# actual_price_mwh, compliant (bool), overage_mwh. Use when asked whether a specific
# price reading breached the APC or MPC, or when evaluating LOR1 reserve thresholds.
# Not for trend analysis or aggregations — use the Genie tool for those.'
# LANGUAGE PYTHON
# AS $$
# import json
# try:
#     from pyspark.sql import SparkSession
#     from pyspark.sql import functions as F
#     spark = SparkSession.builder.getOrCreate()
#     row = (
#         spark.table("{CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds")
#         .filter(
#             (F.col("region") == region) &
#             (F.col("threshold_name") == threshold_name)
#         )
#         .first()
#     )
#     if row is None:
#         return json.dumps({{"error": f"No threshold found for {{threshold_name}} in {{region}}"}})
#     threshold = float(row["threshold_value_mwh"])
#     compliant = actual_price_mwh <= threshold
#     overage   = round(actual_price_mwh - threshold, 2) if not compliant else 0.0
#     return json.dumps({{
#         "region":             region,
#         "threshold_name":     threshold_name,
#         "threshold_value_mwh": threshold,
#         "actual_price_mwh":   actual_price_mwh,
#         "compliant":          compliant,
#         "overage_mwh":        overage,
#     }})
# except Exception as e:
#     return json.dumps({{"error": str(e)}})
# $$
# """)
# print(f"Registered: {CATALOG}.{SCHEMA_AEMO}.check_nem_price_compliance")
print("Uncomment the spark.sql block above, then run this cell to register the new tool.")
print()
print("Once registered, the tool is automatically discovered by the multi-server client.")
print("No code changes needed in the agent — just rebuild it (re-run Section 1.4 cell).")

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 3 — Verify the new tool appears in the aggregated list:**

# COMMAND ----------

async def verify_new_tool():
    """Verify the new UC function appears as an MCP tool after registration."""
    async with DatabricksMultiServerMCPClient(all_servers) as multi_client:
        tools = await multi_client.get_tools()
        tool_names = [t.name for t in tools]
        compliance_tool = f"{CATALOG}__{SCHEMA_AEMO}__check_nem_price_compliance"

        print(f"All available tools ({len(tools)}):")
        for name in tool_names:
            marker = " ← NEW" if "compliance" in name else ""
            print(f"  {name}{marker}")

        print()
        if compliance_tool in tool_names:
            print("New tool is registered and discoverable via MCP.")
        else:
            print("New tool not found — make sure Step 2 above ran successfully.")

asyncio.run(verify_new_tool())

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 4 — Test question for the new tool:**
# MAGIC
# MAGIC ```python
# MAGIC # Test the new compliance tool
# MAGIC compliance_q = (
# MAGIC     "The spot price in SA1 reached $450/MWh during interval 18:30 yesterday. "
# MAGIC     "Has this breached the Administered Price Cap? If yes, what does this mean?"
# MAGIC )
# MAGIC
# MAGIC with mlflow.start_run(run_name="bonus_compliance_check"):
# MAGIC     compliance_answer = asyncio.run(
# MAGIC         build_and_run_agent(compliance_q, run_name="compliance_check")
# MAGIC     )
# MAGIC print(compliance_answer)
# MAGIC ```
# MAGIC
# MAGIC **Success criteria for the bonus tool:**
# MAGIC
# MAGIC | Check | Expected |
# MAGIC |-------|---------|
# MAGIC | Tool used | `workshop_au__aemo__check_nem_price_compliance` called |
# MAGIC | Parameters | `region='SA1', threshold_name='ADMINISTERED_PRICE_CAP', actual_price_mwh=450.0` |
# MAGIC | Answer | Confirms breach (APC = $300, actual = $450, overage = $150) |
# MAGIC | Context | Agent explains what APC breach means operationally |
# MAGIC | No Genie | Agent did NOT call Genie for this — it used the deterministic function |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 03 Complete</strong><br>
# MAGIC   You built a production-grade LangGraph ReAct agent, tested it with 4 AEMO questions,
# MAGIC   inspected full reasoning traces in MLflow, and understood the production deployment
# MAGIC   pattern. The agent routes questions to the correct MCP server without any hardcoded
# MAGIC   logic — all based on tool descriptions you control in Unity Catalog and Genie.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lab 03 — Review questions
# MAGIC
# MAGIC 1. The Q4 multi-tool trace shows the agent called `ask_aemo_nem_operations` twice.
# MAGIC    Why two Genie calls instead of one? What did the second call need that the first
# MAGIC    result did not contain?
# MAGIC
# MAGIC 2. You notice Q3 (UC Function) took 12.8 seconds even though UC functions run fast.
# MAGIC    What is likely adding most of the latency, and how would you reduce it?
# MAGIC
# MAGIC 3. You add a new UC function `summarise_dispatch_bids` to the `workshop_au.aemo` schema.
# MAGIC    Do you need to update the agent code to make the agent aware of this new tool? Why or why not?
# MAGIC
# MAGIC 4. The system prompt tells the agent to always include a data freshness disclaimer.
# MAGIC    The warm-up answer included it, but your Q4 answer did not.
# MAGIC    What is the most likely cause, and how would you debug this?
# MAGIC
# MAGIC 5. A security reviewer asks: "Can the agent access tables outside `workshop_au.aemo`?"
# MAGIC    Give a complete technical answer covering: UC permissions, Genie Space trusted assets,
# MAGIC    and Vector Search index scope.
# MAGIC
# MAGIC ---

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 28px 32px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 12px 0; font-family: 'DM Sans', sans-serif;">
# MAGIC     Workshop 2c Complete — What you built
# MAGIC   </h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 16px 0;">
# MAGIC     Over three labs you built a production-grade AI agent for NEM operations —
# MAGIC     from architecture understanding to live tool calls to MLflow trace inspection.
# MAGIC   </p>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 0.92em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 7px 10px;">Lab</th>
# MAGIC       <th style="text-align: left; padding: 7px 10px;">What you built</th>
# MAGIC       <th style="text-align: left; padding: 7px 10px;">AU East</th>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 01</td>
# MAGIC       <td style="padding: 5px 10px;">Architecture map, UI navigation, environment verified</td>
# MAGIC       <td style="padding: 5px 10px;">All endpoints ✅</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 02</td>
# MAGIC       <td style="padding: 5px 10px;">Direct MCP calls to all 3 server types, multi-server tool discovery</td>
# MAGIC       <td style="padding: 5px 10px;">All endpoints ✅</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 5px 10px;">Lab 03</td>
# MAGIC       <td style="padding: 5px 10px;">Full ReAct agent, 4 AEMO questions, MLflow traces, deployment preview</td>
# MAGIC       <td style="padding: 5px 10px;">All endpoints ✅</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 8px 0; font-weight: bold;">
# MAGIC     Key packages used across Workshop 2c:
# MAGIC   </p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0 0 14px 0; padding-left: 20px; font-size: 0.92em;">
# MAGIC     <li><code>databricks-mcp</code> — low-level <code>DatabricksMCPClient</code> for tool discovery and direct calls</li>
# MAGIC     <li><code>databricks-langchain</code> — <code>DatabricksMultiServerMCPClient</code>, <code>DatabricksMCPServer</code>, <code>ChatDatabricks</code></li>
# MAGIC     <li><code>langgraph</code> — <code>create_react_agent</code> for the ReAct loop</li>
# MAGIC     <li><code>mlflow</code> — <code>langchain.autolog()</code> for automatic trace capture</li>
# MAGIC   </ul>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 6px 0; font-weight: bold;">Next steps:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0; padding-left: 20px; font-size: 0.92em;">
# MAGIC     <li>Lab 04 (Bonus): Deploy to Model Serving with <code>get_databricks_resources()</code></li>
# MAGIC     <li>Lab 05 (Bonus): Add human-in-the-loop confirmation for high-stakes tool calls</li>
# MAGIC     <li>Production checklist: Service Principal auth, Secret Scopes for PATs, MLflow evaluation</li>
# MAGIC     <li>Governance: <code>system.access.audit</code> dashboard for MCP call visibility</li>
# MAGIC   </ul>
# MAGIC </div>
