# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Extending Genie Code Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 5 pre-requisite — run this BEFORE the labs</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 5.**
# MAGIC
# MAGIC It:
# MAGIC 1. Creates the `workshop_au.energy` catalog and schema
# MAGIC 2. Loads energy tables from DBFS (same dataset as Session 1)
# MAGIC 3. Registers 3 UC functions participants will call from Genie Code
# MAGIC 4. Grants participants `EXECUTE` on all three functions
# MAGIC 5. Smoke-tests the functions with sample inputs
# MAGIC 6. Prints the skills directory paths participants should create
# MAGIC
# MAGIC Expected runtime: ~8 minutes

# COMMAND ----------

dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",           "workshop_au",              "Catalog")
dbutils.widgets.text("schema",            "energy",                   "Energy schema")
dbutils.widgets.text("participant_emails","",                         "Participant emails (comma-separated)")
dbutils.widgets.text("data_path",         "dbfs:/tmp/au_workshop/sample_data", "DBFS path to energy CSVs")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
DATA_PATH    = dbutils.widgets.get("data_path")

ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST  = ctx.apiUrl().get().replace("https://", "")
TOKEN = ctx.apiToken().get()

print(f"Catalog    : {CATALOG}.{SCHEMA}")
print(f"Data path  : {DATA_PATH}")
print()
print("Upload energy CSVs to DBFS first if not already there:")
print(f"  databricks fs cp -r ./data/sample_data/ {DATA_PATH}/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create catalog and schema

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} COMMENT 'AU AI Workshops — energy sector sample data'")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA} COMMENT 'Energy network data for Session 5 Genie Code labs'")
# Also ensure the audit schema exists — regulatory_reports lives there
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.audit COMMENT 'AU AI Workshops — regulatory and audit data'")
print(f"✅ {CATALOG}.{SCHEMA} ready")
print(f"✅ {CATALOG}.audit ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Load energy tables from DBFS CSV
# MAGIC
# MAGIC Same six tables as Session 1. Safe to re-run — uses overwrite mode.

# COMMAND ----------

# Table definitions: (csv_filename, target_table_fqn, description, partition_cols)
TABLE_DEFS = [
    (
        "energy_assets.csv",
        f"{CATALOG}.{SCHEMA}.energy_assets",
        "Network assets — transformers, substations, cables, poles, meters",
        ["region"],
    ),
    (
        "meter_readings.csv",
        f"{CATALOG}.{SCHEMA}.meter_readings",
        "30-minute interval meter readings (NEM12-style)",
        ["customer_type"],
    ),
    (
        "outage_events.csv",
        f"{CATALOG}.{SCHEMA}.outage_events",
        "Planned and unplanned network outage events with SAIDI/SAIFI",
        ["region", "event_type"],
    ),
    (
        "maintenance_work_orders.csv",
        f"{CATALOG}.{SCHEMA}.maintenance_work_orders",
        "Maintenance work orders linked to energy assets",
        ["work_type", "status"],
    ),
    (
        "regulatory_reports.csv",
        f"{CATALOG}.audit.regulatory_reports",
        "AER, AEMO, and ESC regulatory submissions",
        ["jurisdiction", "report_type"],
    ),
    (
        "policy_documents.csv",
        f"{CATALOG}.ai_governance.policy_documents",
        "Internal policy documents for Vector Search RAG demo",
        ["doc_type"],
    ),
]

loaded_tables = {}

for csv_file, table_name, description, partition_cols in TABLE_DEFS:
    csv_path = f"{DATA_PATH}/{csv_file}"
    print(f"\nLoading {table_name}...")

    # Create parent schema if needed (policy_documents goes into ai_governance)
    parent_schema = ".".join(table_name.split(".")[:2])
    try:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {parent_schema}")
    except Exception:
        pass

    try:
        df = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "true")
            .option("multiLine", "true")
            .option("escape", '"')
            .csv(csv_path)
        )
        row_count = df.count()

        writer = (
            df.write
            .format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .option("delta.enableChangeDataFeed", "true")
        )
        if row_count >= 5000 and partition_cols:
            writer = writer.partitionBy(*partition_cols)

        writer.saveAsTable(table_name)
        spark.sql(f"COMMENT ON TABLE {table_name} IS '{description}'")
        spark.sql(f"OPTIMIZE {table_name}")

        final = spark.table(table_name).count()
        loaded_tables[table_name] = final
        print(f"  ✅ {final:,} rows → {table_name}")
    except Exception as e:
        print(f"  ❌ {table_name}: {e}")

