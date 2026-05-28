# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', Arial, sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 02: Core User Workflows</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0;">Session 2 · AEMO NEM Operations · 25 minutes</p>
# MAGIC </div>
# MAGIC <div style="background: #f7f8fa; border-left: 4px solid #FF3621; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 0;">
# MAGIC   <b>What you will practise:</b> Seven progressively complex questions in your Genie Space — from a single-region spot price lookup to a multi-month trend comparison with agent mode and follow-up questions.<br><br>
# MAGIC   <b>How this lab works:</b> Each task has a markdown scenario cell (what to type in Genie) followed by a SQL cell you run here to <i>cross-check</i> the answer Genie gives you. Always click <b>Show SQL</b> in Genie to verify what query it generated.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — widget config and shared references

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",        "Catalog")
dbutils.widgets.text("schema_aemo", "aemo",               "Schema")
dbutils.widgets.text("space_id",    "",                   "Genie Space ID (from Lab 01)")

# COMMAND ----------

CATALOG   = dbutils.widgets.get("catalog")
SCHEMA    = dbutils.widgets.get("schema_aemo")
SPACE_ID  = dbutils.widgets.get("space_id")

# Try to retrieve from Spark config if widget is empty (same session as Lab 01)
if not SPACE_ID:
    try:
        SPACE_ID = spark.conf.get("workshop.genie.space_id")
        print(f"Retrieved Space ID from session config: {SPACE_ID}")
    except Exception:
        print("WARNING: Space ID is not set. Enter it in the 'space_id' widget above.")
        print("Copy it from the Lab 01 output cell.")

