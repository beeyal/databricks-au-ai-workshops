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
# MAGIC | 2 | Test with 4 AEMO Questions | UC Function, Vector Search, Genie, multi-tool chain | 20 min |
# MAGIC | 3 | View Traces in MLflow | Navigate Experiments UI, read trace waterfall, share with team | 10 min |
# MAGIC | Bonus | Claude Desktop Config + Audit trail | Connect your laptop to the same MCP servers | open-ended |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ReAct pattern
# MAGIC
# MAGIC ```
# MAGIC User question → LLM reasons → picks tool → calls via MCP → receives result
# MAGIC     ↑_____________________________ loop until enough info ________________|
# MAGIC                      → final answer (1 loop for simple, 3-5 for compound)
# MAGIC ```
# MAGIC
# MAGIC `create_react_agent` from LangGraph builds this loop automatically. All tool calls go through `DatabricksMultiServerMCPClient` which routes each call to the correct MCP server.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration (loads Lab 02 values)

# COMMAND ----------

import json
from pathlib import Path

_config_path = Path("/tmp/workshop2c_config.json")
_saved = json.loads(_config_path.read_text()) if _config_path.exists() else {}

dbutils.widgets.text("catalog",           _saved.get("CATALOG",        "workshop_au"),          "Catalog name")
dbutils.widgets.text("schema_aemo",       _saved.get("SCHEMA_AEMO",    "aemo"),                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint",       _saved.get("PT_ENDPOINT",    "au_east_llm_inregion"), "PT endpoint name")
dbutils.widgets.text("genie_space_id",    _saved.get("GENIE_SPACE_ID", ""),                     "Genie Space ID")
dbutils.widgets.text("vs_index",          _saved.get("VS_INDEX_NAME",
                     "workshop_au.aemo.aemo_market_notices_index"),                              "VS index (3-part name)")
dbutils.widgets.text("mlflow_experiment",
                     "/Shared/workshop2c-aemo-operations-agent",                                 "MLflow experiment path")

CATALOG           = dbutils.widgets.get("catalog")
SCHEMA_AEMO       = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT       = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID    = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME     = dbutils.widgets.get("vs_index")
MLFLOW_EXPERIMENT = dbutils.widgets.get("mlflow_experiment")

from databricks.sdk import WorkspaceClient
ws         = WorkspaceClient()
HOST       = ws.config.host.rstrip("/")
vs_parts   = VS_INDEX_NAME.split(".")
VS_MCP_URL = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"

print("Configuration loaded.")
print(f"  HOST              : {HOST}")
print(f"  CATALOG.SCHEMA    : {CATALOG}.{SCHEMA_AEMO}")
print(f"  PT_ENDPOINT       : {PT_ENDPOINT}")
print(f"  GENIE_SPACE_ID    : {GENIE_SPACE_ID or '(not set)'}")
print(f"  VS_INDEX_NAME     : {VS_INDEX_NAME}")
print(f"  MLflow experiment : {MLFLOW_EXPERIMENT}")

if not GENIE_SPACE_ID:
    print("\nNOTE: GENIE_SPACE_ID not set — agent runs with UC Functions + Vector Search only.")

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
# MAGIC   🖱️ UI: Create the MLflow Experiment and check PT endpoint
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Experiments: Left sidebar → Machine Learning → Experiments
# MAGIC   Option A — Create now: [+ Create experiment] → name: workshop2c-aemo-operations-agent
# MAGIC                          Location: /Shared/ → [Create]
# MAGIC   Option B — Let code create it: mlflow.set_experiment() does this automatically.
# MAGIC
# MAGIC PT endpoint: Machine Learning → Serving → find au_east_llm_inregion
# MAGIC   Status: Ready (green). If not Ready, ask the workshop facilitator.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Enable MLflow autologging

# COMMAND ----------

import mlflow

# mlflow.langchain.autolog() instruments LangGraph automatically —
# every LLM call, tool call, and agent step is captured as a trace span.
mlflow.langchain.autolog()

experiment = mlflow.set_experiment(MLFLOW_EXPERIMENT)

print(f"MLflow autologging enabled for LangChain/LangGraph.")
print(f"\nExperiment name : {experiment.name}")
print(f"Experiment ID   : {experiment.experiment_id}")
print(f"\nEvery agent run produces a trace visible in:")
print(f"  Machine Learning → Experiments → {experiment.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MLflow autologging enabled for LangChain/LangGraph.
# MAGIC
# MAGIC Experiment name : /Shared/workshop2c-aemo-operations-agent
# MAGIC Experiment ID   : 8675309abcdef
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Configure the MCP servers

# COMMAND ----------

from databricks_langchain import DatabricksMCPServer, DatabricksMultiServerMCPClient

uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG, schema=SCHEMA_AEMO,
    name="aemo-uc-tools", timeout=30.0, handle_tool_error=True,
)

genie_server = None
if GENIE_SPACE_ID:
    genie_server = DatabricksMCPServer(
        name="aemo-nem-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0, handle_tool_error=True,
    )

vs_server = DatabricksMCPServer(
    name="aemo-market-notices",
    url=VS_MCP_URL, timeout=30.0, handle_tool_error=True,
)

all_servers = [uc_server] + ([genie_server] if genie_server else []) + [vs_server]

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

# COMMAND ----------

AEMO_SYSTEM_PROMPT = """You are the AEMO Operations Assistant, a technical AI agent for the
National Electricity Market (NEM) operated by the Australian Energy Market Operator (AEMO).

Your users are NEM market participants (generators, retailers) and AEMO operations staff.

## Domain rules

- Always use NEM region codes: NSW1, VIC1, QLD1, SA1, TAS1
- Express prices in $/MWh; generation in MW; energy in MWh
- Market Price Cap (MPC) = $14,000/MWh (hard ceiling on any dispatch interval)
- "Price spike" = spot price > $300/MWh
- LOR1/LOR2/LOR3 = Lack of Reserve conditions (LOR3 = load shedding imminent)
- "Yesterday" = the most recent complete day in the dataset

## Tool selection guidance

Use the Genie tool (ask_aemo_nem_operations) for:
  - Trends, averages, or totals over a time window
  - "How many", "what was the average", "show me all intervals where..."

Use UC Function tools (workshop_au__aemo__*) for:
  - Specific region+date calculations
  - DUID lookups

Use Vector Search (search_aemo_market_notices_index) for:
  - Market notices, LOR events, AEMO bulletins
  - "Were there any notices about...", policy documents

## Citation requirements

Every factual claim MUST cite its source:
  - Genie results: "(Source: NEM dispatch data via Genie)"
  - UC function results: "(Source: {function_name} function)"
  - Vector Search results: "(Source: market notices, notice ID [ID])"

Always add: "Note: This data reflects the workshop dataset and may not represent live NEM conditions."

## When a tool call fails

Explain what you tried to retrieve and why it failed. Never make up or estimate numbers.
"""

print(f"System prompt ready. Length: {len(AEMO_SYSTEM_PROMPT):,} characters")
print("\nKey sections: domain rules, tool selection, citations, error handling")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC System prompt ready. Length: 1,247 characters
# MAGIC Key sections: domain rules, tool selection, citations, error handling
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Build the LangGraph ReAct agent

# COMMAND ----------

import asyncio
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import ChatDatabricks

llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=4096)

