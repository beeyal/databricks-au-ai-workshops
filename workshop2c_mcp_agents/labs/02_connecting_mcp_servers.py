# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 02: Connecting to Databricks MCP Servers
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Energy Sector
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Low-level MCP client exploration, Genie NL-to-SQL, Vector Search semantic search,
# MAGIC     and multi-server tool aggregation — all hands-on before building the agent.
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>40 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Lab 01 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All MCP endpoints: AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Auth</strong><br>Automatic via WorkspaceClient
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will learn
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | Low-Level MCP Client | `DatabricksMCPClient` — connect to UC Functions, list tools, inspect schemas, call directly | 10 min |
# MAGIC | 2 | Genie Space as MCP Server | Find Space ID in UI, connect, call with NEM questions, inspect SQL + result | 10 min |
# MAGIC | 3 | Vector Search as MCP Server | Find index in UI, connect, semantic search over market notices | 10 min |
# MAGIC | 4 | Multi-Server Tool Discovery | `DatabricksMultiServerMCPClient`, aggregate all tools, understand the 20-tool limit | 10 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why learn the low-level client before building an agent?
# MAGIC
# MAGIC When your agent makes the wrong tool call or returns a bad answer, you need to debug at the
# MAGIC MCP level — not just at the "agent said X" level. Understanding what each MCP server returns
# MAGIC lets you:
# MAGIC - Verify tools exist and have the right descriptions before connecting an LLM
# MAGIC - Test tool calls directly without waiting for LLM inference
# MAGIC - Inspect the raw MCP response shape (needed when parsing results in custom agents)
# MAGIC - Confirm UC function permissions are correct before an agent hits a 403

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration (loads Lab 01 values)

# COMMAND ----------

# Restore Lab 01 configuration. If the file does not exist (different cluster),
# fill in the widgets manually — they will override the file values.

import json
from pathlib import Path

# Try to load saved config; fall back to empty dict if not found
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

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME  = dbutils.widgets.get("vs_index")

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print("Configuration loaded.")
print(f"  HOST           : {HOST}")
print(f"  CATALOG.SCHEMA : {CATALOG}.{SCHEMA_AEMO}")
print(f"  PT_ENDPOINT    : {PT_ENDPOINT}")
print(f"  GENIE_SPACE_ID : {GENIE_SPACE_ID}")
print(f"  VS_INDEX_NAME  : {VS_INDEX_NAME}")

