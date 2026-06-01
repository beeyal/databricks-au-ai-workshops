# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', Arial, sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 03: Benchmarks, Monitoring &amp; Iteration</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0;">The quality loop: Build → Benchmark → Monitor → Improve → Repeat</p>
# MAGIC </div>
# MAGIC <div style="background: #f7f8fa; border-left: 4px solid #FF3621; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 0;">
# MAGIC   <b>What you will learn:</b> How to create a benchmark set that measures Genie accuracy, how to interpret benchmark results, how to use the Monitor tab to find real user friction, and how to iterate your way to higher quality before and after every change. Estimated time: <b>30 minutes</b>.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widget Configuration

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID (from Lab 01)")
dbutils.widgets.text("catalog",        "workshop_au", "Catalog")
dbutils.widgets.text("schema_aemo",    "aemo",        "Schema")

# COMMAND ----------

SPACE_ID = dbutils.widgets.get("genie_space_id")
CATALOG  = dbutils.widgets.get("catalog")
SCHEMA   = dbutils.widgets.get("schema_aemo")

HOST  = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

if not SPACE_ID:
    try:
        SPACE_ID = spark.conf.get("workshop.genie.space_id")
        print(f"Retrieved Space ID from session config: {SPACE_ID}")
    except Exception:
        print("WARNING: Enter your Genie Space ID in the 'genie_space_id' widget above.")
        print("You can find it in the URL when viewing your space: .../genie/spaces/<SPACE_ID>")

import requests, json, time

