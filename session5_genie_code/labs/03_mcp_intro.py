# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 28px 32px; border-radius: 10px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 2em; font-family: 'DM Sans', sans-serif;">
# MAGIC     Lab 03: MCP Introduction
# MAGIC   </h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 1em;">
# MAGIC     Session 5: Extending Genie Code — AEMO Workshop · Australia East
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Duration</strong><br>10 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01 and 02 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All MCP servers: AU East
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC ### What you will do
# MAGIC
# MAGIC | Step | Topic | Time |
# MAGIC |------|-------|------|
# MAGIC | 1 | What MCP is — the USB-C analogy | 3 min |
# MAGIC | 2 | Three in-region Databricks MCP servers | 3 min |
# MAGIC | 3 | Quick demo — list tools on a UC Functions MCP server | 4 min |
# MAGIC
# MAGIC > **Note:** This lab is a conceptual introduction and a single tool-discovery demo.
# MAGIC > For hands-on agent building with MCP, see Session 4 (MCP Agents workshop).

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — What Is MCP?
# MAGIC
# MAGIC **Model Context Protocol (MCP)** is an open standard that connects AI agents to data sources and tools
# MAGIC using a single, consistent interface. Anthropic published the spec in late 2024; it is now adopted
# MAGIC across Claude, Genie Code, VS Code, and dozens of third-party tools.
# MAGIC
# MAGIC ### The USB-C analogy
# MAGIC
# MAGIC Before USB-C, every device had a different cable — and you needed to know in advance what your device expected.
# MAGIC MCP is to AI agents what USB-C is to devices: **one standard plug that works everywhere**.
# MAGIC
# MAGIC ```
# MAGIC  Without MCP                          With MCP
# MAGIC ┌─────────────────────────────┐      ┌─────────────────────────────┐
# MAGIC │ Agent A ─────► Custom SDK   │      │  Agent A ─────────┐         │
# MAGIC │ Agent B ─────► REST wrapper │      │  Agent B ─────────┼──► MCP  │
# MAGIC │ Agent C ─────► Bespoke auth │      │  Agent C ─────────┘   Server│
# MAGIC │ (each connection unique)    │      │  (one interface — any agent)│
# MAGIC └─────────────────────────────┘      └─────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### What MCP gives an AI agent
# MAGIC
# MAGIC | Capability | What the agent can do |
# MAGIC |------------|----------------------|
# MAGIC | `tools/list` | Discover what functions are available |
# MAGIC | `tools/call` | Execute a specific function with arguments |
# MAGIC | `resources/list` | Discover data resources (files, tables) |
# MAGIC | `resources/read` | Read a specific resource |
# MAGIC
# MAGIC An MCP server exposes these four endpoints over HTTP + SSE (Server-Sent Events).
# MAGIC The agent negotiates which tools exist, decides which to call, and passes arguments — without any custom integration code per data source.
# MAGIC
# MAGIC ### Why it matters for AEMO
# MAGIC
# MAGIC - You register UC functions once → they are immediately available to **any** MCP-compatible agent
# MAGIC - The Genie Space you created in Session 2 is **already an MCP server** — no extra code needed
# MAGIC - Any future AI tool that supports MCP can reach your AEMO data without a new integration

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Three In-Region Databricks MCP Servers
# MAGIC
# MAGIC Databricks exposes three MCP server types. All endpoints use the pattern:
# MAGIC `https://{workspace-host}/api/2.0/mcp/...`
# MAGIC
# MAGIC All three are in-region for **Azure Australia East** — no data leaves the region.
# MAGIC
# MAGIC | MCP Server | URL pattern | What it exposes |
# MAGIC |------------|-------------|-----------------|
# MAGIC | **UC Functions** | `/api/2.0/mcp/functions/{catalog}/{schema}` | All Python/SQL functions in a UC schema as callable tools |
# MAGIC | **Genie Space** | `/api/2.0/mcp/genie/{space_id}` | One `ask_question` NL-to-SQL tool for a specific Genie Space |
# MAGIC | **Vector Search** | `/api/2.0/mcp/vector-search/{catalog}/{schema}/{index}` | One semantic similarity search tool over a VS index |
# MAGIC
# MAGIC ### When to use each
# MAGIC
# MAGIC | Your goal | Use this MCP server |
# MAGIC |-----------|---------------------|
# MAGIC | Run a calculation (SAIDI, peak demand, data quality check) | UC Functions |
# MAGIC | Let an agent query structured tables in plain English | Genie Space |
# MAGIC | Let an agent search documents, policies, or unstructured content | Vector Search |
# MAGIC
# MAGIC ### How they relate to what you built today
# MAGIC
# MAGIC ```
# MAGIC  Lab 01 — Custom Instructions                 →  every conversation
# MAGIC  Lab 02 — Skills                              →  on-demand reference
# MAGIC  Lab 03 — MCP: UC Functions / Genie / VS      →  executable tools + live data
# MAGIC
# MAGIC  Skills inform the agent WHAT to do.
# MAGIC  MCP tools give the agent something to DO IT WITH.
# MAGIC ```
# MAGIC
# MAGIC ### Authentication
# MAGIC
# MAGIC MCP servers use the same OAuth token as the rest of Databricks.
# MAGIC `DatabricksMCPClient` handles token refresh automatically.
# MAGIC UC Functions: callers need `EXECUTE` privilege on the function — the same governance that applies in SQL.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Quick Demo: List Tools on a UC Functions MCP Server
# MAGIC
# MAGIC The cell below connects to the UC Functions MCP server for the `workshop_au.aemo` schema
# MAGIC and prints every tool (UC function) that the server exposes.
# MAGIC
# MAGIC This is the same list that a LangGraph or OpenAI Agents SDK agent would receive when it
# MAGIC calls `tools/list` — you are seeing exactly what the AI sees.

