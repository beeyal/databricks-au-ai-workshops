# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', Arial, sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 02: The Instruction Hierarchy</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0;">SQL Expressions → Golden Queries → Joins → Text Instructions (use in that order)</p>
# MAGIC   <p style="color: rgba(255,255,255,0.7); font-size: 0.95em; margin: 8px 0 0 0;">Session 2 · AEMO NEM Operations · 35 minutes</p>
# MAGIC </div>
# MAGIC <div style="background: #f7f8fa; border-left: 4px solid #FF3621; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 0;">
# MAGIC   <b>What this lab teaches:</b> Genie does not treat all instructions equally. There is a strict priority order that determines how it interprets every question. Master this stack and your Space will give accurate, consistent answers without manual debugging.<br><br>
# MAGIC   <b>How this lab works:</b> Each section is UI-first — you configure your Genie Space via the Configure tab, then run a code cell here to verify the underlying SQL logic works. Code cells are cross-checks, not the primary workflow.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Priority Stack — Read This First
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────────────────────────────┐
# MAGIC │                    GENIE INSTRUCTION PRIORITY STACK                             │
# MAGIC │                                                                                 │
# MAGIC │  ① SQL Expressions (Measures / Filters / Fields)          ← MOST RELIABLE      │
# MAGIC │     Compiled at query time. Genie uses these for every matching question.       │
# MAGIC │     Best for: KPIs, standard aggregations, common filters                      │
# MAGIC │                          │                                                      │
# MAGIC │                          ▼                                                      │
# MAGIC │  ② Golden Queries (Example SQL)                           ← COMPLEX PATTERNS   │
# MAGIC │     Genie checks golden query titles before generating SQL.                     │
# MAGIC │     A title match → pre-written SQL runs directly → shown as "Trusted".        │
# MAGIC │     Best for: multi-table joins, complex CASE logic, templated reports          │
# MAGIC │                          │                                                      │
# MAGIC │                          ▼                                                      │
# MAGIC │  ③ Join Configuration                                     ← STRUCTURAL RULES   │
# MAGIC │     Explicit join conditions between tables.                                    │
# MAGIC │     Without these, Genie may guess wrong join keys or refuse to join.          │
# MAGIC │     Best for: FK relationships, bridge tables, canonical join paths             │
# MAGIC │                          │                                                      │
# MAGIC │                          ▼                                                      │
# MAGIC │  ④ Text Instructions                                      ← LAST RESORT        │
# MAGIC │     Natural language rules applied broadly.                                     │
# MAGIC │     High maintenance, easy to contradict. Use sparingly.                       │
# MAGIC │     Best for: output formatting, unit conventions, terminology fallbacks        │
# MAGIC └─────────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Why this order matters:** If you put a KPI definition in Text Instructions instead of a SQL Expression,
# MAGIC Genie will sometimes interpret it differently on different questions. SQL Expressions are compiled —
# MAGIC they produce the same result every time. Text instructions are interpreted — they can drift.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",  "Catalog")
dbutils.widgets.text("schema_aemo", "aemo",         "Schema")
dbutils.widgets.text("space_id",    "",             "Genie Space ID (from Lab 01)")

# COMMAND ----------

CATALOG  = dbutils.widgets.get("catalog")
SCHEMA   = dbutils.widgets.get("schema_aemo")
SPACE_ID = dbutils.widgets.get("space_id")

if not SPACE_ID:
    try:
        SPACE_ID = spark.conf.get("workshop.genie.space_id")
        print(f"Retrieved Space ID from session config: {SPACE_ID}")
    except Exception:
        print("WARNING: Space ID not set. Enter it in the 'space_id' widget above.")
        print("Copy it from the Lab 01 output cell.")

print(f"Catalog  : {CATALOG}")
print(f"Schema   : {SCHEMA}")
print(f"Space ID : {SPACE_ID}")

# COMMAND ----------

