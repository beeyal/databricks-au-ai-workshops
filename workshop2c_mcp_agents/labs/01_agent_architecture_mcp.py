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
# MAGIC     Understand the AEMO Operations Agent we build across this workshop, navigate the MCP ecosystem,
# MAGIC     and verify your environment before writing a single line of agent code.
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
# MAGIC | 1 | What We're Building | The AEMO Operations Agent — architecture walkthrough, UI exploration | 10 min |
# MAGIC | 2 | The MCP Ecosystem in Databricks | Navigate AI Gateway MCPs tab, understand server types and URLs | 10 min |
# MAGIC | 3 | Package Setup & Authentication | Install packages, verify workspace connection, confirm MCP servers reachable | 10 min |
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
# MAGIC | **No vendor lock-in** | MCP is an open standard (Anthropic, 2024) — the client library is client-side only |
# MAGIC | **Consistent auth** | Same Databricks OAuth/PAT as any other workspace API — no new secrets to manage |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — What We're Building (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — The AEMO Operations Agent
# MAGIC
# MAGIC Over Labs 01–03 you will build a production-grade agent that answers questions about the
# MAGIC National Electricity Market (NEM). Here is what the finished agent looks like:
# MAGIC
# MAGIC ```
# MAGIC ┌─── AEMO Operations Agent ─────────────────────────────────────────────────┐
# MAGIC │                                                                            │
# MAGIC │  User: "Were there any price spikes in VIC yesterday and what             │
# MAGIC │         generators were dispatched during those events?"                  │
# MAGIC │                                                                            │
# MAGIC │  Agent thinks:                                                             │
# MAGIC │  Step 1: Query spot_prices via Genie MCP   → find spikes above threshold  │
# MAGIC │  Step 2: Get dispatch data via Genie MCP   → find generators dispatched   │
# MAGIC │  Step 3: Calculate constraint violations via UC Function MCP              │
# MAGIC │  Step 4: Search market notices via Vector Search MCP                      │
# MAGIC │  Step 5: Synthesise results  → answer with data sources cited             │
# MAGIC │                                                                            │
# MAGIC │  All data stays in AU East ✅    All calls logged in audit ✅             │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **What makes this different from a simple RAG chatbot?**
# MAGIC
# MAGIC A RAG chatbot retrieves pre-embedded text. This agent:
# MAGIC - Runs **live SQL** against NEM tables via Genie (real-time data, not embeddings)
# MAGIC - Calls **Python functions** registered in Unity Catalog for calculations
# MAGIC - Performs **semantic search** across market notices and policy documents
# MAGIC - **Chains results** across tools — one tool's output feeds the next question
# MAGIC - Leaves a full **audit trail** of every data access in `system.access.audit`

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — The data domain: AEMO NEM operations
# MAGIC
# MAGIC All labs use Australian energy data. Here is the domain context you need:
# MAGIC
# MAGIC | Term | Meaning | Example |
# MAGIC |------|---------|---------|
# MAGIC | **NEM** | National Electricity Market — the interconnected grid covering QLD, NSW, VIC, SA, TAS | — |
# MAGIC | **Region** | NEM dispatch region code | `VIC1`, `NSW1`, `QLD1`, `SA1`, `TAS1` |
# MAGIC | **Spot price** | 5-minute dispatch price in $/MWh | `$14,000/MWh` (price cap) |
# MAGIC | **Price spike** | Interval where spot price exceeds a threshold | Above `$300/MWh` = volatile |
# MAGIC | **DUID** | Dispatchable Unit Identifier — unique code for a generator | `LOYB1` = Loy Yang B Unit 1 |
# MAGIC | **Dispatch** | When AEMO instructs a generator to produce at a target MW level | 150 MW dispatch |
# MAGIC | **LOR** | Lack of Reserve — system condition where reserve margin is too low | LOR3 = emergency |
# MAGIC | **Market notice** | Official AEMO bulletin about system conditions | "LOR2 declared VIC 14:30" |
# MAGIC
# MAGIC You do not need to be an energy expert. The agent's system prompt provides this context
# MAGIC to the LLM — you will write it in Lab 03.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Three MCP servers, three tool types
# MAGIC
# MAGIC The agent connects to three Databricks MCP servers simultaneously:
# MAGIC
# MAGIC ```
# MAGIC ┌─── AEMO Operations Agent (LangGraph ReAct) ───────────────────────────────┐
# MAGIC │                                                                            │
# MAGIC │         User question                                                      │
# MAGIC │              │                                                             │
# MAGIC │              ▼                                                             │
# MAGIC │   Claude Sonnet 4.6  (Provisioned Throughput endpoint — AU East)          │
# MAGIC │              │                                                             │
# MAGIC │    ┌─────────┼──────────────────┐                                         │
# MAGIC │    ▼         ▼                  ▼                                         │
# MAGIC │                                                                            │
# MAGIC │  Genie MCP           UC Functions MCP         Vector Search MCP           │
# MAGIC │  ──────────────       ─────────────────        ─────────────────          │
# MAGIC │  NL → SQL over        Python functions         Semantic search            │
# MAGIC │  NEM dispatch &       registered in UC:        over market notices        │
# MAGIC │  pricing tables       • calculate_peak_demand  & policy docs              │
# MAGIC │                       • get_region_summary                                │
# MAGIC │  Tool: ask_genie      • lookup_duid_info        Tool: search              │
# MAGIC │                       Tools: 3 UC functions                               │
# MAGIC │                                                                            │
# MAGIC │  /api/2.0/mcp/        /api/2.0/mcp/functions/  /api/2.0/mcp/             │
# MAGIC │  genie/{id}           workshop_au/aemo          vector-search/...         │
# MAGIC │                                                                            │
# MAGIC │              All endpoints: Australia East ✅                             │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Why use three server types instead of one?**
# MAGIC
# MAGIC | Server type | Strength | Use when |
# MAGIC |-------------|----------|----------|
# MAGIC | **Genie MCP** | NL → SQL translation with business context | User asks a data question in plain English |
# MAGIC | **UC Functions MCP** | Deterministic Python logic, regulatory calculations | You need a precise computed result |
# MAGIC | **Vector Search MCP** | Fuzzy semantic similarity search | User asks about documents, notices, policies |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Tool selection: how the LLM decides which MCP server to call
# MAGIC
# MAGIC The LLM selects tools based on **tool descriptions**, not hardcoded routing logic.
# MAGIC Each MCP server exposes its tools with a name and description. The LLM reads these at
# MAGIC inference time and picks the best tool for the question.
# MAGIC
# MAGIC This means your tool descriptions are load-bearing. Compare:
# MAGIC
# MAGIC ```
# MAGIC BAD  description: "Gets spot price data"
# MAGIC
# MAGIC GOOD description: "Ask a natural language question about NEM spot prices, dispatch schedules,
# MAGIC                    or generator output. Use for questions like 'what was the average VIC
# MAGIC                    price yesterday', 'show me dispatch intervals above $300', or 'which
# MAGIC                    generators ran in SA during the last price spike'. Returns a data table
# MAGIC                    and a plain-English summary. Do NOT use for document search or
# MAGIC                    regulatory calculations — use the other tools for those."
# MAGIC ```
# MAGIC
# MAGIC The "GOOD" version tells the LLM:
# MAGIC - What kinds of questions this tool answers (positive examples)
# MAGIC - What it does NOT answer (negative examples — prevents wrong routing)
# MAGIC - What format the result comes back in
# MAGIC
# MAGIC For Databricks MCP servers, Genie's tool description comes from your Genie Space name
# MAGIC and description. UC function descriptions come from the `COMMENT` on each function.
# MAGIC Vector Search descriptions come from the index name. You control all three.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — UI Exploration 1: Navigate the Genie Section (3 min)
# MAGIC </div>
# MAGIC
# MAGIC Open the Genie section in your workspace. This is where the Genie MCP server is backed.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Left sidebar → Genie (diamond/sparkle icon)
# MAGIC
# MAGIC What you should see:
# MAGIC ┌─── Genie ────────────────────────────────────────────────────────────────┐
# MAGIC │  [+ New Space]                                          Search [      ]  │
# MAGIC │  ──────────────────────────────────────────────────────────────────────  │
# MAGIC │                                                                          │
# MAGIC │  My spaces                                                               │
# MAGIC │  ┌──────────────────────────────────────────────────────────────┐        │
# MAGIC │  │  AEMO NEM Operations                                         │        │
# MAGIC │  │  "NEM dispatch and spot price data for AEMO operations..."   │        │
# MAGIC │  │  Created by you · 3 tables                                   │        │
# MAGIC │  └──────────────────────────────────────────────────────────────┘        │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC If you see "AEMO NEM Operations" — great, the setup script ran successfully.
# MAGIC If you see no spaces — run setup/00_workspace_setup.py first, then return here.
# MAGIC ```
# MAGIC
# MAGIC **Click on the "AEMO NEM Operations" space, then click "Configure".**
# MAGIC Look at the Instructions tab — this is the system prompt that shapes every Genie conversation.
# MAGIC You wrote something similar in Workshop 2b. In this workshop, you will call it via MCP
# MAGIC from an agent instead of from the Genie chat UI.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — The MCP Ecosystem in Databricks (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — The 5 Databricks MCP server types
# MAGIC
# MAGIC Databricks exposes five categories of MCP server, all on the pattern
# MAGIC `https://<workspace>/api/2.0/mcp/...`
# MAGIC
# MAGIC | MCP Server type | URL pattern | What it exposes | Tool count |
# MAGIC |----------------|-------------|-----------------|-----------|
# MAGIC | **UC Functions — schema** | `.../mcp/functions/{catalog}/{schema}` | All UC functions in a schema | One per function |
# MAGIC | **UC Functions — single** | `.../mcp/functions/{catalog}/{schema}/{function}` | A single named function | 1 |
# MAGIC | **Genie Space** | `.../mcp/genie/{genie_space_id}` | NL-to-SQL tool backed by a Genie Space | 1 |
# MAGIC | **Vector Search** | `.../mcp/vector-search/{catalog}/{schema}/{index}` | Semantic search over a VS index | 1 |
# MAGIC | **Databricks SQL** | `.../mcp/sql` | Direct SQL execution | 1 |
# MAGIC
# MAGIC All five types are **in-region for Australia East**. No query leaves your workspace region.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 2.2 — Tool naming convention for UC Functions
# MAGIC
# MAGIC UC function names use **double-underscore** (`__`) as separators in MCP tool names:
# MAGIC
# MAGIC ```
# MAGIC  UC function:    workshop_au.aemo.calculate_peak_demand
# MAGIC                     │          │          │
# MAGIC                  catalog    schema    function_name
# MAGIC                     │          │          │
# MAGIC                     └──────────┴──────────┘
# MAGIC                             joined with __
# MAGIC                             │
# MAGIC  MCP tool name:  workshop_au__aemo__calculate_peak_demand
# MAGIC ```
# MAGIC
# MAGIC This matters when you inspect tool call traces in MLflow or write routing logic in tests.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — UI Exploration 2: The AI Gateway MCPs Tab (5 min)
# MAGIC </div>
# MAGIC
# MAGIC The AI Gateway MCPs tab shows every MCP endpoint registered in your workspace.
# MAGIC This is your control plane for MCP servers.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar)
# MAGIC           → Serving
# MAGIC           → AI Gateway tab (horizontal nav at top)
# MAGIC           → MCPs sub-tab
# MAGIC
# MAGIC What you will see:
# MAGIC
# MAGIC ┌─── AI Gateway → MCPs ──────────────────────────────────────────────────────┐
# MAGIC │  Available MCP Servers                              [+ Add external MCP]   │
# MAGIC │  ──────────────────────────────────────────────────────────────────────── │
# MAGIC │                                                                             │
# MAGIC │  ● workshop_au.aemo.*  (UC Functions)                                      │
# MAGIC │    URL: https://{workspace}/api/2.0/mcp/functions/workshop_au/aemo         │
# MAGIC │    Tools: 3  (calculate_peak_demand, get_region_summary, lookup_duid_info) │
# MAGIC │    Status: Active                                   [Copy URL]  [View]      │
# MAGIC │                                                                             │
# MAGIC │  ● AEMO NEM Operations  (Genie Space)                                      │
# MAGIC │    URL: https://{workspace}/api/2.0/mcp/genie/01jxyz...                   │
# MAGIC │    Tools: 1  (ask_aemo_nem_operations)                                     │
# MAGIC │    Status: Active                                   [Copy URL]  [View]      │
# MAGIC │                                                                             │
# MAGIC │  ● aemo_market_notices_index  (Vector Search)                              │
# MAGIC │    URL: https://{workspace}/api/2.0/mcp/vector-search/                    │
# MAGIC │         workshop_au/aemo/aemo_market_notices_index                         │
# MAGIC │    Tools: 1  (search_aemo_market_notices_index)                            │
# MAGIC │    Status: Active                                   [Copy URL]  [View]      │
# MAGIC │                                                                             │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Actions to take right now:
# MAGIC   1. Click [Copy URL] next to each server — note the URL pattern
# MAGIC   2. Click [View] on the UC Functions server — see the 3 tool names and schemas
# MAGIC   3. Click [View] on the Genie server — see that it has exactly 1 tool
# MAGIC ```
# MAGIC
# MAGIC **If you do not see MCP servers listed:** the workspace setup script may not have run.
# MAGIC See `setup/00_workspace_setup.py`. The MCPs tab may also be labelled differently in your
# MAGIC workspace version — look for "MCP" or "Model Context Protocol" in the AI Gateway navigation.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Finding your Genie Space ID
# MAGIC
# MAGIC The Genie MCP server URL requires your Genie Space ID. You need this in Labs 02 and 03.
# MAGIC There are two ways to find it:
# MAGIC
# MAGIC **Method A — Browser URL bar:**
# MAGIC ```
# MAGIC Navigate: Left sidebar → Genie → click "AEMO NEM Operations"
# MAGIC
# MAGIC Look at the URL bar:
# MAGIC ┌─── Browser URL ──────────────────────────────────────────────────────────┐
# MAGIC │  https://adb-1234567890.7.azuredatabricks.net/genie/rooms/01jxyz123abc  │
# MAGIC │                                                            ↑             │
# MAGIC │                                          This is your GENIE_SPACE_ID    │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Copy everything after /genie/rooms/
# MAGIC Example: 01jxyz123abc456def789
# MAGIC ```
# MAGIC
# MAGIC **Method B — AI Gateway MCPs tab:**
# MAGIC ```
# MAGIC AI Gateway → MCPs → click the Genie server row
# MAGIC The URL shown ends with /mcp/genie/{GENIE_SPACE_ID}
# MAGIC The last path segment is your Genie Space ID.
# MAGIC ```
# MAGIC
# MAGIC Write your Space ID here (you will paste it into the widget in Labs 02 and 03):
# MAGIC
# MAGIC ```
# MAGIC My GENIE_SPACE_ID = _________________________________
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Finding your Vector Search index name
# MAGIC
# MAGIC The Vector Search MCP server URL uses a 3-part index name: `catalog.schema.index_name`.
# MAGIC
# MAGIC **Method A — Catalog Explorer:**
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog (grid icon)
# MAGIC
# MAGIC ┌─── Catalog Explorer ──────────────────────────────────────────────────────┐
# MAGIC │  workshop_au  (catalog)                                                   │
# MAGIC │    aemo  (schema)                                                         │
# MAGIC │      Tables                                                               │
# MAGIC │        spot_prices                                                        │
# MAGIC │        dispatch_intervals                                                 │
# MAGIC │        market_notices                                                     │
# MAGIC │      Vector Search Indexes          ← expand this                        │
# MAGIC │        aemo_market_notices_index    ← full name below                    │
# MAGIC │          Full name: workshop_au.aemo.aemo_market_notices_index            │
# MAGIC └───────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Method B — AI Gateway MCPs tab:**
# MAGIC ```
# MAGIC AI Gateway → MCPs → click the Vector Search server row
# MAGIC The URL ends with /mcp/vector-search/{catalog}/{schema}/{index}
# MAGIC Read off the last three path segments.
# MAGIC ```
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
# MAGIC Navigate: Left sidebar → Catalog → workshop_au → aemo → Functions
# MAGIC
# MAGIC ┌─── Catalog Explorer ──────────────────────────────────────────────────────┐
# MAGIC │  workshop_au  (catalog)                                                   │
# MAGIC │    aemo  (schema)                                                         │
# MAGIC │      Functions                      ← expand this                        │
# MAGIC │        calculate_peak_demand                                              │
# MAGIC │          • Signature: (region STRING, date STRING) → STRING              │
# MAGIC │          • Comment:   "Calculate peak spot price and dispatch..."         │
# MAGIC │        get_region_summary                                                 │
# MAGIC │        lookup_duid_info                                                   │
# MAGIC └───────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Note the COMMENT on each function — this becomes the MCP tool description.
# MAGIC The LLM reads these descriptions when deciding which tool to call.
# MAGIC Click on calculate_peak_demand and read its comment — is it descriptive enough?
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Section 2 complete</strong><br>
# MAGIC   You have located all three MCP servers in the UI, found your Genie Space ID, Vector Search
# MAGIC   index name, and UC function schema. You know where the MCP URL for each server comes from.
# MAGIC   Section 3 verifies your Python environment and tests that the servers are reachable.
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
# MAGIC There are three separate packages for different integration patterns.
# MAGIC Do **not** mix them — they serve distinct purposes:
# MAGIC
# MAGIC | Package | What it gives you | Use for |
# MAGIC |---------|-------------------|---------|
# MAGIC | `databricks-mcp` | Low-level `DatabricksMCPClient` | Tool discovery, direct MCP calls |
# MAGIC | `databricks-langchain` | `DatabricksMCPServer`, `DatabricksMultiServerMCPClient`, `ChatDatabricks` | LangGraph agents (Labs 02 and 03) |
# MAGIC | `databricks-openai` | `McpServer` for the OpenAI Agents SDK | OpenAI Agents SDK pattern (bonus) |
# MAGIC
# MAGIC We install all three now. In Databricks notebooks, `pip install` runs on the cluster
# MAGIC driver. After the install we call `dbutils.library.restartPython()` to ensure the new
# MAGIC packages are importable.

