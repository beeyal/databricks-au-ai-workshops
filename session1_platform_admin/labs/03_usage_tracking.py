# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">Lab 03: Usage Tracking &amp; Cost Attribution</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries · Databricks</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | ~30 minutes |
# MAGIC | **Prerequisites** | Lab 01 complete — AI Gateway endpoint with usage tracking enabled |
# MAGIC | **By the end** | Cost attribution view built, budget alert configured, reference SQL card printed |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 0: Setup & Permissions Check</h2>
# MAGIC </div>
# MAGIC
# MAGIC System tables used in this lab:
# MAGIC `system.ai_gateway.usage` (~15 min latency) | `system.access.audit` (~1 hr) | `system.billing.usage` (~2 hrs) | `system.serving.served_entities` (near real-time)

# COMMAND ----------

dbutils.widgets.text("workspace_url", "https://<your-workspace>.azuredatabricks.net", "Workspace URL")
dbutils.widgets.text("catalog",       "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",        "ai_governance",        "Schema name")
dbutils.widgets.text("gw_endpoint",   "au_east_llm_inregion", "AI Gateway endpoint name")

WORKSPACE_URL_W = dbutils.widgets.get("workspace_url")
CATALOG_W       = dbutils.widgets.get("catalog")
SCHEMA_W        = dbutils.widgets.get("schema")
GW_ENDPOINT     = dbutils.widgets.get("gw_endpoint")

print(f"Workspace URL  : {WORKSPACE_URL_W}")
print(f"Catalog.Schema : {CATALOG_W}.{SCHEMA_W}")
print(f"GW endpoint    : {GW_ENDPOINT}")

# COMMAND ----------

SYSTEM_TABLES = [
    "system.ai_gateway.usage",
    "system.access.audit",
    "system.billing.usage",
    "system.serving.served_entities",
]

