# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">📊 Lab 04: Usage Tracking & Cost Attribution</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries · Databricks</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | **Prerequisites** | Lab 02 complete — AI Gateway endpoint with usage tracking enabled |
# MAGIC | **By the end** | Cost attribution view built, budget alert configured, reference SQL card printed |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC | Table | What it contains | Latency |
# MAGIC |---|---|---|
# MAGIC | `system.ai_gateway.usage` | Token usage, latency, tags, guardrail hits | ~15 min |
# MAGIC | `system.access.audit` | All API calls including Genie, serving endpoint invocations | ~1 hour |
# MAGIC | `system.billing.usage` | DBU consumption by SKU — includes Model Serving DBUs | ~2 hours |
# MAGIC | `system.serving.served_entities` | Current model serving endpoint inventory | Near real-time |

# COMMAND ----------

# MAGIC %md
# MAGIC ## UI navigation — do this before running any code
# MAGIC
# MAGIC **Browse the system catalog:**
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog icon → system → ai_gateway → usage → Sample Data tab
# MAGIC You should see: columns including endpoint_name, databricks_user_id, input_tokens, output_tokens, status_code, request_tags, guardrail_action.
# MAGIC ```
# MAGIC
# MAGIC **AI Gateway usage dashboard:**
# MAGIC ```
# MAGIC Navigate: AI Gateway → [your endpoint] → **Metrics tab**
# MAGIC You should see: token consumption chart, request latency, error rates, and a per-request log with user, token count, and status.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 0: Setup & Permissions Check</h2>
# MAGIC </div>

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

# Verify access to all key system tables before running subsequent sections
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
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 1: Querying system.ai_gateway.usage</h2>
# MAGIC </div>
# MAGIC
# MAGIC Each row in `system.ai_gateway.usage` represents one request routed through an AI Gateway endpoint. The table has ~15 minute latency — data from Labs 02/03 may already be visible.
# MAGIC
# MAGIC 🖱️ **UI:** AI Gateway → [your endpoint] → **Metrics tab**
# MAGIC You should see: Token consumption chart, request latency, error rates (200/400/429 breakdown), and a per-request log with user, token count, and status. This is the visual summary of the same data queried below.
# MAGIC
# MAGIC ⚡ **Or run the cells below to query `system.ai_gateway.usage` directly for custom aggregations and cost attribution:**

# COMMAND ----------

# View the full schema of the ai_gateway usage table
display(spark.sql("DESCRIBE system.ai_gateway.usage"))

# COMMAND ----------

# Recent requests: date, endpoint, team, project, token counts — last 7 days
recent_requests = spark.sql("""
  SELECT
    DATE(timestamp)                                       AS request_date,
    endpoint_name,
    model_name,
    request_tags['team']                                  AS team,
    request_tags['project']                               AS project,
    COUNT(*)                                              AS request_count,
    SUM(input_tokens)                                     AS total_input_tokens,
    SUM(output_tokens)                                    AS total_output_tokens,
    SUM(input_tokens + output_tokens)                     AS total_tokens,
    ROUND(AVG(execution_time_ms), 0)                      AS avg_latency_ms,
    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END)   AS successful_requests,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)   AS rate_limited_requests,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)   AS blocked_requests
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1, 2, 3, 4, 5
  ORDER BY request_date DESC, total_tokens DESC
""")

display(recent_requests)

# COMMAND ----------

# Top users by token consumption — last 30 days
top_users = spark.sql("""
  SELECT
    databricks_user_id                                    AS user_id,
    COUNT(*)                                              AS request_count,
    SUM(input_tokens + output_tokens)                     AS total_tokens,
    ROUND(AVG(execution_time_ms), 0)                      AS avg_latency_ms,
    COUNT(DISTINCT endpoint_name)                         AS endpoints_used,
    MAX(DATE(timestamp))                                  AS last_seen
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1
  ORDER BY total_tokens DESC
  LIMIT 20
""")

display(top_users)

# COMMAND ----------

