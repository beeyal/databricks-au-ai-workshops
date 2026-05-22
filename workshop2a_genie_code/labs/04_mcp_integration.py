# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 04: MCP Integration (Model Context Protocol)
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop: Genie Code for Developers — Australian Regulated Industries
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Connect AI agents to UC Functions, Genie, Vector Search, and SQL — all in-region for AU East
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>45 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01, 02, 03 complete
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
# MAGIC | 1 | Concepts & Ecosystem | MCP standard, 5 Databricks server types, AI Gateway MCPs tab, architecture | 10 min |
# MAGIC | 2 | UC Functions via MCP | Low-level `DatabricksMCPClient`, tool discovery, direct function calls | 10 min |
# MAGIC | 3 | Multi-MCP Agent with LangGraph | `DatabricksMultiServerMCPClient`, ReAct agent, MLflow traces | 15 min |
# MAGIC | 4 | OpenAI Agents SDK Pattern | `McpServer` async context manager, UC + Vector Search, production notes | 10 min |
# MAGIC | Bonus | Claude Desktop Config | External IDE / local development setup | open-ended |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why MCP matters for regulated industries
# MAGIC
# MAGIC | Concern | MCP answer |
# MAGIC |---------|-----------|
# MAGIC | **Data residency** | All Databricks MCP endpoints are workspace-local — calls never leave AU East |
# MAGIC | **Auth and access control** | Standard Databricks OAuth/PAT — same controls as any workspace API call |
# MAGIC | **Auditability** | Every MCP call appears in `system.access.audit` with user identity and parameters |
# MAGIC | **UC governance** | UC function permissions govern which tools the agent can call |
# MAGIC | **No external vendor dependency** | The MCP client library is client-side only — it connects to your workspace, not a third-party cloud |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — MCP Concepts and Ecosystem (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — What is MCP?
# MAGIC
# MAGIC **Model Context Protocol (MCP)** is an open standard (Anthropic, 2024) that lets AI agents
# MAGIC connect to data sources and tools through a uniform HTTP interface.
# MAGIC
# MAGIC Think of it as USB-C for AI tools: any MCP-compatible agent can connect to any MCP-compatible
# MAGIC server without custom integration code. Databricks implements MCP as standard authenticated
# MAGIC HTTP endpoints on your workspace.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 1.2 — The 5 Databricks MCP server types
# MAGIC
# MAGIC All endpoints follow the pattern `https://<workspace>/api/2.0/mcp/...`
# MAGIC
# MAGIC | MCP Server | URL pattern | What it exposes |
# MAGIC |------------|-------------|-----------------|
# MAGIC | **UC Functions (schema)** | `.../mcp/functions/{catalog}/{schema}` | All UC functions in a schema as MCP tools |
# MAGIC | **UC Functions (single)** | `.../mcp/functions/{catalog}/{schema}/{function}` | A single named UC function |
# MAGIC | **Genie Space** | `.../mcp/genie/{genie_space_id}` | A single NL-to-SQL tool backed by a Genie Space |
# MAGIC | **Vector Search** | `.../mcp/vector-search/{catalog}/{schema}/{index}` | Semantic similarity search over a VS index |
# MAGIC | **Databricks SQL** | `.../mcp/sql` | Direct SQL execution tool (use with care — scoped to warehouse permissions) |
# MAGIC
# MAGIC All five are **in-region for Australia East**. No data leaves your workspace region.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 1.3 — Architecture overview
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────────────┐
# MAGIC │                Energy Operations Agent (AU East)                     │
# MAGIC │                                                                      │
# MAGIC │   User question: "What was peak demand for NMI 6001234567 in July?" │
# MAGIC │          │                                                           │
# MAGIC │          ▼                                                           │
# MAGIC │   Claude Sonnet 4.6 (via Provisioned Throughput endpoint)           │
# MAGIC │          │                                                           │
# MAGIC │          │  LLM selects tool based on question type                 │
# MAGIC │          ▼                                                           │
# MAGIC │  ┌──────────────┬──────────────────┬──────────────────────────┐     │
# MAGIC │  │  Genie MCP   │  Vector Search   │   UC Functions MCP       │     │
# MAGIC │  │  NL→SQL over │  MCP             │   calculate_peak_demand  │     │
# MAGIC │  │  meter tables│  Policy docs RAG │   lookup_asset_status    │     │
# MAGIC │  │  /mcp/genie/ │  /mcp/vector-    │   /mcp/functions/        │     │
# MAGIC │  │  {space_id}  │  search/{index}  │   {catalog}/{schema}     │     │
# MAGIC │  └──────────────┴──────────────────┴──────────────────────────┘     │
# MAGIC │                                                                      │
# MAGIC │              All MCP endpoints: Australia East ✅                   │
# MAGIC │              All calls logged in system.access.audit ✅             │
# MAGIC └──────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 1.4 — Tool naming convention for UC Functions
# MAGIC
# MAGIC UC function names use double-underscore (`__`) as separator in MCP tool names:
# MAGIC
# MAGIC ```
# MAGIC  UC function:    workshop_au.energy.calculate_peak_demand
# MAGIC                      │          │          │
# MAGIC                   catalog    schema    function_name
# MAGIC                      │          │          │
# MAGIC                      └──────────┴──────────┘
# MAGIC                              joined with __
# MAGIC                              │
# MAGIC  MCP tool name:  workshop_au__energy__calculate_peak_demand
# MAGIC ```
# MAGIC
# MAGIC This is important to know when routing tool calls in code that inspects tool names.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 1.5 — Agent mode tool limits
# MAGIC
# MAGIC | Limit | Value | Notes |
# MAGIC |-------|-------|-------|
# MAGIC | Max tools total (agent mode) | 20 | Across all MCP servers combined |
# MAGIC | Max tools per MCP server | 15 | Per `DatabricksMCPServer` / `McpServer` |
# MAGIC | Genie MCP tool count | 1 | Exposes exactly one NL-to-SQL tool |
# MAGIC | Vector Search MCP tool count | 1 | Exposes exactly one similarity-search tool |
# MAGIC | UC Functions MCP tool count | = number of functions in schema | Each UC function becomes one MCP tool |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Finding MCP Servers in the AI Gateway Tab
# MAGIC </div>
# MAGIC
# MAGIC The AI Gateway UI shows all MCP endpoints available in your workspace.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar)
# MAGIC           → Serving
# MAGIC           → AI Gateway tab (top navigation)
# MAGIC           → MCPs tab (inside AI Gateway)
# MAGIC
# MAGIC What you will see:
# MAGIC
# MAGIC ┌─────────────────────────────────────────────────────────────────────┐
# MAGIC │  AI Gateway > MCPs                                                  │
# MAGIC │                                                                     │
# MAGIC │  UC Functions         workshop_au.energy                            │
# MAGIC │  URL: https://....azuredatabricks.net/api/2.0/mcp/functions/        │
# MAGIC │       workshop_au/energy                                            │
# MAGIC │  Status: Active   Tools: 3                                          │
# MAGIC │                                                                     │
# MAGIC │  Genie               Energy Operations Workshop                     │
# MAGIC │  URL: https://....azuredatabricks.net/api/2.0/mcp/genie/01jf3...   │
# MAGIC │  Status: Active   Tools: 1                                          │
# MAGIC │                                                                     │
# MAGIC │  Vector Search       workshop_au.energy.policy_docs_index           │
# MAGIC │  URL: https://....azuredatabricks.net/api/2.0/mcp/vector-search/   │
# MAGIC │       workshop_au/energy/policy_docs_index                          │
# MAGIC │  Status: Active   Tools: 1                                          │
# MAGIC └─────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC You can copy the MCP URL directly from this tab.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Finding Your Genie Space ID
# MAGIC </div>
# MAGIC
# MAGIC The Genie Space ID is in the browser URL when you open your Genie Space:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Genie (left sidebar) → click your space → look at the browser URL bar
# MAGIC
# MAGIC ┌─── Browser URL bar ──────────────────────────────────────────────────┐
# MAGIC │  https://adb-xxxx.azuredatabricks.net/genie/spaces/01jf3k2m9xyz456 │
# MAGIC │                                                        ↑            │
# MAGIC │                                            Your GENIE_SPACE_ID      │
# MAGIC └──────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC GENIE_SPACE_ID = "01jf3k2m9xyz456"
# MAGIC ```
# MAGIC
# MAGIC If you do not have a Genie Space, create one:
# MAGIC ```
# MAGIC 1. Genie (left sidebar) → New Genie Space
# MAGIC 2. Name: "Energy Operations Workshop"
# MAGIC 3. Add tables: workshop_au.energy.interval_reads, workshop_au.energy.asset_maintenance
# MAGIC 4. Description: "NEM meter interval reads and asset maintenance data for NSW and VIC operations."
# MAGIC 5. Click Save — copy the Space ID from the URL
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Finding Your Vector Search Index Name
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Navigate: Catalog (left sidebar) → expand your catalog → expand schema → Vector Search Indexes
# MAGIC
# MAGIC ┌─── Catalog Explorer ─────────────────────────────────────────────────┐
# MAGIC │  workshop_au (catalog)                                               │
# MAGIC │    energy (schema)                                                   │
# MAGIC │      Tables                                                          │
# MAGIC │        interval_reads                                                │
# MAGIC │        asset_maintenance                                             │
# MAGIC │      Vector Search Indexes                 ← look here               │
# MAGIC │        policy_docs_index                   ← full name below        │
# MAGIC │          Full name: workshop_au.energy.policy_docs_index             │
# MAGIC └──────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC VS_INDEX_NAME = "workshop_au.energy.policy_docs_index"
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.6 — Install the correct packages
# MAGIC
# MAGIC > There are THREE separate packages for different integration patterns.
# MAGIC > Do **not** mix them up — they serve different purposes.
# MAGIC
# MAGIC | Package | What it gives you | Use for |
# MAGIC |---------|-------------------|---------|
# MAGIC | `databricks-mcp` | Low-level `DatabricksMCPClient` | Direct MCP calls, tool discovery |
# MAGIC | `databricks-langchain` | `DatabricksMCPServer`, `DatabricksMultiServerMCPClient`, `ChatDatabricks` | LangGraph agents |
# MAGIC | `databricks-openai` | `McpServer` for the OpenAI Agents SDK | OpenAI Agents SDK pattern |