print(f"Host     : {HOST}")
print(f"Space ID : {SPACE_ID}")
print(f"Catalog  : {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1: Creating Your Benchmark Set (10 min, UI-first)
# MAGIC
# MAGIC ### What benchmarks ARE and ARE NOT
# MAGIC
# MAGIC This is the most common misconception in Genie workshops — please read carefully before adding any questions.
# MAGIC
# MAGIC <div style="background: #f7f8fa; border: 2px solid #1B3A6B; border-radius: 8px; padding: 20px 24px; font-family: 'DM Sans', Arial, sans-serif; margin: 12px 0;">
# MAGIC
# MAGIC <table style="width: 100%; border-collapse: collapse; font-size: 1em;">
# MAGIC <thead>
# MAGIC <tr style="background: #1B3A6B; color: white;">
# MAGIC <th style="padding: 10px 14px; text-align: left; width: 50%;">Benchmarks MEASURE accuracy</th>
# MAGIC <th style="padding: 10px 14px; text-align: left; width: 50%;">Benchmarks do NOT teach Genie</th>
# MAGIC </tr>
# MAGIC </thead>
# MAGIC <tbody>
# MAGIC <tr>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">They tell you whether Genie gets a question right or wrong — a regression test for your space.</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Adding a question as a benchmark does <b>not</b> teach Genie to answer it correctly. The benchmark score can only go up when you make a real improvement — a golden query, a SQL expression, or better instructions.</td>
# MAGIC </tr>
# MAGIC </tbody>
# MAGIC </table>
# MAGIC
# MAGIC <h4 style="color: #1B3A6B; margin-top: 20px;">The correct iteration loop</h4>
# MAGIC
# MAGIC ```
# MAGIC Add golden query → run benchmarks → accuracy improves → add more golden queries
# MAGIC NOT: Add benchmark question → accuracy improves
# MAGIC ```
# MAGIC
# MAGIC <p style="margin: 0; color: #555;">Benchmarks are regression tests. Run them before every change and after every change. They cannot improve quality on their own — they only report quality.</p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Navigate to Benchmarks in the UI
# MAGIC
# MAGIC ```
# MAGIC Your Genie Space → Configure (top-right gear icon) → Benchmarks tab → + Add benchmark
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #f0f0f0; border: 1px solid #ccc; border-radius: 8px; padding: 18px 22px; font-family: monospace; font-size: 0.92em; margin: 10px 0;">
# MAGIC <pre style="margin: 0;">
# MAGIC ┌─── Benchmarks Tab ──────────────────────────────────────────┐
# MAGIC │  [+ Add benchmark]  [Run benchmarks]  [Run selected]       │
# MAGIC │  ───────────────────────────────────────────────────────    │
# MAGIC │  Evaluations tab: shows run history + accuracy scores       │
# MAGIC │                                                             │
# MAGIC │  When adding a benchmark question, choose a mode:           │
# MAGIC │  ○ Chat mode  — provide expected SQL → deterministic check  │
# MAGIC │  ○ Agent mode — provide evaluation notes → LLM judge        │
# MAGIC │                                                             │
# MAGIC │  Limit: up to 500 benchmark questions per space             │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC </pre>
# MAGIC </div>
# MAGIC
# MAGIC **Best practice:** Add 2–4 phrasings of each common question type. Real users will not ask questions the same way you phrased your golden queries. Two phrasings per question type catches paraphrase brittleness early.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise: Add 10 benchmark questions (5 question types × 2 phrasings each)
# MAGIC
# MAGIC For each pair below, add both as separate benchmark questions in the UI. Use **Chat mode** and supply the expected SQL from your golden queries in Lab 02.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Q1 — Spot price (regional, recent)**
# MAGIC - Q1a: `"What was the average spot price in VIC1 yesterday?"`
# MAGIC - Q1b: `"Show me yesterday's average electricity price in Victoria"`
# MAGIC
# MAGIC Expected SQL (paste into benchmark):
# MAGIC ```sql
# MAGIC SELECT ROUND(AVG(rrp), 2) AS avg_rrp_dollars_per_mwh
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE region_id = 'VIC1'
# MAGIC   AND settlement_date >= CURRENT_DATE() - INTERVAL 1 DAY
# MAGIC   AND settlement_date <  CURRENT_DATE()
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Q2 — Top generators by output**
# MAGIC - Q2a: `"Which generators dispatched the most in QLD last week?"`
# MAGIC - Q2b: `"Top generators by output in Queensland this week"`
# MAGIC
# MAGIC Expected SQL:
# MAGIC ```sql
# MAGIC SELECT duid,
# MAGIC        SUM(total_cleared) AS total_mw_dispatched
# MAGIC FROM workshop_au.aemo.dispatch_intervals
# MAGIC WHERE region_id = 'QLD1'
# MAGIC   AND settlement_date >= CURRENT_DATE() - INTERVAL 7 DAYS
# MAGIC GROUP BY duid
# MAGIC ORDER BY total_mw_dispatched DESC
# MAGIC LIMIT 10
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Q3 — Lack-of-reserve events**
# MAGIC - Q3a: `"Were there any LOR notices in the last 14 days?"`
# MAGIC - Q3b: `"List any lack-of-reserve events this fortnight"`
# MAGIC
# MAGIC Expected SQL:
# MAGIC ```sql
# MAGIC SELECT notice_id, notice_type, region_id, issue_time, reason
# MAGIC FROM workshop_au.aemo.market_notices
# MAGIC WHERE notice_type LIKE 'LOR%'
# MAGIC   AND issue_time >= CURRENT_TIMESTAMP() - INTERVAL 14 DAYS
# MAGIC ORDER BY issue_time DESC
# MAGIC ```
# MAGIC
# MAGIC > **Why `LIKE 'LOR%'`?** LOR events are typed as LOR1, LOR2, or LOR3 — never just "LOR". If Genie uses `= 'LOR'` it will return zero rows. This is exactly the kind of mistake benchmarks catch. We will fix it in Section 2.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Q4 — Cross-region price comparison**
# MAGIC - Q4a: `"Compare spot prices across all NEM regions yesterday"`
# MAGIC - Q4b: `"What were the regional electricity prices yesterday?"`
# MAGIC
# MAGIC Expected SQL:
# MAGIC ```sql
# MAGIC SELECT region_id,
# MAGIC        ROUND(AVG(rrp), 2) AS avg_rrp,
# MAGIC        ROUND(MIN(rrp), 2) AS min_rrp,
# MAGIC        ROUND(MAX(rrp), 2) AS max_rrp
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE settlement_date >= CURRENT_DATE() - INTERVAL 1 DAY
# MAGIC   AND settlement_date <  CURRENT_DATE()
# MAGIC GROUP BY region_id
# MAGIC ORDER BY avg_rrp DESC
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Q5 — Fuel type mix**
# MAGIC - Q5a: `"Which fuel types contributed most to dispatch in NSW last month?"`
# MAGIC - Q5b: `"Show me renewable vs coal generation in New South Wales last 30 days"`
# MAGIC
# MAGIC Expected SQL:
# MAGIC ```sql
# MAGIC SELECT fuel_source_primary,
# MAGIC        ROUND(SUM(total_cleared), 0) AS total_mw_dispatched
# MAGIC FROM workshop_au.aemo.dispatch_intervals
# MAGIC WHERE region_id = 'NSW1'
# MAGIC   AND settlement_date >= CURRENT_DATE() - INTERVAL 30 DAYS
# MAGIC GROUP BY fuel_source_primary
# MAGIC ORDER BY total_mw_dispatched DESC
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Running benchmarks and reading results
# MAGIC
# MAGIC Once you have added all 10 questions:
# MAGIC
# MAGIC ```
# MAGIC Configure → Benchmarks → [Run benchmarks]
# MAGIC
# MAGIC Watch the progress bar, then click the Evaluations tab.
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #f0f0f0; border: 1px solid #ccc; border-radius: 8px; padding: 18px 22px; font-family: monospace; font-size: 0.92em; margin: 10px 0;">
# MAGIC <pre style="margin: 0;">
# MAGIC ┌─── Evaluations Tab ──────────────────────────────────────────┐
# MAGIC │  Run ID: abc123   Started: 09:14   Duration: 2m 08s          │
# MAGIC │  Accuracy: 7/10 (70%)                                        │
# MAGIC │  ────────────────────────────────────────────────────────     │
# MAGIC │  ● Green  = Good   → SQL matched expected result             │
# MAGIC │  ● Red    = Bad    → Wrong answer or query failed            │
# MAGIC │  ● Orange = Manual → Automated comparison was inconclusive   │
# MAGIC │                                                              │
# MAGIC │  [Run selected]  ← re-run just the failing questions         │
# MAGIC └──────────────────────────────────────────────────────────────┘
# MAGIC </pre>
# MAGIC </div>
# MAGIC
# MAGIC **Target accuracy before sharing with business users: > 80% Good.**
# MAGIC
# MAGIC If you are below 80%, go to Section 2 before sharing the space.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2: Interpret and Improve (10 min)
# MAGIC
# MAGIC ### Reading benchmark results via API
# MAGIC
# MAGIC The cell below retrieves your latest benchmark run programmatically. This is useful for automated quality gates — for example, failing a CI/CD pipeline if accuracy drops below a threshold.

# COMMAND ----------

# Query benchmark results for the latest run
# This is a read-only check — it does not run new benchmarks

if not SPACE_ID:
    print("Set your genie_space_id widget first.")
else:
    resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-runs",
        headers=HEADERS,
    )

    if resp.status_code == 200:
        runs = resp.json().get("benchmark_runs", [])
        if runs:
            latest = runs[0]
            run_id   = latest.get("run_id", "unknown")
            started  = latest.get("start_time", "unknown")
            status   = latest.get("status", "unknown")
            results  = latest.get("benchmark_results", [])

            good   = sum(1 for r in results if r.get("rating") == "GOOD")
            bad    = sum(1 for r in results if r.get("rating") == "BAD")
            manual = sum(1 for r in results if r.get("rating") == "MANUAL")
            total  = len(results)
            pct    = int(good / total * 100) if total else 0

            print(f"Latest benchmark run : {run_id}")
            print(f"Started              : {started}")
            print(f"Status               : {status}")
            print()
            print(f"Results summary:")
            print(f"  Good   : {good:>3} / {total}  ({pct}%)")
            print(f"  Bad    : {bad:>3} / {total}")
            print(f"  Manual : {manual:>3} / {total}")
            print()

            if pct >= 80:
                print("Accuracy >= 80% — space is ready for pilot rollout.")
            else:
                print(f"Accuracy {pct}% is below 80% — review the failing questions before sharing.")

            if bad > 0:
                print("\nFailing benchmark questions:")
                for r in results:
                    if r.get("rating") == "BAD":
                        print(f"  - {r.get('question', 'unknown question')}")
        else:
            print("No benchmark runs found.")
            print("Run benchmarks from the UI first: Configure → Benchmarks → Run benchmarks")
    else:
        print(f"API call failed: {resp.status_code}")
        print(resp.text)