print()
print(f"Loaded {len(loaded_tables)} table(s) totalling {sum(loaded_tables.values()):,} rows.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Register UC functions
# MAGIC
# MAGIC Three Python UDFs that Genie Code can call via the UC Functions MCP server.
# MAGIC These wrap realistic logic over the energy tables loaded in Step 2.
# MAGIC
# MAGIC | Function | Returns | Purpose |
# MAGIC |----------|---------|---------|
# MAGIC | `calculate_peak_demand` | `STRUCT<peak_mw, peak_time>` | Highest demand MW + timestamp in a date range and region |
# MAGIC | `get_outage_summary` | `STRUCT<count, total_saidi>` | Outage count + total SAIDI minutes for a region over N days |
# MAGIC | `lookup_asset_status` | `STRUCT<condition_score, last_inspection>` | Latest condition score and inspection date for an asset |

# COMMAND ----------

# ── calculate_peak_demand ─────────────────────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_peak_demand(
    start_date DATE    COMMENT 'Start of the date range (inclusive)',
    end_date   DATE    COMMENT 'End of the date range (inclusive)',
    region     STRING  COMMENT 'Network region e.g. VIC, NSW, QLD, SA, TAS'
)
RETURNS STRUCT<peak_mw: DOUBLE, peak_time: TIMESTAMP>
COMMENT 'Returns the highest total demand MW and its timestamp for a region in a given date range. Aggregates 30-minute meter intervals.'
LANGUAGE PYTHON
AS $$
import datetime

# Build a simple SQL query over the meter_readings table via Spark SQL
# The function runs on the serverless driver — we use the pre-loaded catalog context.
try:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    catalog = "{CATALOG}"
    schema  = "{SCHEMA}"

    result = spark.sql(f"""
        SELECT
            DATE_TRUNC('HOUR', reading_time) AS hour_bucket,
            SUM(interval_kwh) / 0.5          AS total_mw
        FROM   {{catalog}}.{{schema}}.meter_readings
        WHERE  DATE(reading_time) BETWEEN DATE('{{start_date}}') AND DATE('{{end_date}}')
          AND  UPPER(region) = UPPER('{{region}}')
        GROUP  BY 1
        ORDER  BY total_mw DESC
        LIMIT  1
    """).collect()

    if not result:
        return {"peak_mw": None, "peak_time": None}

    row = result[0]
    return {
        "peak_mw":   round(float(row["total_mw"]), 2),
        "peak_time": row["hour_bucket"],
    }
except Exception as exc:
    raise ValueError(f"calculate_peak_demand error: {{exc}}")
$$
""")
print(f"✅ {CATALOG}.{SCHEMA}.calculate_peak_demand registered")

# COMMAND ----------

# ── get_outage_summary ────────────────────────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_outage_summary(
    region STRING  COMMENT 'Network region e.g. VIC, NSW, QLD, SA, TAS',
    days   INT     COMMENT 'Number of days to look back from today'
)
RETURNS STRUCT<count: INT, total_saidi: DOUBLE>
COMMENT 'Returns the number of outage events and total SAIDI minutes for a region over the last N days.'
LANGUAGE PYTHON
AS $$
try:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    catalog = "{CATALOG}"
    schema  = "{SCHEMA}"

    result = spark.sql(f"""
        SELECT
            COUNT(*)              AS event_count,
            COALESCE(SUM(saidi_minutes), 0) AS total_saidi
        FROM   {{catalog}}.{{schema}}.outage_events
        WHERE  UPPER(region) = UPPER('{{region}}')
          AND  start_time >= CURRENT_DATE - INTERVAL {{days}} DAYS
    """).collect()

    if not result:
        return {"count": 0, "total_saidi": 0.0}

    row = result[0]
    return {
        "count":       int(row["event_count"]),
        "total_saidi": round(float(row["total_saidi"]), 2),
    }
except Exception as exc:
    raise ValueError(f"get_outage_summary error: {{exc}}")
$$
""")
print(f"✅ {CATALOG}.{SCHEMA}.get_outage_summary registered")

# COMMAND ----------

# ── lookup_asset_status ───────────────────────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.lookup_asset_status(
    asset_id STRING COMMENT 'Asset identifier from energy_assets.asset_id'
)
RETURNS STRUCT<condition_score: INT, last_inspection: DATE>
COMMENT 'Returns the current condition score (1–10) and the date of the last recorded inspection for an asset. Joins energy_assets to maintenance_work_orders.'
LANGUAGE PYTHON
AS $$
try:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    catalog = "{CATALOG}"
    schema  = "{SCHEMA}"

    result = spark.sql(f"""
        SELECT
            a.condition_score,
            MAX(DATE(w.completion_date)) AS last_inspection
        FROM   {{catalog}}.{{schema}}.energy_assets a
        LEFT   JOIN {{catalog}}.{{schema}}.maintenance_work_orders w
               ON a.asset_id = w.asset_id
        WHERE  a.asset_id = '{{asset_id}}'
        GROUP  BY a.condition_score
        LIMIT  1
    """).collect()

    if not result:
        return {"condition_score": None, "last_inspection": None}

    row = result[0]
    return {
        "condition_score":  int(row["condition_score"]) if row["condition_score"] is not None else None,
        "last_inspection":  row["last_inspection"],
    }
