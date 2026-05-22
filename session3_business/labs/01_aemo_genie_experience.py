# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A4B 0%, #FF3621 100%); padding: 40px 32px 32px 32px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-size: 2.4em; font-weight: 700; margin: 0 0 8px 0;">⚡ Session 3: AEMO Genie Experience</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.9); font-size: 1.2em; margin: 0 0 20px 0;">Ask questions about NEM operations data in plain English</p>
# MAGIC   <table style="color: white; border-collapse: collapse; width: 100%;">
# MAGIC     <tr>
# MAGIC       <td style="padding: 6px 20px 6px 0; font-size: 0.95em;"><strong>⏱ Duration:</strong> 2 hours</td>
# MAGIC       <td style="padding: 6px 20px 6px 0; font-size: 0.95em;"><strong>👥 Audience:</strong> Business Users (30 participants)</td>
# MAGIC       <td style="padding: 6px 0 6px 0;    font-size: 0.95em;"><strong>💻 Coding required:</strong> None</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC </div>
# MAGIC
# MAGIC > **What you will learn today**
# MAGIC > - Navigate the AEMO NEM Operations Genie Space
# MAGIC > - Ask operational questions in plain English and get data-backed answers
# MAGIC > - Verify that answers are correct before sharing them
# MAGIC > - Build a simple live dashboard from a Genie conversation
# MAGIC > - Know what questions Genie handles well — and when to ask for analyst help

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Quick connection check
# MAGIC
# MAGIC Before we open Genie, let's confirm you are connected to the AEMO Databricks workspace.
# MAGIC
# MAGIC 1. Make sure the cluster shown at the top of this notebook says **"AEMO Workshops"** (green dot).
# MAGIC 2. Run the cell below — click the ▶ button or press **Shift + Enter**.
# MAGIC 3. You should see your email address printed. If you see an error, raise your hand.

# COMMAND ----------

import subprocess, os