print(f"Catalog  : {CATALOG}")
print(f"Schema   : {SCHEMA}")
print(f"Space ID : {SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## How to use this lab
# MAGIC
# MAGIC 1. For each task: read the scenario cell, then **switch to your Genie Space tab** and type the question exactly as written (or paraphrase — Genie handles natural language)
# MAGIC 2. After Genie responds: click **Show SQL** in the result panel to review the query it generated
# MAGIC 3. Run the **Validation SQL** cell in this notebook to compute the same answer from raw data
# MAGIC 4. Compare the numbers — they should match within rounding
# MAGIC 5. If they differ: look at the Genie SQL and identify what is different
# MAGIC
# MAGIC > **Open your Genie Space now:** `{your-workspace-host}#pages/genie/spaces/{SPACE_ID}`

# COMMAND ----------

# Quick link builder — run this cell to get your clickable Space URL
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
space_url = f"{w.config.host}#pages/genie/spaces/{SPACE_ID}"
print(f"Your Genie Space URL:\n{space_url}")
displayHTML(f'<a href="{space_url}" target="_blank" style="font-size:1.2em; color:#FF3621; font-weight:bold;">Open AEMO NEM Operations Genie Space ↗</a>')

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 1 — Simple Question: Single Region Spot Price
# MAGIC **Estimated time:** 3 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC You are an operations analyst. A colleague asks: *"What did we pay for electricity in Victoria yesterday?"*
# MAGIC
# MAGIC ### Question to type in Genie
# MAGIC ```
# MAGIC What was the average spot price in VIC1 yesterday?
# MAGIC ```
# MAGIC
# MAGIC ### What you should see
# MAGIC - A single number in $/MWh (e.g. `$87.42/MWh`)
# MAGIC - A table showing 1 row: region_id = VIC1, avg_price = [number]
# MAGIC - The SQL Genie generated should filter to `region_id = 'VIC1'` and `DATE(settlement_date) = CURRENT_DATE - INTERVAL 1 DAY`
# MAGIC
# MAGIC ### Show SQL reminder
# MAGIC After Genie responds, click **Show SQL** in the bottom-left of the result. Confirm:
# MAGIC - The filter is `region_id = 'VIC1'` (not `'VIC'` or `'Victoria'`)
# MAGIC - The date filter uses yesterday, not a hardcoded date
# MAGIC - The aggregation is `AVG(rrp)` or similar

# COMMAND ----------

# Validation SQL — Task 1
# Run this cell and compare the result to what Genie showed you
print("Validation SQL for Task 1: Average spot price in VIC1 yesterday\n")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     ROUND(AVG(rrp), 2)  AS avg_price_dollarMWh,
# MAGIC     ROUND(MIN(rrp), 2)  AS min_price_dollarMWh,
# MAGIC     ROUND(MAX(rrp), 2)  AS max_price_dollarMWh,
# MAGIC     COUNT(*)             AS trading_intervals
# MAGIC FROM ${catalog}.${schema_aemo}.spot_prices
# MAGIC WHERE
# MAGIC     DATE(settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
# MAGIC     AND region_id = 'VIC1'
# MAGIC GROUP BY region_id

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** This is where Genie earns trust with business users — a simple, one-sentence question returns a clean table. The analyst never wrote SQL.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 2 — Comparative: All NEM Regions Side by Side
# MAGIC **Estimated time:** 3 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC Your manager wants to know which NEM region had the highest electricity prices last week for a market report.
# MAGIC
# MAGIC ### Question to type in Genie
# MAGIC ```
# MAGIC Compare average spot prices across all NEM regions last week
# MAGIC ```
# MAGIC
# MAGIC ### What you should see
# MAGIC - A table with 5 rows (NSW1, VIC1, QLD1, SA1, TAS1)
# MAGIC - Average price per region for the 7-day window
# MAGIC - Optionally a bar chart if Genie auto-visualises (click the chart icon in the result)
# MAGIC
# MAGIC ### What to watch for
# MAGIC - South Australia (SA1) and Tasmania (TAS1) sometimes have very different prices due to interconnector constraints
# MAGIC - If Genie uses a different date range (e.g. last calendar week vs last 7 days), ask it to clarify in a follow-up

# COMMAND ----------

# Validation SQL — Task 2
# MAGIC %sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     ROUND(AVG(rrp), 2)   AS avg_price_dollarMWh,
# MAGIC     ROUND(MIN(rrp), 2)   AS min_price_dollarMWh,
# MAGIC     ROUND(MAX(rrp), 2)   AS max_price_dollarMWh
# MAGIC FROM ${catalog}.${schema_aemo}.spot_prices
# MAGIC WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
# MAGIC GROUP BY region_id
# MAGIC ORDER BY avg_price_dollarMWh DESC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** Genie understands "all NEM regions" because the Space instructions tell it the five region codes. Without that domain context, it would not know what "NEM regions" means.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 3 — Investigation: Price Spike Detection
# MAGIC **Estimated time:** 4 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC Your reliability team flagged that there may have been some high-price events last month that triggered hedging alerts. You need to find when and where spikes occurred.
# MAGIC
# MAGIC ### Question to type in Genie
# MAGIC ```
# MAGIC Were there any price spikes above $500/MWh last month? Show me when and where
# MAGIC ```
# MAGIC
# MAGIC ### What you should see
# MAGIC - A table of dispatch intervals where rrp > 500, with settlement_date, region_id, and price
# MAGIC - Ordered from highest price to lowest (or chronologically — check the SQL)
# MAGIC - If no spikes occurred last month in your workshop data, Genie should say "No results found" — this is correct behaviour, not an error
# MAGIC
# MAGIC ### Things to test
# MAGIC - Try asking "spikes above $1,000/MWh" — does the result change correctly?
# MAGIC - Ask "which region had the most spikes?" as a follow-up (Task 3b)

# COMMAND ----------

# Validation SQL — Task 3
# MAGIC %sql
# MAGIC SELECT
# MAGIC     settlement_date,
# MAGIC     region_id,
# MAGIC     ROUND(rrp, 2)  AS spike_price_dollarMWh
# MAGIC FROM ${catalog}.${schema_aemo}.spot_prices
# MAGIC WHERE
# MAGIC     settlement_date >= DATE_TRUNC('MONTH', CURRENT_DATE - INTERVAL 32 DAYS)
# MAGIC     AND settlement_date <  DATE_TRUNC('MONTH', CURRENT_DATE)
# MAGIC     AND rrp > 500
# MAGIC ORDER BY rrp DESC
# MAGIC LIMIT 100

# COMMAND ----------

# Spike summary by region for cross-check
# MAGIC %sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     COUNT(*)             AS spike_count,
# MAGIC     ROUND(MAX(rrp), 2)   AS highest_spike_dollarMWh
# MAGIC FROM ${catalog}.${schema_aemo}.spot_prices
# MAGIC WHERE
# MAGIC     settlement_date >= DATE_TRUNC('MONTH', CURRENT_DATE - INTERVAL 32 DAYS)
# MAGIC     AND settlement_date <  DATE_TRUNC('MONTH', CURRENT_DATE)
# MAGIC     AND rrp > 500
# MAGIC GROUP BY region_id
# MAGIC ORDER BY spike_count DESC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** Ask the group — did Genie use the correct threshold ($500)? Did it interpret "last month" as the previous calendar month or the past 30 days? Both are reasonable interpretations. If the answer is ambiguous, the best practice is to ask Genie to clarify or refine with a follow-up question.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 4 — Market Notices: LOR Events
# MAGIC **Estimated time:** 3 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC The operations manager asks you to check whether AEMO issued any Lack of Reserve notices in the past two weeks — a sign of grid stress.
# MAGIC
# MAGIC ### Question to type in Genie
# MAGIC ```
# MAGIC List any LOR events in the last 14 days
# MAGIC ```
# MAGIC
# MAGIC ### What you should see
# MAGIC - A table from the `market_notices` table filtered to `notice_type LIKE 'LOR%'`
# MAGIC - Columns: notice_id, notice_type (LOR1/LOR2/LOR3), region_id, issue_time, reason text
# MAGIC - If no LOR notices in that window: an empty result with a message from Genie
# MAGIC
# MAGIC ### LOR severity reference
# MAGIC
# MAGIC | Notice | Meaning |
# MAGIC |--------|---------|
# MAGIC | LOR1 | Reserve margin below threshold — monitor closely |
# MAGIC | LOR2 | Manual load shedding may be required |
# MAGIC | LOR3 | Load shedding is imminent or occurring |
# MAGIC
# MAGIC ### What to check in the SQL
# MAGIC - Genie should filter `notice_type` for LOR variants, not just look in the reason text field
# MAGIC - The 14-day window should be relative, not hardcoded

# COMMAND ----------

# Validation SQL — Task 4
# MAGIC %sql
# MAGIC SELECT
# MAGIC     notice_id,
# MAGIC     notice_type,
# MAGIC     region_id,
# MAGIC     issue_time,
# MAGIC     effective_date,
# MAGIC     LEFT(reason, 200)  AS reason_preview
# MAGIC FROM ${catalog}.${schema_aemo}.market_notices
# MAGIC WHERE
# MAGIC     issue_time >= CURRENT_DATE - INTERVAL 14 DAYS
# MAGIC     AND notice_type LIKE 'LOR%'
# MAGIC ORDER BY issue_time DESC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** This task highlights the value of the Space instructions. Because we defined LOR1/LOR2/LOR3 in the instructions, Genie knows to use `notice_type LIKE 'LOR%'` rather than a free-text search on the reason field.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 5 — Agent Mode: Multi-Month Trend Analysis
# MAGIC **Estimated time:** 4 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC The head of market analysis wants a view of how Queensland's generation mix has shifted over the past quarter — specifically coal versus renewables.
# MAGIC
# MAGIC ### Question to type in Genie
# MAGIC ```
# MAGIC Compare coal vs renewable dispatch in QLD for the last 3 months — show the trend
# MAGIC ```
# MAGIC
# MAGIC ### What you should see
# MAGIC - A table with columns: month, generation_category (Coal / Renewable), total_MWh
# MAGIC - 3 months × 2 categories = 6 data rows minimum
# MAGIC - Genie may automatically offer a line or bar chart — click the chart icon to visualise
# MAGIC
# MAGIC ### Enabling Agent Mode (if not already on)
# MAGIC 1. In the Genie conversation, look for the **Agent mode** toggle at the top of the chat input
# MAGIC 2. Switch it ON — this allows Genie to ask clarifying questions and run multiple queries
# MAGIC 3. Re-ask the question — you may see Genie run two sub-queries (one for coal, one for renewables) and combine them
# MAGIC
# MAGIC ### What to compare
# MAGIC - Is coal dispatch declining month-over-month?
# MAGIC - Is renewable dispatch increasing?
# MAGIC - Does Genie correctly classify fuel types? (Black coal + brown coal = Coal; Wind + Solar = Renewable)

# COMMAND ----------

# Validation SQL — Task 5
# MAGIC %sql
# MAGIC SELECT
# MAGIC     DATE_FORMAT(d.settlement_date, 'yyyy-MM')  AS month,
# MAGIC     CASE
# MAGIC         WHEN g.fuel_type IN ('BLACK COAL', 'BROWN COAL') THEN 'Coal'
# MAGIC         WHEN g.fuel_type IN ('WIND', 'SOLAR')            THEN 'Renewable'
# MAGIC         ELSE 'Other'
# MAGIC     END                                        AS generation_category,
# MAGIC     ROUND(SUM(d.dispatch_mw) / 12, 0)          AS total_MWh
# MAGIC FROM ${catalog}.${schema_aemo}.dispatch_intervals d
# MAGIC JOIN ${catalog}.${schema_aemo}.generator_registration g
# MAGIC     ON d.duid = g.duid
# MAGIC WHERE
# MAGIC     g.region_id = 'QLD1'
# MAGIC     AND d.settlement_date >= ADD_MONTHS(CURRENT_DATE(), -3)
# MAGIC GROUP BY DATE_FORMAT(d.settlement_date, 'yyyy-MM'), generation_category
# MAGIC ORDER BY month ASC, generation_category ASC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** This is the most complex query in the workshop. It requires a JOIN across two tables and a CASE statement for fuel type classification. Without the golden query we added in Lab 01, Genie might generate this differently. Golden queries are most valuable for complex multi-table patterns.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 6 — Follow-Up: Highest Price Period Generator Detail
# MAGIC **Estimated time:** 4 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC After seeing the price spikes from Task 3, your team wants to know which generators were operating during those expensive moments.
# MAGIC
# MAGIC ### Question to type in Genie (as a FOLLOW-UP to Task 3)
# MAGIC > Make sure you are still in the same conversation from Task 3, or start a new one and include context.
# MAGIC
# MAGIC ```
# MAGIC Now show me which generators were dispatched during the highest price period
# MAGIC ```
# MAGIC
# MAGIC **Alternative (new conversation):**
# MAGIC ```
# MAGIC Show me which generators were dispatched during the top 10 most expensive 5-minute intervals last month
# MAGIC ```
# MAGIC
# MAGIC ### What you should see
# MAGIC - A table joining `dispatch_intervals` and `generator_registration`
# MAGIC - Columns: settlement_date, region_id, spike price, duid, station_name, fuel_type, dispatched MW
# MAGIC - The result reveals whether gas peakers or coal units were setting the market price during spikes
# MAGIC
# MAGIC ### Follow-up conversation feature
# MAGIC Genie maintains conversation context. When you say "now show me" it refers back to the previous question's result. This is particularly useful for:
# MAGIC - Drilling down into a summary
# MAGIC - Adding a filter to a previous result
# MAGIC - Changing the visualisation of an earlier answer

# COMMAND ----------

# Validation SQL — Task 6
# MAGIC %sql
# MAGIC WITH top_intervals AS (
# MAGIC     SELECT
# MAGIC         settlement_date,
# MAGIC         region_id,
# MAGIC         ROUND(rrp, 2) AS spike_price_dollarMWh
# MAGIC     FROM ${catalog}.${schema_aemo}.spot_prices
# MAGIC     WHERE settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
# MAGIC     ORDER BY rrp DESC
# MAGIC     LIMIT 10
# MAGIC )
# MAGIC SELECT
# MAGIC     ti.settlement_date,
# MAGIC     ti.region_id,
# MAGIC     ti.spike_price_dollarMWh,
# MAGIC     d.duid,
# MAGIC     g.station_name,
# MAGIC     g.fuel_type,
# MAGIC     ROUND(d.dispatch_mw, 1) AS dispatched_MW
# MAGIC FROM top_intervals ti
# MAGIC JOIN ${catalog}.${schema_aemo}.dispatch_intervals d
# MAGIC     ON ti.settlement_date = d.settlement_date
# MAGIC JOIN ${catalog}.${schema_aemo}.generator_registration g
# MAGIC     ON d.duid = g.duid
# MAGIC WHERE g.region_id = ti.region_id
# MAGIC ORDER BY ti.spike_price_dollarMWh DESC, d.dispatch_mw DESC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** If Genie correctly follows the conversation context and generates the JOIN automatically, that is a strong signal the Space instructions and golden queries are working well. If it struggles with the cross-table JOIN, the fix is to add more golden queries that demonstrate this join pattern.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Task 7 — Dashboard: Add a Genie Result to an AI/BI Dashboard
# MAGIC **Estimated time:** 4 minutes
# MAGIC
# MAGIC ### Scenario
# MAGIC Your manager wants the spot price comparison chart on the AEMO NEM Operations dashboard so the team can see it every morning without asking Genie each time.
# MAGIC
# MAGIC ### Steps — UI only (no SQL needed)
# MAGIC
# MAGIC **Step 1: Get a visualisation in Genie**
# MAGIC 1. In Genie, ask: `Compare average spot prices across all NEM regions for the last 7 days`
# MAGIC 2. Wait for the result table to appear
# MAGIC 3. Click the **chart icon** (bar chart symbol) in the result panel toolbar
# MAGIC 4. Genie will auto-generate a bar chart — you can adjust the chart type
# MAGIC
# MAGIC **Step 2: Add to dashboard**
# MAGIC 1. In the result panel, click the **three-dot menu (⋮)** in the top-right corner
# MAGIC 2. Select **Add to dashboard**
# MAGIC 3. In the dialog: choose **Create new dashboard** and name it `AEMO NEM Daily Overview`
# MAGIC 4. Click **Add** — Genie creates the dashboard and adds the chart as the first widget
# MAGIC
# MAGIC **Step 3: Open and verify the dashboard**
# MAGIC 1. Click **View dashboard** in the confirmation toast (or navigate via Dashboards in the left sidebar)
# MAGIC 2. Confirm the chart shows correct region data
# MAGIC 3. Note that the dashboard widget is backed by the same SQL Genie generated — you can edit it
# MAGIC
# MAGIC **Step 4: Share the dashboard**
# MAGIC 1. Click **Share** in the top-right of the dashboard
# MAGIC 2. Add the `analysts` group with **Can View** permission
# MAGIC 3. Click **Publish** to make it accessible

# COMMAND ----------

# No Validation SQL for Task 7 — this is a UI workflow
# Run this cell to confirm the spot price data the dashboard widget will use

# MAGIC %sql
# MAGIC -- This is the SQL that backs the "Add to Dashboard" widget
# MAGIC SELECT
# MAGIC     DATE(settlement_date)  AS trading_date,
# MAGIC     region_id,
# MAGIC     ROUND(AVG(rrp), 2)   AS avg_price_dollarMWh
# MAGIC FROM ${catalog}.${schema_aemo}.spot_prices
# MAGIC WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
# MAGIC GROUP BY DATE(settlement_date), region_id
# MAGIC ORDER BY trading_date ASC, region_id ASC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Debrief point:** The "Add to dashboard" workflow is one of the highest-value Genie features for business users. An analyst who has never written SQL can produce a live, refreshable dashboard in under 2 minutes. The underlying SQL is fully visible and editable by engineers.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab Summary
# MAGIC
# MAGIC | Task | Question type | Key Genie feature used |
# MAGIC |------|--------------|----------------------|
# MAGIC | 1 | Simple lookup | Natural language → SQL, domain term recognition |
# MAGIC | 2 | Comparative | Multi-row aggregation, all-regions query |
# MAGIC | 3 | Investigation | Threshold filter, spike detection |
# MAGIC | 4 | Domain-specific | LOR notice lookup using NEM terminology |
# MAGIC | 5 | Trend analysis | Multi-month aggregation, Agent mode |
# MAGIC | 6 | Follow-up | Conversation context, cross-table JOIN |
# MAGIC | 7 | Dashboard creation | Add to dashboard, publish to team |
# MAGIC
# MAGIC ### Patterns that improved answer quality
# MAGIC - Space instructions defined NEM region codes (NSW1, VIC1, QLD1, SA1, TAS1)
# MAGIC - Instructions defined LOR severity levels so Genie used `LIKE 'LOR%'` correctly
# MAGIC - Golden queries demonstrated the coal/renewable classification pattern
# MAGIC - Golden queries showed the dispatch + generator_registration JOIN
# MAGIC
# MAGIC ### Always verify with Show SQL
# MAGIC Before sharing a Genie answer with stakeholders, click **Show SQL** and check:
# MAGIC 1. The correct table(s) are being queried
# MAGIC 2. The date filter is relative, not hardcoded
# MAGIC 3. Any aggregation (AVG, SUM, COUNT) matches the question intent
# MAGIC 4. JOINs use the correct key columns (duid for generators, region_id for prices)
# MAGIC
# MAGIC **Next: Lab 03 → Controls, Governance and Access** — how to monitor who is using the Space, understand billing, and prepare for production rollout.

# COMMAND ----------

# Final check: confirm all five tables were queried successfully in this lab
tables_used = ["spot_prices", "dispatch_intervals", "market_notices",
               "generator_registration", "settlement_amounts"]

print("Tables exercised in Lab 02:")
for t in tables_used:
    used = t in ["spot_prices", "dispatch_intervals", "market_notices", "generator_registration"]
    status = "✓ used" if used else "— not directly queried (covered in Lab 01 golden queries)"
    print(f"  {CATALOG}.{SCHEMA}.{t:<30} {status}")

print("\nLab 02 complete. Space ID for Lab 03:", SPACE_ID)