# COMMAND ----------

%pip install databricks-mcp databricks-langchain databricks-openai mlflow --quiet
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (after restart):**
# MAGIC ```
# MAGIC Python interpreter restarted.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.7 — Workshop configuration

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",         "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("genie_space_id", "FILL_IN",              "Genie Space ID")
dbutils.widgets.text("vs_index",       "workshop_au.energy.policy_docs_index", "VS index (3-part name)")

CATALOG       = dbutils.widgets.get("catalog")
SCHEMA        = dbutils.widgets.get("schema")
PT_ENDPOINT   = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME  = dbutils.widgets.get("vs_index")

from databricks.sdk import WorkspaceClient
ws = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host : {HOST}")
print(f"Catalog.Schema : {CATALOG}.{SCHEMA}")
print(f"PT endpoint    : {PT_ENDPOINT}")
print(f"Genie Space ID : {GENIE_SPACE_ID}")
print(f"VS index       : {VS_INDEX_NAME}")

if GENIE_SPACE_ID == "FILL_IN":
    print("\nNOTE: Update the 'genie_space_id' widget above with your Genie Space ID.")
    print("      Section 2 (UC Functions) does not require a Genie Space ID.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workspace host : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC Catalog.Schema : workshop_au.energy
# MAGIC PT endpoint    : au_east_llm_inregion
# MAGIC Genie Space ID : 01jf3k2m9xyz456   (or FILL_IN if not set yet)
# MAGIC VS index       : workshop_au.energy.policy_docs_index
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — UC Functions via MCP (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — What the UC Functions MCP server exposes
# MAGIC
# MAGIC When you point a `DatabricksMCPClient` at a schema endpoint, it discovers every UC function
# MAGIC in that schema and makes each one available as an MCP tool. The tool name, description, and
# MAGIC parameter schema come directly from the UC function's `COMMENT` metadata.
# MAGIC
# MAGIC ```
# MAGIC UC function definition (Lab 03):
# MAGIC
# MAGIC   CREATE FUNCTION workshop_au.energy.calculate_peak_demand(
# MAGIC       nmi        STRING  COMMENT 'National Meter Identifier',
# MAGIC       start_date STRING  COMMENT 'YYYY-MM-DD',
# MAGIC       end_date   STRING  COMMENT 'YYYY-MM-DD'
# MAGIC   )
# MAGIC   RETURNS STRING
# MAGIC   COMMENT 'Calculate peak 30-minute demand for a NEM meter over a date range.'
# MAGIC
# MAGIC MCP tool exposed:
# MAGIC
# MAGIC   name:        workshop_au__energy__calculate_peak_demand
# MAGIC                         ^^    ^^
# MAGIC                    catalog  schema  (double-underscore separator)
# MAGIC   description: "Calculate peak 30-minute demand for a NEM meter over a date range."
# MAGIC   inputSchema: { nmi: string, start_date: string, end_date: string }
# MAGIC ```
# MAGIC
# MAGIC The descriptions you wrote in `COMMENT` blocks are what the LLM uses to decide when
# MAGIC to call this tool. Write them as capability statements, not implementation notes.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — List tools with `DatabricksMCPClient`

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient

ws = WorkspaceClient()

# Build the MCP endpoint URL for the schema
uc_mcp_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}"

print(f"UC Functions MCP endpoint:")
print(f"  {uc_mcp_url}")
print()

# Authentication is automatic — WorkspaceClient reads credentials from the
# Databricks notebook context, environment variables, or ~/.databrickscfg
# No token handling required.
client = DatabricksMCPClient(uc_mcp_url, ws)

tools = client.list_tools()

print(f"Discovered {len(tools)} tool(s) in {CATALOG}.{SCHEMA}:\n")
for t in tools:
    print(f"  Tool name  : {t.name}")
    print(f"  Description: {t.description[:120]}...")
    if hasattr(t, "inputSchema") and t.inputSchema:
        params = list(t.inputSchema.get("properties", {}).keys())
        print(f"  Parameters : {params}")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC UC Functions MCP endpoint:
# MAGIC   https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/energy
# MAGIC
# MAGIC Discovered 2 tool(s) in workshop_au.energy:
# MAGIC
# MAGIC   Tool name  : workshop_au__energy__calculate_peak_demand
# MAGIC   Description: Calculate peak 30-minute demand for a NEM meter over a date range. Returns
# MAGIC                the maximum half-hour energy read and when...
# MAGIC   Parameters : ['nmi', 'start_date', 'end_date']
# MAGIC
# MAGIC   Tool name  : workshop_au__energy__lookup_asset_status
# MAGIC   Description: Look up maintenance history and operational status of a network asset.
# MAGIC                Returns work orders YTD, total outage minutes...
# MAGIC   Parameters : ['asset_id']
# MAGIC ```
# MAGIC
# MAGIC Notice the tool names use `__` to join catalog, schema, and function name.
# MAGIC This is the MCP naming convention for UC functions.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Call a UC function directly via `DatabricksMCPClient`
# MAGIC
# MAGIC You can call any discovered tool by name using `client.call_tool()`.
# MAGIC The client handles MCP protocol framing, authentication, and response parsing.

# COMMAND ----------

# Call calculate_peak_demand via the low-level MCP client
tool_name = f"{CATALOG}__{SCHEMA}__calculate_peak_demand"

print(f"Calling tool: {tool_name}")
print(f"Arguments  : nmi='6001234567', start_date='2024-07-01', end_date='2024-07-07'")
print()

result = client.call_tool(
    tool_name,
    {
        "nmi": "6001234567",
        "start_date": "2024-07-01",
        "end_date": "2024-07-07",
    },
)

import json
print("Raw MCP response:")
print(json.dumps(result, indent=2, default=str))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC Calling tool: workshop_au__energy__calculate_peak_demand
# MAGIC Arguments  : nmi='6001234567', start_date='2024-07-01', end_date='2024-07-07'
# MAGIC
# MAGIC Raw MCP response:
# MAGIC {
# MAGIC   "content": [
# MAGIC     {
# MAGIC       "type": "text",
# MAGIC       "text": "{\"nmi\": \"6001234567\", \"peak_kwh\": 2.49, \"peak_date\": \"2024-07-04\",
# MAGIC                \"peak_interval_number\": 35, \"peak_time_approx\": \"17:00\",
# MAGIC                \"date_range\": \"2024-07-01 to 2024-07-07\"}"
# MAGIC     }
# MAGIC   ],
# MAGIC   "isError": false
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC The MCP response wraps the UC function's return value in a standard `content` array.
# MAGIC Every MCP server type (Genie, Vector Search, UC Functions) uses this same response shape.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Inspect response content

# COMMAND ----------

# Parse the nested JSON from the MCP text content
if result and "content" in result:
    raw_text = result["content"][0]["text"]
    parsed = json.loads(raw_text)
    print("Parsed function result:")
    for k, v in parsed.items():
        print(f"  {k:<25} {v}")
else:
    print("Unexpected response shape:", result)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Parsed function result:
# MAGIC   nmi                       6001234567
# MAGIC   peak_kwh                  2.49
# MAGIC   peak_date                 2024-07-04
# MAGIC   peak_interval_number      35
# MAGIC   peak_time_approx          17:00
# MAGIC   date_range                2024-07-01 to 2024-07-07
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.5 — Call a single-function endpoint
# MAGIC
# MAGIC If you want to expose only one function (rather than all functions in a schema),
# MAGIC use the single-function endpoint URL:

# COMMAND ----------

# Single-function endpoint — exposes only calculate_peak_demand
single_fn_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}/calculate_peak_demand"
single_client = DatabricksMCPClient(single_fn_url, ws)

