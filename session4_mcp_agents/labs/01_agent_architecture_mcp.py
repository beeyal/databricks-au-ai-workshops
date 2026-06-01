# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 01: Agent Architecture &amp; MCP Ecosystem
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Energy Sector
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Understand the AEMO Operations Agent, navigate the MCP ecosystem, and verify your environment.
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>30 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Workspace access, workshop catalog created
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All MCP endpoints: AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Role</strong><br>Developer / ML Engineer
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will learn
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | What We're Building | AEMO Operations Agent architecture | 10 min |
# MAGIC | 2 | The MCP Ecosystem | Navigate AI Gateway MCPs tab, server types and URLs | 10 min |
# MAGIC | 3 | Package Setup & Auth | Install packages, verify workspace, confirm MCP servers reachable | 10 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why MCP for regulated industries?
# MAGIC
# MAGIC | Concern | MCP answer |
# MAGIC |---------|-----------|
# MAGIC | **Data residency** | All Databricks MCP endpoints are workspace-local — no data leaves AU East |
# MAGIC | **Audit trail** | Every MCP call is recorded in `system.access.audit` with user identity and arguments |
# MAGIC | **Access control** | Unity Catalog EXECUTE grants govern which tools an agent can call |
# MAGIC | **No vendor lock-in** | MCP is an open standard (Anthropic, 2024) — client library is client-side only |
# MAGIC | **Consistent auth** | Same Databricks OAuth/PAT as any other workspace API |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — What We're Building (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — The AEMO Operations Agent
# MAGIC
# MAGIC Over Labs 01–03 you will build an agent that answers questions about the National Electricity Market (NEM).
# MAGIC
# MAGIC ```
# MAGIC ┌─── AEMO Operations Agent ──────────────────────────────────┐
# MAGIC │  User: "Were there price spikes in VIC yesterday?"         │
# MAGIC │  Step 1: Query spot_prices via Genie MCP                   │
# MAGIC │  Step 2: Get dispatch data via Genie MCP                   │
# MAGIC │  Step 3: Calculate constraints via UC Function MCP         │
# MAGIC │  Step 4: Search market notices via Vector Search MCP       │
# MAGIC └────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC Unlike a RAG chatbot, this agent runs live SQL via Genie, calls Python functions in Unity Catalog for calculations, and performs semantic search across market notices — leaving a full audit trail in `system.access.audit`.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — AEMO NEM domain quick reference
# MAGIC
# MAGIC | Term | Meaning | Example |
# MAGIC |------|---------|---------|
# MAGIC | **NEM** | National Electricity Market — QLD, NSW, VIC, SA, TAS | — |
# MAGIC | **Region** | NEM dispatch region code | `VIC1`, `NSW1`, `SA1` |
# MAGIC | **Spot price** | 5-minute dispatch price in $/MWh | $14,000/MWh (price cap) |
# MAGIC | **Price spike** | Interval where spot price > $300/MWh | — |
# MAGIC | **DUID** | Dispatchable Unit Identifier — unique generator code | `LOYB1` |
# MAGIC | **LOR** | Lack of Reserve — reserve margin too low | LOR3 = emergency |
# MAGIC | **Market notice** | Official AEMO bulletin | "LOR2 declared VIC 14:30" |
# MAGIC
# MAGIC The agent's system prompt (written in Lab 03) provides this context to the LLM.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Three MCP servers, three tool types
# MAGIC
# MAGIC | Server type | Strength | URL pattern |
# MAGIC |-------------|----------|-------------|
# MAGIC | **Genie MCP** | NL → SQL translation over NEM tables | `.../mcp/genie/{space_id}` |
# MAGIC | **UC Functions MCP** | Deterministic Python calculations | `.../mcp/functions/{catalog}/{schema}` |
# MAGIC | **Vector Search MCP** | Semantic search over market notices | `.../mcp/vector-search/{cat}/{schema}/{index}` |
# MAGIC
# MAGIC All three endpoint types are in-region for Australia East. The LLM selects tools based on **tool descriptions** — not hardcoded routing. Your UC function `COMMENT` and Genie Space description are the descriptions the LLM reads at inference time.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ UI: Navigate to the Genie section (3 min)
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Genie (diamond/sparkle icon)
# MAGIC → click "AEMO NEM Operations" → Configure → Instructions tab
# MAGIC ```
# MAGIC
# MAGIC The Instructions tab contains the system prompt that shapes Genie's SQL translation. In Lab 03 you will call this same space via MCP from an agent rather than from the Genie chat UI.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — The MCP Ecosystem in Databricks (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — The 5 Databricks MCP server types
# MAGIC
# MAGIC | MCP Server type | URL pattern | Tool count |
# MAGIC |----------------|-------------|-----------|
# MAGIC | **UC Functions — schema** | `.../mcp/functions/{catalog}/{schema}` | One per function |
# MAGIC | **UC Functions — single** | `.../mcp/functions/{catalog}/{schema}/{function}` | 1 |
# MAGIC | **Genie Space** | `.../mcp/genie/{genie_space_id}` | 1 |
# MAGIC | **Vector Search** | `.../mcp/vector-search/{catalog}/{schema}/{index}` | 1 |
# MAGIC | **Databricks SQL** | `.../mcp/sql` | 1 |
# MAGIC
# MAGIC ### 2.2 — Tool naming convention for UC Functions
# MAGIC
# MAGIC UC function names use **double-underscore** separators in MCP tool names:
# MAGIC ```
# MAGIC  UC function:   workshop_au.aemo.calculate_peak_demand
# MAGIC  MCP tool name: workshop_au__aemo__calculate_peak_demand
# MAGIC ```
# MAGIC This matters when inspecting tool call traces in MLflow or writing routing tests.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ UI: The AI Gateway MCPs tab (5 min)
# MAGIC </div>
# MAGIC
# MAGIC **REQUIRES AI Gateway v2:** Account Console → Previews → toggle "AI Gateway V2" ON first.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → AI Gateway → MCPs tab
# MAGIC Shows all registered MCP servers with endpoint URLs and usage stats.
# MAGIC Actions: [Copy URL] next to each server, [View] to see tool names and schemas.
# MAGIC ```
# MAGIC
# MAGIC If the MCPs tab is not visible, AI Gateway V2 is not enabled for your workspace. You can still use MCP via code — the tab is the UI control plane only.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Finding your Genie Space ID
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Genie → click "AEMO NEM Operations"
# MAGIC Browser URL bar: .../genie/rooms/{GENIE_SPACE_ID}
# MAGIC Copy everything after /genie/rooms/
# MAGIC ```
# MAGIC
# MAGIC **Alternative:** AI Gateway → MCPs → click the Genie server row — URL ends with `/mcp/genie/{GENIE_SPACE_ID}`.
# MAGIC
# MAGIC Write your Space ID here — you will paste it into widgets in Labs 02 and 03:
# MAGIC ```
# MAGIC My GENIE_SPACE_ID = _________________________________
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Finding your Vector Search index name
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Compute → Vector Search tab
# MAGIC Click an index to see: status, row count, embedding model, sync history.
# MAGIC Full name format: {catalog}.{schema}.{index_name}
# MAGIC e.g. workshop_au.aemo.aemo_market_notices_index
# MAGIC ```
# MAGIC
# MAGIC There is NO query UI for Vector Search — use the Python SDK or `vector_search()` SQL function.
# MAGIC
# MAGIC Write your index name here:
# MAGIC ```
# MAGIC My VS_INDEX = workshop_au.aemo._________________________________
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.5 — Finding your UC Functions schema
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Catalog → workshop_au → aemo → Functions
# MAGIC Click calculate_peak_demand → read the Comment field.
# MAGIC The Comment IS the MCP tool description the LLM reads when deciding which tool to call.
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2</strong><br>
# MAGIC   You have located all three MCP servers in the UI, found your Genie Space ID, Vector Search index name, and UC function schema.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Package Setup &amp; Authentication (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — The three MCP packages
# MAGIC
# MAGIC | Package | What it gives you | Use for |
# MAGIC |---------|-------------------|---------|
# MAGIC | `databricks-mcp` | Low-level `DatabricksMCPClient` | Tool discovery, direct MCP calls |
# MAGIC | `databricks-langchain` | `DatabricksMCPServer`, `DatabricksMultiServerMCPClient`, `ChatDatabricks` | LangGraph agents (Labs 02 and 03) |
# MAGIC | `databricks-openai` | `McpServer` for OpenAI Agents SDK | OpenAI Agents SDK pattern (bonus) |