print("Checking access to system tables...\n")
for table in SYSTEM_TABLES:
    try:
        count = spark.sql(f"SELECT COUNT(*) AS n FROM {table}").collect()[0]["n"]
        print(f"  [OK]   {table} — {count:,} rows accessible")
    except Exception as e:
        err = str(e)[:90]
        print(f"  [FAIL] {table}")
        print(f"         {err}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Audit Logging — Quick Check

# COMMAND ----------

# Verify audit logging is active and AI events are flowing.
# Queries system.access.audit for recent AI-related actions.
try:
    audit_check = spark.sql("""
        SELECT
            service_name,
            action_name,
            COUNT(*) AS event_count
        FROM system.access.audit
        WHERE event_date >= current_date() - INTERVAL 7 DAYS
          AND service_name IN ('serverlessRealTimeInference', 'aibiGenie', 'aiPlayground', 'modelServing')
        GROUP BY 1, 2
        ORDER BY event_count DESC
        LIMIT 10
    """)
    row_count = audit_check.count()
    if row_count > 0:
        print(f"PASS — AI events present in system.access.audit ({row_count} distinct service/action combinations in last 7 days)")
        display(audit_check)
    else:
        print("WARNING — No AI events in last 7 days. Run AI Playground once, then re-check.")
except Exception as e:
    print(f"CANNOT VERIFY — {e}")
    print("ACTION: Enable system tables in Account Console → Settings → System tables")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 1: Querying system.ai_gateway.usage</h2>
# MAGIC </div>
# MAGIC
# MAGIC Each row represents one request routed through an AI Gateway endpoint. ~15 minute latency — data from Labs 01/02 may already be visible.
# MAGIC
# MAGIC 🖱️ **UI:** AI Gateway → [your endpoint] → **Metrics tab** — token consumption chart, request latency, error rates (200/400/429 breakdown), and per-request log.

# COMMAND ----------

# View the full schema of the ai_gateway usage table
display(spark.sql("DESCRIBE system.ai_gateway.usage"))

# COMMAND ----------

# Note: system.ai_gateway.usage populates once AI Gateway traffic flows through your endpoint.
# If you see 0 rows: (1) confirm endpoint is Ready, (2) confirm at least one request was sent,
# (3) wait ~15 minutes.

# COMMAND ----------

# Recent requests: date, endpoint, team, project, token counts — last 7 days
recent_requests = spark.sql("""
  SELECT
    DATE(event_time)                                      AS request_date,
    endpoint_name,
    destination_model,
    request_tags['team']                                  AS team,
    request_tags['project']                               AS project,
    COUNT(*)                                              AS request_count,
    SUM(input_tokens)                                     AS total_input_tokens,
    SUM(output_tokens)                                    AS total_output_tokens,
    SUM(input_tokens + output_tokens)                     AS total_tokens,
    ROUND(AVG(latency_ms), 0)                             AS avg_latency_ms,
    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END)   AS successful_requests,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)   AS rate_limited_requests,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)   AS blocked_requests
  FROM system.ai_gateway.usage
  WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1, 2, 3, 4, 5
  ORDER BY request_date DESC, total_tokens DESC
""")

display(recent_requests)

# COMMAND ----------

# Top users by token consumption — last 30 days
top_users = spark.sql("""
  SELECT
    requester                                             AS user_id,
    COUNT(*)                                              AS request_count,
    SUM(input_tokens + output_tokens)                     AS total_tokens,
    ROUND(AVG(latency_ms), 0)                             AS avg_latency_ms,
    COUNT(DISTINCT endpoint_name)                         AS endpoints_used,
    MAX(DATE(event_time))                                 AS last_seen
  FROM system.ai_gateway.usage
  WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1
  ORDER BY total_tokens DESC
  LIMIT 20
""")

display(top_users)

# COMMAND ----------

# Daily trend — capacity planning and spike detection
daily_trend = spark.sql("""
  SELECT
    DATE(event_time)                                         AS usage_date,
    endpoint_name,
    SUM(input_tokens + output_tokens)                        AS total_tokens,
    COUNT(*)                                                 AS request_count,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)      AS rate_limited
  FROM system.ai_gateway.usage
  WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1, 2
  ORDER BY 1, 2
""")

display(daily_trend)

# COMMAND ----------

# Blocked request analysis — status_code = 400 (blocked by guardrail), 429 (rate limited)
# Note: guardrail_action and guardrail_type columns are not exposed in system.ai_gateway.usage.
guardrail_hits = spark.sql("""
  SELECT
    DATE(event_time)                             AS event_date,
    endpoint_name,
    CASE
      WHEN status_code = 400 THEN 'BLOCKED (400)'
      WHEN status_code = 429 THEN 'RATE_LIMITED (429)'
      ELSE CONCAT('OTHER (', CAST(status_code AS STRING), ')')
    END                                          AS outcome,
    COUNT(*)                                     AS hit_count,
    COUNT(DISTINCT requester)                    AS unique_users
  FROM system.ai_gateway.usage
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND status_code != 200
  GROUP BY 1, 2, 3
  ORDER BY 1 DESC, hit_count DESC
""")

display(guardrail_hits)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 2: Querying system.access.audit for AI Events</h2>
# MAGIC </div>
# MAGIC
# MAGIC | Action type | Service name | Description |
# MAGIC |---|---|---|
# MAGIC | `queryEndpoint` | `modelServing` | Serving endpoint called (inference traffic) |
# MAGIC | `genieConversation` | `aibiGenie` | Genie Space conversation |
# MAGIC | `aiPlaygroundQuery` | `aiPlayground` | AI Playground used |
# MAGIC | `putInferenceEndpointAiGateway` | `serverlessRealTimeInference` | AI Gateway config created or updated |
# MAGIC | `changeInferenceEndpointAcl` | `serverlessRealTimeInference` | Endpoint permission change |
# MAGIC
# MAGIC > `modelServing` covers inference calls and non-AI-Gateway endpoint lifecycle. AI Gateway configuration actions appear under `serverlessRealTimeInference`.
# MAGIC
# MAGIC 🖱️ **UI:** Left sidebar → Catalog → system → access → audit → Sample Data tab.

# COMMAND ----------

# Model serving inference calls — last 7 days
serving_calls = spark.sql("""
  SELECT
    DATE(event_time)                AS event_date,
    action_name,
    user_identity.email             AS user_email,
    request_params['endpointName']  AS endpoint_name,
    response.status_code           AS response_code,
    COUNT(*)                        AS call_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
    AND service_name = 'modelServing'
    AND action_name = 'queryEndpoint'
  GROUP BY 1, 2, 3, 4, 5
  ORDER BY 1 DESC, call_count DESC
""")

display(serving_calls)

# COMMAND ----------

# Genie Space usage — last 7 days
genie_usage = spark.sql("""
  SELECT
    DATE(event_time)                    AS event_date,
    user_identity.email                 AS user_email,
    action_name,
    request_params['spaceId']           AS space_id,
    COUNT(*)                            AS query_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
    AND service_name = 'aibiGenie'
  GROUP BY 1, 2, 3, 4
  ORDER BY 1 DESC, query_count DESC
""")

display(genie_usage)

# COMMAND ----------

# AI Playground usage — flag for security review if regulated-data users appear here
# Note: audit records the activity but NOT the prompt content
playground_usage = spark.sql("""
  SELECT
    DATE(event_time)                AS event_date,
    user_identity.email             AS user_email,
    COUNT(*)                        AS session_count,
    MAX(event_time)                 AS last_use
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND service_name = 'aiPlayground'
  GROUP BY 1, 2
  ORDER BY 1 DESC, session_count DESC
""")

display(playground_usage)

# COMMAND ----------

# AI Gateway configuration changes — change management audit evidence
# AI Gateway config events appear under service_name = 'serverlessRealTimeInference', NOT 'modelServing'.
gateway_changes = spark.sql("""
  SELECT
    event_time,
    user_identity.email             AS changed_by,
    action_name,
    request_params['endpointName']  AS endpoint_name,
    response.status_code           AS result_code,
    request_params                  AS change_details
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 90 DAYS
    AND service_name = 'serverlessRealTimeInference'
    AND action_name IN (
      'putInferenceEndpointAiGateway',
      'deleteInferenceEndpointAiGateway',
      'changeInferenceEndpointAcl',
      'createServingEndpoint',
      'updateServingEndpoint',
      'deleteServingEndpoint'
    )
  ORDER BY event_time DESC
""")

display(gateway_changes)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 3: Cost Attribution View — By Team and Project</h2>
# MAGIC </div>
# MAGIC
# MAGIC Applications pass cost centre tags via `databricks-request-tag` HTTP header (e.g. `team=network-ops;project=meter-anomaly`). These appear in `system.ai_gateway.usage.request_tags` as a MAP column.
# MAGIC
# MAGIC 🖱️ **UI:** After creating the view below, browse it via Catalog → [catalog] → [schema] → `ai_gateway_cost_attribution`.

# COMMAND ----------

# Token pricing — illustrative blended rates. Update to contracted rates.
# These are NOT published list prices — for reference only.
#   databricks-claude-haiku-4-5  : ~$1.00/1M input, ~$5.00/1M output  (Provisioned Throughput)
#   databricks-claude-sonnet-4-6 : ~$3.00/1M input, ~$15.00/1M output (Provisioned Throughput)

ILLUSTRATIVE_INPUT_RATE_PER_1M  = 0.90   # AUD — update to contracted rate
ILLUSTRATIVE_OUTPUT_RATE_PER_1M = 2.70   # AUD — update to contracted rate

print(f"Illustrative blended rates: ${ILLUSTRATIVE_INPUT_RATE_PER_1M}/1M input, ${ILLUSTRATIVE_OUTPUT_RATE_PER_1M}/1M output (AUD)")

# COMMAND ----------

CATALOG_NAME = CATALOG_W
SCHEMA_NAME  = SCHEMA_W

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

create_view_sql = f"""
CREATE OR REPLACE VIEW {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution AS
WITH usage_base AS (
  SELECT
    DATE(event_time)                                    AS usage_date,
    endpoint_name,
    destination_model,
    COALESCE(request_tags['team'],        'untagged')   AS team,
    COALESCE(request_tags['project'],     'untagged')   AS project,
    COALESCE(request_tags['environment'], 'unknown')    AS environment,
    requester                                           AS user_id,
    COUNT(*)                                            AS request_count,
    SUM(CASE WHEN status_code = 200 THEN input_tokens  ELSE 0 END) AS input_tokens,
    SUM(CASE WHEN status_code = 200 THEN output_tokens ELSE 0 END) AS output_tokens,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)  AS rate_limited_requests,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)  AS blocked_requests,
    AVG(CASE WHEN status_code = 200 THEN latency_ms END) AS avg_latency_ms
  FROM system.ai_gateway.usage
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  usage_date, endpoint_name, destination_model, team, project, environment, user_id,
  request_count, input_tokens, output_tokens,
  input_tokens + output_tokens                                      AS total_tokens,
  rate_limited_requests, blocked_requests,
  ROUND(avg_latency_ms, 0)                                          AS avg_latency_ms,
  ROUND(input_tokens  / 1000000.0 * 0.90, 4)                       AS est_input_cost_aud,
  ROUND(output_tokens / 1000000.0 * 2.70, 4)                       AS est_output_cost_aud,
  ROUND((input_tokens / 1000000.0 * 0.90) +
        (output_tokens / 1000000.0 * 2.70), 4)                     AS est_total_cost_aud
FROM usage_base
"""

# TODO: Uncomment to create the view
# spark.sql(create_view_sql)
# print(f"View created: {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution")

print("View creation SQL is ready — uncomment to execute.")
print(f"Target view: {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution")

# COMMAND ----------

# Monthly cost by team — for internal chargeback and finance reporting
try:
    cost_by_team = spark.sql(f"""
      SELECT
        DATE_TRUNC('month', usage_date)     AS billing_month,
        team,
        SUM(request_count)                  AS total_requests,
        SUM(total_tokens)                   AS total_tokens,
        ROUND(SUM(est_total_cost_aud), 2)   AS estimated_cost_aud
      FROM {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution
      GROUP BY 1, 2
      ORDER BY 1 DESC, estimated_cost_aud DESC
    """)
    display(cost_by_team)
except Exception as _e:
    print(f"[SKIP] View not yet created — uncomment the spark.sql(create_view_sql) block above and re-run first.")
    print(f"       Error: {_e}")

# COMMAND ----------

# TODO: Uncomment to export cost attribution to a UC volume for finance reporting
# from datetime import date as _date
# spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.cost_reports")
# (cost_by_team.coalesce(1).write
#     .mode("overwrite").option("header", "true")
#     .csv(f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/cost_reports/cost_by_team_{_date.today().strftime('%Y-%m')}.csv"))

print("Cost attribution export is commented out — uncomment after view is created.")

# COMMAND ----------

# Identify requests without team/project tags — these cannot be attributed to a cost centre
untagged_requests = spark.sql("""
  SELECT
    DATE(event_time)                    AS request_date,
    endpoint_name,
    requester                           AS user_id,
    COUNT(*)                            AS untagged_request_count,
    SUM(input_tokens + output_tokens)   AS untagged_tokens
  FROM system.ai_gateway.usage
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND status_code = 200
    AND (
      request_tags['team']    IS NULL
      OR request_tags['project'] IS NULL
    )
  GROUP BY 1, 2, 3
  ORDER BY 1 DESC, untagged_tokens DESC
""")

display(untagged_requests)
print("\nNote: Untagged requests indicate applications not passing the 'databricks-request-tag' header.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 4: Usage Charts</h2>
# MAGIC </div>
# MAGIC
# MAGIC Run each cell and click the **chart icon** in the output header to switch to a visualisation view.

# COMMAND ----------

# Daily tokens by team — line chart: X = usage_date, Y = total_tokens, Group by = team
daily_by_team = spark.sql("""
  SELECT
    DATE(event_time)                             AS usage_date,
    COALESCE(request_tags['team'], 'untagged')   AS team,
    SUM(input_tokens + output_tokens)            AS total_tokens,
    COUNT(*)                                     AS request_count
  FROM system.ai_gateway.usage
  WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS AND status_code = 200
  GROUP BY 1, 2
  ORDER BY 1, 2
""")

display(daily_by_team)

# COMMAND ----------

# Endpoint utilisation — bar chart: X = endpoint_name, Y = total_requests
endpoint_utilisation = spark.sql("""
  SELECT
    endpoint_name,
    COUNT(*)                                               AS total_requests,
    SUM(input_tokens + output_tokens)                      AS total_tokens,
    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END)    AS successful,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)    AS rate_limited,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)    AS blocked,
    ROUND(AVG(latency_ms), 0)                              AS avg_latency_ms,
    ROUND(SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS success_rate_pct
  FROM system.ai_gateway.usage
  WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY total_requests DESC
""")

display(endpoint_utilisation)

# COMMAND ----------

# Request outcome breakdown — pie/donut by outcome
# Note: guardrail_type is not exposed in system.ai_gateway.usage; use status_code to classify.
guardrail_summary = spark.sql("""
  SELECT
    CASE
      WHEN status_code = 200 THEN '200 Success'
      WHEN status_code = 429 THEN '429 Rate Limited'
      WHEN status_code = 400 THEN '400 Blocked'
      ELSE CONCAT(CAST(status_code AS STRING), ' Other')
    END                  AS outcome,
    COUNT(*)             AS request_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
  FROM system.ai_gateway.usage
  WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY request_count DESC
""")

display(guardrail_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 5: Budget Alerts — Scheduled Notebook Pattern</h2>
# MAGIC </div>
# MAGIC
# MAGIC Define thresholds, query `system.ai_gateway.usage` for current spend, send a notification when a threshold is crossed. Schedule this notebook as a Databricks job (8am AEST daily).
# MAGIC
# MAGIC 🖱️ **UI (to schedule):** Top-right toolbar → Schedules & Triggers → Add trigger → Scheduled → Cron expression `0 0 8 * * ?` → Timezone: Australia/Sydney → Create

# COMMAND ----------

# TODO: Set your budget thresholds (AUD estimated costs at illustrative token rates)
BUDGET_CONFIG = {
    "daily_warn_aud":     50.0,
    "daily_critical_aud": 100.0,
    "monthly_warn_aud":   500.0,
    "monthly_cap_aud":    1000.0,
    "alert_recipients": [
        "ai-platform-team@example.com.au",    # TODO: update
        "data-governance@example.com.au",     # TODO: update
    ],
}

print("Budget thresholds configured:")
for key, value in BUDGET_CONFIG.items():
    print(f"  {key:<30} {value}")

# COMMAND ----------

from datetime import date
import calendar


def check_daily_budget(budget_config: dict) -> dict:
    today = date.today().isoformat()
    result = spark.sql(f"""
      SELECT
        ROUND(
          SUM(input_tokens  / 1000000.0 * {ILLUSTRATIVE_INPUT_RATE_PER_1M}) +
          SUM(output_tokens / 1000000.0 * {ILLUSTRATIVE_OUTPUT_RATE_PER_1M}), 2
        ) AS estimated_cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE DATE(event_time) = '{today}' AND status_code = 200
    """).collect()[0]

    cost     = result["estimated_cost_aud"] or 0.0
    tokens   = result["total_tokens"]       or 0
    requests = result["request_count"]      or 0

    status = (
        "CRITICAL" if cost >= budget_config["daily_critical_aud"]
        else "WARN"   if cost >= budget_config["daily_warn_aud"]
        else "OK"
    )

    return {
        "check_date": today, "estimated_cost_aud": cost,
        "total_tokens": tokens, "request_count": requests,
        "status": status,
        "daily_warn_threshold": budget_config["daily_warn_aud"],
        "daily_critical_threshold": budget_config["daily_critical_aud"],
    }


def check_monthly_budget(budget_config: dict) -> dict:
    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    result = spark.sql(f"""
      SELECT
        ROUND(
          SUM(input_tokens  / 1000000.0 * {ILLUSTRATIVE_INPUT_RATE_PER_1M}) +
          SUM(output_tokens / 1000000.0 * {ILLUSTRATIVE_OUTPUT_RATE_PER_1M}), 2
        ) AS estimated_cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE DATE(event_time) >= '{month_start}' AND status_code = 200
    """).collect()[0]

    cost          = result["estimated_cost_aud"] or 0.0
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed  = today.day
    projected     = cost * days_in_month / days_elapsed if days_elapsed > 0 else 0

    status = (
        "CAP_REACHED" if cost >= budget_config["monthly_cap_aud"]
        else "WARN"   if cost >= budget_config["monthly_warn_aud"]
        else "OK"
    )

    return {
        "month_start": month_start, "mtd_cost_aud": cost,
        "projected_monthly_cost_aud": round(projected, 2),
        "total_tokens": result["total_tokens"] or 0,
        "status": status, "days_elapsed": days_elapsed, "days_in_month": days_in_month,
    }


def print_budget_report(daily: dict, monthly: dict) -> None:
    print("=" * 60)
    print(f"AI Gateway Budget Report — {daily['check_date']}")
    print("=" * 60)

    daily_icon = {"OK": "[OK]", "WARN": "[WARN]", "CRITICAL": "[CRITICAL]"}[daily["status"]]
    print(f"\nDaily:   {daily_icon}")
    print(f"  Cost today      : ${daily['estimated_cost_aud']:.2f} AUD")
    print(f"  Warn threshold  : ${daily['daily_warn_threshold']:.2f} AUD")
    print(f"  Critical at     : ${daily['daily_critical_threshold']:.2f} AUD")
    print(f"  Requests today  : {daily['request_count']:,}")

    monthly_icon = {"OK": "[OK]", "WARN": "[WARN]", "CAP_REACHED": "[CAP REACHED]"}.get(monthly["status"], "[UNKNOWN]")
    print(f"\nMonthly: {monthly_icon}")
    print(f"  MTD cost        : ${monthly['mtd_cost_aud']:.2f} AUD")
    print(f"  Projected total : ${monthly['projected_monthly_cost_aud']:.2f} AUD  "
          f"({monthly['days_elapsed']}/{monthly['days_in_month']} days elapsed)")

    if daily["status"] != "OK" or monthly["status"] != "OK":
        print(f"\nAction required: review top users via the cost attribution view.")


print("Running budget checks...")
try:
    daily_result   = check_daily_budget(BUDGET_CONFIG)
    monthly_result = check_monthly_budget(BUDGET_CONFIG)
    print_budget_report(daily_result, monthly_result)
except Exception as e:
    print(f"Budget check failed: {e}")
    print("Likely cause: system.ai_gateway.usage is not yet populated (requires AI Gateway activity).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Schedule as a daily alert job
# MAGIC
# MAGIC **Via the UI:**
# MAGIC ```
# MAGIC Navigate: this notebook → Schedules & Triggers (top-right toolbar) → Add trigger → Scheduled → Cron
# MAGIC Cron expression: 0 0 8 * * ?   (8am daily)   Timezone: Australia/Sydney
# MAGIC ```
# MAGIC
# MAGIC **Via the SDK:**
# MAGIC ```python
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks.sdk.service.jobs import Task, NotebookTask, CronSchedule
# MAGIC
# MAGIC w = WorkspaceClient()
# MAGIC job = w.jobs.create(
# MAGIC     name="AI Gateway Daily Budget Alert",
# MAGIC     tasks=[Task(
# MAGIC         task_key="budget-check",
# MAGIC         notebook_task=NotebookTask(notebook_path="/Shared/workshops/03_usage_tracking"),
# MAGIC     )],
# MAGIC     schedule=CronSchedule(
# MAGIC         quartz_cron_expression="0 0 8 * * ?",
# MAGIC         timezone_id="Australia/Sydney",
# MAGIC     ),
# MAGIC     email_notifications={"on_failure": ["ai-platform-team@example.com.au"]},
# MAGIC )
# MAGIC print(f"Job created: {job.job_id}")
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 6: Reference SQL Query Card</h2>
# MAGIC </div>

# COMMAND ----------

REFERENCE_QUERIES = {
    "Top users — last 30 days": """
SELECT
  requester                                     AS user_id,
  SUM(input_tokens + output_tokens)             AS total_tokens,
  COUNT(*)                                      AS request_count,
  ROUND(AVG(latency_ms), 0)                     AS avg_latency_ms
FROM system.ai_gateway.usage
WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  AND status_code = 200
GROUP BY 1
ORDER BY total_tokens DESC
LIMIT 20
    """,

    "Cost by team — current month": """
-- Rates (0.90 / 2.70 AUD per 1M tokens) are illustrative blended estimates.
SELECT
  COALESCE(request_tags['team'], 'untagged')     AS team,
  SUM(input_tokens  / 1000000.0 * 0.90)
+ SUM(output_tokens / 1000000.0 * 2.70)          AS est_cost_aud,
  SUM(input_tokens + output_tokens)              AS total_tokens,
  COUNT(*)                                       AS request_count
FROM system.ai_gateway.usage
WHERE DATE(event_time) >= DATE_TRUNC('month', CURRENT_DATE)
  AND status_code = 200
GROUP BY 1
ORDER BY est_cost_aud DESC
    """,

    "Rate limit hit rate — last 7 days": """
SELECT
  DATE(event_time)                               AS usage_date,
  endpoint_name,
  COUNT(*)                                       AS total_requests,
  SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited,
  ROUND(
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
  )                                              AS rate_limited_pct
FROM system.ai_gateway.usage
WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
GROUP BY 1, 2
ORDER BY 1 DESC, rate_limited_pct DESC
    """,

    "Genie usage — last 7 days": """
SELECT
  DATE(event_time)                   AS event_date,
  user_identity.email                AS user_email,
  COUNT(*)                           AS query_count
FROM system.access.audit
WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  AND service_name = 'aibiGenie'
GROUP BY 1, 2
ORDER BY 1 DESC, query_count DESC
    """,

    "AI Gateway change log — last 90 days": """
-- AI Gateway config changes appear under 'serverlessRealTimeInference', not 'modelServing'.
SELECT
  event_time,
  user_identity.email                AS changed_by,
  action_name,
  request_params['endpointName']     AS endpoint_name,
  response.status_code              AS result_code
FROM system.access.audit
WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 90 DAYS
  AND service_name = 'serverlessRealTimeInference'
  AND action_name IN (
    'putInferenceEndpointAiGateway',
    'deleteInferenceEndpointAiGateway',
    'changeInferenceEndpointAcl',
    'createServingEndpoint',
    'updateServingEndpoint',
    'deleteServingEndpoint'
  )
ORDER BY event_time DESC
    """,
}

print("Reference query card:")
for query_name, sql in REFERENCE_QUERIES.items():
    print(f"\n{'─' * 60}")
    print(f"  Query: {query_name}")
    print(f"{'─' * 60}")
    print(sql.strip())

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 03 Checkpoint

# COMMAND ----------

print("=" * 60)
print("  Lab 03 — Checkpoint Summary")
print("=" * 60)
print()

lab03_checks = [
    "Audit logging verified active — AI events flowing into system.access.audit",
    "system.ai_gateway.usage schema explored (date, endpoint, team, project, token counts)",
    "Top users by token consumption (30-day) queried",
    "Daily trend query written (capacity and anomaly detection)",
    "Guardrail hit analysis query written",
    "system.access.audit queried — model serving, Genie, AI Playground, change log",
    "Cost attribution view defined (by team / project / environment)",
    "Untagged request detection query written",
    "Budget check functions (daily and monthly) reviewed",
    "Budget alert job scheduling pattern documented (UI + SDK)",
    "Reference SQL query card printed",
]

for check in lab03_checks:
    print(f"  [DONE]  {check}")

print()
print("-" * 60)
print("  Next lab : 04_data_residency_compliance.py")
print("  Topic    : Data residency verification and compliance evidence")
print("-" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #F0F4F8; padding: 16px; border-radius: 6px; margin-top: 16px">
# MAGIC <h3 style="color: #1B3139; margin: 0 0 12px 0">system.ai_gateway.usage — Column Reference</h3>
# MAGIC
# MAGIC | Column | Type | Description |
# MAGIC |---|---|---|
# MAGIC | `request_id` | STRING | Unique request identifier |
# MAGIC | `event_time` | TIMESTAMP | Request receipt timestamp |
# MAGIC | `endpoint_name` | STRING | AI Gateway endpoint name |
# MAGIC | `destination_model` | STRING | Specific model used |
# MAGIC | `requester` | STRING | User email or service principal ID |
# MAGIC | `input_tokens` | LONG | Input token count |
# MAGIC | `output_tokens` | LONG | Output token count |
# MAGIC | `latency_ms` | LONG | End-to-end gateway latency in milliseconds |
# MAGIC | `status_code` | INTEGER | HTTP response code (200, 400, 429) |
# MAGIC | `request_tags` | MAP&lt;STRING,STRING&gt; | Per-request tags from `Databricks-Ai-Gateway-Request-Tags` header |
# MAGIC | `endpoint_tags` | MAP&lt;STRING,STRING&gt; | Tags configured on the endpoint (team, cost_center, etc.) |
# MAGIC
# MAGIC > **Access:** Only account admins can query `system.ai_gateway.usage`.
# MAGIC > **Latency:** ~15 minutes from request time.
# MAGIC > **Genie July 6, 2026 pricing change:** LLM usage in Genie Spaces moves to pay-as-you-go beyond a free monthly per-user allowance. Only overage is subject to budget controls. Genie SQL warehouse compute is billed separately under `billing_origin_product = 'SQL'`.
# MAGIC </div>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Section 7: Billing Model, Split Billing & Out-of-the-Box Monitoring
# MAGIC
# MAGIC ### 7a. How AI Features Are Charged
# MAGIC
# MAGIC AI Gateway adds zero overhead DBUs. All model serving costs appear as `MODEL_SERVING` records in `system.billing.usage`.
# MAGIC
# MAGIC | Feature | `billing_origin_product` | `sku_name` pattern | Billing model |
# MAGIC |---|---|---|---|
# MAGIC | FMAPI Pay-Per-Token (via AI Gateway) | `MODEL_SERVING` | `LIKE '%SERVERLESS_REAL_TIME_INFERENCE%'` | DBUs per 1M tokens |
# MAGIC | FMAPI Provisioned Throughput | `MODEL_SERVING` | `LIKE '%SERVERLESS_REAL_TIME_INFERENCE%'` | DBUs/hour, always-on |
# MAGIC | Genie LLM usage (post-July 6 overage) | `MODEL_SERVING` | `LIKE '%SERVERLESS_REAL_TIME_INFERENCE%'` | Free tier per user; overage billed in DBUs |
# MAGIC
# MAGIC > **sku_name note:** Use a LIKE filter — exact match returns zero rows.
# MAGIC > **FMAPI PT billing note:** Always-on, billed DBUs/hour regardless of traffic. Shut down PT endpoints when not needed.
# MAGIC
# MAGIC ### 7b. Split Billing — Endpoint Tags Pattern
# MAGIC
# MAGIC Endpoint-level tags propagate into `custom_tags` in `system.billing.usage` on every `MODEL_SERVING` record.

# COMMAND ----------

split_billing_sql = """
SELECT
  DATE_TRUNC('month', usage_date)                    AS billing_month,
  custom_tags['team']                                AS team,
  custom_tags['cost_center']                         AS cost_center,
  usage_metadata.ai_gateway_endpoint_name            AS endpoint,
  SUM(usage_quantity)                                AS total_dbus,
  COUNT(*)                                           AS record_count
FROM system.billing.usage
WHERE billing_origin_product = 'MODEL_SERVING'
  AND usage_metadata.ai_gateway_endpoint_name IS NOT NULL
  AND usage_date >= CURRENT_DATE() - INTERVAL 90 DAYS
GROUP BY 1, 2, 3, 4
ORDER BY billing_month DESC, total_dbus DESC
"""

print("Split billing SQL (run in a SQL cell or via display(spark.sql(...))):")
print(split_billing_sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 7c. Out-of-the-Box Monitoring: Built-in AI Gateway Dashboard
# MAGIC
# MAGIC **Navigate:** Left sidebar → AI Gateway → **"Create Dashboard"** → after creation, click **"View Dashboard"**.
# MAGIC
# MAGIC > **Version requirement:** Dashboard must be v0.4+ to include the **Cost Observability** tab.
# MAGIC
# MAGIC | Tab | Data source |
# MAGIC |---|---|
# MAGIC | Overview / Performance / Usage | `system.ai_gateway.usage` |
# MAGIC | Cost Observability | `system.billing.usage` |
# MAGIC | External MCP Server | `system.ai_gateway.usage` (Gated Beta) |
# MAGIC
# MAGIC ### 7d. Unity AI Gateway Cost Controls — Hard Spend Caps
# MAGIC
# MAGIC **Navigate:** Account Console → Usage → Budgets tab → Add budget → Resource type: Unity AI Gateway
# MAGIC - Scope: entire account, specific workspaces, user groups, or individual users
# MAGIC - Hard cap: "Block usage when budget is exhausted"
# MAGIC
# MAGIC > **Rate limits vs budgets:** Rate limits control REQUEST RATE (QPM/TPM). Budget controls control SPEND (DBUs). Use both.
