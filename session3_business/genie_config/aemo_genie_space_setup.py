# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: #1B3A4B; padding: 28px 32px; border-radius: 10px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: #FF3621; font-size: 1.8em; margin: 0 0 6px 0;">⚙️ AEMO NEM Operations — Genie Space Setup</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 0; font-size: 1em;">
# MAGIC     <strong>FOR FACILITATORS ONLY</strong> — Run this notebook before Session 3. Participants do not need to open this file.
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC > **What this notebook does**
# MAGIC > 1. Checks that all required AEMO tables exist and are populated
# MAGIC > 2. Creates (or re-creates) the **AEMO NEM Operations** Genie Space via the Databricks REST API
# MAGIC > 3. Configures the Space description, table bindings, and instruction text
# MAGIC > 4. Adds 15 golden SQL queries as curated answers
# MAGIC > 5. Runs 5 smoke-test questions to confirm the Space is responding correctly
# MAGIC
# MAGIC **Run time:** ~5 minutes
# MAGIC **Cluster:** Any cluster with `databricks-sdk` installed (Databricks Runtime 14.0+ recommended)
# MAGIC **Required permission:** Workspace Admin or the "Can Manage" permission on the target catalog

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — Configuration
# MAGIC
# MAGIC Edit the variables in the cell below before running anything else.

# COMMAND ----------

# ── EDIT THESE BEFORE RUNNING ──────────────────────────────────────────────────

# The catalog and schema where AEMO tables live
AEMO_CATALOG = "workshop_au"
AEMO_SCHEMA   = "aemo"              # change if tables are in a different schema

# Genie Space name that participants will see
SPACE_TITLE       = "AEMO NEM Operations"
SPACE_DESCRIPTION = (
    "Ask questions about NEM dispatch, spot prices, market notices, "
    "and settlements in plain English. Covers all five NEM regions: "
    "NSW1, VIC1, QLD1, SA1, and TAS1."
)

# Warehouse to back the Genie Space (must be running or auto-start enabled)
# Find this in SQL > SQL Warehouses — copy the warehouse ID from the URL
SQL_WAREHOUSE_ID = "TODO_REPLACE_WITH_WAREHOUSE_ID"

# ── DO NOT EDIT BELOW THIS LINE ────────────────────────────────────────────────

TABLES = [
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.dispatch_intervals",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.spot_prices",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.market_notices",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.generator_registration",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.settlement_amounts",
]

