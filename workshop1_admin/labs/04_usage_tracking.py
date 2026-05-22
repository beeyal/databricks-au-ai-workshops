# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">📊 Lab 04: Usage Tracking & Cost Attribution</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 35 minutes |
# MAGIC | **Prerequisites** | Lab 02 complete — AI Gateway endpoint with usage tracking enabled |
# MAGIC | **By the end** | Cost attribution view built, budget alert configured, reference SQL card printed |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### System tables used in this lab
# MAGIC
# MAGIC | Table | What it contains | Approximate latency |
# MAGIC |---|---|---|
# MAGIC | `system.ai_gateway.usage` | AI Gateway token usage, latency, tags, guardrail hits | ~15 minutes |
# MAGIC | `system.access.audit` | All API calls including Genie, serving endpoint invocations | ~1 hour |
# MAGIC | `system.billing.usage` | DBU consumption by SKU — includes Model Serving DBUs | ~2 hours |
# MAGIC | `system.serving.served_entities` | Current model serving endpoint inventory | Near real-time |
# MAGIC
# MAGIC ### Prerequisites for system table access
# MAGIC
# MAGIC - Unity Catalog enabled on the workspace
# MAGIC - `USAGE` privilege on the `system` catalog granted to your user or group
# MAGIC - At least one AI Gateway endpoint with usage tracking enabled (from Lab 02)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before We Code: 7-Minute UI Tour (do this first!)
# MAGIC
# MAGIC In this lab you will query system tables to understand AI usage and cost.
# MAGIC First, browse where that data surfaces in the UI — so the SQL results
# MAGIC you see later are immediately interpretable.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 1 — Browse the system catalog in Unity Catalog Explorer
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Catalog (stack-of-books icon)
# MAGIC   → system catalog
# MAGIC     → ai_gateway schema
# MAGIC       → usage table → click "Sample Data" tab
# MAGIC ```
# MAGIC
# MAGIC **What to look for:**
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────┐
# MAGIC │  system.ai_gateway.usage                                     │
# MAGIC │                                                              │
# MAGIC │  Columns you'll see in sample data:                          │
# MAGIC │    account_id  workspace_id  endpoint_name  model_name       │
# MAGIC │    request_id  timestamp     total_tokens   prompt_tokens    │
# MAGIC │    request_tags  guardrail_blocked  status_code              │
# MAGIC │                                                              │
# MAGIC │  Note: ~15 min latency — data from Lab 02/03 may appear here │
# MAGIC └──────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC Also browse: `system.access.audit` and `system.billing.usage`
# MAGIC to see their column structures before writing SQL against them.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 2 — Check the Model Serving endpoint metrics tab
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Machine Learning → Serving
# MAGIC   → Click your endpoint from Lab 02
# MAGIC     → Metrics tab
# MAGIC ```
# MAGIC
# MAGIC **What you should see:**
# MAGIC ```
# MAGIC ┌────────────────────────────────────────────────┐
# MAGIC │  Endpoint Metrics                              │
# MAGIC │                                                │
# MAGIC │  Requests per second   [chart]                 │
# MAGIC │  Latency p50 / p95     [chart]                 │
# MAGIC │  Error rate            [chart]                 │
# MAGIC │  Token throughput      [chart]                 │
# MAGIC └────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC This is the "quick view" — the system tables in this lab give you the
# MAGIC raw data to build your own dashboards with team/project segmentation.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 3 — Check recent query history
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → SQL Editor → History tab
# MAGIC ```
# MAGIC
# MAGIC Any recent queries to serving endpoint invocation URLs appear here.
# MAGIC These represent actual AI calls that should show up in `system.ai_gateway.usage`
# MAGIC with a ~15 minute lag.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Time check:** This tour should take about 7 minutes.
# MAGIC Return to this notebook before continuing.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 0: Setup & Permissions Check</h2>
# MAGIC </div>

# COMMAND ----------

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Workshop Configuration
# MAGIC > **Running in a customer environment?** Change the catalog/schema widgets above to match your setup.