# COMMAND ----------

%pip install databricks-mcp databricks-langchain databricks-openai mlflow langchain-core langgraph --quiet
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Python interpreter restarted.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Workshop widgets
# MAGIC
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Check your workspace URL
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Browser address bar: https://adb-1234567890123456.7.azuredatabricks.net/...
# MAGIC                                ↑ This is your HOST — appears in every MCP endpoint URL.
# MAGIC ```

# COMMAND ----------

dbutils.widgets.text("catalog",         "workshop_au",               "Catalog name")
dbutils.widgets.text("schema_aemo",     "aemo",                      "AEMO schema name")
dbutils.widgets.text("pt_endpoint",     "au_east_llm_inregion",      "PT endpoint name")
dbutils.widgets.text("genie_space_id",  "",                          "Genie Space ID")
dbutils.widgets.text("vs_index",        "workshop_au.aemo.aemo_market_notices_index",
                                                                      "VS index (3-part name)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME  = dbutils.widgets.get("vs_index")

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print("Workshop configuration")
print("=" * 55)
print(f"  Workspace host  : {HOST}")
print(f"  Catalog.Schema  : {CATALOG}.{SCHEMA_AEMO}")
print(f"  PT endpoint     : {PT_ENDPOINT}")
print(f"  Genie Space ID  : {GENIE_SPACE_ID}")
print(f"  VS index        : {VS_INDEX_NAME}")
print("=" * 55)

if GENIE_SPACE_ID == "":
    print("\nACTION REQUIRED: paste your Genie Space ID into the 'genie_space_id' widget above.")
    print("  → Left sidebar → Genie → AEMO NEM Operations → copy ID from URL")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workshop configuration
# MAGIC =======================================================
# MAGIC   Workspace host  : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC   Catalog.Schema  : workshop_au.aemo
# MAGIC   PT endpoint     : au_east_llm_inregion
# MAGIC   Genie Space ID  : 01jxyz123abc456  (or FILL_IN if not set yet)
# MAGIC   VS index        : workshop_au.aemo.aemo_market_notices_index
# MAGIC =======================================================
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Verify package imports

# COMMAND ----------

import sys
print(f"Python {sys.version.split()[0]}")
print()

imports_to_check = [
    ("databricks.sdk",         "WorkspaceClient"),
    ("databricks_mcp",         "DatabricksMCPClient"),
    ("databricks_langchain",   "DatabricksMCPServer"),
    ("databricks_langchain",   "DatabricksMultiServerMCPClient"),
    ("databricks_langchain",   "ChatDatabricks"),
    ("langgraph.prebuilt",     "create_react_agent"),
    ("langchain_core.messages","HumanMessage"),
    ("mlflow",                 "mlflow"),
]

all_ok = True
for module, name in imports_to_check:
    try:
        mod = __import__(module, fromlist=[name])
        getattr(mod, name) if name != "mlflow" else mod
        print(f"  OK   {module}.{name}")
    except Exception as e:
        print(f"  FAIL {module}.{name} — {e}")
        all_ok = False

print()
if all_ok:
    print("All imports successful. Environment is ready for Labs 02 and 03.")
else:
    print("Some imports failed. Re-run the %pip install cell and restart Python again.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Python 3.11.x
# MAGIC
# MAGIC   OK   databricks.sdk.WorkspaceClient
# MAGIC   OK   databricks_mcp.DatabricksMCPClient
# MAGIC   OK   databricks_langchain.DatabricksMCPServer
# MAGIC   OK   databricks_langchain.DatabricksMultiServerMCPClient
# MAGIC   OK   databricks_langchain.ChatDatabricks
# MAGIC   OK   langgraph.prebuilt.create_react_agent
# MAGIC   OK   langchain_core.messages.HumanMessage
# MAGIC   OK   mlflow.mlflow
# MAGIC
# MAGIC All imports successful. Environment is ready for Labs 02 and 03.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — Authentication
# MAGIC
# MAGIC `WorkspaceClient()` in a Databricks notebook auto-authenticates — no manual token needed. It reads credentials injected by Databricks at cluster start, and `DatabricksMCPServer` classes use `WorkspaceClient()` internally.
# MAGIC
# MAGIC Outside notebooks (local IDE, Claude Desktop, CI/CD): use a Personal Access Token from User Settings → Access Tokens, stored in `~/.databrickscfg` or `DATABRICKS_TOKEN`. Never commit PATs to git.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Verify workspace connection

# COMMAND ----------

from databricks.sdk import WorkspaceClient

ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")
me   = ws.current_user.me()

print("Workspace connection verified.")
print()
print(f"  Host        : {HOST}")
print(f"  User        : {me.user_name}")
print(f"  Display name: {me.display_name}")
print()

if "azuredatabricks.net" in HOST:
    print("  Cloud       : Azure Databricks")
elif "gcp.databricks.com" in HOST:
    print("  Cloud       : GCP Databricks")
elif "cloud.databricks.com" in HOST:
    print("  Cloud       : AWS Databricks")

try:
    tables = list(ws.tables.list(catalog_name=CATALOG, schema_name=SCHEMA_AEMO))
    print(f"  Catalog     : {CATALOG}.{SCHEMA_AEMO} — accessible ({len(tables)} tables visible)")
except Exception as e:
    print(f"  Catalog     : {CATALOG}.{SCHEMA_AEMO} — WARNING: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workspace connection verified.
# MAGIC
# MAGIC   Host        : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC   User        : you@yourcompany.com
# MAGIC   Display name: Your Name
# MAGIC
# MAGIC   Cloud       : Azure Databricks
# MAGIC   Catalog     : workshop_au.aemo — accessible (3 tables visible)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Verify MCP server reachability

# COMMAND ----------

import requests
import json

def check_mcp_server(name: str, url: str) -> bool:
    """Makes a JSON-RPC tools/list call to confirm the MCP server responds."""
    try:
        token   = ws.config.token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        resp    = requests.post(url, headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            tools = resp.json().get("result", {}).get("tools", [])
            print(f"  OK    {name}")
            print(f"        Tools : {[t['name'] for t in tools]}")
            return True
        else:
            print(f"  WARN  {name} — HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  FAIL  {name} — {e}")
        return False


print("MCP server reachability check")
print("=" * 60)

servers_to_check = [
    ("UC Functions (aemo schema)",
     f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"),
]

if GENIE_SPACE_ID != "":
    servers_to_check.append(
        ("Genie Space (AEMO NEM Operations)",
         f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}")
    )
else:
    print("  SKIP  Genie Space — GENIE_SPACE_ID not set")

vs_parts = VS_INDEX_NAME.split(".")
servers_to_check.append(
    ("Vector Search (market notices)",
     f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}")
)

print()
results = [check_mcp_server(name, url) for name, url in servers_to_check]
print()
print("=" * 60)
print(f"Reachable: {sum(results)}/{len(results)} MCP servers")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MCP server reachability check
# MAGIC ============================================================
# MAGIC
# MAGIC   OK    UC Functions (aemo schema)
# MAGIC         Tools : ['workshop_au__aemo__calculate_peak_demand',
# MAGIC                  'workshop_au__aemo__get_region_summary',
# MAGIC                  'workshop_au__aemo__lookup_duid_info']
# MAGIC
# MAGIC   OK    Genie Space (AEMO NEM Operations)
# MAGIC         Tools : ['ask_aemo_nem_operations']
# MAGIC
# MAGIC   OK    Vector Search (market notices)
# MAGIC         Tools : ['search_aemo_market_notices_index']
# MAGIC
# MAGIC ============================================================
# MAGIC Reachable: 3/3 MCP servers
# MAGIC ```
# MAGIC
# MAGIC | Error | Fix |
# MAGIC |-------|-----|
# MAGIC | HTTP 401 | Re-run `ws = WorkspaceClient()` |
# MAGIC | HTTP 404 | Check catalog/schema spelling or Genie Space ID |
# MAGIC | HTTP 403 | Check UC EXECUTE grant on functions; CAN_USE on Genie Space |
# MAGIC | Timeout | VS endpoint offline — re-run setup script, wait ~5 min |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.7 — Persist configuration for Labs 02 and 03

# COMMAND ----------

import json
from pathlib import Path

config = {
    "HOST":           HOST,
    "CATALOG":        CATALOG,
    "SCHEMA_AEMO":    SCHEMA_AEMO,
    "PT_ENDPOINT":    PT_ENDPOINT,
    "GENIE_SPACE_ID": GENIE_SPACE_ID,
    "VS_INDEX_NAME":  VS_INDEX_NAME,
}

config_path = Path("/tmp/workshop2c_config.json")
config_path.write_text(json.dumps(config, indent=2))

print(f"Configuration saved to {config_path}")
print()
print(json.dumps(config, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Configuration saved to /tmp/workshop2c_config.json
# MAGIC
# MAGIC {
# MAGIC   "HOST": "https://adb-1234567890123456.7.azuredatabricks.net",
# MAGIC   "CATALOG": "workshop_au",
# MAGIC   "SCHEMA_AEMO": "aemo",
# MAGIC   "PT_ENDPOINT": "au_east_llm_inregion",
# MAGIC   "GENIE_SPACE_ID": "01jxyz123abc456def789",
# MAGIC   "VS_INDEX_NAME": "workshop_au.aemo.aemo_market_notices_index"
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC Note: `/tmp/` is local to the cluster driver. If you switch clusters between labs, re-run this notebook to regenerate the config file.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Lab 01 complete</strong><br>
# MAGIC   You explored the AEMO Operations Agent architecture, navigated the AI Gateway MCPs tab,
# MAGIC   located your Genie Space ID and Vector Search index, installed packages, verified auth,
# MAGIC   and confirmed all three MCP servers are reachable. Lab 02 builds on this with hands-on MCP client calls.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lab 01 — Review questions
# MAGIC
# MAGIC 1. For the question *"Show me market notices mentioning LOR events in VIC last week"*, which MCP server type should the LLM use, and why not the others?
# MAGIC
# MAGIC 2. A UC function is named `workshop_au.aemo.calculate_peak_demand`. What is its MCP tool name?
# MAGIC
# MAGIC 3. Can you connect a local VS Code to the same Databricks MCP servers used in the notebook? What credential is needed?
# MAGIC
# MAGIC 4. Why do Databricks MCP endpoints satisfy the AEMO data residency requirement?
# MAGIC
# MAGIC 5. The Genie MCP server exposes exactly 1 tool; UC Functions MCP exposes N tools (one per function). What implication does this have for the 20-tool agent limit?
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Continue to Lab 02: Connecting to Databricks MCP Servers**

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 01 Complete</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 0.95em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Lab</th>
# MAGIC       <th style="text-align: left; padding: 6px 10px;">What you build</th>
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Status</th>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 01 (this lab)</td>
# MAGIC       <td style="padding: 5px 10px;">Architecture understanding, environment setup</td>
# MAGIC       <td style="padding: 5px 10px;">Complete ✅</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 02</td>
# MAGIC       <td style="padding: 5px 10px;">Low-level MCP client, discover + call each server</td>
# MAGIC       <td style="padding: 5px 10px;">Next →</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 5px 10px;">Lab 03</td>
# MAGIC       <td style="padding: 5px 10px;">Full ReAct agent, 4 AEMO test questions, MLflow traces</td>
# MAGIC       <td style="padding: 5px 10px;">After Lab 02</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC </div>