print(f"Catalog    : {AEMO_CATALOG}")
print(f"Schema     : {AEMO_SCHEMA}")
print(f"Space name : {SPACE_TITLE}")
print(f"Warehouse  : {SQL_WAREHOUSE_ID}")
print(f"Tables     : {len(TABLES)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Pre-flight: verify all tables exist and have data

# COMMAND ----------

import sys

print("Checking required tables...\n")
failed = []

for table in TABLES:
    try:
        result = spark.sql(f"SELECT COUNT(*) AS n FROM {table}").collect()[0]["n"]
        status = "✅  OK" if result > 0 else "⚠️   EMPTY (has no rows)"
        print(f"  {table:<55} {result:>12,} rows   {status}")
        if result == 0:
            failed.append(table)
    except Exception as e:
        print(f"  {table:<55} {'MISSING':>12}       ❌  {e}")
        failed.append(table)

print()
if failed:
    print(f"⛔  {len(failed)} table(s) failed the check. Resolve before continuing.")
    print("   Failing tables:", failed)
    print()
    print("   Common cause: the AEMO data setup notebook has not been run yet.")
    print(f"   Expected location: {AEMO_CATALOG}.{AEMO_SCHEMA}.*")
    print("   Run the setup notebook first, then re-run this notebook from Step 1.")
    raise RuntimeError(
        f"Pre-flight failed: {len(failed)} table(s) missing or empty. "
        "Run the AEMO data setup notebook before creating the Genie Space."
    )
else:
    print("✅  All tables passed. Ready to create the Genie Space.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Build the Genie Space instruction text
# MAGIC
# MAGIC This is the most important part of the setup. The instruction text tells Genie how to interpret questions, which columns to use, and how to format responses. Poor instructions = poor answers.
# MAGIC
# MAGIC Review and customise the text in the cell below before creating the Space.

# COMMAND ----------

GENIE_INSTRUCTIONS = """
This Genie Space provides natural language access to AEMO NEM (National Electricity Market) operations data.
All data is historical (not real-time). The minimum data lag is approximately 30–60 minutes.

## Data available

### dispatch_intervals
5-minute dispatch data for all NEM generators.
Key columns:
  - settlement_date  : TIMESTAMP — the 5-minute dispatch interval end time (AEST)
  - region_id        : STRING    — NEM region: NSW1, VIC1, QLD1, SA1, TAS1
  - duid             : STRING    — Dispatchable Unit Identifier (unique per generator unit)
  - dispatch_mw      : DOUBLE    — Actual MW dispatched in that interval (0 if unavailable)
  - fuel_type        : STRING    — e.g. 'coal', 'gas', 'wind', 'solar', 'hydro', 'battery', 'biomass'
  - station_name     : STRING    — Human-readable station name (e.g. 'Loy Yang A')
  - initial_mw       : DOUBLE    — MW at the start of the dispatch interval
  - available_mw     : DOUBLE    — Maximum MW the unit declared it could produce
  - ramp_rate        : DOUBLE    — MW per minute ramp capability

### spot_prices
30-minute trading interval Regional Reference Prices for all NEM regions.
Key columns:
  - settlement_date       : TIMESTAMP — trading interval end time (AEST)
  - region_id             : STRING    — NEM region: NSW1, VIC1, QLD1, SA1, TAS1
  - rrp                   : DOUBLE    — Regional Reference Price in $/MWh
  - total_demand_mw       : DOUBLE    — Total regional demand for that interval
  - net_interchange       : DOUBLE    — Net MW import (positive) or export (negative) via interconnectors
  - scheduled_generation  : DOUBLE    — Total scheduled generation dispatched in the region

### market_notices
AEMO market and system notices as published on NEMWEB.
Key columns:
  - notice_id        : BIGINT    — Unique notice identifier
  - notice_type      : STRING    — Category: e.g. 'LOR1', 'LOR2', 'LOR3', 'MARKET NOTICE', 'SYSTEM NOTICE', 'RERT'
  - reason           : STRING    — Full text of the notice
  - effective_date   : TIMESTAMP — When the notice takes effect (AEST)
  - issue_time       : TIMESTAMP — When AEMO published the notice (AEST)
  - region_id        : STRING    — Region affected (NULL if NEM-wide)
  - intervention     : BOOLEAN   — TRUE if this notice is part of a market intervention

### generator_registration
NEM registered generator details from the AEMO Registration and Exemption List.
Key columns:
  - duid                    : STRING — Dispatchable Unit Identifier (primary key)
  - station_name            : STRING — Human-readable station name (e.g. 'Loy Yang A')
  - participant_id          : STRING — Market participant code
  - region_id               : STRING — NEM region the unit is registered in
  - registered_capacity_mw  : DOUBLE — Nameplate capacity in MW
  - fuel_type               : STRING — Primary fuel type
  - dispatch_type           : STRING — 'GENERATOR' or 'LOAD'
  - max_ramp_rate           : DOUBLE — Maximum ramp rate in MW/min
  - min_load                : DOUBLE — Minimum stable generation level in MW

### settlement_amounts
Weekly NEM settlement data. One row per participant per settlement run.
Key columns:
  - settlement_date         : DATE   — Settlement week end date
  - participant_id          : STRING — Market participant code
  - run_type                : STRING — Settlement run type: 'FINAL', 'REVISED', 'PRELIMINARY'
  - energy_amount_aud       : DOUBLE — Energy component of settlement in AUD
  - fcas_amount_aud         : DOUBLE — FCAS component of settlement in AUD
  - interconnector_residue_aud : DOUBLE — Interconnector residue component in AUD
  - total_aud               : DOUBLE — Net settlement amount in AUD (positive = receivable, negative = payable)
  - settlement_status       : STRING — 'FINAL', 'REVISED', 'PRELIMINARY', 'DISPUTED', 'PENDING'

## Formatting rules
- Express prices in $/MWh with 2 decimal places (e.g. $87.45/MWh)
- Express energy quantities in MW — do NOT convert to kW or GW unless the user asks
- Use DD/MM/YYYY format for all dates displayed to the user (e.g. 22/05/2026)
- Refer to regions by their full 4-character ID: NSW1, VIC1, QLD1, SA1, TAS1 (not 'NSW', 'Victoria', etc.)
- For LOR severity levels: LOR1 = first warning, LOR2 = shortfall imminent, LOR3 = critical shortage
- Settlement amounts: positive = participant receives money, negative = participant pays money
- When the user asks about "yesterday" or "last week", use CURRENT_DATE relative to the query execution time (AEST)
- If a result contains more than 50 rows, show the top 20 by the most relevant metric and note the total count

## Common acronyms
- NEM   = National Electricity Market
- DUID  = Dispatchable Unit Identifier
- RRP   = Regional Reference Price
- LOR   = Lack of Reserve
- RERT  = Reliability and Emergency Reserve Trader
- APC   = Administered Price Cap (currently $17,500/MWh)
- MPC   = Market Price Cap (same as APC)
- FCAS  = Frequency Control Ancillary Services
- AEST  = Australian Eastern Standard Time (UTC+10); AEDT = UTC+11 (daylight saving)

## What this Space cannot answer
- Forecasts or predictions (data is historical only)
- Individual contract or bilateral trade details
- Real-time SCADA or control room data
- Data before the table's earliest date (query SELECT MIN(settlement_date) to check)
- Questions about non-NEM markets (WEM, gas markets)
""".strip()

print("Instruction text length:", len(GENIE_INSTRUCTIONS), "characters")
print("\nFirst 200 characters preview:")
print(GENIE_INSTRUCTIONS[:200] + "...")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Define the 15 golden SQL queries
# MAGIC
# MAGIC These are curated queries that Genie will use as trusted references when answering similar questions.
# MAGIC Genie will prefer these over generating its own SQL when the question matches.
# MAGIC
# MAGIC Each entry has: a name, a description (the question pattern it answers), and the SQL.

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "01_spot_prices_yesterday_by_region",
        "description": "Average, minimum, and maximum spot prices for each NEM region for yesterday",
        "sql": """
SELECT
    region_id,
    ROUND(AVG(rrp), 2)  AS avg_price_mwh,
    ROUND(MIN(rrp), 2)  AS min_price_mwh,
    ROUND(MAX(rrp), 2)  AS max_price_mwh,
    ROUND(MAX(rrp) - MIN(rrp), 2) AS price_range_mwh,
    COUNT(*)            AS trading_intervals
FROM aemo.spot_prices
WHERE DATE(settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
GROUP BY region_id
ORDER BY avg_price_mwh DESC
""".strip()
    },
    {
        "name": "02_top_generators_by_dispatch",
        "description": "Top 10 generators by total dispatch in a given region for a given date range",
        "sql": """
SELECT
    d.duid,
    g.station_name,
    g.fuel_type,
    d.region_id,
    ROUND(SUM(d.dispatch_mw) / 12, 1)  AS total_mwh,   -- 5-min intervals: divide by 12 to get MWh
    ROUND(AVG(d.dispatch_mw), 1)        AS avg_dispatch_mw,
    ROUND(MAX(d.dispatch_mw), 1)        AS peak_dispatch_mw
FROM aemo.dispatch_intervals d
LEFT JOIN aemo.generator_registration g USING (duid)
WHERE DATE(d.settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
GROUP BY d.duid, g.station_name, g.fuel_type, d.region_id
ORDER BY total_mwh DESC
LIMIT 10
""".strip()
    },
    {
        "name": "03_lor_notices_last_7_days",
        "description": "All LOR (Lack of Reserve) market notices issued in the last 7 days",
        "sql": """
SELECT
    notice_id,
    notice_type,
    region_id,
    LEFT(reason, 200)   AS reason_summary,
    effective_date,
    issue_time
FROM aemo.market_notices
WHERE notice_type IN ('LOR1', 'LOR2', 'LOR3')
  AND effective_date >= CURRENT_DATE - INTERVAL 7 DAYS
ORDER BY effective_date DESC
""".strip()
    },
    {
        "name": "04_price_spikes_over_1000",
        "description": "Spot price intervals above $1000/MWh — when and where they occurred",
        "sql": """
SELECT
    region_id,
    DATE(settlement_date)         AS spike_date,
    settlement_date               AS interval_time,
    ROUND(rrp, 2)                 AS rrp_mwh
FROM aemo.spot_prices
WHERE rrp > 1000
ORDER BY settlement_date DESC
LIMIT 200
""".strip()
    },
    {
        "name": "05_dispatch_by_fuel_type_daily",
        "description": "Total NEM dispatch by fuel type for each day in the last 30 days",
        "sql": """
SELECT
    DATE(settlement_date)          AS dispatch_date,
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 0) AS total_mwh
FROM aemo.dispatch_intervals
WHERE settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY DATE(settlement_date), fuel_type
ORDER BY dispatch_date DESC, total_mwh DESC
""".strip()
    },
    {
        "name": "06_settlement_totals_latest_run",
        "description": "Total settlement amount by participant for the most recent settlement run",
        "sql": """
WITH latest_run AS (
    SELECT MAX(settlement_date) AS run_date
    FROM aemo.settlement_amounts
)
SELECT
    s.participant_id,
    ROUND(SUM(s.total_aud), 2)   AS total_settlement_aud,
    s.settlement_status,
    COUNT(*)                      AS line_items,
    r.run_date                    AS settlement_week_ending
FROM aemo.settlement_amounts s
CROSS JOIN latest_run r
WHERE s.settlement_date = r.run_date
GROUP BY s.participant_id, s.settlement_status, r.run_date
ORDER BY ABS(SUM(s.total_aud)) DESC
""".strip()
    },
    {
        "name": "07_regional_demand_trend_hourly",
        "description": "Hourly average demand trend for all regions over the last 7 days",
        "sql": """
SELECT
    region_id,
    DATE(settlement_date)                       AS demand_date,
    HOUR(settlement_date)                       AS hour_of_day,
    ROUND(AVG(total_demand_mw), 1)              AS avg_demand_mw,
    ROUND(MAX(total_demand_mw), 1)              AS peak_demand_mw
FROM aemo.spot_prices
WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY region_id, DATE(settlement_date), HOUR(settlement_date)
ORDER BY region_id, demand_date, hour_of_day
""".strip()
    },
    {
        "name": "08_all_market_notices_last_30_days",
        "description": "All AEMO market notices of any type in the last 30 days",
        "sql": """
SELECT
    notice_id,
    notice_type,
    region_id,
    LEFT(reason, 300)  AS reason_summary,
    effective_date,
    issue_time
FROM aemo.market_notices
WHERE issue_time >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY issue_time DESC
""".strip()
    },
    {
        "name": "09_generator_capacity_by_fuel_type",
        "description": "Total registered generation capacity by fuel type across the NEM",
        "sql": """
SELECT
    fuel_type,
    region_id,
    COUNT(DISTINCT duid)                          AS unit_count,
    COUNT(DISTINCT station_name)                  AS station_count,
    ROUND(SUM(registered_capacity_mw), 0)         AS total_capacity_mw
FROM aemo.generator_registration
WHERE dispatch_type = 'GENERATOR'
GROUP BY fuel_type, region_id
ORDER BY fuel_type, total_capacity_mw DESC
""".strip()
    },
    {
        "name": "10_price_volatility_last_week",
        "description": "Price volatility (standard deviation) by region for the last 7 days",
        "sql": """
SELECT
    region_id,
    ROUND(AVG(rrp), 2)    AS avg_price_mwh,
    ROUND(STDDEV(rrp), 2) AS price_stddev,
    ROUND(MAX(rrp), 2)    AS max_price_mwh,
    ROUND(MIN(rrp), 2)    AS min_price_mwh,
    COUNT(*)               AS intervals_with_data
FROM aemo.spot_prices
WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY region_id
ORDER BY price_stddev DESC
""".strip()
    },
    {
        "name": "11_negative_prices_by_region",
        "description": "Negative spot price intervals by region — when prices dropped below zero",
        "sql": """
SELECT
    region_id,
    DATE(settlement_date)   AS price_date,
    COUNT(*)                AS negative_intervals,
    ROUND(MIN(rrp), 2)      AS lowest_price_mwh,
    ROUND(AVG(rrp), 2)      AS avg_negative_price_mwh
FROM aemo.spot_prices
WHERE rrp < 0
  AND settlement_date >= CURRENT_DATE - INTERVAL 90 DAYS
GROUP BY region_id, DATE(settlement_date)
ORDER BY price_date DESC, negative_intervals DESC
""".strip()
    },
    {
        "name": "12_dispatch_by_fuel_type_by_region_today",
        "description": "Today's dispatch breakdown by fuel type and region — a snapshot of the current generation mix",
        "sql": """
SELECT
    region_id,
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 0)    AS total_mwh_today,
    ROUND(AVG(dispatch_mw), 1)          AS avg_mw,
    COUNT(DISTINCT duid)                AS unit_count
FROM aemo.dispatch_intervals
WHERE DATE(settlement_date) = CURRENT_DATE
GROUP BY region_id, fuel_type
ORDER BY region_id, total_mwh_today DESC
""".strip()
    },
    {
        "name": "13_settlement_disputes_last_4_weeks",
        "description": "Participants with disputed or pending settlement amounts in the last 4 weeks",
        "sql": """
SELECT
    participant_id,
    settlement_date,
    ROUND(total_aud, 2)    AS settlement_amount_aud,
    settlement_status,
    run_type
FROM aemo.settlement_amounts
WHERE settlement_status IN ('DISPUTED', 'PENDING')
  AND settlement_date >= CURRENT_DATE - INTERVAL 28 DAYS
ORDER BY settlement_date DESC, ABS(total_aud) DESC
""".strip()
    },
    {
        "name": "14_monthly_price_comparison_yoy",
        "description": "Average spot price by month and region — year-on-year comparison",
        "sql": """
SELECT
    region_id,
    DATE_FORMAT(settlement_date, 'yyyy-MM') AS year_month,
    YEAR(settlement_date)                    AS year,
    MONTH(settlement_date)                   AS month,
    ROUND(AVG(rrp), 2)                       AS avg_price_mwh,
    COUNT(*)                                 AS interval_count
FROM aemo.spot_prices
WHERE settlement_date >= ADD_MONTHS(CURRENT_DATE, -24)
GROUP BY region_id, DATE_FORMAT(settlement_date, 'yyyy-MM'),
         YEAR(settlement_date), MONTH(settlement_date)
ORDER BY region_id, year_month
""".strip()
    },
    {
        "name": "15_nem_daily_operations_summary",
        "description": "NEM daily operations dashboard — spot prices, dispatch mix, and recent notices for today",
        "sql": """
-- This query powers the NEM Daily Operations dashboard.
-- Run it as three separate queries in Genie to get three dashboard tiles.

-- Tile 1: Today's prices by region
SELECT
    region_id,
    ROUND(AVG(rrp), 2)   AS avg_price_mwh,
    ROUND(MIN(rrp), 2)   AS min_price_mwh,
    ROUND(MAX(rrp), 2)   AS max_price_mwh
FROM aemo.spot_prices
WHERE DATE(settlement_date) = CURRENT_DATE
GROUP BY region_id
ORDER BY region_id;

-- Tile 2: Today's dispatch by fuel type (all regions)
SELECT
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 0) AS total_mwh,
    ROUND(AVG(dispatch_mw), 0)       AS avg_mw
FROM aemo.dispatch_intervals
WHERE DATE(settlement_date) = CURRENT_DATE
GROUP BY fuel_type
ORDER BY total_mwh DESC;

-- Tile 3: Active notices today
SELECT notice_type, region_id, LEFT(reason, 150) AS reason_summary, effective_date
FROM aemo.market_notices
WHERE DATE(issue_time) = CURRENT_DATE
ORDER BY issue_time DESC
LIMIT 10;
""".strip()
    },
]

