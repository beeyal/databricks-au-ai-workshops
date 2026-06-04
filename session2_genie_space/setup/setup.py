# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">AEMO Data Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2 pre-requisite — run this BEFORE the labs</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 2.**
# MAGIC It loads the AEMO sample data into Unity Catalog, adds column comments,
# MAGIC and creates the derived objects (metric view, materialized view, UC function)
# MAGIC that Lab 01 demonstrates.  The labs will create the Genie Space itself.
# MAGIC
# MAGIC Expected runtime: ~8 minutes

# COMMAND ----------

dbutils.widgets.text("catalog",      "workshop_au",  "Catalog")
dbutils.widgets.text("schema",       "aemo",         "Schema")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA  = dbutils.widgets.get("schema")

print(f"Catalog : {CATALOG}.{SCHEMA}")
print("Data    : generated via SQL (no CSV files needed)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create catalog and schema

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ {CATALOG}.{SCHEMA} ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Generate AEMO tables via SQL
# MAGIC
# MAGIC No CSV files needed — data is generated directly using SQL functions.
# MAGIC Safe to re-run (uses CREATE OR REPLACE TABLE).

# COMMAND ----------

TABLES_SQL = {
    "spot_prices": f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.spot_prices AS
WITH regions AS (SELECT explode(array('NSW1','VIC1','QLD1','SA1','TAS1')) AS region_id),
dates AS (SELECT date_add('2025-01-01', pos) AS dt FROM (SELECT sequence(0,364) AS seq) LATERAL VIEW posexplode(seq) t AS pos, dt),
hourly AS (SELECT region_id, timestampadd(MINUTE, h*30, CAST(dt AS TIMESTAMP)) AS settlement_date FROM regions CROSS JOIN dates LATERAL VIEW posexplode(sequence(0,47)) t AS h, hv)
SELECT region_id, settlement_date,
  ROUND(CASE region_id
    WHEN 'NSW1' THEN 85+rand()*80+CASE WHEN hour(settlement_date) BETWEEN 17 AND 21 THEN rand()*200 ELSE 0 END
    WHEN 'VIC1' THEN 78+rand()*90+CASE WHEN hour(settlement_date) BETWEEN 17 AND 21 THEN rand()*250 ELSE 0 END
    WHEN 'QLD1' THEN 72+rand()*70+CASE WHEN hour(settlement_date) BETWEEN 8  AND 11 THEN rand()*150 ELSE 0 END
    WHEN 'SA1'  THEN 65+rand()*120+CASE WHEN rand()<0.05 THEN rand()*500 ELSE 0 END
    WHEN 'TAS1' THEN 55+rand()*40 END,2) AS rrp,
  ROUND(rand()*20+5,2) AS raise_6sec, ROUND(rand()*15+3,2) AS lower_6sec,
  ROUND(CASE region_id WHEN 'NSW1' THEN 8000+rand()*2000 WHEN 'VIC1' THEN 6000+rand()*1500
    WHEN 'QLD1' THEN 7000+rand()*1800 WHEN 'SA1' THEN 1500+rand()*500 WHEN 'TAS1' THEN 1200+rand()*300 END,0) AS total_demand_mw,
  ROUND(rand()*500-250,0) AS net_interchange,
  ROUND(CASE region_id WHEN 'NSW1' THEN 7500+rand()*2000 WHEN 'VIC1' THEN 5500+rand()*1500
    WHEN 'QLD1' THEN 6500+rand()*1800 WHEN 'SA1' THEN 1400+rand()*600 WHEN 'TAS1' THEN 1100+rand()*400 END,0) AS scheduled_generation
FROM hourly""",

    "generator_registration": f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.generator_registration AS
SELECT concat('UNIT',lpad(cast(id AS STRING),4,'0')) AS duid,
  CASE (id%20) WHEN 0 THEN 'Bayswater' WHEN 1 THEN 'Eraring' WHEN 2 THEN 'Loy Yang A'
    WHEN 3 THEN 'Hazelwood' WHEN 4 THEN 'Callide B' WHEN 5 THEN 'Gladstone'
    WHEN 6 THEN 'Hornsdale Wind Farm' WHEN 7 THEN 'Snowtown Wind Farm'
    WHEN 8 THEN 'Murchison Wind Farm' WHEN 9 THEN 'Coopers Gap Wind Farm'
    WHEN 10 THEN 'Darlington Point Solar' WHEN 11 THEN 'Limondale Solar Farm'
    WHEN 12 THEN 'Bungala Solar One' WHEN 13 THEN 'Gannawarra Solar Farm'
    WHEN 14 THEN 'Macquarie Wind Farm' WHEN 15 THEN 'Hornsdale Power Reserve'
    WHEN 16 THEN 'Capital Battery' WHEN 17 THEN 'Warradarge Wind Farm'
    WHEN 18 THEN 'Taralga Wind Farm' WHEN 19 THEN 'Engie Pelican Point'
  END AS station_name,
  concat('PART',lpad(cast(((id%8)+1) AS STRING),3,'0')) AS participant_id,
  CASE (id%5) WHEN 0 THEN 'NSW1' WHEN 1 THEN 'VIC1' WHEN 2 THEN 'QLD1' WHEN 3 THEN 'SA1' WHEN 4 THEN 'TAS1' END AS region_id,
  CASE (id%7) WHEN 0 THEN 'coal' WHEN 1 THEN 'coal' WHEN 2 THEN 'gas'
    WHEN 3 THEN 'wind' WHEN 4 THEN 'solar' WHEN 5 THEN 'hydro' WHEN 6 THEN 'battery' END AS fuel_type,
  ROUND(200+rand()*1500,0) AS registered_capacity_mw,
  concat('CONN',lpad(cast(id AS STRING),4,'0')) AS connection_point_id,
  'GENERATOR' AS dispatch_type, ROUND(5+rand()*20,1) AS max_ramp_rate, ROUND(rand()*50,0) AS min_load
FROM (SELECT explode(sequence(1,60)) AS id)""",

    "dispatch_intervals": f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.dispatch_intervals AS
WITH dates AS (SELECT date_add('2025-10-01',pos) AS dt FROM (SELECT sequence(0,91) AS seq) LATERAL VIEW posexplode(seq) t AS pos,dt),
intervals AS (SELECT dt, i FROM dates LATERAL VIEW posexplode(sequence(0,287)) t AS i,iv),
gen AS (SELECT duid,station_name,region_id,fuel_type,registered_capacity_mw FROM {CATALOG}.{SCHEMA}.generator_registration)
SELECT g.region_id, timestampadd(MINUTE,i.i*5,CAST(i.dt AS TIMESTAMP)) AS settlement_date,
  g.duid, g.station_name, g.fuel_type,
  ROUND(CASE g.fuel_type
    WHEN 'solar' THEN CASE WHEN hour(timestampadd(MINUTE,i.i*5,CAST(i.dt AS TIMESTAMP))) BETWEEN 7 AND 18 THEN g.registered_capacity_mw*(0.2+rand()*0.7) ELSE 0 END
    WHEN 'wind'  THEN g.registered_capacity_mw*(0.1+rand()*0.8)
    WHEN 'coal'  THEN g.registered_capacity_mw*(0.6+rand()*0.35)
    WHEN 'gas'   THEN g.registered_capacity_mw*rand()*(CASE WHEN hour(timestampadd(MINUTE,i.i*5,CAST(i.dt AS TIMESTAMP))) BETWEEN 17 AND 22 THEN 0.9 ELSE 0.3 END)
    WHEN 'hydro' THEN g.registered_capacity_mw*(0.3+rand()*0.6)
    ELSE g.registered_capacity_mw*(rand()*0.8) END,1) AS dispatch_mw,
  ROUND(g.registered_capacity_mw*(0.4+rand()*0.5),1) AS initial_mw,
  ROUND(g.registered_capacity_mw*(0.7+rand()*0.3),1) AS available_mw,
  ROUND(5+rand()*15,1) AS ramp_rate, g.region_id AS state
FROM gen g CROSS JOIN intervals i
WHERE (g.duid LIKE '%0%' OR g.duid LIKE '%1%')
LIMIT 500000""",

    "market_notices": f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.market_notices AS
SELECT concat('NTC',lpad(cast(id AS STRING),6,'0')) AS notice_id,
  CASE (id%10) WHEN 0 THEN 'LOR1' WHEN 1 THEN 'LOR2' WHEN 2 THEN 'LOR3'
    ELSE array('SYSTEM_STRENGTH','INTER_REGIONAL','MARKET_SUSPENSION','ADMINISTERED_PRICE','RESERVE_NOTICE','DIRECTION','ELECTRICITY_STATEMENT')[id%7] END AS notice_type,
  timestampadd(HOUR,-(id*6),current_timestamp()) AS issue_time,
  concat('Notice regarding NEM operations in region ',
    CASE (id%5) WHEN 0 THEN 'NSW1' WHEN 1 THEN 'VIC1' WHEN 2 THEN 'QLD1' WHEN 3 THEN 'SA1' WHEN 4 THEN 'TAS1' END,
    '. Reserve levels are ',CASE (id%3) WHEN 0 THEN 'below LOR1 threshold.' WHEN 1 THEN 'critically low.' ELSE 'being monitored.' END) AS reason,
  date_add(current_date(),-(id%60)) AS effective_date,
  CASE (id%5) WHEN 0 THEN 'NSW1' WHEN 1 THEN 'VIC1' WHEN 2 THEN 'QLD1' WHEN 3 THEN 'SA1' WHEN 4 THEN 'TAS1' END AS region_id,
  (id%4=0) AS intervention
FROM (SELECT explode(sequence(1,500)) AS id)""",

    "settlement_amounts": f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.settlement_amounts AS
SELECT date_add(date_trunc('week',current_date()),-(id*7)) AS settlement_date,
  concat('PART',lpad(cast(((id%8)+1) AS STRING),3,'0')) AS participant_id,
  CASE (id%3) WHEN 0 THEN 'FINAL' WHEN 1 THEN 'REVISED' ELSE 'PRELIMINARY' END AS run_type,
  ROUND(rand()*5000000-1000000,2) AS energy_amount_aud, ROUND(rand()*500000,2) AS fcas_amount_aud,
  ROUND(rand()*200000-100000,2) AS interconnector_residue_aud, ROUND(rand()*5700000-1100000,2) AS total_aud,
  CASE (id%3) WHEN 0 THEN 'FINAL' WHEN 1 THEN 'FINAL' ELSE 'PENDING' END AS settlement_status
FROM (SELECT explode(sequence(1,500)) AS id)""",

    "constraint_sets": f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.constraint_sets AS
SELECT concat('CONSTR_',lpad(cast(id AS STRING),4,'0')) AS constraint_id,
  CASE (id%3) WHEN 0 THEN 'thermal' WHEN 1 THEN 'voltage' ELSE 'stability' END AS constraint_type,
  timestampadd(HOUR,-(id*4),current_timestamp()) AS activated_datetime,
  CASE WHEN id%3=0 THEN NULL ELSE timestampadd(HOUR,-(id*4)+(2+(id%8)),current_timestamp()) END AS deactivated_datetime,
  concat('Constraint on transmission element due to ',
    CASE (id%3) WHEN 0 THEN 'thermal loading limits' WHEN 1 THEN 'voltage stability requirements' ELSE 'transient stability limits' END) AS reason,
  ROUND(200+rand()*1800,0) AS rhs_value,
  CASE (id%5) WHEN 0 THEN 'NSW1' WHEN 1 THEN 'VIC1' WHEN 2 THEN 'QLD1' WHEN 3 THEN 'SA1' WHEN 4 THEN 'TAS1' END AS region_affected,
  (id%3=0) AS interconnector
FROM (SELECT explode(sequence(1,1000)) AS id)""",
}

print("Generating AEMO tables via SQL (no CSV files needed)...")
results = []
for table_name, sql in TABLES_SQL.items():
    fqn = f"{CATALOG}.{SCHEMA}.{table_name}"
    try:
        spark.sql(sql)
        count = spark.table(fqn).count()
        results.append(("✅", table_name, f"{count:,} rows"))
    except Exception as e:
        results.append(("❌", table_name, str(e)[:120]))

for icon, tbl, msg in results:
    print(f"{icon} {tbl}: {msg}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Add column comments (all tables)

# COMMAND ----------

COLUMN_COMMENTS = {
    f"{CATALOG}.{SCHEMA}.spot_prices": {
        "settlement_date": "Trading interval end time. 30-minute intervals. AEST/AEDT timezone. Use DATE(settlement_date) to filter by day.",
        "region_id":       "NEM region. Must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix.",
        "rrp":             "Regional Reference Price in $/MWh. Normal range $50–$200. Market cap $15,300/MWh. Floor -$1,000/MWh. Negative = oversupply.",
        "raise_6sec":      "6-second raise FCAS price. Hide unless FCAS analysis is needed.",
        "lower_6sec":      "6-second lower FCAS price. Hide unless FCAS analysis is needed.",
        "total_demand_mw": "Total scheduled demand for the region in MW.",
        "net_interchange": "Net MW flow between regions. Positive = exporting.",
        "scheduled_generation": "Total scheduled generation in the region in MW.",
    },
    f"{CATALOG}.{SCHEMA}.dispatch_intervals": {
        "settlement_date": "5-minute dispatch interval end time. Sum dispatch_mw and divide by 12 to convert to MWh.",
        "region_id":       "NEM region where the unit dispatched. Must be NSW1, VIC1, QLD1, SA1, or TAS1.",
        "duid":            "Dispatchable Unit Identifier. Join to generator_registration.duid for station_name and fuel_type.",
        "dispatch_mw":     "Actual MW dispatched in this 5-minute interval. SUM(dispatch_mw)/12 = MWh.",
        "initial_mw":      "Initial MW target at interval start.",
        "available_mw":    "MW available for dispatch.",
        "ramp_rate":       "Maximum ramp rate in MW per minute.",
        "fuel_type":       "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "station_name":    "Human-readable station name e.g. Bayswater, Loy Yang A.",
        "state":           "Australian state the unit is located in.",
    },
    f"{CATALOG}.{SCHEMA}.market_notices": {
        "notice_id":     "Unique identifier for the market notice.",
        "notice_type":   "LOR1 = reserve watch. LOR2 = shortfall threatened. LOR3 = imminent critical shortage. Use LIKE 'LOR%' to match all LOR types.",
        "issue_time":    "When AEMO published the notice. Use to filter recent events.",
        "reason":        "Free-text description. Use SUBSTRING(reason, 1, 200) for summaries.",
        "effective_date":"When the notice takes effect.",
        "region_id":     "NEM region. NULL means NEM-wide notice.",
        "intervention":  "True if this is an AEMO market intervention.",
    },
    f"{CATALOG}.{SCHEMA}.generator_registration": {
        "duid":                   "Dispatchable Unit Identifier. Primary key. Join to dispatch_intervals.duid.",
        "station_name":           "Human-readable station name.",
        "participant_id":         "Market participant code.",
        "region_id":              "NEM region where registered.",
        "fuel_type":              "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "registered_capacity_mw": "Maximum registered capacity in MW.",
        "connection_point_id":    "NEM connection point identifier for the unit.",
        "dispatch_type":          "GENERATOR, LOAD, or BIDIRECTIONAL.",
        "max_ramp_rate":          "Maximum ramp rate in MW per minute.",
        "min_load":               "Minimum stable load in MW.",
    },
    f"{CATALOG}.{SCHEMA}.constraint_sets": {
        "constraint_id":         "Unique constraint identifier e.g. S_RADIAL_SA_1.",
        "constraint_type":       "Type of constraint: thermal, voltage, stability.",
        "activated_datetime":    "When the constraint became active.",
        "deactivated_datetime":  "When the constraint was lifted. NULL if still active.",
        "reason":                "Free-text description of why the constraint was activated.",
        "rhs_value":             "Right-hand side MW limit of the constraint equation.",
        "region_affected":       "NEM region impacted by this constraint.",
        "interconnector":        "True if this constraint involves an interconnector flow.",
    },
    f"{CATALOG}.{SCHEMA}.settlement_amounts": {
        "settlement_date":            "Settlement week end date.",
        "participant_id":             "Market participant code.",
        "run_type":                   "FINAL, REVISED, or PRELIMINARY.",
        "energy_amount_aud":          "Energy component of settlement in AUD.",
        "fcas_amount_aud":            "FCAS (ancillary services) component in AUD.",
        "interconnector_residue_aud": "Interconnector residue component in AUD.",
        "total_aud":                  "Net settlement amount in AUD.",
        "settlement_status":          "FINAL, PENDING, or DISPUTED.",
    },
}

ok = err = 0
for table_fqn, columns in COLUMN_COMMENTS.items():
    for col, comment in columns.items():
        try:
            safe_comment = comment.replace("'", "\\'")
            spark.sql(f"ALTER TABLE {table_fqn} ALTER COLUMN `{col}` COMMENT '{safe_comment}'")
            ok += 1
        except Exception as e:
            print(f"  ⚠️  {table_fqn.split('.')[-1]}.{col}: {e}")
            err += 1

print(f"✅ {ok} column comments set ({err} errors)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Add table descriptions

# COMMAND ----------

TABLE_DESCRIPTIONS = {
    f"{CATALOG}.{SCHEMA}.spot_prices":            "NEM 30-minute trading interval spot prices. Key column: rrp = Regional Reference Price in $/MWh. Regions: NSW1, VIC1, QLD1, SA1, TAS1.",
    f"{CATALOG}.{SCHEMA}.dispatch_intervals":     "NEM 5-minute generator dispatch data. Key columns: duid (join to generator_registration), dispatch_mw (divide by 12 for MWh), fuel_type. 12 intervals = 1 hour.",
    f"{CATALOG}.{SCHEMA}.market_notices":         "AEMO market and system notices including LOR events. Filter: WHERE notice_type LIKE 'LOR%' for LOR events. LOR1/LOR2/LOR3 = escalating reserve severity.",
    f"{CATALOG}.{SCHEMA}.generator_registration": "NEM registered generator details. Join to dispatch_intervals on duid to get station_name and fuel_type.",
    f"{CATALOG}.{SCHEMA}.settlement_amounts":     "Weekly NEM settlement amounts by participant. run_type: FINAL = confirmed, PRELIMINARY = estimate. total_aud = net amount.",
    f"{CATALOG}.{SCHEMA}.constraint_sets":        "NEM network and system constraints. Activated when a network element is at risk. rhs_value = MW limit. Join region_affected to spot_prices.region_id.",
}

for fqn, desc in TABLE_DESCRIPTIONS.items():
    try:
        safe_desc = desc.replace("'", "\\'")
        spark.sql(f"COMMENT ON TABLE {fqn} IS '{safe_desc}'")
        print(f"✅ {fqn.split('.')[-1]}")
    except Exception as e:
        print(f"❌ {fqn.split('.')[-1]}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Smoke test — verify row counts and sample data

# COMMAND ----------

print("Table row counts:")
all_ok = True
expected = {
    "spot_prices":            1_000,
    "dispatch_intervals":     5_000,
    "market_notices":           100,
    "generator_registration":    50,
    "settlement_amounts":        100,
    "constraint_sets":         1_000,
}
for tbl, min_rows in expected.items():
    try:
        count = spark.table(f"{CATALOG}.{SCHEMA}.{tbl}").count()
        ok    = count >= min_rows
        icon  = "✅" if ok else "⚠️ "
        print(f"  {icon} {tbl}: {count:,} rows")
        if not ok:
            all_ok = False
    except Exception as e:
        print(f"  ❌ {tbl}: {e}")
        all_ok = False

print()
if all_ok:
    print("✅ All tables loaded. Continuing to create derived objects...")
else:
    print("⚠️  Some tables are empty or missing.")
    print("   Re-run this notebook to regenerate tables.")
    print("   Derived objects (Steps 6–8) will fail if source tables are absent.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Create view — NEM spot price KPIs
# MAGIC
# MAGIC Creates a pre-aggregated view that exposes avg price, peak price, and interval count
# MAGIC by region and trading day. Genie queries hit this view instead of re-scanning the
# MAGIC full `spot_prices` table every time, reducing latency and scan cost for "what was the
# MAGIC average spot price in NSW last week?" style questions.
# MAGIC
# MAGIC > **Note on metric views:** Unity Catalog metric views (`CREATE VIEW ... WITH METRICS LANGUAGE YAML`)
# MAGIC > are a Private Preview feature as of mid-2026 and are not available in all workspaces.
# MAGIC > This setup uses a standard `CREATE VIEW` with an equivalent SQL definition so it works
# MAGIC > reliably across all workshop environments.  When metric views reach GA, the YAML block
# MAGIC > would replace the GROUP BY here, allowing Genie and AI/BI dashboards to compose
# MAGIC > dimensions and measures dynamically without hard-coded aggregations.

# COMMAND ----------

METRIC_VIEW_FQN = f"{CATALOG}.{SCHEMA}.nem_spot_metrics"

# Standard view — logically equivalent to a metric view with dimensions (region_id, trading_date)
# and measures (avg_spot_price, peak_spot_price, interval_count).
# Used in place of WITH METRICS YAML syntax for broad runtime compatibility.
METRIC_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {METRIC_VIEW_FQN}
COMMENT 'NEM spot price KPIs by region and trading day.
  avg_spot_price  = average RRP in $/MWh (normal range $50-$200).
  peak_spot_price = maximum RRP in $/MWh (market cap $15,300/MWh).
  interval_count  = number of 30-minute trading intervals in the group.
  Intended dimensions: region_id, trading_date.
  Equivalent to a metric view once that feature reaches GA in this workspace.'
AS
SELECT
    region_id,
    DATE(settlement_date)   AS trading_date,
    ROUND(AVG(rrp), 2)      AS avg_spot_price,
    ROUND(MAX(rrp), 2)      AS peak_spot_price,
    COUNT(*)                AS interval_count
FROM {CATALOG}.{SCHEMA}.spot_prices
GROUP BY region_id, DATE(settlement_date)
"""

try:
    spark.sql(METRIC_VIEW_SQL)
    count = spark.table(METRIC_VIEW_FQN).count()
    print(f"✅ nem_spot_metrics created — {count:,} rows")
except Exception as e:
    print(f"❌ nem_spot_metrics: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7: Create materialized view — daily dispatch summary
# MAGIC
# MAGIC Pre-aggregates `dispatch_intervals` (5-minute, potentially millions of rows) into
# MAGIC a daily summary by region and fuel type.  Genie queries hit this view instead of
# MAGIC the raw table, dramatically reducing scan cost for "how much solar generated
# MAGIC yesterday?" style questions.

# COMMAND ----------

MV_FQN = f"{CATALOG}.{SCHEMA}.daily_dispatch_summary"

MV_SQL = f"""
CREATE OR REPLACE VIEW {MV_FQN}
COMMENT 'Daily NEM dispatch summary by region and fuel type.
  total_mwh  = SUM(dispatch_mw)/12 converts 5-minute MW readings to MWh.
  avg_dispatch_mw = average MW output across all dispatch intervals for the day.
  Note: implemented as a standard view (equivalent to a materialized view for workshop purposes).'
AS
SELECT
    DATE(settlement_date)          AS dispatch_date,
    region_id,
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 1) AS total_mwh,
    ROUND(AVG(dispatch_mw), 1)      AS avg_dispatch_mw
FROM {CATALOG}.{SCHEMA}.dispatch_intervals
GROUP BY DATE(settlement_date), region_id, fuel_type
"""

try:
    spark.sql(MV_SQL)
    count = spark.table(MV_FQN).count()
    print(f"✅ daily_dispatch_summary created — {count:,} rows")
except Exception as e:
    print(f"❌ daily_dispatch_summary: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 8: Create UC function — market cap exposure calculator
# MAGIC
# MAGIC A SQL table-valued function that returns interval count, avg RRP, and max RRP
# MAGIC for a given region above a configurable price threshold.  Participants call it
# MAGIC in Lab 01 to demonstrate UC Functions as a Genie tool.
# MAGIC
# MAGIC Usage:
# MAGIC ```sql
# MAGIC SELECT * FROM workshop_au.aemo.calculate_market_cap_exposure('NSW1', 300.0);
# MAGIC ```

# COMMAND ----------

FUNC_FQN = f"{CATALOG}.{SCHEMA}.calculate_market_cap_exposure"

FUNC_SQL = f"""
CREATE OR REPLACE FUNCTION {FUNC_FQN}(
    region_id_param   STRING  COMMENT 'NEM region to analyse. One of: NSW1, VIC1, QLD1, SA1, TAS1.',
    threshold_param   DOUBLE  DEFAULT 300.0
        COMMENT 'RRP threshold in $/MWh above which an interval is considered a cap-exposure event. Defaults to $300/MWh.'
)
RETURNS TABLE (
    interval_count  BIGINT  COMMENT 'Number of 30-minute intervals with RRP above the threshold.',
    avg_rrp         DOUBLE  COMMENT 'Average RRP across those high-price intervals ($/MWh).',
    max_rrp         DOUBLE  COMMENT 'Maximum RRP observed — peak cap-exposure event ($/MWh).'
)
COMMENT 'Returns market cap exposure metrics for a NEM region above a configurable RRP threshold.
Example: SELECT * FROM {FUNC_FQN}(\\\'NSW1\\\', 300.0)'
RETURN
    SELECT
        COUNT(*)            AS interval_count,
        ROUND(AVG(rrp), 2)  AS avg_rrp,
        ROUND(MAX(rrp), 2)  AS max_rrp
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE region_id = region_id_param
      AND rrp > threshold_param
"""

try:
    spark.sql(FUNC_SQL)
    # Smoke-test: call the function with default threshold on NSW1
    test_df = spark.sql(f"SELECT * FROM {FUNC_FQN}('NSW1', 300.0)")
    row = test_df.collect()[0]
    print(f"✅ calculate_market_cap_exposure created")
    print(f"   Smoke test NSW1 >$300/MWh → {row['interval_count']} intervals, "
          f"avg ${row['avg_rrp']}/MWh, max ${row['max_rrp']}/MWh")
except Exception as e:
    print(f"❌ calculate_market_cap_exposure: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup complete — summary

# COMMAND ----------

print("=" * 60)
print("Session 2 setup summary")
print("=" * 60)
print()
print("Base tables:")
for tbl in ["spot_prices", "dispatch_intervals", "market_notices",
            "generator_registration", "settlement_amounts", "constraint_sets"]:
    try:
        count = spark.table(f"{CATALOG}.{SCHEMA}.{tbl}").count()
        print(f"  ✅ {tbl}: {count:,} rows")
    except Exception as e:
        print(f"  ❌ {tbl}: {e}")

print()
print("Derived objects (Lab 01 demos):")
for obj, kind in [
    ("nem_spot_metrics",              "metric view / view"),
    ("daily_dispatch_summary",        "materialized view"),
    ("calculate_market_cap_exposure", "UC function"),
]:
    try:
        spark.sql(f"DESCRIBE {CATALOG}.{SCHEMA}.{obj}")
        print(f"  ✅ {obj} ({kind})")
    except Exception as e:
        print(f"  ❌ {obj}: {e}")

print()
print("Next steps:")
print("  1. Run Step 9 (below) to grant participant access")
print("  2. Open Lab 01: session2_genie_space/labs/01_genie_space_setup.py")
print("  3. Create the Genie Space via UI and paste the Space ID into the widget")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What this notebook does NOT do
# MAGIC
# MAGIC The following are handled by the labs — do not add them here:
# MAGIC
# MAGIC - ❌ Create the Genie Space → **Lab 01** (participants do this in the UI)
# MAGIC - ❌ Add golden queries → **Lab 02** (automated upload script)
# MAGIC - ❌ Add text instructions → **Lab 02**
# MAGIC - ❌ Add benchmarks → **Lab 02**
# MAGIC - ❌ Set permissions → **Lab 05**

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 9: Grant participant access
# MAGIC
# MAGIC Enter participant emails as a comma-separated list. The script grants:
# MAGIC - `USE CATALOG` + `USE SCHEMA` + `SELECT` on the AEMO schema (so Genie can query tables)
# MAGIC - `EXECUTE` on all functions in the schema (so participants can call `calculate_market_cap_exposure`)
# MAGIC - `CREATE` permission on the schema (so participants can create their own Genie Spaces)

# COMMAND ----------

dbutils.widgets.text("participant_emails", "", "Participant emails (comma-separated)")
raw_emails = dbutils.widgets.get("participant_emails")

participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

if not participants:
    print("Enter participant emails in the widget above, then re-run this cell.")
else:
    print(f"Granting access to {len(participants)} participants:\n")

    grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT EXECUTE ON SCHEMA {CATALOG}.{SCHEMA} TO",        # needed to call calculate_market_cap_exposure
        f"GRANT CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} TO",  # needed to create Genie Space assets
    ]

    ok = err = 0
    for email in participants:
        for grant_prefix in grants:
            stmt = f"{grant_prefix} `{email}`"
            try:
                spark.sql(stmt)
                ok += 1
            except Exception as e:
                print(f"  ⚠️  {email}: {e}")
                err += 1
        print(f"  ✅ {email}")

    print(f"\n{ok} grants applied ({err} errors)")
    print()
    print("Participants can now:")
    print(f"  • Query all tables and views in {CATALOG}.{SCHEMA}")
    print(f"  • Call calculate_market_cap_exposure() and other UC functions")
    print(f"  • Create Genie Spaces backed by those tables")
    print(f"  • Run Lab 01–05")

# COMMAND ----------

# Verify grants were applied
if participants:
    print(f"Current grants on {CATALOG}.{SCHEMA}:")
    display(spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.{SCHEMA}"))

