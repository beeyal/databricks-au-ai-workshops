# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A4B 0%, #FF3621 100%); padding: 40px 32px 32px 32px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-size: 2.4em; font-weight: 700; margin: 0 0 8px 0;">Session 3: AEMO Genie Experience</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.9); font-size: 1.2em; margin: 0 0 20px 0;">Ask questions about NEM operations data in plain English</p>
# MAGIC   <table style="color: white; border-collapse: collapse; width: 100%;">
# MAGIC     <tr>
# MAGIC       <td style="padding: 6px 20px 6px 0; font-size: 0.95em;"><strong>Duration:</strong> 2 hours</td>
# MAGIC       <td style="padding: 6px 20px 6px 0; font-size: 0.95em;"><strong>Audience:</strong> Business users</td>
# MAGIC       <td style="padding: 6px 0 6px 0; font-size: 0.95em;"><strong>Coding required:</strong> None</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC </div>
# MAGIC
# MAGIC **What you will do today:**
# MAGIC - Ask operational questions in plain English and get data-backed answers
# MAGIC - Verify that answers are correct before sharing them
# MAGIC - Build a simple live dashboard from a Genie conversation

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Quick connection check
# MAGIC
# MAGIC Make sure the cluster at the top of this notebook says **"AEMO Workshops"** (green dot). Then run the cell below — click the triangle button or press **Shift + Enter**. You should see your email address. If you see an error, raise your hand.

# COMMAND ----------

spark.sql("USE CATALOG workshop_au")

