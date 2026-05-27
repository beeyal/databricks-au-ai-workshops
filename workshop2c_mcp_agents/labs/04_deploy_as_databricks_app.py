# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 04: Deploying Your Agent as a Databricks App
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Regulated Industries
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Make your MCP agent accessible to business users as a governed web application
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Estimated time</strong><br>45 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Prerequisites</strong><br>Labs 01, 02, 03 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Data residency</strong><br>App runs in AU East
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Auth</strong><br>Databricks OAuth (automatic)
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will build
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | UI Tour | Apps gallery, management page, permissions, logs | 10 min |
# MAGIC | 2 | App Files | Write `app.py`, `requirements.txt`, `app.yaml` | 15 min |
# MAGIC | 3 | Deploy | Create app wizard: name, source, resources, env vars | 10 min |
# MAGIC | 4 | Test & Share | Open the live URL, verify the agent, share access | 10 min |
# MAGIC
# MAGIC **Why Databricks Apps instead of a notebook:**
# MAGIC
# MAGIC | Option | Access | Auth | Governance |
# MAGIC |--------|--------|------|------------|
# MAGIC | Notebook | Engineers with workspace seat | PAT / cluster | None |
# MAGIC | **Databricks App** | **Any user you invite** | **Databricks OAuth** | **system.access.audit** |
# MAGIC
# MAGIC Apps run as a managed service principal inside your workspace region — for AEMO, all compute stays in Australia East.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Workshop configuration

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo",    "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("genie_space_id", "",                     "AEMO Genie Space ID")
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

if not GENIE_SPACE_ID:
    print("\nNOTE: Set 'genie_space_id' widget — the app still deploys without it.")

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
# MAGIC Databricks Apps runs Python web frameworks (Gradio, Streamlit, FastAPI, Flask) as serverless containers — no server to provision, no container registry to manage.
# MAGIC
# MAGIC **How to get there (two options):**
# MAGIC ```
# MAGIC Option A: Left sidebar → Apps
# MAGIC Option B: Click the grid/waffle icon at the very top of the workspace → select "Apps"
# MAGIC ```
# MAGIC
# MAGIC **Apps home page:**
# MAGIC ```
# MAGIC ┌─── Databricks Apps ──────────────────────────────────────┐
# MAGIC │  [+ Create app]                       Search apps        │
# MAGIC │  ──────────────────────────────────────────────────────  │
# MAGIC │  My Apps:   App Name | Status | URL                      │
# MAGIC │  Shared with me:   (none yet)                            │
# MAGIC └──────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — The template gallery and app name rules
# MAGIC
# MAGIC Click **[+ Create app]** to open the template picker. For this lab select **Custom** — we bring our own `app.py`. The LangGraph template is useful for quick agent demos without custom UI code.
# MAGIC
# MAGIC **App name rules — permanent after creation:**
# MAGIC ```
# MAGIC ✅  lowercase letters, numbers, hyphens only (3–40 chars)
# MAGIC ❌  no underscores, spaces, or uppercase
# MAGIC ❌  cannot be changed after creation (must delete and recreate)
# MAGIC
# MAGIC aemo-operations-agent  →  https://aemo-operations-agent-{ws-id}.databricksapps.com
# MAGIC ```
# MAGIC
# MAGIC Use `aemo-operations-agent-{your-initials}` if multiple participants share the same workspace.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — The app management page
# MAGIC
# MAGIC After deployment, the management page is where you control everything.
# MAGIC
# MAGIC ```
# MAGIC ┌─── App: aemo-operations-agent ───────────────────────────────┐
# MAGIC │  Status: Running      URL: https://aemo-...databricksapps.com │
# MAGIC │  [Open app] [Redeploy] [Stop] [Delete]                        │
# MAGIC │  Tabs: Overview | Resources | Logs | Deployments              │
# MAGIC └───────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC | Tab | What you see |
# MAGIC |-----|-------------|
# MAGIC | **Overview** | Service principal name, last deployed time, permissions |
# MAGIC | **Logs** | stdout/stderr — first stop when the app fails to start |
# MAGIC | **Deployments** | Full history; click any row to view or restore that version |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — App permissions
# MAGIC
# MAGIC Apps use Databricks OAuth. Users who click the app URL are prompted to log in with their Databricks account — no PAT required.
# MAGIC
# MAGIC ```
# MAGIC App management page → Permissions tab → [Edit permissions]
# MAGIC
# MAGIC Principal                     Permission
# MAGIC aemo-operations-team (group)  CAN_USE    ← can open the app URL
# MAGIC you@databricks.com            IS_OWNER   ← full control
# MAGIC
# MAGIC CAN_USE    → open the URL (no workspace seat needed)
# MAGIC CAN_MANAGE → redeploy, edit settings, view logs
# MAGIC ```
# MAGIC
# MAGIC A business analyst with CAN_USE can open the agent without ever touching a notebook. Their session appears in `system.access.audit`.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Create the Agent App Files (15 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Three-file pattern
# MAGIC
# MAGIC Every Databricks App needs exactly these files in a workspace folder:
# MAGIC
# MAGIC | File | Purpose |
# MAGIC |------|---------|
# MAGIC | `app.py` | Entry point — Gradio chat UI wrapping the AEMO agent |
# MAGIC | `requirements.txt` | Packages installed at app startup |
# MAGIC | `app.yaml` | Runtime config: command, env vars, resources |
# MAGIC
# MAGIC **Why Gradio?** `gr.ChatInterface` handles conversation history, streaming output, and example prompts in five lines of code. For a production customer-facing tool you would typically choose Streamlit or FastAPI + React.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — The `app.py` architecture
# MAGIC
# MAGIC | Component | What it does |
# MAGIC |-----------|--------------|
# MAGIC | `build_agent()` | Async — creates MCP servers + LangGraph ReAct agent |
# MAGIC | `chat()` | Sync wrapper called by Gradio on each user message |
# MAGIC | `gr.ChatInterface` | Chat history, streaming, example prompts |
# MAGIC | `demo.launch(port=8080)` | Start Gradio server on port 8080 (required by Apps) |
# MAGIC
# MAGIC The agent is rebuilt per message in this workshop. In production, initialise it once at module load and reuse across requests.