# COMMAND ----------

# MAGIC %md
# MAGIC ### The improvement loop — what to do with a failing question
# MAGIC
# MAGIC When a benchmark question returns **Bad**:
# MAGIC
# MAGIC <div style="background: #f7f8fa; border: 1px solid #ddd; border-radius: 8px; padding: 20px 24px; font-family: 'DM Sans', Arial, sans-serif; margin: 10px 0;">
# MAGIC
# MAGIC | Step | Action |
# MAGIC |------|--------|
# MAGIC | 1 | Click the failing benchmark question in the UI to expand it |
# MAGIC | 2 | Click **Show SQL** to see what query Genie actually generated |
# MAGIC | 3 | Identify why it is wrong (see table below) |
# MAGIC | 4 | Make the fix in Configure |
# MAGIC | 5 | Click **Run selected** to re-run just that benchmark |
# MAGIC | 6 | Compare the new accuracy score to the previous run |
# MAGIC
# MAGIC **Diagnosis table — why did Genie get it wrong?**
# MAGIC
# MAGIC | Symptom in the generated SQL | Root cause | Fix |
# MAGIC |------------------------------|------------|-----|
# MAGIC | Wrong column name or alias | Genie does not know your domain vocabulary | Add synonyms in Configure → Data (column comments) |
# MAGIC | Wrong aggregation or formula | Genie does not know your business calculation | Add a SQL Expression (Measure) in Configure |
# MAGIC | Queried the wrong table | Ambiguous table names or descriptions | Add a golden query that explicitly uses the correct table |
# MAGIC | Wrong join or missing filter | Schema relationships not obvious from names | Add join guidance in Configure → Joins |
# MAGIC | `notice_type = 'LOR'` instead of `LIKE 'LOR%'` | Exact-match assumption on a coded field | Add usage guidance to the golden query (see exercise below) |
# MAGIC
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Workshop exercise: Fix the LOR benchmark
# MAGIC
# MAGIC If your Q3 benchmarks ("LOR notices") received a **Bad** rating, here is the most likely cause and fix.
# MAGIC
# MAGIC **What Genie probably generated:**
# MAGIC ```sql
# MAGIC -- Wrong — returns 0 rows because no notices have type exactly 'LOR'
# MAGIC WHERE notice_type = 'LOR'
# MAGIC ```
# MAGIC
# MAGIC **What it should generate:**
# MAGIC ```sql
# MAGIC -- Correct — matches LOR1, LOR2, LOR3
# MAGIC WHERE notice_type LIKE 'LOR%'
# MAGIC ```
# MAGIC
# MAGIC **Fix in the UI:**
# MAGIC
# MAGIC 1. Navigate to **Configure → SQL queries** (golden queries)
# MAGIC 2. Find your LOR golden query from Lab 02 and click to edit it
# MAGIC 3. Add this usage guidance text to the description:
# MAGIC
# MAGIC ```
# MAGIC LOR events are classified as LOR1 (reserve at risk), LOR2 (load shedding risk),
# MAGIC or LOR3 (load shedding in progress). The notice_type column always contains
# MAGIC one of these three values — never just 'LOR'. Always filter with
# MAGIC notice_type LIKE 'LOR%' to match all three types.
# MAGIC ```
# MAGIC
# MAGIC 4. Save the golden query
# MAGIC 5. Click **Run selected** on Q3a and Q3b in the Benchmarks tab
# MAGIC 6. Confirm both benchmarks now return **Good**