# Daily trend — useful for capacity planning and spike detection
daily_trend = spark.sql("""
  SELECT
    DATE(timestamp)                                          AS usage_date,
    endpoint_name,
    SUM(input_tokens + output_tokens)                        AS total_tokens,
    COUNT(*)                                                 AS request_count,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)      AS rate_limited
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1, 2
  ORDER BY 1, 2
""")

display(daily_trend)

# COMMAND ----------

# Guardrail hit analysis — understand what is being blocked and why
guardrail_hits = spark.sql("""
  SELECT
    DATE(timestamp)                              AS event_date,
    endpoint_name,
    guardrail_action                             AS action,
    guardrail_type                               AS guardrail,
    COUNT(*)                                     AS hit_count,
    COUNT(DISTINCT databricks_user_id)           AS unique_users
  FROM system.ai_gateway.usage
  WHERE
    timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND guardrail_action IS NOT NULL
  GROUP BY 1, 2, 3, 4
  ORDER BY 1 DESC, hit_count DESC
""")

display(guardrail_hits)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 2: Querying system.access.audit for AI Events</h2>
# MAGIC </div>
# MAGIC
# MAGIC The audit log captures all API activity. Key action types for AI governance:
# MAGIC
# MAGIC | Action type | Service name | Description |
# MAGIC |---|---|---|
# MAGIC | `queryEndpoint` | `modelServing` | Serving endpoint was called |
# MAGIC | `genieConversation` | `databricksGenie` | Genie Space conversation |
# MAGIC | `aiPlaygroundQuery` | `aiPlayground` | AI Playground used |
# MAGIC | `updateAiGateway` | `modelServing` | AI Gateway config changed |
# MAGIC
# MAGIC 🖱️ **UI:** Left sidebar → Catalog → system → access → audit → Sample Data tab (or open a Query Editor and run `SELECT * FROM system.access.audit LIMIT 100`)
# MAGIC You should see: Raw audit rows with event_time, user_identity, action_name, service_name, and request_params. The queries below filter these to AI-specific events.
# MAGIC
# MAGIC ⚡ **Run the cells below to query AI events from `system.access.audit`:**

# COMMAND ----------