# COMMAND ----------

APP_PY_CONTENT = '''# app.py — AEMO Operations Agent UI
# Databricks Apps entry point

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
PT_ENDPOINT    = os.environ.get("PT_ENDPOINT",    "au_east_llm_inregion")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
WORKSPACE_URL  = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
CATALOG        = os.environ.get("CATALOG",        "workshop_au")
SCHEMA_AEMO    = os.environ.get("SCHEMA_AEMO",    "aemo")

mlflow.set_experiment("/Apps/aemo-operations-agent")

# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------

async def build_agent():
    servers = [
        DatabricksMCPServer.from_uc_function(
            catalog=CATALOG,
            schema=SCHEMA_AEMO,
            name="aemo-uc-tools",
        ),
    ]

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
        "You help operations staff answer questions about NEM dispatch intervals, "
        "spot prices, market notices, settlements, and generation unit status. "
        "When you use a tool, briefly explain what you looked up before presenting results. "
        "All data is from Australia East — data residency is maintained."
    )

    return create_react_agent(llm, tools, state_modifier=system_prompt)


# ---------------------------------------------------------------------------
# Gradio chat handler
# ---------------------------------------------------------------------------

def chat(message: str, history: list) -> str:
    async def run():
        agent  = await build_agent()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]}
        )
        return result["messages"][-1].content

    return asyncio.run(run())


# ---------------------------------------------------------------------------
# Gradio interface
# ---------------------------------------------------------------------------

demo = gr.ChatInterface(
    fn=chat,
    title="AEMO NEM Operations Assistant",
    description=(
        "Ask questions about NEM dispatch intervals, spot prices, market notices, "
        "settlements, and generation unit status. "
        "All data is processed in **Australia East** — SOCI Act / critical infrastructure data residency maintained."
    ),
    examples=[
        "What was the average spot price in VIC yesterday?",
        "Which generators dispatched the most in NSW last week?",
        "Were there any LOR1 or LOR2 events this week?",
        "Show me the five highest 5-minute dispatch prices across all regions this month.",
    ],
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="orange"),
    retry_btn="Retry",
    undo_btn="Undo last turn",
    clear_btn="Clear conversation",
)


# ---------------------------------------------------------------------------
# Entry point — Databricks Apps expects port 8080
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080, show_error=True)
'''

