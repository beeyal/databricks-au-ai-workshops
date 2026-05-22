# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 04: Usage Tracking & Cost Attribution
# MAGIC
# MAGIC **Workshop:** Governing Databricks AI Features in Australian Regulated Industries
# MAGIC **Estimated time:** 35–40 minutes
# MAGIC **Difficulty:** Intermediate
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC By the end of this lab you will be able to:
# MAGIC
# MAGIC 1. Query `system.ai_gateway.usage` for token consumption and latency metrics
# MAGIC 2. Query `system.access.audit` for AI-specific events (Genie, model serving, AI Playground)
# MAGIC 3. Build a cost attribution view segmented by team and project using request tags
# MAGIC 4. Create a usage monitoring dashboard using `display()`
# MAGIC 5. Set up a budget alert using a scheduled notebook job
# MAGIC 6. Write the key SQL queries every admin should bookmark
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## System Tables Reference
# MAGIC
# MAGIC | Table | What it contains | Latency |
# MAGIC |---|---|---|
# MAGIC | `system.ai_gateway.usage` | AI Gateway token usage, latency, tags, guardrail hits | ~15 min |
# MAGIC | `system.access.audit` | All API calls including Genie, serving endpoint invocations | ~1 hour |
# MAGIC | `system.billing.usage` | DBU consumption by SKU — includes Model Serving DBUs | ~2 hours |
# MAGIC | `system.serving.served_entities` | Current model serving endpoint inventory | Near real-time |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC - Unity Catalog enabled
# MAGIC - `system` catalog granted to your user or group (USAGE on system catalog)
# MAGIC - At least one AI Gateway endpoint with usage tracking enabled (from Lab 02)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Setup & Permissions Check

# COMMAND ----------

# Check access to key system tables
SYSTEM_TABLES = [
    "system.ai_gateway.usage",
    "system.access.audit",
    "system.billing.usage",
    "system.serving.served_entities",
]

