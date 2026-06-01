# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 02: Benchmarks, Golden Queries & Instructions</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 35 minutes |
# MAGIC | **Covers** | Slides 25, 28–29 — Benchmarks first, then Example SQL, then Text |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key rule: Benchmarks before instructions (Slide 25)
# MAGIC
# MAGIC > *"Create a set of questions that you expect users to ask as benchmarks. Create 'correct SQL' for each. Run benchmarks as you iterate on your instructions."*
# MAGIC
# MAGIC **Why benchmarks come first:**
# MAGIC - You need a baseline before you start changing things
# MAGIC - Benchmarks are your regression test — they tell you if a change made things better or worse
# MAGIC - Target: >80% Good before sharing with business users

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID")
SPACE_ID = dbutils.widgets.get("genie_space_id")
CATALOG  = "workshop_au"
SCHEMA   = "aemo"
HOST     = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN    = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS  = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
print(f"Space: {SPACE_ID or 'not set'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Add Benchmarks (Slide 25 + Slide 36)
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Benchmarks → + Add benchmark**
# MAGIC
# MAGIC Add 2 phrasings of each question type (Slide 36 — AEMO benchmark question bank):
# MAGIC
# MAGIC ### Type 1: Spot prices by region
# MAGIC | Phrasing | Expected SQL |
# MAGIC |---|---|
# MAGIC | "What was the average spot price in NSW1 yesterday?" | `SELECT region_id, ROUND(AVG(rrp),2) AS avg_price FROM workshop_au.aemo.spot_prices WHERE region_id='NSW1' AND DATE(settlement_date) = CURRENT_DATE - 1` |
# MAGIC | "Show me yesterday's regional reference price for NSW" | Same |
# MAGIC
# MAGIC ### Type 2: Price spikes
# MAGIC | Phrasing | Expected SQL |
# MAGIC |---|---|
# MAGIC | "How many 5-minute intervals exceeded $300/MWh in VIC last week?" | `SELECT COUNT(*) FROM workshop_au.aemo.spot_prices WHERE region_id='VIC1' AND rrp > 300 AND settlement_date >= CURRENT_DATE - 7` |
# MAGIC | "Show price spike events above $1000/MWh this month by region" | `SELECT region_id, COUNT(*) as spikes FROM ... WHERE rrp > 1000 AND ...` |
# MAGIC
# MAGIC ### Type 3: Generator dispatch
# MAGIC | Phrasing | Expected SQL |
# MAGIC |---|---|
# MAGIC | "Which generators dispatched the most MW in QLD last week?" | `SELECT d.duid, g.station_name, ROUND(SUM(d.dispatch_mw)/12,1) AS mwh FROM dispatch_intervals d LEFT JOIN generator_registration g ON d.duid=g.duid WHERE d.region_id='QLD1' AND ...` |
# MAGIC | "Show top 10 generators by total dispatch in South Australia this month" | Similar with SA1 |
# MAGIC
# MAGIC ### Type 4: Fuel mix
# MAGIC | Phrasing | Expected SQL |
# MAGIC |---|---|
# MAGIC | "What was the fuel mix for dispatch in SA today?" | `SELECT fuel_type, ROUND(SUM(dispatch_mw)/12,1) AS mwh FROM dispatch_intervals WHERE region_id='SA1' AND DATE(settlement_date)=CURRENT_DATE GROUP BY fuel_type` |
# MAGIC | "Show renewable generation as a % of total dispatch this quarter" | CASE WHEN fuel_type IN ('solar','wind') ... |
# MAGIC
# MAGIC ### Type 5: LOR / market notices
# MAGIC | Phrasing | Expected SQL |
# MAGIC |---|---|
# MAGIC | "Were there any LOR events in the last fortnight?" | `SELECT * FROM market_notices WHERE notice_type LIKE 'LOR%' AND issue_time >= CURRENT_TIMESTAMP - INTERVAL 14 DAYS` |
# MAGIC | "List all lack-of-reserve notices from the past 30 days" | Same with 30 days |
# MAGIC
# MAGIC ⚠️ **Run benchmarks BEFORE adding any golden queries.** This gives you a true baseline.

# COMMAND ----------

# Helper: SQL for each benchmark type to paste as expected SQL
benchmarks = {
    "avg_spot_nsw1_yesterday": """
SELECT region_id, ROUND(AVG(rrp), 2) AS avg_price_mwh
FROM workshop_au.aemo.spot_prices
WHERE region_id = 'NSW1'
  AND DATE(settlement_date) = CURRENT_DATE - 1
GROUP BY region_id""",

    "price_spikes_vic_last_week": """
SELECT COUNT(*) AS spike_count
FROM workshop_au.aemo.spot_prices
WHERE region_id = 'VIC1'
  AND rrp > 300
  AND settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS""",

    "top_generators_qld_last_week": """
SELECT d.duid, g.station_name, g.fuel_type,
       ROUND(SUM(d.dispatch_mw) / 12, 1) AS total_mwh
FROM workshop_au.aemo.dispatch_intervals d
LEFT JOIN workshop_au.aemo.generator_registration g ON d.duid = g.duid
WHERE d.region_id = 'QLD1'
  AND d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY d.duid, g.station_name, g.fuel_type
ORDER BY total_mwh DESC
LIMIT 10""",

    "fuel_mix_sa_today": """
SELECT fuel_type,
       ROUND(SUM(dispatch_mw) / 12, 1) AS total_mwh
FROM workshop_au.aemo.dispatch_intervals
WHERE region_id = 'SA1'
  AND DATE(settlement_date) = CURRENT_DATE
GROUP BY fuel_type
ORDER BY total_mwh DESC""",

    "lor_events_last_14_days": """
SELECT notice_type, issue_time, region_id,
       SUBSTRING(reason, 1, 200) AS summary
FROM workshop_au.aemo.market_notices
WHERE notice_type LIKE 'LOR%'
  AND issue_time >= CURRENT_TIMESTAMP - INTERVAL 14 DAYS
ORDER BY issue_time DESC"""
}

print("Copy these SQL statements as expected answers for your benchmark questions:\n")
for name, sql in benchmarks.items():
    print(f"--- {name} ---")
    print(sql.strip())
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Add Golden Queries / Example SQL (Slide 28)
# MAGIC
# MAGIC > *"After UC metadata and Knowledge Store, Example SQL is your next best option. Leverage parameterised example SQL wherever possible. The question title will have more impact on Genie's behaviour than Usage Guidance — include the most common phrasing as the title."*
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Instructions → SQL Queries → + Add**
# MAGIC
# MAGIC Add these 5 parameterised golden queries:

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 1 — Average spot price by region
# MAGIC **Title:** `What was the average spot price by region for :date_period?`
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     ROUND(AVG(rrp), 2)  AS avg_price_mwh,
# MAGIC     ROUND(MIN(rrp), 2)  AS min_price_mwh,
# MAGIC     ROUND(MAX(rrp), 2)  AS max_price_mwh,
# MAGIC     COUNT(*)            AS interval_count
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE DATE(settlement_date) = :date_period
# MAGIC GROUP BY region_id
# MAGIC ORDER BY avg_price_mwh DESC
# MAGIC ```
# MAGIC **Parameters:** date_period (Date) — e.g. yesterday, last Monday
# MAGIC **Usage guidance:** Use when asking about price levels or averages for a specific day

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 2 — Price spike events
# MAGIC **Title:** `Were there any price spikes above $:threshold per MWh in :region last month?`
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     DATE(settlement_date)  AS spike_date,
# MAGIC     settlement_date        AS interval_time,
# MAGIC     ROUND(rrp, 2)          AS price_mwh
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE region_id = :region
# MAGIC   AND rrp > :threshold
# MAGIC   AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
# MAGIC ORDER BY rrp DESC
# MAGIC ```
# MAGIC **Parameters:** region (String — NEM region e.g. VIC1), threshold (Decimal — default 300)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 3 — Top generators by dispatch
# MAGIC **Title:** `Which generators dispatched the most in :region last week?`
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     d.duid,
# MAGIC     g.station_name,
# MAGIC     g.fuel_type,
# MAGIC     ROUND(SUM(d.dispatch_mw) / 12, 1)  AS total_mwh,
# MAGIC     ROUND(AVG(d.dispatch_mw), 1)        AS avg_dispatch_mw
# MAGIC FROM workshop_au.aemo.dispatch_intervals d
# MAGIC LEFT JOIN workshop_au.aemo.generator_registration g ON d.duid = g.duid
# MAGIC WHERE d.region_id = :region
# MAGIC   AND d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
# MAGIC GROUP BY d.duid, g.station_name, g.fuel_type
# MAGIC ORDER BY total_mwh DESC
# MAGIC LIMIT 15
# MAGIC ```
# MAGIC **Parameters:** region (String — e.g. QLD1, SA1)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 4 — Fuel mix by region
# MAGIC **Title:** `What was the fuel mix for dispatch in :region for :period?`
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     CASE
# MAGIC         WHEN fuel_type IN ('solar', 'wind')   THEN 'Renewable'
# MAGIC         WHEN fuel_type IN ('coal', 'gas')     THEN 'Fossil Fuel'
# MAGIC         ELSE 'Other'
# MAGIC     END                                 AS generation_type,
# MAGIC     fuel_type,
# MAGIC     ROUND(SUM(dispatch_mw) / 12, 0)     AS total_mwh
# MAGIC FROM workshop_au.aemo.dispatch_intervals
# MAGIC WHERE region_id = :region
# MAGIC   AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
# MAGIC GROUP BY generation_type, fuel_type
# MAGIC ORDER BY total_mwh DESC
# MAGIC ```
# MAGIC **Parameters:** region (String), period (String — for display only)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Query 5 — LOR and market notices
# MAGIC **Title:** `Were there any LOR notices in the last :days days?`
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     notice_type,
# MAGIC     issue_time,
# MAGIC     effective_date,
# MAGIC     region_id,
# MAGIC     SUBSTRING(reason, 1, 250) AS summary
# MAGIC FROM workshop_au.aemo.market_notices
# MAGIC WHERE notice_type LIKE 'LOR%'
# MAGIC   AND issue_time >= CURRENT_TIMESTAMP - INTERVAL :days DAYS
# MAGIC ORDER BY issue_time DESC
# MAGIC ```
# MAGIC **Parameters:** days (Integer — default 14)
# MAGIC **Usage guidance:** Use when asking about lack-of-reserve events, LOR1/LOR2/LOR3 events, reserve warnings

# COMMAND ----------

# Validate all 5 golden query SQLs work against actual data
import pyspark.sql.functions as F

tests = {
    "avg_prices": f"SELECT region_id, ROUND(AVG(rrp),2) AS avg FROM {CATALOG}.{SCHEMA}.spot_prices WHERE DATE(settlement_date) = CURRENT_DATE - 1 GROUP BY region_id ORDER BY avg DESC",
    "price_spikes": f"SELECT COUNT(*) AS spikes FROM {CATALOG}.{SCHEMA}.spot_prices WHERE rrp > 300 AND settlement_date >= CURRENT_DATE - 7",
    "top_generators": f"SELECT d.duid, g.station_name, ROUND(SUM(d.dispatch_mw)/12,1) AS mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals d LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid=g.duid WHERE d.settlement_date>=CURRENT_DATE-7 GROUP BY d.duid,g.station_name ORDER BY mwh DESC LIMIT 5",
    "fuel_mix": f"SELECT fuel_type, ROUND(SUM(dispatch_mw)/12,0) AS mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals WHERE settlement_date>=CURRENT_DATE-30 GROUP BY fuel_type ORDER BY mwh DESC",
    "lor_events": f"SELECT notice_type, COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.market_notices WHERE notice_type LIKE 'LOR%' AND issue_time>=CURRENT_TIMESTAMP-INTERVAL 30 DAYS GROUP BY notice_type"
}

for name, sql in tests.items():
    try:
        count = spark.sql(sql).count()
        print(f"✅ {name}: {count} rows")
    except Exception as e:
        print(f"❌ {name}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Text Instructions — last resort only (Slide 29)
# MAGIC
# MAGIC > *"General text instructions are the last option — if something could be expressed as table metadata or Example SQL, it should be. There is no filtering on general text instructions — they occupy a lot of context window."*
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Instructions → Text → + Add instruction**
# MAGIC
# MAGIC **✅ Valid text instructions (universal rules):**
# MAGIC
# MAGIC Add these 4 — and no more:
# MAGIC 1. "Always express prices in $/MWh with 2 decimal places."
# MAGIC 2. "Region codes must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix. Never use NSW, VIC, QLD, SA, or TAS without the suffix."
# MAGIC 3. "LOR1 = first reserve watch warning. LOR2 = reserve shortfall is threatened. LOR3 = imminent critical shortage."
# MAGIC 4. "When asked about 'today' with no data available, say so and suggest using yesterday instead."
# MAGIC
# MAGIC **❌ Anti-patterns — do NOT put these in text instructions:**
# MAGIC - "Average spot price means the average of the rrp column" → use a golden query or SQL expression instead
# MAGIC - "Join dispatch_intervals to generator_registration using duid" → use Join configuration instead
# MAGIC - "LOR notices have notice_type LOR1, LOR2, or LOR3" → use entity matching instead

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 02 Checkpoint
# MAGIC
# MAGIC - [ ] 10 benchmark questions added (5 types × 2 phrasings), benchmarks RUN to get baseline
# MAGIC - [ ] 5 golden queries added with parameters and accurate titles
# MAGIC - [ ] 4 (and only 4) text instructions added
# MAGIC - [ ] **Baseline benchmark score noted** — you need this to measure improvement in Lab 03
# MAGIC
# MAGIC **→ Next: Lab 03 — Run Benchmarks, Monitor & Iterate**