# Quick link to Genie Space — run this to open it alongside the lab
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
space_url = f"{w.config.host}#pages/genie/spaces/{SPACE_ID}"
print(f"Your Genie Space URL:\n{space_url}\n")
displayHTML(
    f'<a href="{space_url}" target="_blank" '
    f'style="font-size:1.2em; color:#FF3621; font-weight:bold;">'
    f'Open AEMO NEM Operations Genie Space ↗</a>'
)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Section 1: SQL Expressions — Defining Your KPIs
# MAGIC **10 minutes | UI-first**
# MAGIC
# MAGIC ## Navigate to SQL Expressions
# MAGIC
# MAGIC ```
# MAGIC ┌─── Configure Tab ────────────────────────────────────────────────────────────────┐
# MAGIC │  [Data]  [Instructions]  [Benchmarks]  [Monitor]                                  │
# MAGIC │                                                                                    │
# MAGIC │  Instructions:                                                                     │
# MAGIC │  ├── SQL Expressions    ← click here first                                        │
# MAGIC │  │     ├── Measures     (KPIs and aggregations)                                   │
# MAGIC │  │     ├── Filters      (common WHERE conditions)                                  │
# MAGIC │  │     └── Fields       (grouping dimensions / calculated columns)                 │
# MAGIC │  ├── SQL Queries        (golden queries — Section 2)                               │
# MAGIC │  └── Text               (free-text rules — Section 4)                              │
# MAGIC └────────────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ## What SQL Expressions do
# MAGIC
# MAGIC SQL Expressions let you pre-define fragments of SQL that Genie inserts into generated queries.
# MAGIC They are the most reliable instruction type because they are **compiled, not interpreted**.
# MAGIC
# MAGIC | Type | What it defines | Example |
# MAGIC |------|----------------|---------|
# MAGIC | **Measure** | An aggregation that answers "how much / how many" | `ROUND(AVG(rrp), 2)` |
# MAGIC | **Filter** | A reusable WHERE clause fragment | `settlement_date >= DATE_TRUNC(...)` |
# MAGIC | **Field** | A calculated grouping dimension or label | `CASE WHEN fuel_type IN (...) THEN ...` |
# MAGIC
# MAGIC > **When a user asks "what is the average spot price?" — Genie will use the Measure you define
# MAGIC here, not re-derive it from scratch. This is how you guarantee consistent KPI calculations.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercise 1.1 — Add 4 SQL Expressions via UI
# MAGIC
# MAGIC In your Genie Space: **Configure → Instructions → SQL Expressions → + Add expression**
# MAGIC
# MAGIC Add each expression below. The code cells after this block let you verify the SQL is correct
# MAGIC before you type it into the UI.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Expression 1: Average Spot Price (Measure)
# MAGIC
# MAGIC ```
# MAGIC Name:         Average Spot Price
# MAGIC Type:         Measure
# MAGIC SQL:          ROUND(AVG(spot_prices.rrp), 2)
# MAGIC Synonyms:     avg price, typical price, mean price, average electricity price
# MAGIC Instructions: Always express in $/MWh to 2 decimal places.
# MAGIC               Represents the Regional Reference Price (RRP) — the wholesale electricity price
# MAGIC               for a 5-minute dispatch interval in a given NEM region.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Expression 2: Price Spike Count (Measure)
# MAGIC
# MAGIC ```
# MAGIC Name:         Price Spike Events
# MAGIC Type:         Measure
# MAGIC SQL:          COUNT(CASE WHEN spot_prices.rrp > 300 THEN 1 END)
# MAGIC Synonyms:     high price events, spikes, price peaks, price exceedances
# MAGIC Instructions: A price spike is any 5-minute interval where rrp exceeds $300/MWh.
# MAGIC               Report the count of such intervals. Do not confuse with the market price cap.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Expression 3: Current Quarter (Filter)
# MAGIC
# MAGIC ```
# MAGIC Name:         Current Quarter
# MAGIC Type:         Filter
# MAGIC SQL:          spot_prices.settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
# MAGIC Instructions: Apply this filter when the user says 'this quarter' or 'current quarter'
# MAGIC               without specifying start and end dates explicitly.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Expression 4: Generation Type (Field)
# MAGIC
# MAGIC ```
# MAGIC Name:         Generation Type
# MAGIC Type:         Field
# MAGIC SQL:          CASE
# MAGIC                 WHEN dispatch_intervals.fuel_type IN ('solar', 'wind') THEN 'Renewable'
# MAGIC                 WHEN dispatch_intervals.fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
# MAGIC                 ELSE 'Other'
# MAGIC               END
# MAGIC Synonyms:     fuel category, energy type, generation category, fuel mix bucket
# MAGIC Instructions: Use this field whenever grouping generation data by broad fuel type.
# MAGIC               'Renewable' includes solar and wind only. Hydro is classified as 'Other'.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Expression 1: Average Spot Price
# MAGIC
# MAGIC Run this cell to confirm the SQL works on your data before entering it in the UI.
# MAGIC The result is what Genie will produce when a user asks "what is the average spot price?".

# COMMAND ----------