print(f"LLM endpoint : {PT_ENDPOINT}")
print(f"Temperature  : 0.0  (deterministic)")
print()

async def build_and_run_agent(question: str, run_name: str = "agent_run") -> str:
    """
    Builds the ReAct agent with all configured MCP servers, runs one question,
    and returns the final answer string.

    The async with block manages MCP connection lifecycle — connections close
    automatically when the block exits, even on exception.
    mlflow.start_run() captures the full ReAct trace including LLM inputs/outputs,
    tool calls with arguments, MCP responses, and token usage.
    """
    async with DatabricksMultiServerMCPClient(all_servers) as multi_client:
        tools = await multi_client.get_tools()
        agent = create_react_agent(model=llm, tools=tools, prompt=AEMO_SYSTEM_PROMPT)

        with mlflow.start_run(run_name=run_name, nested=True):
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=question)]}
            )

    return result["messages"][-1].content

print("Agent builder function ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC LLM endpoint : au_east_llm_inregion
# MAGIC Temperature  : 0.0  (deterministic)
# MAGIC
# MAGIC Agent builder function ready.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 — Verify with a warm-up question

# COMMAND ----------

warmup_q = "What NEM regions are covered in the dataset and what tables are available?"

print(f"Warm-up question: {warmup_q}\nRunning agent...\n")

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
# MAGIC =================================================================
# MAGIC AGENT ANSWER (warm-up):
# MAGIC =================================================================
# MAGIC The AEMO NEM Operations dataset covers all five NEM regions: NSW1, VIC1, QLD1, SA1, TAS1.
# MAGIC
# MAGIC Tables available:
# MAGIC   - spot_prices: 5-minute dispatch interval spot prices by region
# MAGIC   - dispatch_intervals: Generator dispatch targets and actual output by DUID
# MAGIC   - market_notices: Official AEMO bulletins about system conditions
# MAGIC
# MAGIC (Source: NEM dispatch data via Genie)
# MAGIC Note: This data reflects the workshop dataset and may not represent live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 1</strong><br>
# MAGIC   MLflow autologging is on, the experiment exists, the system prompt is defined, and the agent responded to a warm-up question. Section 2 runs four AEMO-specific test questions.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Test with 4 AEMO Questions (20 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC | # | Question | Expected tool | Why |
# MAGIC |---|----------|--------------|-----|
# MAGIC | Q1 | Average spot price in VIC1 yesterday | Genie MCP | Aggregation over a time window |
# MAGIC | Q2 | Market notices about constraints in NSW1 | Vector Search MCP | Semantic document search |
# MAGIC | Q3 | Peak demand calculation for QLD1 | UC Function MCP | Deterministic calculation |
# MAGIC | Q4 | Price spikes in SA1 AND dispatched generators | Genie + UC Function | Multi-tool chain |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Question 1: Average spot price via Genie MCP

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Side-by-side with Genie before running Q1
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Open Genie in a separate tab: Left sidebar → Genie → AEMO NEM Operations → [Chat]
# MAGIC Ask: "What was the average spot price in VIC1 for the last available day?"
# MAGIC The agent's answer below should match Genie's direct answer.
# MAGIC If they differ, the agent routed to the wrong tool — check the MLflow trace.
# MAGIC ```

# COMMAND ----------

q1 = (
    "What was the average spot price in VIC1 for the most recent full day in the dataset? "
    "Express in $/MWh and note how many intervals are included in the average."
)

print(f"Q1: {q1}\nExpected tool: ask_aemo_nem_operations (Genie)\nRunning...\n")

with mlflow.start_run(run_name="lab03_q1_avg_price"):
    answer_q1 = asyncio.run(build_and_run_agent(q1, run_name="q1_avg_price"))

print("=" * 65)
print("AGENT ANSWER — Q1:")
print("=" * 65)
print(answer_q1)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q1:
# MAGIC =================================================================
# MAGIC The average spot price in VIC1 for the most recent full day was **$87.15/MWh**,
# MAGIC calculated across **288 intervals** (24 hours × 12 five-minute intervals/hour).
# MAGIC
# MAGIC (Source: NEM dispatch data via Genie)
# MAGIC Note: This data reflects the workshop dataset and may not represent live NEM conditions.
# MAGIC ```
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | Tool used | MLflow trace shows `ask_aemo_nem_operations` was called |
# MAGIC | Unit | Answer shows `$/MWh` not `$/kWh` |
# MAGIC | Interval count | 288 = 24 hours × 12 five-minute intervals |
# MAGIC | Region code | Says "VIC1" not "VIC" |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Question 2: Market notices via Vector Search MCP

# COMMAND ----------

q2 = (
    "Search for any market notices about constraint issues or constraint violations in NSW1. "
    "Summarise the top 3 most relevant notices — include the notice ID, date, and key content."
)

print(f"Q2: {q2[:80]}...\nExpected tool: search_aemo_market_notices_index (Vector Search)\nRunning...\n")

with mlflow.start_run(run_name="lab03_q2_market_notices"):
    answer_q2 = asyncio.run(build_and_run_agent(q2, run_name="q2_market_notices"))

print("=" * 65)
print("AGENT ANSWER — Q2:")
print("=" * 65)
print(answer_q2)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q2:
# MAGIC =================================================================
# MAGIC 1. **MN-2024-0187** (2024-02-28): Constraint Set NSW_MAIN_2 activated due to
# MAGIC    Transgrid 330kV outage, limiting NSW1 imports from QLD1 to 850 MW for ~4 hours.
# MAGIC    (Source: market notices, notice ID MN-2024-0187)
# MAGIC
# MAGIC 2. **MN-2024-0203** (2024-03-14): NSW–VIC interconnector below normal capacity
# MAGIC    following planned maintenance.
# MAGIC    (Source: market notices, notice ID MN-2024-0203)
# MAGIC ```
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | Tool used | MLflow trace shows `search_aemo_market_notices_index` |
# MAGIC | Semantic match | Notices returned discuss constraints even if not all say "constraint" |
# MAGIC | Notice IDs | Format MN-YYYY-XXXX in each result |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Question 3: Peak demand via UC Function MCP

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ UI: Check the UC function Comment before Q3
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Catalog → workshop_au → aemo → Functions → get_region_summary
# MAGIC Read the Comment: the "Not for single-day spot prices..." clause is what prevents
# MAGIC the LLM from using this function when the user asks for per-interval data.
# MAGIC Negative examples in Comments are as important as positive descriptions.
# MAGIC ```

# COMMAND ----------

q3 = (
    "Calculate the peak demand and average spot price for QLD1 over the last 30 days "
    "in the dataset. Also give me the top 3 fuel types by total generation during that period."
)

print(f"Q3: {q3}\nExpected tool: workshop_au__aemo__get_region_summary (UC Function)\nRunning...\n")

with mlflow.start_run(run_name="lab03_q3_peak_demand"):
    answer_q3 = asyncio.run(build_and_run_agent(q3, run_name="q3_peak_demand"))

print("=" * 65)
print("AGENT ANSWER — Q3:")
print("=" * 65)
print(answer_q3)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q3:
# MAGIC =================================================================
# MAGIC QLD1 performance summary — last 30 days:
# MAGIC
# MAGIC   Average spot price    : $104.70/MWh
# MAGIC   Price spikes >$300    : 8 intervals
# MAGIC   Peak demand interval  : 2024-06-21 17:30 AEST
# MAGIC
# MAGIC   Generation by fuel type (top 3):
# MAGIC   1. Coal: 48.2%    2. Gas: 21.7%    3. Solar: 18.9%
# MAGIC
# MAGIC (Source: get_region_summary function)
# MAGIC ```
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | Tool used | MLflow trace shows `workshop_au__aemo__get_region_summary` |
# MAGIC | Parameters | Trace shows `region="QLD1"`, `days=30` |
# MAGIC | Source | "get_region_summary function" not "Genie" |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Question 4: Multi-tool chain (Genie + UC Function + Vector Search)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Predict the tool sequence before running Q4
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Question 4 requires: spike data (Genie) → dispatch data (Genie) →
# MAGIC                      DUID lookup (UC Function) → market notices (Vector Search)
# MAGIC
# MAGIC Write your predicted tool sequence here before running:
# MAGIC   My prediction: _________________________________________________
# MAGIC Then compare to the MLflow trace after the run.
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

print(f"Q4 (compound — predicting multi-tool chain):")
print(f"  {q4[:100]}...")
print("\nExpected tool sequence:")
print("  1. ask_aemo_nem_operations → find spike intervals (Genie SQL)")
print("  2. ask_aemo_nem_operations → get dispatch data for those intervals")
print("  3. workshop_au__aemo__lookup_duid_info → generator names per DUID")
print("  4. search_aemo_market_notices_index → notices about SA1 price events")
print("\nRunning (may take 30-60 seconds for multi-tool chain)...\n")

with mlflow.start_run(run_name="lab03_q4_spike_analysis"):
    answer_q4 = asyncio.run(build_and_run_agent(q4, run_name="q4_spike_analysis"))

print("=" * 65)
print("AGENT ANSWER — Q4 (multi-tool chain):")
print("=" * 65)
print(answer_q4)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (structure — actual values depend on dataset):**
# MAGIC ```
# MAGIC =================================================================
# MAGIC AGENT ANSWER — Q4 (multi-tool chain):
# MAGIC =================================================================
# MAGIC There were 4 price spike intervals in SA1 exceeding $1,000/MWh:
# MAGIC
# MAGIC | # | Date / Time (AEST)  | Spot Price ($/MWh) |
# MAGIC |---|---------------------|--------------------|
# MAGIC | 1 | 2024-06-18 17:00    | $14,000.00 (MPC)   |
# MAGIC | 2 | 2024-06-18 17:05    | $11,200.00         |
# MAGIC
# MAGIC Generators dispatched during spike intervals on 18 June 2024:
# MAGIC - TORRB1 (Torrens Island B Unit 1) — Gas CCGT, AGL Energy — 200 MW
# MAGIC - PELICAN1 (Pelican Point) — Gas CCGT, Engie — 478 MW
# MAGIC
# MAGIC Related market notices:
# MAGIC - MN-2024-0419: "LOR2 Declared — South Australia. Reserve margin below LOR2 threshold."
# MAGIC
# MAGIC (Sources: NEM dispatch data via Genie, lookup_duid_info function, market notices search)
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2</strong><br>
# MAGIC   You ran 4 questions: Genie, Vector Search, UC Function, and multi-tool chain. The agent routed each question to the correct MCP server based on tool descriptions alone. Section 3 inspects the traces.
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
# MAGIC Left sidebar → Machine Learning → Experiments
# MAGIC → /Shared/workshop2c-aemo-operations-agent → click lab03_q4_spike_analysis → Traces tab
# MAGIC
# MAGIC In the trace tree, MCP calls appear as spans labeled with the tool name.
# MAGIC Expand any span to see: request sent to MCP, response received, latency per span.
# MAGIC Click any LLMCall span to see full message history, reasoning, and token counts.
# MAGIC
# MAGIC Trace structure for Q4 (multi-tool):
# MAGIC   AgentRun → LLMCall → ToolCall(ask_aemo_nem_operations)
# MAGIC           → LLMCall → ToolCall(ask_aemo_nem_operations)
# MAGIC           → LLMCall → ToolCall(lookup_duid_info)
# MAGIC           → LLMCall → ToolCall(search_aemo_market_notices_index)
# MAGIC           → LLMCall → final answer
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Retrieve the Q4 trace programmatically

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient

client_mlflow = MlflowClient()
experiment    = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)