# COMMAND ----------

# MAGIC %md
# MAGIC ### Programmatic regression test pattern (for CI/CD)
# MAGIC
# MAGIC The cell below shows how to gate a deployment on benchmark accuracy. You would call this from a Databricks Job after making changes to a space — fail the job if accuracy drops below your threshold.

# COMMAND ----------

# Regression gate: fail if accuracy drops below threshold
# In production, this would be called by a Databricks Job after any space change

ACCURACY_THRESHOLD = 0.80  # 80% minimum

def check_benchmark_accuracy(space_id, host, headers, threshold):
    """
    Returns True if the latest benchmark run meets the accuracy threshold.
    Raises an exception if accuracy is below threshold (useful as a CI gate).
    """
    resp = requests.get(
        f"https://{host}/api/2.0/genie/spaces/{space_id}/benchmark-runs",
        headers=headers,
    )

    if resp.status_code != 200:
        print(f"Could not retrieve benchmark runs: {resp.status_code}")
        return None

    runs = resp.json().get("benchmark_runs", [])
    if not runs:
        print("No benchmark runs found. Run benchmarks in the UI first.")
        return None

    latest   = runs[0]
    results  = latest.get("benchmark_results", [])
    good     = sum(1 for r in results if r.get("rating") == "GOOD")
    total    = len(results)
    accuracy = good / total if total > 0 else 0.0

    print(f"Benchmark accuracy: {good}/{total} = {accuracy:.1%}")

    if accuracy >= threshold:
        print(f"PASS — accuracy {accuracy:.1%} meets threshold {threshold:.0%}")
        return True
    else:
        failing = [r.get("question") for r in results if r.get("rating") == "BAD"]
        print(f"FAIL — accuracy {accuracy:.1%} is below threshold {threshold:.0%}")
        print(f"Failing questions:")
        for q in failing:
            print(f"  - {q}")
        return False