single_tools = single_client.list_tools()
print(f"Single-function endpoint exposes {len(single_tools)} tool(s):")
for t in single_tools:
    print(f"  {t.name}")

print()
print("This is useful when:")
print("  - You want least-privilege access (expose only the tool the agent needs)")
print("  - You are building a specialised agent that should only call one function")
print("  - You want to avoid hitting the 15-tools-per-server limit in agent mode")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Single-function endpoint exposes 1 tool(s):
# MAGIC   workshop_au__energy__calculate_peak_demand
# MAGIC
# MAGIC This is useful when:
# MAGIC   - You want least-privilege access (expose only the tool the agent needs)
# MAGIC   - You are building a specialised agent that should only call one function
# MAGIC   - You want to avoid hitting the 15-tools-per-server limit in agent mode
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2 complete</strong><br>
# MAGIC   You can discover and call UC functions via the low-level <code>DatabricksMCPClient</code>.
# MAGIC   Authentication was automatic via <code>WorkspaceClient()</code> — no token handling needed.
# MAGIC   Section 3 builds a full agent that connects to multiple MCP servers simultaneously.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Multi-MCP Agent with LangGraph (15 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Why LangGraph for multi-MCP agents?
# MAGIC
# MAGIC `databricks-langchain` provides `DatabricksMultiServerMCPClient` which:
# MAGIC - Connects to multiple MCP servers simultaneously
# MAGIC - Collects all tools from all servers into a single tool list for the LLM
# MAGIC - Handles routing — when the LLM calls a tool, the client dispatches to the right server
# MAGIC - Integrates natively with LangGraph's `create_react_agent`
# MAGIC - Automatically traces calls to MLflow (no manual instrumentation needed)
# MAGIC
# MAGIC The `ChatDatabricks` LLM wrapper connects to your Provisioned Throughput endpoint in-region.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Create the regulatory policy documents table and Vector Search index
# MAGIC
# MAGIC Section 3 uses a Vector Search MCP server. Run this setup if you have not already done so.

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, IntegerType

policy_docs = [
    (1, "SAIDI Reporting Requirements",
     "SAIDI (System Average Interruption Duration Index) measures the total duration of "
     "interruptions per customer per year. Under AER Service Target Performance Incentive "
     "Scheme (STPIS), distributors must report SAIDI annually. The threshold for NSW "
     "distribution networks is 250 minutes per customer per year. Breaches attract financial "
     "penalties calculated at AUD 15,000 per customer per minute above threshold."),
    (2, "NEM12 Data Quality Standards",
     "NEM12 files must contain 48 interval records per day per meter. Quality flags must be: "
     "A (Actual) for meter-read data, E (Estimated) for data substituted by estimation, "
     "S (Substituted) for data replaced by MDMA. Estimated reads exceeding 5% of intervals "
     "in a billing period require mandatory customer notification under National Energy Retail "
     "Rules clause 46. Meters with persistent quality issues require MDMA review within 10 days."),
    (3, "Critical Peak Demand Management",
     "During network emergencies, AEMO may issue an Emergency Backstop Mechanism (EBM) "
     "direction. Retailers must curtail consumption by 10% within 30 minutes of an EBM notice. "
     "Non-compliance incurs penalties under National Electricity Rules clause 4.10.3. Smart "
     "meters with interval data are mandatory for EBM-eligible customers above 160 MWh per year."),
    (4, "Meter Data Retention Policy",
     "Under the Privacy Act 1988 and the National Energy Retail Rules, meter data must be "
     "retained for a minimum of 7 years. Data must be stored in Australia (s.16C Privacy Act). "
     "Access by third parties requires customer explicit consent via a signed metering data "
     "authorisation form. Retailers must provide customers with access to their own data within "
     "5 business days of request."),
    (5, "Voltage Quality Compliance",
     "Distribution network service providers must maintain supply voltage within -6% to +10% of "
     "nominal voltage (230V) at the customer connection point. Monitoring is required at "
     "representative points across the network. Exceedances must be reported to AER quarterly. "
     "Persistent exceedances (more than 5% of measured intervals in a month) trigger an obligation "
     "to invest in network remediation within 12 months."),
    (6, "Critical Infrastructure Cybersecurity",
     "Under the Security of Critical Infrastructure Act 2018, electricity network operators must "
     "implement a Critical Infrastructure Risk Management Program (CIRMP). AEMO requires notification "
     "of significant cyber incidents within 12 hours. Operational technology (OT) systems including "
     "SCADA and EMS must be patched within 30 days of a critical vulnerability disclosure."),
]

schema = StructType([
    StructField("doc_id",  IntegerType(), False),
    StructField("title",   StringType(),  True),
    StructField("content", StringType(),  True),
])

df_docs = spark.createDataFrame(policy_docs, schema=schema)
df_docs.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_policy_docs")

print(f"Created {CATALOG}.{SCHEMA}.regulatory_policy_docs with {df_docs.count()} documents:")
df_docs.select("doc_id", "title").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Created workshop_au.energy.regulatory_policy_docs with 6 documents:
# MAGIC +------+---------------------------------------+
# MAGIC |doc_id|title                                  |
# MAGIC +------+---------------------------------------+
# MAGIC |1     |SAIDI Reporting Requirements           |
# MAGIC |2     |NEM12 Data Quality Standards           |
# MAGIC |3     |Critical Peak Demand Management        |
# MAGIC |4     |Meter Data Retention Policy            |
# MAGIC |5     |Voltage Quality Compliance             |
# MAGIC |6     |Critical Infrastructure Cybersecurity  |
# MAGIC +------+---------------------------------------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Create Vector Search endpoint and index (skip if already exists)

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn, PipelineType
)

