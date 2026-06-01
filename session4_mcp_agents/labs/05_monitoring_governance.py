# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 05: Monitoring & Governing Your MCP Agent
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Regulated Industries
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     From demo to production: visibility, cost control, and audit trail
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Estimated time</strong><br>30 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Prerequisites</strong><br>Labs 01–04 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>Data residency</strong><br>All audit data in AU East
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong>SOCI Act relevance</strong><br>Critical infrastructure compliance evidence
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will learn
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | AI Gateway | Usage dashboard, inference table, rate limits per SP | 10 min |
# MAGIC | 2 | MLflow Traces | Trace UI, slow/failed MCP call detection | 10 min |
# MAGIC | 3 | Audit Logging | `system.access.audit` for MCP, SOCI Act + Privacy Act evidence, anomaly alerts | 10 min |
# MAGIC
# MAGIC **Why agents need more governance than notebooks:** a single user message can trigger ten tool calls across three systems. The governance surface is proportionally larger.
# MAGIC
# MAGIC | Risk | Without controls | With this lab |
# MAGIC |------|-----------------|---------------|
# MAGIC | Cost overrun | Unbounded PT endpoint calls | AI Gateway rate limits per SP |
# MAGIC | Data exfiltration | No record of which tables the agent queried | `system.access.audit` logs every MCP call |
# MAGIC | Incident investigation | "Something went wrong" — no detail | MLflow traces: every tool call and LLM step |
# MAGIC | SOCI Act 2018 | Cannot demonstrate AI access controls | Full chain: user → agent → tool → data asset |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Workshop configuration

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo", "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("app_name",    "aemo-operations-agent","App name (from Lab 04)")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA_AEMO = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT = dbutils.widgets.get("pt_endpoint")
APP_NAME    = dbutils.widgets.get("app_name")