if not experiment:
    print(f"Experiment not found: {MLFLOW_EXPERIMENT}")
else:
    runs = client_mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.mlflow.runName = 'lab03_q4_spike_analysis'",
        order_by=["start_time DESC"],
        max_results=1,
    )

    if not runs:
        print("Run 'lab03_q4_spike_analysis' not found — make sure Section 2.4 ran successfully.")
    else:
        run    = runs[0]
        run_id = run.info.run_id
        print(f"Run: {run.info.run_name}")
        print(f"ID : {run_id}")
        print(f"URL: {HOST}/ml/experiments/{experiment.experiment_id}/runs/{run_id}\n")

        try:
            traces = mlflow.search_traces(
                experiment_ids=[experiment.experiment_id],
                filter_string=f"attributes.run_id = '{run_id}'",
                max_results=5,
            )
            print(f"Traces found: {len(traces)}")
            for trace in traces:
                print(f"\n  Trace ID  : {trace.info.trace_id}")
                print(f"  Status    : {trace.info.status}")
                print(f"  Duration  : {trace.info.execution_time_ms}ms")
                if hasattr(trace, "data") and trace.data:
                    spans      = trace.data.spans
                    tool_spans = [s for s in spans if s.span_type.name == "TOOL"]
                    llm_spans  = [s for s in spans if s.span_type.name == "LLM"]
                    print(f"  LLM calls : {len(llm_spans)}")
                    print(f"  Tool calls: {len(tool_spans)}")
                    if tool_spans:
                        print(f"  Tools used: {[s.name for s in tool_spans]}")
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
# MAGIC   Trace ID  : 0196xyz...
# MAGIC   Status    : OK
# MAGIC   Duration  : 44823ms
# MAGIC   LLM calls : 5
# MAGIC   Tool calls: 4
# MAGIC   Tools used: ['ask_aemo_nem_operations', 'ask_aemo_nem_operations',
# MAGIC               'workshop_au__aemo__lookup_duid_info', 'search_aemo_market_notices_index']
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Compare latency across the 4 questions

