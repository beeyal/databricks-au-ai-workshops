# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 04 SOLUTION: Usage Tracking & Cost Attribution
# MAGIC
# MAGIC **This is the reference solution notebook. All TODO items are completed.**

# COMMAND ----------

import json
import calendar
from datetime import datetime, timezone, date
from databricks.sdk import WorkspaceClient

# SOLUTION: Configuration
CATALOG_NAME = "energy_ai"
SCHEMA_NAME  = "analytics"

w = WorkspaceClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Permissions Check — SOLUTION

# COMMAND ----------

# SOLUTION: Check all required system tables
SYSTEM_TABLES = [
    "system.ai_gateway.usage",
    "system.access.audit",
    "system.billing.usage",
    "system.serving.served_entities",
]

print("System table access check:")
for table in SYSTEM_TABLES:
    try:
        count = spark.sql(f"SELECT COUNT(*) as n FROM {table}").collect()[0]["n"]
        print(f"  [OK]   {table:<45} {count:,} rows")
    except Exception as e:
        print(f"  [FAIL] {table:<45} {str(e)[:60]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. AI Gateway Usage Queries — SOLUTION

# COMMAND ----------

# SOLUTION: Recent requests overview
recent_requests = spark.sql("""
  SELECT
    DATE(timestamp)                                       AS request_date,
    endpoint_name,
    model_name,
    COALESCE(request_tags['team'],    'untagged')         AS team,
    COALESCE(request_tags['project'], 'untagged')         AS project,
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

# SOLUTION: Top users by token consumption
top_users = spark.sql("""
  SELECT
    databricks_user_id                            AS user_id,
    COUNT(*)                                      AS request_count,
    SUM(input_tokens + output_tokens)             AS total_tokens,
    ROUND(AVG(execution_time_ms), 0)              AS avg_latency_ms,
    COUNT(DISTINCT endpoint_name)                 AS endpoints_used,
    MIN(DATE(timestamp))                          AS first_seen,
    MAX(DATE(timestamp))                          AS last_seen
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1
  ORDER BY total_tokens DESC
  LIMIT 20
""")
display(top_users)

# COMMAND ----------

# SOLUTION: Daily trend
daily_trend = spark.sql("""
  SELECT
    DATE(timestamp)                    AS usage_date,
    endpoint_name,
    SUM(input_tokens + output_tokens)  AS total_tokens,
    COUNT(*)                           AS request_count,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  GROUP BY 1, 2
  ORDER BY 1, 2
""")
display(daily_trend)

# COMMAND ----------

# SOLUTION: Guardrail hit analysis
guardrail_hits = spark.sql("""
  SELECT
    DATE(timestamp)                    AS event_date,
    endpoint_name,
    guardrail_action                   AS action,
    guardrail_type                     AS guardrail,
    COUNT(*)                           AS hit_count,
    COUNT(DISTINCT databricks_user_id) AS unique_users
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
# MAGIC ## 2. Audit Log Queries — SOLUTION

# COMMAND ----------

# SOLUTION: Model serving invocations
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

# SOLUTION: Genie usage
genie_usage = spark.sql("""
  SELECT
    DATE(event_time)                AS event_date,
    user_identity.email             AS user_email,
    action_name,
    request_params['spaceId']       AS space_id,
    COUNT(*)                        AS query_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
    AND service_name = 'databricksGenie'
  GROUP BY 1, 2, 3, 4
  ORDER BY 1 DESC, query_count DESC
""")
display(genie_usage)

# COMMAND ----------

# SOLUTION: AI Playground usage
playground_usage = spark.sql("""
  SELECT
    DATE(event_time)       AS event_date,
    user_identity.email    AS user_email,
    action_name,
    COUNT(*)               AS session_count
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND service_name = 'aiPlayground'
  GROUP BY 1, 2, 3
  ORDER BY 1 DESC, session_count DESC
""")
display(playground_usage)

# COMMAND ----------

# SOLUTION: AI Gateway change log
gateway_changes = spark.sql("""
  SELECT
    event_time,
    user_identity.email             AS changed_by,
    action_name,
    request_params['endpointName']  AS endpoint_name,
    response.status_code            AS result_code
  FROM system.access.audit
  WHERE
    event_time >= CURRENT_TIMESTAMP - INTERVAL 90 DAYS
    AND service_name = 'modelServing'
    AND action_name IN (
      'createServingEndpoint', 'updateServingEndpoint',
      'deleteServingEndpoint', 'updateAiGateway', 'putAiGateway'
    )
  ORDER BY event_time DESC
""")
display(gateway_changes)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Cost Attribution View — SOLUTION

# COMMAND ----------

# SOLUTION: Create cost attribution view
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution AS
WITH usage_base AS (
  SELECT
    DATE(timestamp)                                   AS usage_date,
    endpoint_name,
    model_name,
    COALESCE(request_tags['team'],       'untagged')  AS team,
    COALESCE(request_tags['project'],    'untagged')  AS project,
    COALESCE(request_tags['environment'],'unknown')   AS environment,
    databricks_user_id                                AS user_id,
    COUNT(*)                                          AS request_count,
    SUM(input_tokens)                                 AS input_tokens,
    SUM(output_tokens)                                AS output_tokens,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited_requests,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END) AS blocked_requests,
    AVG(execution_time_ms)                            AS avg_latency_ms
  FROM system.ai_gateway.usage
  WHERE status_code = 200
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  usage_date, endpoint_name, model_name, team, project, environment, user_id,
  request_count, input_tokens, output_tokens,
  input_tokens + output_tokens                                    AS total_tokens,
  rate_limited_requests, blocked_requests,
  ROUND(avg_latency_ms, 0)                                       AS avg_latency_ms,
  ROUND(input_tokens  / 1000000.0 * 0.90, 4)                    AS est_input_cost_aud,
  ROUND(output_tokens / 1000000.0 * 2.70, 4)                    AS est_output_cost_aud,
  ROUND((input_tokens / 1000000.0 * 0.90) +
        (output_tokens / 1000000.0 * 2.70), 4)                  AS est_total_cost_aud
FROM usage_base
""")

print(f"View created: {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution")

# COMMAND ----------

# SOLUTION: Cost by team
cost_by_team = spark.sql(f"""
  SELECT
    DATE_TRUNC('month', usage_date)      AS billing_month,
    team,
    SUM(request_count)                   AS total_requests,
    SUM(total_tokens)                    AS total_tokens,
    ROUND(SUM(est_total_cost_aud), 2)    AS estimated_cost_aud
  FROM {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution
  GROUP BY 1, 2
  ORDER BY 1 DESC, estimated_cost_aud DESC
""")
display(cost_by_team)

# COMMAND ----------

# SOLUTION: Untagged requests
untagged = spark.sql("""
  SELECT
    DATE(timestamp)                     AS request_date,
    endpoint_name,
    databricks_user_id                  AS user_id,
    COUNT(*)                            AS untagged_count,
    SUM(input_tokens + output_tokens)   AS untagged_tokens
  FROM system.ai_gateway.usage
  WHERE
    timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND status_code = 200
    AND (request_tags['team'] IS NULL OR request_tags['project'] IS NULL)
  GROUP BY 1, 2, 3
  ORDER BY 1 DESC, untagged_tokens DESC
""")
display(untagged)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Dashboard Queries — SOLUTION

# COMMAND ----------

# SOLUTION: All dashboard charts
daily_by_team = spark.sql("""
  SELECT
    DATE(timestamp)                              AS usage_date,
    COALESCE(request_tags['team'], 'untagged')   AS team,
    SUM(input_tokens + output_tokens)            AS total_tokens,
    COUNT(*)                                     AS request_count
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS AND status_code = 200
  GROUP BY 1, 2 ORDER BY 1, 2
""")
display(daily_by_team)

# COMMAND ----------

endpoint_utilisation = spark.sql("""
  SELECT
    endpoint_name,
    COUNT(*)                                             AS total_requests,
    SUM(input_tokens + output_tokens)                    AS total_tokens,
    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END)  AS successful,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)  AS rate_limited,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)  AS blocked,
    ROUND(AVG(execution_time_ms), 0)                     AS avg_latency_ms,
    ROUND(SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS success_rate_pct
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY total_requests DESC
""")
display(endpoint_utilisation)

# COMMAND ----------

guardrail_summary = spark.sql("""
  SELECT
    CASE
      WHEN status_code = 200                                 THEN '200 Success'
      WHEN status_code = 429                                 THEN '429 Rate Limited'
      WHEN status_code = 400 AND guardrail_type = 'pii'     THEN '400 PII Blocked'
      WHEN status_code = 400 AND guardrail_type = 'safety'  THEN '400 Safety Blocked'
      WHEN status_code = 400                                 THEN '400 Other Block'
      ELSE CONCAT(CAST(status_code AS STRING), ' Other')
    END              AS outcome,
    COUNT(*)         AS request_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1 ORDER BY request_count DESC
""")
display(guardrail_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Budget Alert — SOLUTION

# COMMAND ----------

# SOLUTION: Budget thresholds
BUDGET_CONFIG = {
    "daily_warn_aud": 50.0,
    "daily_critical_aud": 100.0,
    "monthly_warn_aud": 500.0,
    "monthly_cap_aud": 1000.0,
    "alert_recipients": ["ai-platform-team@example.com.au", "data-governance@example.com.au"],
}


def check_daily_budget(budget_config):
    today = date.today().isoformat()
    result = spark.sql(f"""
      SELECT
        ROUND(SUM(input_tokens/1000000.0*0.90) + SUM(output_tokens/1000000.0*2.70), 2) AS cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE DATE(timestamp) = '{today}' AND status_code = 200
    """).collect()[0]
    cost = result["cost_aud"] or 0.0
    status = ("CRITICAL" if cost >= budget_config["daily_critical_aud"]
              else "WARN" if cost >= budget_config["daily_warn_aud"]
              else "OK")
    return {
        "check_date": today,
        "estimated_cost_aud": cost,
        "total_tokens": result["total_tokens"] or 0,
        "request_count": result["request_count"] or 0,
        "status": status,
        "daily_warn_threshold": budget_config["daily_warn_aud"],
        "daily_critical_threshold": budget_config["daily_critical_aud"],
    }


def check_monthly_budget(budget_config):
    today       = date.today()
    month_start = today.replace(day=1).isoformat()
    result = spark.sql(f"""
      SELECT
        ROUND(SUM(input_tokens/1000000.0*0.90) + SUM(output_tokens/1000000.0*2.70), 2) AS cost_aud,
        SUM(input_tokens + output_tokens) AS total_tokens,
        COUNT(*) AS request_count
      FROM system.ai_gateway.usage
      WHERE DATE(timestamp) >= '{month_start}' AND status_code = 200
    """).collect()[0]
    cost = result["cost_aud"] or 0.0
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed  = today.day
    projected     = cost * days_in_month / days_elapsed if days_elapsed > 0 else 0
    status = ("CAP_REACHED" if cost >= budget_config["monthly_cap_aud"]
              else "WARN" if cost >= budget_config["monthly_warn_aud"]
              else "OK")
    return {
        "month_start": month_start,
        "mtd_cost_aud": cost,
        "projected_monthly_cost_aud": round(projected, 2),
        "status": status,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
    }


def print_budget_report(daily, monthly):
    icons = {"OK": "[OK]", "WARN": "[WARN]", "CRITICAL": "[CRITICAL]", "CAP_REACHED": "[CAP]"}
    print(f"Daily  {icons.get(daily['status'])}: ${daily['estimated_cost_aud']:.2f} AUD  "
          f"({daily['request_count']:,} requests, {daily['total_tokens']:,} tokens)")
    print(f"Monthly {icons.get(monthly['status'])}: ${monthly['mtd_cost_aud']:.2f} AUD MTD  "
          f"(projected ${monthly['projected_monthly_cost_aud']:.2f})")


try:
    daily   = check_daily_budget(BUDGET_CONFIG)
    monthly = check_monthly_budget(BUDGET_CONFIG)
    print_budget_report(daily, monthly)
except Exception as e:
    print(f"Budget check failed (expected if no AI Gateway activity yet): {e}")

# COMMAND ----------

# SOLUTION: Save budget result to Delta
def save_budget_check(catalog, schema, daily, monthly):
    table = f"{catalog}.{schema}.ai_budget_checks"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    row = [{
        "check_timestamp":    datetime.now(timezone.utc).isoformat(),
        "check_date":         daily["check_date"],
        "daily_cost_aud":     daily["estimated_cost_aud"],
        "daily_status":       daily["status"],
        "mtd_cost_aud":       monthly["mtd_cost_aud"],
        "projected_cost_aud": monthly["projected_monthly_cost_aud"],
        "monthly_status":     monthly["status"],
    }]
    df = spark.createDataFrame(row)
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
    print(f"Budget check saved to: {table}")


try:
    save_budget_check(CATALOG_NAME, SCHEMA_NAME, daily, monthly)
except Exception as e:
    print(f"Save skipped (expected if no usage data): {e}")

# COMMAND ----------

print("=" * 60)
print("Lab 04 SOLUTION — Complete")
print("=" * 60)
print("  [DONE] system.ai_gateway.usage: recent requests, top users, trends, guardrail hits")
print("  [DONE] system.access.audit: serving, Genie, Playground, gateway change log")
print("  [DONE] Cost attribution view created")
print("  [DONE] Cost by team query (monthly rollup)")
print("  [DONE] Untagged request detection")
print("  [DONE] Dashboard charts: daily by team, endpoint utilisation, guardrail summary")
print("  [DONE] Daily and monthly budget check functions")
print("  [DONE] Budget result saved to Delta")