user = spark.sql("SELECT current_user() AS me").collect()[0]["me"]
print(f"Connected as: {user}")
print(f"Spark version: {spark.version}")
print(f"You are ready to start.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Confirm the AEMO data is available
# MAGIC
# MAGIC Run this cell to check that the tables Genie will use have data. Each row should show a number above zero — if you see ERROR or EMPTY, raise your hand.

# COMMAND ----------

tables = [
    "aemo.spot_prices",
    "aemo.dispatch_intervals",
    "aemo.market_notices",
    "aemo.generator_registration",
    "aemo.settlement_amounts",
]

print(f"{'Table':<40} {'Row count':>15}")
print("-" * 57)
for t in tables:
    try:
        count = spark.sql(f"SELECT COUNT(*) AS n FROM {t}").collect()[0]["n"]
        status = "OK" if count > 0 else "EMPTY — raise your hand"
        print(f"{t:<40} {count:>14,}  {status}")
    except Exception as e:
        print(f"{t:<40} {'ERROR':>15}  {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 1 — Getting Started with Genie
# MAGIC **20 minutes**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 1: Open the AEMO NEM Operations Genie Space
# MAGIC
# MAGIC **In the Databricks left sidebar:**
# MAGIC ```
# MAGIC Left sidebar → Genie (sparkle/lightning icon) → click "AEMO NEM Operations"
# MAGIC ```
# MAGIC
# MAGIC If you cannot see "Genie" in the sidebar, click the grid icon at the very top of the sidebar to show all apps.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 2: The interface — five things to know
# MAGIC
# MAGIC | What | Where | How |
# MAGIC |------|-------|-----|
# MAGIC | **Ask a question** | Text box at the bottom | Type in plain English, press Enter |
# MAGIC | **See the SQL** | Click `{ }` below any answer | Verify what data Genie actually queried |
# MAGIC | **Download results** | Click the down-arrow on any result table | Saves a CSV to your computer |
# MAGIC | **Add to dashboard** | Click the chart icon on any result | Saves the tile to a Lakeview dashboard |
# MAGIC | **Share** | Click the share icon at the top right | Creates a link for colleagues |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 3: Your first question
# MAGIC
# MAGIC Type the following into the Genie chat box and press **Enter:**
# MAGIC
# MAGIC > *"What was the average spot price in each NEM region yesterday?"*
# MAGIC
# MAGIC You should see a table with one row per region (NSW1, VIC1, QLD1, SA1, TAS1) and an average RRP column in $/MWh. Now click **"Show SQL"** — you do not need to understand every line, just check it references `aemo.spot_prices` and filters to yesterday. That confirms Genie is looking at the right data.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 2 — Guided Task Cards
# MAGIC **60 minutes (10 minutes per task)**
# MAGIC
# MAGIC Each task has: a business scenario, the question to type, what to expect, a follow-up to try, and a verification SQL cell.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #f0f4ff; border-left: 5px solid #4361EE; padding: 20px 24px; border-radius: 6px;">
# MAGIC
# MAGIC ### Task 1 — Spot Prices
# MAGIC
# MAGIC **Scenario:** Your manager wants yesterday's price summary before the 8 AM morning report — averages and extremes for each region.
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC > *"What were the average, minimum, and maximum spot prices for each NEM region yesterday?"*
# MAGIC
# MAGIC You should see a table with five rows and three price columns (average, minimum, maximum RRP in $/MWh).
# MAGIC
# MAGIC **Follow-up to try:**
# MAGIC > *"Which region had the highest price volatility last week?"*
# MAGIC
# MAGIC Then run the SQL cell below and compare the numbers.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 1 — compare these numbers to what Genie told you.
spark.sql("""
    SELECT
        region_id,
        ROUND(AVG(rrp), 2)  AS avg_price_mwh,
        ROUND(MIN(rrp), 2)  AS min_price_mwh,
        ROUND(MAX(rrp), 2)  AS max_price_mwh,
        COUNT(*)            AS intervals
    FROM aemo.spot_prices
    WHERE DATE(settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
    GROUP BY region_id
    ORDER BY avg_price_mwh DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #fff8f0; border-left: 5px solid #F4A261; padding: 20px 24px; border-radius: 6px;">
# MAGIC
# MAGIC ### Task 2 — Generator Dispatch
# MAGIC
# MAGIC **Scenario:** A generating unit tripped in QLD during the afternoon peak. Your operations team needs to know which units were dispatching.
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC > *"Show me the top 10 generators by total dispatch in QLD1 yesterday"*
# MAGIC
# MAGIC You should see a ranked table showing station name, fuel type, and total MWh dispatched.
# MAGIC
# MAGIC **Follow-up to try:**
# MAGIC > *"Were there any generators in QLD1 that had dispatch below their minimum load level yesterday?"*
# MAGIC
# MAGIC Then run the SQL cell below and compare.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 2
spark.sql("""
    SELECT
        d.duid,
        g.station_name,
        g.fuel_type,
        ROUND(SUM(d.dispatch_mw), 1)  AS total_dispatch_mw,
        COUNT(*)                       AS dispatch_intervals
    FROM aemo.dispatch_intervals d
    LEFT JOIN aemo.generator_registration g USING (duid)
    WHERE DATE(d.settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
      AND d.region_id = 'QLD1'
    GROUP BY d.duid, g.station_name, g.fuel_type
    ORDER BY total_dispatch_mw DESC
    LIMIT 10
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #f0fff4; border-left: 5px solid #2A9D8F; padding: 20px 24px; border-radius: 6px;">
# MAGIC
# MAGIC ### Task 3 — Market Notices
# MAGIC
# MAGIC **Scenario:** Your reliability team does a weekly review of LOR (Lack of Reserve) declarations. You need a summary for the weekly report.
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC > *"List any LOR (lack of reserve) notices issued in the last 7 days"*
# MAGIC
# MAGIC You should see a table of LOR notices with region, reason, and date. If there are none, Genie will say the count is zero — that is a valid answer.
# MAGIC
# MAGIC **LOR severity levels:** LOR1 = reserve tightening, LOR2 = shortfall imminent, LOR3 = load shedding possible.
# MAGIC
# MAGIC **Follow-up to try:**
# MAGIC > *"Which NEM region has had the most LOR events so far this year?"*
# MAGIC
# MAGIC Then run the SQL cell below and compare.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 3
spark.sql("""
    SELECT
        notice_type,
        region_id,
        reason,
        effective_date
    FROM aemo.market_notices
    WHERE notice_type LIKE 'LOR%'
      AND effective_date >= CURRENT_DATE - INTERVAL 7 DAYS
    ORDER BY effective_date DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #fff0f0; border-left: 5px solid #E63946; padding: 20px 24px; border-radius: 6px;">
# MAGIC
# MAGIC ### Task 4 — Price Spike Investigation
# MAGIC
# MAGIC **Scenario:** The risk team flagged elevated prices last month. Before writing the incident brief, they need a precise list of when spot prices exceeded $1,000/MWh — region, interval, and duration.
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC > *"Were there any spot prices above $1000/MWh last month, and if so when and where did they occur?"*
# MAGIC
# MAGIC You should see a table of high-price events with region, date, time interval, and RRP value.
# MAGIC
# MAGIC **Follow-up to try:**
# MAGIC > *"For those high-price events, how long did prices stay above $300/MWh before returning to normal?"*
# MAGIC
# MAGIC If Genie struggles with the follow-up, break it into two questions: first get the spike events, then ask about duration for a specific region and date.
# MAGIC
# MAGIC Then run the SQL cell below and compare.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 4
spark.sql("""
    SELECT
        region_id,
        DATE(settlement_date)          AS spike_date,
        COUNT(*)                       AS spike_intervals,
        ROUND(MAX(rrp), 2)             AS peak_price_mwh,
        ROUND(AVG(rrp), 2)             AS avg_spike_price_mwh,
        MIN(settlement_date)           AS first_interval,
        MAX(settlement_date)           AS last_interval
    FROM aemo.spot_prices
    WHERE rrp > 1000
      AND settlement_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH)
      AND settlement_date <  DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY region_id, DATE(settlement_date)
    ORDER BY spike_date, peak_price_mwh DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #f5f0ff; border-left: 5px solid #7209B7; padding: 20px 24px; border-radius: 6px;">
# MAGIC
# MAGIC ### Task 5 — Settlement Summary
# MAGIC
# MAGIC **Scenario:** Finance needs settlement totals by participant for the most recent weekly run — largest net payers and receivers.
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC > *"What is the total settlement amount by participant for the most recent settlement run?"*
# MAGIC
# MAGIC You should see a table of participant IDs with total settlement amounts in AUD, sorted from largest to smallest.
# MAGIC
# MAGIC **Follow-up to try:**
# MAGIC > *"Which participants have pending or disputed settlement amounts in the last 4 weeks?"*
# MAGIC
# MAGIC Then run the SQL cell below and compare.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 5
spark.sql("""
    WITH latest_run AS (
        SELECT MAX(settlement_date) AS run_date FROM aemo.settlement_amounts
    )
    SELECT
        s.participant_id,
        ROUND(SUM(s.total_aud), 2)  AS total_settlement_aud,
        s.settlement_status,
        COUNT(*)                     AS line_items
    FROM aemo.settlement_amounts s
    INNER JOIN latest_run r ON s.settlement_date = r.run_date
    GROUP BY s.participant_id, s.settlement_status
    ORDER BY ABS(SUM(s.total_aud)) DESC
    LIMIT 20
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #f0faff; border-left: 5px solid #0077B6; padding: 20px 24px; border-radius: 6px;">
# MAGIC
# MAGIC ### Task 6 — Building Your Morning Dashboard
# MAGIC
# MAGIC **Scenario:** Your team checks NEM conditions every morning before the 8 AM stand-up. You want a single dashboard that shows the current state of the market at a glance.
# MAGIC
# MAGIC **Step 1 — Ask Genie for a market summary:**
# MAGIC > *"Give me a summary of today's NEM operations — spot prices by region, total dispatch by fuel type, and any active market notices"*
# MAGIC
# MAGIC Genie will return 2–3 result tiles. Each tile has a chart or table icon.
# MAGIC
# MAGIC **Step 2 — Add results to a dashboard:**
# MAGIC 1. On the spot price result, click the **chart icon** or **"Add to dashboard"**
# MAGIC 2. In the dialog, click **"Create new dashboard"**
# MAGIC 3. Name it: **NEM Daily Operations** → click **Add**
# MAGIC 4. Repeat for the dispatch and notices results
# MAGIC
# MAGIC **Step 3 — Open and share your dashboard:**
# MAGIC 1. Click **"Open dashboard"** in the confirmation, or go to **Dashboards** in the left sidebar
# MAGIC 2. Find "NEM Daily Operations" and open it
# MAGIC 3. Click **Share** (top right) → search for a colleague → set "Can view" → click **Share**
# MAGIC
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 3 — Your Own Questions
# MAGIC **20 minutes**
# MAGIC
# MAGIC Use Genie to ask anything related to NEM operations data that is relevant to your role. Below are patterns that work well and some starters to try.
# MAGIC
# MAGIC **Question patterns that work well:**
# MAGIC ```
# MAGIC "What was the [metric] for [region] in [time period]?"
# MAGIC "Compare [thing A] with [thing B] for [time period]"
# MAGIC "Show me the top/bottom [N] [things] by [metric]"
# MAGIC "How has [metric] changed over [time period]?"
# MAGIC "Were there any [events] in [region] last [period]?"
# MAGIC ```
# MAGIC
# MAGIC **20 starter questions — pick any that interest you:**
# MAGIC
# MAGIC 1. What was the demand-weighted average price in each region this week?
# MAGIC 2. Which trading intervals had negative spot prices in SA1 this month?
# MAGIC 3. How many times did the spot price exceed the Market Price Cap this year?
# MAGIC 4. What was the total renewable energy dispatched in the NEM last week?
# MAGIC 5. How does this month's average price in VIC1 compare to the same month last year?
# MAGIC 6. Which coal generators had the lowest capacity factors last month?
# MAGIC 7. Show me the average dispatch for wind farms in SA1 by hour of day.
# MAGIC 8. Which generators have been in scheduled outage this week?
# MAGIC 9. What is the total registered capacity of battery storage in the NEM?
# MAGIC 10. Which fuel type contributed the most to peak demand this month?
# MAGIC 11. List all AEMO market notices issued in the last 30 days.
# MAGIC 12. Were there any frequency events or system strength notices this week?
# MAGIC 13. What was the average interconnector flow between NSW1 and QLD1 this week?
# MAGIC 14. Were there any RERT activations this month?
# MAGIC 15. How many inter-regional trades occurred between VIC1 and SA1 last month?
# MAGIC 16. What is the total settlement value of the most recent four weekly runs?
# MAGIC 17. Which participants had settlement amounts over $10 million last month?
# MAGIC 18. How many settlement line items are currently in a disputed status?
# MAGIC 19. What is the trend in total settlement amounts over the last 12 weeks?
# MAGIC 20. Which region contributed the most to total settlement value last month?
# MAGIC
# MAGIC **When Genie does not have the answer:**
# MAGIC
# MAGIC | Situation | What to do |
# MAGIC |-----------|-----------|
# MAGIC | Complex multi-step question | Break into 2–3 simpler questions in sequence |
# MAGIC | Data Genie cannot access | Ask your data team to add the source |
# MAGIC | Predictions or forecasts | Genie reads historical data only — use AWEFS/MSIP |
# MAGIC | Near-real-time data | Data has a 30–60 minute lag — check AEMO NEMWEB for live feeds |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 4 — Wrap-Up and Next Steps
# MAGIC **20 minutes**
# MAGIC
# MAGIC ## What you have done today
# MAGIC - Connected to the AEMO Databricks workspace
# MAGIC - Navigated Genie and learned to verify answers using "Show SQL"
# MAGIC - Completed 6 guided tasks covering prices, dispatch, notices, and settlements
# MAGIC - Built and shared a live NEM Daily Operations dashboard
# MAGIC
# MAGIC ## How to keep using Genie after today
# MAGIC
# MAGIC **Access:** Genie is available 24/7. Log in at the same URL you used today. The "AEMO NEM Operations" Space is pinned in the Genie section of the left sidebar.
# MAGIC
# MAGIC **Your dashboard:** "NEM Daily Operations" is saved in your workspace and refreshes automatically each morning.
# MAGIC
# MAGIC ## Reporting a wrong answer
# MAGIC
# MAGIC If you see something that looks incorrect: click **"Show SQL"** to see what query ran, then click the **thumbs down** icon and add a note. This feedback goes directly to the data team who maintain the Space.
# MAGIC
# MAGIC Always verify numbers before including them in a report. "Show SQL" and the verification SQL cells in this notebook are your best tools.
# MAGIC
# MAGIC ## Requesting a Genie Space for your team
# MAGIC
# MAGIC 1. Write down 5–10 questions your team asks regularly
# MAGIC 2. Note which data sources or reports those answers currently come from
# MAGIC 3. Contact the AEMO Data Platform team — details below
# MAGIC
# MAGIC The team will assess whether the data is already in the platform and can configure a Space in 1–2 weeks.
# MAGIC
# MAGIC ## Contact
# MAGIC
# MAGIC | Need | Who to contact |
# MAGIC |------|---------------|
# MAGIC | Access issues or login problems | [TODO: AEMO IT Service Desk] |
# MAGIC | Wrong data or missing data | [TODO: AEMO Data Platform Team] |
# MAGIC | New Genie Space for your team | [TODO: AEMO Data Platform Team] |
# MAGIC | Training and enablement | [TODO: AEMO Training Coordinator] |
# MAGIC
# MAGIC **Session feedback:** [TODO: insert feedback form link] — 2 minutes, helps the data team prioritise which questions to add to the Genie Space.