# COMMAND ----------

%pip install databricks-mcp databricks-langchain databricks-openai mlflow langchain-core langgraph --quiet
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Python interpreter restarted.
# MAGIC ```
# MAGIC
# MAGIC The restart is normal — it reloads the Python environment with the new packages.
# MAGIC All subsequent cells run in the fresh environment.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Workshop widgets
# MAGIC
# MAGIC <div style="background: #2E4057; color: white; padding: 12px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖱️ Before We Code — Check your workspace URL
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Look at your browser address bar right now:
# MAGIC
# MAGIC ┌─── Browser URL ──────────────────────────────────────────────────────────┐
# MAGIC │  https://adb-1234567890123456.7.azuredatabricks.net/...                 │
# MAGIC │  ↑ This is your workspace HOST                                           │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC The HOST value appears in every MCP endpoint URL.
# MAGIC You will also need it for the Claude Desktop config in the Bonus section of Lab 03.
# MAGIC ```
# MAGIC
# MAGIC Fill in the widgets below with your environment values, then run the cell.

# COMMAND ----------

dbutils.widgets.text("catalog",         "workshop_au",               "Catalog name")
dbutils.widgets.text("schema_aemo",     "aemo",                      "AEMO schema name")
dbutils.widgets.text("pt_endpoint",     "au_east_llm_inregion",      "PT endpoint name")
dbutils.widgets.text("genie_space_id",  "FILL_IN",                   "Genie Space ID")
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