print(APP_PY_CONTENT)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Write `app.py` to the workspace folder

# COMMAND ----------

import os

APP_FOLDER = f"/Workspace/Users/{ws.current_user.me().user_name}/apps/aemo-operations-agent"
dbutils.fs.mkdirs(APP_FOLDER)
dbutils.fs.put(f"{APP_FOLDER}/app.py", APP_PY_CONTENT, overwrite=True)
print(f"app.py written to: {APP_FOLDER}/app.py")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Write `requirements.txt`
# MAGIC
# MAGIC Pin versions conservatively for regulated workloads — deterministic builds prevent surprises at redeploy time.

# COMMAND ----------

REQUIREMENTS_CONTENT = """gradio>=4.0,<5.0
databricks-langchain>=0.1.0
databricks-mcp>=0.1.0
langgraph>=1.0.9
mlflow>=2.17.0
"""

dbutils.fs.put(f"{APP_FOLDER}/requirements.txt", REQUIREMENTS_CONTENT, overwrite=True)
print(f"requirements.txt written to: {APP_FOLDER}/requirements.txt")
print(REQUIREMENTS_CONTENT)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.5 — Write `app.yaml`
# MAGIC
# MAGIC The `resources` block is important: listing your PT endpoint here causes Apps to automatically grant the app's managed service principal `CAN_QUERY` on that endpoint — no manual permission grants needed.

# COMMAND ----------