# COMMAND ----------

%pip install databricks-mcp --quiet
dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog", "workshop_au", "Catalog name")
dbutils.widgets.text("schema",  "aemo",        "Schema name")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA  = dbutils.widgets.get("schema")

from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
HOST = w.config.host.rstrip("/")

print(f"Workspace: {HOST}")
print(f"Schema   : {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Connect and list tools

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient

url    = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}"
client = DatabricksMCPClient(url, w)

print(f"Connecting to MCP server: {url}\n")

tools = client.list_tools()

if not tools:
    print("No tools found in this schema.")
    print("This is expected if workshop_au.aemo has no UC functions registered yet.")
    print("\nIf you completed the full skills lab and want to see tools, try:")
    print(f"  url = f\"{HOST}/api/2.0/mcp/functions/workshop_au/workshop_lab\"")
else:
    print(f"Found {len(tools)} tool(s) in {CATALOG}.{SCHEMA}:\n")
    for tool in tools:
        print(f"  Tool: {tool.name}")
        if hasattr(tool, "description") and tool.description:
            print(f"  Desc: {tool.description[:100]}...")
        print()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — What the output means
# MAGIC
# MAGIC Each entry is a UC function registered in the schema. The name you see here is the MCP tool name —
# MAGIC Databricks converts dots to double underscores:
# MAGIC
# MAGIC ```
# MAGIC UC function:  workshop_au.aemo.calculate_peak_demand
# MAGIC MCP tool name: workshop_au__aemo__calculate_peak_demand
# MAGIC ```
# MAGIC
# MAGIC When an agent receives this list, it reads each `description` field to decide when to call which tool.
# MAGIC This is why the `COMMENT` you write in `CREATE FUNCTION ... COMMENT '...'` is so important —
# MAGIC it becomes the agent's tool selection signal.
# MAGIC
# MAGIC **Good COMMENT format:**
# MAGIC ```sql
# MAGIC COMMENT 'Calculate SAIDI for a network zone over a date range.
# MAGIC Returns JSON with saidi_minutes and compliance_status vs AER target.
# MAGIC Use this when asked about reliability metrics, SAIDI, outage performance,
# MAGIC or AER compliance for a specific region or network zone.'
# MAGIC ```
# MAGIC
# MAGIC The phrase "Use this when asked about..." directly guides the LLM's tool selection decision.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — The Genie Space MCP endpoint
# MAGIC
# MAGIC If you created a Genie Space in Session 2, its MCP endpoint is already live.
# MAGIC Replace `YOUR_GENIE_SPACE_ID` with your actual space ID to see its single tool:

