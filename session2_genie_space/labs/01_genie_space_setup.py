# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 01: Create Your Genie Space</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 55 minutes |
# MAGIC | **Prerequisites** | AEMO tables loaded — run `session2_genie_space/setup/setup.py` first if not done by facilitator |
# MAGIC | **Covers** | Slides 9, 23–27 — Setup, UC Metadata, Metric Views, UC Functions, Knowledge Store |
# MAGIC
# MAGIC > **Before running any code cell:** confirm `workshop_au.aemo` tables exist — run the verify cell below. If tables are missing, ask your facilitator to run `session2_genie_space/setup/setup.py`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The mental model
# MAGIC
# MAGIC > *"Think of Genie as a brand new analyst. Brilliant at SQL, but knows nothing about your business. Everything they know comes from what you put in the space."*
# MAGIC
# MAGIC > ⚠️ **Prerequisite:** Both workspace settings must be ON before Genie works:
# MAGIC > Geography enforcement (Account Console → Security and compliance) + Partner-Powered AI Features (workspace settings). Never disable Partner-Powered — it kills Genie entirely.
# MAGIC
# MAGIC ## Genie Space structure (verified in UI)

# MAGIC ```
# MAGIC Top-level tabs: Chat | Monitor | Benchmark | Configure | Share
# MAGIC
# MAGIC Configure sub-tabs: About | Data | Instructions
# MAGIC
# MAGIC Instructions sub-tabs: Text | Joins | SQL Expressions | SQL Queries
# MAGIC ```
# MAGIC
# MAGIC ## Priority stack
# MAGIC
# MAGIC | Priority | Method | Why |
# MAGIC |---|---|---|
# MAGIC | **1st** | UC Metadata | First and best — column descriptions, PK/FK |
# MAGIC | **2nd** | Metric Views | Pre-defined measures with business names — Genie inherits definitions automatically |
# MAGIC | **3rd** | UC Functions | Reusable calculations Genie can call by name |
# MAGIC | **4th** | Knowledge Store | Synonyms, joins, entity matching |
# MAGIC | **5th** | Example SQL | Complex parameterised patterns |
# MAGIC | **Last** | Text Instructions | Universal rules only |

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID (from URL after creating)")
SPACE_ID = dbutils.widgets.get("genie_space_id")

CATALOG = "workshop_au"
SCHEMA  = "aemo"
HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print(f"Catalog: {CATALOG}.{SCHEMA}")
print(f"Space:   {SPACE_ID or '(create the space first, then paste ID here)'}")

# COMMAND ----------

# Verify AEMO tables exist before proceeding — STOP if any table is missing
REQUIRED_TABLES = [
    f"{CATALOG}.{SCHEMA}.spot_prices",
    f"{CATALOG}.{SCHEMA}.dispatch_intervals",
    f"{CATALOG}.{SCHEMA}.market_notices",
    f"{CATALOG}.{SCHEMA}.generator_registration",
    f"{CATALOG}.{SCHEMA}.settlement_amounts",
    f"{CATALOG}.{SCHEMA}.constraint_sets",
]

missing = []
for t in REQUIRED_TABLES:
    try:
        spark.sql(f"SELECT 1 FROM {t} LIMIT 1")
        print(f"  [OK] {t.split('.')[-1]}")
    except Exception:
        missing.append(t)
        print(f"  [MISSING] {t}")

if missing:
    raise RuntimeError(
        f"\n{len(missing)} table(s) missing in {CATALOG}.{SCHEMA}. "
        "Ask your facilitator to run session2_genie_space/setup/setup.py before continuing."
    )