if GENIE_SPACE_ID == "FILL_IN":
    print("\nACTION REQUIRED: paste your Genie Space ID into the 'genie_space_id' widget above.")
    print("  → Navigate: Left sidebar → Genie → AEMO NEM Operations → copy ID from URL")

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
# MAGIC
# MAGIC If you see `FILL_IN` for Genie Space ID — follow the navigation in Section 2.3 above.
# MAGIC Labs 02 and 03 need a real Genie Space ID to test the Genie MCP server.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Verify package imports
# MAGIC
# MAGIC Run the imports and confirm there are no `ModuleNotFoundError` exceptions.
# MAGIC If any import fails, re-run the `%pip install` cell above.

# COMMAND ----------

# Verify all required packages are importable after the restart

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
# MAGIC ### 3.4 — Authentication: why `WorkspaceClient()` needs no arguments
# MAGIC
# MAGIC In Databricks notebooks, authentication is **automatic**. You do not manage tokens.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Authentication flow in Databricks notebooks ───────────────────────────┐
# MAGIC │                                                                            │
# MAGIC │  Your notebook runs inside a cluster attached to this workspace.          │
# MAGIC │                                                                            │
# MAGIC │  WorkspaceClient()  →  reads credentials from the cluster environment     │
# MAGIC │                         (injected by Databricks at cluster start)          │
# MAGIC │                                                                            │
# MAGIC │  DatabricksMCPClient(url, ws)  →  uses ws.config to get OAuth token       │
# MAGIC │                                    sends   Authorization: Bearer <token>   │
# MAGIC │                                    to the MCP server endpoint             │
# MAGIC │                                                                            │
# MAGIC │  DatabricksMCPServer(url=...) →  also uses WorkspaceClient internally    │
# MAGIC │                                                                            │
# MAGIC │  Result: zero token management in notebook code                           │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Outside notebooks (local IDE, Claude Desktop, CI/CD):
# MAGIC   - Use a Personal Access Token (PAT) from User Settings → Access Tokens
# MAGIC   - Store in ~/.databrickscfg or an environment variable DATABRICKS_TOKEN
# MAGIC   - Never commit PATs to git
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Verify connection and confirm your workspace identity