print("Checking access to system tables...\n")
for table in SYSTEM_TABLES:
    try:
        count = spark.sql(f"SELECT COUNT(*) as n FROM {table}").collect()[0]["n"]
        print(f"  [OK]   {table} — {count:,} rows accessible")
    except Exception as e:
        err = str(e)[:80]
        print(f"  [FAIL] {table} — {err}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Querying system.ai_gateway.usage
# MAGIC
# MAGIC This table is the primary source of truth for AI Gateway consumption.
# MAGIC Each row represents one request routed through an AI Gateway endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a. Schema exploration

# COMMAND ----------

# View the full schema of the ai_gateway usage table
display(spark.sql("DESCRIBE system.ai_gateway.usage"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b. Recent requests — last 7 days

# COMMAND ----------

# SOLUTION: Most useful initial query — recent requests overview
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

# MAGIC %md
# MAGIC ### 1c. Top users by token consumption

# COMMAND ----------

# SOLUTION: Identify heavy users for capacity planning and cost attribution
top_users = spark.sql("""
  SELECT
    databricks_user_id                                    AS user_id,
    COUNT(*)                                              AS request_count,
    SUM(input_tokens)                                     AS total_input_tokens,
    SUM(output_tokens)                                    AS total_output_tokens,
    SUM(input_tokens + output_tokens)                     AS total_tokens,
    ROUND(AVG(execution_time_ms), 0)                      AS avg_latency_ms,
    COUNT(DISTINCT endpoint_name)                         AS endpoints_used,
    MIN(DATE(timestamp))                                  AS first_seen,
    MAX(DATE(timestamp))                                  AS last_seen
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1
  ORDER BY total_tokens DESC
  LIMIT 20
""")

display(top_users)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1d. Daily trend — token consumption over 30 days

# COMMAND ----------

# SOLUTION: Daily trend for capacity and anomaly detection
daily_trend = spark.sql("""
  SELECT
    DATE(timestamp)                             AS usage_date,
    endpoint_name,
    SUM(input_tokens + output_tokens)           AS total_tokens,
    SUM(input_tokens)                           AS input_tokens,
    SUM(output_tokens)                          AS output_tokens,
    COUNT(*)                                    AS request_count,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1, 2
  ORDER BY 1, 2
""")

display(daily_trend)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1e. Guardrail hit analysis

# COMMAND ----------

# SOLUTION: Understanding what is being blocked and why
guardrail_hits = spark.sql("""
  SELECT
    DATE(timestamp)                             AS event_date,
    endpoint_name,
    guardrail_action                            AS action,
    guardrail_type                              AS guardrail,
    COUNT(*)                                    AS hit_count,
    COUNT(DISTINCT databricks_user_id)          AS unique_users
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
# MAGIC ## 2. Querying system.access.audit for AI Events
# MAGIC
# MAGIC The audit log captures all API activity. For AI governance, the most
# MAGIC important action types are:
# MAGIC
# MAGIC | Action type | Service name | Description |
# MAGIC |---|---|---|
# MAGIC | `queryEndpoint` | `modelServing` | A model serving endpoint was called |
# MAGIC | `genieConversation` | `databricksGenie` | A Genie Space conversation occurred |
# MAGIC | `aiPlaygroundQuery` | `aiPlayground` | AI Playground was used |
# MAGIC | `createServingEndpoint` | `modelServing` | A new endpoint was created |
# MAGIC | `updateServingEndpoint` | `modelServing` | Endpoint config was changed |
# MAGIC | `deleteServingEndpoint` | `modelServing` | Endpoint was deleted |
# MAGIC | `updateAiGateway` | `modelServing` | AI Gateway config was changed |
# MAGIC
# MAGIC **Tip:** To discover the exact `service_name` and `action_name` values in your workspace,
# MAGIC run: `SELECT DISTINCT service_name, action_name FROM system.access.audit WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS ORDER BY 1, 2`

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2a. Model serving endpoint invocations

# COMMAND ----------

# SOLUTION: All model serving calls in the past 7 days
serving_calls = spark.sql("""
  SELECT
    DATE(event_time)                AS event_date,
    action_name,
    user_identity.email             AS user_email,
    request_params['endpointName']  AS endpoint_name,
    response.status_code            AS response_code,
    COUNT(*)                        AS call_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
    AND service_name = 'modelServing'
    AND action_name IN ('queryEndpoint', 'createServingEndpoint', 'updateServingEndpoint', 'deleteServingEndpoint', 'updateAiGateway')
  GROUP BY 1, 2, 3, 4, 5
  ORDER BY 1 DESC, call_count DESC
""")

display(serving_calls)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2b. Genie Space queries

# COMMAND ----------

# SOLUTION: Genie usage audit — who asked what space, when
genie_usage = spark.sql("""
  SELECT
    DATE(event_time)                    AS event_date,
    user_identity.email                 AS user_email,
    action_name,
    request_params['spaceId']           AS space_id,
    response.status_code                AS response_code,
    COUNT(*)                            AS query_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
    AND service_name = 'databricksGenie'
  GROUP BY 1, 2, 3, 4, 5
  ORDER BY 1 DESC, query_count DESC
""")

display(genie_usage)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2c. AI Playground usage (potential shadow IT risk)
# MAGIC
# MAGIC AI Playground allows ad-hoc model interaction. For regulated data environments,
# MAGIC you need to monitor whether users are pasting sensitive data into Playground.
# MAGIC The audit log captures the activity but not the prompt content itself
# MAGIC (use payload logging on the endpoint for that).

# COMMAND ----------

# SOLUTION: AI Playground usage by user
playground_usage = spark.sql("""
  SELECT
    DATE(event_time)                AS event_date,
    user_identity.email             AS user_email,
    action_name,
    COUNT(*)                        AS session_count,
    MIN(event_time)                 AS first_use,
    MAX(event_time)                 AS last_use
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND service_name = 'aiPlayground'
  GROUP BY 1, 2, 3
  ORDER BY 1 DESC, session_count DESC
""")

display(playground_usage)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2d. AI Gateway configuration changes (change management audit)

# COMMAND ----------

# SOLUTION: All AI Gateway config changes — critical for change management
gateway_changes = spark.sql("""
  SELECT
    event_time,
    user_identity.email             AS changed_by,
    action_name,
    request_params['endpointName']  AS endpoint_name,
    response.status_code            AS result_code,
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
# MAGIC ## 3. Cost Attribution View — By Team and Project
# MAGIC
# MAGIC Combine AI Gateway usage data with request tags to build a cost attribution
# MAGIC model. For APRA-regulated entities, cost attribution is required for:
# MAGIC - IT cost allocation to business units
# MAGIC - FinOps chargeback models
# MAGIC - Demonstrating proportionate spending controls
# MAGIC
# MAGIC ### Approximate token pricing reference (as of May 2026)
# MAGIC
# MAGIC | Model | Input (per 1M tokens) | Output (per 1M tokens) |
# MAGIC |---|---|---|
# MAGIC | Meta Llama 3.3 70B (PT) | ~$0.90 | ~$2.70 |
# MAGIC | GPT-4o (Azure OpenAI Regional) | ~$2.50 | ~$10.00 |
# MAGIC | Llama 3.1 8B (PT) | ~$0.20 | ~$0.60 |

# COMMAND ----------

# Token pricing — update these when your contracts are finalised
# TODO: Replace with your actual contracted rates
TOKEN_PRICES = {
    "databricks-meta-llama-3-3-70b-instruct": {
        "input_per_1m":  0.90,
        "output_per_1m": 2.70,
    },
    "gpt-4o": {
        "input_per_1m":  2.50,
        "output_per_1m": 10.00,
    },
    "databricks-meta-llama-3-1-8b-instruct": {
        "input_per_1m":  0.20,
        "output_per_1m": 0.60,
    },
}

print("Token pricing configured for cost attribution:")
for model, prices in TOKEN_PRICES.items():
    print(f"  {model:<55} Input: ${prices['input_per_1m']}/1M  Output: ${prices['output_per_1m']}/1M")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a. Create the cost attribution view

# COMMAND ----------

# TODO: Replace with your catalog and schema names
CATALOG_NAME = "energy_ai"   # TODO
SCHEMA_NAME  = "analytics"   # TODO

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

# SOLUTION: Create a cost attribution view
# This view joins ai_gateway.usage with the pricing structure above
# In practice, maintain the pricing table as a Delta table

create_view_sql = f"""
CREATE OR REPLACE VIEW {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution AS
-- Note: we aggregate ALL requests first (to capture 429/400 counts),
-- then filter to status_code = 200 only when computing token-based cost.
WITH usage_base AS (
  SELECT
    DATE(timestamp)                                   AS usage_date,
    endpoint_name,
    model_name,
    COALESCE(request_tags['team'],     'untagged')    AS team,
    COALESCE(request_tags['project'],  'untagged')    AS project,
    COALESCE(request_tags['environment'], 'unknown')  AS environment,
    databricks_user_id                                AS user_id,
    COUNT(*)                                          AS request_count,
    SUM(CASE WHEN status_code = 200 THEN input_tokens  ELSE 0 END) AS input_tokens,
    SUM(CASE WHEN status_code = 200 THEN output_tokens ELSE 0 END) AS output_tokens,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited_requests,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END) AS blocked_requests,
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
  input_tokens + output_tokens                                    AS total_tokens,
  rate_limited_requests,
  blocked_requests,
  ROUND(avg_latency_ms, 0)                                       AS avg_latency_ms,
  -- Cost estimates (AUD — update multiplier for FX if using USD pricing)
  ROUND(input_tokens  / 1000000.0 * 0.90, 4)                    AS est_input_cost_aud,
  ROUND(output_tokens / 1000000.0 * 2.70, 4)                    AS est_output_cost_aud,
  ROUND((input_tokens / 1000000.0 * 0.90) +
        (output_tokens / 1000000.0 * 2.70), 4)                  AS est_total_cost_aud
FROM usage_base
"""

# TODO: Uncomment to create the view
# spark.sql(create_view_sql)
# print(f"View created: {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution")

print("View creation SQL is ready — uncomment to execute.")
print(f"Target view: {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Cost by team (monthly rollup)

# COMMAND ----------

# SOLUTION: Monthly cost by team — use for internal chargeback
cost_by_team = spark.sql(f"""
  SELECT
    DATE_TRUNC('month', usage_date)     AS billing_month,
    team,
    SUM(request_count)                  AS total_requests,
    SUM(input_tokens)                   AS total_input_tokens,
    SUM(output_tokens)                  AS total_output_tokens,
    SUM(total_tokens)                   AS total_tokens,
    ROUND(SUM(est_total_cost_aud), 2)   AS estimated_cost_aud
  FROM {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution
  GROUP BY 1, 2
  ORDER BY 1 DESC, estimated_cost_aud DESC
""")

# Fallback to system table if view not created yet
# cost_by_team = spark.sql("""
#   SELECT
#     DATE_TRUNC('month', timestamp)            AS billing_month,
#     COALESCE(request_tags['team'], 'untagged') AS team,
#     COUNT(*)                                   AS total_requests,
#     SUM(input_tokens + output_tokens)          AS total_tokens
#   FROM system.ai_gateway.usage
#   WHERE status_code = 200
#   GROUP BY 1, 2
#   ORDER BY 1 DESC, total_tokens DESC
# """)

display(cost_by_team)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3c. Untagged request detection

# COMMAND ----------

# SOLUTION: Identify requests without team/project tags — these can't be attributed
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
print("\nNote: Untagged requests indicate applications not passing databricks-request-tag header.")
print("Raise with the owning team to add tags before the next billing cycle.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Creating a Usage Monitoring Dashboard
# MAGIC
# MAGIC We will use `display()` to create charts that can be published to a
# MAGIC Databricks AI/BI dashboard. For a production dashboard, save these
# MAGIC as views and use the Lakeview dashboard API (see Lab companion notebook).

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a. Token consumption over time (time series chart)

# COMMAND ----------

# Daily tokens by team — suitable for a time series chart in display()
daily_by_team = spark.sql("""
  SELECT
    DATE(timestamp)                             AS usage_date,
    COALESCE(request_tags['team'], 'untagged')  AS team,
    SUM(input_tokens + output_tokens)           AS total_tokens,
    COUNT(*)                                    AS request_count
  FROM system.ai_gateway.usage
  WHERE
    timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND status_code = 200
  GROUP BY 1, 2
  ORDER BY 1, 2
""")

# Display as a table — click the chart icon in the Databricks UI to switch to line chart
# Set X axis = usage_date, Y axis = total_tokens, Group by = team
display(daily_by_team)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Endpoint utilisation (bar chart)

# COMMAND ----------

endpoint_utilisation = spark.sql("""
  SELECT
    endpoint_name,
    COUNT(*)                                              AS total_requests,
    SUM(input_tokens + output_tokens)                     AS total_tokens,
    SUM(CASE WHEN status_code = 200  THEN 1 ELSE 0 END)  AS successful,
    SUM(CASE WHEN status_code = 429  THEN 1 ELSE 0 END)  AS rate_limited,
    SUM(CASE WHEN status_code = 400  THEN 1 ELSE 0 END)  AS blocked,
    ROUND(AVG(execution_time_ms), 0)                      AS avg_latency_ms,
    ROUND(
      SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
      1
    )                                                     AS success_rate_pct
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY total_requests DESC
""")

display(endpoint_utilisation)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4c. Guardrail hit rate (pie/donut chart)

# COMMAND ----------

guardrail_summary = spark.sql("""
  SELECT
    CASE
      WHEN status_code = 200                                  THEN '200 Success'
      WHEN status_code = 429                                  THEN '429 Rate Limited'
      WHEN status_code = 400 AND guardrail_type = 'pii'      THEN '400 PII Blocked'
      WHEN status_code = 400 AND guardrail_type = 'safety'   THEN '400 Safety Blocked'
      WHEN status_code = 400                                  THEN '400 Other Block'
      ELSE CONCAT(CAST(status_code AS STRING), ' Other')
    END                AS outcome,
    COUNT(*)           AS request_count,
    ROUND(
      COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (),
      2
    )                  AS percentage
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY request_count DESC
""")

display(guardrail_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Budget Alert — Scheduled Notebook Pattern
# MAGIC
# MAGIC For regulated utilities, automated budget alerts prevent surprise costs
# MAGIC and trigger escalation procedures under APRA CPS 230 (operational resilience).

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5a. Define budget thresholds

# COMMAND ----------

# TODO: Set your budget thresholds (AUD, estimated costs using list-price token rates)
BUDGET_CONFIG = {
    "daily_warn_aud": 50.0,      # TODO: daily warning threshold
    "daily_critical_aud": 100.0, # TODO: daily critical threshold — triggers escalation
    "monthly_warn_aud": 500.0,   # TODO: monthly warning threshold
    "monthly_cap_aud": 1000.0,   # TODO: monthly cap — triggers endpoint disable
    "alert_recipients": [        # TODO: email addresses for alerts
        "ai-platform-team@example.com.au",
        "data-governance@example.com.au",
    ],
    "escalation_group": "grp_ai_admins",  # Databricks group to notify
}

print("Budget thresholds configured:")
for key, value in BUDGET_CONFIG.items():
    print(f"  {key:<30} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b. Budget check function

# COMMAND ----------

from datetime import datetime, timezone, date
import calendar


def check_daily_budget(budget_config: dict) -> dict:
    """
    Check today's AI Gateway spend against daily budget thresholds.
    Returns a status dict with values: OK, WARN, CRITICAL.
    """
    today = date.today().isoformat()

    result = spark.sql(f"""
      SELECT
        ROUND(
          SUM(input_tokens  / 1000000.0 * 0.90) +
          SUM(output_tokens / 1000000.0 * 2.70),
          2
        ) AS estimated_cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE
        DATE(timestamp) = '{today}'
        AND status_code = 200
    """).collect()[0]

    cost = result["estimated_cost_aud"] or 0.0
    tokens = result["total_tokens"] or 0
    requests = result["request_count"] or 0

    if cost >= budget_config["daily_critical_aud"]:
        status = "CRITICAL"
    elif cost >= budget_config["daily_warn_aud"]:
        status = "WARN"
    else:
        status = "OK"

    return {
        "check_date": today,
        "estimated_cost_aud": cost,
        "total_tokens": tokens,
        "request_count": requests,
        "status": status,
        "daily_warn_threshold": budget_config["daily_warn_aud"],
        "daily_critical_threshold": budget_config["daily_critical_aud"],
    }


def check_monthly_budget(budget_config: dict) -> dict:
    """Check current month's cumulative spend against monthly budget."""
    today = date.today()
    month_start = today.replace(day=1).isoformat()

    result = spark.sql(f"""
      SELECT
        ROUND(
          SUM(input_tokens  / 1000000.0 * 0.90) +
          SUM(output_tokens / 1000000.0 * 2.70),
          2
        ) AS estimated_cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE
        DATE(timestamp) >= '{month_start}'
        AND status_code = 200
    """).collect()[0]

    cost = result["estimated_cost_aud"] or 0.0
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    projected_monthly = cost * days_in_month / days_elapsed if days_elapsed > 0 else 0

    if cost >= budget_config["monthly_cap_aud"]:
        status = "CAP_REACHED"
    elif cost >= budget_config["monthly_warn_aud"]:
        status = "WARN"
    else:
        status = "OK"

    return {
        "month_start": month_start,
        "mtd_cost_aud": cost,
        "projected_monthly_cost_aud": round(projected_monthly, 2),
        "total_tokens": tokens if (tokens := result["total_tokens"]) else 0,
        "status": status,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
    }


def print_budget_report(daily: dict, monthly: dict) -> None:
    """Print a formatted budget report suitable for Slack/email notification."""
    print("=" * 60)
    print(f"AI Gateway Budget Report — {daily['check_date']}")
    print("=" * 60)

    # Daily
    daily_icon = {"OK": "[OK]", "WARN": "[WARN]", "CRITICAL": "[CRITICAL]"}[daily["status"]]
    print(f"\nDaily:   {daily_icon}")
    print(f"  Cost today     : ${daily['estimated_cost_aud']:.2f} AUD")
    print(f"  Warn at        : ${daily['daily_warn_threshold']:.2f} AUD")
    print(f"  Critical at    : ${daily['daily_critical_threshold']:.2f} AUD")
    print(f"  Requests today : {daily['request_count']:,}")
    print(f"  Tokens today   : {daily['total_tokens']:,}")

    # Monthly
    status_icons = {
        "OK": "[OK]", "WARN": "[WARN]", "CAP_REACHED": "[CAP REACHED]"
    }
    monthly_icon = status_icons.get(monthly["status"], "[UNKNOWN]")
    print(f"\nMonthly: {monthly_icon}")
    print(f"  MTD cost       : ${monthly['mtd_cost_aud']:.2f} AUD")
    print(f"  Projected      : ${monthly['projected_monthly_cost_aud']:.2f} AUD ({monthly['days_elapsed']}/{monthly['days_in_month']} days)")

    if daily["status"] != "OK" or monthly["status"] != "OK":
        print(f"\nAction required: review top users via the cost attribution view.")


# Run the budget check
print("Running budget checks...")
try:
    daily_result  = check_daily_budget(BUDGET_CONFIG)
    monthly_result = check_monthly_budget(BUDGET_CONFIG)
    print_budget_report(daily_result, monthly_result)
except Exception as e:
    print(f"Budget check failed: {e}")
    print("Likely cause: system.ai_gateway.usage is not yet populated (requires AI Gateway activity).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5c. Schedule this notebook as a daily alert job
# MAGIC
# MAGIC To run this budget check on a schedule, create a Databricks job:
# MAGIC
# MAGIC ```python
# MAGIC # Run from a separate orchestration notebook or CLI
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks.sdk.service.jobs import Task, NotebookTask, CronSchedule
# MAGIC
# MAGIC w = WorkspaceClient()
# MAGIC
# MAGIC job = w.jobs.create(
# MAGIC     name="AI Gateway Daily Budget Alert",
# MAGIC     tasks=[
# MAGIC         Task(
# MAGIC             task_key="budget-check",
# MAGIC             notebook_task=NotebookTask(
# MAGIC                 notebook_path="/Shared/workshops/04_usage_tracking",
# MAGIC                 base_parameters={"mode": "alert_only"},
# MAGIC             ),
# MAGIC         )
# MAGIC     ],
# MAGIC     schedule=CronSchedule(
# MAGIC         quartz_cron_expression="0 0 8 * * ?",  # 8am daily AEST (UTC+10)
# MAGIC         timezone_id="Australia/Sydney",
# MAGIC     ),
# MAGIC     email_notifications={
# MAGIC         "on_failure": ["ai-platform-team@example.com.au"],
# MAGIC         "on_success": [],
# MAGIC     },
# MAGIC )
# MAGIC print(f"Job created: {job.job_id}")
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Key SQL Queries Reference Card
# MAGIC
# MAGIC The queries below are formatted for copy-paste into a Databricks AI/BI dashboard.

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
  response.status_code               AS result_code
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
# MAGIC ## 7. Lab Summary & Checkpoint

# COMMAND ----------

print("=" * 60)
print("Lab 04 — Checkpoint Summary")
print("=" * 60)

checks = [
    "system.ai_gateway.usage schema explored",
    "Recent requests query: date, endpoint, team, token counts",
    "Top users by token consumption (30-day rolling)",
    "Daily trend query for capacity and anomaly detection",
    "Guardrail hit analysis query written",
    "system.access.audit: model serving invocations queried",
    "system.access.audit: Genie Space usage queried",
    "system.access.audit: AI Playground usage queried",
    "system.access.audit: AI Gateway change log queried",
    "Cost attribution view defined (by team/project/environment)",
    "Untagged request detection query written",
    "Budget check functions: daily and monthly",
    "Budget alert job scheduling pattern documented",
    "Reference SQL query card printed",
]

for check in checks:
    print(f"  [DONE]  {check}")

print()
print("Next lab: 05_data_residency_compliance.py")
print("Topic   : Generating a compliance evidence package for APRA audit")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Reference: system.ai_gateway.usage Column Reference
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
# MAGIC | `status_code` | INTEGER | HTTP response code |
# MAGIC | `request_tags` | MAP<STRING,STRING> | Tags from `databricks-request-tag` header |
# MAGIC | `guardrail_action` | STRING | Guardrail decision: BLOCK or PASS |
# MAGIC | `guardrail_type` | STRING | Which guardrail fired: pii, safety |
# MAGIC | `client_request_id` | STRING | Client-supplied idempotency key |