else:
    print(f"\nAll {len(REQUIRED_TABLES)} tables present — ready to proceed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 0: Metric Views + Materialized Views
# MAGIC
# MAGIC **Why do this before creating the space?**
# MAGIC
# MAGIC Raw tables force Genie to infer what "revenue", "output", or "price spike" means from column
# MAGIC names alone. That guessing is where mistakes happen. Metric views and materialized views shift
# MAGIC that burden from Genie to you — you define the business logic once in SQL/YAML, and Genie
# MAGIC inherits it automatically every time someone asks a question.
# MAGIC
# MAGIC | Object | What it does | When to use |
# MAGIC |---|---|---|
# MAGIC | **Materialized view** | Pre-computes and caches an aggregation; refreshed on schedule | High-cardinality source tables where the same rollup is queried repeatedly |
# MAGIC | **Metric view** | Declares named measures + dimensions in YAML; Genie reads display names and synonyms directly | Any KPI that needs a consistent, governed definition across teams |
# MAGIC
# MAGIC > **Both are added to the Genie space the same way as a regular table:** Configure → Data → Add.
# MAGIC > They appear in the object picker alongside tables and views.
# MAGIC
# MAGIC > **Note:** setup.py has already created these objects (`nem_spot_metrics`, `daily_dispatch_summary`,
# MAGIC > `calculate_market_cap_exposure`) in `workshop_au.aemo` if your facilitator ran it before the
# MAGIC > session. The cells below use `CREATE OR REPLACE` / `CREATE ... IF NOT EXISTS` so it is safe to
# MAGIC > re-run them — they will produce identical objects whether setup.py ran or not.
# MAGIC
# MAGIC ### Step 0a: Create a Materialized View
# MAGIC
# MAGIC **🖱️ UI:** SQL Editor (left sidebar) → open a new query → paste the SQL below → Run → the MV appears in Catalog under `workshop_au.aemo`
# MAGIC
# MAGIC **⚡ Automated:**

# COMMAND ----------

# Step 0a — Materialized view: daily dispatch summary by fuel type and region.
# Pre-computes the SUM(dispatch_mw)/12 → MWh conversion that Genie would otherwise
# have to infer from raw 5-minute dispatch_intervals rows.
# Uses CREATE ... IF NOT EXISTS so that if setup.py already created this object, the
# existing rows are preserved rather than replaced.
# Requires DBR 17.3+ or a serverless SQL warehouse (Serverless Preview channel 2025.16+).

spark.sql(f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {CATALOG}.{SCHEMA}.daily_dispatch_summary
COMMENT 'Daily generation output by fuel type and region (MWh). Refreshed automatically. Use instead of dispatch_intervals for daily or weekly aggregation questions.'
AS
SELECT
    DATE(di.settlement_date)           AS dispatch_date,
    di.region_id,
    di.fuel_type,
    ROUND(SUM(di.dispatch_mw) / 12, 1) AS total_mwh,
    ROUND(AVG(di.dispatch_mw), 1)      AS avg_dispatch_mw
FROM {CATALOG}.{SCHEMA}.dispatch_intervals di
GROUP BY
    DATE(di.settlement_date),
    di.region_id,
    di.fuel_type
""")

print(f"✅ Materialized view ready: {CATALOG}.{SCHEMA}.daily_dispatch_summary")
print("   Columns: dispatch_date, region_id, fuel_type, total_mwh, avg_dispatch_mw")

# COMMAND ----------

# Verify the materialized view is queryable and has data
mv_df = spark.sql(f"""
SELECT fuel_type, region_id, SUM(total_mwh) AS total_mwh
FROM {CATALOG}.{SCHEMA}.daily_dispatch_summary
GROUP BY fuel_type, region_id
ORDER BY total_mwh DESC
LIMIT 10
""")
print(f"Materialized view row count (top-10 sample):")
mv_df.show(truncate=60)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 0b: Create a Metric View
# MAGIC
# MAGIC A metric view uses a special YAML-in-SQL syntax to declare named **measures** (aggregates) and
# MAGIC **dimensions** (group-by fields) with display names, synonyms, and format hints. Genie reads
# MAGIC these directly — so when someone asks "what was the average spot price in Victoria last week?"
# MAGIC Genie knows exactly which measure and dimension to use without guessing from column names.
# MAGIC
# MAGIC **🖱️ UI:** SQL Editor → new query → paste the SQL below → Run → metric view appears in Catalog
# MAGIC under `workshop_au.aemo` with a distinct icon
# MAGIC
# MAGIC **⚡ Automated:**

# COMMAND ----------

# Step 0b — Metric view: NEM spot price KPIs over spot_prices.
# Declares avg_spot_price and peak_spot_price as first-class named measures.
# Genie picks up display_name, synonyms, and format automatically.
# Uses CREATE OR REPLACE VIEW so the definition stays in sync whether or not
# setup.py created nem_spot_metrics before this cell ran.
# Requires DBR 17.3+ or Serverless SQL warehouse (Preview channel 2025.16+).
# Falls back to a regular view if WITH METRICS is not yet supported on this runtime.

METRIC_VIEW_FQN = f"{CATALOG}.{SCHEMA}.nem_spot_metrics"

METRIC_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {METRIC_VIEW_FQN}
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
comment: "NEM spot price metrics by region and trading interval. Use for price trend, spike analysis, and regional comparison questions."
source: {CATALOG}.{SCHEMA}.spot_prices

fields:
  - name: Region
    expr: region_id
    comment: "NEM region code: NSW1, VIC1, QLD1, SA1, TAS1"
    display_name: "NEM Region"
    synonyms: ["region", "state", "zone", "NEM region"]

  - name: Trading Date
    expr: DATE(settlement_date)
    comment: "Calendar date of the 30-minute trading interval"
    display_name: "Trading Date"
    synonyms: ["date", "day", "trading day", "interval date"]
    format: "date"

  - name: Trading Hour
    expr: HOUR(settlement_date)
    comment: "Hour of day (0–23) for the trading interval"
    display_name: "Hour of Day"
    synonyms: ["hour", "time of day"]

measures:
  - name: Avg Spot Price
    expr: ROUND(AVG(rrp), 2)
    comment: "Average Regional Reference Price in $/MWh across selected intervals"
    display_name: "Average Spot Price ($/MWh)"
    synonyms: ["average price", "spot price", "RRP", "price", "average RRP"]
    format: "number"

  - name: Peak Spot Price
    expr: ROUND(MAX(rrp), 2)
    comment: "Maximum Regional Reference Price ($/MWh) — identifies price spikes"
    display_name: "Peak Spot Price ($/MWh)"
    synonyms: ["peak price", "maximum price", "price spike", "highest price"]
    format: "number"

  - name: Price Spike Count
    expr: COUNT(CASE WHEN rrp > 5000 THEN 1 END)
    comment: "Number of 30-minute intervals where spot price exceeded $5,000/MWh"
    display_name: "Price Spike Count (>$5k/MWh)"
    synonyms: ["spikes", "high price events", "extreme prices", "price exceedances"]
    format: "number"

  - name: Interval Count
    expr: COUNT(*)
    comment: "Number of 30-minute trading intervals in the group."
    display_name: "Interval Count"
    format: "number"
$$
"""

METRIC_VIEW_FALLBACK_SQL = f"""
-- Fallback: regular view used because WITH METRICS is not yet supported on this runtime.
-- The query is logically equivalent; dimensions are baked into the GROUP BY.
CREATE OR REPLACE VIEW {METRIC_VIEW_FQN} AS
SELECT
    region_id,
    DATE(settlement_date)     AS trading_date,
    ROUND(AVG(rrp), 2)        AS avg_spot_price,
    ROUND(MAX(rrp), 2)        AS peak_spot_price,
    COUNT(*)                  AS interval_count,
    COUNT(CASE WHEN rrp > 5000 THEN 1 END) AS price_spike_count
FROM {CATALOG}.{SCHEMA}.spot_prices
GROUP BY region_id, DATE(settlement_date)
"""

try:
    spark.sql(METRIC_VIEW_SQL)
    print(f"✅ Metric view created (WITH METRICS / YAML syntax): {METRIC_VIEW_FQN}")
    print("   Measures: Avg Spot Price, Peak Spot Price, Price Spike Count, Interval Count")
    print("   Dimensions: Region, Trading Date, Trading Hour")
except Exception as e:
    err_msg = str(e)
    if "PARSE_SYNTAX_ERROR" in err_msg or "mismatched input" in err_msg.lower() or "with metrics" in err_msg.lower():
        print(f"  ℹ️  WITH METRICS not supported on this runtime — falling back to regular view")
        try:
            spark.sql(METRIC_VIEW_FALLBACK_SQL)
            print(f"✅ nem_spot_metrics created (regular view fallback)")
        except Exception as e2:
            print(f"❌ nem_spot_metrics: {e2}")
    else:
        print(f"❌ nem_spot_metrics: {err_msg[:200]}")

# COMMAND ----------

# Verify the metric view is queryable and that the WITH METRICS marker is present.
# We query nem_spot_metrics directly — not the underlying spot_prices table —
# so this cell fails fast if the view creation above did not succeed.

mv_check = spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.nem_spot_metrics LIMIT 5")
print(f"Metric view renders: {mv_check.count()} rows returned (first 5 shown)")
mv_check.show(truncate=60)

# Confirm the WITH METRICS marker is visible in the extended description.
# Look for 'Type' or 'Provider' rows that indicate metric view metadata.
desc_df = spark.sql(f"DESCRIBE EXTENDED {CATALOG}.{SCHEMA}.nem_spot_metrics")
metric_markers = desc_df.filter(
    desc_df["col_name"].contains("Type") |
    desc_df["col_name"].contains("Provider") |
    desc_df["col_name"].contains("View Text") |
    desc_df["col_name"].contains("Table Type")
).collect()

if metric_markers:
    print("\nMetric view metadata (DESCRIBE EXTENDED excerpts):")
    for row in metric_markers:
        print(f"  {row['col_name']}: {str(row['data_type'])[:120]}")
else:
    print("\n⚠️  No Type/Provider metadata found — view may have been created via the fallback path.")
    print("   This is fine for the lab; Genie will treat it as a regular view.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: UC Column Comments
# MAGIC
# MAGIC **🖱️ UI:** Catalog → workshop_au → aemo → [table] → **Overview tab** (not Columns tab) → hover over a column → click **Add comment** button that appears
# MAGIC
# MAGIC **⚡ Or run the cell below to automate all columns at once.**
# MAGIC The script uses `ALTER TABLE … ALTER COLUMN … COMMENT` — which replaces any existing comment.

# COMMAND ----------

# Automated: set all column comments in one run
# Replaces existing comments. Safe to re-run.

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
        "duid":            "Dispatchable Unit Identifier. Unique per generating unit. Join to generator_registration on duid for station_name and fuel_type.",
        "dispatch_mw":     "Actual MW dispatched in this 5-minute interval. Divide SUM(dispatch_mw)/12 to get MWh.",
        "initial_mw":      "Initial MW target at interval start.",
        "available_mw":    "MW available for dispatch.",
        "ramp_rate":       "Maximum ramp rate in MW per minute.",
        "fuel_type":       "Generation technology: solar, wind, coal, gas, hydro, battery. Group with CASE into Renewable (solar, wind) vs Fossil Fuel (coal, gas).",
        "station_name":    "Human-readable station name e.g. Bayswater, Loy Yang A.",
        "state":           "Australian state the unit is located in.",
    },
    f"{CATALOG}.{SCHEMA}.market_notices": {
        "notice_id":     "Unique identifier for the market notice.",
        "notice_type":   "LOR1 = reserve watch. LOR2 = shortfall threatened. LOR3 = imminent critical shortage. Use LIKE 'LOR%' to match all LOR types.",
        "issue_time":    "When AEMO published the notice. Use to filter recent events.",
        "reason":        "Free-text description of the notice. Use SUBSTRING(reason, 1, 200) for summaries.",
        "effective_date":"When the notice takes effect.",
        "region_id":     "NEM region. NULL means the notice applies NEM-wide.",
        "intervention":  "True if this is an AEMO intervention notice.",
    },
    f"{CATALOG}.{SCHEMA}.generator_registration": {
        "duid":                   "Dispatchable Unit Identifier. Primary key. Join to dispatch_intervals.duid.",
        "station_name":           "Human-readable station name.",
        "participant_id":         "Market participant code (company identifier).",
        "region_id":              "NEM region where registered.",
        "fuel_type":              "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "registered_capacity_mw": "Maximum registered capacity in MW.",
        "connection_point_id":    "NEM connection point identifier for the unit.",
        "dispatch_type":          "GENERATOR, LOAD, or BIDIRECTIONAL.",
        "max_ramp_rate":          "Maximum ramp rate in MW per minute.",
        "min_load":               "Minimum stable load in MW.",
    },
}
# settlement_amounts and constraint_sets: column comments are added in Lab 02
# alongside the Example SQL and Text Instructions steps.
# All other columns above match setup.py.

results = []
for table_fqn, columns in COLUMN_COMMENTS.items():
    for col, comment in columns.items():
        safe_comment = comment.replace("'", "\\'")
        sql = f"ALTER TABLE {table_fqn} ALTER COLUMN `{col}` COMMENT '{safe_comment}'"
        try:
            spark.sql(sql)
            results.append(("✅", table_fqn.split(".")[-1], col))
        except Exception as e:
            results.append(("❌", table_fqn.split(".")[-1], f"{col}: {e}"))

print(f"Set {sum(1 for r in results if r[0]=='✅')} column comments")
for icon, tbl, col in results:
    print(f"  {icon} {tbl}.{col}")

# COMMAND ----------

# Verify column comments landed — query system.information_schema.columns
# Shows all columns with a non-null comment in the 4 core Lab 01 tables.

VERIFY_TABLES = ["spot_prices", "dispatch_intervals", "market_notices", "generator_registration"]

verify_sql = f"""
SELECT table_name, column_name, comment
FROM   {CATALOG}.information_schema.columns
WHERE  table_schema = '{SCHEMA}'
  AND  table_name   IN ({', '.join(f"'{t}'" for t in VERIFY_TABLES)})
  AND  comment      IS NOT NULL
ORDER BY table_name, ordinal_position
"""

result_df = spark.sql(verify_sql)
print(f"Columns with comments: {result_df.count()}")
result_df.show(truncate=80)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Table-level descriptions
# MAGIC
# MAGIC **🖱️ UI:** Catalog → [table] → Overview tab → Edit description
# MAGIC
# MAGIC **⚡ Automated:**

# COMMAND ----------

TABLE_DESCRIPTIONS = {
    f"{CATALOG}.{SCHEMA}.spot_prices": (
        "NEM 30-minute trading interval spot prices. "
        "Key column: rrp = Regional Reference Price in $/MWh. "
        "Regions: NSW1, VIC1, QLD1, SA1, TAS1."
    ),
    f"{CATALOG}.{SCHEMA}.dispatch_intervals": (
        "NEM 5-minute generator dispatch data. "
        "Key columns: duid (join to generator_registration), dispatch_mw (divide by 12 for MWh), fuel_type. "
        "12 intervals = 1 hour."
    ),
    f"{CATALOG}.{SCHEMA}.market_notices": (
        "AEMO market and system notices including LOR events. "
        "Key column: notice_type (LOR1/LOR2/LOR3 = escalating lack-of-reserve severity). "
        "Filter: WHERE notice_type LIKE 'LOR%' for LOR events."
    ),
    f"{CATALOG}.{SCHEMA}.generator_registration": (
        "NEM registered generator details. "
        "Join to dispatch_intervals on duid to get station_name and fuel_type."
    ),
    f"{CATALOG}.{SCHEMA}.settlement_amounts": (
        "Weekly NEM settlement amounts by participant. "
        "run_type: FINAL = confirmed, PRELIMINARY = estimate. "
        "total_aud = net settlement amount in AUD."
    ),
    f"{CATALOG}.{SCHEMA}.constraint_sets": (
        "NEM network and system constraints. Activated when a network element is at risk. "
        "rhs_value = MW limit. Join region_affected to spot_prices.region_id."
    ),
    f"{CATALOG}.{SCHEMA}.daily_dispatch_summary": (
        "Materialized view: daily generation output by fuel type and region in MWh. "
        "Use for daily or weekly dispatch aggregation questions. "
        "Refreshed automatically from dispatch_intervals."
    ),
    f"{CATALOG}.{SCHEMA}.nem_spot_metrics": (
        "Metric view: NEM spot price KPIs with pre-defined measures. "
        "Use for average spot price, price spike count, and demand questions by region or date. "
        "Genie reads measure names and synonyms directly from this view."
    ),
}

for table_fqn, desc in TABLE_DESCRIPTIONS.items():
    safe_desc = desc.replace("'", "\\'")
    try:
        spark.sql(f"COMMENT ON TABLE {table_fqn} IS '{safe_desc}'")
        print(f"✅ {table_fqn.split('.')[-1]}")
    except Exception as e:
        print(f"❌ {table_fqn.split('.')[-1]}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Create the Space
# MAGIC
# MAGIC **🖱️ UI (do this first):** Left sidebar → **Genie Spaces** → click **+ New**
# MAGIC ```
# MAGIC 1. Pick tables — add ALL of the following:
# MAGIC    - spot_prices
# MAGIC    - dispatch_intervals
# MAGIC    - market_notices
# MAGIC    - generator_registration
# MAGIC    - daily_dispatch_summary   ← the materialized view from Step 0a
# MAGIC    - nem_spot_metrics         ← the metric view from Step 0b
# MAGIC    (generator_registration is required for the duid join in Step 4)
# MAGIC 2. Click Create
# MAGIC 3. Configure → About tab → set Title and Description:
# MAGIC    Title:       AEMO NEM Operations
# MAGIC    Description: Natural language access to NEM spot prices, dispatch data,
# MAGIC                 and market notices for the Market Operations team.
# MAGIC 4. Configure → About tab → set Warehouse: select your serverless warehouse
# MAGIC 5. Copy the Space ID from the browser URL bar  (…/genie/rooms/<SPACE_ID>)
# MAGIC 6. Paste into the widget at the top of this notebook
# MAGIC ```
# MAGIC
# MAGIC > **Note on the metric view in the UI:** After adding `nem_spot_metrics` via Configure → Data,
# MAGIC > you will see its declared measures (Avg Spot Price, Peak Spot Price, etc.) listed under the
# MAGIC > object — Genie has already read the YAML definitions. You do not need to add synonyms for these
# MAGIC > columns manually; they came from the `synonyms:` fields in the metric view YAML.
# MAGIC
# MAGIC **⚡ Verify the space is live:**

# COMMAND ----------

import requests, json

if SPACE_ID:
    resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=HEADERS)
    if resp.status_code == 200:
        s = resp.json()
        print(f"✅ Space: {s.get('title')}")
        print(f"   URL: https://{HOST}/genie/rooms/{SPACE_ID}")
    else:
        print(f"❌ {resp.status_code}: {resp.text[:200]}")
else:
    print("Enter Space ID in the widget above first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Knowledge Store — synonyms, entity matching, joins
# MAGIC
# MAGIC **🖱️ UI for synonyms:** Configure → Data → [table] → click **pen icon** next to column → **Synonyms** tab → Save
# MAGIC **🖱️ UI for entity matching:** Configure → Data → [table] → click **pen icon** next to column → **Advanced** → **Entity matching** → enable
# MAGIC **🖱️ UI for joins:** Configure → Instructions → **Joins** → + Add
# MAGIC
# MAGIC Synonyms and entity matching are set in the space UI — do these manually in the Configure tab.
# MAGIC The join relationship can also be set via the space settings API:

# COMMAND ----------

# Automated: add the join relationship via serialized_space PATCH
# Joins live inside serialized_space under instructions.join_specs (same as benchmarks/golden
# queries/text instructions in Lab 02).
# There is NO separate /joins sub-endpoint — sending a top-level {"joins":[...]} payload is
# accepted (HTTP 200) but has no effect on the join_specs. Sending "join_instructions" as a
# top-level key in serialized_space returns HTTP 400 "Unknown field 'join_instructions'".
# The correct pattern: GET with include_serialized_space=true, merge the join entry into
# config["instructions"]["join_specs"] using the internal join_spec object format, then
# PATCH {"serialized_space": json.dumps(config)}.
# (Synonyms and entity matching must be done in the UI — Configure → Data tab)

import uuid

if not SPACE_ID:
    print("Enter Space ID in widget first.")
else:
    # Step 1: read current serialized_space config
    get_resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
        headers=HEADERS,
        params={"include_serialized_space": "true"},
    )
    if get_resp.status_code != 200:
        print(f"❌ Could not read space config: {get_resp.status_code} {get_resp.text[:200]}")
        print("Add the join manually in the UI:")
        print("  Configure → Instructions → Joins → + Add")
        print("  Left: dispatch_intervals  |  Right: generator_registration")
        print("  Condition: dispatch_intervals.duid = generator_registration.duid")
        print("  Relationship: Many-to-one")
    else:
        import json as _json
        _decoder = _json.JSONDecoder(strict=False)
        space = get_resp.json()
        etag  = space.get("etag")
        raw   = space.get("serialized_space") or "{}"
        # Use strict=False to handle embedded newlines in content strings
        config, _ = _decoder.raw_decode(raw)

        # Step 2: merge the join entry into instructions.join_specs
        # The join_spec object format (verified against Genie API v2):
        #   id, left (identifier + alias), right (identifier + alias),
        #   sql: ["<condition>", "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--"]
        instructions = config.setdefault("instructions", {})
        existing_specs = instructions.setdefault("join_specs", [])
        left_id  = f"{CATALOG}.{SCHEMA}.dispatch_intervals"
        right_id = f"{CATALOG}.{SCHEMA}.generator_registration"
        # De-duplicate: only add if this join pair is not already present
        already_present = any(
            j.get("left", {}).get("identifier") == left_id and
            j.get("right", {}).get("identifier") == right_id
            for j in existing_specs
        )
        if not already_present:
            existing_specs.append({
                "id": uuid.uuid4().hex,
                "left":  {"identifier": left_id,  "alias": "di"},
                "right": {"identifier": right_id, "alias": "gr"},
                "sql": [
                    "`di`.`duid` = `gr`.`duid`",
                    "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--",
                ],
            })
            print(f"Adding join: {left_id} → {right_id}")
        else:
            print("Join already present — skipping duplicate.")

        # Step 3: PATCH the updated serialized_space back
        body = {"serialized_space": _json.dumps(config)}
        if etag:
            body["etag"] = etag
        patch_resp = requests.patch(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
            headers=HEADERS,
            json=body,
        )
        if patch_resp.status_code in (200, 204):
            print("✅ Join configured: dispatch_intervals ↔ generator_registration on duid")
        else:
            # Falls back to showing the manual UI steps
            print(f"API returned {patch_resp.status_code}: {patch_resp.text[:300]}")
            print("Add the join manually in the UI:")
            print("  Configure → Instructions → Joins → + Add")
            print("  Left: dispatch_intervals  |  Right: generator_registration")
            print("  Condition: dispatch_intervals.duid = generator_registration.duid")
            print("  Relationship: Many-to-one")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Synonyms to add manually (Configure → Data → [table] → column → Synonyms)
# MAGIC
# MAGIC | Table | Column | Synonyms |
# MAGIC |---|---|---|
# MAGIC | spot_prices | `region_id` | region, state, NEM region, zone |
# MAGIC | spot_prices | `rrp` | price, spot price, market price |
# MAGIC | dispatch_intervals | `dispatch_mw` | dispatch, output, generation, MW |
# MAGIC | dispatch_intervals | `fuel_type` | fuel, energy type, generation type |
# MAGIC
# MAGIC > The metric view (`nem_spot_metrics`) already declares synonyms in YAML — no manual
# MAGIC > synonym entry needed for its measures.
# MAGIC
# MAGIC ### Entity matching to enable (Configure → Data → [table] → column → Advanced → **Entity matching** → toggle on)
# MAGIC
# MAGIC | Column | Maps |
# MAGIC |---|---|
# MAGIC | `region_id` | NSW → NSW1, Victoria → VIC1, QLD → QLD1, SA → SA1, TAS → TAS1 |
# MAGIC | `notice_type` | lack of reserve → LOR%, reserve warning → LOR1, critical shortage → LOR3 |
# MAGIC | `fuel_type` | renewables → solar/wind, coal → coal, gas peakers → gas |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: UC Functions in Genie Space
# MAGIC
# MAGIC UC Functions let Genie call a named SQL function instead of writing the same calculation
# MAGIC inline every time. When a user asks a question that maps to the function, Genie will call it
# MAGIC by name and explain what it did — making the answer auditable and consistent.
# MAGIC
# MAGIC **Use case:** Market operations needs to quickly assess exposure when spot prices approach the
# MAGIC market price cap ($15,300/MWh). This function returns cap-exposure metrics for any region
# MAGIC above a configurable price threshold.
# MAGIC
# MAGIC ### Step 5a: Create the UC Function
# MAGIC
# MAGIC **🖱️ UI:** SQL Editor → new query → paste the SQL below → Run → function appears in Catalog
# MAGIC under `workshop_au.aemo` with a function icon
# MAGIC
# MAGIC **⚡ Automated:**

# COMMAND ----------

# Step 5a — Create a UC Function: market cap exposure calculator for a region.
# Table-valued function: takes a region code and optional threshold, returns
# interval_count, avg_rrp, and max_rrp for high-price intervals.
# Matches the signature created by setup.py so both notebooks produce the same object.
# Genie will call this when asked about price risk, cap exposure, or high-price events.

FUNC_FQN = f"{CATALOG}.{SCHEMA}.calculate_market_cap_exposure"

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FUNC_FQN}(
    region_id_param   STRING  COMMENT 'NEM region to analyse. One of: NSW1, VIC1, QLD1, SA1, TAS1.',
    threshold_param   DOUBLE  DEFAULT 300.0
        COMMENT 'RRP threshold in $/MWh above which an interval is counted as a cap-exposure event. Defaults to $300/MWh.'
)
RETURNS TABLE (
    interval_count  BIGINT  COMMENT 'Number of 30-minute intervals with RRP above the threshold.',
    avg_rrp         DOUBLE  COMMENT 'Average RRP across those high-price intervals ($/MWh).',
    max_rrp         DOUBLE  COMMENT 'Maximum RRP observed — peak cap-exposure event ($/MWh).'
)
COMMENT 'Returns market cap exposure metrics for a NEM region above a configurable RRP threshold. Call this when asked about price risk, cap exposure, high-price events, or extreme pricing for a region. Example: SELECT * FROM {FUNC_FQN}(\\\'NSW1\\\', 300.0)'
RETURN
    SELECT
        COUNT(*)            AS interval_count,
        ROUND(AVG(rrp), 2)  AS avg_rrp,
        ROUND(MAX(rrp), 2)  AS max_rrp
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE region_id = region_id_param
      AND rrp > threshold_param