# COMMAND ----------

question_runs = [
    "lab03_q1_avg_price",
    "lab03_q2_market_notices",
    "lab03_q3_peak_demand",
    "lab03_q4_spike_analysis",
]

experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)

if experiment:
    print(f"  {'Run name':<35} {'Duration':>12} {'Tool calls':>12} {'LLM calls':>10}")
    print("  " + "-" * 73)

    for run_name in question_runs:
        runs = client_mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"tags.mlflow.runName = '{run_name}'",
            order_by=["start_time DESC"], max_results=1,
        )
        if runs:
            r          = runs[0]
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

    print("\nObservations:")
    print("  Q4 (multi-tool) is slowest — each tool call adds latency")
    print("  Genie calls are slowest per tool (SQL execution + NL translation)")
    print("  UC Function calls are fastest (deterministic Python, no SQL)")
    print("  Vector Search calls are fast (pre-built embedding index)")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC   Run name                             Duration   Tool calls  LLM calls
# MAGIC   -------------------------------------------------------------------------
# MAGIC   lab03_q1_avg_price                       11.2s            1          2
# MAGIC   lab03_q2_market_notices                   8.4s            1          2
# MAGIC   lab03_q3_peak_demand                     12.8s            1          2
# MAGIC   lab03_q4_spike_analysis                  44.8s            4          5
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Share trace URLs with your team

