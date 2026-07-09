# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">MCP Agents Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 4 pre-requisite — run this BEFORE the labs</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 4.**
# MAGIC
# MAGIC It:
# MAGIC 1. Creates the `workshop_au.aemo` catalog and schema
# MAGIC 2. Loads six AEMO tables from DBFS
# MAGIC 3. Sets column comments for Genie / MCP query quality
# MAGIC 4. Checks your Provisioned Throughput endpoint is `READY`
# MAGIC 5. Grants participant access (SELECT + CREATE TABLE — needed for MCP agent tools)
# MAGIC 6. Prints MCP endpoint URLs for the labs
# MAGIC
# MAGIC Expected runtime: ~5 minutes

# COMMAND ----------

dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",           "workshop_au",             "Catalog")
dbutils.widgets.text("schema_aemo",       "aemo",                    "AEMO schema")
dbutils.widgets.text("pt_endpoint",       "au_east_llm_inregion",    "PT endpoint name")
dbutils.widgets.text("vs_endpoint",       "workshop_vs",             "Vector Search endpoint name")
dbutils.widgets.text("genie_space_id",    "",                        "Genie Space ID (optional — for MCP URL)")
dbutils.widgets.text("participant_emails","",                        "Participant emails (comma-separated)")
dbutils.widgets.text("data_path",         "dbfs:/tmp/au_workshop/sample_data/aemo", "DBFS path to AEMO CSVs")

CATALOG          = dbutils.widgets.get("catalog")
SCHEMA_AEMO      = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT      = dbutils.widgets.get("pt_endpoint")
VS_ENDPOINT      = dbutils.widgets.get("vs_endpoint")
GENIE_SPACE_ID   = dbutils.widgets.get("genie_space_id").strip()
DATA_PATH        = dbutils.widgets.get("data_path")

# Extract workspace URL and PAT from the running notebook context
ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST  = ctx.apiUrl().get().rstrip("/")  # strip trailing slash for clean URL joins
TOKEN = ctx.apiToken().get()  # notebook-scoped token, not a PAT

print(f"Catalog    : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint: {PT_ENDPOINT}")
print(f"VS endpoint: {VS_ENDPOINT}")
print(f"Data path  : {DATA_PATH}")
print()
print("Upload AEMO CSVs to DBFS first if not already there:")
print(f"  databricks fs cp -r ./data/sample_data/aemo/ {DATA_PATH}/")

# COMMAND ----------

# Preflight: verify DBFS data path is populated before starting
try:
    files     = dbutils.fs.ls(DATA_PATH)
    csv_files = [f.name for f in files if f.name.endswith(".csv")]  # ignore non-CSV files
    if len(csv_files) < 6:
        raise FileNotFoundError(f"Only {len(csv_files)} CSV(s) found at {DATA_PATH}; need 6.")
    print(f"Preflight OK: {len(csv_files)} CSV files found at {DATA_PATH}")