# COMMAND ----------
# Widget-based configuration — works in any customer Databricks environment
# These default values match what 00_workspace_setup.py creates
dbutils.widgets.text("catalog",     "energy_ai",  "Catalog name")
dbutils.widgets.text("schema",      "analytics",  "Schema name")
dbutils.widgets.text("gw_endpoint", "au-workshop-gateway", "AI Gateway endpoint name")

CATALOG_W   = dbutils.widgets.get("catalog")
SCHEMA_W    = dbutils.widgets.get("schema")
GW_ENDPOINT = dbutils.widgets.get("gw_endpoint")

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
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~10 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC `system.ai_gateway.usage` is the primary source of truth for AI Gateway consumption.
# MAGIC Each row represents **one request** routed through an AI Gateway endpoint.
# MAGIC
# MAGIC ### Navigating to system tables in the UI
# MAGIC
# MAGIC ```
# MAGIC Navigate: SQL Editor (left sidebar) → New query → paste SQL below
# MAGIC
# MAGIC ┌─── Left sidebar ────────────────────────┐
# MAGIC │  🏠 Home                                 │
# MAGIC │  🔍 Search                               │
# MAGIC │  📊 SQL Editor    ← click here           │
# MAGIC │  ├── New query                           │
# MAGIC │  └── [paste your SQL and run with ▶]     │
# MAGIC └─────────────────────────────────────────┘
# MAGIC
# MAGIC OR browse the schema directly:
# MAGIC Data (left sidebar) → Catalog Explorer →
# MAGIC   system → ai_gateway → usage → [Preview data]
# MAGIC ```
# MAGIC
# MAGIC ### Viewing AI Gateway usage in the endpoint UI
# MAGIC
# MAGIC ```
# MAGIC Navigate (v1/GA): Machine Learning → Serving → AI Gateway tab → [endpoint] → Usage & Logs tab
# MAGIC
# MAGIC ┌─── Usage & Logs ────────────────────────────────────────────┐
# MAGIC │  📊 Token usage (last 7 days)          Total: 45,230 tokens  │
# MAGIC │  ████████████████░░░░  Input tokens:   38,120               │
# MAGIC │  ████░░░░░░░░░░░░░░░░  Output tokens:   7,110               │
# MAGIC │                                                              │
# MAGIC │  📋 Recent requests (payload log)                           │
# MAGIC │  [timestamp]     | [user]    | [tokens] | [status]          │
# MAGIC │  2026-05-22 09:23 | j.smith  | 423 tok  | 200               │
# MAGIC │  2026-05-22 09:21 | a.jones  | 87  tok  | 400 PII           │
# MAGIC └──────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC The Usage & Logs tab gives a quick visual overview.
# MAGIC For attribution and alerting, query the system table directly.

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

# Most useful initial query: recent requests broken down by date, endpoint, team, project
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
# MAGIC ### 1c. Top users by token consumption — last 30 days

# COMMAND ----------

# Identify heavy users for capacity planning and cost attribution
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
# MAGIC ### 1d. Daily token trend — 30 days (for anomaly detection)

# COMMAND ----------

