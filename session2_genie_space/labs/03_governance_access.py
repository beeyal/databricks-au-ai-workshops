# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 03: Benchmark, Monitor & Rollout</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 30 minutes |
# MAGIC | **Covers** | Slides 13, 16, 31–32 — Feedback, Benchmarks, Rollout, Alerts |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The iteration loop (Slide 25)
# MAGIC
# MAGIC ```
# MAGIC Baseline benchmarks (Lab 02) ──►
# MAGIC     Ask in Genie ──► fails or gives wrong answer
# MAGIC         ──► Identify why (wrong column? wrong join? missing context?)
# MAGIC         ──► Fix: add golden query / entity match / synonym
# MAGIC     Re-run benchmarks ──► compare to baseline
# MAGIC         ──► improvement? → move to next failure
# MAGIC         ──► no improvement? → check your fix was in the right place
# MAGIC ```

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID")
SPACE_ID = dbutils.widgets.get("genie_space_id")
CATALOG  = "workshop_au"
SCHEMA   = "aemo"
HOST     = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN    = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS  = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Run Benchmarks and Read Results (Slide 16)
# MAGIC
# MAGIC > *"Benchmarks detect drift or inconsistencies over time. They surface regressions or bugs early and before org-wide adoption."*
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Benchmarks → Run benchmarks**
# MAGIC
# MAGIC Watch the Evaluations tab:
# MAGIC ```
# MAGIC Green = Good (SQL matched or result set matched)
# MAGIC Red   = Bad  (wrong answer, empty result, or query error)
# MAGIC Orange = Manual review (automated comparison inconclusive)
# MAGIC
# MAGIC Target before sharing with business users: > 80% Good
# MAGIC ```

# COMMAND ----------

import requests, json

if SPACE_ID:
    resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-runs",
        headers=HEADERS
    )
    if resp.status_code == 200:
        runs = resp.json().get("benchmark_runs", [])
        if runs:
            latest = runs[0]
            results = latest.get("benchmark_results", [])
            good    = sum(1 for r in results if r.get("rating") == "GOOD")
            bad     = sum(1 for r in results if r.get("rating") == "BAD")
            manual  = sum(1 for r in results if r.get("rating") == "MANUAL")
            total   = len(results)
            pct     = int(good / total * 100) if total else 0
            print(f"Latest run — {pct}% Good ({good}/{total})")
            print(f"  ✅ Good:   {good}")
            print(f"  ❌ Bad:    {bad}")
            print(f"  ⚠️  Manual: {manual}")
            if bad:
                print(f"\nBad questions to investigate:")
                for r in results:
                    if r.get("rating") == "BAD":
                        print(f"  → {r.get('question', 'unknown')[:80]}")
        else:
            print("No benchmark runs yet — run benchmarks in the UI first.")
    else:
        print(f"Error {resp.status_code}")
