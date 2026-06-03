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
# MAGIC | **Prerequisites** | Lab 02 complete — benchmarks uploaded and baseline score noted |
# MAGIC | **Covers** | Slides 17–20 — Learning, User Feedback, Rollout, Alerts |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The iteration loop
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
# MAGIC 🖱️ Navigate: **Benchmark** tab (top-level) → **Run benchmarks**
# MAGIC
# MAGIC Watch the Evaluations tab:
# MAGIC ```
# MAGIC Green  = GOOD        (SQL matched or result set matched)
# MAGIC Red    = BAD         (wrong answer, empty result, or query error)
# MAGIC Orange = NEEDS_REVIEW (automated comparison inconclusive — requires manual check)
# MAGIC
# MAGIC Target before sharing with business users: > 80% Good
# MAGIC ```

# COMMAND ----------

import requests, json

if SPACE_ID:
    # Step A: list eval runs (the API term for "benchmark runs")
    runs_resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/eval-runs",
        headers=HEADERS
    )
    if runs_resp.status_code != 200:
        print(f"Error listing eval runs: {runs_resp.status_code}")
        print(runs_resp.text[:200])
    else:
        runs = runs_resp.json().get("eval_runs", [])
        if not runs:
            print("No benchmark runs yet — run benchmarks in the UI first (Benchmark tab (top-level) → Run benchmarks).")
        else:
            latest_run_id = runs[0].get("eval_run_id")
            run_status    = runs[0].get("eval_run_status")
            print(f"Latest eval run: {latest_run_id}  status: {run_status}")

            if run_status != "DONE":
                print("Run is still in progress — wait for it to complete, then re-run this cell.")
            else:
                # Step B: list results for the latest run
                results_resp = requests.get(
                    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/eval-runs/{latest_run_id}/results",
                    headers=HEADERS
                )
                if results_resp.status_code != 200:
                    print(f"Error listing results: {results_resp.status_code}")
                    print(results_resp.text[:200])
                else:
                    result_items = results_resp.json().get("eval_results", [])
                    # Step C: fetch assessment (GOOD/BAD/NEEDS_REVIEW) for each result
                    good = bad = needs_review = 0
                    bad_questions = []
                    for item in result_items:
                        rid = item.get("result_id")
                        detail_resp = requests.get(
                            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/eval-runs/{latest_run_id}/results/{rid}",
                            headers=HEADERS
                        )
                        if detail_resp.status_code == 200:
                            assessment = detail_resp.json().get("assessment", "NEEDS_REVIEW")
                        else:
                            assessment = "NEEDS_REVIEW"
                        if assessment == "GOOD":
                            good += 1
                        elif assessment == "BAD":
                            bad += 1
                            bad_questions.append(item.get("question", "unknown"))
                        else:
                            needs_review += 1

                    total = len(result_items)
                    pct   = int(good / total * 100) if total else 0
                    print(f"\nLatest run — {pct}% Good ({good}/{total})")
                    print(f"  ✅ Good:         {good}")
                    print(f"  ❌ Bad:          {bad}")
                    print(f"  ⚠️  Needs review: {needs_review}")
                    if bad_questions:
                        print(f"\nBad questions to investigate:")
                        for q in bad_questions:
                            print(f"  → {q[:80]}")