if GENIE_SPACE_ID == "FILL_IN":
    print("\nNOTE: Genie Space ID not set — Section 2 will be skipped.")
    print("      Navigate: Genie → AEMO NEM Operations → copy ID from URL bar.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Configuration loaded.
# MAGIC   HOST           : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC   CATALOG.SCHEMA : workshop_au.aemo
# MAGIC   PT_ENDPOINT    : au_east_llm_inregion
# MAGIC   GENIE_SPACE_ID : 01jxyz123abc456
# MAGIC   VS_INDEX_NAME  : workshop_au.aemo.aemo_market_notices_index
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — Low-Level MCP Client: Discover Available Tools (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — What the UC Functions MCP server exposes
# MAGIC </div>
# MAGIC
# MAGIC Before running any code, look at the UC Functions in the Catalog UI.
# MAGIC This is exactly what the MCP client will discover programmatically.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog → workshop_au → aemo → Functions
# MAGIC
# MAGIC ┌─── Catalog Explorer: Functions ───────────────────────────────────────────┐
# MAGIC │  workshop_au.aemo.calculate_peak_demand                                   │
# MAGIC │    RETURNS STRING                                                         │
# MAGIC │    COMMENT: "Calculate peak spot price and total dispatch for a NEM       │
# MAGIC │     region on a given date. Returns JSON with: region, date,              │
# MAGIC │     peak_price_mwh, peak_interval, total_dispatch_mw, avg_price_mwh.     │
# MAGIC │     Use for questions about a specific region's price or dispatch on a    │
# MAGIC │     single day. Not for multi-day trends (use Genie for those)."          │
# MAGIC │                                                                           │
# MAGIC │  workshop_au.aemo.get_region_summary                                     │
# MAGIC │    RETURNS STRING                                                         │
# MAGIC │    COMMENT: "Return a JSON summary of NEM region conditions for a         │
# MAGIC │     rolling window..."                                                    │
# MAGIC │                                                                           │
# MAGIC │  workshop_au.aemo.lookup_duid_info                                       │
# MAGIC │    RETURNS STRING                                                         │
# MAGIC │    COMMENT: "Look up generator information by DUID (Dispatchable Unit    │
# MAGIC │     Identifier)..."                                                       │
# MAGIC └───────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Notice: the COMMENT on each function IS the tool description the LLM will read.
# MAGIC Click on calculate_peak_demand → scroll to "Comment" — it should be a full paragraph
# MAGIC describing what questions this function answers, not just what it returns.
# MAGIC ```
# MAGIC
# MAGIC **Also check permissions:**
# MAGIC ```
# MAGIC Click calculate_peak_demand → Permissions tab
# MAGIC
# MAGIC You should see:
# MAGIC   EXECUTE  →  your user or your group (e.g. workshop-participants)
# MAGIC
# MAGIC Without EXECUTE, the MCP server returns HTTP 403 when the agent calls the tool.
# MAGIC This is the UC governance control for MCP tool access.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Connect with `DatabricksMCPClient` and list tools

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient
import json

ws  = WorkspaceClient()
# Re-read HOST after restart in case WorkspaceClient was recreated
HOST = ws.config.host.rstrip("/")

# The UC Functions MCP endpoint URL for the whole schema
uc_mcp_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"

print(f"UC Functions MCP endpoint:")
print(f"  {uc_mcp_url}")
print()

# WorkspaceClient() auto-authenticates from notebook context.
# DatabricksMCPClient wraps the HTTP calls and handles MCP protocol framing.
client = DatabricksMCPClient(uc_mcp_url, ws)

tools = client.list_tools()

print(f"Discovered {len(tools)} tool(s) in {CATALOG}.{SCHEMA_AEMO}:\n")
for t in tools:
    desc_preview = (t.description or "")[:100]
    print(f"  Tool: {t.name}")
    print(f"  Desc: {desc_preview}...")
    if hasattr(t, "inputSchema") and t.inputSchema:
        params = list(t.inputSchema.get("properties", {}).keys())
        print(f"  Params: {params}")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC UC Functions MCP endpoint:
# MAGIC   https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/aemo
# MAGIC
# MAGIC Discovered 3 tool(s) in workshop_au.aemo:
# MAGIC
# MAGIC   Tool: workshop_au__aemo__calculate_peak_demand
# MAGIC   Desc: Calculate peak spot price and total dispatch for a NEM region on a given date.
# MAGIC         Returns JSON with: region, date, peak_price_mwh, peak_interval, total_dispatch_mw...
# MAGIC   Params: ['region', 'date']
# MAGIC
# MAGIC   Tool: workshop_au__aemo__get_region_summary
# MAGIC   Desc: Return a JSON summary of NEM region conditions for a rolling window. Covers avg
# MAGIC         spot price, number of price spikes (>$300/MWh), total generation by fuel type...
# MAGIC   Params: ['region', 'days']
# MAGIC
# MAGIC   Tool: workshop_au__aemo__lookup_duid_info
# MAGIC   Desc: Look up generator information by DUID (Dispatchable Unit Identifier)...
# MAGIC   Params: ['duid']
# MAGIC ```
# MAGIC
# MAGIC The tool names follow the `catalog__schema__function_name` pattern (double-underscores).
# MAGIC This is consistent across all UC Functions MCP endpoints.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Inspect a full tool schema
# MAGIC
# MAGIC The `inputSchema` on each tool is a JSON Schema object. The LLM uses this to know
# MAGIC what arguments to pass. Let us look at the full schema for `calculate_peak_demand`:

# COMMAND ----------

# Find and print the full schema for calculate_peak_demand
target_tool = next(
    (t for t in tools if "calculate_peak_demand" in t.name),
    None
)

if target_tool:
    print(f"Full schema for: {target_tool.name}")
    print("=" * 60)
    print(f"Description:\n  {target_tool.description}")
    print()
    if hasattr(target_tool, "inputSchema") and target_tool.inputSchema:
        print("Input schema (JSON Schema):")
        print(json.dumps(target_tool.inputSchema, indent=2))
    else:
        print("No inputSchema found.")
else:
    print("Tool not found — check CATALOG and SCHEMA_AEMO widget values.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Full schema for: workshop_au__aemo__calculate_peak_demand
# MAGIC ============================================================
# MAGIC Description:
# MAGIC   Calculate peak spot price and total dispatch for a NEM region on a given date.
# MAGIC   Returns JSON with: region, date, peak_price_mwh, peak_interval, total_dispatch_mw,
# MAGIC   avg_price_mwh. Use for questions about a specific region's price or dispatch
# MAGIC   performance on a single day. Not for multi-day trends — use the Genie tool for those.
# MAGIC
# MAGIC Input schema (JSON Schema):
# MAGIC {
# MAGIC   "type": "object",
# MAGIC   "properties": {
# MAGIC     "region": {
# MAGIC       "type": "string",
# MAGIC       "description": "NEM region code. Values: NSW1, VIC1, QLD1, SA1, TAS1"
# MAGIC     },
# MAGIC     "date": {
# MAGIC       "type": "string",
# MAGIC       "description": "Date in YYYY-MM-DD format (AEST)"
# MAGIC     }
# MAGIC   },
# MAGIC   "required": ["region", "date"]
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC The JSON Schema `description` fields on each parameter come from the
# MAGIC `COMMENT` annotations on the UC function parameters. Well-written parameter
# MAGIC descriptions prevent the LLM from passing malformed values (e.g. "VIC" instead of "VIC1").

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Call a UC function directly via `DatabricksMCPClient`
# MAGIC
# MAGIC `client.call_tool()` makes a direct MCP tool call. Use this for:
# MAGIC - Testing a UC function without spinning up an agent
# MAGIC - Debugging function output independently from LLM reasoning
# MAGIC - Verifying permission grants are in place

# COMMAND ----------

from datetime import date, timedelta

# Use yesterday's date for the query (data is more likely to exist)
query_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
tool_name  = f"{CATALOG}__{SCHEMA_AEMO}__calculate_peak_demand"

print(f"Calling: {tool_name}")
print(f"Args   : region='VIC1', date='{query_date}'")
print()

result = client.call_tool(
    tool_name,
    {
        "region": "VIC1",
        "date":   query_date,
    },
)

print("Raw MCP response:")
print(json.dumps(result, indent=2, default=str))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC Calling: workshop_au__aemo__calculate_peak_demand
# MAGIC Args   : region='VIC1', date='2024-06-30'
# MAGIC
# MAGIC Raw MCP response:
# MAGIC {
# MAGIC   "content": [
# MAGIC     {
# MAGIC       "type": "text",
# MAGIC       "text": "{\"region\": \"VIC1\", \"date\": \"2024-06-30\",
# MAGIC                \"peak_price_mwh\": 342.50, \"peak_interval\": \"17:30\",
# MAGIC                \"total_dispatch_mw\": 5840.2, \"avg_price_mwh\": 87.40}"
# MAGIC     }
# MAGIC   ],
# MAGIC   "isError": false
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC Every MCP server type (Genie, Vector Search, UC Functions) uses this same envelope:
# MAGIC a `content` array of items, each with `type` and `text` (or `data` for binary).
# MAGIC The `isError: false` field confirms the UC function executed without raising an exception.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Parse and display the function result

# COMMAND ----------

# Parse the nested JSON out of the MCP content envelope
if result and not result.get("isError", False) and "content" in result:
    raw_text = result["content"][0]["text"]
    try:
        parsed = json.loads(raw_text)
        print(f"Parsed result for VIC1 on {query_date}:")
        print()
        print(f"  Region              : {parsed.get('region', 'n/a')}")
        print(f"  Date                : {parsed.get('date', 'n/a')}")
        print(f"  Peak price ($/MWh)  : {parsed.get('peak_price_mwh', 'n/a')}")
        print(f"  Peak interval       : {parsed.get('peak_interval', 'n/a')}")
        print(f"  Avg price ($/MWh)   : {parsed.get('avg_price_mwh', 'n/a')}")
        print(f"  Total dispatch (MW) : {parsed.get('total_dispatch_mw', 'n/a')}")
        print()

        # Was there a price spike? (threshold: $300/MWh)
        peak = parsed.get("peak_price_mwh", 0)
        if peak and float(peak) > 300:
            print(f"  NOTE: Peak price ${peak}/MWh exceeded $300/MWh spike threshold.")
        else:
            print(f"  NOTE: No price spike (peak below $300/MWh threshold).")

    except json.JSONDecodeError:
        print("Result is plain text (not JSON):")
        print(raw_text)

elif result and result.get("isError"):
    print("Tool call returned an error:")
    print(result.get("content", [{"text": "Unknown error"}])[0].get("text", ""))
else:
    print("No result returned — check that the UC function exists and you have EXECUTE permission.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Parsed result for VIC1 on 2024-06-30:
# MAGIC
# MAGIC   Region              : VIC1
# MAGIC   Date                : 2024-06-30
# MAGIC   Peak price ($/MWh)  : 342.50
# MAGIC   Peak interval       : 17:30
# MAGIC   Avg price ($/MWh)   : 87.40
# MAGIC   Total dispatch (MW) : 5840.2
# MAGIC
# MAGIC   NOTE: Peak price $342.50/MWh exceeded $300/MWh spike threshold.
# MAGIC ```
# MAGIC
# MAGIC This is exactly the data the agent will use in Lab 03 when answering
# MAGIC *"Were there any price spikes in VIC yesterday?"*

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 — Single-function endpoint (least-privilege pattern)
# MAGIC
# MAGIC If you want to expose only one UC function (not the whole schema), use the
# MAGIC single-function endpoint. This is the least-privilege pattern for production agents.

# COMMAND ----------

# Single-function endpoint — exposes only calculate_peak_demand
single_fn_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}/calculate_peak_demand"
single_client = DatabricksMCPClient(single_fn_url, ws)

single_tools = single_client.list_tools()
print(f"Single-function endpoint exposes {len(single_tools)} tool(s):")
for t in single_tools:
    print(f"  {t.name}")

print()
print("When to use single-function vs schema endpoint:")
print()
print("  Schema endpoint (mcp/functions/catalog/schema):")
print("    + Automatically includes new functions as you add them")
print("    + Less URL management — one endpoint per schema")
print("    - Exposes all functions to the agent (no function-level isolation)")
print()
print("  Single-function endpoint (mcp/functions/catalog/schema/function):")
print("    + Least-privilege: agent can only call this one function")
print("    + Useful when one agent should have narrower access than another")
print("    - You must manage one URL per function")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Single-function endpoint exposes 1 tool(s):
# MAGIC   workshop_au__aemo__calculate_peak_demand
# MAGIC
# MAGIC When to use single-function vs schema endpoint:
# MAGIC
# MAGIC   Schema endpoint (mcp/functions/catalog/schema):
# MAGIC     + Automatically includes new functions as you add them
# MAGIC     + Less URL management — one endpoint per schema
# MAGIC     - Exposes all functions to the agent (no function-level isolation)
# MAGIC
# MAGIC   Single-function endpoint (mcp/functions/catalog/schema/function):
# MAGIC     + Least-privilege: agent can only call this one function
# MAGIC     + Useful when one agent should have narrower access than another
# MAGIC     - You must manage one URL per function
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 1 complete</strong><br>
# MAGIC   You used <code>DatabricksMCPClient</code> to discover 3 UC function tools, read their full
# MAGIC   JSON Schema, and make a direct tool call. Auth was automatic. Section 2 connects to the
# MAGIC   Genie Space MCP server and runs NL-to-SQL queries.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Genie Space as MCP Server (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — Confirm your Genie Space ID
# MAGIC </div>
# MAGIC
# MAGIC The Genie MCP server URL requires your Space ID. You found this in Lab 01 Section 2.3.
# MAGIC If you skipped that step, find it now:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Left sidebar → Genie → AEMO NEM Operations
# MAGIC
# MAGIC Look at the browser URL bar:
# MAGIC ┌─── Browser URL ──────────────────────────────────────────────────────────┐
# MAGIC │  https://adb-xxxx.azuredatabricks.net/genie/rooms/01jxyz123abc456def   │
# MAGIC │                                                   ↑                     │
# MAGIC │                                       This is your GENIE_SPACE_ID      │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC If you see /genie/spaces/ instead of /genie/rooms/ — copy the ID after spaces/
# MAGIC Both URL patterns reference the same thing.
# MAGIC
# MAGIC Paste this value into the 'genie_space_id' widget at the top of this notebook
# MAGIC then re-run the Configuration cell before continuing.
# MAGIC ```
# MAGIC
# MAGIC **Also look at the Genie Space configuration before running code:**
# MAGIC ```
# MAGIC Genie → AEMO NEM Operations → Configure tab
# MAGIC
# MAGIC What to check:
# MAGIC   Tables tab: spot_prices, dispatch_intervals, market_notices — all three should be listed
# MAGIC   Instructions tab: should contain AEMO domain context (NEM regions, price spike definition)
# MAGIC   SQL queries tab: should have 3+ golden queries seeded by the setup script
# MAGIC
# MAGIC The MCP tool description that the LLM reads comes from:
# MAGIC   1. The Genie Space title → becomes part of the tool name
# MAGIC   2. The Genie Space description → becomes the tool description
# MAGIC   3. The Instructions → shapes NL-to-SQL translation quality
# MAGIC
# MAGIC A Genie Space with good instructions → better MCP tool call quality.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Connect to Genie Space via MCP and list tools

# COMMAND ----------

# Skip this section if Genie Space ID is not configured
if GENIE_SPACE_ID == "FILL_IN":
    print("Genie Space ID not set — skipping Section 2.")
    print("Set the 'genie_space_id' widget and re-run the Configuration cell to enable this section.")
    GENIE_MCP_AVAILABLE = False
else:
    genie_mcp_url = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
    genie_client  = DatabricksMCPClient(genie_mcp_url, ws)

    genie_tools = genie_client.list_tools()
    print(f"Genie MCP endpoint: {genie_mcp_url}")
    print()
    print(f"Discovered {len(genie_tools)} tool(s):")
    print()
    for t in genie_tools:
        print(f"  Tool name  : {t.name}")
        print(f"  Description: {t.description}")
        print()
        if hasattr(t, "inputSchema") and t.inputSchema:
            props = t.inputSchema.get("properties", {})
            for param_name, param_schema in props.items():
                print(f"    Parameter '{param_name}': {param_schema.get('description','')}")
    GENIE_MCP_AVAILABLE = True

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Genie MCP endpoint: https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/genie/01jxyz...
# MAGIC
# MAGIC Discovered 1 tool(s):
# MAGIC
# MAGIC   Tool name  : ask_aemo_nem_operations
# MAGIC   Description: Ask a natural language question about NEM spot prices, dispatch
# MAGIC                schedules, generator output, or price spike events. The Genie Space
# MAGIC                translates your question to SQL and runs it against the AEMO NEM
# MAGIC                tables. Returns a data table and a plain-English summary.
# MAGIC                Examples: 'What was the average VIC1 price last week?',
# MAGIC                'Show me intervals above $300/MWh in SA1 last month'.
# MAGIC
# MAGIC     Parameter 'question': The natural language question about NEM data to answer.
# MAGIC ```
# MAGIC
# MAGIC The Genie MCP server always exposes **exactly 1 tool** regardless of how many tables
# MAGIC are in the Genie Space. The tool name is derived from the Genie Space title.
# MAGIC This counts as only 1 toward the 20-tool agent limit.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Call the Genie tool directly with an AEMO question

# COMMAND ----------

if not GENIE_MCP_AVAILABLE:
    print("Skipping — Genie Space not configured.")
else:
    genie_tool_name = genie_tools[0].name
    question = "What was the average spot price per region for the last 7 days in the dataset?"

    print(f"Calling: {genie_tool_name}")
    print(f"Question: {question}")
    print()

    genie_result = genie_client.call_tool(genie_tool_name, {"question": question})

    print("Raw MCP response:")
    if genie_result and "content" in genie_result:
        for item in genie_result["content"]:
            item_type = item.get("type", "unknown")
            item_text = item.get("text", "")
            print(f"\n  [{item_type}]")
            print(f"  {item_text[:600]}")
            if len(item_text) > 600:
                print(f"  ... (truncated, total {len(item_text)} chars)")
    else:
        print(genie_result)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Calling: ask_aemo_nem_operations
# MAGIC Question: What was the average spot price per region for the last 7 days in the dataset?
# MAGIC
# MAGIC Raw MCP response:
# MAGIC
# MAGIC   [text]
# MAGIC   The average spot price by NEM region for the last 7 days was:
# MAGIC
# MAGIC   | Region | Avg Price ($/MWh) |
# MAGIC   |--------|------------------|
# MAGIC   | NSW1   | 92.40            |
# MAGIC   | VIC1   | 87.15            |
# MAGIC   | QLD1   | 104.70           |
# MAGIC   | SA1    | 98.25            |
# MAGIC   | TAS1   | 61.80            |
# MAGIC
# MAGIC   [text]
# MAGIC   Generated SQL:
# MAGIC   SELECT region,
# MAGIC          ROUND(AVG(spot_price_mwh), 2) AS avg_price_mwh
# MAGIC   FROM workshop_au.aemo.spot_prices
# MAGIC   WHERE interval_datetime >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
# MAGIC   GROUP BY region
# MAGIC   ORDER BY avg_price_mwh DESC
# MAGIC ```
# MAGIC
# MAGIC The Genie MCP response includes:
# MAGIC - A plain-English summary table (first `text` item)
# MAGIC - The SQL Genie generated (second `text` item)
# MAGIC
# MAGIC The LLM in your agent receives both. In Lab 03 you will see how the agent
# MAGIC cites the data source when constructing its final answer.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Test with an AEMO-specific spike detection question

# COMMAND ----------

if not GENIE_MCP_AVAILABLE:
    print("Skipping — Genie Space not configured.")
else:
    spike_question = (
        "How many intervals had a spot price above $300 per MWh in VIC1? "
        "Show the top 5 highest price intervals with date and time."
    )

    print(f"Question: {spike_question}")
    print()

    spike_result = genie_client.call_tool(genie_tool_name, {"question": spike_question})

    if spike_result and "content" in spike_result:
        for item in spike_result["content"]:
            if item.get("type") == "text":
                print(item["text"][:800])
                print()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Question: How many intervals had a spot price above $300 per MWh in VIC1?
# MAGIC Show the top 5 highest price intervals with date and time.
# MAGIC
# MAGIC There were 14 intervals where the VIC1 spot price exceeded $300/MWh.
# MAGIC
# MAGIC Top 5 highest-priced intervals in VIC1:
# MAGIC
# MAGIC | Rank | Interval Datetime       | Spot Price ($/MWh) |
# MAGIC |------|-------------------------|--------------------|
# MAGIC | 1    | 2024-01-18 17:00:00     | 14,000.00          |
# MAGIC | 2    | 2024-01-18 17:05:00     | 12,300.00          |
# MAGIC | 3    | 2024-02-14 18:30:00     | 8,750.00           |
# MAGIC | 4    | 2024-02-14 18:35:00     | 7,200.00           |
# MAGIC | 5    | 2024-03-07 16:55:00     | 4,150.00           |
# MAGIC
# MAGIC Note: $14,000/MWh is the NEM Market Price Cap (MPC) — the maximum price AEMO
# MAGIC can set for any dispatch interval.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Understanding Genie MCP polling behaviour
# MAGIC
# MAGIC Some Genie questions trigger complex SQL that takes longer to execute.
# MAGIC The Genie MCP server handles this transparently using a polling pattern:
# MAGIC
# MAGIC ```
# MAGIC What happens behind the scenes for a slow Genie query:
# MAGIC
# MAGIC  1. Client sends:  tools/call  {"question": "..."}
# MAGIC  2. Server replies: 202 Accepted  {"conversation_id": "...", "message_id": "..."}
# MAGIC  3. Client polls:  GET /messages/{message_id}  every ~2s
# MAGIC  4. Server replies: {"status": "EXECUTING_QUERY"}  (still running)
# MAGIC  5. Server replies: {"status": "EXECUTING_QUERY"}  (still running)
# MAGIC  6. Server replies: {"status": "COMPLETED", "attachments": [...]}
# MAGIC  7. Client returns the final completed result to the caller
# MAGIC
# MAGIC DatabricksMCPClient and DatabricksMultiServerMCPClient handle this polling
# MAGIC loop internally. The timeout= parameter controls the maximum wait.
# MAGIC
# MAGIC Default timeout for Genie: 60 seconds
# MAGIC Default timeout for UC Functions: 30 seconds
# MAGIC Default timeout for Vector Search: 30 seconds
# MAGIC
# MAGIC If a Genie query times out in production, check:
# MAGIC   1. SQL warehouse is running (not idle/stopped)
# MAGIC   2. Query complexity (Genie sometimes generates table scans)
# MAGIC   3. Data volume (is the table partitioned correctly?)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2 complete</strong><br>
# MAGIC   You connected to the Genie Space MCP server, discovered its single NL-to-SQL tool, and
# MAGIC   ran two AEMO questions. You understand the polling pattern and how Genie Space configuration
# MAGIC   affects tool quality. Section 3 connects to the Vector Search MCP server.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Vector Search as MCP Server (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — Locate your Vector Search index in the UI
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog → workshop_au → aemo
# MAGIC           → expand "Vector Search Indexes"
# MAGIC
# MAGIC ┌─── Catalog Explorer ──────────────────────────────────────────────────────┐
# MAGIC │  workshop_au (catalog)                                                    │
# MAGIC │    aemo (schema)                                                          │
# MAGIC │      Tables                                                               │
# MAGIC │        spot_prices                                                        │
# MAGIC │        dispatch_intervals                                                 │
# MAGIC │        market_notices          ← source table for the VS index            │
# MAGIC │      Vector Search Indexes     ← click to expand                         │
# MAGIC │        aemo_market_notices_index                                          │
# MAGIC │          Full name: workshop_au.aemo.aemo_market_notices_index            │
# MAGIC │          Endpoint : workshop-vs-endpoint                                  │
# MAGIC │          Status   : Ready (green)                                         │
# MAGIC └───────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click on aemo_market_notices_index to see:
# MAGIC   - Source table: workshop_au.aemo.market_notices
# MAGIC   - Embedding column: notice_text
# MAGIC   - Embedding model: databricks-qwen3-embedding-0-6b  ← in-region ✅ (NOT gte-large-en which is cross-geo)
# MAGIC   - Sync status: Synced (green tick)
# MAGIC   - Row count: should match market_notices table row count
# MAGIC
# MAGIC If Status shows "Syncing" or "Not Ready":
# MAGIC   Wait 2–3 minutes and refresh. The Vector Search endpoint needs to be ONLINE
# MAGIC   before the MCP server can answer search queries.
# MAGIC ```
# MAGIC
# MAGIC **Also check permissions on the VS index:**
# MAGIC ```
# MAGIC Click the index → Permissions tab
# MAGIC
# MAGIC You need: USE on catalog → USE on schema → SELECT on the source table
# MAGIC           AND USE ENDPOINT on the VS endpoint
# MAGIC
# MAGIC Without these, the MCP server returns HTTP 403 on search calls.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Connect to Vector Search MCP and list the search tool

# COMMAND ----------

# Build the Vector Search MCP URL from the 3-part index name
# Format: /api/2.0/mcp/vector-search/{catalog}/{schema}/{index_name}
vs_parts  = VS_INDEX_NAME.split(".")     # ["workshop_au", "aemo", "aemo_market_notices_index"]
vs_mcp_url = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"

print(f"Vector Search MCP endpoint:")
print(f"  {vs_mcp_url}")
print()
print(f"Derived from index name: {VS_INDEX_NAME}")
print(f"  catalog = {vs_parts[0]}")
print(f"  schema  = {vs_parts[1]}")
print(f"  index   = {vs_parts[2]}")
print()

vs_client = DatabricksMCPClient(vs_mcp_url, ws)
vs_tools  = vs_client.list_tools()

print(f"Discovered {len(vs_tools)} tool(s):")
print()
for t in vs_tools:
    print(f"  Tool name  : {t.name}")
    print(f"  Description: {t.description}")
    if hasattr(t, "inputSchema") and t.inputSchema:
        props = t.inputSchema.get("properties", {})
        for pname, pschema in props.items():
            pdesc = pschema.get("description", "")
            print(f"    '{pname}': {pdesc}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Vector Search MCP endpoint:
# MAGIC   https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/vector-search/
# MAGIC   workshop_au/aemo/aemo_market_notices_index
# MAGIC
# MAGIC Derived from index name: workshop_au.aemo.aemo_market_notices_index
# MAGIC   catalog = workshop_au
# MAGIC   schema  = aemo
# MAGIC   index   = aemo_market_notices_index
# MAGIC
# MAGIC Discovered 1 tool(s):
# MAGIC
# MAGIC   Tool name  : search_aemo_market_notices_index
# MAGIC   Description: Search AEMO market notices using semantic similarity. Returns the most
# MAGIC                relevant notices based on meaning, not just keyword matching. Use for
# MAGIC                questions like 'find notices about LOR events', 'search for constraint
# MAGIC                issues in NSW', or 'what market notices mentioned fuel shortages'.
# MAGIC     'query': Natural language search query
# MAGIC     'num_results': Number of results to return (default: 5)
# MAGIC ```
# MAGIC
# MAGIC Like Genie, Vector Search MCP exposes exactly **1 tool** per index.
# MAGIC The tool name is `search_{index_name}`.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Run a semantic search over market notices

# COMMAND ----------

vs_tool_name = vs_tools[0].name
search_query = "LOR event Victoria low reserve"

print(f"Calling : {vs_tool_name}")
print(f"Query   : {search_query}")
print()

vs_result = vs_client.call_tool(
    vs_tool_name,
    {
        "query":       search_query,
        "num_results": 5,
    },
)

# Parse and display results
if vs_result and "content" in vs_result and not vs_result.get("isError"):
    for item in vs_result["content"]:
        if item.get("type") == "text":
            text = item["text"]
            print("Search results:")
            print(text[:1200])
            if len(text) > 1200:
                print(f"  ... ({len(text)} chars total)")
else:
    print("Search result:", vs_result)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Calling : search_aemo_market_notices_index
# MAGIC Query   : LOR event Victoria low reserve
# MAGIC
# MAGIC Search results:
# MAGIC [
# MAGIC   {
# MAGIC     "notice_id": "MN-2024-0234",
# MAGIC     "published_at": "2024-01-18T16:45:00",
# MAGIC     "notice_type": "LOR",
# MAGIC     "region": "VIC1",
# MAGIC     "title": "LOR2 Declared — Victoria 16:45 AEST",
# MAGIC     "notice_text": "AEMO has declared a Lack of Reserve 2 (LOR2) condition for the
# MAGIC                     Victoria region. Forecast reserve margin has fallen below the
# MAGIC                     LOR2 threshold of 850 MW...",
# MAGIC     "score": 0.9341
# MAGIC   },
# MAGIC   {
# MAGIC     "notice_id": "MN-2024-0156",
# MAGIC     "notice_type": "LOR",
# MAGIC     "region": "VIC1",
# MAGIC     "title": "Reserve Notice — Tight Conditions Expected",
# MAGIC     "score": 0.8812
# MAGIC   },
# MAGIC   ...
# MAGIC ]
# MAGIC ```
# MAGIC
# MAGIC The `score` field is the cosine similarity between the query embedding and each document
# MAGIC embedding. Higher is more semantically similar. The Vector Search MCP server uses
# MAGIC `databricks-qwen3-embedding-0-6b` to embed the query at search time — no separate embedding step.
# MAGIC This model is in-region for AU East ✅. Never use `databricks-gte-large-en` — it is cross-geo.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Compare keyword search vs semantic search
# MAGIC
# MAGIC The power of Vector Search is that it finds semantically similar content even when
# MAGIC the exact words do not match. Let us test with a paraphrased query:

# COMMAND ----------

# Same meaning, completely different words
paraphrased_queries = [
    "LOR event Victoria low reserve",           # exact terminology
    "Victoria electricity shortage emergency",  # paraphrase — no "LOR"
    "SA generator tripped constraints binding", # different region, different phrasing
]

print("Semantic search — same concept, different words:\n")
for query in paraphrased_queries:
    result = vs_client.call_tool(vs_tool_name, {"query": query, "num_results": 2})
    print(f"  Query: '{query}'")
    if result and "content" in result:
        try:
            hits = json.loads(result["content"][0]["text"])
            for hit in hits[:2]:
                score = hit.get("score", "?")
                title = hit.get("title", hit.get("notice_text", "?")[:60])
                print(f"    Score {score:.4f}: {title}")
        except Exception:
            print(f"    {result['content'][0]['text'][:120]}")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Semantic search — same concept, different words:
# MAGIC
# MAGIC   Query: 'LOR event Victoria low reserve'
# MAGIC     Score 0.9341: LOR2 Declared — Victoria 16:45 AEST
# MAGIC     Score 0.8812: Reserve Notice — Tight Conditions Expected
# MAGIC
# MAGIC   Query: 'Victoria electricity shortage emergency'
# MAGIC     Score 0.8205: LOR2 Declared — Victoria 16:45 AEST
# MAGIC     Score 0.7943: Emergency Backstop Mechanism — VIC1 Activated
# MAGIC
# MAGIC   Query: 'SA generator tripped constraints binding'
# MAGIC     Score 0.8890: Constraint Set SA_MAIN_1 Activated — South Australia
# MAGIC     Score 0.8401: Generator Trip — Torrens Island Unit 3
# MAGIC ```
# MAGIC
# MAGIC The second query ("Victoria electricity shortage emergency") finds the LOR notice even
# MAGIC though "LOR" never appears in the query. This is the semantic match that keyword search
# MAGIC cannot do — and why the agent uses Vector Search for "policy documents and notices" questions
# MAGIC rather than a SQL LIKE query.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 3 complete</strong><br>
# MAGIC   You connected to the Vector Search MCP server, searched for AEMO market notices, and
# MAGIC   observed how semantic similarity works across paraphrased queries. Section 4 combines
# MAGIC   all three servers into a single multi-server client — the foundation for Lab 03's agent.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Multi-Server Tool Discovery (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — Review the tool limits in AI Gateway
# MAGIC </div>
# MAGIC
# MAGIC Before combining servers, understand the limits you are working within.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning → Serving → AI Gateway → MCPs
# MAGIC
# MAGIC Click each server row. Look at the "Tools" count:
# MAGIC ┌─── Tool count summary ────────────────────────────────────────────────────┐
# MAGIC │  Server                     Type            Tools                        │
# MAGIC │  ─────────────────────────  ──────────────  ─────                       │
# MAGIC │  workshop_au.aemo.*         UC Functions    3                            │
# MAGIC │  AEMO NEM Operations        Genie Space     1                            │
# MAGIC │  aemo_market_notices_index  Vector Search   1                            │
# MAGIC │                                             ─────                       │
# MAGIC │                             Total           5   (well under 20 limit)   │
# MAGIC └───────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC The limits for agent mode:
# MAGIC   Max tools total:      20  (across all MCP servers combined)
# MAGIC   Max tools per server: 15  (per DatabricksMCPServer or McpServer)
# MAGIC
# MAGIC At 3 + 1 + 1 = 5 tools, the AEMO agent is well within limits.
# MAGIC If you add more UC functions, watch the total stays under 20.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Declare server configs with `DatabricksMCPServer`
# MAGIC
# MAGIC `DatabricksMCPServer` is a **declarative config object** — it describes how to connect
# MAGIC to a server but does not connect yet. Connections are made lazily when the client
# MAGIC is used in an `async with` context manager (you will see this in Lab 03).

# COMMAND ----------

import asyncio
from databricks_langchain import DatabricksMCPServer, DatabricksMultiServerMCPClient

# Server 1 — UC Functions (all 3 functions in the aemo schema)
uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG,
    schema=SCHEMA_AEMO,
    name="aemo-uc-tools",           # logical name used in debug logs and traces
    timeout=30.0,
    handle_tool_error=True,         # surface UC exceptions as tool error text, not agent crashes
)
print(f"Server config 1: {uc_server.name}")
print(f"  URL: {HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}")

# Server 2 — Genie Space (conditional on having a valid Space ID)
if GENIE_SPACE_ID != "FILL_IN":
    genie_server = DatabricksMCPServer(
        name="aemo-nem-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0,               # Genie runs real SQL — allow 60 seconds
        handle_tool_error=True,
    )
    print(f"Server config 2: {genie_server.name}")
    print(f"  URL: {HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}")
    servers = [uc_server, genie_server]
else:
    print("Server config 2: Genie — SKIPPED (GENIE_SPACE_ID not set)")
    servers = [uc_server]

# Server 3 — Vector Search (market notices index)
vs_server = DatabricksMCPServer(
    name="aemo-market-notices",
    url=vs_mcp_url,
    timeout=30.0,
    handle_tool_error=True,
)
servers.append(vs_server)
print(f"Server config 3: {vs_server.name}")
print(f"  URL: {vs_mcp_url}")
print()
print(f"Total MCP servers configured: {len(servers)}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Server config 1: aemo-uc-tools
# MAGIC   URL: https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/aemo
# MAGIC Server config 2: aemo-nem-genie
# MAGIC   URL: https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/genie/01jxyz...
# MAGIC Server config 3: aemo-market-notices
# MAGIC   URL: https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/vector-search/...
# MAGIC
# MAGIC Total MCP servers configured: 3
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Aggregate all tools with `DatabricksMultiServerMCPClient`
# MAGIC
# MAGIC `DatabricksMultiServerMCPClient` connects to all servers simultaneously and merges
# MAGIC their tool lists. This is the client that the LangGraph agent uses internally in Lab 03.

# COMMAND ----------

async def inspect_all_tools():
    """
    Connect to all configured MCP servers and collect the combined tool list.
    The async with block manages connection lifecycle — connections are closed
    automatically when the block exits.
    """
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        all_tools = await multi_client.get_tools()

        print(f"Total tools across {len(servers)} MCP server(s): {len(all_tools)}")
        print()

        for t in all_tools:
            desc = (t.description or "")[:90]
            # Identify which server this tool came from by its name pattern
            if t.name.startswith(f"{CATALOG}__"):
                origin = "UC Functions"
            elif t.name.startswith("ask_"):
                origin = "Genie Space"
            elif t.name.startswith("search_"):
                origin = "Vector Search"
            else:
                origin = "unknown"

            print(f"  [{origin}]  {t.name}")
            print(f"    {desc}...")
            print()

        return all_tools

all_tools = asyncio.run(inspect_all_tools())

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Total tools across 3 MCP server(s): 5
# MAGIC
# MAGIC   [UC Functions]  workshop_au__aemo__calculate_peak_demand
# MAGIC     Calculate peak spot price and total dispatch for a NEM region on a given date...
# MAGIC
# MAGIC   [UC Functions]  workshop_au__aemo__get_region_summary
# MAGIC     Return a JSON summary of NEM region conditions for a rolling window...
# MAGIC
# MAGIC   [UC Functions]  workshop_au__aemo__lookup_duid_info
# MAGIC     Look up generator information by DUID (Dispatchable Unit Identifier)...
# MAGIC
# MAGIC   [Genie Space]   ask_aemo_nem_operations
# MAGIC     Ask a natural language question about NEM spot prices, dispatch schedules...
# MAGIC
# MAGIC   [Vector Search]  search_aemo_market_notices_index
# MAGIC     Search AEMO market notices using semantic similarity...
# MAGIC ```
# MAGIC
# MAGIC Five tools from three servers in a single aggregated list. The `multi_client`
# MAGIC handles dispatch: when `get_tools()` returns these to the agent and the LLM picks
# MAGIC one to call, `multi_client` routes the call to the correct server automatically.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Tool limit planning for production agents
# MAGIC
# MAGIC Understanding the 20-tool limit matters when you scale beyond the workshop.

# COMMAND ----------

print("Tool limit analysis for the AEMO Operations Agent")
print("=" * 60)
print()

tool_budget = 20       # total agent limit
per_server  = 15       # per DatabricksMCPServer limit

current_tools = len(all_tools)
remaining     = tool_budget - current_tools

print(f"  Current tools         : {current_tools}/20")
print(f"  Remaining budget      : {remaining}")
print()
print("Strategies when approaching the limit:")
print()
print("  1. Use single-function UC endpoints instead of schema endpoint")
print("     e.g. /mcp/functions/workshop_au/aemo/calculate_peak_demand  (1 tool)")
print("     instead of /mcp/functions/workshop_au/aemo               (N tools)")
print()
print("  2. Split into specialised agents (sub-agents)")
print("     Price spike agent (Genie + peak demand function)")
print("     Policy agent (Vector Search + regulatory compliance function)")
print("     Orchestrator routes to the right sub-agent")
print()
print("  3. Create multiple Genie Spaces for different domains")
print("     Each still costs only 1 tool regardless of table count")
print()
print("  4. Consolidate UC functions")
print("     Merge related single-purpose functions into one function with a 'mode' param")
print("     (trade-off: harder to write good tool descriptions)")
print()

# Count tools by server type for the current setup
uc_count   = sum(1 for t in all_tools if t.name.startswith(f"{CATALOG}__"))
genie_count = sum(1 for t in all_tools if t.name.startswith("ask_"))
vs_count    = sum(1 for t in all_tools if t.name.startswith("search_"))
print(f"  Tool breakdown:  UC Functions={uc_count},  Genie={genie_count},  Vector Search={vs_count}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Tool limit analysis for the AEMO Operations Agent
# MAGIC ============================================================
# MAGIC
# MAGIC   Current tools         : 5/20
# MAGIC   Remaining budget      : 15
# MAGIC
# MAGIC Strategies when approaching the limit:
# MAGIC
# MAGIC   1. Use single-function UC endpoints instead of schema endpoint
# MAGIC      e.g. /mcp/functions/workshop_au/aemo/calculate_peak_demand  (1 tool)
# MAGIC      instead of /mcp/functions/workshop_au/aemo               (N tools)
# MAGIC   ...
# MAGIC
# MAGIC   Tool breakdown:  UC Functions=3,  Genie=1,  Vector Search=1
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Save the server configs for Lab 03
# MAGIC
# MAGIC Lab 03 will create the full agent using these same server configs.
# MAGIC Save them to the config file so Lab 03 can load them without re-entering values.

# COMMAND ----------

import json
from pathlib import Path

# Update the config with confirmed values
config_path = Path("/tmp/workshop2c_config.json")
config = json.loads(config_path.read_text()) if config_path.exists() else {}

config.update({
    "HOST":            HOST,
    "CATALOG":         CATALOG,
    "SCHEMA_AEMO":     SCHEMA_AEMO,
    "PT_ENDPOINT":     PT_ENDPOINT,
    "GENIE_SPACE_ID":  GENIE_SPACE_ID,
    "VS_INDEX_NAME":   VS_INDEX_NAME,
    "VS_MCP_URL":      vs_mcp_url,
    "GENIE_MCP_URL":   f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}" if GENIE_SPACE_ID != "FILL_IN" else None,
    "UC_MCP_URL":      f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}",
    "TOOL_COUNT":      len(all_tools),
})

config_path.write_text(json.dumps(config, indent=2))

print(f"Configuration updated and saved to {config_path}")
print()
print(f"  UC Functions MCP  : {config['UC_MCP_URL']}")
print(f"  Genie MCP         : {config.get('GENIE_MCP_URL', 'not configured')}")
print(f"  Vector Search MCP : {config['VS_MCP_URL']}")
print(f"  Total tools       : {config['TOOL_COUNT']}")
print()
print("Ready for Lab 03: Building a Multi-Tool ReAct Agent")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Configuration updated and saved to /tmp/workshop2c_config.json
# MAGIC
# MAGIC   UC Functions MCP  : https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/aemo
# MAGIC   Genie MCP         : https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/genie/01jxyz...
# MAGIC   Vector Search MCP : https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/vector-search/...
# MAGIC   Total tools       : 5
# MAGIC
# MAGIC Ready for Lab 03: Building a Multi-Tool ReAct Agent
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Lab 02 complete</strong><br>
# MAGIC   You have hands-on experience with all three Databricks MCP client patterns:
# MAGIC   <code>DatabricksMCPClient</code> for direct calls, per-server clients for Genie and
# MAGIC   Vector Search, and <code>DatabricksMultiServerMCPClient</code> for combined tool discovery.
# MAGIC   You understand what the LLM sees when the agent assembles its tool list.
# MAGIC   Lab 03 builds the full ReAct agent on top of this foundation.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lab 02 — Review questions
# MAGIC
# MAGIC 1. You run `client.list_tools()` against the UC Functions MCP endpoint and see 0 tools.
# MAGIC    The functions exist in Unity Catalog. What are the two most likely causes?
# MAGIC
# MAGIC 2. The Genie MCP server exposes 1 tool regardless of table count.
# MAGIC    The UC Functions MCP server (schema endpoint) exposes N tools (one per function).
# MAGIC    Why does this asymmetry matter for a developer building an agent with 12 UC functions
# MAGIC    and 3 Genie Spaces?
# MAGIC
# MAGIC 3. A Vector Search semantic query for "Victoria electricity reserve shortage" returns
# MAGIC    a notice titled "LOR2 Declared — Victoria" with score 0.82.
# MAGIC    Another query, "VIC1 lack of reserve two", returns the same notice with score 0.94.
# MAGIC    What explains the higher score for the second query?
# MAGIC
# MAGIC 4. `DatabricksMCPServer.from_uc_function(catalog=..., schema=...)` and
# MAGIC    `DatabricksMCPServer(url=f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}")` —
# MAGIC    are these equivalent? When would you prefer one over the other?
# MAGIC
# MAGIC 5. You want to deploy your AEMO agent to production Model Serving. Your notebook
# MAGIC    uses `WorkspaceClient()` auto-auth. What do you need to change for the deployment?
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Continue to Lab 03: Building a Multi-Tool ReAct Agent**

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 02 Complete</h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 14px 0;">
# MAGIC     You can now connect to, discover, and directly call any Databricks MCP server.
# MAGIC     You know what tools the agent will see, what descriptions the LLM reads, and
# MAGIC     how the 20-tool limit affects production agent design.
# MAGIC   </p>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 0.95em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 6px 10px;">What you did in Lab 02</th>
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Key learning</th>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">UC Functions: listed tools, inspected schemas, called directly</td>
# MAGIC       <td style="padding: 5px 10px;">Tool descriptions come from UC COMMENT metadata</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Genie Space: connected, ran 2 NEM questions, saw SQL</td>
# MAGIC       <td style="padding: 5px 10px;">1 tool per Genie Space; quality shaped by instructions</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Vector Search: semantic search, paraphrase comparison</td>
# MAGIC       <td style="padding: 5px 10px;">Matches on meaning, not keywords; 1 tool per index</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 5px 10px;">Multi-server: aggregated 5 tools from 3 servers</td>
# MAGIC       <td style="padding: 5px 10px;">20-tool limit; routing is automatic via multi_client</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 0; font-size: 0.9em;">
# MAGIC     Lab 03 connects an LLM to this tool list and builds the full AEMO Operations Agent.
# MAGIC   </p>
# MAGIC </div>