except Exception as exc:
    raise RuntimeError(
        f"STOP: Cannot read data from {DATA_PATH}:\n  {exc}\n\n"
        f"Upload CSVs first (from the repo root):\n"
        f"  databricks fs cp -r ./data/sample_data/aemo/ {DATA_PATH}/"
    ) from exc

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create catalog and schema

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} COMMENT 'AU AI Workshops — energy sector sample data'")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA_AEMO} COMMENT 'AEMO NEM wholesale market data for Session 4 MCP labs'")
print(f"✅ {CATALOG}.{SCHEMA_AEMO} ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Load AEMO tables from DBFS CSV

# COMMAND ----------

# Six AEMO tables: (table_name, partition_cols, table_description)
AEMO_TABLES = [
    (
        "dispatch_intervals",
        ["region_id", "fuel_type"],
        "NEM 5-minute dispatch intervals — coal/gas/wind/solar/hydro/battery generators",
    ),
    (
        "spot_prices",
        ["region_id"],
        "NEM 30-minute spot prices (RRP) and FCAS prices per region",
    ),
    (
        "market_notices",
        [],
        "AEMO market notices including LOR1/LOR2/LOR3 reserve events and system normal",
    ),
    (
        "generator_registration",
        ["region_id", "fuel_type"],
        "NEM registered generator data — capacity, ramp rates, participant details",
    ),
    (
        "constraint_sets",
        ["constraint_type"],
        "NEM constraint activations — thermal, voltage and stability constraints",
    ),
    (
        "settlement_amounts",
        ["run_type"],
        "Weekly NEM settlement amounts by participant — energy, FCAS, interconnector residue",
    ),
]

results = []
for table_name, partitions, description in AEMO_TABLES:
    fqn  = f"{CATALOG}.{SCHEMA_AEMO}.{table_name}"
    path = f"{DATA_PATH}/{table_name}.csv"
    try:
        # Read CSV; multiLine+escape handles quoted fields with embedded newlines
        df = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "true")
            .option("multiLine", "true")
            .option("escape", '"')
            .csv(path)
        )
        row_count = df.count()

        # CDF enabled so the VS Delta Sync index can track row-level changes
        writer = (
            df.write
            .format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .option("delta.enableChangeDataFeed", "true")
        )
        # Only partition large tables; small ones don't benefit from partitioning
        if row_count >= 2000 and partitions:
            writer = writer.partitionBy(*partitions)
        writer.saveAsTable(fqn)

        spark.sql(f"COMMENT ON TABLE {fqn} IS '{description}'")

        final = spark.table(fqn).count()
        results.append(("✅", table_name, f"{final:,} rows"))
    except Exception as e:
        results.append(("❌", table_name, str(e)[:160]))