w = WorkspaceClient()
VS_ENDPOINT_NAME = "workshop-vs-endpoint"

# Create VS endpoint (idempotent)
try:
    w.vector_search_endpoints.create_endpoint(
        name=VS_ENDPOINT_NAME,
        endpoint_type=EndpointType.STANDARD,
    )
    print(f"Created VS endpoint: {VS_ENDPOINT_NAME}")
    print("Waiting for endpoint to come ONLINE (first creation: ~5 min)...")
    w.vector_search_endpoints.wait_get_endpoint_vector_search_endpoint_online(VS_ENDPOINT_NAME)
    print("Endpoint is ONLINE.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Endpoint '{VS_ENDPOINT_NAME}' already exists — skipping.")
    else:
        print(f"Endpoint note: {e}")

# COMMAND ----------

# Create Vector Search index (idempotent)
VS_INDEX_FULL = f"{CATALOG}.{SCHEMA}.policy_docs_index"

try:
    w.vector_search_indexes.create_index(
        name=VS_INDEX_FULL,
        endpoint_name=VS_ENDPOINT_NAME,
        primary_key="doc_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=f"{CATALOG}.{SCHEMA}.regulatory_policy_docs",
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="content",
                    # ✅ qwen3 is in-region for AU East. gte-large-en is cross-geo — never use it.
                    embedding_model_endpoint_name="databricks-qwen3-embedding-0-6b",
                )
            ],
        ),
    )
    print(f"Created index: {VS_INDEX_FULL}")
    print("Index is syncing — wait 2-3 minutes before testing it.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Index '{VS_INDEX_FULL}' already exists — triggering sync...")
        w.vector_search_indexes.sync_index(VS_INDEX_FULL)
        print("Sync triggered.")
    else:
        print(f"Index note: {e}")

# Override widget value with confirmed index name
VS_INDEX_NAME = VS_INDEX_FULL
print(f"\nUsing VS index: {VS_INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Endpoint 'workshop-vs-endpoint' already exists — skipping.
# MAGIC Index 'workshop_au.energy.policy_docs_index' already exists — triggering sync...
# MAGIC Sync triggered.
# MAGIC
# MAGIC Using VS index: workshop_au.energy.policy_docs_index
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — Connect to multiple MCP servers with `DatabricksMultiServerMCPClient`
# MAGIC
# MAGIC `DatabricksMCPServer` is a declarative config object — it describes a server but does not
# MAGIC connect yet. `DatabricksMultiServerMCPClient` takes a list of server configs and manages
# MAGIC connections, tool aggregation, and dispatch.

# COMMAND ----------

import asyncio
import mlflow
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import (
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
    ChatDatabricks,
)

# Server 1: UC Functions (all functions in the energy schema)
uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG,
    schema=SCHEMA,
    name="uc-tools",           # logical name for logging / debugging
    timeout=30.0,
    handle_tool_error=True,    # surface UC exceptions as tool error messages, not crashes
)

# Server 2: Genie Space (NL-to-SQL over meter tables)
# Skip if Genie Space ID not set — the agent will still work with UC + VS tools
if GENIE_SPACE_ID != "FILL_IN":
    genie_server = DatabricksMCPServer(
        name="energy-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0,           # Genie queries can take longer — they run actual SQL
        handle_tool_error=True,
    )
    servers = [uc_server, genie_server]
    print("MCP servers configured: UC Functions + Genie Space")
else:
    servers = [uc_server]
    print("NOTE: Genie Space ID not set — using UC Functions only.")
    print("      Set the 'genie_space_id' widget and re-run to include Genie.")

# Server 3: Vector Search (policy documents semantic search)
vs_server = DatabricksMCPServer(
    name="policy-docs-vs",
    url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
    timeout=30.0,
    handle_tool_error=True,
)
servers.append(vs_server)
print(f"MCP servers configured ({len(servers)} total): " + ", ".join(s.name for s in servers))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MCP servers configured: UC Functions + Genie Space
# MAGIC MCP servers configured (3 total): uc-tools, energy-genie, policy-docs-vs
# MAGIC ```
# MAGIC (If Genie Space ID is not set: 2 total — uc-tools, policy-docs-vs)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Inspect aggregated tools from all servers

# COMMAND ----------

async def inspect_aggregated_tools():
    """Connect to all servers and list every available tool."""
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        tools = await multi_client.get_tools()
        print(f"Total tools across all MCP servers: {len(tools)}\n")
        for t in tools:
            # tool.name and tool.description come from the MCP server
            desc_preview = (t.description or "")[:80]
            print(f"  [{t.name}]")
            print(f"    {desc_preview}...")
            print()
        return tools

tools = asyncio.run(inspect_aggregated_tools())

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Total tools across all MCP servers: 4
# MAGIC
# MAGIC   [workshop_au__energy__calculate_peak_demand]
# MAGIC     Calculate peak 30-minute demand for a NEM meter over a date range. Returns the maximum...
# MAGIC
# MAGIC   [workshop_au__energy__lookup_asset_status]
# MAGIC     Look up maintenance history and operational status of a network asset. Returns work orders...
# MAGIC
# MAGIC   [ask_energy_genie]
# MAGIC     Ask a natural language question about energy meter data. The Genie Space translates your...
# MAGIC
# MAGIC   [search_policy_docs_index]
# MAGIC     Search regulatory policy documents using semantic similarity. Returns the most relevant...
# MAGIC ```
# MAGIC
# MAGIC The Genie tool name comes from the Genie Space name. The Vector Search tool name comes from
# MAGIC the index name. Both are auto-discovered — no manual tool registration.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Build the ReAct agent and run three questions

# COMMAND ----------

# Configure MLflow experiment for tracing
mlflow.set_experiment("/Shared/workshop-lab04-mcp-agent")

# The LLM — ChatDatabricks points to your in-region PT endpoint
llm = ChatDatabricks(
    endpoint=PT_ENDPOINT,
    temperature=0.0,
    max_tokens=2048,
)

system_prompt = (
    "You are an expert energy operations assistant for an Australian electricity network operator. "
    "You help operations staff with:\n"
    "  - Meter data analysis (NEM12 interval reads, NMI registers)\n"
    "  - Regulatory compliance (AER, AEMO, SAIDI/SAIFI thresholds)\n"
    "  - Asset maintenance and reliability analysis\n\n"
    "Always use your tools to answer questions — never guess or estimate values. "
    "When you have tool results, provide a clear and actionable summary. "
    "Reference specific numbers, dates, and regulatory requirements where relevant."
)

async def run_langgraph_agent(question: str, run_name: str = "agent_run") -> str:
    """Run the multi-MCP ReAct agent and return the final answer."""
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        agent_tools = await multi_client.get_tools()

        agent = create_react_agent(
            model=llm,
            tools=agent_tools,
            prompt=system_prompt,
        )

        with mlflow.start_run(run_name=run_name):
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=question)]}
            )

        # The final message is the agent's answer
        final_message = result["messages"][-1]
        return final_message.content

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.7 — Question 1: UC Function tool (peak demand)

# COMMAND ----------

q1 = (
    "What was the peak demand for meter NMI 6001234567 during the first week of July 2024, "
    "and at what time of day did it occur?"
)
print(f"Question: {q1}\n")

answer1 = asyncio.run(run_langgraph_agent(q1, run_name="q1_peak_demand"))