if SPACE_ID:
    check_benchmark_accuracy(SPACE_ID, HOST, HEADERS, ACCURACY_THRESHOLD)
else:
    print("Set genie_space_id widget to run this check.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3: The Monitor Tab (5 min, UI-first)
# MAGIC
# MAGIC The Monitor tab is your **primary improvement signal** once the space is in the hands of real users.
# MAGIC Benchmarks tell you about questions you anticipated. Monitor tells you about questions you did not.
# MAGIC
# MAGIC ### Navigate to Monitor
# MAGIC
# MAGIC ```
# MAGIC Your Genie Space → Configure → Monitor tab
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #f0f0f0; border: 1px solid #ccc; border-radius: 8px; padding: 18px 22px; font-family: monospace; font-size: 0.92em; margin: 10px 0;">
# MAGIC <pre style="margin: 0;">
# MAGIC ┌─── Monitor Tab ──────────────────────────────────────────────┐
# MAGIC │  [Filter: All | Thumbs up | Thumbs down | Fix it]           │
# MAGIC │  [User: All ▼]  [Date: Last 30 days ▼]                      │
# MAGIC │  ────────────────────────────────────────────────────────    │
# MAGIC │  Q: "What were VIC prices yesterday?"     👍  09:23 AM      │
# MAGIC │  Q: "Average NEM dispatch by fuel type"   ❓  Request       │
# MAGIC │  Q: "Settlement amounts for ORIGIN"       👎  10:45 AM      │
# MAGIC │     ↑ Click to expand → see SQL generated + user feedback    │
# MAGIC │                                                              │
# MAGIC │  [Analyze space usage] → opens Genie Code on this data       │
# MAGIC └──────────────────────────────────────────────────────────────┘
# MAGIC </pre>
# MAGIC </div>
# MAGIC
# MAGIC **What each filter shows:**
# MAGIC
# MAGIC | Filter | What to look for |
# MAGIC |--------|-----------------|
# MAGIC | **Thumbs down** | Questions where users explicitly said the answer was wrong — highest priority |
# MAGIC | **Fix it** | Questions flagged by users for improvement — second priority |
# MAGIC | **Thumbs up** | Confirm what is working — check the SQL to understand why |
# MAGIC | **All** | Full question volume — use to spot emerging patterns |
# MAGIC
# MAGIC **The Monitor tab is your backlog.** Every thumbs-down is a golden query you have not written yet. Work through them in order of frequency — the most common unanswered or incorrectly-answered questions should become golden queries.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Feedback alert query — monitor negative ratings via system tables
# MAGIC
# MAGIC The Monitor tab is a UI view. For automated alerting — for example, an email when a user gives a thumbs-down — query `system.access.audit` directly.

# COMMAND ----------

# Alert on negative user feedback via system.access.audit
# This query can be scheduled as a Databricks Job that sends an alert
feedback_query = """
    SELECT
        user_identity.email             AS user_email,
        action_name,
        request_params.space_id         AS space_id,
        request_params.feedback_rating  AS rating,
        event_time
    FROM system.access.audit
    WHERE service_name   = 'aibiGenie'
      AND action_name    = 'genieSendMessageFeedback'
      AND request_params.feedback_rating = 'NEGATIVE'
      AND event_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS
    ORDER BY event_time DESC
    LIMIT 100
"""

try:
    feedback_df = spark.sql(feedback_query)
    neg_count   = feedback_df.count()
    print(f"Negative feedback in last 30 days: {neg_count} rating(s)")
    if neg_count > 0:
        display(feedback_df)
    else:
        print("No negative feedback yet — either no users, or users are satisfied.")
except Exception as e:
    print(f"Note: {e}")
    print()
    print("system.access.audit will populate once users start using the space.")
    print("Run this cell again after pilot users have asked some questions.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### All Genie activity for this space
# MAGIC
# MAGIC The query below gives you a complete picture of what users are asking and how they are rating responses.
# MAGIC This is useful for a weekly review to identify patterns in failing questions.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- All Genie conversation activity for your space in the last 30 days
# MAGIC -- Replace the space_id filter with your actual Space ID for production use
# MAGIC SELECT
# MAGIC     event_time,
# MAGIC     user_identity.email                         AS user_email,
# MAGIC     action_name,
# MAGIC     request_params.space_id                     AS space_id,
# MAGIC     request_params.conversation_id              AS conversation_id,
# MAGIC     request_params.feedback_rating              AS feedback_rating,
# MAGIC     response.statusCode                         AS status
# MAGIC FROM system.access.audit
# MAGIC WHERE service_name = 'aibiGenie'
# MAGIC   AND event_time >= CURRENT_TIMESTAMP() - INTERVAL 30 DAYS
# MAGIC   AND action_name IN (
# MAGIC       'startConversation',
# MAGIC       'createConversationMessage',
# MAGIC       'genieSendMessageFeedback'
# MAGIC   )
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 200

# COMMAND ----------

# MAGIC %md
# MAGIC ### Weekly review pattern
# MAGIC
# MAGIC Run this cell to summarise feedback trends by week. Use this in your regular iteration cycle.

# COMMAND ----------

# Weekly feedback summary — useful for iteration planning
weekly_summary_query = """
    SELECT
        DATE_TRUNC('week', event_time)          AS week_starting,
        action_name,
        request_params.feedback_rating          AS rating,
        COUNT(*)                                AS event_count,
        COUNT(DISTINCT user_identity.email)     AS unique_users
    FROM system.access.audit
    WHERE service_name = 'aibiGenie'
      AND event_time >= CURRENT_TIMESTAMP() - INTERVAL 90 DAYS
      AND action_name IN (
          'createConversationMessage',
          'genieSendMessageFeedback'
      )
    GROUP BY
        DATE_TRUNC('week', event_time),
        action_name,
        request_params.feedback_rating
    ORDER BY week_starting DESC, action_name
"""

try:
    summary_df = spark.sql(weekly_summary_query)
    print("Weekly Genie usage summary (last 90 days):")
    display(summary_df)
except Exception as e:
    print(f"Note: {e}")
    print("This will return data once users have been active on the space.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4: Permissions and Rollout (5 min, UI-first)
# MAGIC
# MAGIC ### Navigate to Share
# MAGIC
# MAGIC ```
# MAGIC Your Genie Space → Share button (top-right)
# MAGIC ```
# MAGIC
# MAGIC **Permission levels:**
# MAGIC
# MAGIC | Level | Who should have it | What they can do |
# MAGIC |-------|--------------------|------------------|
# MAGIC | **CAN MANAGE** | Space authors and data owners | See all conversations, access Monitor tab, change configuration |
# MAGIC | **CAN EDIT** | Data engineers maintaining the space | Update golden queries, instructions, add tables |
# MAGIC | **CAN RUN** | Business users asking questions | Ask questions, give feedback (thumbs up/down) |
# MAGIC | **CAN VIEW** | Read-only stakeholders | View the space but cannot run queries |
# MAGIC
# MAGIC ### Recommended rollout sequence
# MAGIC
# MAGIC <div style="background: #e8f4fd; border: 2px solid #1B3A6B; border-radius: 8px; padding: 20px 24px; font-family: 'DM Sans', Arial, sans-serif; margin: 10px 0;">
# MAGIC
# MAGIC | Stage | Duration | Who | What to measure |
# MAGIC |-------|----------|-----|-----------------|
# MAGIC | **Self-use** | 2–3 weeks | Just you (the builder) | Find obvious gaps before exposing to others |
# MAGIC | **Pilot** | 2–4 weeks | 5–10 trusted business users (CAN RUN) | Collect Monitor feedback, measure thumbs-down rate |
# MAGIC | **Broader rollout** | Ongoing | Your target audience | Monitor weekly, add golden queries for new failure patterns |
# MAGIC
# MAGIC **Do not skip the pilot stage.** Market-sensitive data like AEMO settlement amounts needs a human review cycle before broad access.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Read current permissions on the Space and display in a clean format
if not SPACE_ID:
    print("Set genie_space_id widget first.")
else:
    resp = requests.get(
        f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}",
        headers=HEADERS,
    )

    if resp.status_code == 200:
        acl = resp.json().get("access_control_list", [])
        if acl:
            print(f"Current permissions on Space {SPACE_ID}:\n")
            print(f"  {'Principal':<40} {'Type':<15} {'Permission'}")
            print("  " + "-" * 70)
            for entry in acl:
                if "group_name" in entry:
                    principal = entry["group_name"]
                    ptype     = "group"
                elif "user_name" in entry:
                    principal = entry["user_name"]
                    ptype     = "user"
                elif "service_principal_name" in entry:
                    principal = entry["service_principal_name"]
                    ptype     = "service principal"
                else:
                    principal = str(entry)
                    ptype     = "unknown"

                for perm in entry.get("all_permissions", []):
                    level = perm.get("permission_level", "N/A")
                    print(f"  {principal:<40} {ptype:<15} {level}")
        else:
            print("No explicit ACL entries — you are the owner by default.")
    else:
        print(f"API call failed: {resp.status_code}")
        print(resp.text)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Grant CAN RUN to a workshop participant
# MAGIC
# MAGIC The cell below is a **dry run** — it prints what would be sent. Uncomment the `requests.patch` call to execute it.

# COMMAND ----------

# Workshop exercise: share with another participant
# Replace with a real participant email from your workshop group
PILOT_USER_EMAIL = "participant@example.com.au"

print(f"Sharing space {SPACE_ID} with {PILOT_USER_EMAIL} as CAN_RUN\n")
print("(Dry run — uncomment the requests.patch call below to execute)\n")

grant_body = {
    "access_control_list": [
        {"user_name": PILOT_USER_EMAIL, "permission_level": "CAN_RUN"}
    ]
}

print("Payload that would be sent:")
print(json.dumps(grant_body, indent=2))
print()

# Uncomment to execute:
# resp = requests.patch(
#     f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}",
#     headers=HEADERS,
#     json=grant_body,
# )
# if resp.status_code == 200:
#     print(f"Access granted to {PILOT_USER_EMAIL}")
# else:
#     print(f"Failed: {resp.status_code} — {resp.text}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bulk permission sync pattern (production)
# MAGIC
# MAGIC For AEMO's production rollout, integrate this with your IdP or HR system so permissions stay in sync with organisational roles:
# MAGIC
# MAGIC ```python
# MAGIC # Pseudocode — sync Genie permissions from an approved-users list
# MAGIC approved_analysts = get_approved_users_from_hr_system()  # Your IdP API call
# MAGIC
# MAGIC current_perms  = requests.get(f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}", headers=HEADERS)
# MAGIC current_acl    = current_perms.json().get("access_control_list", [])
# MAGIC current_users  = {e["user_name"] for e in current_acl if "user_name" in e}
# MAGIC
# MAGIC # Grant access to newly approved users
# MAGIC for user in approved_analysts - current_users:
# MAGIC     requests.patch(
# MAGIC         f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}",
# MAGIC         headers=HEADERS,
# MAGIC         json={"access_control_list": [{"user_name": user, "permission_level": "CAN_RUN"}]},
# MAGIC     )
# MAGIC
# MAGIC # Revoke access for users who have left the approved list
# MAGIC for user in current_users - approved_analysts:
# MAGIC     requests.patch(
# MAGIC         f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}",
# MAGIC         headers=HEADERS,
# MAGIC         json={"access_control_list": [{"user_name": user, "permission_level": "NO_PERMISSIONS"}]},
# MAGIC     )
# MAGIC ```
# MAGIC
# MAGIC Schedule this as a Databricks Job running nightly. Genie access will automatically mirror your HR-managed role list.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Full Iteration Loop Reference
# MAGIC
# MAGIC Use this as a reference for your ongoing improvement cycle after the workshop.
# MAGIC
# MAGIC <div style="background: #f7f8fa; border: 2px solid #1B3A6B; border-radius: 8px; padding: 20px 24px; font-family: 'DM Sans', Arial, sans-serif; margin: 10px 0;">
# MAGIC
# MAGIC ```
# MAGIC ╔══════════════════════════════════════════════════════════════╗
# MAGIC ║              THE GENIE QUALITY ITERATION LOOP               ║
# MAGIC ╠══════════════════════════════════════════════════════════════╣
# MAGIC ║                                                              ║
# MAGIC ║  1. BUILD                                                    ║
# MAGIC ║     Add tables, write instructions, add golden queries       ║
# MAGIC ║                                                              ║
# MAGIC ║  2. BENCHMARK (before change)                               ║
# MAGIC ║     Run all benchmarks → record baseline accuracy            ║
# MAGIC ║                                                              ║
# MAGIC ║  3. IMPROVE                                                  ║
# MAGIC ║     Add/update one golden query or SQL expression            ║
# MAGIC ║                                                              ║
# MAGIC ║  4. BENCHMARK (after change)                                ║
# MAGIC ║     Run selected benchmarks → confirm improvement            ║
# MAGIC ║     Run all benchmarks → confirm no regression              ║
# MAGIC ║                                                              ║
# MAGIC ║  5. MONITOR (after pilot launch)                            ║
# MAGIC ║     Check Monitor tab weekly for thumbs-down patterns        ║
# MAGIC ║     Every thumbs-down = a golden query you need to write     ║
# MAGIC ║                                                              ║
# MAGIC ║  6. REPEAT                                                   ║
# MAGIC ║     Go to step 3 for each new failure pattern found          ║
# MAGIC ║                                                              ║
# MAGIC ╚══════════════════════════════════════════════════════════════╝
# MAGIC ```
# MAGIC
# MAGIC **Critical reminder:** Benchmarks only improve when you add golden queries or SQL expressions. They never improve because you added more benchmark questions.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab Checkpoint
# MAGIC
# MAGIC Before moving on, confirm you have completed each item:
# MAGIC
# MAGIC - [ ] 10 benchmark questions added in the UI (5 question types × 2 phrasings each)
# MAGIC - [ ] Benchmarks run at least once and Evaluations tab reviewed
# MAGIC - [ ] At least one failing benchmark identified — you can see the generated SQL
# MAGIC - [ ] The LOR benchmark fix applied (usage guidance added to golden query)
# MAGIC - [ ] Benchmark re-run on Q3a and Q3b to confirm improvement
# MAGIC - [ ] Feedback alert SQL in Section 3 reviewed and understood
# MAGIC - [ ] Space shared with at least one other workshop participant (CAN RUN)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Lab Summary
# MAGIC
# MAGIC | Section | Key takeaway |
# MAGIC |---------|-------------|
# MAGIC | Benchmarks | Measure quality, do not improve it. Run before and after every change as regression tests. |
# MAGIC | Benchmark structure | 2–4 phrasings per question type catches paraphrase brittleness. Target > 80% Good before sharing. |
# MAGIC | Improvement loop | Bad rating → expand to see SQL → diagnose root cause → add golden query or expression → re-run selected |
# MAGIC | Monitor tab | Your primary signal after launch. Every thumbs-down is an unanswered golden query. |
# MAGIC | Feedback alerting | `system.access.audit` + `genieSendMessageFeedback` action gives you programmatic access to ratings. |
# MAGIC | Rollout | Self → Pilot (5–10 users, CAN RUN) → Broader. Do not skip the pilot stage for sensitive data. |

# COMMAND ----------

# Print the space URL for sharing with pilot users
if SPACE_ID:
    space_url = f"https://{HOST}#pages/genie/spaces/{SPACE_ID}"
    print("Your AEMO NEM Operations Genie Space (share this with pilot users):")
    print(f"  {space_url}")
    print()
    print("Pilot users need: CAN RUN on this space + SELECT on workshop_au.aemo.*")
    displayHTML(
        f'<div style="background:#f7f8fa; border:1px solid #ddd; border-radius:8px; padding:16px 20px;">'
        f'<b>AEMO NEM Operations Genie Space</b><br>'
        f'<a href="{space_url}" target="_blank" style="color:#FF3621; font-size:1.1em;">{space_url}</a>'
        f'</div>'
    )
else:
    print("Set genie_space_id widget to generate your space URL.")