from databricks.sdk import WorkspaceClient
ws = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host  : {HOST}")
print(f"Catalog.Schema  : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint     : {PT_ENDPOINT}")
print(f"App name        : {APP_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — AI Gateway for MCP Agents (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Navigate to the AI Gateway usage dashboard
# MAGIC
# MAGIC The AI Gateway records every call to your PT endpoint — from notebooks, Apps, or direct API. It is your first stop for cost and performance questions.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Serving → au_east_llm_inregion → Monitor tab
# MAGIC ```
# MAGIC
# MAGIC **What the Monitor tab shows:**
# MAGIC ```
# MAGIC Token usage (24h):  input 3,891 / output 632
# MAGIC Request volume:     44 success / 3 rate-limited (429)
# MAGIC Latency:            p50 987ms  p90 2,341ms  p99 4,892ms
# MAGIC ```
# MAGIC
# MAGIC For MCP agents, input tokens are consistently higher than output — the system prompt + tool schemas + tool results all count as input on every turn.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Query the AI Gateway inference table
# MAGIC
# MAGIC The inference table stores one row per request — richer than the metrics chart. Navigate to it:
# MAGIC ```
# MAGIC Left sidebar → Serving → au_east_llm_inregion → AI Gateway tab
# MAGIC   Inference table: workshop_au.aemo.inference_au_east_llm_inregion
# MAGIC ```
# MAGIC
# MAGIC Calls from the deployed App appear with the App SP identity (`app-sp-aemo-...`), not your personal email.

# COMMAND ----------

INFERENCE_TABLE = f"{CATALOG}.{SCHEMA_AEMO}.inference_{PT_ENDPOINT.replace('-', '_')}"
print(f"Inference table: {INFERENCE_TABLE}\n")

sql_usage_summary = f"""
-- AI Gateway usage summary — last 24 hours
SELECT
  DATE_TRUNC('hour', timestamp)                          AS hour,
  client_user_id,
  COUNT(*)                                               AS request_count,
  SUM(usage.prompt_tokens)                               AS input_tokens,
  SUM(usage.completion_tokens)                           AS output_tokens,
  ROUND(AVG(databricks_output.latency_ms), 0)            AS avg_latency_ms,
  SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)    AS rate_limited_count
FROM {INFERENCE_TABLE}
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
GROUP BY 1, 2
ORDER BY 1 DESC, 4 DESC
"""
print(sql_usage_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Query inference table with PySpark

# COMMAND ----------

try:
    df = spark.sql(f"""
        SELECT
            client_user_id,
            COUNT(*)                                           AS requests,
            SUM(usage.total_tokens)                           AS total_tokens,
            ROUND(AVG(databricks_output.latency_ms), 0)       AS avg_latency_ms,
            MAX(databricks_output.latency_ms)                 AS max_latency_ms,
            SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) AS errors
        FROM {INFERENCE_TABLE}
        WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
        GROUP BY client_user_id
        ORDER BY total_tokens DESC
        LIMIT 10
    """)
    print(f"Top callers to {PT_ENDPOINT} — last 7 days:\n")
    df.show(truncate=60)
except Exception as e:
    print(f"Could not query inference table: {e}")
    print("\nPossible causes:")
    print("  - AI Gateway inference logging not enabled on the endpoint")
    print("    -> Serving -> endpoint -> AI Gateway tab -> enable logging")
    print("  - No calls in the last 7 days")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Set rate limits for the agent's service principal
# MAGIC
# MAGIC In production, give the App SP a budget separate from interactive users.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Serving → au_east_llm_inregion → AI Gateway tab → Rate limits
# MAGIC   → [+ Add rate limit] → select principal → set type and value
# MAGIC ```
# MAGIC
# MAGIC | Limit type | Suggested value | Rationale |
# MAGIC |-----------|----------------|-----------|
# MAGIC | `tokens/day` per App SP | 500,000 | ~AUD $5–10/day ceiling at PT pricing |
# MAGIC | `requests/minute` per App SP | 60 | Throttles runaway loops — healthy agent handles <10/min |
# MAGIC | `requests/minute` default | 200 | Headroom for interactive notebook users |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — MLflow Traces for Agent Debugging (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Navigate to the MLflow Traces UI
# MAGIC
# MAGIC MLflow Tracing records every step of an agent run — the user question, each LLM call, each tool invocation, inputs/outputs, latency, and errors.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Experiments → /Apps/aemo-operations-agent → Traces tab
# MAGIC ```
# MAGIC
# MAGIC **Reading the trace tree (click any row):**
# MAGIC ```
# MAGIC AgentRun (2,341ms)
# MAGIC  ├── LLMCall — tool selection (456ms)
# MAGIC  │     Output: tool_call { name: "ask_genie", args: {...} }
# MAGIC  ├── MCPToolCall — ask_genie (1,203ms)
# MAGIC  │     Input:  { query: "average spot price VIC yesterday" }
# MAGIC  │     Output: { sql: "...", result: [{"avg(RRP)": 142.50}] }
# MAGIC  └── LLMCall — synthesise answer (682ms)
# MAGIC        Output: "The average spot price in VIC1 yesterday was $142.50/MWh..."
# MAGIC ```
# MAGIC
# MAGIC | Symptom | Where to look |
# MAGIC |---------|--------------|
# MAGIC | Wrong answer | LLMCall (synthesis) input — did the tool return what you expected? |
# MAGIC | Slow response | Which node has the highest duration — LLM or MCP tool? |
# MAGIC | Tool not called | First LLMCall output — did the LLM select the right tool? |
# MAGIC | Tool call failed | MCPToolCall output — error message from the UC function |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Query MLflow traces programmatically

# COMMAND ----------

import mlflow
from mlflow.entities import ViewType

EXPERIMENT_NAME = "/Apps/aemo-operations-agent"

try:
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        print(f"Experiment '{EXPERIMENT_NAME}' not found.")
        print("Run some queries through the deployed app first, then re-run this cell.")
    else:
        print(f"Experiment found: {experiment.name}  (ID: {experiment.experiment_id})\n")
        recent_runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="",
            run_view_type=ViewType.ACTIVE_ONLY,
            max_results=20,
            order_by=["start_time DESC"],
        )
        if recent_runs.empty:
            print("No runs found yet. Run queries through the app to generate traces.")
        else:
            display_cols = [c for c in recent_runs.columns
                            if any(k in c for k in ["start_time", "end_time", "status", "metrics", "params"])]
            print(f"Recent runs ({len(recent_runs)}):\n")
            print(recent_runs[display_cols[:8]].to_string(index=False))
except Exception as e:
    print(f"Could not query MLflow: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Find the slowest MCP tool calls

# COMMAND ----------

try:
    traces = mlflow.search_traces(
        experiment_names=[EXPERIMENT_NAME],
        filter_string="",
        max_results=50,
    )

    if not traces:
        print("No traces found. Run some queries through the app first.")
    else:
        print(f"Found {len(traces)} traces. Analysing MCP tool call latencies...\n")
        tool_latencies = []
        for trace in traces:
            for span in trace.data.spans:
                if span.span_type in ("TOOL", "RETRIEVER") or "mcp" in span.name.lower():
                    duration_ms = (span.end_time_ns - span.start_time_ns) / 1_000_000
                    tool_latencies.append({
                        "tool_name":   span.name[:40],
                        "duration_ms": round(duration_ms, 0),
                        "status":      span.status.status_code if span.status else "unknown",
                        "trace_id":    trace.info.trace_id[:12] + "...",
                    })

        if tool_latencies:
            tool_latencies.sort(key=lambda x: x["duration_ms"], reverse=True)
            print(f"{'Tool name':<42} {'Duration ms':>12} {'Status':<12} {'Trace'}")
            print("-" * 90)
            for row in tool_latencies[:15]:
                print(f"{row['tool_name']:<42} {row['duration_ms']:>12.0f} {str(row['status']):<12} {row['trace_id']}")
        else:
            print("No MCP tool spans found. Ensure app.py has MLflow autolog or manual tracing enabled.")

except Exception as e:
    print(f"Trace query failed: {e}")
    print(f"MLflow search_traces requires MLflow 2.17+. Installed: {mlflow.__version__}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Find failed tool calls

# COMMAND ----------

try:
    traces = mlflow.search_traces(
        experiment_names=[EXPERIMENT_NAME],
        filter_string="",
        max_results=100,
    )

    failed_spans = []
    for trace in traces:
        for span in trace.data.spans:
            status = span.status.status_code if span.status else "UNSET"
            if str(status) in ("ERROR", "INTERNAL_ERROR", "UNSET"):
                failed_spans.append({
                    "trace_id":  trace.info.trace_id[:16] + "...",
                    "span_name": span.name[:40],
                    "status":    str(status),
                    "error":     (span.attributes or {}).get("exception.message", "—")[:60],
                })

    if not failed_spans:
        print("No failed spans found in recent traces. All MCP tool calls completed successfully.")
    else:
        print(f"Found {len(failed_spans)} failed span(s):\n")
        for row in failed_spans:
            print(f"  Trace:  {row['trace_id']}")
            print(f"  Span:   {row['span_name']}")
            print(f"  Status: {row['status']}")
            print(f"  Error:  {row['error']}\n")

except Exception as e:
    print(f"Trace query failed: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Audit Logging for MCP Calls (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — What `system.access.audit` records for MCP
# MAGIC
# MAGIC Every MCP call is written to `system.access.audit` with `service_name = 'mcpServer'`. One agent call with 3 tool invocations produces 3 rows — each attributed to the calling identity.
# MAGIC
# MAGIC **Navigate:**
# MAGIC ```
# MAGIC Left sidebar → Catalog → system catalog → access schema → audit table
# MAGIC   Or: SELECT * FROM system.access.audit WHERE service_name = 'mcpServer' LIMIT 10
# MAGIC ```
# MAGIC
# MAGIC | Column | What it contains |
# MAGIC |--------|-----------------|
# MAGIC | `event_time` | When the call happened |
# MAGIC | `user_identity.email` | Who made the call (user or SP) |
# MAGIC | `service_name` | `mcpServer` for all MCP calls |
# MAGIC | `action_name` | The specific tool called (top-level column) |
# MAGIC | `response.statusCode` | 200 = success, 4xx/5xx = error |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Query all MCP tool calls from your agent

# COMMAND ----------

# MAGIC %sql
# MAGIC -- All MCP tool calls in the last hour
# MAGIC SELECT
# MAGIC   event_time,
# MAGIC   user_identity.email                              AS user,
# MAGIC   action_name                                     AS mcp_action,
# MAGIC   request_params                                  AS request_params,
# MAGIC   response.statusCode                             AS http_status
# MAGIC FROM system.access.audit
# MAGIC WHERE service_name = 'mcpServer'
# MAGIC   AND action_name  = 'mcpToolsCall'
# MAGIC   AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 50

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Find which data assets the agent accessed most

# COMMAND ----------

sql_asset_access = """
-- Data asset access frequency via MCP — last 7 days
SELECT
  action_name                                        AS mcp_action,
  user_identity.email                                AS accessed_by,
  COUNT(*)                                           AS call_count,
  SUM(CASE WHEN response.statusCode = 200 THEN 1 ELSE 0 END) AS success_count,
  SUM(CASE WHEN response.statusCode != 200 THEN 1 ELSE 0 END) AS error_count,
  MIN(event_time)                                    AS first_seen,
  MAX(event_time)                                    AS last_seen
FROM system.access.audit
WHERE service_name = 'mcpServer'
  AND action_name  = 'mcpToolsCall'
  AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
GROUP BY 1, 2
ORDER BY call_count DESC
"""
print("Run this in a SQL cell or DBSQL editor to see data asset access by agent:\n")
print(sql_asset_access)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — MCP Audit and SOCI Act Compliance
# MAGIC
# MAGIC The SOCI Act 2018 and Privacy Act 1988 require audit trails for critical infrastructure data access, including access by automated systems. The controls in this workshop provide the following compliance evidence:
# MAGIC
# MAGIC | SOCI Act 2018 requirement | Control | Evidence location |
# MAGIC |--------------------------|---------|-------------------|
# MAGIC | Asset access is logged | Every MCP call → `system.access.audit` | `WHERE service_name='mcpServer' AND action_name='mcpToolsCall'` |
# MAGIC | Access attributed to an identity | App runs as named SP; notebook calls use user email | `user_identity.email` column |
# MAGIC | Access controls are enforced | UC function permissions control which tools the agent can call | UC audit + function GRANT history |
# MAGIC | Rate limits prevent abuse | AI Gateway per-SP rate limits | AI Gateway metrics |
# MAGIC | Agent behaviour is traceable | MLflow traces: every reasoning step | MLflow experiment traces UI |
# MAGIC | Data stays in region | All MCP endpoints are workspace-local AU East | No egress in Azure network logs |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Detection query: all MCP tools called in the last 24 hours

# COMMAND ----------

try:
    df = spark.sql("""
        SELECT
            action_name                                        AS tool_name,
            COUNT(DISTINCT user_identity.email)                AS distinct_callers,
            COUNT(*)                                           AS total_calls,
            MIN(event_time)                                    AS first_call,
            MAX(event_time)                                    AS last_call
        FROM system.access.audit
        WHERE service_name = 'mcpServer'
          AND action_name  = 'mcpToolsCall'
          AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
        GROUP BY tool_name
        ORDER BY total_calls DESC
    """)

    if df.count() == 0:
        print("No MCP tool calls found in the last 24 hours.")
        print("Trigger some queries through the app or notebook, then re-run.")
    else:
        print("MCP tool calls — last 24 hours:\n")
        df.show(truncate=50)

except Exception as e:
    print(f"Could not query system.access.audit: {e}")
    print("\nEnsure you have USAGE privilege on the system catalog.")
    print("Ask your workspace admin: GRANT USAGE ON CATALOG system TO <your-user>")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Anomaly detection: MCP calls outside business hours

# COMMAND ----------

sql_after_hours = """
-- MCP calls outside business hours (before 7am or after 7pm AEST)
SELECT
  event_time,
  user_identity.email                          AS caller,
  action_name                                  AS tool_called,
  HOUR(CONVERT_TIMEZONE('UTC', 'Australia/Sydney', event_time)) AS hour_aest
FROM system.access.audit
WHERE service_name = 'mcpServer'
  AND action_name  = 'mcpToolsCall'
  AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  AND (
    HOUR(CONVERT_TIMEZONE('UTC', 'Australia/Sydney', event_time)) < 7
    OR
    HOUR(CONVERT_TIMEZONE('UTC', 'Australia/Sydney', event_time)) > 19
  )
ORDER BY event_time DESC
LIMIT 20
"""
print("After-hours MCP call detection query (run in SQL cell or DBSQL):\n")
print(sql_after_hours)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.7 — Create a DBSQL Alert for anomalous MCP activity
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → SQL Editor → paste the after-hours query above → Run → [Save]
# MAGIC   → [+ Create Alert] (top right of the query editor)
# MAGIC
# MAGIC Alert settings:
# MAGIC   Name:       AEMO Agent MCP After-Hours Activity
# MAGIC   Condition:  count(*) >= 1   (trigger if any after-hours calls appear)
# MAGIC   Schedule:   Every 1 hour
# MAGIC   Notify:     email or Slack channel
# MAGIC   → [Create Alert]
# MAGIC ```
# MAGIC
# MAGIC Results remain in `system.access.audit` — no extra data movement required. Roll out-of-hours call detection as a standard Databricks Job to close the SOCI Act 2018 continuous monitoring loop.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary — Lab 05
# MAGIC
# MAGIC | Control | What it gives you | Where to configure |
# MAGIC |---------|------------------|--------------------|
# MAGIC | AI Gateway Monitor tab | Token usage, latency, error rate | Serving → endpoint → Monitor |
# MAGIC | AI Gateway inference table | Per-request log: who, when, how many tokens | Serving → endpoint → AI Gateway tab |
# MAGIC | AI Gateway rate limits | Budget caps per user / per SP | Serving → endpoint → AI Gateway → Rate limits |
# MAGIC | MLflow traces | Full agent reasoning + tool call tree | Experiments → your experiment → Traces |
# MAGIC | `system.access.audit` | Every MCP call attributed to an identity | Catalog → system → access → audit |
# MAGIC | DBSQL Alert | Automated anomaly detection and notification | SQL Editor → Save → Create Alert |
# MAGIC
# MAGIC **SOCI Act 2018 + Privacy Act compliance checklist after Labs 01–05:**
# MAGIC - All LLM inference stays in AU East (PT endpoint + workspace-local MCP)
# MAGIC - Every agent call attributed to a named identity in `system.access.audit`
# MAGIC - UC function permissions control which tools the agent can call
# MAGIC - AI Gateway rate limits prevent runaway cost and abuse
# MAGIC - MLflow traces provide post-hoc review of agent reasoning
# MAGIC - DBSQL alerts detect and notify on anomalous patterns
# MAGIC - App permissions use SSO groups — onboarding/offboarding via AD
# MAGIC
# MAGIC **Workshop 2c complete.** You have built, deployed, and governed an MCP agent end to end — Lab 01 setup, Lab 02 UC Functions as tools, Lab 03 multi-MCP LangGraph agent, Lab 04 Databricks App, Lab 05 monitoring and audit. The full stack runs in Australia East. Every call is attributable. Every tool is governed by Unity Catalog.