else:
    print("Enter Space ID in widget.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Diagnose and Fix Failures
# MAGIC
# MAGIC For each "Bad" benchmark — click to expand and read the generated SQL.
# MAGIC
# MAGIC **AEMO-specific debugging (Slide 36 — Iteration rule):**
# MAGIC
# MAGIC | Symptom | Likely cause | Fix |
# MAGIC |---|---|---|
# MAGIC | Used `region_id = 'NSW'` instead of `'NSW1'` | Entity matching not enabled | Enable entity matching for region_id |
# MAGIC | Used `notice_type = 'LOR'` instead of `LIKE 'LOR%'` | No entity matching for notice_type | Enable entity matching for notice_type; add usage guidance to LOR golden query |
# MAGIC | Didn't join to generator_registration | Join relationship not configured | Add join in Configure → Instructions → Joins |
# MAGIC | Wrong column name for price | Synonym not set | Add 'price', 'spot price' as synonyms for rrp |
# MAGIC | Wrong date filter | No guidance on date column | Add column description for settlement_date |
# MAGIC
# MAGIC **After fixing → re-run the specific failing benchmark:**
# MAGIC ```
# MAGIC Configure → Benchmarks → select failing question → Run selected
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: The Monitor Tab — real user feedback (Slide 13)
# MAGIC
# MAGIC > *"User feedback continuously improves Genie's quality by capturing real-world user input and routing it to authors for action."*
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Monitor**
# MAGIC
# MAGIC ```
# MAGIC Filter by:  [All] [👍 Thumbs up] [👎 Thumbs down] [🔧 Fix it] [📋 Request review]
# MAGIC
# MAGIC Click any question → expand → read the SQL Genie generated
# MAGIC   → if wrong: identify the issue → fix with golden query or entity match → re-run benchmark
# MAGIC
# MAGIC [Analyze space usage] → opens Genie Code to analyse Monitor data for patterns
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Alert on user feedback (Slide 32)
# MAGIC
# MAGIC > *"The audit system table reflects all events within ~15 minutes. Query it and use in an alert."*

# COMMAND ----------

# Feedback alert query — from Slide 32
feedback_sql = """
    SELECT
        user_identity.email         AS user_email,
        action_name,
        request_params.space_id     AS space_id,
        request_params.feedback_rating AS rating,
        event_time
    FROM system.access.audit
    WHERE service_name = 'aibiGenie'
      AND action_name  = 'genieSendMessageFeedback'
      AND event_time   >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    ORDER BY event_time DESC
"""

try:
    feedback = spark.sql(feedback_sql)
    total    = feedback.count()
    negative = feedback.filter("rating = 'NEGATIVE'").count()
    print(f"Last 30 days: {total} feedback events, {negative} negative")
    if negative:
        print("\nNegative feedback — investigate these in the Monitor tab:")
        display(feedback.filter("rating = 'NEGATIVE'").limit(10))
except Exception as e:
    print(f"Note: {e}")
    print("system.access.audit populates once users start using the space.")

print("""
To set up an alert:
  SQL Editor → new query → paste the SQL above → Run
  → Save query → Alerts → + Create alert → select query → threshold: negative_count > 0
  → Notify: your email
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Permissions & Rollout (Slide 31)
# MAGIC
# MAGIC > *"Once you feel your space is ready, use it yourself for a few weeks to answer questions that come in. Adjust instructions as needed. Then identify 5–10 initial test users."*
# MAGIC
# MAGIC **Three-phase rollout:**
# MAGIC
# MAGIC | Phase | Who | What to do |
# MAGIC |---|---|---|
# MAGIC | 1 — Self (weeks 1-2) | You + data team | Answer real questions using the space. Fix failures. Target >80% benchmark score. |
# MAGIC | 2 — Pilot (weeks 3-4) | 5-10 business users | Update description + starter questions. Configure feedback alert. Share with CAN RUN. Review Monitor weekly. |
# MAGIC | 3 — Broad rollout | Wider team | Share with more groups. Assign a named Monitor reviewer. Quarterly benchmark re-run. |
# MAGIC
# MAGIC **🖱️ Share the space: top-right → Share button**
# MAGIC
# MAGIC | Permission | What they can do |
# MAGIC |---|---|
# MAGIC | CAN MANAGE | Full control, sees all conversations and Monitor tab |
# MAGIC | CAN EDIT | Modify instructions and queries |
# MAGIC | CAN RUN | Ask questions and give feedback |

# COMMAND ----------

# Verify permissions via API
if SPACE_ID:
    resp = requests.get(
        f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}",
        headers=HEADERS
    )
    if resp.status_code == 200:
        acl = resp.json().get("access_control_list", [])
        print("Current space permissions:")
        for entry in acl:
            p = entry.get("user_name") or entry.get("group_name") or "unknown"
            level = entry.get("permission_level", "unknown")
            print(f"  {level}: {p}")
    else:
        print(f"Error {resp.status_code}: {resp.text[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 03 Checkpoint
# MAGIC
# MAGIC - [ ] Benchmarks run and Evaluations tab reviewed
# MAGIC - [ ] At least 1 failing benchmark identified, diagnosed, and fixed
# MAGIC - [ ] Benchmark re-run confirms improvement
# MAGIC - [ ] Feedback alert SQL understood
# MAGIC - [ ] Space shared with at least 1 other participant (CAN RUN)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🎯 Session 2 Complete
# MAGIC
# MAGIC You've built a quality Genie Space following the official best practices:
# MAGIC 1. ✅ UC metadata first — descriptions, synonyms, entity matching, join config
# MAGIC 2. ✅ Benchmarks created before iterating
# MAGIC 3. ✅ Golden queries with parameterisation and accurate titles
# MAGIC 4. ✅ Text instructions used sparingly (4 rules only)
# MAGIC 5. ✅ Feedback alerting configured
# MAGIC 6. ✅ Rollout plan understood
# MAGIC
# MAGIC **Next steps for AEMO:**
# MAGIC - Use the space yourself for 2 weeks answering real market operations questions
# MAGIC - Add golden queries for every question type that fails
# MAGIC - When benchmark score > 80% — identify your 5-10 pilot business users