except Exception as exc:
    raise ValueError(f"lookup_asset_status error: {{exc}}")
$$
""")
print(f"✅ {CATALOG}.{SCHEMA}.lookup_asset_status registered")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Grant EXECUTE on UC functions to participants

# COMMAND ----------

raw_emails   = dbutils.widgets.get("participant_emails")
participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

FUNCTIONS = [
    f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
    f"{CATALOG}.{SCHEMA}.get_outage_summary",
    f"{CATALOG}.{SCHEMA}.lookup_asset_status",
]

if not participants:
    print("No participant emails provided — skipping grants.")
    print("Enter emails in the 'participant_emails' widget and re-run this cell.")
else:
    print(f"Granting EXECUTE to {len(participants)} participant(s):\n")

    # Base grants needed to reach the functions
    base_grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.audit TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.audit TO",
    ]

    ok = err = 0
    for email in participants:
        for grant_prefix in base_grants:
            try:
                spark.sql(f"{grant_prefix} `{email}`")
                ok += 1
            except Exception as e:
                print(f"  ⚠️  {email} base grant: {e}")
                err += 1

        for fn_fqn in FUNCTIONS:
            stmt = f"GRANT EXECUTE ON FUNCTION {fn_fqn} TO `{email}`"
            try:
                spark.sql(stmt)
                ok += 1
            except Exception as e:
                print(f"  ⚠️  {email} EXECUTE on {fn_fqn.split('.')[-1]}: {e}")
                err += 1

        print(f"  ✅ {email}")

    print(f"\n{ok} grants applied ({err} errors)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Smoke test — call each function

# COMMAND ----------

print("Smoke testing UC functions...\n")

smoke_ok = True

# Test 1: calculate_peak_demand
try:
    result = spark.sql(f"""
        SELECT {CATALOG}.{SCHEMA}.calculate_peak_demand(
            CURRENT_DATE - INTERVAL 30 DAYS,
            CURRENT_DATE,
            'VIC'
        ) AS peak
    """).collect()[0]["peak"]
    print(f"✅ calculate_peak_demand: peak_mw={result['peak_mw']}, peak_time={result['peak_time']}")
except Exception as e:
    print(f"❌ calculate_peak_demand: {e}")
    smoke_ok = False

# Test 2: get_outage_summary
try:
    result = spark.sql(f"""
        SELECT {CATALOG}.{SCHEMA}.get_outage_summary('NSW', 90) AS summary
    """).collect()[0]["summary"]
    print(f"✅ get_outage_summary:    count={result['count']}, total_saidi={result['total_saidi']}")
except Exception as e:
    print(f"❌ get_outage_summary: {e}")
    smoke_ok = False

# Test 3: lookup_asset_status — pick a real asset_id from the table
try:
    first_asset = spark.sql(f"SELECT asset_id FROM {CATALOG}.{SCHEMA}.energy_assets LIMIT 1").collect()[0][0]
    result = spark.sql(f"""
        SELECT {CATALOG}.{SCHEMA}.lookup_asset_status('{first_asset}') AS status
    """).collect()[0]["status"]
    print(f"✅ lookup_asset_status:   condition_score={result['condition_score']}, last_inspection={result['last_inspection']}")
except Exception as e:
    print(f"❌ lookup_asset_status: {e}")
    smoke_ok = False

print()
if smoke_ok:
    print("✅ All three UC functions are working.")
else:
    print("⚠️  One or more functions failed. Check that energy tables are loaded (Step 2).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Skills directory paths for participants

# COMMAND ----------

print("=" * 70)
print("  SKILLS DIRECTORY PATHS — share these with participants")
print("=" * 70)
print()
print("  Skills are SKILL.md files inside named subdirectories.")
print("  Two storage locations:")
print()
print("  Personal (visible to you only):")
print("    /Users/{your-email}/.assistant/skills/{skill-name}/SKILL.md")
print()
print("  Workspace (visible to all users — set by admin):")
print("    /Workspace/.assistant/skills/{skill-name}/SKILL.md")
print()
print("  Three skills participants create in Lab 02:")
print()
print("    energy-analytics/SKILL.md")
print("    regulatory-compliance/SKILL.md")
print("    genie-space-creator/SKILL.md")
print()
print("  To find your username:")
print("    spark.sql(\"SELECT current_user()\").show()")
print()
print("  Full example path for energy-analytics:")
print("    /Users/<your-email>/.assistant/skills/energy-analytics/SKILL.md")
print()
print(f"  UC Functions registered in {CATALOG}.{SCHEMA}:")
for fn in FUNCTIONS:
    print(f"    {fn}")
print()
print("=" * 70)
print("  Session 5 setup complete. Ready for labs.")
print("=" * 70)