# Verify: Average Spot Price Measure
avg_price_check = spark.sql(f"""
    SELECT
        region_id,
        ROUND(AVG(rrp), 2)  AS average_spot_price_dollarMWh
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY region_id
    ORDER BY average_spot_price_dollarMWh DESC
""")
print("Average Spot Price by region — current quarter:")
display(avg_price_check)
print("\nSQL Expression to enter in UI:")
print("  ROUND(AVG(spot_prices.rrp), 2)")
print("\n✅ If this returned rows, the SQL Expression is valid. Enter it in the UI.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Expression 2: Price Spike Count
# MAGIC
# MAGIC Run this cell to confirm the spike count logic. $300/MWh is the definition we are
# MAGIC encoding — it should produce the same count every time a user asks "how many spikes?".

# COMMAND ----------

# Verify: Price Spike Count Measure
spike_check = spark.sql(f"""
    SELECT
        region_id,
        COUNT(CASE WHEN rrp > 300 THEN 1 END)  AS price_spike_events,
        ROUND(AVG(rrp), 2)                      AS avg_price_for_context
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY region_id
    ORDER BY price_spike_events DESC
""")
print("Price Spike Events (rrp > $300/MWh) — current quarter:")
display(spike_check)
print("\nSQL Expression to enter in UI:")
print("  COUNT(CASE WHEN spot_prices.rrp > 300 THEN 1 END)")
print("\n✅ Spike count confirmed. The threshold ($300) is now codified in the Measure, not left to interpretation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Expression 3: Current Quarter Filter

# COMMAND ----------

# Verify: Current Quarter Filter
filter_check = spark.sql(f"""
    SELECT
        DATE_TRUNC('quarter', CURRENT_DATE)  AS quarter_start,
        CURRENT_DATE                          AS today,
        COUNT(*)                              AS intervals_in_current_quarter
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
""")
print("Current Quarter filter boundary:")
display(filter_check)
print("\nSQL Filter to enter in UI:")
print("  spot_prices.settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)")
print("\n✅ Filter verified. Genie will apply this whenever the user says 'this quarter'.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Expression 4: Generation Type Field

# COMMAND ----------

# Verify: Generation Type Field
fuel_field_check = spark.sql(f"""
    SELECT
        CASE
            WHEN fuel_type IN ('solar', 'wind') THEN 'Renewable'
            WHEN fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
            ELSE 'Other'
        END                            AS generation_type,
        fuel_type,
        ROUND(SUM(dispatch_mw) / 12, 0) AS total_mwh
    FROM {CATALOG}.{SCHEMA}.dispatch_intervals
    WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY generation_type, fuel_type
    ORDER BY total_mwh DESC
""")
print("Generation Type field — dispatch this quarter by fuel bucket:")
display(fuel_field_check)
print("\nSQL Field to enter in UI:")
print("""  CASE
    WHEN dispatch_intervals.fuel_type IN ('solar', 'wind') THEN 'Renewable'
    WHEN dispatch_intervals.fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
    ELSE 'Other'
  END""")
print("\n✅ Field verified. This replaces any ad-hoc CASE logic Genie might otherwise generate inconsistently.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1 Checkpoint
# MAGIC
# MAGIC Before moving to Section 2, confirm all four expressions are added in the UI:
# MAGIC
# MAGIC - [ ] **Average Spot Price** — Type: Measure — SQL: `ROUND(AVG(spot_prices.rrp), 2)`
# MAGIC - [ ] **Price Spike Events** — Type: Measure — SQL: `COUNT(CASE WHEN spot_prices.rrp > 300 THEN 1 END)`
# MAGIC - [ ] **Current Quarter** — Type: Filter — SQL: `spot_prices.settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)`
# MAGIC - [ ] **Generation Type** — Type: Field — SQL: `CASE WHEN ... THEN 'Renewable' ...`
# MAGIC
# MAGIC > **Why this matters:** Test the Measures now. Ask your Genie Space: *"What is the average spot price this quarter?"*
# MAGIC > Genie should use your Measure expression directly. Click **Show SQL** — you will see `ROUND(AVG(rrp), 2)` in the query,
# MAGIC > not some other formulation it invented.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Section 2: Golden Queries — Teaching Patterns
# MAGIC **15 minutes | UI-first**
# MAGIC
# MAGIC ## Navigate to Golden Queries
# MAGIC
# MAGIC ```
# MAGIC Configure → Instructions → SQL Queries → + Add
# MAGIC ```
# MAGIC
# MAGIC ## Why golden queries are routing rules, not just examples
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────────────────────────┐
# MAGIC │  How Genie processes a user question:                                            │
# MAGIC │                                                                                  │
# MAGIC │  User: "What was the average spot price by region yesterday?"                    │
# MAGIC │                           │                                                      │
# MAGIC │                           ▼                                                      │
# MAGIC │  Step 1: Check golden query TITLES for a semantic match                         │
# MAGIC │          → Match found → run pre-written SQL directly → label: "Trusted"        │
# MAGIC │          → No match   → generate SQL from scratch using all other instructions  │
# MAGIC │                                                                                  │
# MAGIC │  This means golden query titles are ROUTING RULES.                              │
# MAGIC │  Write titles exactly as users would type the question.                         │
# MAGIC │                                                                                  │
# MAGIC │  ✅  "What was the average spot price by region for :date_period?"              │
# MAGIC │  ❌  "Average prices"     ← too vague to match, never routes here              │
# MAGIC │  ❌  "Spot price query"   ← not how a user phrases a question                  │
# MAGIC └──────────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ## Parameters in golden queries
# MAGIC
# MAGIC Golden queries support named parameters (`:parameter_name`). When Genie matches a golden
# MAGIC query, it prompts the user to fill in the parameter value before running the SQL.
# MAGIC Parameters make golden queries reusable across dates, regions, and time windows.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercise 2.1 — Add 5 Golden Queries via UI
# MAGIC
# MAGIC For each query below:
# MAGIC 1. In Genie: **Configure → Instructions → SQL Queries → + Add**
# MAGIC 2. Paste the title exactly as written (this is what Genie matches against)
# MAGIC 3. Paste the SQL into the query editor
# MAGIC 4. Add parameters where indicated
# MAGIC 5. Click **Save**
# MAGIC
# MAGIC Run the verification cell beneath each query before entering it in the UI.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Golden Query 1: Spot Prices by Region
# MAGIC
# MAGIC **Title to enter in UI (copy exactly):**
# MAGIC ```
# MAGIC What was the average spot price by region for :date_period?
# MAGIC ```
# MAGIC
# MAGIC **Parameter:**
# MAGIC - Name: `date_period`
# MAGIC - Type: Date
# MAGIC - Comment: `e.g., 'yesterday', 'last week', 'June 1'`
# MAGIC
# MAGIC **SQL:**
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     ROUND(AVG(rrp), 2)   AS avg_price_mwh,
# MAGIC     ROUND(MIN(rrp), 2)   AS min_price_mwh,
# MAGIC     ROUND(MAX(rrp), 2)   AS max_price_mwh,
# MAGIC     COUNT(*)             AS interval_count
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE DATE(settlement_date) = :date_period
# MAGIC GROUP BY region_id
# MAGIC ORDER BY avg_price_mwh DESC
# MAGIC ```

# COMMAND ----------

# Verify Golden Query 1: Spot Prices by Region
# Using CURRENT_DATE - 1 as a stand-in for :date_period
gq1_verify = spark.sql(f"""
    SELECT
        region_id,
        ROUND(AVG(rrp), 2)  AS avg_price_mwh,
        ROUND(MIN(rrp), 2)  AS min_price_mwh,
        ROUND(MAX(rrp), 2)  AS max_price_mwh,
        COUNT(*)             AS interval_count
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE DATE(settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
    GROUP BY region_id
    ORDER BY avg_price_mwh DESC
""")
print("Golden Query 1 verification — spot prices by region (yesterday as test date):")
display(gq1_verify)
print("\n✅ SQL valid. Enter this query in the UI with :date_period replacing the hardcoded date.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Golden Query 2: Price Spikes Above $300
# MAGIC
# MAGIC **Title to enter in UI (copy exactly):**
# MAGIC ```
# MAGIC Were there any price spikes above $300 per MWh in :region last month?
# MAGIC ```
# MAGIC
# MAGIC **Parameters:**
# MAGIC - Name: `region`
# MAGIC - Type: String
# MAGIC - Comment: `NEM region code: NSW1, VIC1, QLD1, SA1, TAS1`
# MAGIC
# MAGIC **SQL:**
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     region_id,
# MAGIC     DATE(settlement_date)  AS spike_date,
# MAGIC     settlement_date        AS interval_time,
# MAGIC     ROUND(rrp, 2)          AS price_mwh
# MAGIC FROM workshop_au.aemo.spot_prices
# MAGIC WHERE region_id = :region
# MAGIC   AND rrp > 300
# MAGIC   AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
# MAGIC ORDER BY rrp DESC
# MAGIC ```

# COMMAND ----------

# Verify Golden Query 2: Price Spikes
# Test with VIC1 — change the region string to test other regions
test_region = "VIC1"

gq2_verify = spark.sql(f"""
    SELECT
        region_id,
        DATE(settlement_date)  AS spike_date,
        settlement_date        AS interval_time,
        ROUND(rrp, 2)          AS price_mwh
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE region_id = '{test_region}'
      AND rrp > 300
      AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
    ORDER BY rrp DESC
""")
print(f"Golden Query 2 verification — price spikes in {test_region} (last 30 days):")
display(gq2_verify)
row_count = gq2_verify.count()
if row_count == 0:
    print(f"\nNo spikes above $300 in {test_region} in the last 30 days — this is a valid result, not an error.")
else:
    print(f"\n{row_count} spike intervals found. SQL is valid. Enter in the UI with :region as the parameter.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Golden Query 3: Generator Dispatch Ranking
# MAGIC
# MAGIC **Title to enter in UI (copy exactly):**
# MAGIC ```
# MAGIC Which generators dispatched the most in :region last week?
# MAGIC ```
# MAGIC
# MAGIC **Parameters:**
# MAGIC - Name: `region`
# MAGIC - Type: String
# MAGIC - Comment: `NEM region code e.g. QLD1`
# MAGIC
# MAGIC **SQL:**
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
# MAGIC
# MAGIC > **Note:** This golden query demonstrates the dispatch ↔ generator_registration JOIN pattern.
# MAGIC > When Genie matches this title, it runs the pre-written JOIN rather than attempting to construct
# MAGIC > a join from scratch. This is the primary reason complex joins belong in golden queries.

# COMMAND ----------

# Verify Golden Query 3: Generator Dispatch Ranking
test_region_gq3 = "QLD1"

gq3_verify = spark.sql(f"""
    SELECT
        d.duid,
        g.station_name,
        g.fuel_type,
        ROUND(SUM(d.dispatch_mw) / 12, 1)  AS total_mwh,
        ROUND(AVG(d.dispatch_mw), 1)        AS avg_dispatch_mw
    FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
    LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid
    WHERE d.region_id = '{test_region_gq3}'
      AND d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY d.duid, g.station_name, g.fuel_type
    ORDER BY total_mwh DESC
    LIMIT 15
""")
print(f"Golden Query 3 verification — top generators in {test_region_gq3} last week:")
display(gq3_verify)
print("\n✅ JOIN confirmed working. This query demonstrates the dispatch ↔ generator_registration pattern.")
print("   Enter in UI with :region as the parameter.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Golden Query 4: LOR Market Notices
# MAGIC
# MAGIC **Title to enter in UI (copy exactly):**
# MAGIC ```
# MAGIC Were there any LOR notices in the last :days days?
# MAGIC ```
# MAGIC
# MAGIC **Parameters:**
# MAGIC - Name: `days`
# MAGIC - Type: Integer
# MAGIC - Comment: `Number of days to look back, e.g. 7, 14, 30`
# MAGIC
# MAGIC **SQL:**
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     notice_type,
# MAGIC     issue_time,
# MAGIC     effective_date,
# MAGIC     region_id,
# MAGIC     SUBSTRING(reason, 1, 200)  AS summary
# MAGIC FROM workshop_au.aemo.market_notices
# MAGIC WHERE notice_type LIKE 'LOR%'
# MAGIC   AND issue_time >= CURRENT_TIMESTAMP - INTERVAL :days DAYS
# MAGIC ORDER BY issue_time DESC
# MAGIC ```

# COMMAND ----------

# Verify Golden Query 4: LOR Notices
test_days = 30

gq4_verify = spark.sql(f"""
    SELECT
        notice_type,
        issue_time,
        effective_date,
        region_id,
        SUBSTRING(reason, 1, 200)  AS summary
    FROM {CATALOG}.{SCHEMA}.market_notices
    WHERE notice_type LIKE 'LOR%'
      AND issue_time >= CURRENT_TIMESTAMP - INTERVAL {test_days} DAYS
    ORDER BY issue_time DESC
""")
print(f"Golden Query 4 verification — LOR notices in the last {test_days} days:")
display(gq4_verify)
lor_count = gq4_verify.count()
if lor_count == 0:
    print(f"\nNo LOR notices in the last {test_days} days — this is a valid result.")
    print("Try increasing test_days if you want to see historical LOR data.")
else:
    print(f"\n{lor_count} LOR notices found. SQL is valid. Enter in the UI with :days as the parameter.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Golden Query 5: Renewable vs Fossil Fuel Dispatch Comparison
# MAGIC
# MAGIC **Title to enter in UI (copy exactly):**
# MAGIC ```
# MAGIC Compare renewable versus fossil fuel dispatch in :region for :period?
# MAGIC ```
# MAGIC
# MAGIC **Parameters:**
# MAGIC - Name: `region` — Type: String
# MAGIC - Name: `period` — Type: String — Comment: `e.g. 'last month', 'this week', '30 days'`
# MAGIC
# MAGIC **SQL:**
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     CASE
# MAGIC         WHEN fuel_type IN ('solar', 'wind') THEN 'Renewable'
# MAGIC         WHEN fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
# MAGIC         ELSE 'Other'
# MAGIC     END        AS generation_type,
# MAGIC     fuel_type,
# MAGIC     ROUND(SUM(dispatch_mw) / 12, 0)  AS total_mwh
# MAGIC FROM workshop_au.aemo.dispatch_intervals
# MAGIC WHERE region_id = :region
# MAGIC   AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
# MAGIC GROUP BY generation_type, fuel_type
# MAGIC ORDER BY total_mwh DESC
# MAGIC ```
# MAGIC
# MAGIC > **Note:** The `:period` parameter is accepted by Genie but this SQL uses a fixed 30-day window
# MAGIC > for simplicity. In a production Space you would use a more sophisticated date parsing approach
# MAGIC > or restrict `period` to a set of supported values in the parameter comment.

# COMMAND ----------

# Verify Golden Query 5: Fuel Mix Comparison
test_region_gq5 = "NSW1"

gq5_verify = spark.sql(f"""
    SELECT
        CASE
            WHEN fuel_type IN ('solar', 'wind') THEN 'Renewable'
            WHEN fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
            ELSE 'Other'
        END                              AS generation_type,
        fuel_type,
        ROUND(SUM(dispatch_mw) / 12, 0)  AS total_mwh
    FROM {CATALOG}.{SCHEMA}.dispatch_intervals
    WHERE region_id = '{test_region_gq5}'
      AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
    GROUP BY generation_type, fuel_type
    ORDER BY total_mwh DESC
""")
print(f"Golden Query 5 verification — fuel mix in {test_region_gq5} last 30 days:")
display(gq5_verify)
print("\n✅ Fuel mix CASE logic confirmed. This query encodes the same Generation Type logic")
print("   as SQL Expression 4 — golden queries inherit SQL Expression definitions automatically.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify: Golden Query Titles Are Discoverable
# MAGIC
# MAGIC After adding all 5 golden queries, test them in Genie by asking questions that should match.
# MAGIC Look for the **"Trusted"** label on the result — this confirms a golden query was matched.

# COMMAND ----------

# Summary of expected golden query title matches
print("Expected golden query matches — test these in your Genie Space:\n")

title_tests = [
    ("What was the average spot price by region for yesterday?",
     "Golden Query 1", "Trusted label expected"),
    ("Were there any price spikes above $300 per MWh in SA1 last month?",
     "Golden Query 2", "Trusted label expected"),
    ("Which generators dispatched the most in VIC1 last week?",
     "Golden Query 3", "Trusted label expected"),
    ("Were there any LOR notices in the last 14 days?",
     "Golden Query 4", "Trusted label expected"),
    ("Compare renewable versus fossil fuel dispatch in QLD1 for last month?",
     "Golden Query 5", "Trusted label expected"),
]

for question, query, expected in title_tests:
    print(f"  Question : {question}")
    print(f"  Routes to: {query} — {expected}")
    print()

print("If any question does NOT show 'Trusted': check that the title in the UI matches")
print("exactly what you entered (including the :parameter_name tokens).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2 Checkpoint
# MAGIC
# MAGIC - [ ] Golden Query 1 added — "What was the average spot price by region for :date_period?"
# MAGIC - [ ] Golden Query 2 added — "Were there any price spikes above $300 per MWh in :region last month?"
# MAGIC - [ ] Golden Query 3 added — "Which generators dispatched the most in :region last week?"
# MAGIC - [ ] Golden Query 4 added — "Were there any LOR notices in the last :days days?"
# MAGIC - [ ] Golden Query 5 added — "Compare renewable versus fossil fuel dispatch in :region for :period?"
# MAGIC - [ ] At least one golden query tested in Genie — "Trusted" label confirmed

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Section 3: Join Configuration — Structural Rules
# MAGIC **5 minutes | UI-first**
# MAGIC
# MAGIC ## Why explicit joins matter
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────────────────────────┐
# MAGIC │  Without join configuration:                                                     │
# MAGIC │  Genie sees two tables with a shared column (duid) and must guess the join.     │
# MAGIC │  Result: sometimes it guesses correctly, sometimes it does a cross-join,         │
# MAGIC │  sometimes it refuses to join at all.                                            │
# MAGIC │                                                                                  │
# MAGIC │  With join configuration:                                                        │
# MAGIC │  Genie knows exactly: dispatch_intervals.duid = generator_registration.duid     │
# MAGIC │  with a many-to-one relationship (many intervals per generator).                 │
# MAGIC │  Result: consistent, correct joins every time.                                   │
# MAGIC └──────────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ## Navigate to Join Configuration
# MAGIC
# MAGIC ```
# MAGIC Configure → Instructions → SQL Queries → Joins tab
# MAGIC → Click "+ Add join"
# MAGIC ```
# MAGIC
# MAGIC **Or alternatively:**
# MAGIC ```
# MAGIC Configure → Data → [select a table] → Joins tab
# MAGIC ```
# MAGIC
# MAGIC ## Exercise 3.1 — Configure the dispatch ↔ generator_registration join
# MAGIC
# MAGIC Fill in the join dialog:
# MAGIC
# MAGIC ```
# MAGIC Left table:   dispatch_intervals
# MAGIC Right table:  generator_registration
# MAGIC Join type:    LEFT JOIN
# MAGIC Condition:    dispatch_intervals.duid = generator_registration.duid
# MAGIC Relationship: Many-to-one
# MAGIC               (many dispatch intervals per registered generator)
# MAGIC ```
# MAGIC
# MAGIC Click **Save**.
# MAGIC
# MAGIC > **After saving:** Ask Genie a question that requires both tables:
# MAGIC > *"Show me the fuel type breakdown of dispatch in NSW1 last week"*
# MAGIC > Click **Show SQL** — the JOIN should appear as a LEFT JOIN on duid, not a CROSS JOIN.

# COMMAND ----------

# Verify: Join logic before configuring in UI
# This is exactly the JOIN Genie will use after you configure it
join_verify = spark.sql(f"""
    SELECT
        d.region_id,
        d.duid,
        g.station_name,
        g.fuel_type,
        COUNT(*)                             AS interval_count,
        ROUND(SUM(d.dispatch_mw) / 12, 0)   AS total_mwh
    FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
    LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g
        ON d.duid = g.duid
    WHERE d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY d.region_id, d.duid, g.station_name, g.fuel_type
    ORDER BY total_mwh DESC
    LIMIT 20
""")
print("Join verification — dispatch_intervals LEFT JOIN generator_registration (on duid):")
display(join_verify)

# Check for any null station_names — would indicate unmatched duids
unmatched = join_verify.filter("station_name IS NULL").count()
matched   = join_verify.filter("station_name IS NOT NULL").count()
print(f"\nMatched rows (station_name found): {matched}")
print(f"Unmatched rows (duid not in generator_registration): {unmatched}")
if unmatched > 0:
    print("  → Some DUIDs appear in dispatch but not in generator_registration.")
    print("    This is expected for test data. The LEFT JOIN handles this gracefully.")
print("\n✅ Join logic confirmed. Configure this join in the UI using the instructions above.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3 Checkpoint
# MAGIC
# MAGIC - [ ] Join configured: `dispatch_intervals` ↔ `generator_registration` on `duid`
# MAGIC - [ ] Join type: LEFT JOIN, Relationship: Many-to-one
# MAGIC - [ ] Tested in Genie: asked a question requiring both tables, confirmed JOIN in Show SQL

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Section 4: Text Instructions — Use Sparingly
# MAGIC **5 minutes | UI-first**
# MAGIC
# MAGIC ## Navigate to Text Instructions
# MAGIC
# MAGIC ```
# MAGIC Configure → Instructions → Text → + Add instruction
# MAGIC ```
# MAGIC
# MAGIC ## When text instructions are appropriate
# MAGIC
# MAGIC Text instructions should only apply rules that:
# MAGIC 1. Must affect **every single response** regardless of question type
# MAGIC 2. Cannot be expressed as SQL (output formatting, terminology clarification)
# MAGIC 3. Are short enough that Genie will not misinterpret them
# MAGIC
# MAGIC ## Anti-patterns — what NOT to put in text instructions
# MAGIC
# MAGIC ```
# MAGIC ❌ "Use example SQL to calculate SAIDI"
# MAGIC    → This belongs in a golden query. Text instructions cannot reference SQL reliably.
# MAGIC
# MAGIC ❌ "Join dispatch_intervals to generator_registration using duid"
# MAGIC    → This belongs in Join Configuration. Text instructions for joins are unreliable.
# MAGIC
# MAGIC ❌ "Average spot price means AVG(rrp)"
# MAGIC    → This belongs in a SQL Expression (Measure). Text instructions for KPIs drift over time.
# MAGIC
# MAGIC ❌ Long paragraphs explaining AEMO market rules
# MAGIC    → Genie will not reliably apply long text instructions. Keep each instruction to 1-2 sentences.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercise 4.1 — Add 4 Text Instructions via UI
# MAGIC
# MAGIC In Genie: **Configure → Instructions → Text → + Add instruction**
# MAGIC
# MAGIC Add each instruction below as a separate entry (do not combine into one large block).
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Text Instruction 1: Price Units
# MAGIC ```
# MAGIC Always express electricity prices in $/MWh with 2 decimal places.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Text Instruction 2: Region Code Format
# MAGIC ```
# MAGIC Region codes must be NSW1, VIC1, QLD1, SA1, or TAS1.
# MAGIC Never use NSW, VIC, QLD, SA, or TAS without the '1' suffix.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Text Instruction 3: Reliability Metric Definitions
# MAGIC ```
# MAGIC SAIDI = minutes of outage per customer per year (lower is better).
# MAGIC SAIFI = interruptions per customer per year (lower is better).
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Text Instruction 4: Today's Date Handling
# MAGIC ```
# MAGIC When the user asks about 'today' without specifying a date, use DATE(CURRENT_TIMESTAMP)
# MAGIC as the date filter. If no data is available for today, say so and suggest using yesterday.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC > **After adding all 4:** Test with a price question. The response should always show `$87.42/MWh`
# MAGIC > format, not `87.42` or `$87/MWh`. This is the text instruction working as a formatting guard.

# COMMAND ----------

# Reference cell: show what correct output format looks like
print("Text Instruction 1 — expected output format for price questions:")
print()

sample_prices = spark.sql(f"""
    SELECT
        region_id,
        ROUND(AVG(rrp), 2)  AS avg_price_mwh
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY region_id
    ORDER BY avg_price_mwh DESC
""")

rows = sample_prices.collect()
print(f"{'Region':<8} {'Avg Price':>15}")
print(f"{'------':<8} {'---------':>15}")
for row in rows:
    price_str = f"${row.avg_price_mwh:.2f}/MWh"
    print(f"{row.region_id:<8} {price_str:>15}")

print()
print("This is the format the Text Instruction enforces.")
print("Without it, Genie might return '87.42' or '$87/MWh' — both technically correct but inconsistent.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4 Checkpoint
# MAGIC
# MAGIC - [ ] Text Instruction 1 added: price formatting (`$/MWh` with 2 decimal places)
# MAGIC - [ ] Text Instruction 2 added: region code format (`NSW1` not `NSW`)
# MAGIC - [ ] Text Instruction 3 added: SAIDI/SAIFI definitions
# MAGIC - [ ] Text Instruction 4 added: today's date handling
# MAGIC - [ ] Tested a price question in Genie — confirmed `$/MWh` format in the response

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC # Lab 02 Final Verification
# MAGIC
# MAGIC Run this cell to confirm the underlying SQL for all four instruction types is working.
# MAGIC Then do a final end-to-end test in Genie.

# COMMAND ----------

print("=" * 70)
print("LAB 02 FINAL VERIFICATION — Instruction Hierarchy")
print("=" * 70)
print()

results = {}

# Test 1: SQL Expression (Average Spot Price)
try:
    r = spark.sql(f"""
        SELECT ROUND(AVG(rrp), 2) AS avg_price
        FROM {CATALOG}.{SCHEMA}.spot_prices
        WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    """).collect()[0]
    results["SQL Expression — Average Spot Price"] = f"${r.avg_price:.2f}/MWh"
except Exception as e:
    results["SQL Expression — Average Spot Price"] = f"ERROR: {e}"

# Test 2: SQL Expression (Price Spike Count)
try:
    r = spark.sql(f"""
        SELECT COUNT(CASE WHEN rrp > 300 THEN 1 END) AS spikes
        FROM {CATALOG}.{SCHEMA}.spot_prices
        WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    """).collect()[0]
    results["SQL Expression — Price Spike Count"] = f"{r.spikes} spikes this quarter"
except Exception as e:
    results["SQL Expression — Price Spike Count"] = f"ERROR: {e}"

# Test 3: SQL Expression (Current Quarter Filter)
try:
    r = spark.sql(f"""
        SELECT COUNT(*) AS intervals
        FROM {CATALOG}.{SCHEMA}.spot_prices
        WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    """).collect()[0]
    results["SQL Expression — Current Quarter Filter"] = f"{r.intervals:,} intervals in scope"
except Exception as e:
    results["SQL Expression — Current Quarter Filter"] = f"ERROR: {e}"

# Test 4: SQL Expression (Generation Type Field)
try:
    rows = spark.sql(f"""
        SELECT DISTINCT
            CASE
                WHEN fuel_type IN ('solar', 'wind') THEN 'Renewable'
                WHEN fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
                ELSE 'Other'
            END AS generation_type
        FROM {CATALOG}.{SCHEMA}.dispatch_intervals
        LIMIT 10
    """).collect()
    buckets = sorted(set(r.generation_type for r in rows))
    results["SQL Expression — Generation Type Field"] = f"Buckets: {', '.join(buckets)}"
except Exception as e:
    results["SQL Expression — Generation Type Field"] = f"ERROR: {e}"

# Test 5: Golden Query 3 JOIN pattern
try:
    r = spark.sql(f"""
        SELECT COUNT(*) AS joined_rows
        FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
        LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid
        WHERE d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
    """).collect()[0]
    results["Golden Query + Join — dispatch ↔ generator_registration"] = f"{r.joined_rows:,} joined rows"
except Exception as e:
    results["Golden Query + Join — dispatch ↔ generator_registration"] = f"ERROR: {e}"

# Test 6: LOR golden query pattern
try:
    r = spark.sql(f"""
        SELECT COUNT(*) AS lor_count
        FROM {CATALOG}.{SCHEMA}.market_notices
        WHERE notice_type LIKE 'LOR%'
          AND issue_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    """).collect()[0]
    results["Golden Query — LOR notices pattern"] = f"{r.lor_count} LOR notices (last 30 days)"
except Exception as e:
    results["Golden Query — LOR notices pattern"] = f"ERROR: {e}"

# Print summary
print(f"{'Instruction Type / Test':<55} {'Result'}")
print(f"{'-'*55} {'-'*30}")
for test, result in results.items():
    status = "✅" if "ERROR" not in result else "❌"
    print(f"{status}  {test:<53} {result}")

print()
all_pass = all("ERROR" not in v for v in results.values())
if all_pass:
    print("All 6 instruction type tests passed.")
    print("Your Genie Space is configured with a complete instruction hierarchy.")
else:
    print("Some tests failed — check the ERROR messages above and fix before proceeding to Lab 03.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## End-to-End Genie Test
# MAGIC
# MAGIC Ask these questions in your Genie Space and verify the expected behaviour:
# MAGIC
# MAGIC | Question | Expected behaviour | What to check |
# MAGIC |----------|-------------------|---------------|
# MAGIC | `What is the average spot price in NSW1 this quarter?` | Uses Measure + Filter SQL Expressions | Show SQL: `ROUND(AVG(rrp), 2)` + quarter filter |
# MAGIC | `How many price spikes were there in QLD1 this quarter?` | Uses spike count Measure + quarter filter | Show SQL: `COUNT(CASE WHEN rrp > 300...)` |
# MAGIC | `Which generators dispatched the most in VIC1 last week?` | Matches Golden Query 3, shows "Trusted" | "Trusted" badge on result |
# MAGIC | `Were there any LOR notices in the last 7 days?` | Matches Golden Query 4, shows "Trusted" | "Trusted" badge on result |
# MAGIC | `Show me the fuel mix in SA1 for the last month` | Uses Generation Type Field + matches GQ5 | CASE statement in SQL |
# MAGIC | `What is the average spot price today?` | Text Instruction: uses TODAY's date | Suggests yesterday if no data |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 02 Complete Checklist
# MAGIC
# MAGIC ### Section 1: SQL Expressions
# MAGIC - [ ] **Average Spot Price** (Measure) — `ROUND(AVG(spot_prices.rrp), 2)` — verified by code cell
# MAGIC - [ ] **Price Spike Events** (Measure) — `COUNT(CASE WHEN spot_prices.rrp > 300 THEN 1 END)` — verified
# MAGIC - [ ] **Current Quarter** (Filter) — `spot_prices.settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)` — verified
# MAGIC - [ ] **Generation Type** (Field) — CASE WHEN fuel_type IN ('solar','wind') ... — verified
# MAGIC
# MAGIC ### Section 2: Golden Queries
# MAGIC - [ ] GQ1: "What was the average spot price by region for :date_period?" — verified and added
# MAGIC - [ ] GQ2: "Were there any price spikes above $300 per MWh in :region last month?" — verified and added
# MAGIC - [ ] GQ3: "Which generators dispatched the most in :region last week?" — verified and added
# MAGIC - [ ] GQ4: "Were there any LOR notices in the last :days days?" — verified and added
# MAGIC - [ ] GQ5: "Compare renewable versus fossil fuel dispatch in :region for :period?" — verified and added
# MAGIC - [ ] At least 2 golden queries show "Trusted" label when matched in Genie
# MAGIC
# MAGIC ### Section 3: Join Configuration
# MAGIC - [ ] dispatch_intervals ↔ generator_registration — LEFT JOIN on duid — configured in UI
# MAGIC - [ ] JOIN confirmed in Show SQL after asking a cross-table question
# MAGIC
# MAGIC ### Section 4: Text Instructions
# MAGIC - [ ] Price formatting: `$/MWh` with 2 decimal places
# MAGIC - [ ] Region code format: `NSW1` not `NSW`
# MAGIC - [ ] SAIDI/SAIFI definitions added
# MAGIC - [ ] Today's date handling added
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Next: Lab 03 → Governance, Access Controls and Monitoring**
# MAGIC
# MAGIC You will learn: row-level security via Dynamic Views, Space permissions, benchmark
# MAGIC evaluation, and the Monitor tab for understanding how your Space is being used in production.

# COMMAND ----------

# Carry forward Space ID for Lab 03
try:
    spark.conf.set("workshop.genie.space_id", SPACE_ID)
except Exception:
    pass

print(f"Space ID carried forward for Lab 03: {SPACE_ID}")
print()
print("Priority stack summary:")
print("  ① SQL Expressions  — most reliable, compiled into every matching query")
print("  ② Golden Queries   — routing rules for complex patterns, labeled 'Trusted'")
print("  ③ Join Config      — explicit FK relationships, prevents join guessing")
print("  ④ Text Instructions — output formatting only, use sparingly")
print()
print("Lab 02 complete.")
