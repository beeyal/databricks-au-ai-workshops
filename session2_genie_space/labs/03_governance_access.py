# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 03: Benchmark, Monitor & Rollout</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 35 minutes |
# MAGIC | **Prerequisites** | Lab 02 complete — benchmarks uploaded and baseline score noted |
# MAGIC | **Covers** | Slides 13, 16, 31–32 — Feedback, Benchmarks, Rollout, Alerts |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The iteration loop
# MAGIC
# MAGIC ```
# MAGIC Baseline benchmarks (Lab 02) ──►
# MAGIC     Run all benchmarks ──► note score and BAD questions
# MAGIC         ──► click a BAD result ──► read the generated SQL
# MAGIC         ──► Identify why (wrong value? wrong column? missing join?)
# MAGIC         ──► Fix: entity match / golden query / instruction / synonym
# MAGIC     Re-run selected benchmark ──► confirm it improved
# MAGIC         ──► improvement? → move to next failure
# MAGIC         ──► no improvement? → check your fix was saved to the right place
# MAGIC ```
# MAGIC
# MAGIC This lab puts you through that loop with a **deliberate flaw** already planted in the space —
# MAGIC you will find it, diagnose it, fix it, and confirm the improvement before moving on.

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
# MAGIC ## Step 0: Find and Fix the Deliberate Flaw
# MAGIC
# MAGIC > This space was set up with one known misconfiguration. Your job is to find it using benchmarks,
# MAGIC > diagnose the root cause, apply the fix, and re-run to confirm improvement.
# MAGIC > This is the human-in-the-loop benchmark iteration workflow you will use every week in production.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 0a — Run all benchmarks and record the baseline score
# MAGIC
# MAGIC **🖱️ UI:** **Benchmark** tab (top-level) → **Run benchmarks** → wait for Evaluations tab to populate
# MAGIC
# MAGIC Note the overall % Good score here before you change anything: `_____% Good`
# MAGIC
# MAGIC That number is your baseline. Every fix you make should move it upward.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 0b — Identify the BAD result
# MAGIC
# MAGIC > **Facilitator note:** The shared workshop space has entity matching for `region_id` disabled before
# MAGIC > this lab starts — that is the planted flaw. If you are working in **your own space** (not the shared
# MAGIC > workshop space), you will not see this flaw because you never disabled it. In that case, skip
# MAGIC > steps 0b–0e and go directly to Step 1 — your space is already clean for this column.
# MAGIC
# MAGIC **🖱️ UI:** Evaluations tab → filter by **Red (BAD)** → click on a failing benchmark to expand it
# MAGIC
# MAGIC Look at the two SQL panes side by side:
# MAGIC
# MAGIC | Pane | What it shows |
# MAGIC |---|---|
# MAGIC | **Expected SQL** | The SQL you told Genie was correct when you uploaded the benchmark |
# MAGIC | **Generated SQL** | What Genie actually produced when asked this question today |
# MAGIC
# MAGIC Look for the region filter. You will see something like:
# MAGIC ```sql
# MAGIC -- Expected SQL
# MAGIC WHERE region_id = 'NSW1'
# MAGIC
# MAGIC -- Genie's generated SQL
# MAGIC WHERE region_id = 'NSW'
# MAGIC ```
# MAGIC
# MAGIC Genie is producing `'NSW'` instead of the correct NEM region code `'NSW1'`.
# MAGIC This is the deliberate flaw.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 0c — Diagnose the cause
# MAGIC
# MAGIC When a user types "New South Wales" or "NSW", Genie must map that natural language term to the
# MAGIC exact value stored in the `region_id` column (`NSW1`, `VIC1`, `QLD1`, `SA1`, `TAS1`).
# MAGIC
# MAGIC That mapping is called **entity matching** (also labelled "Format assistance" in the Configure UI).
# MAGIC Entity matching is disabled for `region_id` — so Genie guesses the raw string `'NSW'` instead of
# MAGIC looking up the correct code.
# MAGIC
# MAGIC **Root cause:** Entity matching not enabled for `spot_prices.region_id`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 0d — Apply the fix
# MAGIC
# MAGIC **🖱️ UI:** Configure → Data → `spot_prices` (click to expand) → `region_id` (click to expand)
# MAGIC → **Format assistance** → toggle **ON** → **Save**
# MAGIC
# MAGIC When enabled, Genie queries the actual distinct values in `region_id` at question time and matches
# MAGIC the user's words to those values. It will find `NSW1`, `VIC1`, `QLD1`, `SA1`, `TAS1` and use
# MAGIC the correct code in every query.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 0e — Re-run only the failing benchmark and confirm
# MAGIC
# MAGIC Do not re-run all benchmarks — that is slow and wastes quota.
# MAGIC Target just the question you fixed.
# MAGIC
# MAGIC **🖱️ UI:** Benchmark tab → click the failing question (checkbox on the left) → **Run selected**
# MAGIC
# MAGIC Wait for the result. It should move from Red (BAD) to Green (GOOD).
# MAGIC
# MAGIC Note the new overall score here: `_____% Good`
# MAGIC
# MAGIC If it is still BAD: check that Format assistance was saved. Go to Configure → Data → spot_prices
# MAGIC → region_id — the toggle should show ON. If the toggle is already ON, the save did not take —
# MAGIC toggle it OFF and then ON again, then Save. Re-run the selected benchmark.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Read Benchmark Results via API (Slide 16)
# MAGIC
# MAGIC > *"Benchmarks detect drift or inconsistencies over time. They surface regressions or bugs early — before org-wide adoption."*
# MAGIC
# MAGIC The cell below reads your latest benchmark run and prints the score.
# MAGIC Run it after the UI run completes to confirm you are reading the post-fix numbers.
# MAGIC
# MAGIC ```
# MAGIC Green  = GOOD         (SQL matched or result set matched)
# MAGIC Red    = BAD          (wrong answer, empty result, or query error)
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
            print("No benchmark runs yet — run benchmarks in the UI first (Benchmark tab → Run benchmarks).")
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
                    needs_review_questions = []
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
                            needs_review_questions.append(item.get("question", "unknown"))

                    total = len(result_items)
                    pct   = int(good / total * 100) if total else 0
                    print(f"\nLatest run — {pct}% Good ({good}/{total})")
                    print(f"  Good:         {good}")
                    print(f"  Bad:          {bad}")
                    print(f"  Needs review: {needs_review}")
                    if bad_questions:
                        print(f"\nBAD questions to investigate:")
                        for q in bad_questions:
                            print(f"  -> {q[:80]}")
                    if needs_review_questions:
                        print(f"\nNEEDS_REVIEW questions (manual check required):")
                        for q in needs_review_questions:
                            print(f"  -> {q[:80]}")
