# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 04: Monitoring Usage, Cost & Feedback</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 25 minutes |
# MAGIC | **Prerequisites** | Lab 03 complete — benchmarks run, at least one iteration done |
# MAGIC | **Covers** | Slides 19, 32 — Audit logging, feedback alerts, cost tracking |
# MAGIC
# MAGIC > *"Genie logs each event with user identity, timestamp, and workspace — done through System Tables."*
# MAGIC > *(Slide 19 — Audit Logging)*

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID")
SPACE_ID = dbutils.widgets.get("genie_space_id")
CATALOG  = "workshop_au"
SCHEMA   = "aemo"
HOST     = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN    = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS  = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
LOOKBACK = 30  # days
print(f"Monitoring last {LOOKBACK} days | Space: {SPACE_ID or 'all spaces'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Who is using Genie and how often?
# MAGIC
# MAGIC **🖱️ UI:** Monitor tab (top-level, not under Configure) (shows questions + ratings per user)
# MAGIC
# MAGIC **⚡ Automated — full usage breakdown:**

# COMMAND ----------

usage_sql = f"""
SELECT
    DATE(event_time)                        AS date,
    user_identity.email                     AS user,
    COUNT(CASE WHEN action_name = 'genieCreateConversationMessage' THEN 1 END) AS questions_asked,
    COUNT(CASE WHEN action_name = 'updateConversationMessageFeedback'
               AND request_params.feedback_rating = 'POSITIVE' THEN 1 END)    AS thumbs_up,
    COUNT(CASE WHEN action_name = 'updateConversationMessageFeedback'
               AND request_params.feedback_rating = 'NEGATIVE' THEN 1 END)    AS thumbs_down
FROM system.access.audit
WHERE service_name = 'aibiGenie'
  AND event_time  >= CURRENT_TIMESTAMP - INTERVAL {LOOKBACK} DAYS
  {"AND request_params.space_id = '" + SPACE_ID + "'" if SPACE_ID else ""}
GROUP BY date, user
ORDER BY date DESC, questions_asked DESC
"""

try:
    usage = spark.sql(usage_sql)
    total_users = usage.select("user").distinct().count()
    total_q     = usage.agg({"questions_asked": "sum"}).collect()[0][0] or 0
    print(f"Last {LOOKBACK} days: {total_users} users, {total_q} questions")
    display(usage)
except Exception as e:
    print(f"Note: {e}\nsystem.access.audit populates once the space is in use.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Feedback quality — what's working and what isn't?

# COMMAND ----------

feedback_sql = f"""
SELECT
    action_name,
    request_params.feedback_rating          AS rating,
    user_identity.email                     AS user,
    event_time,
    request_params.space_id                 AS space_id
FROM system.access.audit
WHERE service_name = 'aibiGenie'
  AND action_name  = 'updateConversationMessageFeedback'
  AND event_time  >= CURRENT_TIMESTAMP - INTERVAL {LOOKBACK} DAYS
  {"AND request_params.space_id = '" + SPACE_ID + "'" if SPACE_ID else ""}
ORDER BY event_time DESC
"""

try:
    feedback = spark.sql(feedback_sql)
    pos  = feedback.filter("rating = 'POSITIVE'").count()
    neg  = feedback.filter("rating = 'NEGATIVE'").count()
    total = pos + neg
    score = round(pos * 100 / total, 1) if total else None
    print(f"Feedback score: {score}% positive ({pos} 👍 / {neg} 👎) — last {LOOKBACK} days")
    if neg:
        print("→ Check the Monitor tab to see which questions got thumbs-down")
    display(feedback)
except Exception as e:
    print(f"Note: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Cost — how much is this Genie Space costing?
# MAGIC
# MAGIC Genie runs on serverless SQL warehouse. Cost is in serverless SQL DBUs.

# COMMAND ----------

cost_sql = f"""
SELECT
    DATE(usage_date)                        AS date,
    usage_metadata.warehouse_id             AS warehouse,
    SUM(usage_quantity)                     AS serverless_dbus,
    ROUND(SUM(usage_quantity) * 0.70, 2)   AS est_cost_usd
FROM system.billing.usage
WHERE sku_name LIKE '%SERVERLESS_SQL%'
  AND usage_date >= CURRENT_DATE - {LOOKBACK}
GROUP BY date, warehouse
ORDER BY date DESC, serverless_dbus DESC
"""

try:
    cost = spark.sql(cost_sql)
    total_dbus = cost.agg({"serverless_dbus": "sum"}).collect()[0][0] or 0
    total_usd  = cost.agg({"est_cost_usd": "sum"}).collect()[0][0] or 0
    print(f"Last {LOOKBACK} days: {round(total_dbus, 1)} serverless DBUs ≈ USD ${total_usd:.2f}")
    print("Note: multiply by your contracted DBU rate for actual cost")
    display(cost)
except Exception as e:
    print(f"Note: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Set up a feedback alert (Slide 32)
# MAGIC
# MAGIC > *"You can query the audit table and use that query in an alert."*
# MAGIC
# MAGIC **🖱️ UI to create the alert:**
# MAGIC ```
# MAGIC SQL Editor → new query → paste the SQL below → Run → Save as "Genie Negative Feedback Alert"
# MAGIC Alerts (left sidebar) → + Create alert
# MAGIC   → Query: Genie Negative Feedback Alert
# MAGIC   → Condition: negative_feedback_count > 0
# MAGIC   → Schedule: every 15 minutes
# MAGIC   → Notify: your email
# MAGIC → Save
# MAGIC ```

# COMMAND ----------

# Alert query — from Slide 32. Save this in SQL Editor and wire to an Alert.
alert_sql = f"""
SELECT
    COUNT(*) AS negative_feedback_count,
    COLLECT_LIST(user_identity.email) AS users_who_gave_negative
FROM system.access.audit
WHERE service_name = 'aibiGenie'
  AND action_name  = 'updateConversationMessageFeedback'
  AND request_params.feedback_rating = 'NEGATIVE'
  AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 60 MINUTES
  {"AND request_params.space_id = '" + SPACE_ID + "'" if SPACE_ID else ""}
"""

print("Save this as a SQL query and connect it to a Databricks Alert:\n")
print(alert_sql)

# Check if there's recent negative feedback right now
try:
    result = spark.sql(alert_sql).collect()[0]
    count  = result["negative_feedback_count"]
    if count:
        print(f"\n⚠️  {count} negative feedback(s) in the last 60 minutes — check the Monitor tab")
    else:
        print("\n✅ No negative feedback in the last 60 minutes")
except Exception as e:
    print(f"\nNote: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Build a monitoring dashboard
# MAGIC
# MAGIC **🖱️ UI — create the dashboard:**
# MAGIC ```
# MAGIC Dashboards (left sidebar) → + Create → AI/BI Dashboard
# MAGIC → Name: "AEMO Genie Space — Usage Monitor"
# MAGIC → Add canvas
# MAGIC ```
# MAGIC
# MAGIC **Add these 4 widgets using the queries above:**
# MAGIC
# MAGIC | Widget | Query | Chart type |
# MAGIC |---|---|---|
# MAGIC | Daily active users | Usage query grouped by date | Line chart (x=date, y=users) |
# MAGIC | Questions per user | Usage query grouped by user | Bar chart |
# MAGIC | Feedback score trend | Feedback query grouped by date | Line chart (pos vs neg) |
# MAGIC | Cost trend | Cost query grouped by date | Area chart |
# MAGIC
# MAGIC **⚡ Or: let Genie build it for you**
# MAGIC ```
# MAGIC Open a new Genie conversation (or use Genie Code in a notebook)
# MAGIC Ask: "Build a monitoring dashboard for Genie Space usage using system.access.audit
# MAGIC       and system.billing.usage. Include daily active users, feedback score,
# MAGIC       and serverless DBU cost trends."
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6: Summary view — everything in one table

# COMMAND ----------

summary_sql = f"""
WITH
questions AS (
    SELECT
        DATE(event_time)           AS date,
        COUNT(DISTINCT user_identity.email) AS active_users,
        COUNT(*)                   AS total_questions
    FROM system.access.audit
    WHERE service_name = 'aibiGenie'
      AND action_name  = 'genieCreateConversationMessage'
      AND event_time  >= CURRENT_TIMESTAMP - INTERVAL {LOOKBACK} DAYS
      {"AND request_params.space_id = '" + SPACE_ID + "'" if SPACE_ID else ""}
    GROUP BY date
),
fb AS (
    SELECT
        DATE(event_time) AS date,
        SUM(CASE WHEN request_params.feedback_rating = 'POSITIVE' THEN 1 ELSE 0 END) AS positive,
        SUM(CASE WHEN request_params.feedback_rating = 'NEGATIVE' THEN 1 ELSE 0 END) AS negative
    FROM system.access.audit
    WHERE service_name = 'aibiGenie'
      AND action_name  = 'updateConversationMessageFeedback'
      AND event_time  >= CURRENT_TIMESTAMP - INTERVAL {LOOKBACK} DAYS
    GROUP BY date
)
SELECT
    q.date,
    q.active_users,
    q.total_questions,
    COALESCE(fb.positive, 0)                                                    AS thumbs_up,
    COALESCE(fb.negative, 0)                                                    AS thumbs_down,
    CASE WHEN COALESCE(fb.positive,0)+COALESCE(fb.negative,0) > 0
         THEN ROUND(fb.positive * 100.0 / (fb.positive + fb.negative), 1)
         ELSE NULL END                                                          AS feedback_score_pct
FROM questions q
LEFT JOIN fb ON q.date = fb.date
ORDER BY q.date DESC
"""

try:
    summary = spark.sql(summary_sql)
    display(summary)
    print("\nSave this query and add it to a dashboard for ongoing monitoring.")
except Exception as e:
    print(f"Note: {e}\nRun this once the space has real users.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 04 Checkpoint
# MAGIC - [ ] Usage query run — understand who is asking questions
# MAGIC - [ ] Feedback score calculated — baseline for improvement tracking
# MAGIC - [ ] Cost query run — understand serverless DBU consumption
# MAGIC - [ ] Feedback alert SQL saved in SQL Editor
# MAGIC - [ ] Alert configured (or noted for post-session setup)
# MAGIC - [ ] Monitoring dashboard created (or planned)
# MAGIC
# MAGIC **→ Next: Lab 05 — Operating Model, Certification & Permissions**