for icon, tbl, msg in results:
    print(f"{icon} {tbl}: {msg}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2b: Shift sample dates to "now"
# MAGIC The sample CSVs carry fixed 2025 dates. So that relative-time queries
# MAGIC ("last 30 days", "yesterday") work **whenever** the workshop is run, shift every
# MAGIC date/timestamp column forward by one global offset so the latest operational
# MAGIC interval lands on today. Genie and the UC functions both depend on this. Re-run
# MAGIC the loader (Step 2) before re-shifting if you run setup more than once.

# COMMAND ----------

# (table, column, date_only?) for every temporal column across the AEMO tables.
DATE_COLUMNS = [
    ("spot_prices",        "settlement_date",      False),
    ("dispatch_intervals", "settlement_date",      False),
    ("market_notices",     "issue_time",           False),
    ("market_notices",     "effective_date",       False),
    ("settlement_amounts", "settlement_date",      True),
    ("constraint_sets",    "activated_datetime",   False),
    ("constraint_sets",    "deactivated_datetime", False),
]

# One global offset (days), computed from the newest operational interval, so all
# tables keep their relative timing after the shift.
offset = spark.sql(
    f"SELECT datediff(current_date(), max(to_date(settlement_date))) AS d "
    f"FROM {CATALOG}.{SCHEMA_AEMO}.spot_prices"
).collect()[0]["d"]

if offset and offset > 0:
    for table, col, date_only in DATE_COLUMNS:
        fqn  = f"{CATALOG}.{SCHEMA_AEMO}.{table}"
        expr = f"date_add({col}, {offset})" if date_only else f"{col} + make_dt_interval({offset})"
        try:
            spark.sql(f"UPDATE {fqn} SET {col} = {expr} WHERE {col} IS NOT NULL")
        except Exception as e:
            print(f"  ⚠️  {table}.{col}: {e}")
    print(f"✅ Shifted all sample dates forward by {offset} days — latest interval is now ~today")
else:
    print(f"Sample data already current (offset={offset}); no shift applied")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Set column comments

# COMMAND ----------

COLUMN_COMMENTS = {
    f"{CATALOG}.{SCHEMA_AEMO}.spot_prices": {
        "settlement_date": "Trading interval end time. 30-minute intervals. AEST/AEDT timezone. Use DATE(settlement_date) to filter by day.",
        "region_id":       "NEM region. Must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix.",
        "rrp":             "Regional Reference Price in $/MWh. Normal range $50–$200. Market cap $15,300/MWh. Floor -$1,000/MWh. Negative = oversupply.",
        "raise_6sec":      "6-second raise FCAS price. Hide unless FCAS analysis is needed.",
        "lower_6sec":      "6-second lower FCAS price. Hide unless FCAS analysis is needed.",
        "total_demand_mw": "Total scheduled demand for the region in MW.",
        "net_interchange": "Net MW flow between regions. Positive = exporting.",
        "scheduled_generation": "Total scheduled generation in the region in MW.",
    },
    f"{CATALOG}.{SCHEMA_AEMO}.dispatch_intervals": {
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
    f"{CATALOG}.{SCHEMA_AEMO}.market_notices": {
        "notice_id":      "Unique identifier for the market notice.",
        "notice_type":    "LOR1 = reserve watch. LOR2 = shortfall threatened. LOR3 = imminent critical shortage. Use LIKE 'LOR%' to match all LOR types.",
        "issue_time":     "When AEMO published the notice. Use to filter recent events.",
        "reason":         "Free-text description. Use SUBSTRING(reason, 1, 200) for summaries.",
        "effective_date": "When the notice takes effect.",
        "region_id":      "NEM region. NULL means NEM-wide notice.",
        "intervention":   "True if this is an AEMO market intervention.",
    },
    f"{CATALOG}.{SCHEMA_AEMO}.generator_registration": {
        "duid":                   "Dispatchable Unit Identifier. Primary key. Join to dispatch_intervals.duid.",
        "station_name":           "Human-readable station name.",
        "participant_id":         "Market participant code.",
        "region_id":              "NEM region where registered.",
        "fuel_type":              "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "registered_capacity_mw": "Maximum registered capacity in MW.",
        "dispatch_type":          "GENERATOR, LOAD, or BIDIRECTIONAL.",
        "max_ramp_rate":          "Maximum ramp rate in MW per minute.",
        "min_load":               "Minimum stable load in MW.",
    },
    f"{CATALOG}.{SCHEMA_AEMO}.settlement_amounts": {
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

# Apply per-column comments so Genie/MCP can surface accurate field descriptions
ok = err = 0
for table_fqn, columns in COLUMN_COMMENTS.items():
    for col, comment in columns.items():
        try:
            spark.sql(f"ALTER TABLE {table_fqn} ALTER COLUMN `{col}` COMMENT '{comment}'")
            ok += 1
        except Exception as e:
            print(f"  ⚠️  {table_fqn.split('.')[-1]}.{col}: {e}")
            err += 1

print(f"✅ {ok} column comments set ({err} errors)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Check Provisioned Throughput endpoint
# MAGIC
# MAGIC Session 4 agents call the PT endpoint directly (not pay-per-token cross-geo models).
# MAGIC The endpoint must exist and be in `READY` state before participants start Lab 03.

# COMMAND ----------

import requests

def check_pt_endpoint(endpoint_name: str, host: str, token: str) -> None:
    # Serving endpoints REST API — no SDK wrapper needed for a simple status check
    url     = f"{host}/api/2.0/serving-endpoints/{endpoint_name}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp    = requests.get(url, headers=headers)

    if resp.status_code == 404:
        print(f"❌ PT endpoint '{endpoint_name}' NOT FOUND.")
        print()
        print("  How to deploy it:")
        print("  ─────────────────────────────────────────────────────────────────")
        print("  1. Open the Databricks workspace in your browser.")
        print("  2. Go to: Serving (left sidebar) → Create serving endpoint")
        print("  3. Name:   enter your endpoint name (e.g. au_east_llm_inregion)")
        print("  4. Entity: choose 'Foundation model'")
        print("  5. Model:  select 'databricks-claude-haiku-4-5'")
        print("  6. Provisioned throughput: tick the PT checkbox")
        print("  7. Scale-to-zero: disable (keep warm for the workshop)")
        print("  8. Click 'Create' and wait ~5–10 min for state = READY")
        print()
        print("  Re-run this cell once the endpoint is READY.")
        return

    if resp.status_code != 200:
        print(f"⚠️  Could not query endpoint: HTTP {resp.status_code} {resp.text[:200]}")
        return

    data  = resp.json()
    state = data.get("state", {}).get("ready", "UNKNOWN")  # nested under "state.ready"
    model = None
    try:
        # Path varies; guard against missing keys for non-FM endpoints
        model = data["config"]["served_entities"][0]["foundation_model"]["name"]
    except Exception:
        pass

    if state == "READY":
        print(f"✅ PT endpoint '{endpoint_name}' is READY.")
        if model:
            print(f"   Model: {model}")
    else:
        print(f"⚠️  PT endpoint '{endpoint_name}' exists but state = {state}.")
        print("   Wait for it to reach READY before starting Lab 03.")
        print(f"   Check: {host}/ml/endpoints/{endpoint_name}")


check_pt_endpoint(PT_ENDPOINT, HOST, TOKEN)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Grant participant access
# MAGIC
# MAGIC Grants:
# MAGIC - `USE CATALOG` — required to address tables
# MAGIC - `USE SCHEMA` — required for schema-scoped queries
# MAGIC - `SELECT` on aemo schema — MCP UC Functions server reads these tables
# MAGIC - `CREATE TABLE` on aemo schema — MCP agent write tools need this

# COMMAND ----------

raw_emails = dbutils.widgets.get("participant_emails")
# Normalise to lowercase; skip blank entries from trailing commas
participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

if not participants:
    print("No participant emails provided — skipping grants.")
    print("Enter emails in the 'participant_emails' widget and re-run this cell.")
else:
    print(f"Granting access to {len(participants)} participant(s):\n")

    # Four grants needed: catalog navigation + schema navigation + read + write
    grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
        f"GRANT CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
    ]

    ok = err = 0
    for email in participants:
        for grant_prefix in grants:
            stmt = f"{grant_prefix} `{email}`"  # backtick-quote email for UC identity
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
    print(f"  • Query all tables in {CATALOG}.{SCHEMA_AEMO}")
    print(f"  • Use the UC Functions MCP server backed by those tables")
    print(f"  • Run MCP agent tools that write (CREATE TABLE) to the schema")

# COMMAND ----------

# Verify grants
if participants:
    print(f"Current grants on {CATALOG}.{SCHEMA_AEMO}:")
    display(spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.{SCHEMA_AEMO}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6a: Create Vector Search endpoint and index
# MAGIC
# MAGIC Creates the `workshop_vs` endpoint (if missing) and a Delta Sync index on
# MAGIC `market_notices.reason` using `databricks-gte-large-en` embeddings.
# MAGIC Allow **5–10 minutes** for the index to reach ONLINE status.

# COMMAND ----------

import time
import datetime
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointStatusState, EndpointType,
    DeltaSyncVectorIndexSpecRequest, EmbeddingSourceColumn,
    VectorIndexType, PipelineType,
)

ws_sdk = WorkspaceClient()  # uses env/profile auth; no explicit token needed
VS_INDEX_NAME  = f"{CATALOG}.{SCHEMA_AEMO}.aemo_market_notices_index"
EMBEDDING_MODEL = "databricks-gte-large-en"  # in-region embedding model for AU East

# Enable CDF on source table (required for Delta Sync index)
spark.sql(
    f"ALTER TABLE {CATALOG}.{SCHEMA_AEMO}.market_notices "
    f"SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
)
print(f"CDF enabled on {CATALOG}.{SCHEMA_AEMO}.market_notices")

# Create endpoint if missing; get_endpoint raises if it doesn't exist
try:
    ep = ws_sdk.vector_search_endpoints.get_endpoint(VS_ENDPOINT)
    print(f"VS endpoint '{VS_ENDPOINT}' exists (state={ep.endpoint_status.state})")
except Exception:
    print(f"Creating VS endpoint '{VS_ENDPOINT}'...")
    ws_sdk.vector_search_endpoints.create_endpoint_and_wait(
        name=VS_ENDPOINT,
        endpoint_type=EndpointType.STANDARD,  # STANDARD supports both sync and delta-sync
        timeout=datetime.timedelta(minutes=20),
    )

# Poll until ONLINE — provisioning typically takes 3–5 min; 40×30 s = 20 min max
for _ in range(40):
    ep = ws_sdk.vector_search_endpoints.get_endpoint(VS_ENDPOINT)
    if ep.endpoint_status.state == EndpointStatusState.ONLINE:
        print(f"VS endpoint ONLINE.")
        break
    print(f"  waiting... state={ep.endpoint_status.state}")
    time.sleep(30)  # 30-second poll interval
else:
    raise RuntimeError(f"Endpoint '{VS_ENDPOINT}' not ONLINE after 20 min.")

# Re-use existing index if present; otherwise create with delta_sync spec
try:
    ws_sdk.vector_search_indexes.get_index(index_name=VS_INDEX_NAME)
    print(f"VS index exists — triggering sync.")
    ws_sdk.vector_search_indexes.sync_index(index_name=VS_INDEX_NAME)  # refresh embeddings
except Exception:
    ws_sdk.vector_search_indexes.create_index(
        name=VS_INDEX_NAME,
        endpoint_name=VS_ENDPOINT,
        index_type=VectorIndexType.DELTA_SYNC,  # syncs automatically from Delta table
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=f"{CATALOG}.{SCHEMA_AEMO}.market_notices",
            primary_key="notice_id",  # must be unique; drives upsert/delete
            pipeline_type=PipelineType.TRIGGERED,  # manual sync, not continuous
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="reason",  # free-text field to embed for semantic search
                    embedding_model_endpoint_name=EMBEDDING_MODEL,
                )
            ],
        ),
    )
    print(f"VS index creation triggered. Polling for ONLINE status (max 20 min)...")

# Poll until ready_for_search — initial backfill can take up to 10 min
for _ in range(40):
    idx_info = ws_sdk.vector_search_indexes.get_index(index_name=VS_INDEX_NAME)
    ready    = getattr(idx_info.status, "ready_for_search", False)  # attr absent until ONLINE
    if ready:
        print(f"VS index ONLINE and ready for search.")
        break
    print(f"  waiting... index not yet ready")
    time.sleep(30)
else:
    raise RuntimeError(
        f"VS index '{VS_INDEX_NAME}' not ONLINE after 20 min. "
        f"Check the Vector Search UI for errors."
    )

print(f"\nVS index name: {VS_INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6b: Register UC Functions for NEM calculations
# MAGIC
# MAGIC Registers three functions in `{CATALOG}.{SCHEMA_AEMO}` and grants EXECUTE
# MAGIC to all participant emails. Lab 02 and Lab 03 discover these via the UC
# MAGIC Functions MCP server.

# COMMAND ----------

# calculate_peak_demand: single-day aggregation of spot prices + dispatch for one region
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA_AEMO}.calculate_peak_demand(
    region STRING COMMENT 'NEM region code. Values: NSW1, VIC1, QLD1, SA1, TAS1',
    date   STRING COMMENT 'Date in YYYY-MM-DD format (AEST)'
)
RETURNS STRING
COMMENT 'Calculate peak spot price and total dispatch for a NEM region on a given date.
Returns JSON: region, date, peak_price_mwh, peak_interval, avg_price_mwh, total_dispatch_mw.
Not for trend analysis over time windows (use Genie for those).'
LANGUAGE SQL
RETURN (
    -- Price and dispatch are aggregated in separate CTEs and combined via a
    -- 1-row CROSS JOIN. (A correlated dispatch subquery nested inside the
    -- aggregate SELECT trips SCALAR_SUBQUERY_IS_IN_GROUP_BY_OR_AGGREGATE_FUNCTION.)
    WITH price AS (
        SELECT round(max(rrp), 2)                              AS peak_price_mwh,
               cast(max_by(settlement_date, rrp) AS STRING)    AS peak_interval,
               round(avg(rrp), 2)                              AS avg_price_mwh
        FROM   {CATALOG}.{SCHEMA_AEMO}.spot_prices
        WHERE  region_id = region AND date(settlement_date) = date
    ),
    disp AS (
        SELECT round(coalesce(sum(dispatch_mw), 0.0), 1)       AS total_dispatch_mw
        FROM   {CATALOG}.{SCHEMA_AEMO}.dispatch_intervals
        WHERE  region_id = region AND date(settlement_date) = date
    )
    SELECT to_json(named_struct(
        'region',            region,
        'date',              date,
        'peak_price_mwh',    price.peak_price_mwh,
        'peak_interval',     price.peak_interval,
        'avg_price_mwh',     price.avg_price_mwh,
        'total_dispatch_mw', disp.total_dispatch_mw
    ))
    FROM price CROSS JOIN disp
)
""")

# get_region_summary: rolling-window stats; CTEs split price/fuel work before joining
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA_AEMO}.get_region_summary(
    region STRING COMMENT 'NEM region code. Values: NSW1, VIC1, QLD1, SA1, TAS1',
    days   INT    COMMENT 'Rolling window in days. Typical: 7, 30, 90'
)
RETURNS STRING
COMMENT 'Return JSON summary of NEM region for a rolling window: avg_price_mwh,
spike_count (>$300/MWh), peak_demand_interval, top_3_fuel_types.
Not for single-day spot prices (use calculate_peak_demand). Not for market notices.'
LANGUAGE SQL
RETURN (
    -- Each aggregate lives in its own CTE and the single-row results are
    -- combined with CROSS JOIN, so no aggregate/scalar-subquery nesting.
    WITH sp AS (
        SELECT *
        FROM   {CATALOG}.{SCHEMA_AEMO}.spot_prices
        WHERE  region_id = region
        AND    settlement_date >= date_sub(current_date(), days)
    ),
    price_agg AS (
        SELECT round(avg(rrp), 2)                                        AS avg_price_mwh,
               cast(sum(case when rrp > 300 then 1 else 0 end) AS INT)   AS spike_count,  -- $300/MWh threshold
               cast(max_by(settlement_date, rrp) AS STRING)             AS peak_demand_interval
        FROM   sp
    ),
    fuel AS (
        -- Top-3 fuel types by total MW dispatched in the window
        SELECT fuel_type, sum(dispatch_mw) AS total_mw
        FROM   {CATALOG}.{SCHEMA_AEMO}.dispatch_intervals
        WHERE  region_id = region
        AND    settlement_date >= date_sub(current_date(), days)
        GROUP  BY fuel_type
        ORDER  BY total_mw DESC
        LIMIT  3
    ),
    grand AS (SELECT sum(total_mw) AS grand_total FROM fuel),  -- denominator for % share
    fuel_json AS (
        SELECT collect_list(named_struct(
                   'fuel_type', fuel.fuel_type,
                   'pct',       round(fuel.total_mw / grand.grand_total * 100, 1)
               )) AS top_fuel_types
        FROM fuel CROSS JOIN grand  -- CROSS JOIN is safe: grand is 1 row
    )
    SELECT to_json(named_struct(
        'region',               region,
        'days',                 days,
        'avg_price_mwh',        price_agg.avg_price_mwh,
        'spike_count',          price_agg.spike_count,
        'peak_demand_interval', price_agg.peak_demand_interval,
        'top_fuel_types',       fuel_json.top_fuel_types
    ))
    FROM price_agg CROSS JOIN fuel_json
)
""")