print("=" * 65)
print("AGENT ANSWER:")
print("=" * 65)
print(answer1)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Question: What was the peak demand for meter NMI 6001234567 during the first week of July 2024,
# MAGIC and at what time of day did it occur?
# MAGIC
# MAGIC =================================================================
# MAGIC AGENT ANSWER:
# MAGIC =================================================================
# MAGIC The peak demand for NMI 6001234567 during 1–7 July 2024 was **2.49 kWh** in a single
# MAGIC 30-minute interval. This occurred on **4 July 2024** at approximately **17:00**
# MAGIC (interval 35 in NEM12 notation, counting from midnight in 30-minute blocks).
# MAGIC
# MAGIC This peak aligns with the typical evening residential demand peak for NSW networks.
# MAGIC ```
# MAGIC
# MAGIC The agent called `workshop_au__energy__calculate_peak_demand` via the UC Functions MCP server.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.8 — Question 2: Vector Search tool (regulatory compliance)

# COMMAND ----------

q2 = (
    "Our meter for NMI 6001234567 has about 3% estimated reads this month. "
    "Does this comply with NEM12 standards, and do we need to notify the customer?"
)
print(f"Question: {q2}\n")

answer2 = asyncio.run(run_langgraph_agent(q2, run_name="q2_nem12_compliance"))

print("=" * 65)
print("AGENT ANSWER:")
print("=" * 65)
print(answer2)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Question: Our meter for NMI 6001234567 has about 3% estimated reads this month.
# MAGIC Does this comply with NEM12 standards, and do we need to notify the customer?
# MAGIC
# MAGIC =================================================================
# MAGIC AGENT ANSWER:
# MAGIC =================================================================
# MAGIC A 3% estimated read rate complies with NEM12 standards. Under the National Energy Retail
# MAGIC Rules clause 46, mandatory customer notification is only required when estimated reads
# MAGIC exceed **5%** of intervals in a billing period.
# MAGIC
# MAGIC At 3%, no notification is required. However, it is best practice to investigate the
# MAGIC cause of estimated intervals to prevent the rate climbing above 5% before the billing
# MAGIC period closes. If the rate reaches 5%, MDMA review is required within 10 days.
# MAGIC ```
# MAGIC
# MAGIC The agent called `search_policy_docs_index` via the Vector Search MCP server.
# MAGIC No Genie or UC functions were called — the LLM correctly selected the policy search tool.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.9 — Question 3: Multi-tool chain (three tools in one question)

# COMMAND ----------

q3 = (
    "Morning operations briefing — three things:\n"
    "1. Peak demand for meter 6001234567 in the first week of July 2024.\n"
    "2. Maintenance status of asset TF-NSW-001.\n"
    "3. What are the regulatory data retention obligations for our meter data?"
)
print(f"Question:\n{q3}\n")

answer3 = asyncio.run(run_langgraph_agent(q3, run_name="q3_multi_tool_briefing"))

print("=" * 65)
print("AGENT ANSWER:")
print("=" * 65)
print(answer3)

# COMMAND ----------

# MAGIC %md
# MAGIC **What to observe in the output:** The agent issues **three separate tool calls**:
# MAGIC - `workshop_au__energy__calculate_peak_demand` for question 1
# MAGIC - `workshop_au__energy__lookup_asset_status` for question 2
# MAGIC - `search_policy_docs_index` (Vector Search) for question 3
# MAGIC
# MAGIC The LLM reads the compound question, decomposes it into sub-problems, routes each to the
# MAGIC correct MCP server, then synthesises all three results into a single briefing.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Viewing MCP Agent Traces in MLflow
# MAGIC </div>
# MAGIC
# MAGIC After running the three questions, inspect the reasoning traces in MLflow:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar) → Experiments
# MAGIC           → /Shared/workshop-lab04-mcp-agent
# MAGIC           → click a run (e.g. "q3_multi_tool_briefing")
# MAGIC           → Traces tab
# MAGIC
# MAGIC What you will see for question 3 (multi-tool):
# MAGIC
# MAGIC   AgentRun (total: ~8s)
# MAGIC   ├── LLMCall     "Morning briefing — three things..."
# MAGIC   │               → decides to call 3 tools
# MAGIC   ├── ToolCall    workshop_au__energy__calculate_peak_demand
# MAGIC   │               nmi=6001234567, start=2024-07-01, end=2024-07-07
# MAGIC   │               → result: peak_kwh=2.49, peak_date=2024-07-04
# MAGIC   ├── ToolCall    workshop_au__energy__lookup_asset_status
# MAGIC   │               asset_id=TF-NSW-001
# MAGIC   │               → result: work_orders=3, outage_minutes=47
# MAGIC   ├── ToolCall    search_policy_docs_index
# MAGIC   │               query="meter data retention obligations"
# MAGIC   │               → result: doc_id=4, title="Meter Data Retention Policy"
# MAGIC   └── LLMCall     synthesises all three results → final briefing
# MAGIC
# MAGIC Click any ToolCall span to see: the exact arguments sent, the full MCP response,
# MAGIC and the latency for that specific tool call.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 3 complete</strong><br>
# MAGIC   You built a LangGraph ReAct agent that simultaneously uses UC Functions, Genie, and
# MAGIC   Vector Search via MCP. The agent correctly selects the right tool for each question type
# MAGIC   without any explicit routing logic — the LLM uses tool descriptions to decide.
# MAGIC   All calls are traced in MLflow automatically.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — OpenAI Agents SDK Pattern (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — When to use the OpenAI Agents SDK vs LangGraph
# MAGIC
# MAGIC | | LangGraph (`databricks-langchain`) | OpenAI Agents SDK (`databricks-openai`) |
# MAGIC |---|---|---|
# MAGIC | **Best for** | Complex multi-step, stateful, or conditional workflows | Simple to mid-complexity tool-using agents |
# MAGIC | **Graph control** | Full DAG — you define nodes and edges | Automatic — SDK manages the ReAct loop |
# MAGIC | **MCP integration** | `DatabricksMultiServerMCPClient` | `McpServer.from_uc_function()` or `McpServer(url=...)` |
# MAGIC | **Async pattern** | `async with` context manager | `async with` context manager |
# MAGIC | **MLflow tracing** | Automatic via LangChain callbacks | Manual `mlflow.start_run()` or autolog |
# MAGIC
# MAGIC The OpenAI Agents SDK does **not** send data to OpenAI. It is a client-side framework.
# MAGIC All API calls go to your Databricks workspace PT endpoint — `base_url` controls the destination.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — `McpServer.from_uc_function()` — UC Functions MCP

# COMMAND ----------

import asyncio
import mlflow
from agents import Agent, Runner
from databricks_openai.agents import McpServer

# The model string must match an endpoint in your workspace
# Use your PT endpoint name — e.g., "databricks-claude-sonnet-4-6" if it is the endpoint name
# or the full endpoint: f"databricks/{PT_ENDPOINT}"
MODEL = f"databricks/{PT_ENDPOINT}"

async def run_openai_agents_uc_demo(question: str) -> str:
    """Demonstrate the OpenAI Agents SDK with a UC Functions MCP server."""

    # McpServer.from_uc_function() builds the correct URL and handles auth automatically.
    # It uses WorkspaceClient() internally — no token needed.
    async with McpServer.from_uc_function(
        catalog=CATALOG,
        schema=SCHEMA,
        timeout=30.0,
    ) as uc_server:

        agent = Agent(
            name="energy-ops-agent",
            instructions=(
                "You are an expert energy operations assistant for an Australian electricity "
                "network operator. Use your tools to answer questions about meter data and "
                "asset maintenance. Always cite specific numbers from the tool results."
            ),
            model=MODEL,
            mcp_servers=[uc_server],
        )

        result = await Runner.run(
            agent,
            [{"role": "user", "content": question}],
        )

    return result.final_output

# Run a test question
question_uc = "What was the peak demand for NMI 6001234567 during July 2024?"
print(f"Question: {question_uc}\n")

answer_uc = asyncio.run(run_openai_agents_uc_demo(question_uc))