# Display who is logged in
user = spark.sql("SELECT current_user() AS me").collect()[0]["me"]
print(f"✅  Connected as: {user}")
print(f"✅  Spark version: {spark.version}")
print(f"✅  You are ready to start the session.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Confirm the AEMO data is available
# MAGIC
# MAGIC Run the cell below to check the tables Genie will query on your behalf.
# MAGIC You do **not** need to understand the SQL — just confirm each table shows a row count above zero.

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
        status = "✅" if count > 0 else "⚠️  EMPTY"
        print(f"{t:<40} {count:>14,}  {status}")
    except Exception as e:
        print(f"{t:<40} {'ERROR':>15}  ❌  {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 1 — Getting Started with Genie
# MAGIC **Estimated time: 20 minutes | No coding required**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 1: Open the AEMO NEM Operations Genie Space
# MAGIC
# MAGIC **In the Databricks left sidebar, navigate to:**
# MAGIC
# MAGIC ```
# MAGIC Left sidebar  →  Genie  →  "AEMO NEM Operations"
# MAGIC ```
# MAGIC
# MAGIC > If you cannot see "Genie" in the sidebar, click the grid icon (⊞) at the very top of the sidebar to show all apps.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 2: Familiarise yourself with the interface
# MAGIC
# MAGIC When the Genie Space opens, you will see something like this:
# MAGIC
# MAGIC ```
# MAGIC ┌─── AEMO NEM Operations ──────────────────────────────────────────────┐
# MAGIC │  [💬 Chat]  [⚙️ Configure]                                            │
# MAGIC │  ────────────────────────────────────────────────────────────────    │
# MAGIC │                                                                       │
# MAGIC │              ⚡ Ask me anything about NEM operations                  │
# MAGIC │                                                                       │
# MAGIC │  ┌─────────────────────────────────────────────────────────────┐    │
# MAGIC │  │ What would you like to know?                       [Send ▶] │    │
# MAGIC │  └─────────────────────────────────────────────────────────────┘    │
# MAGIC │                                                                       │
# MAGIC │  Suggested questions:                                                 │
# MAGIC │  "What was the average spot price in VIC1 yesterday?"                │
# MAGIC │  "Which generators dispatched the most in NSW1 last week?"           │
# MAGIC │  "Are there any active LOR events?"                                  │
# MAGIC └──────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 3: Interface walkthrough — the six things you need to know
# MAGIC
# MAGIC | Feature | Where to find it | What it does |
# MAGIC |---|---|---|
# MAGIC | **Ask a question** | The text box at the bottom of the chat | Type your question in plain English and press Enter or click Send |
# MAGIC | **Show SQL** | Click the `{ }` icon below any Genie answer | See the exact SQL query Genie wrote — useful for verifying the answer |
# MAGIC | **Verify the answer** | Click "Show SQL" then "Run SQL" | Runs the SQL directly so you can confirm the numbers yourself |
# MAGIC | **Download results** | Click the ⬇ icon on any result table | Downloads a CSV of the answer to your computer |
# MAGIC | **Add to dashboard** | Click the chart icon (📊) on any result | Saves the result as a tile on a Lakeview dashboard |
# MAGIC | **Share conversation** | Click the share icon (🔗) at the top right | Creates a link your colleagues can open to see the same conversation |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 4: Your first question
# MAGIC
# MAGIC Type the following into the Genie chat box and press **Enter**:
# MAGIC
# MAGIC > *"What was the average spot price in each NEM region yesterday?"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC - A table with one row per region (NSW1, VIC1, QLD1, SA1, TAS1)
# MAGIC - An "Average RRP" column in $/MWh
# MAGIC - Genie may also render this as a bar chart automatically
# MAGIC
# MAGIC **Now click "Show SQL"** and look at the query Genie generated. You do not need to understand every line — just check that it references `aemo.spot_prices` and filters to yesterday's date. That confirms it is looking at the right data.
# MAGIC
# MAGIC > **Tip:** If Genie gives you an answer you are unsure about, "Show SQL" is always your first step to verifying it.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 2 — Guided Task Cards
# MAGIC **Estimated time: 60 minutes (10 minutes per task) | No coding required**
# MAGIC
# MAGIC Work through each task at your own pace. Each task has:
# MAGIC - A **business scenario** — the reason you are looking at this data
# MAGIC - The **question to type** in Genie (copy it exactly, then experiment)
# MAGIC - **What you should see** in the response
# MAGIC - A **follow-up question** to try once the first one works
# MAGIC - A **verification SQL** cell you can run to double-check Genie's answer

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #f0f4ff; border-left: 5px solid #4361EE; padding: 20px 24px; border-radius: 6px; margin-bottom: 8px;">
# MAGIC
# MAGIC ### Task 1 — Spot Prices ⚡
# MAGIC **Time: 10 minutes**
# MAGIC
# MAGIC **Business scenario**
# MAGIC Your manager has asked for yesterday's price summary in time for the 8 AM morning report. They want averages and extremes for each region so the team can see at a glance whether prices were normal or unusual.
# MAGIC
# MAGIC **Step 1 — Type this into Genie:**
# MAGIC > *"What were the average, minimum, and maximum spot prices for each NEM region yesterday?"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC A table with five rows (one per region) and three price columns — average, minimum, and maximum RRP in $/MWh. Genie may also offer a bar chart view.
# MAGIC
# MAGIC **Step 2 — Follow-up question to try:**
# MAGIC > *"Which region had the highest price volatility last week?"*
# MAGIC
# MAGIC Genie should calculate standard deviation or price range by region and rank them.
# MAGIC
# MAGIC **Step 3 — Verify Genie's answer** using the SQL cell below.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 1 — run this and compare to what Genie told you.
# The numbers should match (or be very close — Genie rounds to 2 decimal places).

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
# MAGIC <div style="background: #fff8f0; border-left: 5px solid #F4A261; padding: 20px 24px; border-radius: 6px; margin-bottom: 8px;">
# MAGIC
# MAGIC ### Task 2 — Generator Dispatch 🏭
# MAGIC **Time: 10 minutes**
# MAGIC
# MAGIC **Business scenario**
# MAGIC There was a report of a major generating unit tripping in QLD during the afternoon peak. Your operations team needs to know which units were dispatching and whether any gaps appeared in the dispatch stack.
# MAGIC
# MAGIC **Step 1 — Type this into Genie:**
# MAGIC > *"Show me the top 10 generators by total dispatch in QLD1 yesterday"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC A ranked table showing DUID, station name, fuel type, and total MWh dispatched. The top result is usually a coal or gas unit.
# MAGIC
# MAGIC **Step 2 — Follow-up question to try:**
# MAGIC > *"Were there any generators in QLD1 that had dispatch below their minimum load level yesterday?"*
# MAGIC
# MAGIC This surfaces units that may have been operating in an unusual mode or that tripped and were brought back online at minimum output.
# MAGIC
# MAGIC **Step 3 — Verify Genie's answer** using the SQL cell below.
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
# MAGIC <div style="background: #f0fff4; border-left: 5px solid #2A9D8F; padding: 20px 24px; border-radius: 6px; margin-bottom: 8px;">
# MAGIC
# MAGIC ### Task 3 — Market Notices 📢
# MAGIC **Time: 10 minutes**
# MAGIC
# MAGIC **Business scenario**
# MAGIC Your reliability team does a weekly review of LOR (Lack of Reserve) declarations. You need to pull together a summary of any LOR notices issued in the last 7 days to include in the weekly report.
# MAGIC
# MAGIC **Step 1 — Type this into Genie:**
# MAGIC > *"List any LOR (lack of reserve) notices issued in the last 7 days"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC A table of market notices filtered to LOR1, LOR2, and LOR3 notice types, showing the region, reason text, and effective date/time. If there are no LOR notices, Genie should tell you the count is zero — that is a valid answer.
# MAGIC
# MAGIC **Step 2 — Follow-up question to try:**
# MAGIC > *"Which NEM region has had the most LOR events so far this year?"*
# MAGIC
# MAGIC > **Tip — LOR severity levels:**
# MAGIC > - **LOR1** — First warning, reserve margin tightening
# MAGIC > - **LOR2** — Shortfall is imminent, emergency responses may activate
# MAGIC > - **LOR3** — Critical shortage, load shedding is possible
# MAGIC
# MAGIC **Step 3 — Verify Genie's answer** using the SQL cell below.
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
# MAGIC <div style="background: #fff0f0; border-left: 5px solid #E63946; padding: 20px 24px; border-radius: 6px; margin-bottom: 8px;">
# MAGIC
# MAGIC ### Task 4 — Price Spike Investigation 🔍
# MAGIC **Time: 10 minutes**
# MAGIC
# MAGIC **Business scenario**
# MAGIC The risk team has flagged elevated prices last month. Before they can write the incident brief, they need a precise list of when spot prices exceeded $1,000/MWh — the region, the exact intervals, and how long each spike lasted.
# MAGIC
# MAGIC **Step 1 — Type this into Genie:**
# MAGIC > *"Were there any spot prices above $1000/MWh last month, and if so when and where did they occur?"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC A table of high-price events showing region, date, time interval, and the RRP value. If Genie returns a large number of rows, ask it to summarise by region and day.
# MAGIC
# MAGIC **Step 2 — Follow-up question to try:**
# MAGIC > *"For those high-price events, how long did prices stay above $300/MWh before returning to normal?"*
# MAGIC
# MAGIC This tests Genie's ability to calculate event duration from sequential interval data.
# MAGIC
# MAGIC > **Note:** This is a more complex query. If Genie struggles, try breaking it into two questions: first get the spike events, then ask about duration for a specific region and date.
# MAGIC
# MAGIC **Step 3 — Verify Genie's answer** using the SQL cell below.
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
# MAGIC <div style="background: #f5f0ff; border-left: 5px solid #7209B7; padding: 20px 24px; border-radius: 6px; margin-bottom: 8px;">
# MAGIC
# MAGIC ### Task 5 — Settlement Summary 💰
# MAGIC **Time: 10 minutes**
# MAGIC
# MAGIC **Business scenario**
# MAGIC Finance needs the settlement totals by participant for the most recent weekly settlement run. They want to know who the largest net payers and net receivers are, and whether any amounts are still in dispute or pending.
# MAGIC
# MAGIC **Step 1 — Type this into Genie:**
# MAGIC > *"What is the total settlement amount by participant for the most recent settlement run?"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC A table of participant IDs with their total settlement amounts (in AUD), sorted from largest to smallest. Genie should also tell you the settlement run date.
# MAGIC
# MAGIC **Step 2 — Follow-up question to try:**
# MAGIC > *"Which participants have pending or disputed settlement amounts in the last 4 weeks?"*
# MAGIC
# MAGIC **Step 3 — Verify Genie's answer** using the SQL cell below.
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Verification for Task 5
# Find the most recent settlement run date first, then pull totals
spark.sql("""
    WITH latest_run AS (
        SELECT MAX(settlement_date) AS run_date
        FROM aemo.settlement_amounts
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
# MAGIC <div style="background: #f0faff; border-left: 5px solid #0077B6; padding: 20px 24px; border-radius: 6px; margin-bottom: 8px;">
# MAGIC
# MAGIC ### Task 6 — Building Your Morning Dashboard 📊
# MAGIC **Time: 10 minutes**
# MAGIC
# MAGIC **Business scenario**
# MAGIC Your team checks NEM conditions every morning before the 8 AM stand-up. Instead of running individual questions each day, you want a single dashboard that shows the current state of the market at a glance.
# MAGIC
# MAGIC **Step 1 — Ask Genie to generate a market summary:**
# MAGIC > *"Give me a summary of today's NEM operations — spot prices by region, total dispatch by fuel type, and any active market notices"*
# MAGIC
# MAGIC **What you should see:**
# MAGIC Genie will return 2–3 result tiles covering prices, dispatch, and notices. Each tile will have a small chart or table icon.
# MAGIC
# MAGIC **Step 2 — Add results to a dashboard:**
# MAGIC 1. On the spot price result, click the **chart icon (📊)** or the **"Add to dashboard"** button
# MAGIC 2. In the dialog that appears, click **"Create new dashboard"**
# MAGIC 3. Name it: **NEM Daily Operations**
# MAGIC 4. Click **Add**
# MAGIC 5. Repeat for the dispatch result and the notices result
# MAGIC
# MAGIC **Step 3 — Open and set your dashboard as home:**
# MAGIC 1. Click **"Open dashboard"** in the confirmation toast, or navigate to **Dashboards** in the left sidebar
# MAGIC 2. Find "NEM Daily Operations" and open it
# MAGIC 3. Click the **⋮ (three-dot menu)** at the top right of the dashboard
# MAGIC 4. Select **"Set as home dashboard"**
# MAGIC
# MAGIC > **What this means:** The next time a colleague opens Databricks, this dashboard will be the first thing they see.
# MAGIC
# MAGIC **Step 4 — Share your dashboard:**
# MAGIC 1. Click **Share** (top right of the dashboard)
# MAGIC 2. Search for a colleague's name
# MAGIC 3. Set their permission to **"Can view"**
# MAGIC 4. Click **Share**
# MAGIC
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 3 — Your Own Questions
# MAGIC **Estimated time: 20 minutes | No coding required**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC This is open question time. Use the Genie chat to ask anything related to NEM operations data that is relevant to your role.
# MAGIC
# MAGIC If you are not sure where to start, use the question starters and library below.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Question patterns that work well in Genie
# MAGIC
# MAGIC ```
# MAGIC Good question patterns for Genie:
# MAGIC
# MAGIC ✅  "What was the [metric] for [region] in [time period]?"
# MAGIC       e.g. "What was the average spot price for SA1 in the last 30 days?"
# MAGIC
# MAGIC ✅  "Compare [thing A] with [thing B] for [time period]"
# MAGIC       e.g. "Compare wind and solar dispatch in VIC1 this month"
# MAGIC
# MAGIC ✅  "Show me the top/bottom [N] [things] by [metric]"
# MAGIC       e.g. "Show me the bottom 5 generators by capacity factor last quarter"
# MAGIC
# MAGIC ✅  "How has [metric] changed over [time period]?"
# MAGIC       e.g. "How has battery storage dispatch changed over the last 12 months?"
# MAGIC
# MAGIC ✅  "Were there any [events/anomalies] in [region] last [period]?"
# MAGIC       e.g. "Were there any price separations between NSW1 and VIC1 last week?"
# MAGIC
# MAGIC ✅  "What is the [metric] trend for [region/unit] this [period]?"
# MAGIC       e.g. "What is the evening demand trend for QLD1 this month?"
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Questions that Genie handles less well — and what to do instead
# MAGIC
# MAGIC | Type of question | Why it's harder for Genie | Better approach |
# MAGIC |---|---|---|
# MAGIC | Very complex multi-step analysis | Genie answers one question at a time | Break into 2–3 simpler questions in sequence |
# MAGIC | Data Genie does not have access to | Genie can only query the tables in this Space | Ask your data team to add the source |
# MAGIC | Predictions or forecasts | Genie reads historical data only | Use the AEMO AWEFS/MSIP forecasting tools |
# MAGIC | Near-real-time data | Data typically has a 30–60 minute lag | Check the AEMO NEMWEB portal for live feeds |
# MAGIC | Questions about individual customer contracts | Settlement data is aggregate, not contract-level | Contact the market operations team |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 20 starter questions to try right now
# MAGIC
# MAGIC Pick any that interest you and try them in Genie. Experiment with changing the region, time period, or metric.
# MAGIC
# MAGIC **Market conditions**
# MAGIC 1. "What was the demand-weighted average price in each region this week?"
# MAGIC 2. "Which trading intervals had negative spot prices in SA1 this month?"
# MAGIC 3. "How many times did the spot price exceed the Market Price Cap this year?"
# MAGIC 4. "What was the total renewable energy dispatched in the NEM last week?"
# MAGIC 5. "How does this month's average price in VIC1 compare to the same month last year?"
# MAGIC
# MAGIC **Generator performance**
# MAGIC 6. "Which coal generators had the lowest capacity factors last month?"
# MAGIC 7. "Show me the average dispatch for wind farms in SA1 by hour of day"
# MAGIC 8. "Which generators have been in scheduled outage this week?"
# MAGIC 9. "What is the total registered capacity of battery storage in the NEM?"
# MAGIC 10. "Which fuel type contributed the most to peak demand this month?"
# MAGIC
# MAGIC **Grid events and notices**
# MAGIC 11. "List all AEMO market notices issued in the last 30 days"
# MAGIC 12. "Were there any frequency events or system strength notices this week?"
# MAGIC 13. "How many inter-regional trades occurred between VIC1 and SA1 last month?"
# MAGIC 14. "What was the average interconnector flow between NSW1 and QLD1 this week?"
# MAGIC 15. "Were there any directions or RERT activations this month?"
# MAGIC
# MAGIC **Settlement and finance**
# MAGIC 16. "What is the total settlement value of the most recent four weekly runs?"
# MAGIC 17. "Which participants had settlement amounts over $10 million last month?"
# MAGIC 18. "How many settlement line items are currently in a disputed status?"
# MAGIC 19. "What is the trend in total settlement amounts over the last 12 weeks?"
# MAGIC 20. "Which region contributed the most to total settlement value last month?"

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Part 4 — Wrap-Up and Next Steps
# MAGIC **Estimated time: 20 minutes**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What you have done today
# MAGIC
# MAGIC - Connected to the AEMO Databricks workspace
# MAGIC - Navigated the Genie interface and learned to verify answers using "Show SQL"
# MAGIC - Completed 6 guided operational tasks covering prices, dispatch, notices, and settlements
# MAGIC - Built and shared a live NEM Daily Operations dashboard
# MAGIC - Explored your own operational questions in plain English
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## How to keep using Genie after this session
# MAGIC
# MAGIC **Access:** Genie is available 24/7. Log in at the same URL you used today. The "AEMO NEM Operations" Space is pinned in the Genie section of the left sidebar.
# MAGIC
# MAGIC **Your dashboard:** The "NEM Daily Operations" dashboard you built is saved in your workspace. It will refresh automatically each morning.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Requesting a Genie Space for your own team
# MAGIC
# MAGIC If your team has a specific operational focus (e.g. settlements, retail, network, generation) and you want a Genie Space tailored to your data:
# MAGIC
# MAGIC 1. Write down 5–10 questions your team asks regularly
# MAGIC 2. Note which data sources or reports those answers currently come from
# MAGIC 3. Contact the AEMO Data Platform team — details below
# MAGIC 4. The team will assess whether the data is already in Unity Catalog and can configure a Space in 1–2 weeks
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Suggesting new data sources
# MAGIC
# MAGIC If you ask Genie a question and it says "I don't have access to that data," that data might not yet be in the platform. To request it:
# MAGIC
# MAGIC 1. Note the system or report the data currently lives in
# MAGIC 2. Estimate how often you need it and in what format (daily, weekly, real-time)
# MAGIC 3. Submit a data ingestion request via [TODO: insert AEMO internal request portal link]
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Reporting a wrong answer
# MAGIC
# MAGIC Genie can occasionally produce an incorrect result, especially for unusual time ranges or complex multi-part questions. If you see something that looks wrong:
# MAGIC
# MAGIC 1. Click **"Show SQL"** on the answer to see what query was run
# MAGIC 2. If the SQL looks incorrect, click the **thumbs down (👎)** icon on the response
# MAGIC 3. Add a note describing what you expected to see
# MAGIC 4. This feedback goes directly to the data team who maintain the Space
# MAGIC
# MAGIC > **Important:** Always verify numbers before including them in a report or sending to stakeholders. "Show SQL" and the verification SQL cells in this notebook are your best tools.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Contact
# MAGIC
# MAGIC | Need | Who to contact |
# MAGIC |---|---|
# MAGIC | Access issues or login problems | [TODO: AEMO IT Service Desk] |
# MAGIC | Wrong data or missing data | [TODO: AEMO Data Platform Team] |
# MAGIC | New Genie Space for your team | [TODO: AEMO Data Platform Team] |
# MAGIC | Training and enablement | [TODO: AEMO Training Coordinator] |
# MAGIC | Escalate a data quality issue | [TODO: AEMO Data Governance Team] |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Session feedback
# MAGIC
# MAGIC Please take 2 minutes to complete the session feedback form:
# MAGIC **[TODO: insert feedback form link]**
# MAGIC
# MAGIC Your feedback directly improves future sessions and helps the data team prioritise which questions to add to the Genie Space.