APP_YAML_CONTENT = f"""command: ["python", "app.py"]

env:
  - name: PT_ENDPOINT
    value: {PT_ENDPOINT}
  - name: CATALOG
    value: {CATALOG}
  - name: SCHEMA_AEMO
    value: {SCHEMA_AEMO}
  # To add GENIE_SPACE_ID: uncomment below or set it via the UI Environment tab
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
print(APP_YAML_CONTENT)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.6 — Verify all three files exist

# COMMAND ----------

files = dbutils.fs.ls(APP_FOLDER)
print(f"Files in {APP_FOLDER}:\n")
for f in files:
    print(f"  {f.name:<25} {f.size / 1024:>6.1f} KB")

names = {f.name for f in files}
assert "app.py" in names,           "app.py missing"
assert "requirements.txt" in names, "requirements.txt missing"
assert "app.yaml" in names,         "app.yaml missing"
print("\nAll three required files present. Ready to deploy.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.7 — Copy this path — you will paste it into the Apps UI in Section 3

# COMMAND ----------

print("=" * 65)
print("  Workspace folder path for Databricks Apps deployment")
print("=" * 65)
print(f"\n  {APP_FOLDER}\n")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Deploy via the Databricks Apps UI (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Create the app — step-by-step
# MAGIC
# MAGIC **Step 1 — Open Apps and click [+ Create app]**
# MAGIC ```
# MAGIC Left sidebar → Apps → [+ Create app]
# MAGIC ```
# MAGIC
# MAGIC **Step 2 — Choose "Custom" template** → [Next]
# MAGIC
# MAGIC **Step 3 — Enter the app name**
# MAGIC ```
# MAGIC App name: aemo-operations-agent
# MAGIC (permanent — appears in the URL, lowercase + hyphens only)
# MAGIC ```
# MAGIC → [Next]
# MAGIC
# MAGIC **Step 4 — Set the source location**
# MAGIC ```
# MAGIC Source type: Workspace folder
# MAGIC Workspace folder: paste the path from Section 2.7
# MAGIC     → UI shows: app.py detected / requirements.txt detected / app.yaml detected
# MAGIC ```
# MAGIC → [Next]
# MAGIC
# MAGIC **Step 5 — Review Resources** (auto-populated from `app.yaml`)
# MAGIC ```
# MAGIC Serving endpoint: au_east_llm_inregion   CAN_QUERY
# MAGIC ```
# MAGIC → [Next]
# MAGIC
# MAGIC **Step 6 — Review Environment Variables** (auto-populated from `app.yaml`)
# MAGIC ```
# MAGIC PT_ENDPOINT   au_east_llm_inregion
# MAGIC CATALOG       workshop_au
# MAGIC SCHEMA_AEMO   aemo
# MAGIC [+ Add variable] ← add GENIE_SPACE_ID here if you have one
# MAGIC ```
# MAGIC → [Deploy]
# MAGIC
# MAGIC **Step 7 — Watch deployment**
# MAGIC ```
# MAGIC Status: Pending → Building → Deploying → Running
# MAGIC First deploy: 1–3 minutes (installs requirements.txt)
# MAGIC Subsequent deploys (code-only): ~30 seconds
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — If the app fails: reading the Logs tab
# MAGIC
# MAGIC If status stays on "Deploying" for more than 3 minutes, or shows "Error", click the **Logs** tab first.
# MAGIC
# MAGIC | Error in logs | Cause / Fix |
# MAGIC |---------------|-------------|
# MAGIC | `ModuleNotFoundError: gradio` | `requirements.txt` not found — verify workspace folder path |
# MAGIC | `FileNotFoundError: app.py` | Command in `app.yaml` is wrong path — adjust |
# MAGIC | `Address already in use :8080` | Only one app process should start |
# MAGIC | `403 Forbidden calling /api/2.0/mcp/…` | App service principal lacks EXECUTE on UC schema |
# MAGIC
# MAGIC **To fix the 403:** App management → Overview tab → copy "Service principal" name → Catalog Explorer → `workshop_au.aemo` → Permissions → Grant EXECUTE to that SP.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Grant the app service principal permission on UC functions
# MAGIC
# MAGIC The app runs as its own managed service principal and needs EXECUTE on UC functions. Run this cell after the app has been created.

# COMMAND ----------

try:
    app_info = ws.apps.get(APP_NAME)
    sp_name = app_info.service_principal_name
    print(f"App service principal: {sp_name}")
    print()
    print("Run this SQL in a SQL cell or DBSQL editor:\n")
    print(f"  GRANT USE CATALOG ON CATALOG {CATALOG} TO `{sp_name}`;")
    print(f"  GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO `{sp_name}`;")
    print(f"  GRANT EXECUTE ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO `{sp_name}`;")
except Exception as e:
    print(f"App '{APP_NAME}' not found yet — deploy it first via the UI, then re-run this cell.")
    print(f"(Error: {e})")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — CLI reference (for CI/CD pipelines)
# MAGIC
# MAGIC ```bash
# MAGIC # Create the app (first time)
# MAGIC databricks apps create aemo-operations-agent
# MAGIC
# MAGIC # Deploy from a local directory
# MAGIC databricks apps deploy aemo-operations-agent \
# MAGIC   --source-code-path /local/path/to/app/folder
# MAGIC
# MAGIC # Stream logs
# MAGIC databricks apps logs aemo-operations-agent --follow
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
# MAGIC Once the status shows **Running**, click **[Open app]** on the management page. Run these four questions:
# MAGIC ```
# MAGIC 1. What was the average spot price in VIC yesterday?
# MAGIC 2. Which generators dispatched the most in NSW last week?
# MAGIC 3. Were there any LOR1 or LOR2 events this week?
# MAGIC 4. Show me the five highest 5-minute dispatch prices across all NEM regions this month.
# MAGIC ```
# MAGIC
# MAGIC You should see the agent briefly show "Calling tool: ..." before returning a natural-language answer with query results embedded.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Verify the app is reachable via the SDK

# COMMAND ----------

import urllib.request, urllib.error

try:
    app_info = ws.apps.get(APP_NAME)
    app_url  = app_info.url
    print(f"App URL: {app_url}")
    print(f"Status:  {app_info.compute_status.state if app_info.compute_status else 'unknown'}")

    try:
        with urllib.request.urlopen(f"{app_url}/", timeout=10) as resp:
            print(f"HTTP {resp.status} — app is reachable.")
    except urllib.error.HTTPError as e:
        if e.code == 302:
            print("HTTP 302 redirect to login — expected. Databricks Apps enforces OAuth before serving content.")
            print("Open the URL in a browser to authenticate and use the app.")
        else:
            print(f"HTTP error: {e.code} {e.reason}")
    except Exception as e:
        print(f"Could not reach app URL: {e}")

except Exception as e:
    print(f"App '{APP_NAME}' not found. Deploy it via the UI first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Share the app with business users
# MAGIC
# MAGIC **In the UI:**
# MAGIC ```
# MAGIC App management page → Permissions tab → [Edit permissions]
# MAGIC   → [+ Add principal] → search for user/group → set CAN_USE → [Save]
# MAGIC
# MAGIC Send them: https://aemo-operations-agent-{ws-id}.databricksapps.com
# MAGIC They log in with their Databricks account (SSO via Azure AD) — no PAT needed.
# MAGIC ```
# MAGIC
# MAGIC For regulated industries, grant to a UC group that mirrors your AD group — onboarding and offboarding are then managed in AD, not in Databricks.

# COMMAND ----------

# Example: grant CAN_USE to a group (uncomment and set group name before running)

# from databricks.sdk.service.iam import PermissionLevel
# from databricks.sdk.service.apps import AppAccessControlRequest

# ws.apps.set_permissions(
#     app_name=APP_NAME,
#     access_control_list=[
#         AppAccessControlRequest(
#             group_name="aemo-operations-staff",
#             permission_level=PermissionLevel.CAN_USE,
#         )
#     ],
# )
# print(f"Granted CAN_USE to aemo-operations-staff on app: {APP_NAME}")

print("Uncomment the code above and set your group name to grant access.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Deployment history and rollback
# MAGIC
# MAGIC Every redeploy is versioned. If a new `app.py` breaks something, roll back from the UI:
# MAGIC ```
# MAGIC App management page → Deployments tab
# MAGIC   → click [Restore] on any previous deployment
# MAGIC   → previous version serves traffic within ~30 seconds
# MAGIC ```
# MAGIC Roll back first, investigate second.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 — List all deployed apps

# COMMAND ----------

print(f"{'App name':<35} {'Status':<15} {'URL'}")
print("-" * 100)

try:
    for app in ws.apps.list():
        state = app.compute_status.state if app.compute_status else "—"
        url   = app.url or "—"
        print(f"{app.name:<35} {str(state):<15} {url}")
except Exception as e:
    print(f"Could not list apps: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary — Lab 04
# MAGIC
# MAGIC | What you did | Why it matters |
# MAGIC |-------------|----------------|
# MAGIC | Toured the Apps UI: gallery, management page, permissions, logs | Know where to look when something breaks |
# MAGIC | Wrote `app.py`, `requirements.txt`, `app.yaml` | The three-file pattern every Databricks App needs |
# MAGIC | Deployed via the Create App wizard | Understand each step: name, source, resources, env vars |
# MAGIC | Granted the app SP access to UC functions | Apps run as a service principal — permissions must be explicit |
# MAGIC | Tested the live URL and shared with business users | No workspace seat required — just the URL and a Databricks login |
# MAGIC
# MAGIC **Data residency:** every component runs in Australia East — App container, MCP calls, PT endpoint, and OAuth server. No NEM data or user query content leaves the region.
# MAGIC
# MAGIC **Next:** Lab 05 — Monitoring & Governing Your MCP Agent