print("=" * 65)
print("AGENT ANSWER (OpenAI Agents SDK + UC Functions MCP):")
print("=" * 65)
print(answer_uc)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Question: What was the peak demand for NMI 6001234567 during July 2024?
# MAGIC
# MAGIC =================================================================
# MAGIC AGENT ANSWER (OpenAI Agents SDK + UC Functions MCP):
# MAGIC =================================================================
# MAGIC The peak demand for NMI 6001234567 in July 2024 was **2.49 kWh** in a single
# MAGIC 30-minute interval, occurring on 4 July 2024 at approximately 17:00 (interval 35).
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Combining UC Functions + Vector Search MCP servers

# COMMAND ----------

async def run_openai_agents_multi_mcp(question: str) -> str:
    """Combine UC Functions and Vector Search MCP servers in the OpenAI Agents SDK."""

    async with McpServer.from_uc_function(
        catalog=CATALOG,
        schema=SCHEMA,
        timeout=30.0,
    ) as uc_server:

        async with McpServer(
            url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
            timeout=30.0,
        ) as vs_server:

            agent = Agent(
                name="energy-ops-multi-agent",
                instructions=(
                    "You are an expert energy operations assistant for an Australian electricity "
                    "network operator. You have access to:\n"
                    "  - UC functions for meter calculations and asset lookups\n"
                    "  - A regulatory policy document search tool\n\n"
                    "Use the right tool for each part of the question. "
                    "Always cite specific numbers, thresholds, and regulatory clauses."
                ),
                model=MODEL,
                mcp_servers=[uc_server, vs_server],
            )

            result = await Runner.run(
                agent,
                [{"role": "user", "content": question}],
            )

    return result.final_output


# Test with a question that requires both tool types
question_multi = (
    "Asset TF-NSW-001 has had several maintenance events this year. "
    "How much outage time has it caused, and based on AER SAIDI requirements, "
    "should we be concerned about this asset's contribution to our reliability index?"
)
print(f"Question: {question_multi}\n")

answer_multi = asyncio.run(run_openai_agents_multi_mcp(question_multi))

print("=" * 65)
print("AGENT ANSWER (UC Functions + Vector Search MCP):")
print("=" * 65)
print(answer_multi)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Question: Asset TF-NSW-001 has had several maintenance events this year.
# MAGIC How much outage time has it caused, and based on AER SAIDI requirements,
# MAGIC should we be concerned about this asset's contribution to our reliability index?
# MAGIC
# MAGIC =================================================================
# MAGIC AGENT ANSWER (UC Functions + Vector Search MCP):
# MAGIC =================================================================
# MAGIC Asset TF-NSW-001 has had **3 work orders** year-to-date, resulting in **47 minutes**
# MAGIC of total outage time.
# MAGIC
# MAGIC Under the AER STPIS (SAIDI Reporting Requirements), the NSW threshold is **250 minutes
# MAGIC per customer per year**. At 47 minutes, this single asset is contributing significantly
# MAGIC if the outage affected a large number of customers. The formula for SAIDI contribution
# MAGIC is: (customer_minutes_interrupted) / (total_customers_served).
# MAGIC
# MAGIC Recommendation: if TF-NSW-001 serves more than ~1,000 customers, this asset alone
# MAGIC could be contributing 0.05+ minutes to your network-wide SAIDI. I would recommend
# MAGIC reviewing maintenance scheduling and considering proactive replacement if the trend
# MAGIC continues into H2.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Adding a Genie MCP server (when Genie Space ID is available)

# COMMAND ----------

async def run_openai_agents_with_genie(question: str) -> str:
    """Three MCP servers: UC Functions + Vector Search + Genie Space."""

    if GENIE_SPACE_ID == "FILL_IN":
        print("NOTE: Genie Space ID not configured. Set the 'genie_space_id' widget.")
        print("      Running with UC Functions + Vector Search only.\n")
        return await run_openai_agents_multi_mcp(question)

    async with McpServer.from_uc_function(
        catalog=CATALOG,
        schema=SCHEMA,
        timeout=30.0,
    ) as uc_server:

        async with McpServer(
            url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            timeout=60.0,          # Genie runs actual SQL — allow more time
        ) as genie_server:

            async with McpServer(
                url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
                timeout=30.0,
            ) as vs_server:

                agent = Agent(
                    name="energy-ops-full-agent",
                    instructions=(
                        "You are an expert energy operations assistant. You have access to:\n"
                        "  - UC functions for peak demand calculations and asset lookups\n"
                        "  - A Genie Space for natural language queries over meter consumption data\n"
                        "  - A regulatory policy document search tool\n\n"
                        "For questions about meter data totals or trends, use the Genie tool.\n"
                        "For questions about individual meter calculations, use UC functions.\n"
                        "For questions about regulations or compliance, use the policy search tool.\n"
                        "Cite specific numbers and regulatory references in your answers."
                    ),
                    model=MODEL,
                    mcp_servers=[uc_server, genie_server, vs_server],
                )

                result = await Runner.run(
                    agent,
                    [{"role": "user", "content": question}],
                )

    return result.final_output


# Test with a data-aggregation question (routes to Genie)
question_genie = "What is the total consumption in kWh for each NMI in the dataset?"
print(f"Question: {question_genie}\n")

answer_genie = asyncio.run(run_openai_agents_with_genie(question_genie))

print("=" * 65)
print("AGENT ANSWER (3 MCP servers incl. Genie):")
print("=" * 65)
print(answer_genie)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (with Genie Space configured):**
# MAGIC ```
# MAGIC Question: What is the total consumption in kWh for each NMI in the dataset?
# MAGIC
# MAGIC =================================================================
# MAGIC AGENT ANSWER (3 MCP servers incl. Genie):
# MAGIC =================================================================
# MAGIC Total consumption by NMI across the full dataset:
# MAGIC
# MAGIC | NMI        | Total kWh |
# MAGIC |------------|-----------|
# MAGIC | 6001234567 | 378.4     |
# MAGIC | 6007654321 | 412.1     |
# MAGIC | 6009876543 | 294.7     |
# MAGIC
# MAGIC (Values sourced from interval_reads table via Genie Space SQL query.)
# MAGIC ```
# MAGIC
# MAGIC **Note on Genie MCP polling:** For long-running NL-to-SQL queries, the Genie MCP server
# MAGIC may use a polling pattern — the initial response returns a query ID, and the client polls
# MAGIC until the SQL completes. The `McpServer` and `DatabricksMCPServer` clients handle this
# MAGIC transparently. The `timeout=60.0` parameter controls the maximum wait.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 — Production note: `get_databricks_resources()`
# MAGIC
# MAGIC When deploying an MCP agent to **Databricks Model Serving**, you must declare which
# MAGIC Databricks resources the agent uses. This is how Model Serving knows to inject the
# MAGIC correct service principal credentials for each MCP server at inference time.

# COMMAND ----------

# Production deployment — declare MCP resource dependencies
# This is required ONLY when deploying to Model Serving endpoints.
# In notebooks, authentication is automatic via the notebook session.

# Example (do not run in the lab — for reference only):
#
# from databricks_openai.agents import McpServer
# from mlflow.models.resources import DatabricksResource
#
# async def build_agent_for_deployment():
#     async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA) as uc_server:
#         async with McpServer(
#             url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index"
#         ) as vs_server:
#
#             agent = Agent(
#                 name="energy-ops-prod",
#                 model=MODEL,
#                 mcp_servers=[uc_server, vs_server],
#             )
#
#             # get_databricks_resources() introspects the MCP servers and returns the
#             # resource declarations needed for Model Serving to inject credentials.
#             resources: list[DatabricksResource] = (
#                 await McpServer.get_databricks_resources([uc_server, vs_server])
#             )
#
#             return agent, resources
#
# # Then log to MLflow with resources:
# # with mlflow.start_run():
# #     mlflow.pyfunc.log_model(
# #         "agent",
# #         python_model=...,
# #         resources=resources,   # <-- declares the MCP dependencies
# #     )

