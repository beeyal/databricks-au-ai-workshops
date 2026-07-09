# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 03 — GOVERN: Guardrails, Residency, and Audit
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Session 4: Building AI Agents with MCP — Australian Energy Sector (Level 200)
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Lifecycle phase 3 of 5 &nbsp;•&nbsp; Build → Evaluate → <strong>Govern</strong> → Deploy → Improve
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>30 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01-02 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>Everything AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Focus</strong><br>Residency-forward governance
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will do
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | Residency guardrail | Prove the LLM is in-region PT; block cross-geo | 6 min |
# MAGIC | 2 | AI Gateway | Rate limits, usage tracking, inference tables | 8 min |
# MAGIC | 3 | Content guardrails | PII + safety guardrails on the endpoint | 5 min |
# MAGIC | 4 | UC access controls | The agent's service principal, least privilege | 5 min |
# MAGIC | 5 | Audit trail | `system.access.audit` correlating MCP tool calls | 6 min |
# MAGIC
# MAGIC **Why agents need more governance than notebooks:** one user message can trigger many tool
# MAGIC calls across three systems. The governance surface is proportionally larger.
# MAGIC
# MAGIC | Risk | Without controls | With this lab |
# MAGIC |------|------------------|---------------|
# MAGIC | Data leaves the region | LLM call routed cross-geo | In-region PT endpoint enforced + verified |
# MAGIC | Cost overrun | Unbounded PT calls | AI Gateway rate limits per service principal |
# MAGIC | Sensitive data exposure | Raw PII in prompts/outputs | PII + safety guardrails on the endpoint |
# MAGIC | No access boundary | Agent can read any table | UC grants scope the SP to `workshop_au.aemo` |
# MAGIC | Cannot investigate | "Something went wrong" | `system.access.audit`: every MCP call attributed |

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo", "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name (in-region)")
dbutils.widgets.text("agent_sp",    "",                     "Agent service principal (app SP) app id")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA_AEMO = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT = dbutils.widgets.get("pt_endpoint")
AGENT_SP    = dbutils.widgets.get("agent_sp")

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host : {HOST}")
print(f"Catalog.Schema : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint    : {PT_ENDPOINT}")
print(f"Agent SP       : {AGENT_SP or '(set after Lab 04 app deploy)'}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — Residency guardrail: verify the LLM stays in-region (6 min)
# MAGIC </div>
# MAGIC
# MAGIC <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #FF3621;">The cross-geo / residency block — the reason this workshop exists</strong><br>
# MAGIC   AEMO workloads must not route inference outside Australia East. A
# MAGIC   <strong>provisioned-throughput (PT) serving endpoint</strong> runs the model inside your
# MAGIC   workspace region. A <strong>pay-per-token / Foundation Model API</strong> endpoint may route
# MAGIC   cross-geo and is <strong>forbidden</strong>. This section verifies the agent is on a PT endpoint
# MAGIC   and documents how to block the pay-per-token alternative.
# MAGIC </div>

# COMMAND ----------

# Verify the agent endpoint is provisioned throughput (in-region), not pay-per-token.
ep = ws.serving_endpoints.get(PT_ENDPOINT)

entities = []
try:
    entities = ep.config.served_entities or []
except Exception:
    pass

print(f"Endpoint         : {PT_ENDPOINT}")
print(f"Ready state      : {getattr(getattr(ep, 'state', None), 'ready', 'UNKNOWN')}")
print("Served entities  :")
is_pt = False
for e in entities:
    name = getattr(e, "name", "?")
    ptc  = getattr(e, "provisioned_model_units", None) or getattr(e, "workload_size", None)
    if ptc:
        is_pt = True
    print(f"  - {name}  (provisioned/workload marker: {ptc})")

print()
if is_pt:
    print("PASS: endpoint has provisioned-throughput characteristics — inference stays in AU East.")
else:
    print("REVIEW: could not confirm PT markers. Verify in Serving UI that this is a PT endpoint,")
    print("        NOT a pay-per-token Foundation Model endpoint. Pay-per-token is cross-geo.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Blocking the cross-geo alternative.** In addition to using a PT endpoint, prevent the agent's
# MAGIC service principal from ever calling a pay-per-token endpoint:
# MAGIC ```
# MAGIC Serving → (each pay-per-token / FMAPI endpoint) → Permissions
# MAGIC   → ensure the agent SP has NO CAN_QUERY on any cross-geo endpoint
# MAGIC Only the in-region PT endpoint should grant CAN_QUERY to the agent SP (set in Lab 04).
# MAGIC ```
# MAGIC The residency guarantee is a combination of (1) the agent code pointing at the PT endpoint and
# MAGIC (2) UC/serving permissions denying the SP access to cross-geo endpoints.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — AI Gateway: rate limits, usage tracking, inference tables (8 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Usage tracking (the Monitor tab)
# MAGIC The AI Gateway records every call to the PT endpoint — from notebooks, the app, or direct API.
# MAGIC ```
# MAGIC Serving → au_east_llm_inregion → Monitor tab
# MAGIC   Token usage, request volume (incl. 429 rate-limited), latency p50/p90/p99
# MAGIC ```
# MAGIC For MCP agents, input tokens far exceed output — the system prompt + tool schemas + tool
# MAGIC results all count as input on every turn.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Enable the inference table (one row per request)
# MAGIC ```
# MAGIC Serving → au_east_llm_inregion → AI Gateway tab → Inference tables → Enable
# MAGIC   Destination: workshop_au.aemo.inference_au_east_llm_inregion  (in-region UC table)
# MAGIC ```
# MAGIC Calls from the deployed app appear with the app's service principal identity, not a user email.

# COMMAND ----------

INFERENCE_TABLE = f"{CATALOG}.{SCHEMA_AEMO}.inference_{PT_ENDPOINT.replace('-', '_')}"
print(f"Inference table: {INFERENCE_TABLE}\n")

try:
    df = spark.sql(f"""
        SELECT
            client_user_id,
            COUNT(*)                                            AS requests,
            SUM(usage.total_tokens)                             AS total_tokens,
            ROUND(AVG(databricks_output.latency_ms), 0)         AS avg_latency_ms,
            SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) AS errors
        FROM {INFERENCE_TABLE}
        WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
        GROUP BY client_user_id
        ORDER BY total_tokens DESC
        LIMIT 10
    """)
    df.show(truncate=60)
except Exception as e:
    print(f"Could not query inference table yet: {e}")
    print("Enable AI Gateway inference logging on the endpoint, then re-run after some calls.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Rate limits for the agent's service principal
# MAGIC Give the app SP a budget separate from interactive users.
# MAGIC ```
# MAGIC Serving → au_east_llm_inregion → AI Gateway tab → Rate limits → [+ Add rate limit]
# MAGIC ```
# MAGIC | Limit | Suggested value | Rationale |
# MAGIC |-------|-----------------|-----------|
# MAGIC | tokens/day per app SP | 500,000 | Cost ceiling |
# MAGIC | requests/minute per app SP | 60 | Throttles runaway agent loops |
# MAGIC | requests/minute default | 200 | Headroom for interactive notebook users |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Content guardrails: PII and safety (5 min)
# MAGIC </div>
# MAGIC
# MAGIC AI Gateway can screen prompts and responses at the endpoint — no agent code change needed.
# MAGIC ```
# MAGIC Serving → au_east_llm_inregion → AI Gateway tab → Guardrails
# MAGIC   • Safety     : block harmful/unsafe content in prompts and responses
# MAGIC   • PII        : detect/mask PII (e.g. participant contact details) — choose BLOCK or MASK
# MAGIC   • Invalid keywords / topics (optional): keep the agent inside the NEM domain
# MAGIC ```
# MAGIC Guardrails run in-region as part of the endpoint, so screened content never leaves AU East.

# COMMAND ----------

# MAGIC %md
# MAGIC **Guardrails are enforcement; the system prompt is guidance.** The Lab 01 prompt asks the agent
# MAGIC to stay in the NEM domain and cite sources; the Gateway guardrail is the hard control that a
# MAGIC prompt injection cannot talk its way past. Use both.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — UC access controls for the agent's service principal (5 min)
# MAGIC </div>
# MAGIC
# MAGIC The deployed app (Lab 04) runs as a managed service principal. Least privilege: the SP should
# MAGIC read only what the agent needs — the `workshop_au.aemo` schema and the UC functions — and
# MAGIC nothing else.

# COMMAND ----------

# Least-privilege grants for the agent SP. Fill the agent_sp widget with the app SP's application ID
# (available in the Apps UI after Lab 04), then run.
if AGENT_SP:
    grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{AGENT_SP}`",
        f"GRANT USE SCHEMA  ON SCHEMA  {CATALOG}.{SCHEMA_AEMO} TO `{AGENT_SP}`",
        f"GRANT SELECT      ON SCHEMA  {CATALOG}.{SCHEMA_AEMO} TO `{AGENT_SP}`",
        f"GRANT EXECUTE     ON SCHEMA  {CATALOG}.{SCHEMA_AEMO} TO `{AGENT_SP}`",
    ]
    for stmt in grants:
        try:
            spark.sql(stmt)
            print(f"OK   {stmt}")
        except Exception as e:
            print(f"WARN {stmt}\n     {e}")
    print("\nDeliberately NOT granted: any catalog/schema beyond workshop_au.aemo,")
    print("and NO CAN_QUERY on cross-geo pay-per-token endpoints.")
else:
    print("Set the 'agent_sp' widget to the app service principal's application ID (from Lab 04),")
    print("then re-run to apply least-privilege grants. Preview of statements:")
    for stmt in [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `<agent-sp>`",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO `<agent-sp>`",
        f"GRANT EXECUTE ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO `<agent-sp>`",
    ]:
        print(f"  {stmt}")

# COMMAND ----------

# MAGIC %md
# MAGIC The Genie Space and Vector Search index have their own scope: Genie can only query its trusted
# MAGIC assets, and the Vector Search MCP server only exposes the indexes under
# MAGIC `workshop_au.aemo`. Combined with the UC grants above, the agent cannot reach data outside the
# MAGIC AEMO schema — this is the answer to "can the agent read other tables?" (No.)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 5 — Audit trail: correlate MCP tool calls (6 min)
# MAGIC </div>
# MAGIC
# MAGIC Every MCP call is written to `system.access.audit` with `service_name = 'mcpServer'` and
# MAGIC `action_name = 'mcpToolsCall'`. One agent turn with three tool calls produces three rows, each
# MAGIC attributed to the calling identity (a user email in a notebook, the app SP in production).

# COMMAND ----------

# MAGIC %md
# MAGIC | Column | What it contains |
# MAGIC |--------|------------------|
# MAGIC | `event_time` | When the call happened |
# MAGIC | `user_identity.email` | Who made the call (user or SP) |
# MAGIC | `service_name` | `mcpServer` for all MCP calls |
# MAGIC | `action_name` | `mcpToolsCall` for tool invocations |
# MAGIC | `request_params.toolName` | The specific MCP tool called |
# MAGIC | `response.status_code` | 200 = success, 4xx/5xx = error |

# COMMAND ----------

# MAGIC %sql
# MAGIC -- All MCP tool calls in the last hour, most recent first.
# MAGIC SELECT
# MAGIC   event_time,
# MAGIC   user_identity.email       AS caller,
# MAGIC   request_params.toolName   AS tool_name,
# MAGIC   response.status_code       AS http_status
# MAGIC FROM system.access.audit
# MAGIC WHERE service_name = 'mcpServer'
# MAGIC   AND action_name  = 'mcpToolsCall'
# MAGIC   AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 50

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.1 — Which tools the agent used, and by whom

# COMMAND ----------

try:
    df = spark.sql("""
        SELECT
            request_params.toolName             AS tool_name,
            user_identity.email                 AS caller,
            COUNT(*)                            AS calls,
            SUM(CASE WHEN response.status_code = 200 THEN 1 ELSE 0 END) AS ok,
            SUM(CASE WHEN response.status_code != 200 THEN 1 ELSE 0 END) AS errors,
            MAX(event_time)                     AS last_seen
        FROM system.access.audit
        WHERE service_name = 'mcpServer'
          AND action_name  = 'mcpToolsCall'
          AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
        GROUP BY request_params.toolName, user_identity.email
        ORDER BY calls DESC
    """)
    if df.count() == 0:
        print("No MCP tool calls in the last 24h. Run Lab 01 questions, then re-run.")
    else:
        df.show(truncate=50)
except Exception as e:
    print(f"Could not query system.access.audit: {e}")
    print("Ask an admin: GRANT USAGE ON CATALOG system TO <your-user>")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.2 — Correlate an LLM call with the MCP tool calls it triggered
# MAGIC The audit log attributes every tool call to an identity and timestamp; MLflow traces (Lab 02)
# MAGIC show the reasoning within a single agent run. Together they answer "who asked what, which tools
# MAGIC ran, and did any fail" — the compliance chain for a regulated workload.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Governance summary
# MAGIC
# MAGIC | Control | What it gives you | Where to configure |
# MAGIC |---------|-------------------|--------------------|
# MAGIC | In-region PT endpoint | Inference never leaves AU East | Serving → PT endpoint |
# MAGIC | Deny cross-geo endpoints | No pay-per-token path for the SP | Serving → FMAPI endpoint → Permissions |
# MAGIC | AI Gateway rate limits | Cost + runaway-loop protection | AI Gateway → Rate limits |
# MAGIC | AI Gateway inference table | Per-request usage log (in-region UC) | AI Gateway → Inference tables |
# MAGIC | PII + Safety guardrails | Sensitive-content enforcement | AI Gateway → Guardrails |
# MAGIC | UC least-privilege grants | Agent SP scoped to `workshop_au.aemo` | Catalog → grants |
# MAGIC | `system.access.audit` | Every MCP call attributed to an identity | system catalog |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 03 complete — GOVERN ✅</strong><br>
# MAGIC   The agent now has a residency guarantee (in-region PT + cross-geo denial), AI Gateway rate
# MAGIC   limits and usage tracking, PII/safety guardrails, least-privilege UC access for its service
# MAGIC   principal, and a full <code>system.access.audit</code> trail for every MCP tool call.
# MAGIC   <br><br>
# MAGIC   <strong>Next — Lab 04 (DEPLOY):</strong> ship the governed agent as a React app in Databricks
# MAGIC   Apps, running as that service principal in AU East.
# MAGIC </div>