# lookup_duid_info: point-lookup by DUID; LIMIT 1 guards against duplicate registrations
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA_AEMO}.lookup_duid_info(
    duid STRING COMMENT 'Dispatchable Unit Identifier e.g. TORRB1, PELICAN1'
)
RETURNS STRING
COMMENT 'Look up generator details by DUID. Returns JSON: duid, station_name,
participant_id, region_id, fuel_type, registered_capacity_mw, dispatch_type.
Not for searching by station name (use Genie for that).'
LANGUAGE SQL
RETURN (
    SELECT to_json(named_struct(
        'duid',                   gr.duid,
        'station_name',           gr.station_name,
        'participant_id',         gr.participant_id,
        'region_id',              gr.region_id,
        'fuel_type',              gr.fuel_type,
        'registered_capacity_mw', gr.registered_capacity_mw,
        'dispatch_type',          gr.dispatch_type
    ))
    FROM {CATALOG}.{SCHEMA_AEMO}.generator_registration gr
    WHERE gr.duid = duid
    LIMIT 1
)
""")

print(f"Registered 3 UC Functions in {CATALOG}.{SCHEMA_AEMO}")

# Grant EXECUTE on all three functions so participants can invoke them via MCP
raw_emails   = dbutils.widgets.get("participant_emails")
participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]
for fn in ["calculate_peak_demand", "get_region_summary", "lookup_duid_info"]:
    for email in participants:
        try:
            spark.sql(
                f"GRANT EXECUTE ON FUNCTION "
                f"{CATALOG}.{SCHEMA_AEMO}.{fn} TO `{email}`"
            )
        except Exception as exc:
            print(f"  {email}.{fn}: {exc}")

if participants:
    print(f"EXECUTE grants applied to {len(participants)} participant(s).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Smoke test — verify row counts

# COMMAND ----------

print("Table row counts:")
# Minimum row thresholds — lab queries need enough data to return non-trivial results
expected = {
    "dispatch_intervals":     5_000,
    "spot_prices":            1_000,
    "market_notices":           100,
    "generator_registration":    50,
    "constraint_sets":          200,
    "settlement_amounts":        100,
}

all_ok = True
for tbl, min_rows in expected.items():
    try:
        count = spark.table(f"{CATALOG}.{SCHEMA_AEMO}.{tbl}").count()
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
    print("✅ All tables loaded.")
else:
    print("⚠️  Some tables are empty or missing.")
    print(f"   Upload CSVs to {DATA_PATH}/ and re-run Step 2.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7: MCP endpoint URLs for participants

# COMMAND ----------

# UC Functions MCP URL: path = /functions/{catalog}/{schema}
uc_mcp_url    = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"
# Genie MCP URL requires a space ID; show a placeholder if not provided
genie_mcp_url = (
    f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
    if GENIE_SPACE_ID
    else f"{HOST}/api/2.0/mcp/genie/<SPACE_ID>"
)
# VS MCP URL: dot-separated index name is split into 3 path segments
vs_index_name = f"{CATALOG}.{SCHEMA_AEMO}.aemo_market_notices_index"
vs_parts      = vs_index_name.split(".")  # ["catalog", "schema", "index"]
vs_mcp_url    = f"{HOST}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"

print("=" * 70)
print("  MCP ENDPOINT URLS — share these with participants")
print("=" * 70)
print()
print(f"  UC Functions MCP server:")
print(f"    {uc_mcp_url}")
print()
print(f"  Genie MCP server:")
print(f"    {genie_mcp_url}")
if not GENIE_SPACE_ID:
    print()
    print("    (Enter your Genie Space ID in the 'genie_space_id' widget above")
    print("     to see the full URL. Find the ID in the browser URL when you")
    print("     open your Genie Space: .../genie/spaces/{id})")
print()
print(f"  Vector Search MCP server:")
print(f"    {vs_mcp_url}")
print()
print(f"  Vector Search index name (paste into Lab 02 'vs_index' widget):")
print(f"    {vs_index_name}")
print()
print(f"  Authentication for all MCP servers:")
print(f"    Header: Authorization: Bearer <personal-access-token>")
print(f"    PAT:    User Settings → Developer → Access tokens → Generate new token")
print()
print(f"  Workspace:  {HOST}")
print(f"  PT endpoint: {HOST}/ml/endpoints/{PT_ENDPOINT}")
print()
print("=" * 70)
print("  Session 4 setup complete. Ready for labs.")
print("=" * 70)