print("get_databricks_resources() pattern shown above.")
print("This is required for Model Serving deployment — not needed for notebook execution.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC get_databricks_resources() pattern shown above.
# MAGIC This is required for Model Serving deployment — not needed for notebook execution.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 4 complete</strong><br>
# MAGIC   You used the OpenAI Agents SDK with <code>McpServer</code> async context managers to connect
# MAGIC   UC Functions, Vector Search, and Genie to a single agent. Authentication was automatic.
# MAGIC   You also saw the <code>get_databricks_resources()</code> pattern for production deployment.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Bonus — Claude Desktop and External IDE Configuration
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 1 — Use your Databricks MCP servers from Claude Desktop
# MAGIC
# MAGIC Any MCP-compatible client can connect to your Databricks workspace MCP servers using a PAT.
# MAGIC This lets participants use Claude Desktop or Cursor IDE as a front-end to the same
# MAGIC UC Functions, Genie, and Vector Search tools built in this lab.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Claude Desktop installed on your laptop (claude.ai/desktop)
# MAGIC - A Databricks PAT (User Settings → Access Tokens → Generate new token)
# MAGIC - `npx` available (`npm install -g npx` if not present)
# MAGIC
# MAGIC **Configuration file location:**
# MAGIC - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
# MAGIC - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
# MAGIC
# MAGIC **Example configuration (replace values in angle brackets):**
# MAGIC
# MAGIC ```json
# MAGIC {
# MAGIC   "mcpServers": {
# MAGIC     "databricks-uc-functions": {
# MAGIC       "command": "npx",
# MAGIC       "args": [
# MAGIC         "mcp-remote",
# MAGIC         "https://<workspace>.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/energy",
# MAGIC         "--header",
# MAGIC         "Authorization: Bearer <YOUR_PAT>"
# MAGIC       ]
# MAGIC     },
# MAGIC     "databricks-genie": {
# MAGIC       "command": "npx",
# MAGIC       "args": [
# MAGIC         "mcp-remote",
# MAGIC         "https://<workspace>.azuredatabricks.net/api/2.0/mcp/genie/<GENIE_SPACE_ID>",
# MAGIC         "--header",
# MAGIC         "Authorization: Bearer <YOUR_PAT>"
# MAGIC       ]
# MAGIC     },
# MAGIC     "databricks-policy-docs": {
# MAGIC       "command": "npx",
# MAGIC       "args": [
# MAGIC         "mcp-remote",
# MAGIC         "https://<workspace>.azuredatabricks.net/api/2.0/mcp/vector-search/workshop_au/energy/policy_docs_index",
# MAGIC         "--header",
# MAGIC         "Authorization: Bearer <YOUR_PAT>"
# MAGIC       ]
# MAGIC     }
# MAGIC   }
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC After editing the file, restart Claude Desktop. You should see the Databricks tools appear
# MAGIC in the tools panel (the hammer icon in the chat input area).
# MAGIC
# MAGIC **Security note for regulated environments:**
# MAGIC - Use a PAT with a short expiry (7-30 days) for development
# MAGIC - For team-wide access, use a Service Principal PAT stored in a secrets manager
# MAGIC - Do not commit PATs to git — use environment variable substitution or a secrets file

# COMMAND ----------

# Generate the Claude Desktop config for this participant's workspace
config = {
    "mcpServers": {
        "databricks-uc-functions": {
            "command": "npx",
            "args": [
                "mcp-remote",
                f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}",
                "--header",
                "Authorization: Bearer <YOUR_PAT>"
            ]
        },
        "databricks-policy-docs": {
            "command": "npx",
            "args": [
                "mcp-remote",
                f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
                "--header",
                "Authorization: Bearer <YOUR_PAT>"
            ]
        }
    }
}

if GENIE_SPACE_ID != "FILL_IN":
    config["mcpServers"]["databricks-genie"] = {
        "command": "npx",
        "args": [
            "mcp-remote",
            f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            "--header",
            "Authorization: Bearer <YOUR_PAT>"
        ]
    }

print("Your claude_desktop_config.json snippet:")
print("=" * 65)
print(json.dumps(config, indent=2))
print("=" * 65)
print()
print("Replace <YOUR_PAT> with a token from:")
print(f"  {HOST}/settings/user/developer/access-tokens")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC Your claude_desktop_config.json snippet:
# MAGIC =================================================================
# MAGIC {
# MAGIC   "mcpServers": {
# MAGIC     "databricks-uc-functions": {
# MAGIC       "command": "npx",
# MAGIC       "args": [
# MAGIC         "mcp-remote",
# MAGIC         "https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/energy",
# MAGIC         "--header",
# MAGIC         "Authorization: Bearer <YOUR_PAT>"
# MAGIC       ]
# MAGIC     },
# MAGIC     "databricks-policy-docs": {
# MAGIC       "command": "npx",
# MAGIC       "args": [ ... ]
# MAGIC     }
# MAGIC   }
# MAGIC }
# MAGIC =================================================================
# MAGIC Replace <YOUR_PAT> with a token from:
# MAGIC   https://adb-xxxx.azuredatabricks.net/settings/user/developer/access-tokens
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 2 — Databricks SQL MCP server
# MAGIC
# MAGIC The SQL MCP server exposes a single `execute_sql` tool that runs arbitrary SQL on a
# MAGIC SQL warehouse. Use with care — scope access via warehouse permissions and UC grants.
# MAGIC
# MAGIC ```python
# MAGIC # Example: SQL MCP server (not used in main lab — for reference)
# MAGIC from databricks_langchain import DatabricksMCPServer
# MAGIC
# MAGIC sql_server = DatabricksMCPServer(
# MAGIC     name="databricks-sql",
# MAGIC     url=f"{HOST}/api/2.0/mcp/sql",
# MAGIC     timeout=30.0,
# MAGIC     handle_tool_error=True,
# MAGIC )
# MAGIC
# MAGIC # When added to an agent, the LLM can write and run SQL directly.
# MAGIC # Governance: the tool runs under the identity of the calling principal.
# MAGIC # UC row-level security, column masks, and table grants still apply.
# MAGIC ```
# MAGIC
# MAGIC **When to use the SQL MCP server vs Genie MCP:**
# MAGIC
# MAGIC | | SQL MCP | Genie MCP |
# MAGIC |---|---|---|
# MAGIC | Who writes SQL | The LLM | Genie (NL → SQL translation) |
# MAGIC | Schema knowledge | LLM must know the schema | Genie handles schema discovery |
# MAGIC | Business vocabulary | LLM uses column names literally | Genie uses your business descriptions |
# MAGIC | Best for | Technical agents with schema context in system prompt | Business user-facing agents |

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 3 — Audit MCP calls in system tables
# MAGIC
# MAGIC Every MCP call is logged in the Databricks audit trail. Query it in any SQL cell:

# COMMAND ----------

# View recent MCP-related audit events
# This query reads from system tables — requires the audit log feature to be enabled

audit_query = f"""
SELECT
    event_time,
    user_identity.email         AS user_email,
    service_name,
    action_name,
    request_params              AS mcp_params
FROM system.access.audit
WHERE service_name IN ('vectorSearch', 'databricksSQL', 'genie', 'unityCatalog')
  AND event_time > current_timestamp() - INTERVAL 1 HOUR
ORDER BY event_time DESC
LIMIT 20
"""

