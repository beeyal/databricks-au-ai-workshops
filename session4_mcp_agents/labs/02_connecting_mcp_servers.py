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
# MAGIC     and multi-server tool aggregation.
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
# MAGIC | 1 | Low-Level MCP Client | `DatabricksMCPClient` — connect, list tools, call directly | 10 min |
# MAGIC | 2 | Genie Space as MCP Server | Connect, call with NEM questions, inspect SQL + result | 10 min |
# MAGIC | 3 | Vector Search as MCP Server | Connect, semantic search over market notices | 10 min |
# MAGIC | 4 | Multi-Server Tool Discovery | `DatabricksMultiServerMCPClient`, aggregate tools, 20-tool limit | 10 min |

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration (loads Lab 01 values)

# COMMAND ----------

import json
from pathlib import Path

_config_path = Path("/tmp/workshop2c_config.json")
_saved = json.loads(_config_path.read_text()) if _config_path.exists() else {}

dbutils.widgets.text("catalog",         _saved.get("CATALOG",        "workshop_au"),      "Catalog name")
dbutils.widgets.text("schema_aemo",     _saved.get("SCHEMA_AEMO",    "aemo"),             "AEMO schema name")
dbutils.widgets.text("pt_endpoint",     _saved.get("PT_ENDPOINT",    "au_east_llm_inregion"), "PT endpoint name")
dbutils.widgets.text("genie_space_id",  _saved.get("GENIE_SPACE_ID", ""),          "Genie Space ID")
dbutils.widgets.text("vs_index",        _saved.get("VS_INDEX_NAME",
                     "workshop_au.aemo.aemo_market_notices_index"),                        "VS index (3-part name)")

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

if GENIE_SPACE_ID == "":
    print("\nNOTE: Genie Space ID not set — Section 2 will be skipped.")
    print("      Left sidebar → Genie → AEMO NEM Operations → copy ID from URL bar.")

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
# MAGIC   🖱️ UI: UC Functions before we code
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Catalog → workshop_au → aemo → Functions
# MAGIC Click calculate_peak_demand → read the Comment and check Permissions tab.
# MAGIC You need EXECUTE on each function. Without it, MCP returns HTTP 403.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Connect with `DatabricksMCPClient` and list tools

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient
import json

uc_mcp_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"

print(f"UC Functions MCP endpoint:\n  {uc_mcp_url}\n")

# WorkspaceClient() auto-authenticates from notebook context.
client = DatabricksMCPClient(uc_mcp_url, ws)
tools  = client.list_tools()

print(f"Discovered {len(tools)} tool(s) in {CATALOG}.{SCHEMA_AEMO}:\n")
for t in tools:
    desc_preview = (t.description or "")[:100]
    params = list((t.inputSchema or {}).get("properties", {}).keys()) if hasattr(t, "inputSchema") else []
    print(f"  Tool: {t.name}")
    print(f"  Desc: {desc_preview}...")
    print(f"  Params: {params}\n")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Discovered 3 tool(s) in workshop_au.aemo:
# MAGIC
# MAGIC   Tool: workshop_au__aemo__calculate_peak_demand
# MAGIC   Desc: Calculate peak spot price and total dispatch for a NEM region on a given date...
# MAGIC   Params: ['region', 'date']
# MAGIC
# MAGIC   Tool: workshop_au__aemo__get_region_summary
# MAGIC   Desc: Return a JSON summary of NEM region conditions for a rolling window...
# MAGIC   Params: ['region', 'days']
# MAGIC
# MAGIC   Tool: workshop_au__aemo__lookup_duid_info
# MAGIC   Desc: Look up generator information by DUID...
# MAGIC   Params: ['duid']
# MAGIC ```
# MAGIC
# MAGIC Tool names follow `catalog__schema__function_name` (double-underscores). This is consistent across all UC Functions MCP endpoints.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Inspect a full tool schema

# COMMAND ----------

target_tool = next((t for t in tools if "calculate_peak_demand" in t.name), None)