else:
    print("Enter Space ID in widget.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Diagnose and Fix Remaining Failures
# MAGIC
# MAGIC You just completed one full iteration of the loop (0a → 0b → 0c → 0d → 0e).
# MAGIC Now apply that same loop to every remaining BAD or NEEDS_REVIEW result.
# MAGIC
# MAGIC **The loop, repeated:**
# MAGIC ```
# MAGIC Pick one BAD result from the API output above
# MAGIC   ──► click it in the Evaluations tab ──► read Generated SQL
# MAGIC   ──► use the tables below to identify the cause
# MAGIC   ──► apply the fix (entity match / golden query / instruction / benchmark edit)
# MAGIC   ──► Run selected ──► confirm Green ──► pick the next BAD result
# MAGIC ```
# MAGIC
# MAGIC Work through the BAD list printed above, one question at a time.
# MAGIC Do not batch all fixes and then re-run — fix one, confirm it, then move to the next.
# MAGIC That discipline makes it obvious which fix caused which improvement.
# MAGIC
# MAGIC For each remaining "Bad" or "Needs Review" benchmark: click to expand and read the generated SQL.
# MAGIC Use this reference to identify the cause and apply the correct fix.
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
# MAGIC **Diagnosis path:** open the benchmark → Genie SQL tab → check the WHERE clause on the date column.
# MAGIC If you see a filter using `CURRENT_DATE` or `CURRENT_TIMESTAMP`, this is the cause.
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
# MAGIC **🖱️ UI:** Benchmark tab → click the failing benchmark → **Edit** → update Expected SQL → **Save**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### 🟡 `LLM_JUDGE_MISSING_OR_INCORRECT_FILTER`
# MAGIC Genie's SQL ran and returned data, but the LLM judge detected a missing or wrong filter
# MAGIC compared to what the benchmark expected.
# MAGIC
# MAGIC **Diagnosis path:** compare the two SQL panes side by side. Focus on WHERE clauses and aggregation
# MAGIC expressions. Look for what is present in Expected SQL but absent or different in Generated SQL.
# MAGIC
# MAGIC | What you see in Genie's SQL | Cause | Fix |
# MAGIC |---|---|---|
# MAGIC | Extra columns (`interval_count`, `max_price`, `min_settlement_date`) | Genie being "helpful" — not wrong, just unexpected | Accept it (update benchmark to allow extra cols) or add a golden query with the exact column list |
# MAGIC | Date filter missing or broadened | `settlement_date` column description doesn't make range requirement clear | Strengthen the column description, or add a golden query with an explicit date parameter |
# MAGIC | Region filter dropped (`WHERE region_id = 'QLD1'` missing) | Ambiguous question phrasing | Rephrase the benchmark question to be explicit — "in QLD1" not "in QLD" |
# MAGIC | `ROUND(SUM(dispatch_mw)/12, 1)` changed to `SUM(dispatch_mw)/12` | Column description doesn't specify rounding | Add rounding requirement to the `dispatch_mw` column description |
# MAGIC
# MAGIC **Decision rule:**
# MAGIC - Logic correct, only column names or aliases differ → update the benchmark expected SQL
# MAGIC - Logic wrong (wrong filter, wrong join, wrong aggregation) → add a golden query to override Genie's generation for this pattern
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### 🔴 `RESULT_MISSING_COLUMNS`
# MAGIC Genie's result has different columns from what the benchmark expected.
# MAGIC
# MAGIC **Diagnosis path:** look at the column headers in each result pane. Note which columns are
# MAGIC present in Expected but absent in Generated (or vice versa).
# MAGIC
# MAGIC | What you see | Cause | Fix |
# MAGIC |---|---|---|
# MAGIC | `avg_spot_price` instead of `avg_price_mwh` | Genie chose a different alias | Add `avg_price_mwh` as a synonym for `rrp` so Genie learns the preferred naming |
# MAGIC | Genie returned `date, num_intervals, avg_spot_price` instead of `region_id, avg_price_mwh` | No data for expected date range — Genie rewrote the query to show available dates | Fix the `EMPTY_RESULT` root cause first (update benchmark dates), then re-run |
# MAGIC | Extra columns added | Genie is being helpful | Add a golden query with the exact column list |
# MAGIC
# MAGIC **Rule of thumb:** `RESULT_MISSING_COLUMNS` alone → fix with a golden query.
# MAGIC `RESULT_MISSING_COLUMNS` + `LLM_JUDGE_MISSING_OR_INCORRECT_FILTER` together → fix the date/filter
# MAGIC issue first, then re-run — columns often self-correct once the filter is right.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### AEMO-specific symptom → cause → fix table
# MAGIC
# MAGIC | Symptom in generated SQL | Likely cause | Fix |
# MAGIC |---|---|---|
# MAGIC | `region_id = 'NSW'` instead of `'NSW1'` | Entity matching not enabled | Configure → Data → spot_prices → region_id → Format assistance → enable |
# MAGIC | `notice_type = 'LOR'` instead of `LIKE 'LOR%'` | No entity matching for notice_type | Enable entity matching for notice_type; the LOR golden query already uses `LIKE 'LOR%'` |
# MAGIC | No join to `generator_registration` | Join not configured | Configure → Instructions → Joins — verify the join is listed |
# MAGIC | `rrp` called `spot_price` or `price` | Synonym for rrp not set | Configure → Data → spot_prices → rrp → Synonyms → add "price", "spot price" |
# MAGIC | Date filter missing entirely | No data for queried range, Genie adapted | Update benchmark to use historical date (see EMPTY_RESULT fix above) |
# MAGIC | Genie says "no data available for yesterday" | Data ends 2025-12-31 | Update benchmark expected SQL to use `'2025-12-31'` |
# MAGIC | `SUM(dispatch_mw)/12` not divided | `dispatch_mw` description doesn't mention MWh conversion | Column description for `dispatch_mw` already says "divide by 12 for MWh" — check it is saved |
# MAGIC | Renewable defined as solar+wind+hydro+battery | Genie included hydro/battery | Add a text instruction: "Renewable generation = solar and wind only. Hydro and battery are separate categories." |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **After fixing → re-run just the failing benchmark:**
# MAGIC
# MAGIC **🖱️ UI:** Benchmark tab → click the failing question (checkbox on the left) → **Run selected**
# MAGIC
# MAGIC Do not re-run all benchmarks after every change — it is slow and wastes quota.
# MAGIC Re-run the full set only when you want to measure overall progress.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: The Monitor Tab — real user feedback (Slide 13)
# MAGIC
# MAGIC > *"User feedback continuously improves Genie's quality by capturing real-world user input and routing it to authors for action."*
# MAGIC
# MAGIC The Monitor tab is where production feedback lands. Unlike benchmarks (which you control),
# MAGIC Monitor shows what real users experienced and what they flagged.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 3a — Navigate to Monitor
# MAGIC
# MAGIC **🖱️ UI:** **Monitor** tab (top-level tab, not under Configure — it is next to Benchmark)
# MAGIC
# MAGIC You will see a feed of conversations with filter buttons across the top:
# MAGIC
# MAGIC | Filter | What it shows |
# MAGIC |---|---|
# MAGIC | All | Every conversation in the space |
# MAGIC | Thumbs up | Questions the user rated as correct |
# MAGIC | Thumbs down | Questions the user rated as wrong |
# MAGIC | Fix it | Questions flagged by the author during review (you flagged these) |
# MAGIC | Request review | Questions a user escalated to the space author for investigation |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 3b — Reading a Monitor entry
# MAGIC
# MAGIC **🖱️ UI:** Click any question in the Monitor feed → expand → read the generated SQL
# MAGIC
# MAGIC For each entry you can see:
# MAGIC - The exact question the user asked
# MAGIC - The SQL Genie generated
# MAGIC - The result table returned to the user
# MAGIC - The feedback rating the user gave
# MAGIC - Any comment the user added
# MAGIC
# MAGIC If the SQL is wrong, you can act directly from this view.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 3c — Using "Fix it" to create a golden query from Monitor
# MAGIC
# MAGIC "Fix it" is a shortcut that lets you save a corrected SQL as a golden query without leaving
# MAGIC the Monitor tab. This is the fastest path from "user reported a wrong answer" to "Genie now
# MAGIC gets it right".
# MAGIC
# MAGIC **🖱️ UI:** Monitor tab → expand a Thumbs down entry → read the generated SQL → identify the error
# MAGIC → click **Fix it** (button in the top-right of the expanded entry)
# MAGIC
# MAGIC What happens next:
# MAGIC
# MAGIC ```
# MAGIC 1. The "Fix it" panel opens with the original question pre-filled
# MAGIC 2. The SQL editor shows Genie's incorrect SQL — edit it to the correct version
# MAGIC 3. Click Save — this saves the corrected SQL as a golden query linked to that question
# MAGIC 4. The entry moves to the "Fix it" filter so you can track what you have reviewed
# MAGIC 5. Next time a user asks a semantically similar question, Genie uses the golden query
# MAGIC ```
# MAGIC
# MAGIC This is exactly the same as going to Configure → Instructions → Golden queries → + Add,
# MAGIC but it is faster because the question is already pre-filled from the user's conversation.
# MAGIC
# MAGIC **When to use "Fix it" vs other fixes:**
# MAGIC
# MAGIC | Situation | Best fix |
# MAGIC |---|---|
# MAGIC | Genie used wrong SQL logic for a specific question | Fix it → golden query (overrides Genie's generation for this pattern) |
# MAGIC | Genie used wrong column value (e.g. 'NSW' not 'NSW1') | Entity matching (fixes the value lookup globally, not per-question) |
# MAGIC | Genie misunderstood a business term consistently | Instruction or synonym (fixes globally) |
# MAGIC | The benchmark expected SQL is wrong | Edit the benchmark expected SQL |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 3d — The full feedback loop: Thumbs down → Request review → author action
# MAGIC
# MAGIC This is the workflow when a business user encounters a wrong answer in production:
# MAGIC
# MAGIC ```
# MAGIC User gets a wrong answer
# MAGIC     → clicks Thumbs down (optional: types a comment)
# MAGIC     → optionally clicks "Request review" (escalates to the space author)
# MAGIC
# MAGIC Space author (you) opens Monitor → filters by "Request review"
# MAGIC     → reads the question and the SQL
# MAGIC     → clicks "Fix it" → corrects the SQL → saves as golden query
# MAGIC     → re-runs the benchmark for that question to confirm the fix
# MAGIC
# MAGIC Next time the user asks the same question:
# MAGIC     → Genie uses the golden query → correct answer → user clicks Thumbs up
# MAGIC ```
# MAGIC
# MAGIC **🖱️ UI:** Monitor tab → **Analyze space usage** button (top right) → opens Genie Code
# MAGIC pre-configured to analyse your Monitor data for patterns across all conversations
# MAGIC
# MAGIC Use "Analyze space usage" weekly to spot clusters of failing questions before they are individually
# MAGIC reported — one pattern often explains multiple Thumbs down entries.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Alert on user feedback (Slide 32)
# MAGIC
# MAGIC > *"The audit system table reflects all events within ~15 minutes. Query it and use in an alert."*
# MAGIC
# MAGIC **🖱️ UI:** SQL Editor → paste the query below → Run → **Save** → **Alerts** → + Create alert
# MAGIC → select this query → set threshold: `negative_count > 0` → Notify: your email
# MAGIC
# MAGIC **⚡ Automated:** run the cell below to query the audit table directly and see negative feedback now.

# COMMAND ----------

# Feedback alert query — from Slide 32
feedback_sql = """
    SELECT
        user_identity.email             AS user_email,
        action_name,
        request_params.space_id         AS space_id,
        request_params.feedback_rating  AS rating,
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
    else:
        print("No THUMBS_DOWN feedback yet — system.access.audit populates as users interact with the space.")
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
# MAGIC **🖱️ UI:** Share the space: top-right → **Share** button
# MAGIC
# MAGIC | Permission | What they can do |
# MAGIC |---|---|
# MAGIC | CAN MANAGE | Full control — sees all conversations and the Monitor tab |
# MAGIC | CAN EDIT | Modify instructions, golden queries, and column descriptions |
# MAGIC | CAN RUN | Ask questions and give feedback — the permission for business users |

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
# MAGIC ## Lab 03 Checkpoint
# MAGIC
# MAGIC - [ ] Baseline benchmark score recorded before any changes
# MAGIC - [ ] Deliberate flaw identified (region_id entity matching)
# MAGIC - [ ] Fix applied (Format assistance enabled for region_id)
# MAGIC - [ ] Selected benchmark re-run confirms the fix improved the score
# MAGIC - [ ] At least 1 additional failing benchmark diagnosed and fixed
# MAGIC - [ ] Monitor tab explored — at least 1 entry expanded and SQL reviewed
# MAGIC - [ ] "Fix it" flow understood — know when to use it vs entity matching vs instruction
# MAGIC - [ ] Feedback alert SQL understood
# MAGIC - [ ] Space shared with at least 1 other participant (CAN RUN)
# MAGIC
# MAGIC **Next: Lab 04 — Monitoring Usage, Cost & Feedback**