""")

print(f"✅ UC Function created: {FUNC_FQN}(region_id_param STRING, threshold_param DOUBLE)")
print("   Returns TABLE: interval_count BIGINT, avg_rrp DOUBLE, max_rrp DOUBLE")

# COMMAND ----------

# Test the function directly in SQL before adding it to the space.
# Uses the default threshold ($300/MWh) for each NEM region.
test_df = spark.sql(f"""
SELECT 'NSW1' AS region, * FROM {FUNC_FQN}('NSW1', 300.0)
UNION ALL
SELECT 'VIC1' AS region, * FROM {FUNC_FQN}('VIC1', 300.0)
UNION ALL
SELECT 'QLD1' AS region, * FROM {FUNC_FQN}('QLD1', 300.0)
UNION ALL
SELECT 'SA1'  AS region, * FROM {FUNC_FQN}('SA1',  300.0)
UNION ALL
SELECT 'TAS1' AS region, * FROM {FUNC_FQN}('TAS1', 300.0)
ORDER BY interval_count DESC
""")
print("Market cap exposure by region (last full dataset, threshold $300/MWh):")
print("  interval_count = intervals above threshold | avg_rrp / max_rrp in $/MWh")
test_df.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 5b: Add the Function to the Genie Space
# MAGIC
# MAGIC **🖱️ UI:** Configure → Data → **Functions tab** → + Add → search for `calculate_market_cap_exposure`
# MAGIC → select → Save.
# MAGIC
# MAGIC > This registers the function as a callable tool. Genie will fill in the parameters
# MAGIC > (`region_id_param`, `threshold_param`) from the user's question — e.g. "NSW1" from
# MAGIC > "how exposed is NSW to cap pricing?" — and show the returned table in the chat response.
# MAGIC
# MAGIC **⚡ Automated via serialized_space PATCH:**

# COMMAND ----------

# Automated: register the UC function in the Genie space via serialized_space.
# UC functions with parameters sit under instructions.sql_expressions in the serialized config,
# using the "uc_function" variant (expression_type = "UC_FUNCTION").
# The function_name field is the 3-level FQN; parameters are resolved by Genie from context.

if not SPACE_ID:
    print("Enter Space ID in widget first.")
else:
    get_resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
        headers=HEADERS,
        params={"include_serialized_space": "true"},
    )
    if get_resp.status_code != 200:
        print(f"❌ Could not read space config: {get_resp.status_code} {get_resp.text[:200]}")
        print("\nAdd manually in the UI:")
        print("  Configure → Data → Functions tab → + Add")
        print(f"  Search: calculate_market_cap_exposure")
        print(f"  Select: {CATALOG}.{SCHEMA}.calculate_market_cap_exposure")
    else:
        import json as _json
        _decoder = _json.JSONDecoder(strict=False)
        space = get_resp.json()
        etag  = space.get("etag")
        raw   = space.get("serialized_space") or "{}"
        config, _ = _decoder.raw_decode(raw)

        instructions = config.setdefault("instructions", {})
        existing_exprs = instructions.setdefault("sql_expressions", [])

        fn_fqn = f"{CATALOG}.{SCHEMA}.calculate_market_cap_exposure"
        already_present = any(
            e.get("function_name") == fn_fqn or
            fn_fqn in str(e.get("expression", ""))
            for e in existing_exprs
        )

        if not already_present:
            existing_exprs.append({
                "id":              uuid.uuid4().hex,
                "name":            "Market Cap Exposure",
                "expression_type": "UC_FUNCTION",
                "function_name":   fn_fqn,
                "description":     (
                    "Returns interval count, average RRP, and peak RRP for a NEM region "
                    "above a configurable price threshold. Use when asked about price risk, "
                    "cap exposure, or high-price events for a specific region."
                ),
            })
            print(f"Registering UC function in space: {fn_fqn}")
        else:
            print("UC function already registered — skipping duplicate.")

        body = {"serialized_space": _json.dumps(config)}
        if etag:
            body["etag"] = etag
        patch_resp = requests.patch(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
            headers=HEADERS,
            json=body,
        )
        if patch_resp.status_code in (200, 204):
            print(f"✅ UC function registered in space: {fn_fqn}")
        else:
            print(f"API returned {patch_resp.status_code}: {patch_resp.text[:300]}")
            print("\nAdd manually in the UI:")
            print("  Configure → Data → Functions tab → + Add")
            print(f"  Search and select: calculate_market_cap_exposure")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 5c: Test the Function via Genie Chat
# MAGIC
# MAGIC Open the Genie space chat tab and try these questions — each should trigger the UC function:
# MAGIC
# MAGIC | Question | Expected behaviour |
# MAGIC |---|---|
# MAGIC | "What is the market cap exposure for VIC1 above $300/MWh?" | Genie calls `calculate_market_cap_exposure('VIC1', 300.0)`, returns interval count + avg/max RRP |
# MAGIC | "Which region has the highest price risk above $5,000/MWh?" | Genie calls the function for all 5 regions with threshold 5000, ranks by interval_count |
# MAGIC | "How exposed is South Australia to cap pricing events?" | Entity matching maps "South Australia" → SA1, then calls the function with default threshold |
# MAGIC
# MAGIC > **What to look for:** Genie's response should name the function it called and show the
# MAGIC > returned table (interval_count, avg_rrp, max_rrp). If it writes raw SQL instead, the
# MAGIC > function is not yet registered — re-run Step 5b or add it manually via Configure → Data → Functions.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 01 Checkpoint
# MAGIC - [ ] Materialized view `daily_dispatch_summary` created and queryable (Step 0a)
# MAGIC - [ ] Metric view `nem_spot_metrics` created with named measures (Step 0b)
# MAGIC - [ ] Column comments set on 4 core tables (Step 1 — automated)
# MAGIC - [ ] Table descriptions set on all 8 objects including the two new views (Step 2 — automated)
# MAGIC - [ ] Space created with 6 objects (4 tables + MV + metric view), Space ID in widget (Step 3)
# MAGIC - [ ] Synonyms added for region_id, rrp, dispatch_mw, fuel_type (Step 4 — UI)
# MAGIC - [ ] Entity matching enabled for region_id, notice_type, fuel_type (Step 4 — UI)
# MAGIC - [ ] Join configured: dispatch_intervals ↔ generator_registration (Step 4 — API or UI)
# MAGIC - [ ] UC Function `calculate_market_cap_exposure` created and tested (Step 5a)
# MAGIC - [ ] UC Function registered in Genie space (Step 5b — API or UI)
# MAGIC - [ ] Genie chat returns function-based answer for "market cap exposure for VIC1" (Step 5c)
# MAGIC
# MAGIC **→ Next: Lab 02 — Benchmarks, Golden Queries & Instructions**