# COMMAND ----------

# Optional — replace with your Genie Space ID to verify its MCP endpoint
GENIE_SPACE_ID = ""  # e.g. "01ef1234abcd5678ef90"

if GENIE_SPACE_ID:
    genie_url    = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
    genie_client = DatabricksMCPClient(genie_url, w)
    genie_tools  = genie_client.list_tools()

    print(f"Genie Space MCP endpoint: {genie_url}")
    print(f"Tools exposed: {len(genie_tools)}\n")
    for tool in genie_tools:
        print(f"  Tool: {tool.name}")
        if hasattr(tool, "description") and tool.description:
            print(f"  Desc: {tool.description}")
else:
    print("GENIE_SPACE_ID is empty — set it to verify your Genie Space MCP endpoint.")
    print("\nA Genie Space MCP server always exposes exactly one tool:")
    print("  Tool name : ask_question (or similar NL-to-SQL wrapper)")
    print("  Input     : question (STRING) — the natural language query")
    print("  Output    : query results as structured JSON")
    print("\nThis is how a LangGraph agent would call your Genie Space as one node in a pipeline.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — What Comes Next
# MAGIC
# MAGIC This lab introduced MCP at the conceptual level. For the hands-on agent layer:
# MAGIC
# MAGIC | Session | What you build |
# MAGIC |---------|---------------|
# MAGIC | Session 4 — MCP Agents | Multi-tool LangGraph agent connecting UC Functions + Genie Space + Vector Search |
# MAGIC | Session 4 — MCP Agents | Deploy agent as a Databricks App with OAuth authentication |
# MAGIC | Session 4 — MCP Agents | Monitoring, tracing, and governance via MLflow |
# MAGIC
# MAGIC ### How the three labs in this session fit together
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────────────────┐
# MAGIC │  Session 5: Extending Genie Code                                         │
# MAGIC │                                                                          │
# MAGIC │  Lab 01 — Custom Instructions                                            │
# MAGIC │  "What Genie knows about your domain by default"                         │
# MAGIC │  → AEMO terminology, region codes, table paths, regulatory context       │
# MAGIC │  → Personal: /Users/{email}/.assistant_instructions.md                  │
# MAGIC │                                                                          │
# MAGIC │  Lab 02 — Skills                                                         │
# MAGIC │  "Deep reference loaded on demand"                                       │
# MAGIC │  → energy-analytics: SAIDI/SAIFI formulas, SQL patterns                 │
# MAGIC │  → regulatory-compliance: SOCI Act, Privacy Act, STPIS                  │
# MAGIC │  → genie-space-creator: REST API walkthrough, golden queries             │
# MAGIC │  → Auto-loaded by keyword match or @skill-name invocation                │
# MAGIC │                                                                          │
# MAGIC │  Lab 03 — MCP (this lab)                                                 │
# MAGIC │  "Executable tools — real code runs against real data"                   │
# MAGIC │  → UC Functions MCP: Python/SQL functions as callable tools              │
# MAGIC │  → Genie Space MCP: NL-to-SQL for any agent framework                   │
# MAGIC │  → Vector Search MCP: semantic search over documents                    │
# MAGIC │  → All in-region (Azure Australia East)                                  │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 20px 24px; border-radius: 10px; margin-top: 24px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 03 Complete — Session 5 Done</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; font-size: 0.95em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold; width: 35%;">MCP concept</td>
# MAGIC       <td style="padding: 6px 10px;">Open standard — any MCP-compatible agent can reach your AEMO tools with no custom integration</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Three in-region servers</td>
# MAGIC       <td style="padding: 6px 10px;">UC Functions (calculations) · Genie Space (NL-to-SQL) · Vector Search (documents)</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Tool discovery</td>
# MAGIC       <td style="padding: 6px 10px;"><code style="color:#FF6B35;">DatabricksMCPClient.list_tools()</code> — the same list an agent sees before deciding what to call</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Next session</td>
# MAGIC       <td style="padding: 6px 10px;">Session 4 — build a full multi-tool LangGraph agent with UC Functions + Genie + Vector Search</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC </div>