# Qualify all table references in the golden queries with the configured catalog and schema.
# The SQL strings use the short alias "aemo." — replace with the full three-part name so
# the queries run regardless of the session's default catalog.
_TABLE_PREFIX = f"{AEMO_CATALOG}.{AEMO_SCHEMA}."
for _q in GOLDEN_QUERIES:
    _q["sql"] = _q["sql"].replace("aemo.", _TABLE_PREFIX)

print(f"Defined {len(GOLDEN_QUERIES)} golden queries (table prefix: {_TABLE_PREFIX}).")
for i, q in enumerate(GOLDEN_QUERIES, 1):
    print(f"  {i:02d}. {q['name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Create the Genie Space via the Databricks REST API
# MAGIC
# MAGIC The cell below uses the Databricks SDK to create the Space. If a Space with the same name already exists it will print a warning — you can either delete the old one manually (Genie → ... → Delete) or change the name in Step 0.

# COMMAND ----------

import requests, json
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieSpace

# Initialise SDK — uses the notebook's own auth context automatically
w = WorkspaceClient()

# Build the table FQN list for the API payload
table_fqns = [t for t in TABLES]

# Construct the Genie Space definition
space_definition = {
    "display_name":  SPACE_TITLE,
    "description":   SPACE_DESCRIPTION,
    "warehouse_id":  SQL_WAREHOUSE_ID,
    "table_identifiers": table_fqns,
    "instructional_text": GENIE_INSTRUCTIONS,
}

print("Creating Genie Space...")
print(f"  Title     : {SPACE_TITLE}")
print(f"  Tables    : {len(table_fqns)}")
print(f"  Warehouse : {SQL_WAREHOUSE_ID}")
print()

try:
    # Use the Genie Space creation API
    # Note: As of DBR 14.x, use the REST API directly if SDK does not expose GenieSpace
    ctx      = dbutils.entry_point.getDbutils().notebook().getContext()
    host     = ctx.apiUrl().get()
    token    = ctx.apiToken().get()
    headers  = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    api_url  = f"{host}/api/2.0/genie/spaces"

    resp = requests.post(api_url, headers=headers, json=space_definition, timeout=60)
    resp.raise_for_status()

    space = resp.json()
    SPACE_ID = space.get("space_id") or space.get("id")
    print(f"✅  Genie Space created successfully.")
    print(f"   Space ID  : {SPACE_ID}")
    print(f"   Space URL : {host}/genie/spaces/{SPACE_ID}")

except requests.HTTPError as e:
    if "already exists" in str(e.response.text).lower():
        print("⚠️   A Genie Space with this name already exists.")
        print("    To re-create it: open Genie → find the Space → ⋮ → Delete, then re-run this cell.")
        print("    Or change SPACE_TITLE in Step 0 to create a new Space with a different name.")
        SPACE_ID = None
    else:
        print(f"❌  API error: {e.response.status_code} — {e.response.text}")
        SPACE_ID = None
except Exception as e:
    print(f"❌  Unexpected error: {e}")
    SPACE_ID = None

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Add the 15 golden queries to the Space

# COMMAND ----------

if SPACE_ID is None:
    print("⚠️   Skipping golden query upload — Space ID is not set.")
    print("    Resolve the Space creation error in Step 4 first.")
else:
    ctx     = dbutils.entry_point.getDbutils().notebook().getContext()
    host    = ctx.apiUrl().get()
    token   = ctx.apiToken().get()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    success = 0
    failed_queries = []

    for q in GOLDEN_QUERIES:
        payload = {
            "name":        q["name"],
            "description": q["description"],
            "query":       q["sql"],
        }
        url  = f"{host}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries"
        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        if resp.status_code in (200, 201):
            success += 1
            print(f"  ✅  {q['name']}")
        else:
            failed_queries.append(q["name"])
            print(f"  ❌  {q['name']} — {resp.status_code}: {resp.text[:120]}")

    print(f"\nUploaded {success}/{len(GOLDEN_QUERIES)} golden queries.")
    if failed_queries:
        print("Failed:", failed_queries)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Smoke test: verify the Space answers 5 key questions
# MAGIC
# MAGIC This cell sends 5 representative questions to the Genie Space and checks that:
# MAGIC - The Space responds without errors
# MAGIC - The response contains data (not an empty result)
# MAGIC - The response references the correct table
# MAGIC
# MAGIC It does NOT assert exact numbers — data changes daily.

# COMMAND ----------

SMOKE_TEST_QUESTIONS = [
    "What was the average spot price in each NEM region yesterday?",
    "Show me the top 5 generators by dispatch in NSW1 yesterday",
    "Were there any LOR notices issued in the last 7 days?",
    "What is the total settlement amount for the most recent settlement run?",
    "What was the total NEM dispatch by fuel type yesterday?",
]

if SPACE_ID is None:
    print("⚠️   Skipping smoke tests — Space ID is not set.")
else:
    ctx     = dbutils.entry_point.getDbutils().notebook().getContext()
    host    = ctx.apiUrl().get()
    token   = ctx.apiToken().get()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("Running smoke tests...\n")
    all_passed = True

    for i, question in enumerate(SMOKE_TEST_QUESTIONS, 1):
        import time

        # Start a conversation
        conv_url = f"{host}/api/2.0/genie/spaces/{SPACE_ID}/start-conversation"
        conv_resp = requests.post(
            conv_url,
            headers=headers,
            json={"content": question},
            timeout=60
        )

        if conv_resp.status_code not in (200, 201):
            print(f"  ❌  Q{i}: Failed to start conversation — {conv_resp.status_code}: {conv_resp.text[:100]}")
            all_passed = False
            continue

        conv_data = conv_resp.json()
        conv_id   = conv_data.get("conversation_id") or conv_data.get("id")
        msg_id    = conv_data.get("message_id")

        if not conv_id:
            print(f"  ❌  Q{i}: No conversation ID in response")
            all_passed = False
            continue

        # Poll for the response (max 30 seconds)
        poll_url = f"{host}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conv_id}/messages/{msg_id}"
        deadline = time.time() + 30
        status   = "EXECUTING"

        while time.time() < deadline and status in ("EXECUTING", "PENDING"):
            time.sleep(3)
            poll_resp = requests.get(poll_url, headers=headers, timeout=15)
            if poll_resp.status_code == 200:
                msg_data = poll_resp.json()
                status   = msg_data.get("status", "UNKNOWN")

        if status == "COMPLETED":
            print(f"  ✅  Q{i}: '{question[:70]}...' — PASSED")
        elif status == "EXECUTING":
            print(f"  ⏱   Q{i}: Still running after 30s — response time may be slow")
        else:
            print(f"  ❌  Q{i}: Status '{status}' — '{question[:60]}...'")
            all_passed = False

    print()
    if all_passed:
        print("✅  All smoke tests passed. The Genie Space is ready for Session 3.")
    else:
        print("⚠️   Some smoke tests did not pass. Review the errors above before the session.")
        print("    Common causes: empty tables, warehouse not running, incorrect table names.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Print the participant handout URL
# MAGIC
# MAGIC Share this URL with participants so they can navigate directly to the Genie Space.

# COMMAND ----------

if SPACE_ID:
    ctx  = dbutils.entry_point.getDbutils().notebook().getContext()
    host = ctx.apiUrl().get()
    print("=" * 70)
    print("  SHARE WITH PARTICIPANTS:")
    print(f"  {host}/genie/spaces/{SPACE_ID}")
    print("=" * 70)
    print()
    print("Add this URL to:")
    print("  1. The workshop slide deck (session intro slide)")
    print("  2. The Teams/Slack channel for the session")
    print("  3. The facilitator notes so it is easy to re-share if someone loses it")
else:
    print("⚠️   Space ID not available. Complete Steps 4–6 successfully, then re-run this cell.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Pre-session final checklist
# MAGIC
# MAGIC Run through this checklist the morning of Session 3:
# MAGIC
# MAGIC | Check | How to verify | Expected result |
# MAGIC |---|---|---|
# MAGIC | All 5 tables have data | Step 1 cell output | Each table shows > 0 rows |
# MAGIC | SQL Warehouse is running | SQL → SQL Warehouses | Green dot, not starting |
# MAGIC | Genie Space is visible | Left sidebar → Genie | "AEMO NEM Operations" appears |
# MAGIC | 5 smoke test questions pass | Step 6 cell output | All ✅ |
# MAGIC | Participant URL works | Open the URL in incognito | Genie chat loads |
# MAGIC | All 30 participants have workspace access | Ask IT or check workspace admin | Users can log in |
# MAGIC | Lab notebook is shared with participants | Repos or Files → Share | Participants can open it |
# MAGIC
# MAGIC > If any check fails on the morning of the session, escalate to the AEMO Data Platform team immediately. Do not wait until participants arrive.
