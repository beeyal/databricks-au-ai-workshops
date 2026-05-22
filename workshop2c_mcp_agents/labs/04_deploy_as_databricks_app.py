# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     🚀 Lab 04: Deploying Your Agent as a Databricks App
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Regulated Industries
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Make your MCP agent accessible to business users as a real, governed web application
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
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>App runs in AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Auth</strong><br>Databricks OAuth (automatic)
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will learn
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | UI Tour | Databricks Apps gallery, template picker, app management page | 10 min |
# MAGIC | 2 | App File | Write `app.py` — Gradio chat UI wrapping the AEMO agent | 15 min |
# MAGIC | 3 | Deploy | UI-driven deployment: name, template, resources, environment variables | 10 min |
# MAGIC | 4 | Test & Share | Open the live URL, verify the agent, share with business users | 10 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why Databricks Apps — not a notebook
# MAGIC
# MAGIC | Option | Who can access | Auth model | Scales | Governance |
# MAGIC |--------|---------------|------------|--------|------------|
# MAGIC | Notebook (your current state) | Only engineers with workspace access | PAT / cluster | One user at a time | None |
# MAGIC | **Databricks App** | **Any user you invite via UC permissions** | **Databricks OAuth — no token management** | **Serverless — scales to zero, auto-scales up** | **Usage in system.access.audit** |
# MAGIC | External server (EC2, ACI) | Anyone on the network | You manage | You manage | Nothing automatic |
# MAGIC
# MAGIC Databricks Apps run as a **managed service principal** inside your workspace region.
# MAGIC For AEMO: all compute stays in Australia East — no cross-region data movement even for the UI tier.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Workshop configuration
# MAGIC
# MAGIC Run this cell once. All subsequent cells read from these widgets.

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo",    "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("genie_space_id", "FILL_IN",              "AEMO Genie Space ID")
dbutils.widgets.text("app_name",       "aemo-operations-agent","App name (lowercase + hyphens)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
APP_NAME       = dbutils.widgets.get("app_name")

from databricks.sdk import WorkspaceClient
ws = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host  : {HOST}")
print(f"Catalog.Schema  : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint     : {PT_ENDPOINT}")
print(f"Genie Space ID  : {GENIE_SPACE_ID}")
print(f"App name        : {APP_NAME}")

if GENIE_SPACE_ID == "FILL_IN":
    print("\nNOTE: Set 'genie_space_id' widget to your AEMO Genie Space ID.")
    print("      The app will still deploy without it — Genie is optional.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workspace host  : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC Catalog.Schema  : workshop_au.aemo
# MAGIC PT endpoint     : au_east_llm_inregion
# MAGIC Genie Space ID  : 01jf3k2m9xyz456   (or FILL_IN)
# MAGIC App name        : aemo-operations-agent
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — UI Tour of Databricks Apps (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Navigate to Databricks Apps
# MAGIC
# MAGIC Databricks Apps is the managed application platform built into your workspace.
# MAGIC It runs Python web frameworks (Gradio, Streamlit, FastAPI, Flask, Dash, Reflex) as
# MAGIC serverless containers — no server to provision, no container registry to manage.
# MAGIC
# MAGIC **How to get there:**
# MAGIC ```
# MAGIC Option A (recommended):
# MAGIC   Left sidebar → look for "Apps" icon (rocket or grid depending on workspace version)
# MAGIC   → click it
# MAGIC
# MAGIC Option B (app switcher):
# MAGIC   Click the grid/waffle icon ⊞ at the top-left of the workspace
# MAGIC   → scroll to "Apps" in the product switcher
# MAGIC   → click "Apps"
# MAGIC
# MAGIC Option C (direct URL):
# MAGIC   https://<your-workspace>/apps
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **What the Apps home page looks like (no apps yet):**
# MAGIC ```
# MAGIC ┌─── Databricks Apps ────────────────────────────────────────────────────────┐
# MAGIC │  [+ Create app]                                    🔍 Search apps          │
# MAGIC │  ────────────────────────────────────────────────────────────────────────  │
# MAGIC │                                                                            │
# MAGIC │  My Apps:                                                                  │
# MAGIC │  ┌────────────────────────┬──────────┬───────────────────────────────────┐ │
# MAGIC │  │ App Name               │ Status   │ URL                               │ │
# MAGIC │  ├────────────────────────┼──────────┼───────────────────────────────────┤ │
# MAGIC │  │ (none yet)             │          │                                   │ │
# MAGIC │  └────────────────────────┴──────────┴───────────────────────────────────┘ │
# MAGIC │                                                                            │
# MAGIC │  Shared with me:                                                           │
# MAGIC │  ┌────────────────────────┬──────────┬───────────────────────────────────┐ │
# MAGIC │  │ (none yet)             │          │                                   │ │
# MAGIC │  └────────────────────────┴──────────┴───────────────────────────────────┘ │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC If the workshop facilitator has pre-deployed a demo app you will see it in
# MAGIC "Shared with me". Click into it to explore before creating your own.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — The template gallery
# MAGIC
# MAGIC Click **[+ Create app]** to open the template picker.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Create an app — Choose a template ─────────────────────────────────────┐
# MAGIC │                                                                            │
# MAGIC │  ╔═══════════════╗  ╔═══════════════╗  ╔═══════════════╗                  │
# MAGIC │  ║  🖥️  Streamlit ║  ║  📊  Gradio   ║  ║  ⚡  FastAPI  ║                  │
# MAGIC │  ║               ║  ║               ║  ║               ║                  │
# MAGIC │  ║  Classic UI   ║  ║  Chat & demo  ║  ║  REST API     ║                  │
# MAGIC │  ║  framework    ║  ║  interfaces   ║  ║  backend      ║                  │
# MAGIC │  ╚═══════════════╝  ╚═══════════════╝  ╚═══════════════╝                  │
# MAGIC │                                                                            │
# MAGIC │  ╔═══════════════╗  ╔═══════════════╗  ╔═══════════════╗                  │
# MAGIC │  ║  🤖 LangGraph  ║  ║  🔷  Flask    ║  ║  📦  Custom   ║ ← use this       │
# MAGIC │  ║     Agent     ║  ║               ║  ║               ║                  │
# MAGIC │  ║  Pre-built    ║  ║  Lightweight  ║  ║  Bring your   ║                  │
# MAGIC │  ║  agent UI     ║  ║  web server   ║  ║  own app.py   ║                  │
# MAGIC │  ╚═══════════════╝  ╚═══════════════╝  ╚═══════════════╝                  │
# MAGIC │                                                                            │
# MAGIC │  [Cancel]                                           [Next →]              │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC For this lab we use **Custom** because we are bringing our own `app.py`.
# MAGIC The LangGraph template is useful for quick agent demos without custom UI code —
# MAGIC worth exploring after this workshop.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — App name rules
# MAGIC
# MAGIC The app name becomes part of your app's permanent URL. Choose carefully.
# MAGIC
# MAGIC ```
# MAGIC App name rules:
# MAGIC   ✅ lowercase letters, numbers, hyphens
# MAGIC   ✅ 3–40 characters
# MAGIC   ❌ no underscores, no spaces, no uppercase
# MAGIC   ❌ cannot be changed after creation (must delete and recreate)
# MAGIC
# MAGIC Name → URL pattern:
# MAGIC   aemo-operations-agent  →  https://aemo-operations-agent-{ws-id}.databricksapps.com
# MAGIC
# MAGIC The {ws-id} suffix is unique to your workspace — no collisions between workspaces.
# MAGIC The full URL is shown on the app management page once deployed.
# MAGIC ```
# MAGIC
# MAGIC **Workshop convention:** use `aemo-operations-agent-{your-initials}` if multiple people
# MAGIC are deploying in the same workspace to avoid name conflicts.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — The app management page
# MAGIC
# MAGIC After clicking an existing app in the gallery, you see its management page.
# MAGIC This is where you control everything post-deployment.
# MAGIC
# MAGIC ```
# MAGIC ┌─── App: aemo-operations-agent ──────────────────────────────────────────────┐
# MAGIC │                                                                              │
# MAGIC │  Status: ✅ Running                                                          │
# MAGIC │  URL:    https://aemo-operations-agent-{ws-id}.databricksapps.com            │
# MAGIC │                                                                              │
# MAGIC │  [Open app ↗]    [Redeploy]    [Stop]    [Delete]                           │
# MAGIC │                                                                              │
# MAGIC │  ┌─────────────┬──────────────┬────────────────┬──────────────────────────┐ │
# MAGIC │  │  Overview   │  Resources   │  Logs          │  Deployment history      │ │
# MAGIC │  └─────────────┴──────────────┴────────────────┴──────────────────────────┘ │
# MAGIC │                                                                              │
# MAGIC │  Overview tab shows:                                                         │
# MAGIC │    • Last deployed: 2025-xx-xx at 09:47 AEST                                │
# MAGIC │    • Service principal: app-sp-aemo-operations-agent@...                    │
# MAGIC │    • Source: workspace path or uploaded file                                │
# MAGIC │    • Permission: who can open the app URL                                   │
# MAGIC │                                                                              │
# MAGIC │  Resources tab shows:                                                        │
# MAGIC │    • Serving endpoints attached (used for permission grants)                │
# MAGIC │    • SQL warehouses attached                                                 │
# MAGIC │    • Secrets referenced                                                      │
# MAGIC │                                                                              │
# MAGIC │  Logs tab shows:                                                             │
# MAGIC │    • stdout / stderr from your app process                                  │
# MAGIC │    • Import errors visible here if app fails to start                       │
# MAGIC │                                                                              │
# MAGIC │  Deployment history tab shows:                                               │
# MAGIC │    • Every redeploy with timestamp and committer                            │
# MAGIC │    • Roll back to any previous deployment                                   │
# MAGIC └──────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 — App permissions: who can open the URL
# MAGIC
# MAGIC Apps use Databricks OAuth for the browser session. Users who click your app URL
# MAGIC are prompted to log in with their Databricks account — no separate password.
# MAGIC
# MAGIC ```
# MAGIC Permissions are managed on the app management page:
# MAGIC
# MAGIC   App management → Permissions tab → [Edit permissions]
# MAGIC
# MAGIC   ┌─── App permissions ────────────────────────────────────────────────────┐
# MAGIC   │  Principal                         Permission                          │
# MAGIC   │  ─────────────────────────────     ──────────────                      │
# MAGIC   │  aemo-operations-team (group)      CAN_USE        ← can open the app  │
# MAGIC   │  beyza.yalavac@databricks.com      IS_OWNER       ← full control       │
# MAGIC   │  [+ Add principal]                                                     │
# MAGIC   └────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Permission levels:
# MAGIC   CAN_USE     → Open the app URL. No workspace access required.
# MAGIC   CAN_MANAGE  → Redeploy, edit settings, view logs.
# MAGIC   IS_OWNER    → Full control including delete.
# MAGIC
# MAGIC Key point for regulated industries:
# MAGIC   A business analyst with CAN_USE can open the agent URL without ever
# MAGIC   getting a Databricks workspace seat or touching any notebook.
# MAGIC   Their session is authenticated and audited — appears in system.access.audit.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Create the Agent App File (15 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — What we are building
# MAGIC
# MAGIC We will create three files that Databricks Apps needs:
# MAGIC
# MAGIC | File | Purpose |
# MAGIC |------|---------|
# MAGIC | `app.py` | The application entry point — Gradio chat UI wrapping the AEMO agent |
# MAGIC | `requirements.txt` | Python packages to install at app startup |
# MAGIC | `app.yaml` | App configuration: command, environment variables, resources |
# MAGIC
# MAGIC All three files live together in a Databricks workspace folder (or local directory
# MAGIC you upload). The app build process installs `requirements.txt`, then runs the
# MAGIC command defined in `app.yaml`.
# MAGIC
# MAGIC ```
# MAGIC Folder structure in workspace:
# MAGIC
# MAGIC   /Users/you@company.com/apps/aemo-agent/
# MAGIC     ├── app.py            ← main application
# MAGIC     ├── requirements.txt  ← pip dependencies
# MAGIC     └── app.yaml          ← runtime configuration
# MAGIC ```
# MAGIC
# MAGIC **Why Gradio?**
# MAGIC Gradio ships a `gr.ChatInterface` component that handles conversation history,
# MAGIC streaming output, and example prompts with five lines of code. For a workshop
# MAGIC demo or internal tool it is the fastest path to a usable chat UI.
# MAGIC For production customer-facing tools you would typically use Streamlit (more
# MAGIC control) or FastAPI + React (full custom UI).

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Write `app.py` to a workspace folder
# MAGIC
# MAGIC The cell below writes the app file directly into a workspace folder using `dbutils.fs`.
# MAGIC
# MAGIC > **Tip for facilitators:** participants can also copy-paste these files into the
# MAGIC > Databricks file browser (Files → Upload) instead of running this cell.
# MAGIC
# MAGIC Read through the file before running — the architecture is important:
# MAGIC
# MAGIC | Component | What it does |
# MAGIC |-----------|--------------|
# MAGIC | `build_agent()` | Async function that creates the MCP servers + LangGraph ReAct agent |
# MAGIC | `chat()` | Sync wrapper called by Gradio on each user message |
# MAGIC | `gr.ChatInterface` | Gradio component: chat history, streaming, example prompts |
# MAGIC | `demo.launch()` | Start the Gradio server on port 8080 (required by Apps) |
# MAGIC
# MAGIC The agent is rebuilt on every message in this workshop implementation.
# MAGIC In production you would initialise the agent once at module load time and
# MAGIC share it across requests — see the comments in the code.

# COMMAND ----------

APP_PY_CONTENT = '''# app.py — AEMO Operations Agent UI
# Databricks Apps entry point
# Deploy via: Apps → Create app → Custom → point to this folder

import gradio as gr
import asyncio
import os

from databricks_langchain import (
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
    ChatDatabricks,
)
from langgraph.prebuilt import create_react_agent
import mlflow

# ---------------------------------------------------------------------------
# Configuration — read from Databricks Apps environment variables
# ---------------------------------------------------------------------------
# These are set in app.yaml (env: block) or via the UI Resources/Environment tab.
# Local defaults below are only for testing outside Apps.

PT_ENDPOINT    = os.environ.get("PT_ENDPOINT",    "au_east_llm_inregion")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
WORKSPACE_URL  = os.environ.get("DATABRICKS_HOST",  "").rstrip("/")
CATALOG        = os.environ.get("CATALOG",        "workshop_au")
SCHEMA_AEMO    = os.environ.get("SCHEMA_AEMO",    "aemo")

# MLflow experiment for tracing — all agent calls will appear here
mlflow.set_experiment("/Apps/aemo-operations-agent")

# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------

async def build_agent():
    """
    Build a LangGraph ReAct agent backed by MCP servers.

    Called on each chat message in this workshop implementation.
    In production: call this once at module load and reuse the agent object.
    Pattern:  _agent = None  →  initialise lazily in an async startup hook.
    """
    servers = [
        DatabricksMCPServer.from_uc_function(
            catalog=CATALOG,
            schema=SCHEMA_AEMO,
            name="aemo-uc-tools",
        ),
    ]

    # Add Genie Space MCP server only if a Space ID is configured
    if GENIE_SPACE_ID:
        servers.append(
            DatabricksMCPServer(
                name="aemo-genie",
                url=f"{WORKSPACE_URL}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            )
        )

    client = DatabricksMultiServerMCPClient(servers)
    tools  = await client.get_tools()
    llm    = ChatDatabricks(endpoint=PT_ENDPOINT)

    system_prompt = (
        "You are the AEMO NEM Operations Assistant. "
        "You help operations staff and analysts answer questions about "
        "NEM dispatch intervals, spot prices, market notices, settlements, "
        "and generation unit status. "
        "When you use a tool, briefly explain what you looked up before "
        "presenting results. "
        "All data is from Australia East — data residency is maintained."
    )

    return create_react_agent(
        llm,
        tools,
        state_modifier=system_prompt,
    )


# ---------------------------------------------------------------------------
# Gradio chat handler
# ---------------------------------------------------------------------------

def chat(message: str, history: list) -> str:
    """
    Synchronous wrapper around the async agent.
    Gradio's ChatInterface calls this function on every user message.

    history: list of [user_msg, assistant_msg] pairs (Gradio format)
    Returns:  assistant response as a plain string
    """

    async def run():
        agent  = await build_agent()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]}
        )
        return result["messages"][-1].content

    return asyncio.run(run())


# ---------------------------------------------------------------------------
# Gradio interface definition
# ---------------------------------------------------------------------------

demo = gr.ChatInterface(
    fn=chat,
    title="⚡ AEMO NEM Operations Assistant",
    description=(
        "Ask questions about NEM dispatch intervals, spot prices, market notices, "
        "settlements, and generation unit status. "
        "All data is processed in **Australia East** — APRA data residency maintained."
    ),
    examples=[
        "What was the average spot price in VIC yesterday?",
        "Which generators dispatched the most in NSW last week?",
        "Were there any LOR1 or LOR2 events this week?",
        "Show me the five highest 5-minute dispatch prices across all regions this month.",
    ],
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="orange",
    ),
    # retry_btn and undo_btn are available in Gradio >= 4.0
    retry_btn="Retry",
    undo_btn="Undo last turn",
    clear_btn="Clear conversation",
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Databricks Apps expects the server on port 8080
    # server_name="0.0.0.0" required so the Apps proxy can reach it
    demo.launch(
        server_name="0.0.0.0",
        server_port=8080,
        show_error=True,      # surface Python tracebacks in the UI during dev
    )
'''

print(APP_PY_CONTENT)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Write the file to the workspace folder
# MAGIC
# MAGIC We use `dbutils.fs.put` to write the file into a workspace path.
# MAGIC This is the folder you will point Databricks Apps to during deployment.

# COMMAND ----------

import os

# Workspace file path for the app folder
APP_FOLDER = f"/Workspace/Users/{ws.current_user.me().user_name}/apps/aemo-operations-agent"

# Create the directory (dbutils.fs.mkdirs works for /Workspace paths)
dbutils.fs.mkdirs(APP_FOLDER)

# Write app.py
dbutils.fs.put(f"{APP_FOLDER}/app.py", APP_PY_CONTENT, overwrite=True)

print(f"app.py written to: {APP_FOLDER}/app.py")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC app.py written to: /Workspace/Users/you@company.com/apps/aemo-operations-agent/app.py
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Write `requirements.txt`
# MAGIC
# MAGIC These packages are installed into the App container at build time.
# MAGIC Pin versions conservatively for regulated workloads — you want deterministic builds.
# MAGIC
# MAGIC > **Note on `mlflow`:** Databricks Apps containers include a base MLflow version.
# MAGIC > Listing it here pins the exact version used in this lab to keep tracing
# MAGIC > behaviour consistent with what you tested in earlier labs.

# COMMAND ----------

REQUIREMENTS_CONTENT = """gradio>=4.0,<5.0
databricks-langchain>=0.1.0
databricks-mcp>=0.1.0
langgraph>=1.0.9
mlflow>=2.17.0
"""

dbutils.fs.put(f"{APP_FOLDER}/requirements.txt", REQUIREMENTS_CONTENT, overwrite=True)

print(f"requirements.txt written to: {APP_FOLDER}/requirements.txt")
print()
print("Contents:")
print(REQUIREMENTS_CONTENT)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC requirements.txt written to: /Workspace/Users/you@company.com/apps/aemo-operations-agent/requirements.txt
# MAGIC
# MAGIC Contents:
# MAGIC gradio>=4.0,<5.0
# MAGIC databricks-langchain>=0.1.0
# MAGIC databricks-mcp>=0.1.0
# MAGIC langgraph>=1.0.9
# MAGIC mlflow>=2.17.0
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.5 — Write `app.yaml`
# MAGIC
# MAGIC `app.yaml` tells Databricks Apps how to start your application and which
# MAGIC workspace resources (serving endpoints, warehouses) it needs permission to access.
# MAGIC
# MAGIC The `resources` block is important: listing your PT endpoint here causes Apps to
# MAGIC automatically grant the app's managed service principal `CAN_QUERY` on that endpoint.
# MAGIC You do not need to manually manage those permissions.
# MAGIC
# MAGIC **app.yaml anatomy:**
# MAGIC ```
# MAGIC command      → shell command to start the app (must start a server on port 8080)
# MAGIC env          → environment variables (plain values or secret references)
# MAGIC resources    → Databricks resources the app needs (endpoint, warehouse, etc.)
# MAGIC ```

# COMMAND ----------

APP_YAML_CONTENT = f"""command: ["python", "app.py"]

env:
  - name: PT_ENDPOINT
    value: {PT_ENDPOINT}
  - name: CATALOG
    value: {CATALOG}
  - name: SCHEMA_AEMO
    value: {SCHEMA_AEMO}
  # GENIE_SPACE_ID: set this via the UI Environment tab after deployment
  # if you do not want to store it in the YAML file.
  # Alternatively uncomment the next two lines:
  # - name: GENIE_SPACE_ID
  #   value: {GENIE_SPACE_ID}

resources:
  - name: aemo-pt-endpoint
    description: Provisioned Throughput endpoint for AEMO agent LLM calls
    serving_endpoint:
      name: {PT_ENDPOINT}
      permission: CAN_QUERY
"""

dbutils.fs.put(f"{APP_FOLDER}/app.yaml", APP_YAML_CONTENT, overwrite=True)

print(f"app.yaml written to: {APP_FOLDER}/app.yaml")
print()
print("Contents:")
print(APP_YAML_CONTENT)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC app.yaml written to: /Workspace/Users/you@company.com/apps/aemo-operations-agent/app.yaml
# MAGIC
# MAGIC Contents:
# MAGIC command: ["python", "app.py"]
# MAGIC
# MAGIC env:
# MAGIC   - name: PT_ENDPOINT
# MAGIC     value: au_east_llm_inregion
# MAGIC   ...
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.6 — Verify all three files exist

# COMMAND ----------

files = dbutils.fs.ls(APP_FOLDER)
print(f"Files in {APP_FOLDER}:\n")
for f in files:
    size_kb = f.size / 1024
    print(f"  {f.name:<25} {size_kb:>6.1f} KB")

assert len(files) == 3, f"Expected 3 files (app.py, requirements.txt, app.yaml), found {len(files)}"
names = {f.name for f in files}
assert "app.py" in names,            "app.py missing"
assert "requirements.txt" in names,  "requirements.txt missing"
assert "app.yaml" in names,          "app.yaml missing"

print("\nAll three required files present. Ready to deploy.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Files in /Workspace/Users/you@company.com/apps/aemo-operations-agent:
# MAGIC
# MAGIC   app.py                    3.2 KB
# MAGIC   app.yaml                  0.4 KB
# MAGIC   requirements.txt          0.1 KB
# MAGIC
# MAGIC All three required files present. Ready to deploy.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.7 — Print the workspace folder path for copy-paste into the UI
# MAGIC
# MAGIC You will need this path in Section 3 when you point Apps to your source folder.

# COMMAND ----------

print("=" * 65)
print("  Workspace folder path for Databricks Apps deployment")
print("=" * 65)
print()
print(f"  {APP_FOLDER}")
print()
print("  Copy this path — you will paste it into the Apps UI in Section 3.")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Deploy via the Databricks Apps UI (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Create the app — step-by-step UI walkthrough
# MAGIC
# MAGIC Follow these steps in the Databricks UI. The code cells in this section
# MAGIC do **not** need to be run — the deployment is UI-driven.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Step 1 — Open Apps and click [+ Create app]**
# MAGIC ```
# MAGIC Left sidebar → Apps → [+ Create app]
# MAGIC ```
# MAGIC
# MAGIC **Step 2 — Choose "Custom" template**
# MAGIC ```
# MAGIC Template gallery → click "Custom"
# MAGIC                            ↑
# MAGIC                    This lets you bring your own app.py
# MAGIC → [Next →]
# MAGIC ```
# MAGIC
# MAGIC **Step 3 — Enter the app name**
# MAGIC ```
# MAGIC ┌─── Name your app ──────────────────────────────────────────────────────────┐
# MAGIC │  App name: [aemo-operations-agent                               ]          │
# MAGIC │                                                                            │
# MAGIC │  ⓘ The app name is permanent and becomes part of your URL.               │
# MAGIC │     Use lowercase letters, numbers, and hyphens only.                     │
# MAGIC │                                                                            │
# MAGIC │  URL preview: https://aemo-operations-agent-{ws-id}.databricksapps.com   │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC → [Next →]
# MAGIC ```
# MAGIC
# MAGIC **Step 4 — Set the source location**
# MAGIC ```
# MAGIC ┌─── Source ─────────────────────────────────────────────────────────────────┐
# MAGIC │  Source type:  ● Workspace folder   ○ Git repository                      │
# MAGIC │                                                                            │
# MAGIC │  Workspace folder:                                                         │
# MAGIC │  [/Users/you@company.com/apps/aemo-operations-agent           ] [Browse]  │
# MAGIC │                  ↑                                                         │
# MAGIC │    Paste the path printed by the cell above (Section 2.7)                │
# MAGIC │                                                                            │
# MAGIC │  ✅ app.py detected                                                       │
# MAGIC │  ✅ requirements.txt detected                                             │
# MAGIC │  ✅ app.yaml detected                                                     │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC → [Next →]
# MAGIC ```
# MAGIC
# MAGIC **Step 5 — Review Resources (auto-populated from app.yaml)**
# MAGIC ```
# MAGIC ┌─── Resources ──────────────────────────────────────────────────────────────┐
# MAGIC │  Resources detected from app.yaml:                                        │
# MAGIC │                                                                            │
# MAGIC │  Type              Name                    Permission                      │
# MAGIC │  ──────────────    ──────────────────────  ──────────────                  │
# MAGIC │  Serving endpoint  au_east_llm_inregion    CAN_QUERY  ✅                   │
# MAGIC │                                                                            │
# MAGIC │  [+ Add resource] if you need to add a SQL warehouse or additional endpoint │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC → [Next →]
# MAGIC ```
# MAGIC
# MAGIC **Step 6 — Review Environment Variables (auto-populated from app.yaml)**
# MAGIC ```
# MAGIC ┌─── Environment variables ───────────────────────────────────────────────────┐
# MAGIC │  Name             Value                    Source                           │
# MAGIC │  ──────────────   ─────────────────────   ──────────                        │
# MAGIC │  PT_ENDPOINT      au_east_llm_inregion     app.yaml                        │
# MAGIC │  CATALOG          workshop_au              app.yaml                        │
# MAGIC │  SCHEMA_AEMO      aemo                     app.yaml                        │
# MAGIC │                                                                            │
# MAGIC │  [+ Add variable] ← add GENIE_SPACE_ID here if you have one               │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC → [Deploy]
# MAGIC ```
# MAGIC
# MAGIC **Step 7 — Watch the deployment progress**
# MAGIC ```
# MAGIC ┌─── App: aemo-operations-agent ─────────────────────────────────────────────┐
# MAGIC │                                                                            │
# MAGIC │  ⟳  Deploying...                                                          │
# MAGIC │     Installing requirements.txt (30–90 seconds)                           │
# MAGIC │     Starting app.py                                                        │
# MAGIC │                                                                            │
# MAGIC │  Deployment typically takes 1–3 minutes on first deploy.                  │
# MAGIC │  Subsequent deploys (same container, just code update) take ~30 seconds.  │
# MAGIC │                                                                            │
# MAGIC │  Status progression:                                                       │
# MAGIC │    Pending → Building → Deploying → Running                               │
# MAGIC │                                          ↑                                │
# MAGIC │                           Wait for this before opening the URL            │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — If the app fails to start: reading the Logs tab
# MAGIC
# MAGIC If the status stays on "Deploying" for more than 3 minutes, or shows "Error",
# MAGIC check the Logs tab first.
# MAGIC
# MAGIC ```
# MAGIC Common errors and fixes:
# MAGIC
# MAGIC Error in logs                          Cause / Fix
# MAGIC ─────────────────────────────────────  ─────────────────────────────────────────────
# MAGIC ModuleNotFoundError: gradio            requirements.txt not found or path wrong —
# MAGIC                                        verify your workspace folder path
# MAGIC
# MAGIC FileNotFoundError: app.py              Command in app.yaml is "python app.py" but
# MAGIC                                        app.py is in a subdirectory — adjust path
# MAGIC
# MAGIC Address already in use :8080           Another process is using port 8080 —
# MAGIC                                        only one app process should be started
# MAGIC
# MAGIC DATABRICKS_HOST not set                app.py references WORKSPACE_URL but the
# MAGIC                                        env var wasn't injected — check app.yaml env block
# MAGIC
# MAGIC 403 Forbidden calling /api/2.0/mcp/…  App service principal lacks permission on the
# MAGIC                                        UC schema — grant EXECUTE on the functions
# MAGIC ```
# MAGIC
# MAGIC **To find the app's service principal name:**
# MAGIC ```
# MAGIC App management page → Overview tab → "Service principal: app-sp-aemo-..."
# MAGIC Copy the SP name, then:
# MAGIC   Catalog Explorer → workshop_au.aemo → Permissions → Grant EXECUTE to that SP
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Granting the app service principal permission on UC functions
# MAGIC
# MAGIC The app runs as its own managed service principal. That SP needs `EXECUTE`
# MAGIC on the UC functions it calls via MCP. Run this after you know the SP name.

# COMMAND ----------

# Get the app's service principal name via the SDK
# (Only works after the app has been created — it may not exist yet at this point)

try:
    app_info = ws.apps.get(APP_NAME)
    sp_name = app_info.service_principal_name
    print(f"App service principal: {sp_name}")
    print()
    print("Grant UC function access with this SQL (run in a SQL cell or DBSQL):")
    print()
    print(f"  GRANT EXECUTE ON SCHEMA {CATALOG}.{SCHEMA_AEMO}")
    print(f"  TO `{sp_name}`;")
    print()
    print("  -- Or grant at catalog level for all schemas:")
    print(f"  GRANT USE CATALOG ON CATALOG {CATALOG}")
    print(f"  TO `{sp_name}`;")
    print(f"  GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_AEMO}")
    print(f"  TO `{sp_name}`;")
    print(f"  GRANT EXECUTE ON SCHEMA {CATALOG}.{SCHEMA_AEMO}")
    print(f"  TO `{sp_name}`;")
except Exception as e:
    print(f"App '{APP_NAME}' not found yet — deploy it first via the UI.")
    print(f"Then re-run this cell to get the grant statements.")
    print(f"(Error: {e})")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — Alternative: deploy via the Databricks CLI (reference)
# MAGIC
# MAGIC The UI approach above is recommended for workshops. For CI/CD pipelines or
# MAGIC automated deployments, use the CLI:
# MAGIC
# MAGIC ```bash
# MAGIC # Authenticate first
# MAGIC databricks auth login --host https://adb-xxxx.azuredatabricks.net
# MAGIC
# MAGIC # Create the app (first time only)
# MAGIC databricks apps create aemo-operations-agent \
# MAGIC   --description "AEMO NEM Operations Assistant"
# MAGIC
# MAGIC # Deploy the app from a local directory
# MAGIC databricks apps deploy aemo-operations-agent \
# MAGIC   --source-code-path /local/path/to/app/folder
# MAGIC
# MAGIC # Check deployment status
# MAGIC databricks apps get aemo-operations-agent
# MAGIC
# MAGIC # List all apps
# MAGIC databricks apps list
# MAGIC
# MAGIC # Stream logs
# MAGIC databricks apps logs aemo-operations-agent --follow
# MAGIC ```
# MAGIC
# MAGIC For Databricks Asset Bundles (DABs), add an `app` resource to your `databricks.yml`:
# MAGIC ```yaml
# MAGIC resources:
# MAGIC   apps:
# MAGIC     aemo-operations-agent:
# MAGIC       name: aemo-operations-agent
# MAGIC       description: AEMO NEM Operations Assistant
# MAGIC       source_code_path: ./app
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Test and Share the App (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Open the app and run the standard test questions
# MAGIC
# MAGIC Once the app status shows **Running**, click **[Open app ↗]** on the management page.
# MAGIC Your browser opens the Gradio chat interface.
# MAGIC
# MAGIC ```
# MAGIC ┌─── ⚡ AEMO NEM Operations Assistant ──────────────────────────────────────────┐
# MAGIC │                                                                               │
# MAGIC │  Ask questions about NEM dispatch intervals, spot prices, market notices,    │
# MAGIC │  settlements, and generation unit status.                                    │
# MAGIC │  All data is processed in Australia East — APRA data residency maintained.  │
# MAGIC │                                                                               │
# MAGIC │  ┌─────────────────────────────────────────────────────────────────────────┐ │
# MAGIC │  │                                                                         │ │
# MAGIC │  │  (conversation area — empty on first load)                             │ │
# MAGIC │  │                                                                         │ │
# MAGIC │  └─────────────────────────────────────────────────────────────────────────┘ │
# MAGIC │                                                                               │
# MAGIC │  Examples:                                                                   │
# MAGIC │  [What was the average spot price in VIC yesterday?]                        │
# MAGIC │  [Which generators dispatched the most in NSW last week?]                   │
# MAGIC │  [Were there any LOR1 or LOR2 events this week?]                            │
# MAGIC │  [Show me the five highest 5-min dispatch prices across all regions]        │
# MAGIC │                                                                               │
# MAGIC │  ┌─────────────────────────────────────────────────────────────────────┬──┐ │
# MAGIC │  │ Type a message...                                                   │▶ │ │
# MAGIC │  └─────────────────────────────────────────────────────────────────────┴──┘ │
# MAGIC └───────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Run these four test questions from Lab 03:**
# MAGIC ```
# MAGIC 1. What was the average spot price in VIC yesterday?
# MAGIC 2. Which generators dispatched the most in NSW last week?
# MAGIC 3. Were there any LOR1 or LOR2 events this week?
# MAGIC 4. Show me the five highest 5-minute dispatch prices across all NEM regions this month.
# MAGIC ```
# MAGIC
# MAGIC You should see the agent:
# MAGIC - Calling the appropriate MCP tool (shown briefly in the UI as "Calling tool: ...")
# MAGIC - Returning a natural-language answer with the query results embedded

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Verify the app is responding via HTTP
# MAGIC
# MAGIC The cell below fetches the app's URL to confirm it is reachable and returning HTTP 200.
# MAGIC This is useful in automated smoke tests and CD pipelines.

# COMMAND ----------

import urllib.request
import urllib.error
import json

# Get app URL from the SDK
try:
    app_info = ws.apps.get(APP_NAME)
    app_url = app_info.url
    print(f"App URL: {app_url}")
    print(f"Status:  {app_info.compute_status.state if app_info.compute_status else 'unknown'}")
    print()

    # Hit the Gradio health endpoint
    # Gradio exposes /info at the root which returns app metadata
    health_url = f"{app_url}/"
    req = urllib.request.Request(health_url)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            print(f"HTTP GET {health_url}")
            print(f"Response: {status} OK")
            print()
            if status == 200:
                print("App is reachable and healthy.")
            else:
                print(f"Unexpected status {status} — check app logs.")
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e.code} {e.reason}")
        print("The app URL requires browser-based OAuth — HTTP GET without a session")
        print("will return 302 (redirect to login). This is expected and correct.")
        print("Open the URL in a browser to authenticate and use the app.")
    except Exception as e:
        print(f"Could not reach app URL: {e}")

except Exception as e:
    print(f"App '{APP_NAME}' not found. Deploy it via the UI first.")
    print(f"(Error: {e})")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (app running, SDK call):**
# MAGIC ```
# MAGIC App URL: https://aemo-operations-agent-{ws-id}.databricksapps.com
# MAGIC Status:  ACTIVE
# MAGIC
# MAGIC HTTP GET https://aemo-operations-agent-{ws-id}.databricksapps.com/
# MAGIC HTTP error: 302 Found
# MAGIC The app URL requires browser-based OAuth — HTTP GET without a session
# MAGIC will return 302 (redirect to login). This is expected and correct.
# MAGIC Open the URL in a browser to authenticate and use the app.
# MAGIC ```
# MAGIC
# MAGIC The 302 redirect is normal — Databricks Apps enforces browser-based OAuth
# MAGIC before serving any content. The app is healthy; it just requires a browser session.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Share the app with business users
# MAGIC
# MAGIC To share the app URL with someone who does not have a workspace notebook seat:
# MAGIC
# MAGIC **In the UI:**
# MAGIC ```
# MAGIC App management page → Permissions tab → [Edit permissions]
# MAGIC   → [+ Add principal]
# MAGIC   → Search for: a user email, a group name, or "All workspace users"
# MAGIC   → Set permission: CAN_USE
# MAGIC   → [Save]
# MAGIC
# MAGIC Then send them the URL:
# MAGIC   https://aemo-operations-agent-{ws-id}.databricksapps.com
# MAGIC
# MAGIC They will be prompted to log in with their Databricks account (SSO via Azure AD).
# MAGIC No PAT, no workspace access, no cluster — just the app URL.
# MAGIC ```
# MAGIC
# MAGIC **Via the SDK (for scripted access control):**

# COMMAND ----------

# Example: grant CAN_USE to a group of AEMO operations staff
# Uncomment and modify before running

# from databricks.sdk.service.iam import PermissionLevel
# from databricks.sdk.service.apps import AppAccessControlRequest

# try:
#     ws.apps.set_permissions(
#         app_name=APP_NAME,
#         access_control_list=[
#             AppAccessControlRequest(
#                 group_name="aemo-operations-staff",
#                 permission_level=PermissionLevel.CAN_USE,
#             )
#         ],
#     )
#     print(f"Granted CAN_USE to aemo-operations-staff on app: {APP_NAME}")
# except Exception as e:
#     print(f"Permission grant failed: {e}")
#     print("Check that the group name exists in your workspace.")

print("Uncomment the code above and set your group name to grant access.")
print()
print("For regulated industries, best practice is to grant to a UC group")
print("that mirrors your LDAP/AD group — not to individual users.")
print("This way onboarding/offboarding is managed in AD, not in Databricks.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — App deployment history: roll back if needed
# MAGIC
# MAGIC Every deployment is versioned. If a new `app.py` breaks something, you can
# MAGIC roll back to any previous deployment from the UI:
# MAGIC
# MAGIC ```
# MAGIC App management page → Deployment history tab
# MAGIC
# MAGIC ┌─── Deployment history: aemo-operations-agent ──────────────────────────────┐
# MAGIC │  #  Time                 Status     Source SHA   Actions                   │
# MAGIC │  ─  ─────────────────   ─────────  ──────────   ─────────────────────     │
# MAGIC │  3  2025-06-12 14:23    Active      a3f8c1d     [View]                    │
# MAGIC │  2  2025-06-12 09:15    Previous    b721e4a     [View] [Restore]          │
# MAGIC │  1  2025-06-11 16:42    Previous    d9c3f82     [View] [Restore]          │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click [Restore] on any row to redeploy that version.
# MAGIC The previous version will serve traffic within ~30 seconds.
# MAGIC ```
# MAGIC
# MAGIC This is especially valuable during incidents: roll back first, investigate second.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 — List all deployed apps (SDK reference)

# COMMAND ----------

print("All apps in this workspace:\n")
print(f"{'App name':<35} {'Status':<15} {'URL'}")
print("-" * 100)

try:
    for app in ws.apps.list():
        state = app.compute_status.state if app.compute_status else "—"
        url   = app.url or "—"
        print(f"{app.name:<35} {str(state):<15} {url}")
except Exception as e:
    print(f"Could not list apps: {e}")
    print("Ensure you have at least CAN_MANAGE on the apps you want to list.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC All apps in this workspace:
# MAGIC
# MAGIC App name                            Status          URL
# MAGIC ----------------------------------------------------------------------------------------------------
# MAGIC aemo-operations-agent               ACTIVE          https://aemo-operations-agent-{ws}.databricksapps.com
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary — Lab 04
# MAGIC
# MAGIC | What you did | Why it matters |
# MAGIC |-------------|----------------|
# MAGIC | Toured the Apps UI: gallery, management page, permissions, logs, history | Know where to look when something breaks |
# MAGIC | Wrote `app.py`, `requirements.txt`, `app.yaml` to a workspace folder | The three-file pattern that every Databricks App needs |
# MAGIC | Deployed via the Create App wizard | Understand each step: name, source, resources, env vars |
# MAGIC | Granted the app SP access to UC functions | Apps run as a service principal — permissions must be explicit |
# MAGIC | Tested the live URL | Confirmed the agent is reachable and authenticated |
# MAGIC | Shared with business users | No workspace seat required — just the app URL and a Databricks login |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin-top: 16px;">
# MAGIC   <strong style="color: #00843D;">Data residency — what just happened</strong><br><br>
# MAGIC   Every component of this stack runs in Australia East:<br>
# MAGIC   <ul style="margin: 8px 0 0 0;">
# MAGIC     <li>The App container runs in the workspace Azure subscription (AU East)</li>
# MAGIC     <li>MCP calls go to <code>/api/2.0/mcp/...</code> on the same workspace — no network hop</li>
# MAGIC     <li>The PT endpoint is in AU East (verified in Lab 01)</li>
# MAGIC     <li>Business user sessions are authenticated by the workspace OAuth server (AU East)</li>
# MAGIC   </ul>
# MAGIC   No NEM data or user query content leaves the region. APRA residency requirement maintained.
# MAGIC </div>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Next:** Lab 05 — Monitoring & Governing Your MCP Agent