# COMMAND ----------

print("Shareable trace URLs for this session:\n")

if experiment:
    for run_name in ["lab03_q4_spike_analysis", "lab03_q1_avg_price"]:
        runs = client_mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"tags.mlflow.runName = '{run_name}'",
            order_by=["start_time DESC"], max_results=1,
        )
        if runs:
            r   = runs[0]
            url = f"{HOST}/ml/experiments/{experiment.experiment_id}/runs/{r.info.run_id}"
            print(f"  {run_name}:\n    {url}\n")

print("Anyone with CAN_READ on the experiment can view traces.")
print(f"Grant access: Machine Learning → Experiments → {MLFLOW_EXPERIMENT} → Permissions")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC   lab03_q4_spike_analysis:
# MAGIC     https://adb-xxxx.azuredatabricks.net/ml/experiments/87654321/runs/abc123def
# MAGIC
# MAGIC   lab03_q1_avg_price:
# MAGIC     https://adb-xxxx.azuredatabricks.net/ml/experiments/87654321/runs/xyz789abc
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 3</strong><br>
# MAGIC   You retrieved traces programmatically, compared latency across question types, and generated shareable trace URLs. The Bonus section shows how to connect your laptop to the same MCP servers.
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
# MAGIC Any MCP-compatible client (Claude Desktop, Cursor, VS Code + MCP extension) can connect to your Databricks workspace MCP servers using a Personal Access Token.
# MAGIC
# MAGIC **Data residency note:** MCP tool calls go directly from your laptop to your Databricks workspace — not via Anthropic. The AEMO data stays within the Databricks workspace. Review your organisation's AI acceptable use policy before using Claude Desktop with production data.
# MAGIC
# MAGIC ```
# MAGIC Get a PAT: Settings (user icon) → Developer → Access tokens → [Generate new token]
# MAGIC   Comment: workshop-2c-claude-desktop   Lifetime: 30 days
# MAGIC   Copy the token — shown only once. Never commit to git.
# MAGIC ```

