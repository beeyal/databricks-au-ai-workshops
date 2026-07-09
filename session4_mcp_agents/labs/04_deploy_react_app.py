# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 04 — DEPLOY: Ship the Agent as a React App
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Session 4: Building AI Agents with MCP — Australian Energy Sector (Level 200)
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Lifecycle phase 4 of 5 &nbsp;•&nbsp; Build → Evaluate → Govern → <strong>Deploy</strong> → Improve
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>40 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01-03 complete; Databricks CLI + Node.js
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>App container: AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Auth</strong><br>Databricks SSO + service principal
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will do
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | Tour the app source | `app/` React frontend + backend, `app.yaml`, resources | 8 min |
# MAGIC | 2 | Build the frontend | `cd app/frontend && npm install && npm run build` | 8 min |
# MAGIC | 3 | Deploy (UI + CLI) | Databricks Apps wizard AND `databricks apps deploy` | 12 min |
# MAGIC | 4 | Verify | `/api/health`, SSO login, service-principal auth | 8 min |
# MAGIC | 5 | Share | Grant `CAN_USE` to workshop participants | 4 min |
# MAGIC
# MAGIC <div style="background: #eef2ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   The React app source lives in <code>session4_mcp_agents/app/</code> and is provided for you —
# MAGIC   you do <strong>not</strong> write app code in this lab. You build the frontend, review the
# MAGIC   config, and deploy. The app wraps the same governed agent you built in Labs 01-03.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",           "Catalog name")
dbutils.widgets.text("schema_aemo", "aemo",                  "AEMO schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion",  "PT endpoint (in-region)")
dbutils.widgets.text("app_name",    "aemo-operations-agent", "App name (lowercase + hyphens)")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA_AEMO = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT = dbutils.widgets.get("pt_endpoint")
APP_NAME    = dbutils.widgets.get("app_name")

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host : {HOST}")
print(f"PT endpoint    : {PT_ENDPOINT}")
print(f"App name       : {APP_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — Tour the app source (8 min)
# MAGIC </div>
# MAGIC
# MAGIC The app directory is a standard Databricks App with a React frontend and a Python backend that
# MAGIC serves the agent:
# MAGIC ```
# MAGIC session4_mcp_agents/app/
# MAGIC   app.yaml            # command, env vars, resource declarations
# MAGIC   requirements.txt    # backend Python deps (fastapi, databricks-langchain, langgraph, ...)
# MAGIC   server.py           # FastAPI server: /api/chat (SSE), /api/health; serves the built SPA
# MAGIC   agent.py            # build_agent() + astream_answer() — the ReAct agent over the 3 MCP servers
# MAGIC   frontend/           # React + Vite chat UI; `npm run build` emits static assets server.py serves
# MAGIC     package.json
# MAGIC     src/
# MAGIC ```
# MAGIC `agent.py` reuses the Lab 01 pattern (ChatDatabricks on the PT endpoint + the three MCP servers)
# MAGIC and `server.py` adds the Lakebase memory table for multi-turn chat.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Review `app/app.yaml`
# MAGIC The manifest declares the run command, environment variables, and — critically — the
# MAGIC **resources** the app's service principal is granted at deploy time.
# MAGIC ```yaml
# MAGIC command: ["python", "server.py"]
# MAGIC
# MAGIC env:
# MAGIC   - name: PT_ENDPOINT
# MAGIC     value: au_east_llm_inregion      # in-region PT endpoint ONLY
# MAGIC   - name: CATALOG
# MAGIC     value: workshop_au
# MAGIC   - name: SCHEMA_AEMO
# MAGIC     value: aemo
# MAGIC
# MAGIC resources:
# MAGIC   - name: aemo-pt-endpoint
# MAGIC     serving_endpoint:
# MAGIC       name: au_east_llm_inregion
# MAGIC       permission: CAN_QUERY          # the SP may query the PT endpoint — nothing cross-geo
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #FF3621;">Residency check</strong><br>
# MAGIC   The only serving endpoint resource is <code>au_east_llm_inregion</code> with
# MAGIC   <code>CAN_QUERY</code>. There is no resource granting the app SP access to any pay-per-token
# MAGIC   endpoint — so the deployed app cannot route inference cross-geo.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Build the React frontend (8 min)
# MAGIC </div>
# MAGIC
# MAGIC Run these in a terminal on the workshop environment (the Databricks CLI and Node.js are
# MAGIC pre-installed). Building produces the static assets the backend serves.

# COMMAND ----------

# MAGIC %md
# MAGIC ```bash
# MAGIC cd session4_mcp_agents/app/frontend
# MAGIC npm install          # install React dependencies
# MAGIC npm run build        # produce production build (e.g. frontend/dist or build/)
# MAGIC ```
# MAGIC
# MAGIC A successful build ends with a bundle summary and no errors. The backend is configured to serve
# MAGIC the build output as the app's UI.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Deploy: Apps UI and the CLI (12 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Option A: Databricks Apps UI
# MAGIC ```
# MAGIC Left sidebar → Apps → [+ Create app]
# MAGIC   Name        : aemo-operations-agent
# MAGIC   Source      : point at session4_mcp_agents/app/  (folder with app.yaml)
# MAGIC   Resources   : confirm au_east_llm_inregion (CAN_QUERY) is attached
# MAGIC   → Create → Deploy
# MAGIC The app deploys in AU East and starts as a managed service principal.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Option B: Databricks CLI
# MAGIC ```bash
# MAGIC # 1. Sync the app source into the workspace
# MAGIC databricks sync session4_mcp_agents/app "/Workspace/Users/<you>/aemo-app" --full
# MAGIC
# MAGIC # 2. Create the app (first time only)
# MAGIC databricks apps create aemo-operations-agent
# MAGIC
# MAGIC # 3. Deploy the synced source
# MAGIC databricks apps deploy aemo-operations-agent \
# MAGIC   --source-code-path "/Workspace/Users/<you>/aemo-app"
# MAGIC
# MAGIC # 4. Watch status until RUNNING
# MAGIC databricks apps get aemo-operations-agent
# MAGIC ```
# MAGIC The CLI path is what you would wire into CI/CD for repeatable deploys.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Check deploy status from the SDK

# COMMAND ----------

try:
    app = ws.apps.get(name=APP_NAME)
    print(f"App    : {app.name}")
    print(f"URL    : {getattr(app, 'url', '(pending)')}")
    print(f"Status : {getattr(getattr(app, 'compute_status', None), 'state', 'UNKNOWN')}")
    sp = getattr(app, 'service_principal_client_id', None) or getattr(app, 'service_principal_name', None)
    print(f"App SP : {sp or '(check Apps UI)'}")
    print("\nUse the App SP value above in Lab 03 Section 4 (least-privilege grants).")
except Exception as e:
    print(f"App '{APP_NAME}' not found yet or not accessible: {e}")
    print("Deploy via Section 3.1 or 3.2 first, then re-run this cell.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Verify (8 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Health check `/api/health`
# MAGIC The backend exposes a health endpoint. From a terminal:
# MAGIC ```bash
# MAGIC APP_URL=$(databricks apps get aemo-operations-agent -o json | python -c "import sys,json;print(json.load(sys.stdin)['url'])")
# MAGIC curl -s -H "Authorization: Bearer $DATABRICKS_TOKEN" "$APP_URL/api/health"
# MAGIC # expect: {"status":"ok"}
# MAGIC ```

# COMMAND ----------

# Verify /api/health from the notebook using the current workspace credentials.
import requests

try:
    app = ws.apps.get(name=APP_NAME)
    app_url = getattr(app, "url", None)
    if not app_url:
        print("App URL not available yet — wait for status RUNNING.")
    else:
        token = ws.config.token or dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
        r = requests.get(f"{app_url.rstrip('/')}/api/health",
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        print(f"GET /api/health -> {r.status_code}")
        print(r.text[:300])
except Exception as e:
    print(f"Health check not run: {e}")
    print("Once the app is RUNNING, re-run. First request may cold-start (15-30s).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — SSO and service-principal auth
# MAGIC - **SSO:** open the app URL in a browser. Databricks OAuth redirects you to sign in — no API
# MAGIC   keys. Any user you grant `CAN_USE` reaches the app through workspace SSO.
# MAGIC - **Service principal:** the app itself runs as a managed SP. Its MCP tool calls and PT endpoint
# MAGIC   calls are attributed to that SP in `system.access.audit` (see Lab 03 Section 5) and in the AI
# MAGIC   Gateway inference table — not to the end user.
# MAGIC
# MAGIC Ask a test question in the browser UI (e.g. *"Average spot price in VIC1?"*), then confirm a
# MAGIC matching row appears in the audit query from Lab 03.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 5 — Share the app (4 min)
# MAGIC </div>
# MAGIC ```
# MAGIC Apps → aemo-operations-agent → Permissions → [+ Add]
# MAGIC   Add participants / a group → CAN_USE
# MAGIC ```
# MAGIC Onboarding and offboarding follow your identity provider groups — no per-user secrets.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 04 complete — DEPLOY ✅</strong><br>
# MAGIC   The governed agent is live as a React app in Databricks Apps, running in AU East as a managed
# MAGIC   service principal, reachable via Databricks SSO, with a verified <code>/api/health</code>
# MAGIC   endpoint and the PT endpoint attached as its only serving resource.
# MAGIC   <br><br>
# MAGIC   <strong>Next — Lab 05 (IMPROVE):</strong> capture user feedback from the deployed app, turn
# MAGIC   negatives into new golden rows, and re-run the Lab 02 evaluation to prove improvement.
# MAGIC </div>