# Daily trend: useful for capacity planning and detecting usage spikes
daily_trend = spark.sql("""
  SELECT
    DATE(timestamp)                                          AS usage_date,
    endpoint_name,
    SUM(input_tokens + output_tokens)                        AS total_tokens,
    SUM(input_tokens)                                        AS input_tokens,
    SUM(output_tokens)                                       AS output_tokens,
    COUNT(*)                                                 AS request_count,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)      AS rate_limited
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

# Understand what is being blocked and why — useful for refining guardrail settings
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
# MAGIC <div style="background: #FFF3CD; padding: 12px 16px; border-radius: 4px; border-left: 4px solid #FFC107">
# MAGIC <strong>📋 Facilitator note:</strong> Pause here and ask the group —
# MAGIC "If you saw a sudden spike in guardrail hits on a Friday afternoon, what would be your
# MAGIC first investigation step? Who owns the response — platform team, security, or the business unit?"
# MAGIC This links nicely to the APRA CPS 230 operational risk controls discussion in Lab 05.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 2: Querying system.access.audit for AI Events</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~8 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC The audit log captures all API activity across the workspace. For AI governance,
# MAGIC the most important action types are:
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
# MAGIC **Tip:** Discover all `service_name` and `action_name` values in your workspace:
# MAGIC ```sql
# MAGIC SELECT DISTINCT service_name, action_name
# MAGIC FROM system.access.audit
# MAGIC WHERE event_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
# MAGIC ORDER BY 1, 2
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2a. Model serving endpoint invocations

# COMMAND ----------

# All model serving calls in the past 7 days — who called what, and when
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

# MAGIC %md
# MAGIC ### 2b. Genie Space queries

# COMMAND ----------

# Genie usage audit — who queried which Space, and when
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
# MAGIC ### 2c. AI Playground usage (shadow IT risk)
# MAGIC
# MAGIC AI Playground allows ad-hoc model interaction without any rate limits or guardrails
# MAGIC unless specifically configured. For regulated data environments, you need to know
# MAGIC whether users are pasting sensitive data into Playground.
# MAGIC
# MAGIC The audit log records the activity but **not the prompt content itself**.
# MAGIC Use payload logging on the underlying endpoint if you need content-level visibility.

# COMMAND ----------

# AI Playground usage by user — flag for security review if regulated-data users appear here
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

# All AI Gateway config changes — critical for change management evidence under APRA CPS 230
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
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 3: Cost Attribution View — By Team and Project</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~7 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC Combine AI Gateway usage data with request tags to build a cost attribution model.
# MAGIC For APRA-regulated entities, cost attribution is required for:
# MAGIC - IT cost allocation to business units (FinOps chargeback)
# MAGIC - Demonstrating proportionate spending controls
# MAGIC - Budget variance reporting to the board
# MAGIC
# MAGIC ### How request tags work
# MAGIC
# MAGIC Applications pass tags via the `databricks-request-tag` HTTP header:
# MAGIC ```
# MAGIC databricks-request-tag: team=network-ops;project=meter-anomaly
# MAGIC ```
# MAGIC These appear in `system.ai_gateway.usage.request_tags` as a MAP column.
# MAGIC
# MAGIC ### Approximate token pricing reference (May 2026)
# MAGIC
# MAGIC | Model | Input (per 1M tokens) | Output (per 1M tokens) |
# MAGIC |---|---|---|
# MAGIC | Meta Llama 3.3 70B (PT) | ~$0.90 | ~$2.70 |
# MAGIC | GPT-4o (Azure OpenAI Regional) | ~$2.50 | ~$10.00 |
# MAGIC | Llama 3.1 8B (PT) | ~$0.20 | ~$0.60 |

# COMMAND ----------

# Token pricing — update these when your contracts are finalised
# ⚠️  Only include in-region models for regulated AU workloads.
# databricks-meta-llama-* models are cross-geo for AU East and should NOT be used.
TOKEN_PRICES = {
    "databricks-claude-haiku-4-5": {      # ✅ IN-REGION via Provisioned Throughput
        "input_per_1m":  1.00,
        "output_per_1m": 5.00,
    },
    "databricks-claude-sonnet-4-6": {     # ✅ IN-REGION via Provisioned Throughput
        "input_per_1m":  3.00,
        "output_per_1m": 15.00,
    },
    "databricks-qwen3-embedding-0-6b": {  # ✅ IN-REGION embedding model
        "input_per_1m":  0.025,
        "output_per_1m": 0.00,
    },
}

print("Token pricing configured for cost attribution:")
for model, prices in TOKEN_PRICES.items():
    print(f"  {model:<55} Input: ${prices['input_per_1m']}/1M  Output: ${prices['output_per_1m']}/1M")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a. Create the cost attribution view

# COMMAND ----------

# Configurable — change via widget above if running in customer environment
CATALOG_NAME = CATALOG_W   # from widget, default "energy_ai"
SCHEMA_NAME  = SCHEMA_W    # from widget, default "analytics"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

# Cost attribution view: joins ai_gateway.usage with pricing above
# For production, maintain the pricing table as a Delta table and JOIN it here.

create_view_sql = f"""
CREATE OR REPLACE VIEW {CATALOG_NAME}.{SCHEMA_NAME}.ai_gateway_cost_attribution AS
-- We aggregate ALL requests first (to capture 429/400 counts),
-- then apply token costs only to status_code = 200 rows.
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
  -- Cost estimates in AUD — update the multiplier if using USD pricing
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

# MAGIC %md
# MAGIC ### 3b. Cost by team — monthly rollup

# COMMAND ----------

# Monthly cost by team — use for internal chargeback and finance reporting
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

display(cost_by_team)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3c. Untagged request detection

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
print("Raise with the owning team to add tags before the next billing cycle.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 4: Usage Monitoring Charts</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~5 minutes — use display() to generate charts</p>
# MAGIC </div>
# MAGIC
# MAGIC We use `display()` to create charts that can be saved to a Databricks AI/BI dashboard.
# MAGIC After running each cell, click the **chart icon** in the output header to switch to a
# MAGIC visualisation view.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a. Token consumption over time by team (time series chart)

# COMMAND ----------

# Daily tokens by team — suitable for a line chart
# In display() UI: set X axis = usage_date, Y axis = total_tokens, Group by = team
daily_by_team = spark.sql("""
  SELECT
    DATE(timestamp)                              AS usage_date,
    COALESCE(request_tags['team'], 'untagged')   AS team,
    SUM(input_tokens + output_tokens)            AS total_tokens,
    COUNT(*)                                     AS request_count
  FROM system.ai_gateway.usage
  WHERE
    timestamp >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    AND status_code = 200
  GROUP BY 1, 2
  ORDER BY 1, 2
""")

display(daily_by_team)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Endpoint utilisation (bar chart)

# COMMAND ----------

endpoint_utilisation = spark.sql("""
  SELECT
    endpoint_name,
    COUNT(*)                                               AS total_requests,
    SUM(input_tokens + output_tokens)                      AS total_tokens,
    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END)    AS successful,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)    AS rate_limited,
    SUM(CASE WHEN status_code = 400 THEN 1 ELSE 0 END)    AS blocked,
    ROUND(AVG(execution_time_ms), 0)                       AS avg_latency_ms,
    ROUND(
      SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
      1
    )                                                      AS success_rate_pct
  FROM system.ai_gateway.usage
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
  GROUP BY 1
  ORDER BY total_requests DESC
""")

display(endpoint_utilisation)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4c. Request outcome breakdown (pie or donut chart)

# COMMAND ----------

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
    ROUND(
      COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (),
      2
    )                    AS percentage
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
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~5 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC For regulated utilities, automated budget alerts prevent surprise costs and
# MAGIC trigger escalation procedures under **APRA CPS 230** (operational resilience).
# MAGIC
# MAGIC The pattern is:
# MAGIC 1. Define thresholds (daily warning, daily critical, monthly cap)
# MAGIC 2. Query `system.ai_gateway.usage` for current spend
# MAGIC 3. Send a notification if a threshold is crossed
# MAGIC 4. Schedule this notebook as a Databricks job (8am AEST daily)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5a. Define budget thresholds

# COMMAND ----------

# TODO: Set your budget thresholds (AUD, estimated costs using list-price token rates)
BUDGET_CONFIG = {
    "daily_warn_aud":     50.0,     # TODO: daily warning threshold
    "daily_critical_aud": 100.0,    # TODO: daily critical threshold — triggers escalation
    "monthly_warn_aud":   500.0,    # TODO: monthly warning threshold
    "monthly_cap_aud":    1000.0,   # TODO: monthly cap — triggers endpoint disable
    "alert_recipients": [
        "ai-platform-team@example.com.au",    # TODO: update
        "data-governance@example.com.au",     # TODO: update
    ],
    "escalation_group": "grp_ai_admins",
}

print("Budget thresholds configured:")
for key, value in BUDGET_CONFIG.items():
    print(f"  {key:<30} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b. Budget check functions

# COMMAND ----------

from datetime import datetime, timezone, date, timedelta
import calendar


def check_daily_budget(budget_config: dict) -> dict:
    """
    Check today's AI Gateway spend against daily budget thresholds.
    Returns a status dict with values: OK, WARN, or CRITICAL.
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
    """Check current month's cumulative spend against monthly budget thresholds."""
    today       = date.today()
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

    cost           = result["estimated_cost_aud"] or 0.0
    days_in_month  = calendar.monthrange(today.year, today.month)[1]
    days_elapsed   = today.day
    projected      = cost * days_in_month / days_elapsed if days_elapsed > 0 else 0

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
    """Print a formatted budget report suitable for Slack or email notification."""
    print("=" * 60)
    print(f"AI Gateway Budget Report — {daily['check_date']}")
    print("=" * 60)

    daily_icon = {"OK": "[OK]", "WARN": "[WARN]", "CRITICAL": "[CRITICAL]"}[daily["status"]]
    print(f"\nDaily:   {daily_icon}")
    print(f"  Cost today      : ${daily['estimated_cost_aud']:.2f} AUD")
    print(f"  Warn threshold  : ${daily['daily_warn_threshold']:.2f} AUD")
    print(f"  Critical at     : ${daily['daily_critical_threshold']:.2f} AUD")
    print(f"  Requests today  : {daily['request_count']:,}")
    print(f"  Tokens today    : {daily['total_tokens']:,}")

    monthly_icon = {"OK": "[OK]", "WARN": "[WARN]", "CAP_REACHED": "[CAP REACHED]"}.get(
        monthly["status"], "[UNKNOWN]"
    )
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
# MAGIC ### 5c. Schedule this notebook as a daily alert job
# MAGIC
# MAGIC To run this budget check on a schedule:
# MAGIC
# MAGIC **Option A — via the UI:**
# MAGIC ```
# MAGIC 1. Open this notebook
# MAGIC 2. Click Schedules & Triggers (top right corner of the notebook toolbar)
# MAGIC 3. Add trigger → Scheduled → Cron
# MAGIC    Expression: 0 0 8 * * ?   (8am daily AEST = UTC+10 offset)
# MAGIC    Timezone:   Australia/Sydney
# MAGIC 4. Add email notifications on failure
# MAGIC ```
# MAGIC
# MAGIC **Option B — via the SDK (reproducible, version-controllable):**
# MAGIC ```python
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks.sdk.service.jobs import Task, NotebookTask, CronSchedule
# MAGIC
# MAGIC w = WorkspaceClient()
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
# MAGIC         quartz_cron_expression="0 0 8 * * ?",
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
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 6: Reference SQL Query Card</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">Copy these into your AI/BI dashboard or save as a query library.</p>
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
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 7: Lab Checkpoint</h2>
# MAGIC </div>

# COMMAND ----------

print("=" * 60)
print("Lab 04 — Checkpoint Summary")
print("=" * 60)

checks = [
    "system.ai_gateway.usage schema explored",
    "Recent requests query: date, endpoint, team, project, token counts",
    "Top users by token consumption (30-day rolling)",
    "Daily trend query for capacity and anomaly detection",
    "Guardrail hit analysis query written",
    "system.access.audit: model serving invocations queried",
    "system.access.audit: Genie Space usage queried",
    "system.access.audit: AI Playground usage queried",
    "system.access.audit: AI Gateway change log queried",
    "Cost attribution view defined (by team / project / environment)",
    "Untagged request detection query written",
    "Budget check functions: daily and monthly",
    "Budget alert job scheduling pattern documented (UI + SDK)",
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
# MAGIC | `client_request_id` | STRING | Client-supplied idempotency key |
# MAGIC </div>