# All model serving calls — last 7 days
serving_calls = spark.sql("""
  SELECT
    DATE(event_time)                AS event_date,
    action_name,
    user_identity.email             AS user_email,
    request_params['endpointName']  AS endpoint_name,
    response.statusCode            AS response_code,
    COUNT(*)                        AS call_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
    AND service_name = 'modelServing'
    AND action_name IN (
      'queryEndpoint',
      'createServingEndpoint',
      'updateServingEndpoint',
      'deleteServingEndpoint',
      'updateAiGateway'
    )
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
    AND service_name = 'databricksGenie'
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

# AI Gateway configuration changes — change management audit evidence (SOCI Act 2018)
gateway_changes = spark.sql("""
  SELECT
    event_time,
    user_identity.email             AS changed_by,
    action_name,
    request_params['endpointName']  AS endpoint_name,
    response.statusCode            AS result_code,
    request_params                  AS change_details
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 90 DAYS
    AND service_name = 'modelServing'
    AND action_name IN (
      'createServingEndpoint',
      'updateServingEndpoint',
      'deleteServingEndpoint',
      'updateAiGateway',
      'putAiGateway'
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
# MAGIC Applications pass cost centre tags via the `databricks-request-tag` HTTP header (e.g. `team=network-ops;project=meter-anomaly`). These appear in `system.ai_gateway.usage.request_tags` as a MAP column.
# MAGIC
# MAGIC 🖱️ **UI:** Left sidebar → Catalog → [catalog] → [schema] → after running the cell below, click `ai_gateway_cost_attribution` to browse the view. For finance reporting, pin the "Monthly cost by team" query result as an AI/BI dashboard widget.
# MAGIC
# MAGIC ⚡ **Run the cell below to create the cost attribution view (uncomment the spark.sql call, then run the query cells):**

# COMMAND ----------

# Token pricing — update when contracts are finalised
# Only include in-region models for regulated AU workloads.
TOKEN_PRICES = {
    "databricks-claude-haiku-4-5": {      # IN-REGION via Provisioned Throughput
        "input_per_1m":  1.00,
        "output_per_1m": 5.00,
    },
    "databricks-claude-sonnet-4-6": {     # IN-REGION via Provisioned Throughput
        "input_per_1m":  3.00,
        "output_per_1m": 15.00,
    },
}

print("Token pricing configured for cost attribution:")
for model, prices in TOKEN_PRICES.items():
    print(f"  {model:<55} Input: ${prices['input_per_1m']}/1M  Output: ${prices['output_per_1m']}/1M")

# COMMAND ----------

CATALOG_NAME = CATALOG_W
SCHEMA_NAME  = SCHEMA_W

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

create_view_sql = f"""
CREATE OR REPLACE VIEW {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution AS
WITH usage_base AS (
  SELECT
    DATE(timestamp)                                     AS usage_date,
    endpoint_name,
    model_name,
    COALESCE(request_tags['team'],        'untagged')   AS team,
    COALESCE(request_tags['project'],     'untagged')   AS project,
    COALESCE(request_tags['environment'], 'unknown')    AS environment,
    databricks_user_id                                  AS user_id,
    COUNT(*)                                            AS request_count,
    SUM(CASE WHEN status_code = 200 THEN input_tokens  ELSE 0 END) AS input_tokens,
    SUM(CASE WHEN status_code = 200 THEN output_tokens ELSE 0 END) AS output_tokens,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)  AS rate_limited_requests,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)  AS blocked_requests,
    AVG(CASE WHEN status_code = 200 THEN execution_time_ms END) AS avg_latency_ms
  FROM system.ai_gateway.usage
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  usage_date,
  endpoint_name,
  model_name,
  team,
  project,
  environment,
  user_id,
  request_count,
  input_tokens,
  output_tokens,
  input_tokens + output_tokens                                      AS total_tokens,
  rate_limited_requests,
  blocked_requests,
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

# COMMAND ----------

# TODO: Uncomment to export the monthly cost attribution to a UC volume for finance reporting
# from datetime import date as _date
# spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.cost_reports")
# (cost_by_team.coalesce(1).write
#     .mode("overwrite")
#     .option("header", "true")
#     .csv(f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/cost_reports/cost_by_team_{_date.today().strftime('%Y-%m')}.csv"))
# print(f"Cost report exported — download via: Catalog → Volumes → {CATALOG_NAME}.{SCHEMA_NAME}.cost_reports")

print("Cost attribution export is commented out — uncomment after view is created and volume is available.")

# COMMAND ----------

# Identify requests without team/project tags — these cannot be attributed to a cost centre
untagged_requests = spark.sql("""
  SELECT
    DATE(timestamp)                     AS request_date,
    endpoint_name,
    databricks_user_id                  AS user_id,
    COUNT(*)                            AS untagged_request_count,
    SUM(input_tokens + output_tokens)   AS untagged_tokens
  FROM system.ai_gateway.usage
  WHERE
    timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
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
# MAGIC Run each cell and click the **chart icon** in the output header to switch to a visualisation view. Charts can be pinned to a Databricks AI/BI dashboard.

# COMMAND ----------

# Daily tokens by team — line chart: X = usage_date, Y = total_tokens, Group by = team
daily_by_team = spark.sql("""
  SELECT
    DATE(timestamp)                              AS usage_date,
    COALESCE(request_tags['team'], 'untagged')   AS team,
    SUM(input_tokens + output_tokens)            AS total_tokens,
    COUNT(*)                                     AS request_count
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS AND status_code = 200
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
    ROUND(AVG(execution_time_ms), 0)                       AS avg_latency_ms,
    ROUND(SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS success_rate_pct
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY total_requests DESC
""")

display(endpoint_utilisation)

# COMMAND ----------

# Request outcome breakdown — pie/donut: segments by outcome
guardrail_summary = spark.sql("""
  SELECT
    CASE
      WHEN status_code = 200                                   THEN '200 Success'
      WHEN status_code = 429                                   THEN '429 Rate Limited'
      WHEN status_code = 400 AND guardrail_type = 'pii'       THEN '400 PII Blocked'
      WHEN status_code = 400 AND guardrail_type = 'safety'    THEN '400 Safety Blocked'
      WHEN status_code = 400                                   THEN '400 Other Block'
      ELSE CONCAT(CAST(status_code AS STRING), ' Other')
    END                  AS outcome,
    COUNT(*)             AS request_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
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
# MAGIC Pattern: define thresholds, query `system.ai_gateway.usage` for current spend, send a notification when a threshold is crossed. Schedule this notebook as a Databricks job (8am AEST daily).
# MAGIC
# MAGIC 🖱️ **UI (to schedule this notebook):** Top-right toolbar of this notebook → Schedules & Triggers → Add trigger → Scheduled → Cron expression `0 0 8 * * ?` → Timezone: Australia/Sydney → Create
# MAGIC You should see: The notebook appear in the Jobs list with a cron schedule. On failure it will send email alerts to the addresses in `BUDGET_CONFIG["alert_recipients"]`.
# MAGIC
# MAGIC ⚡ **Run the cells below to define thresholds and execute the budget check now (runs immediately — no uncomment needed):**

# COMMAND ----------

# TODO: Set your budget thresholds (AUD estimated costs at list-price token rates)
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
    """Check today's spend against daily thresholds. Returns OK, WARN, or CRITICAL."""
    today = date.today().isoformat()
    result = spark.sql(f"""
      SELECT
        ROUND(
          SUM(input_tokens  / 1000000.0 * 0.90) +
          SUM(output_tokens / 1000000.0 * 2.70), 2
        ) AS estimated_cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE DATE(timestamp) = '{today}' AND status_code = 200
    """).collect()[0]

    cost     = result["estimated_cost_aud"] or 0.0
    tokens   = result["total_tokens"]       or 0
    requests = result["request_count"]      or 0

    if cost >= budget_config["daily_critical_aud"]:
        status = "CRITICAL"
    elif cost >= budget_config["daily_warn_aud"]:
        status = "WARN"
    else:
        status = "OK"

    return {
        "check_date":               today,
        "estimated_cost_aud":       cost,
        "total_tokens":             tokens,
        "request_count":            requests,
        "status":                   status,
        "daily_warn_threshold":     budget_config["daily_warn_aud"],
        "daily_critical_threshold": budget_config["daily_critical_aud"],
    }


def check_monthly_budget(budget_config: dict) -> dict:
    """Check current month's cumulative spend against monthly thresholds."""
    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    result = spark.sql(f"""
      SELECT
        ROUND(
          SUM(input_tokens  / 1000000.0 * 0.90) +
          SUM(output_tokens / 1000000.0 * 2.70), 2
        ) AS estimated_cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE DATE(timestamp) >= '{month_start}' AND status_code = 200
    """).collect()[0]

    cost          = result["estimated_cost_aud"] or 0.0
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed  = today.day
    projected     = cost * days_in_month / days_elapsed if days_elapsed > 0 else 0

    if cost >= budget_config["monthly_cap_aud"]:
        status = "CAP_REACHED"
    elif cost >= budget_config["monthly_warn_aud"]:
        status = "WARN"
    else:
        status = "OK"

    return {
        "month_start":                month_start,
        "mtd_cost_aud":               cost,
        "projected_monthly_cost_aud": round(projected, 2),
        "total_tokens":               result["total_tokens"] or 0,
        "status":                     status,
        "days_elapsed":               days_elapsed,
        "days_in_month":              days_in_month,
    }


def print_budget_report(daily: dict, monthly: dict) -> None:
    """Print a formatted budget report."""
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


# Run the budget check
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
# MAGIC         notebook_task=NotebookTask(notebook_path="/Shared/workshops/04_usage_tracking"),
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
  databricks_user_id                            AS user_id,
  SUM(input_tokens + output_tokens)             AS total_tokens,
  COUNT(*)                                      AS request_count,
  ROUND(AVG(execution_time_ms), 0)              AS avg_latency_ms
FROM system.ai_gateway.usage
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  AND status_code = 200
GROUP BY 1
ORDER BY total_tokens DESC
LIMIT 20
    """,

    "Cost by team — current month": """
SELECT
  COALESCE(request_tags['team'], 'untagged')     AS team,
  SUM(input_tokens  / 1000000.0 * 0.90)
+ SUM(output_tokens / 1000000.0 * 2.70)          AS est_cost_aud,
  SUM(input_tokens + output_tokens)              AS total_tokens,
  COUNT(*)                                       AS request_count
FROM system.ai_gateway.usage
WHERE DATE(timestamp) >= DATE_TRUNC('month', CURRENT_DATE)
  AND status_code = 200
GROUP BY 1
ORDER BY est_cost_aud DESC
    """,

    "Rate limit hit rate — last 7 days": """
SELECT
  DATE(timestamp)                                AS usage_date,
  endpoint_name,
  COUNT(*)                                       AS total_requests,
  SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited,
  ROUND(
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
  )                                              AS rate_limited_pct
FROM system.ai_gateway.usage
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
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
  AND service_name = 'databricksGenie'
  AND action_name  = 'genieConversation'
GROUP BY 1, 2
ORDER BY 1 DESC, query_count DESC
    """,

    "Model serving change log — last 90 days": """
SELECT
  event_time,
  user_identity.email                AS changed_by,
  action_name,
  request_params['endpointName']     AS endpoint_name,
  response.statusCode               AS result_code
FROM system.access.audit
WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 90 DAYS
  AND service_name = 'modelServing'
  AND action_name IN (
    'createServingEndpoint', 'updateServingEndpoint',
    'deleteServingEndpoint', 'updateAiGateway', 'putAiGateway'
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
# MAGIC ## ✅ Lab 04 Checkpoint
# MAGIC - [ ] `system.ai_gateway.usage` schema explored — date, endpoint, team, project, token counts
# MAGIC - [ ] Top users by token consumption (30-day) queried
# MAGIC - [ ] Daily trend query written (capacity and anomaly detection)
# MAGIC - [ ] Guardrail hit analysis query written
# MAGIC - [ ] `system.access.audit` queried — model serving, Genie, AI Playground, change log
# MAGIC - [ ] Cost attribution view defined (by team / project / environment)
# MAGIC - [ ] Untagged request detection query written
# MAGIC - [ ] Budget check functions (daily and monthly) reviewed
# MAGIC - [ ] Budget alert job scheduling pattern documented (UI + SDK)
# MAGIC - [ ] Reference SQL query card printed
# MAGIC
# MAGIC **→ Next: Lab 05 — Data Residency & Compliance Evidence**

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #F0F4F8; padding: 16px; border-radius: 6px; margin-top: 16px">
# MAGIC <h3 style="color: #1B3139; margin: 0 0 12px 0">system.ai_gateway.usage — Column Reference</h3>
# MAGIC
# MAGIC | Column | Type | Description |
# MAGIC |---|---|---|
# MAGIC | `timestamp` | TIMESTAMP | Request timestamp |
# MAGIC | `endpoint_name` | STRING | AI Gateway endpoint name |
# MAGIC | `model_name` | STRING | Underlying model name |
# MAGIC | `databricks_user_id` | STRING | User or service principal ID |
# MAGIC | `input_tokens` | LONG | Tokens in the request |
# MAGIC | `output_tokens` | LONG | Tokens in the response |
# MAGIC | `execution_time_ms` | LONG | End-to-end latency in milliseconds |
# MAGIC | `status_code` | INTEGER | HTTP response code (200, 400, 429) |
# MAGIC | `request_tags` | MAP&lt;STRING,STRING&gt; | Tags from `databricks-request-tag` header |
# MAGIC | `guardrail_action` | STRING | Guardrail decision: BLOCK or PASS |
# MAGIC | `guardrail_type` | STRING | Which guardrail fired: pii, safety |
# MAGIC </div>