if target_tool:
    print(f"Full schema for: {target_tool.name}")
    print("=" * 60)
    print(f"Description:\n  {target_tool.description}\n")
    if hasattr(target_tool, "inputSchema") and target_tool.inputSchema:
        print("Input schema (JSON Schema):")
        print(json.dumps(target_tool.inputSchema, indent=2))
else:
    print("Tool not found — check CATALOG and SCHEMA_AEMO widget values.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC Input schema (JSON Schema):
# MAGIC {
# MAGIC   "type": "object",
# MAGIC   "properties": {
# MAGIC     "region": {"type": "string", "description": "NEM region code. Values: NSW1, VIC1, QLD1, SA1, TAS1"},
# MAGIC     "date":   {"type": "string", "description": "Date in YYYY-MM-DD format (AEST)"}
# MAGIC   },
# MAGIC   "required": ["region", "date"]
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC The JSON Schema `description` fields come from `COMMENT` annotations on the UC function parameters. Well-written parameter descriptions prevent the LLM from passing malformed values (e.g. "VIC" instead of "VIC1").

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Call a UC function directly via `DatabricksMCPClient`

# COMMAND ----------

from datetime import date, timedelta

query_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
tool_name  = f"{CATALOG}__{SCHEMA_AEMO}__calculate_peak_demand"

print(f"Calling: {tool_name}")
print(f"Args   : region='VIC1', date='{query_date}'\n")

result = client.call_tool(tool_name, {"region": "VIC1", "date": query_date})

print("Raw MCP response:")
print(json.dumps(result, indent=2, default=str))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC {
# MAGIC   "content": [{"type": "text", "text": "{\"region\": \"VIC1\", \"peak_price_mwh\": 342.50, ...}"}],
# MAGIC   "isError": false
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC Every MCP server type uses this same envelope: a `content` array of items each with `type` and `text`. `isError: false` confirms the UC function executed without raising an exception.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Parse and display the result

# COMMAND ----------

if result and not result.get("isError", False) and "content" in result:
    raw_text = result["content"][0]["text"]
    try:
        parsed = json.loads(raw_text)
        print(f"Parsed result for VIC1 on {query_date}:\n")
        print(f"  Region              : {parsed.get('region', 'n/a')}")
        print(f"  Peak price ($/MWh)  : {parsed.get('peak_price_mwh', 'n/a')}")
        print(f"  Peak interval       : {parsed.get('peak_interval', 'n/a')}")
        print(f"  Avg price ($/MWh)   : {parsed.get('avg_price_mwh', 'n/a')}")
        print(f"  Total dispatch (MW) : {parsed.get('total_dispatch_mw', 'n/a')}")
        peak = parsed.get("peak_price_mwh", 0)
        print(f"\n  {'SPIKE' if float(peak) > 300 else 'No spike'}: peak ${peak}/MWh (threshold $300/MWh)")
    except json.JSONDecodeError:
        print("Result is plain text:", raw_text)
elif result and result.get("isError"):
    print("Error:", result.get("content", [{}])[0].get("text", ""))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Parsed result for VIC1 on 2024-06-30:
# MAGIC
# MAGIC   Region              : VIC1
# MAGIC   Peak price ($/MWh)  : 342.50
# MAGIC   Peak interval       : 17:30
# MAGIC   Avg price ($/MWh)   : 87.40
# MAGIC   Total dispatch (MW) : 5840.2
# MAGIC
# MAGIC   SPIKE: peak $342.50/MWh (threshold $300/MWh)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 — Single-function endpoint (least-privilege pattern)

# COMMAND ----------

single_fn_url  = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}/calculate_peak_demand"
single_client  = DatabricksMCPClient(single_fn_url, ws)
single_tools   = single_client.list_tools()

print(f"Single-function endpoint exposes {len(single_tools)} tool(s):")
for t in single_tools:
    print(f"  {t.name}")

print()
print("Schema endpoint:  auto-includes new functions; exposes all to the agent.")
print("Single endpoint:  least-privilege; one URL per function.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Single-function endpoint exposes 1 tool(s):
# MAGIC   workshop_au__aemo__calculate_peak_demand
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 1</strong><br>
# MAGIC   You used <code>DatabricksMCPClient</code> to discover 3 UC function tools, read their JSON Schema, and make a direct tool call. Section 2 connects to the Genie Space MCP server.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Genie Space as MCP Server (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ UI: Confirm your Genie Space ID
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Genie → AEMO NEM Operations
# MAGIC Browser URL: .../genie/rooms/{GENIE_SPACE_ID}
# MAGIC Paste the ID into the 'genie_space_id' widget and re-run the Configuration cell.
# MAGIC
# MAGIC Also check: Configure → Tables (3 tables), Instructions (AEMO domain context),
# MAGIC SQL queries (3+ golden queries seeded by setup script).
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Connect to Genie Space via MCP and list tools

# COMMAND ----------

if GENIE_SPACE_ID == "":
    print("Genie Space ID not set — skipping Section 2.")
    GENIE_MCP_AVAILABLE = False
else:
    genie_mcp_url  = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
    genie_client   = DatabricksMCPClient(genie_mcp_url, ws)
    genie_tools    = genie_client.list_tools()

    print(f"Genie MCP endpoint: {genie_mcp_url}\n")
    print(f"Discovered {len(genie_tools)} tool(s):\n")
    for t in genie_tools:
        print(f"  Tool name  : {t.name}")
        print(f"  Description: {t.description}\n")
        if hasattr(t, "inputSchema") and t.inputSchema:
            for pname, pschema in t.inputSchema.get("properties", {}).items():
                print(f"    Parameter '{pname}': {pschema.get('description','')}")
    GENIE_MCP_AVAILABLE = True

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Discovered 1 tool(s):
# MAGIC
# MAGIC   Tool name  : ask_aemo_nem_operations
# MAGIC   Description: Ask a natural language question about NEM spot prices, dispatch
# MAGIC                schedules, generator output, or price spike events...
# MAGIC     Parameter 'question': The natural language question about NEM data to answer.
# MAGIC ```
# MAGIC
# MAGIC Genie always exposes **exactly 1 tool** regardless of how many tables are in the Space. This counts as only 1 toward the 20-tool agent limit.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Call the Genie tool with an AEMO question

# COMMAND ----------

if not GENIE_MCP_AVAILABLE:
    print("Skipping — Genie Space not configured.")
else:
    genie_tool_name = genie_tools[0].name
    question = "What was the average spot price per region for the last 7 days in the dataset?"

    print(f"Calling: {genie_tool_name}")
    print(f"Question: {question}\n")

    genie_result = genie_client.call_tool(genie_tool_name, {"question": question})

    if genie_result and "content" in genie_result:
        for item in genie_result["content"]:
            print(f"[{item.get('type','?')}]")
            print(item.get("text","")[:600])
            print()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC [text]
# MAGIC | Region | Avg Price ($/MWh) |
# MAGIC |--------|------------------|
# MAGIC | NSW1   | 92.40            |
# MAGIC | VIC1   | 87.15            |
# MAGIC | QLD1   | 104.70           |
# MAGIC
# MAGIC [text]
# MAGIC Generated SQL:
# MAGIC SELECT region, ROUND(AVG(spot_price_mwh), 2) AS avg_price_mwh
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE interval_datetime >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
# MAGIC GROUP BY region ORDER BY avg_price_mwh DESC
# MAGIC ```
# MAGIC
# MAGIC The Genie MCP response includes a plain-English summary table and the SQL Genie generated. The LLM in your agent receives both.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Test with a spike detection question

# COMMAND ----------

if not GENIE_MCP_AVAILABLE:
    print("Skipping — Genie Space not configured.")
else:
    spike_question = (
        "How many intervals had a spot price above $300 per MWh in VIC1? "
        "Show the top 5 highest price intervals with date and time."
    )
    print(f"Question: {spike_question}\n")
    spike_result = genie_client.call_tool(genie_tool_name, {"question": spike_question})

    if spike_result and "content" in spike_result:
        for item in spike_result["content"]:
            if item.get("type") == "text":
                print(item["text"][:800])

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC There were 14 intervals where the VIC1 spot price exceeded $300/MWh.
# MAGIC
# MAGIC | Rank | Interval Datetime       | Spot Price ($/MWh) |
# MAGIC |------|-------------------------|--------------------|
# MAGIC | 1    | 2024-01-18 17:00:00     | 14,000.00          |
# MAGIC | 2    | 2024-01-18 17:05:00     | 12,300.00          |
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2</strong><br>
# MAGIC   You connected to the Genie Space MCP server, discovered its single NL-to-SQL tool, and ran two AEMO questions. Section 3 connects to the Vector Search MCP server.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Vector Search as MCP Server (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ UI: Locate your Vector Search index
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Compute → Vector Search tab
# MAGIC Click aemo_market_notices_index to see:
# MAGIC   - Source table: workshop_au.aemo.market_notices
# MAGIC   - Embedding model: databricks-qwen3-embedding-0-6b  (in-region AU East ✅)
# MAGIC   - Status: Ready (green) — if "Syncing", wait 2-3 min before continuing
# MAGIC   - Row count matches market_notices table
# MAGIC
# MAGIC NOTE: there is NO query UI for Vector Search — use the Python SDK or MCP.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Connect to Vector Search MCP and list the search tool

# COMMAND ----------

vs_parts   = VS_INDEX_NAME.split(".")
vs_mcp_url = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"

print(f"Vector Search MCP endpoint:\n  {vs_mcp_url}\n")

vs_client = DatabricksMCPClient(vs_mcp_url, ws)
vs_tools  = vs_client.list_tools()

print(f"Discovered {len(vs_tools)} tool(s):\n")
for t in vs_tools:
    print(f"  Tool name  : {t.name}")
    print(f"  Description: {t.description}")
    if hasattr(t, "inputSchema") and t.inputSchema:
        for pname, pschema in t.inputSchema.get("properties", {}).items():
            print(f"    '{pname}': {pschema.get('description','')}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Discovered 1 tool(s):
# MAGIC
# MAGIC   Tool name  : search_aemo_market_notices_index
# MAGIC   Description: Search AEMO market notices using semantic similarity...
# MAGIC     'query': Natural language search query
# MAGIC     'num_results': Number of results to return (default: 5)
# MAGIC ```
# MAGIC
# MAGIC Like Genie, Vector Search MCP exposes exactly **1 tool** per index. The tool name is `search_{index_name}`.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Run a semantic search over market notices

# COMMAND ----------

vs_tool_name = vs_tools[0].name
search_query = "LOR event Victoria low reserve"

print(f"Calling : {vs_tool_name}")
print(f"Query   : {search_query}\n")

vs_result = vs_client.call_tool(vs_tool_name, {"query": search_query, "num_results": 5})

if vs_result and "content" in vs_result and not vs_result.get("isError"):
    for item in vs_result["content"]:
        if item.get("type") == "text":
            print("Search results:")
            print(item["text"][:1200])
else:
    print("Search result:", vs_result)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC [{"notice_id": "MN-2024-0234", "notice_type": "LOR", "region": "VIC1",
# MAGIC   "title": "LOR2 Declared — Victoria 16:45 AEST", "score": 0.9341},
# MAGIC  {"notice_id": "MN-2024-0156", "region": "VIC1", "score": 0.8812}, ...]
# MAGIC ```
# MAGIC
# MAGIC The `score` is cosine similarity between the query embedding and each document. The Vector Search MCP uses `databricks-qwen3-embedding-0-6b` in AU East. Never use `databricks-gte-large-en` — it is cross-geo.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Compare keyword search vs semantic search

# COMMAND ----------

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
# MAGIC   Query: 'LOR event Victoria low reserve'
# MAGIC     Score 0.9341: LOR2 Declared — Victoria 16:45 AEST
# MAGIC
# MAGIC   Query: 'Victoria electricity shortage emergency'
# MAGIC     Score 0.8205: LOR2 Declared — Victoria 16:45 AEST
# MAGIC
# MAGIC   Query: 'SA generator tripped constraints binding'
# MAGIC     Score 0.8890: Constraint Set SA_MAIN_1 Activated — South Australia
# MAGIC ```
# MAGIC
# MAGIC The second query finds the LOR notice even though "LOR" never appears in the query — this is why the agent uses Vector Search for notice questions rather than a SQL LIKE query.
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 3</strong><br>
# MAGIC   You connected to the Vector Search MCP server, searched for AEMO market notices, and observed semantic similarity across paraphrased queries. Section 4 combines all three servers into a single multi-server client.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Multi-Server Tool Discovery (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ UI: Review tool counts in AI Gateway
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → AI Gateway → MCPs tab
# MAGIC
# MAGIC Server                     Type            Tools
# MAGIC workshop_au.aemo.*         UC Functions    3
# MAGIC AEMO NEM Operations        Genie Space     1
# MAGIC aemo_market_notices_index  Vector Search   1
# MAGIC                            Total           5  (well under 20-tool limit)
# MAGIC
# MAGIC Limits: max 20 tools total, max 15 tools per DatabricksMCPServer.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Declare server configs with `DatabricksMCPServer`

# COMMAND ----------

import asyncio
from databricks_langchain import DatabricksMCPServer, DatabricksMultiServerMCPClient

# Server 1: UC Functions
uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG,
    schema=SCHEMA_AEMO,
    name="aemo-uc-tools",
    timeout=30.0,
    handle_tool_error=True,
)
print(f"Server config 1: {uc_server.name}")

# Server 2: Genie Space (conditional)
servers = [uc_server]
if GENIE_SPACE_ID != "":
    genie_server = DatabricksMCPServer(
        name="aemo-nem-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0,
        handle_tool_error=True,
    )
    servers.append(genie_server)
    print(f"Server config 2: {genie_server.name}")
else:
    print("Server config 2: Genie — SKIPPED (GENIE_SPACE_ID not set)")

# Server 3: Vector Search
vs_server = DatabricksMCPServer(
    name="aemo-market-notices",
    url=vs_mcp_url,
    timeout=30.0,
    handle_tool_error=True,
)
servers.append(vs_server)
print(f"Server config 3: {vs_server.name}")
print(f"\nTotal MCP servers configured: {len(servers)}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Server config 1: aemo-uc-tools
# MAGIC Server config 2: aemo-nem-genie
# MAGIC Server config 3: aemo-market-notices
# MAGIC
# MAGIC Total MCP servers configured: 3
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Aggregate all tools with `DatabricksMultiServerMCPClient`

# COMMAND ----------

async def inspect_all_tools():
    """Connect to all configured MCP servers and collect the combined tool list."""
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        all_tools = await multi_client.get_tools()

        print(f"Total tools across {len(servers)} MCP server(s): {len(all_tools)}\n")
        for t in all_tools:
            if t.name.startswith(f"{CATALOG}__"):   origin = "UC Functions"
            elif t.name.startswith("ask_"):          origin = "Genie Space"
            elif t.name.startswith("search_"):       origin = "Vector Search"
            else:                                    origin = "unknown"
            print(f"  [{origin}]  {t.name}")
            print(f"    {(t.description or '')[:90]}...\n")

        return all_tools

all_tools = asyncio.run(inspect_all_tools())

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Total tools across 3 MCP server(s): 5
# MAGIC
# MAGIC   [UC Functions]  workshop_au__aemo__calculate_peak_demand
# MAGIC   [UC Functions]  workshop_au__aemo__get_region_summary
# MAGIC   [UC Functions]  workshop_au__aemo__lookup_duid_info
# MAGIC   [Genie Space]   ask_aemo_nem_operations
# MAGIC   [Vector Search] search_aemo_market_notices_index
# MAGIC ```
# MAGIC
# MAGIC When `get_tools()` returns these to the agent and the LLM picks one, `multi_client` routes the call to the correct server automatically.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Tool limit planning

# COMMAND ----------

tool_budget   = 20
current_tools = len(all_tools)
remaining     = tool_budget - current_tools

print(f"Tool limit analysis")
print("=" * 50)
print(f"  Current tools    : {current_tools}/20")
print(f"  Remaining budget : {remaining}")
print()
print("Strategies when approaching the limit:")
print("  1. Single-function endpoints instead of schema endpoint (1 tool vs N tools)")
print("  2. Split into specialised sub-agents with an orchestrator")
print("  3. Multiple Genie Spaces — each still costs only 1 tool")
print("  4. Consolidate UC functions with a 'mode' parameter")

uc_count    = sum(1 for t in all_tools if t.name.startswith(f"{CATALOG}__"))
genie_count = sum(1 for t in all_tools if t.name.startswith("ask_"))
vs_count    = sum(1 for t in all_tools if t.name.startswith("search_"))
print(f"\n  Breakdown: UC Functions={uc_count}, Genie={genie_count}, Vector Search={vs_count}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Tool limit analysis
# MAGIC ==================================================
# MAGIC   Current tools    : 5/20
# MAGIC   Remaining budget : 15
# MAGIC   Breakdown: UC Functions=3, Genie=1, Vector Search=1
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Save the server configs for Lab 03

# COMMAND ----------

import json
from pathlib import Path

config_path = Path("/tmp/workshop2c_config.json")
config = json.loads(config_path.read_text()) if config_path.exists() else {}

config.update({
    "HOST":           HOST,
    "CATALOG":        CATALOG,
    "SCHEMA_AEMO":    SCHEMA_AEMO,
    "PT_ENDPOINT":    PT_ENDPOINT,
    "GENIE_SPACE_ID": GENIE_SPACE_ID,
    "VS_INDEX_NAME":  VS_INDEX_NAME,
    "VS_MCP_URL":     vs_mcp_url,
    "GENIE_MCP_URL":  f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}" if GENIE_SPACE_ID != "" else None,
    "UC_MCP_URL":     f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}",
    "TOOL_COUNT":     len(all_tools),
})

config_path.write_text(json.dumps(config, indent=2))

print(f"Configuration updated and saved to {config_path}")
print(f"\n  UC Functions MCP  : {config['UC_MCP_URL']}")
print(f"  Genie MCP         : {config.get('GENIE_MCP_URL', 'not configured')}")
print(f"  Vector Search MCP : {config['VS_MCP_URL']}")
print(f"  Total tools       : {config['TOOL_COUNT']}")
print("\nReady for Lab 03: Building a Multi-Tool ReAct Agent")

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
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Lab 02 complete</strong><br>
# MAGIC   You have hands-on experience with <code>DatabricksMCPClient</code> for direct calls, per-server clients for Genie and Vector Search, and <code>DatabricksMultiServerMCPClient</code> for combined tool discovery. Lab 03 builds the full ReAct agent on top of this foundation.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lab 02 — Review questions
# MAGIC
# MAGIC 1. You run `client.list_tools()` against the UC Functions MCP endpoint and see 0 tools. The functions exist in Unity Catalog. What are the two most likely causes?
# MAGIC
# MAGIC 2. Genie MCP exposes 1 tool regardless of table count; UC Functions MCP (schema endpoint) exposes N tools. Why does this asymmetry matter for a developer building an agent with 12 UC functions and 3 Genie Spaces?
# MAGIC
# MAGIC 3. A Vector Search query for "Victoria electricity reserve shortage" returns a notice titled "LOR2 Declared — Victoria" with score 0.82. Another query, "VIC1 lack of reserve two", returns the same notice with score 0.94. What explains the higher score?
# MAGIC
# MAGIC 4. `DatabricksMCPServer.from_uc_function(catalog=..., schema=...)` vs `DatabricksMCPServer(url=f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}")` — are these equivalent? When would you prefer one?
# MAGIC
# MAGIC 5. You want to deploy this AEMO agent to production Model Serving. Your notebook uses `WorkspaceClient()` auto-auth. What do you need to change?
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Continue to Lab 03: Building a Multi-Tool ReAct Agent**

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 02 Complete</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 0.95em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 6px 10px;">What you did</th>
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
# MAGIC       <td style="padding: 5px 10px;">20-tool limit; routing automatic via multi_client</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC </div>