else:
    print("Enter Space ID in widget.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Diagnose and Fix Failures
# MAGIC
# MAGIC For each "Bad" or "Needs Review" benchmark — click to expand and read the generated SQL.
# MAGIC The Benchmark tab shows three assessment codes. Each has a specific fix path.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Assessment code reference
# MAGIC
# MAGIC #### 🔴 `EMPTY_RESULT`
# MAGIC Genie's SQL executed successfully but returned 0 rows.
# MAGIC
# MAGIC **Most common cause in this workshop:** the benchmark expected SQL uses `CURRENT_DATE - 1`,
# MAGIC `CURRENT_DATE - INTERVAL 7 DAYS`, or `DATE_TRUNC('month', CURRENT_DATE)` — but the synthetic
# MAGIC training data ends at **2025-12-31**. Any date filter referencing today (2026) returns zero rows,
# MAGIC so the LLM judge marks it BAD because it cannot compare result sets.
# MAGIC
# MAGIC **Fix:** Update the benchmark's expected SQL to use a hardcoded date within the data range:
# MAGIC
# MAGIC | Original filter | Replace with |
# MAGIC |---|---|
# MAGIC | `DATE(settlement_date) = CURRENT_DATE - 1` | `DATE(settlement_date) = '2025-12-31'` |
# MAGIC | `settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS` | `settlement_date >= '2025-12-25'` |
# MAGIC | `settlement_date >= DATE_TRUNC('month', CURRENT_DATE)` | `settlement_date >= '2025-12-01'` |
# MAGIC | `issue_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS` | `issue_time >= '2025-12-01'` |
# MAGIC
# MAGIC In production (with live data), these filters are correct — update them back before go-live.
# MAGIC
# MAGIC 🖱️ **UI:** Benchmark tab → click the failing benchmark → Edit → update the Expected SQL → Save
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### 🟡 `LLM_JUDGE_MISSING_OR_INCORRECT_FILTER`
# MAGIC Genie's SQL ran and returned data, but the LLM judge detected a missing or wrong filter
# MAGIC compared to what the benchmark expected.
# MAGIC
# MAGIC **Common causes and fixes:**
# MAGIC
# MAGIC | What you see in Genie's SQL | Cause | Fix |
# MAGIC |---|---|---|
# MAGIC | Genie added extra columns (`interval_count`, `max_price`, `min_settlement_date`) | Genie being "helpful" — not wrong, just unexpected | Either accept it (update benchmark expected SQL to allow extra cols) or add a golden query that returns exactly the columns you want |
# MAGIC | Date filter is missing or broadened (shows all dates instead of last 7 days) | Date column description doesn't make the range requirement clear | Strengthen the `settlement_date` column description, or add a golden query with an explicit date parameter |
# MAGIC | Region filter dropped (`WHERE region_id = 'QLD1'` missing) | Ambiguous question phrasing | Rephrase the benchmark question to be more explicit, e.g. "in QLD1" not "in QLD" |
# MAGIC | `ROUND(SUM(dispatch_mw)/12, 1)` changed to `SUM(dispatch_mw)/12` | Column description doesn't specify rounding | Add rounding to the column description for `dispatch_mw` |
# MAGIC
# MAGIC **Quick check:** open the benchmark detail, compare Genie's SQL to the expected SQL side by side.
# MAGIC If the logic is correct and only column names differ → update the benchmark.
# MAGIC If the logic is wrong → add a golden query to override Genie's generation for this pattern.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### 🔴 `RESULT_MISSING_COLUMNS`
# MAGIC Genie's result has different columns from what the benchmark expected.
# MAGIC
# MAGIC **Common causes and fixes:**
# MAGIC
# MAGIC | What you see | Cause | Fix |
# MAGIC |---|---|---|
# MAGIC | `avg_spot_price` instead of `avg_price_mwh` | Genie chose a different alias | Add `avg_price_mwh` as a synonym for `rrp` so Genie learns the preferred naming convention |
# MAGIC | Genie returned `date, num_intervals, avg_spot_price` instead of `region_id, avg_price_mwh` | No data for the expected date range → Genie rewrote the query to show available dates | First fix the `EMPTY_RESULT` root cause (update benchmark dates), then re-run |
# MAGIC | Extra columns added | Genie is being helpful | Add a golden query with the exact column list you want |
# MAGIC
# MAGIC **Rule of thumb:** `RESULT_MISSING_COLUMNS` on its own → fix with a golden query.
# MAGIC `RESULT_MISSING_COLUMNS` + `LLM_JUDGE_MISSING_OR_INCORRECT_FILTER` together → start by fixing the date/filter issue first, then see if columns self-correct.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### AEMO-specific symptom → fix table
# MAGIC
# MAGIC | Symptom in generated SQL | Likely cause | Fix |
# MAGIC |---|---|---|
# MAGIC | `region_id = 'NSW'` instead of `'NSW1'` | Entity matching not enabled | Configure → Data → spot_prices → region_id → Format assistance → enable |
# MAGIC | `notice_type = 'LOR'` instead of `LIKE 'LOR%'` | No entity matching for notice_type | Enable entity matching for notice_type; the LOR golden query already uses `LIKE 'LOR%'` |
# MAGIC | No join to `generator_registration` | Join not configured | Configure → Instructions → Joins — verify the join is listed |
# MAGIC | `rrp` called `spot_price` or `price` | Synonym for rrp not set | Configure → Data → spot_prices → rrp → Synonyms → add "price", "spot price" |
# MAGIC | Date filter missing entirely | No data for queried range, Genie adapted | Update benchmark to use historical date (see EMPTY_RESULT fix above) |
# MAGIC | Genie says "no data available for yesterday" | Data ends 2025-12-31 | Update benchmark expected SQL to use `'2025-12-31'` |
# MAGIC | `SUM(dispatch_mw)/12` not divided | `dispatch_mw` description doesn't mention MWh conversion | Column description for `dispatch_mw` already says "divide by 12 for MWh" — check it's saved |
# MAGIC | Renewable defined as solar+wind+hydro+battery | Genie included hydro/battery in "renewable" | Add a text instruction: "Renewable generation = solar and wind only. Hydro and battery are separate categories." |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **After fixing → re-run just the failing benchmark:**
# MAGIC ```
# MAGIC Benchmark tab → click the failing question → Run selected
# MAGIC ```
# MAGIC Do not re-run all benchmarks after every change — it's slow and wastes quota.
# MAGIC Re-run the full set only when you want to measure overall progress.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: The Monitor Tab — real user feedback (Slide 13)
# MAGIC
# MAGIC > *"User feedback continuously improves Genie's quality by capturing real-world user input and routing it to authors for action."*
# MAGIC
# MAGIC **🖱️ Navigate: Monitor tab (top-level tab, not under Configure)**
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
# MAGIC
# MAGIC **🖱️ UI:** SQL Editor → paste the query below → Save → Alerts → + Create alert → select query → set threshold: negative_count > 0 → Notify: your email
# MAGIC
# MAGIC **⚡ Automated:** run the cell below to query the audit table directly and see negative feedback now.

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
      AND action_name  = 'updateConversationMessageFeedback'
      AND event_time   >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    ORDER BY event_time DESC
"""

try:
    feedback = spark.sql(feedback_sql)
    total    = feedback.count()
    # Actual audit table values are THUMBS_DOWN / THUMBS_UP (not NEGATIVE / POSITIVE)
    negative = feedback.filter("rating = 'THUMBS_DOWN'").count()
    print(f"Last 30 days: {total} feedback events, {negative} negative (THUMBS_DOWN)")
    if negative:
        print("\nNegative feedback — investigate these in the Monitor tab:")
        display(feedback.filter("rating = 'THUMBS_DOWN'").limit(10))
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
        f"https://{HOST}/api/2.0/permissions/genie/{SPACE_ID}",
        headers=HEADERS
    )
    if resp.status_code == 200:
        acl = resp.json().get("access_control_list", [])
        print("Current space permissions:")
        for entry in acl:
            p = entry.get("user_name") or entry.get("group_name") or "unknown"
            # permission_level is nested under all_permissions[0]
            perms = entry.get("all_permissions", [])
            level = perms[0].get("permission_level", "unknown") if perms else "unknown"
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
# MAGIC **→ Next: Lab 04 — Monitoring Usage, Cost & Feedback**