print("SQL to audit recent MCP calls:")
print("=" * 65)
print(audit_query)
print("=" * 65)
print()
print("Run this in a SQL cell or Databricks SQL editor to see the audit trail.")
print("service_name values for MCP endpoints:")
print("  vectorSearch  → Vector Search MCP calls")
print("  genie         → Genie Space MCP calls")
print("  unityCatalog  → UC Function MCP calls")
print("  databricksSQL → SQL MCP calls")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Try It Yourself — Add a Regulatory Compliance Tool
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise — Add `check_regulatory_compliance` as a fourth MCP tool
# MAGIC
# MAGIC Create a new UC function and add it to the multi-MCP agent from Section 3.
# MAGIC
# MAGIC **The function should:**
# MAGIC - Parameters: `region` (STRING), `metric` (STRING: 'SAIDI' or 'SAIFI'), `actual_value` (DOUBLE)
# MAGIC - Look up the threshold from a `regulatory_thresholds` reference table
# MAGIC - Return JSON: `region`, `metric`, `threshold`, `actual_value`, `breach` (bool), `penalty_estimate_aud`
# MAGIC - Penalty formula: `(actual_value - threshold) * 15000` if in breach, else 0
# MAGIC
# MAGIC **Step 1:** Create the thresholds table.

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, DoubleType

threshold_rows = [
    ("NSW", "SAIDI", 250.0),
    ("VIC", "SAIDI", 230.0),
    ("QLD", "SAIDI", 270.0),
    ("SA",  "SAIDI", 260.0),
    ("NSW", "SAIFI", 1.5),
    ("VIC", "SAIFI", 1.4),
    ("QLD", "SAIFI", 1.6),
    ("SA",  "SAIFI", 1.5),
]

threshold_schema = StructType([
    StructField("region",    StringType(), False),
    StructField("metric",    StringType(), False),
    StructField("threshold", DoubleType(), False),
])

(spark.createDataFrame(threshold_rows, threshold_schema)
     .write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_thresholds"))

print(f"Created {CATALOG}.{SCHEMA}.regulatory_thresholds")
spark.table(f"{CATALOG}.{SCHEMA}.regulatory_thresholds").show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Created workshop_au.energy.regulatory_thresholds
# MAGIC +------+-----+---------+
# MAGIC |region|metric|threshold|
# MAGIC +------+-----+---------+
# MAGIC |NSW   |SAIDI|250.0    |
# MAGIC |VIC   |SAIDI|230.0    |
# MAGIC ...
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 2:** Register the UC function (uncomment and run).

# COMMAND ----------

# TODO: Uncomment the block below, fill in the catalog/schema, and run.
#
# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.check_regulatory_compliance(
#     region       STRING COMMENT 'Australian state/territory code: NSW, VIC, QLD, or SA',
#     metric       STRING COMMENT 'Reliability metric to check: SAIDI or SAIFI',
#     actual_value DOUBLE COMMENT 'The actual measured value for the metric this period'
# )
# RETURNS STRING
# COMMENT 'Check whether a SAIDI or SAIFI reliability metric is in breach of AER regulatory
# thresholds for a given Australian state. Returns JSON with: region, metric, threshold,
# actual_value, breach (bool), and penalty_estimate_aud. Use when asked whether performance
# targets have been met or what financial penalty exposure the network faces.'
# LANGUAGE PYTHON
# AS $$
# import json
# try:
#     from pyspark.sql import SparkSession
#     from pyspark.sql import functions as F
#     spark = SparkSession.builder.getOrCreate()
#
#     row = (
#         spark.table("{CATALOG}.{SCHEMA}.regulatory_thresholds")
#         .filter((F.col("region") == region) & (F.col("metric") == metric))
#         .first()
#     )
#     if row is None:
#         return json.dumps({{"error": f"No threshold found for {{metric}} in {{region}}"}})
#
#     threshold = float(row["threshold"])
#     breach = actual_value > threshold
#     penalty = round((actual_value - threshold) * 15000, 2) if breach else 0.0
#
#     return json.dumps({{
#         "region": region,
#         "metric": metric,
#         "threshold": threshold,
#         "actual_value": actual_value,
#         "breach": breach,
#         "penalty_estimate_aud": penalty,
#     }})
# except Exception as e:
#     return json.dumps({{"error": str(e)}})
# $$
# """)
# print(f"Registered: {CATALOG}.{SCHEMA}.check_regulatory_compliance")

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 3:** The new function will be automatically discovered by the next call to
# MAGIC `DatabricksMultiServerMCPClient.get_tools()` or `McpServer.from_uc_function()`.
# MAGIC No code changes needed in the agent — just re-run the agent loop.
# MAGIC
# MAGIC **Test question to validate the new tool:**
# MAGIC
# MAGIC ```python
# MAGIC answer = asyncio.run(run_langgraph_agent(
# MAGIC     "The NSW network had 278 minutes of SAIDI this year. "
# MAGIC     "Are we in breach of AER thresholds? What is our estimated penalty exposure?"
# MAGIC ))
# MAGIC print(answer)
# MAGIC ```
# MAGIC
# MAGIC **Success criteria:**
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | SQL test | `SELECT workshop_au.energy.check_regulatory_compliance('NSW', 'SAIDI', 278)` returns `breach: true, penalty_estimate_aud: 420000.0` (28 × $15k) |
# MAGIC | MLflow trace | Tool call appears as `workshop_au__energy__check_regulatory_compliance` in the Traces tab |
# MAGIC | Answer quality | Agent clearly states threshold (250), actual (278), breach status, and AUD penalty |
# MAGIC | Tool routing | The LLM routes to `check_regulatory_compliance` rather than `search_policy_docs_index` |
# MAGIC
# MAGIC **Bonus:** Modify the system prompt to add a note about regulatory escalation procedure
# MAGIC when `breach: true` is returned, then verify the agent includes it automatically.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 04 Complete</h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 14px 0;">
# MAGIC     You built agents that connect to multiple Databricks MCP servers simultaneously —
# MAGIC     all running within Australia East with automatic authentication and full audit trails.
# MAGIC   </p>
# MAGIC
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 14px;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Lab</th>
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Core skill</th>
# MAGIC       <th style="text-align: left; padding: 6px 10px;">AU East</th>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 01</td>
# MAGIC       <td style="padding: 5px 10px;">Genie Code — generate, explain, fix, document</td>
# MAGIC       <td style="padding: 5px 10px;">In-region ✅</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 02</td>
# MAGIC       <td style="padding: 5px 10px;">Notebook AI chat — schema discovery, SQL gen, agent mode</td>
# MAGIC       <td style="padding: 5px 10px;">In-region ✅</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 03</td>
# MAGIC       <td style="padding: 5px 10px;">UC functions as AI tools — register, test, govern</td>
# MAGIC       <td style="padding: 5px 10px;">In-region ✅</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 5px 10px;">Lab 04</td>
# MAGIC       <td style="padding: 5px 10px;">MCP integration — UC Functions + Genie + Vector Search</td>
# MAGIC       <td style="padding: 5px 10px;">In-region ✅</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 6px 0; font-weight: bold;">Key packages used in this lab:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0 0 12px 0; padding-left: 20px;">
# MAGIC     <li><code>databricks-mcp</code> — low-level <code>DatabricksMCPClient</code> for tool discovery and direct calls</li>
# MAGIC     <li><code>databricks-langchain</code> — <code>DatabricksMultiServerMCPClient</code> + <code>ChatDatabricks</code> for LangGraph agents</li>
# MAGIC     <li><code>databricks-openai</code> — <code>McpServer</code> for the OpenAI Agents SDK pattern</li>
# MAGIC   </ul>
# MAGIC
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 6px 0; font-weight: bold;">Next steps:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0; padding-left: 20px;">
# MAGIC     <li>Lab 05 (optional): Deploying MCP agents to Model Serving using <code>get_databricks_resources()</code></li>
# MAGIC     <li>Workshop 2B: Building no-code NL-to-SQL Genie Spaces for business users</li>
# MAGIC     <li>Production checklist: Service Principal auth, Secret Scopes, MLflow Tracing in Model Serving</li>
# MAGIC   </ul>
# MAGIC </div>