# COMMAND ----------

from databricks.sdk import WorkspaceClient

ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

me = ws.current_user.me()

print("Workspace connection verified.")
print()
print(f"  Host        : {HOST}")
print(f"  User        : {me.user_name}")
print(f"  Display name: {me.display_name}")
print(f"  User ID     : {me.id}")
print()

# Confirm the workspace is an Azure Databricks workspace in AU East
if "azuredatabricks.net" in HOST:
    print("  Cloud       : Azure Databricks")
elif "gcp.databricks.com" in HOST:
    print("  Cloud       : GCP Databricks")
elif "cloud.databricks.com" in HOST:
    print("  Cloud       : AWS Databricks")

# Check the current user can access the workshop catalog
try:
    tables = list(ws.tables.list(catalog_name=CATALOG, schema_name=SCHEMA_AEMO))
    print(f"  Catalog     : {CATALOG}.{SCHEMA_AEMO} — accessible ({len(tables)} tables visible)")
except Exception as e:
    print(f"  Catalog     : {CATALOG}.{SCHEMA_AEMO} — WARNING: {e}")
    print("  Check that the setup script ran and you have SELECT on the schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workspace connection verified.
# MAGIC
# MAGIC   Host        : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC   User        : you@yourcompany.com
# MAGIC   Display name: Your Name
# MAGIC   User ID     : 1234567
# MAGIC
# MAGIC   Cloud       : Azure Databricks
# MAGIC   Catalog     : workshop_au.aemo — accessible (3 tables visible)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Verify MCP server reachability
# MAGIC
# MAGIC Before running full agent code in Labs 02–03, confirm each MCP server responds.
# MAGIC This cell makes a lightweight `tools/list` HTTP call to each endpoint.

# COMMAND ----------

import requests
import json

def check_mcp_server(name: str, url: str) -> bool:
    """
    Makes a JSON-RPC tools/list call to an MCP server endpoint.
    Returns True if the server responds with a valid tools list.
    """
    try:
        # MCP protocol: POST with JSON-RPC initialize, then tools/list
        token = ws.config.token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
        # tools/list is a lightweight discovery call — no data is moved
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        resp = requests.post(url, headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            data        = resp.json()
            tools       = data.get("result", {}).get("tools", [])
            tool_names  = [t["name"] for t in tools]
            print(f"  OK    {name}")
            print(f"        URL   : {url}")
            print(f"        Tools : {tool_names}")
            return True
        else:
            print(f"  WARN  {name} — HTTP {resp.status_code}")
            print(f"        URL   : {url}")
            return False

    except Exception as e:
        print(f"  FAIL  {name} — {e}")
        print(f"        URL   : {url}")
        return False


print("MCP server reachability check")
print("=" * 60)

servers_to_check = [
    ("UC Functions (aemo schema)",
     f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"),
]

if GENIE_SPACE_ID != "FILL_IN":
    servers_to_check.append(
        ("Genie Space (AEMO NEM Operations)",
         f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}")
    )
else:
    print("  SKIP  Genie Space — GENIE_SPACE_ID not set (see widget above)")

# Vector Search URL uses slash-separated parts
vs_parts   = VS_INDEX_NAME.split(".")      # "catalog.schema.index" → ["catalog","schema","index"]
vs_url     = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"
servers_to_check.append(("Vector Search (market notices)", vs_url))

print()
results = []
for name, url in servers_to_check:
    ok = check_mcp_server(name, url)
    results.append(ok)
    print()

print("=" * 60)
ok_count = sum(results)
print(f"Reachable: {ok_count}/{len(results)} MCP servers")
if ok_count < len(results):
    print("Unreachable servers will be skipped or substituted in Labs 02–03.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MCP server reachability check
# MAGIC ============================================================
# MAGIC
# MAGIC   OK    UC Functions (aemo schema)
# MAGIC         URL   : https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/functions/workshop_au/aemo
# MAGIC         Tools : ['workshop_au__aemo__calculate_peak_demand',
# MAGIC                  'workshop_au__aemo__get_region_summary',
# MAGIC                  'workshop_au__aemo__lookup_duid_info']
# MAGIC
# MAGIC   OK    Genie Space (AEMO NEM Operations)
# MAGIC         URL   : https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/genie/01jxyz...
# MAGIC         Tools : ['ask_aemo_nem_operations']
# MAGIC
# MAGIC   OK    Vector Search (market notices)
# MAGIC         URL   : https://adb-xxxx.azuredatabricks.net/api/2.0/mcp/vector-search/...
# MAGIC         Tools : ['search_aemo_market_notices_index']
# MAGIC
# MAGIC ============================================================
# MAGIC Reachable: 3/3 MCP servers
# MAGIC ```
# MAGIC
# MAGIC **If a server shows WARN or FAIL:**
# MAGIC
# MAGIC | Error | Likely cause | Fix |
# MAGIC |-------|-------------|-----|
# MAGIC | HTTP 401 | Auth failed | Re-run `ws = WorkspaceClient()` in the config cell above |
# MAGIC | HTTP 404 | Wrong URL | Check catalog/schema spelling or Genie Space ID |
# MAGIC | HTTP 403 | Missing permission | Check UC EXECUTE grant on functions; CAN_USE on Genie Space |
# MAGIC | Connection timeout | VS endpoint offline | Re-run setup script; VS endpoints take ~5 min to start |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.7 — Persist configuration for Labs 02 and 03
# MAGIC
# MAGIC Save the verified configuration to a file so you do not need to re-enter values
# MAGIC when you open the next notebook. Labs 02 and 03 will load this file automatically.

# COMMAND ----------

import json
from pathlib import Path

config = {
    "HOST":          HOST,
    "CATALOG":       CATALOG,
    "SCHEMA_AEMO":   SCHEMA_AEMO,
    "PT_ENDPOINT":   PT_ENDPOINT,
    "GENIE_SPACE_ID": GENIE_SPACE_ID,
    "VS_INDEX_NAME": VS_INDEX_NAME,
}

config_path = Path("/tmp/workshop2c_config.json")
config_path.write_text(json.dumps(config, indent=2))

print(f"Configuration saved to {config_path}")
print()
print("Contents:")
print(json.dumps(config, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Configuration saved to /tmp/workshop2c_config.json
# MAGIC
# MAGIC Contents:
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
# MAGIC Note: `/tmp/` is local to the cluster driver. If you switch clusters between labs,
# MAGIC re-run this notebook to regenerate the config file, or re-enter values in the widgets.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Checkpoint — Lab 01 complete</strong><br>
# MAGIC   You have: explored the AEMO Operations Agent architecture, navigated the AI Gateway MCPs tab,
# MAGIC   located your Genie Space ID and Vector Search index name, installed packages, verified
# MAGIC   authentication, and confirmed all three MCP servers are reachable.
# MAGIC   Lab 02 builds on this foundation with hands-on MCP client calls.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lab 01 — Review questions
# MAGIC
# MAGIC Answer these before moving to Lab 02:
# MAGIC
# MAGIC 1. The AEMO Operations Agent uses three MCP server types. For the question
# MAGIC    *"Show me all market notices mentioning LOR events in VIC last week"*,
# MAGIC    which MCP server type should the LLM use, and why not the others?
# MAGIC
# MAGIC 2. A UC function is named `workshop_au.aemo.calculate_peak_demand`.
# MAGIC    What is its MCP tool name? Why does the naming convention matter?
# MAGIC
# MAGIC 3. A developer asks: "Can I connect my local VS Code to the same Databricks MCP servers
# MAGIC    we used in the notebook?"  What is the answer and what credential do they need?
# MAGIC
# MAGIC 4. Why do Databricks MCP endpoints satisfy the AEMO data residency requirement
# MAGIC    that no energy market data leaves Australia?
# MAGIC
# MAGIC 5. The Genie MCP server exposes exactly **1 tool** regardless of how many tables
# MAGIC    the Genie Space covers. The UC Functions MCP server exposes **N tools** (one per function).
# MAGIC    What implication does this have for the 20-tool agent limit?
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Continue to Lab 02: Connecting to Databricks MCP Servers**

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 01 Complete</h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 14px 0;">
# MAGIC     You have set the stage for the rest of Workshop 2c. Every subsequent lab builds directly
# MAGIC     on the architecture and configuration established here.
# MAGIC   </p>
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
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 0; font-size: 0.9em;">
# MAGIC     Data residency: All MCP endpoints used in this workshop run in Australia East.
# MAGIC     No AEMO data crosses a regional boundary at any point in the agent call chain.
# MAGIC   </p>
# MAGIC </div>