# COMMAND ----------

import json as _json

config_output = {
    "mcpServers": {
        "databricks-aemo-uc-functions": {
            "command": "npx",
            "args": [
                "mcp-remote",
                f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}",
                "--header", "Authorization: Bearer <YOUR_PAT_HERE>"
            ]
        },
        "databricks-aemo-market-notices": {
            "command": "npx",
            "args": [
                "mcp-remote", VS_MCP_URL,
                "--header", "Authorization: Bearer <YOUR_PAT_HERE>"
            ]
        }
    }
}

if GENIE_SPACE_ID:
    config_output["mcpServers"]["databricks-aemo-genie"] = {
        "command": "npx",
        "args": [
            "mcp-remote",
            f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            "--header", "Authorization: Bearer <YOUR_PAT_HERE>"
        ]
    }

print("Your claude_desktop_config.json snippet")
print("(replace <YOUR_PAT_HERE> with your actual token)\n")
print("File location:")
print("  macOS   : ~/Library/Application Support/Claude/claude_desktop_config.json")
print("  Windows : %APPDATA%\\Claude\\claude_desktop_config.json\n")
print("=" * 65)
print(_json.dumps(config_output, indent=2))
print("=" * 65)
print("\nAfter saving, restart Claude Desktop. In the chat input, click the hammer icon.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 2 — Query the audit trail for your MCP calls

# COMMAND ----------

from datetime import datetime, timedelta

audit_sql = f"""
SELECT
    event_time,
    user_identity.email           AS user_email,
    service_name,
    action_name,
    request_params.toolName       AS tool_name,
    request_params.query          AS query_text
FROM system.access.audit
WHERE user_identity.email = '{ws.current_user.me().user_name}'
  AND event_time > '{(datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")}'
  AND service_name = 'mcpServer' AND action_name = 'mcpToolsCall'
ORDER BY event_time DESC
LIMIT 50
"""

print("Run this SQL in a SQL cell or Databricks SQL editor to see your audit trail:\n")
print("=" * 65)
print(audit_sql)
print("=" * 65)
print("\nAudit trail columns for MCP calls:")
print("  service_name = 'mcpServer'  for ALL MCP tool calls (UC Functions, Genie, Vector Search)")
print("  action_name = 'mcpToolsCall' fixed value for all MCP tool calls (filter value, not tool name)")
print("  response.statusCode         200 = success, 4xx/5xx = error")
print("\nThis is your compliance audit trail — required for AEMO and AER regulated workloads.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 3 — Production deployment preview

# COMMAND ----------

# Production deployment pattern — REFERENCE ONLY
# The only difference from the notebook version:
#   resources = await multi_client.get_databricks_resources()
#   mlflow.langchain.log_model(..., resources=resources)
#
# get_databricks_resources() introspects the MCP server list and returns
# DatabricksResource declarations that tell Model Serving which UC schemas,
# Genie Spaces, and VS indexes the service principal needs at inference time.

PRODUCTION_REFERENCE = '''
# async def build_agent_for_deployment():
#     async with DatabricksMultiServerMCPClient(all_servers) as multi_client:
#         tools     = await multi_client.get_tools()
#         agent     = create_react_agent(
#             model=ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0),
#             tools=tools, prompt=AEMO_SYSTEM_PROMPT,
#         )
#         resources = await multi_client.get_databricks_resources()
#         return agent, resources
#
# agent, resources = asyncio.run(build_agent_for_deployment())
#
# with mlflow.start_run(run_name="aemo-agent-production-v1"):
#     mlflow.langchain.log_model(
#         lc_model=agent,
#         artifact_path="aemo_operations_agent",
#         resources=resources,   # <- critical for Model Serving auth
#         input_example={"input": "What was the average VIC1 price yesterday?"},
#     )
'''

print("Production deployment pattern (reference only):")
print(PRODUCTION_REFERENCE)
print("The two lines that differ from the notebook version:")
print("  resources = await multi_client.get_databricks_resources()")
print("  mlflow.langchain.log_model(..., resources=resources)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 4 — Try it yourself: Add the regulatory compliance tool

# COMMAND ----------

# Step 1 — Create a reference table for NEM regulatory thresholds
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

threshold_rows = [
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
    StructField("region",              StringType(), False),
    StructField("threshold_name",      StringType(), False),
    StructField("threshold_value_mwh", DoubleType(), False),
    StructField("description",         StringType(), True),
])

(spark.createDataFrame(threshold_rows, threshold_schema)
      .write.format("delta").mode("overwrite")
      .option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds"))

print(f"Created: {CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds")
spark.table(f"{CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 2 — Register the UC function (uncomment and run):**

# COMMAND ----------

# TODO: Uncomment and run this block to register the new MCP tool.
#
# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA_AEMO}.check_nem_price_compliance(
#     region           STRING  COMMENT 'NEM region code. Values: NSW1, VIC1, QLD1, SA1, TAS1',
#     threshold_name   STRING  COMMENT 'Threshold: ADMINISTERED_PRICE_CAP, MARKET_PRICE_CAP, SPOT_PRICE_LOR1_TRIGGER',
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
#     from pyspark.sql import SparkSession, functions as F
#     spark = SparkSession.builder.getOrCreate()
#     row = (spark.table("{CATALOG}.{SCHEMA_AEMO}.nem_price_thresholds")
#            .filter((F.col("region") == region) & (F.col("threshold_name") == threshold_name))
#            .first())
#     if row is None:
#         return json.dumps({{"error": f"No threshold for {{threshold_name}} in {{region}}"}})
#     threshold = float(row["threshold_value_mwh"])
#     compliant = actual_price_mwh <= threshold
#     return json.dumps({{
#         "region": region, "threshold_name": threshold_name,
#         "threshold_value_mwh": threshold, "actual_price_mwh": actual_price_mwh,
#         "compliant": compliant,
#         "overage_mwh": round(actual_price_mwh - threshold, 2) if not compliant else 0.0,
#     }})
# except Exception as e:
#     return json.dumps({{"error": str(e)}})
# $$
# """)
# print(f"Registered: {CATALOG}.{SCHEMA_AEMO}.check_nem_price_compliance")
print("Uncomment the spark.sql block above, then run to register the new tool.")
print("Once registered, it is automatically discovered — no agent code changes needed.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 3 — Verify the new tool appears:**

# COMMAND ----------

async def verify_new_tool():
    async with DatabricksMultiServerMCPClient(all_servers) as multi_client:
        tools      = await multi_client.get_tools()
        tool_names = [t.name for t in tools]
        compliance_tool = f"{CATALOG}__{SCHEMA_AEMO}__check_nem_price_compliance"

        print(f"All available tools ({len(tools)}):")
        for name in tool_names:
            marker = " <- NEW" if "compliance" in name else ""
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
# MAGIC ```python
# MAGIC compliance_q = (
# MAGIC     "The spot price in SA1 reached $450/MWh during interval 18:30 yesterday. "
# MAGIC     "Has this breached the Administered Price Cap? If yes, what does this mean?"
# MAGIC )
# MAGIC with mlflow.start_run(run_name="bonus_compliance_check"):
# MAGIC     answer = asyncio.run(build_and_run_agent(compliance_q, run_name="compliance_check"))
# MAGIC print(answer)
# MAGIC ```
# MAGIC
# MAGIC | Check | Expected |
# MAGIC |-------|---------|
# MAGIC | Tool used | `workshop_au__aemo__check_nem_price_compliance` |
# MAGIC | Parameters | `region='SA1', threshold_name='ADMINISTERED_PRICE_CAP', actual_price_mwh=450.0` |
# MAGIC | Answer | Confirms breach (APC=$300, actual=$450, overage=$150) |
# MAGIC | Not Genie | Agent did NOT call Genie — used the deterministic function |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 03 Complete</strong><br>
# MAGIC   You built a production-grade LangGraph ReAct agent, tested it with 4 AEMO questions,
# MAGIC   inspected full reasoning traces in MLflow, and understood the production deployment pattern.
# MAGIC   The agent routes questions to the correct MCP server without any hardcoded logic —
# MAGIC   all based on tool descriptions you control in Unity Catalog and Genie.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lab 03 — Review questions
# MAGIC
# MAGIC 1. The Q4 trace shows the agent called `ask_aemo_nem_operations` twice. Why two Genie calls instead of one? What did the second call need that the first result did not contain?
# MAGIC
# MAGIC 2. Q3 (UC Function) took 12.8 seconds even though UC functions run fast. What is likely adding most of the latency, and how would you reduce it?
# MAGIC
# MAGIC 3. You add a new UC function `summarise_dispatch_bids` to `workshop_au.aemo`. Do you need to update the agent code to make the agent aware of this new tool? Why or why not?
# MAGIC
# MAGIC 4. The system prompt tells the agent to always include a data freshness disclaimer. The warm-up answer included it, but your Q4 answer did not. What is the most likely cause and how would you debug this?
# MAGIC
# MAGIC 5. A security reviewer asks: "Can the agent access tables outside `workshop_au.aemo`?" Give a complete technical answer covering UC permissions, Genie Space trusted assets, and Vector Search index scope.
# MAGIC
# MAGIC ---

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 28px 32px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 12px 0; font-family: 'DM Sans', sans-serif;">
# MAGIC     Workshop 2c Complete — What you built
# MAGIC   </h2>
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
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 8px 0; font-weight: bold;">Key packages:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0 0 14px 0; padding-left: 20px; font-size: 0.92em;">
# MAGIC     <li><code>databricks-mcp</code> — <code>DatabricksMCPClient</code> for tool discovery and direct calls</li>
# MAGIC     <li><code>databricks-langchain</code> — <code>DatabricksMultiServerMCPClient</code>, <code>DatabricksMCPServer</code>, <code>ChatDatabricks</code></li>
# MAGIC     <li><code>langgraph</code> — <code>create_react_agent</code> for the ReAct loop</li>
# MAGIC     <li><code>mlflow</code> — <code>langchain.autolog()</code> for automatic trace capture</li>
# MAGIC   </ul>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 6px 0; font-weight: bold;">Next steps:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0; padding-left: 20px; font-size: 0.92em;">
# MAGIC     <li>Deploy to Model Serving with <code>get_databricks_resources()</code></li>
# MAGIC     <li>Add human-in-the-loop confirmation for high-stakes tool calls</li>
# MAGIC     <li>Production checklist: Service Principal auth, Secret Scopes, MLflow evaluation</li>
# MAGIC     <li>Governance: <code>system.access.audit</code> dashboard for MCP call visibility</li>
# MAGIC   </ul>
# MAGIC </div>
