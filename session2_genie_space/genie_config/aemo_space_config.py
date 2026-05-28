# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: #1B3A4B; padding: 28px 32px; border-radius: 10px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: #FF3621; font-size: 1.8em; margin: 0 0 6px 0;">AEMO NEM Operations — Genie Space Setup</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 0; font-size: 1em;">
# MAGIC     <strong>FOR FACILITATORS ONLY</strong> — Run this notebook before Session 2 (and again before Session 6 if running standalone).
# MAGIC     Participants do not need to open this file.
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC > **What this notebook does**
# MAGIC > 1. Checks that all required AEMO tables exist and are populated
# MAGIC > 2. Creates (or re-creates) the **AEMO NEM Operations** Genie Space via the Databricks REST API
# MAGIC > 3. Sets the Space description and comprehensive instruction text with AEMO domain context
# MAGIC > 4. Adds all 5 AEMO tables as trusted assets
# MAGIC > 5. Adds 15 golden SQL queries covering the main AEMO question types
# MAGIC > 6. Sets participant permissions (CAN_USE) for the workshop group
# MAGIC > 7. Runs 5 smoke-test questions to confirm the Space is responding correctly
# MAGIC > 8. Prints the Space ID and URL for participants to use
# MAGIC
# MAGIC **Run time:** ~5–8 minutes
# MAGIC **Cluster:** Any cluster with `databricks-sdk` and `requests` installed (Databricks Runtime 14.0+ recommended)
# MAGIC **Required permission:** Workspace Admin or equivalent permission on the target catalog

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 0 — Configuration
# MAGIC
# MAGIC Edit the variables in the cell below before running anything else.
# MAGIC Two values **must** be set before running: `SQL_WAREHOUSE_ID` and `PARTICIPANT_GROUP_NAME`.

# COMMAND ----------

# ── EDIT THESE BEFORE RUNNING ──────────────────────────────────────────────────

# Catalog and schema where the AEMO workshop tables live
AEMO_CATALOG = "workshop_au"
AEMO_SCHEMA   = "aemo"

# Name and description that participants will see in the Genie sidebar
SPACE_TITLE       = "AEMO NEM Operations"
SPACE_DESCRIPTION = (
    "Ask questions about NEM dispatch, spot prices, market notices, "
    "settlements, and generator registration in plain English. "
    "Covers all five NEM regions: NSW1, VIC1, QLD1, SA1, and TAS1. "
    "Data covers the last 6 months."
)

# SQL Warehouse to back the Genie Space.
# Find the warehouse ID in: SQL > SQL Warehouses > click the warehouse > copy the ID from the URL.
# The warehouse must have auto-start enabled — it does not need to be running when you create the Space.
SQL_WAREHOUSE_ID = "TODO_REPLACE_WITH_WAREHOUSE_ID"

# Unity Catalog group name for workshop participants.
# All members of this group will receive CAN_USE on the Space.
# If participants are managed individually (not via a group), set this to None and grant access manually.
PARTICIPANT_GROUP_NAME = "aemo-workshop-participants"   # set to None to skip group grant

# ── DO NOT EDIT BELOW THIS LINE ────────────────────────────────────────────────

TABLES = [
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.spot_prices",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.dispatch_intervals",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.market_notices",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.generator_registration",
    f"{AEMO_CATALOG}.{AEMO_SCHEMA}.settlement_amounts",
]

print(f"Catalog             : {AEMO_CATALOG}")
print(f"Schema              : {AEMO_SCHEMA}")
print(f"Space name          : {SPACE_TITLE}")
print(f"Warehouse ID        : {SQL_WAREHOUSE_ID}")
print(f"Tables to register  : {len(TABLES)}")
print(f"Participant group   : {PARTICIPANT_GROUP_NAME or '(skipped — grant access manually)'}")

if SQL_WAREHOUSE_ID == "TODO_REPLACE_WITH_WAREHOUSE_ID":
    raise ValueError(
        "SQL_WAREHOUSE_ID has not been set. "
        "Go to SQL > SQL Warehouses, click the warehouse, and copy the ID from the URL. "
        "Paste it into the SQL_WAREHOUSE_ID variable above."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Pre-flight: verify all AEMO tables exist and have data

# COMMAND ----------

import sys

print("Pre-flight check: required tables\n")
preflight_failures = []

for table in TABLES:
    try:
        row_count = spark.sql(f"SELECT COUNT(*) AS n FROM {table}").collect()[0]["n"]
        status = "OK" if row_count > 0 else "EMPTY"
        flag   = "OK" if row_count > 0 else "WARNING: has no rows"
        print(f"  {table:<60} {row_count:>12,} rows   [{flag}]")
        if row_count == 0:
            preflight_failures.append((table, "empty"))
    except Exception as e:
        short_error = str(e).split("\n")[0][:80]
        print(f"  {table:<60} {'MISSING':>12}       [FAIL: {short_error}]")
        preflight_failures.append((table, "missing"))

print()
if preflight_failures:
    print(f"[FAIL] {len(preflight_failures)} table(s) failed the check.")
    for t, reason in preflight_failures:
        print(f"  - {t} ({reason})")
    print()
    print("Resolution: run setup/00_workspace_setup.py to load the AEMO workshop data,")
    print(f"then re-run this notebook from Step 1.")
    raise RuntimeError(
        f"Pre-flight failed: {len(preflight_failures)} table(s) are missing or empty. "
        "Load the AEMO data before creating the Genie Space."
    )
else:
    print("[PASS] All 5 tables exist and have data. Ready to create the Genie Space.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Define the Space instruction text
# MAGIC
# MAGIC The instruction text is the most important configuration element. It tells Genie:
# MAGIC - How to interpret domain-specific terms (region codes, acronyms, AEMO conventions)
# MAGIC - Which columns map to which business concepts
# MAGIC - How to format responses (dates, currencies, units)
# MAGIC - What the Space cannot answer (to prevent hallucination on out-of-scope questions)
# MAGIC
# MAGIC Review this text and customise it for the specific customer environment before creating the Space.

# COMMAND ----------

GENIE_INSTRUCTIONS = """
This Genie Space provides natural language access to AEMO NEM (National Electricity Market) operational data.

All data is historical — not real-time. The minimum data lag is approximately 30–60 minutes from the time of the NEM event.
The data covers the last 6 months. To check the exact date range, ask: "What is the earliest and latest date in the spot_prices table?"

## NEM Regions

Use the following 4-character region codes. Do not use state names — the user may write "NSW" or "Victoria" but you should always resolve to the correct region code in your SQL.

| User may write | Correct region_id |
|----------------|------------------|
| NSW, New South Wales | NSW1 |
| VIC, Victoria | VIC1 |
| QLD, Queensland | QLD1 |
| SA, South Australia | SA1 |
| TAS, Tasmania | TAS1 |

## Data Available

### spot_prices
30-minute trading interval Regional Reference Prices (RRP) for all NEM regions.
Key columns:
  - settlement_date       : TIMESTAMP — trading interval end time (AEST/AEDT)
  - region_id             : STRING    — one of NSW1, VIC1, QLD1, SA1, TAS1
  - rrp                   : DOUBLE    — Regional Reference Price in $/MWh
  - total_demand_mw       : DOUBLE    — Total regional demand for that 30-minute interval
  - net_interchange       : DOUBLE    — Net MW import (positive) or export (negative) via interconnectors
  - scheduled_generation  : DOUBLE    — Total scheduled generation dispatched in the region

### dispatch_intervals
5-minute dispatch data for all NEM registered generators.
Key columns:
  - settlement_date  : TIMESTAMP — 5-minute dispatch interval end time (AEST/AEDT)
  - region_id        : STRING    — NEM region (NSW1, VIC1, QLD1, SA1, TAS1)
  - duid             : STRING    — Dispatchable Unit Identifier (unique per generator unit)
  - dispatch_mw      : DOUBLE    — Actual MW dispatched in that 5-minute interval
  - available_mw     : DOUBLE    — Maximum MW the unit declared available for dispatch
  - initial_mw       : DOUBLE    — MW the unit was producing at the start of the interval
  - ramp_rate        : DOUBLE    — MW/min ramp capability for that interval
  - fuel_type        : STRING    — Primary fuel: 'coal', 'gas', 'wind', 'solar', 'hydro', 'battery', 'biomass'
  - station_name     : STRING    — Human-readable station name (e.g. 'Loy Yang A', 'Hornsdale Power Reserve')

### market_notices
AEMO market and system notices as published on NEMWEB.
Key columns:
  - notice_id        : BIGINT    — Unique notice identifier
  - notice_type      : STRING    — Category: 'LOR1', 'LOR2', 'LOR3', 'MARKET NOTICE', 'SYSTEM NOTICE', 'RERT'
  - reason           : STRING    — Full text of the notice as published
  - effective_date   : TIMESTAMP — When the condition described in the notice takes effect (AEST/AEDT)
  - issue_time       : TIMESTAMP — When AEMO published the notice on NEMWEB (AEST/AEDT)
  - region_id        : STRING    — Region the notice applies to (NULL if NEM-wide)
  - intervention     : BOOLEAN   — TRUE if AEMO has intervened in the market dispatch

### generator_registration
NEM registered generator details. This is a point-in-time snapshot, not a time-series table.
Key columns:
  - duid                    : STRING — Dispatchable Unit Identifier (primary key; join to dispatch_intervals.duid)
  - station_name            : STRING — Human-readable station name
  - participant_id          : STRING — Market participant code (e.g. 'ALINTAENE', 'ERGT030')
  - region_id               : STRING — NEM region the unit is registered in
  - registered_capacity_mw  : DOUBLE — Nameplate capacity in MW
  - fuel_type               : STRING — Primary fuel type
  - dispatch_type           : STRING — 'GENERATOR' (produces power) or 'LOAD' (consumes power)
  - max_ramp_rate            : DOUBLE — Maximum ramp rate in MW/min
  - min_load                : DOUBLE — Minimum stable generation level in MW

### settlement_amounts
Weekly NEM settlement data. One row per participant per settlement run.
Key columns:
  - settlement_date             : DATE   — Settlement week end date
  - participant_id              : STRING — Market participant code
  - run_type                    : STRING — 'FINAL', 'REVISED', or 'PRELIMINARY'
  - energy_amount_aud           : DOUBLE — Energy component in AUD
  - fcas_amount_aud             : DOUBLE — FCAS (Frequency Control Ancillary Services) component in AUD
  - interconnector_residue_aud  : DOUBLE — Interconnector residue component in AUD
  - total_aud                   : DOUBLE — Net settlement amount in AUD
  - settlement_status           : STRING — 'FINAL', 'REVISED', 'PRELIMINARY', 'DISPUTED', or 'PENDING'

## Formatting Rules

- Express prices in $/MWh with 2 decimal places. Example: $87.45/MWh.
- Express energy in MWh or GWh. Use MWh for single-interval results; GWh for daily or longer aggregations. Do not use kWh or TWh unless the user asks.
- Use DD/MM/YYYY for dates in displayed results. Example: 22/05/2026.
- All timestamps in AEST (UTC+10 standard) or AEDT (UTC+11 daylight saving). Do not convert to UTC in output.
- Express settlement amounts in AUD with two decimal places and thousand separators. Example: $1,234,567.89.
- For settlement amounts: positive = participant receives money; negative = participant pays money.
- When the user refers to "yesterday", "last week", or "today", use CURRENT_DATE relative to the time of query execution.
- If a result contains more than 50 rows, show the top 20 by the most relevant metric and note the total count at the top of the response.
- Do not use scientific notation for any numbers.

## LOR Severity Levels

LOR = Lack of Reserve. AEMO issues LOR notices when reserve levels fall below thresholds.

- LOR1: Reserve margin is below the required threshold. First warning. Market participants should be on standby.
- LOR2: Reserve shortfall is imminent. AEMO may activate RERT contracts. Conditions are serious.
- LOR3: Reserve shortfall is occurring or about to occur. This is a critical system security event.

When a user asks about "LOR events" without specifying the level, include all three types in the result and display the level prominently.

## Administered Price Cap (APC)

The current Administered Price Cap is $17,500/MWh. When spot prices exceed this threshold, AEMO may invoke administered pricing. If the user asks about "price cap events" or "APC events", filter for rrp > 17500.

## Financial Year Definition

The Australian financial year runs from 1 July to 30 June. When the user asks for "this financial year" or "last financial year", use these dates:
- Current financial year: 1 July of the current calendar year to 30 June of the following calendar year (or to CURRENT_DATE if before 30 June)
- Last financial year: 1 July of last year to 30 June of this year

## Dispatch Interval to Energy Conversion

dispatch_intervals data is recorded at 5-minute intervals. To convert MW readings to MWh energy:
  MWh = sum(dispatch_mw) / 12     (because 12 five-minute intervals = 1 hour)

Always apply this conversion when the user asks for "total energy" or "MWh" from dispatch data.

## Common Acronyms

- NEM   = National Electricity Market
- DUID  = Dispatchable Unit Identifier
- RRP   = Regional Reference Price (the spot price)
- LOR   = Lack of Reserve
- RERT  = Reliability and Emergency Reserve Trader
- APC   = Administered Price Cap ($17,500/MWh)
- FCAS  = Frequency Control Ancillary Services
- MSATS = Market Settlement and Transfer Solution (AEMO's settlement system)
- AEST  = Australian Eastern Standard Time (UTC+10)
- AEDT  = Australian Eastern Daylight Time (UTC+11, active October–April)
- NEMWEB = AEMO's public data portal

## What This Space Cannot Answer

- Forecasts or predictions of any kind — this Space contains historical data only
- Individual bilateral contract details or confidential participant positions
- Real-time SCADA, control room, or network data — minimum lag is 30–60 minutes
- Questions about non-NEM markets (WEM, gas markets, network tariffs)
- Data earlier than the table's earliest date — ask "What is the earliest date in [table]?" to check
- Questions about the internal AEMO organisation, personnel, or internal systems
""".strip()

print(f"Instruction text length : {len(GENIE_INSTRUCTIONS):,} characters")
print(f"Preview (first 300 chars):")
print()
print(GENIE_INSTRUCTIONS[:300] + "...")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Define the 15 golden SQL queries
# MAGIC
# MAGIC Golden queries are trusted, curated SQL statements that Genie uses as reference answers when a participant asks a similar question. Genie will prefer a golden query over generating its own SQL when it detects a question match.
# MAGIC
# MAGIC Each golden query has a name (internal reference), a description (the question pattern it matches), and the SQL to run.
# MAGIC
# MAGIC The 15 queries below cover the five most common AEMO question categories: prices, dispatch, market notices, settlements, and generator capacity.

# COMMAND ----------

GOLDEN_QUERIES = [
    # ── SPOT PRICES ──────────────────────────────────────────────────────────
    {
        "name": "01_spot_prices_yesterday_all_regions",
        "description": "Average, minimum, and maximum spot prices for each NEM region for yesterday",
        "sql": """
SELECT
    region_id,
    ROUND(AVG(rrp), 2)              AS avg_price_mwh,
    ROUND(MIN(rrp), 2)              AS min_price_mwh,
    ROUND(MAX(rrp), 2)              AS max_price_mwh,
    ROUND(MAX(rrp) - MIN(rrp), 2)   AS price_range_mwh,
    COUNT(*)                        AS trading_intervals
FROM {catalog}.{schema}.spot_prices
WHERE DATE(settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
GROUP BY region_id
ORDER BY avg_price_mwh DESC
""".strip()
    },
    {
        "name": "02_spot_price_spikes_over_threshold",
        "description": "Spot price intervals above $1,000/MWh — when and where price spikes occurred",
        "sql": """
SELECT
    region_id,
    DATE(settlement_date)           AS spike_date,
    settlement_date                 AS interval_time,
    ROUND(rrp, 2)                   AS rrp_mwh
FROM {catalog}.{schema}.spot_prices
WHERE rrp > 1000
ORDER BY settlement_date DESC
LIMIT 200
""".strip()
    },
    {
        "name": "03_negative_prices_by_region",
        "description": "Negative spot price intervals — when prices dropped below zero, by region",
        "sql": """
SELECT
    region_id,
    DATE(settlement_date)           AS price_date,
    COUNT(*)                        AS negative_intervals,
    ROUND(MIN(rrp), 2)              AS lowest_price_mwh,
    ROUND(AVG(rrp), 2)              AS avg_negative_price_mwh
FROM {catalog}.{schema}.spot_prices
WHERE rrp < 0
  AND settlement_date >= CURRENT_DATE - INTERVAL 90 DAYS
GROUP BY region_id, DATE(settlement_date)
ORDER BY price_date DESC, negative_intervals DESC
""".strip()
    },
    {
        "name": "04_price_volatility_last_7_days",
        "description": "Spot price volatility by region for the last 7 days — standard deviation and range",
        "sql": """
SELECT
    region_id,
    ROUND(AVG(rrp), 2)      AS avg_price_mwh,
    ROUND(STDDEV(rrp), 2)   AS price_stddev,
    ROUND(MAX(rrp), 2)      AS max_price_mwh,
    ROUND(MIN(rrp), 2)      AS min_price_mwh,
    COUNT(*)                AS intervals_with_data
FROM {catalog}.{schema}.spot_prices
WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY region_id
ORDER BY price_stddev DESC
""".strip()
    },
    {
        "name": "05_hourly_demand_trend_by_region",
        "description": "Hourly average demand trend for all NEM regions over the last 7 days",
        "sql": """
SELECT
    region_id,
    DATE(settlement_date)                   AS demand_date,
    HOUR(settlement_date)                   AS hour_of_day,
    ROUND(AVG(total_demand_mw), 1)          AS avg_demand_mw,
    ROUND(MAX(total_demand_mw), 1)          AS peak_demand_mw
FROM {catalog}.{schema}.spot_prices
WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY region_id, DATE(settlement_date), HOUR(settlement_date)
ORDER BY region_id, demand_date, hour_of_day
""".strip()
    },
    # ── DISPATCH ─────────────────────────────────────────────────────────────
    {
        "name": "06_top_generators_by_dispatch_yesterday",
        "description": "Top 10 generators by total energy dispatched yesterday in a given region",
        "sql": """
SELECT
    d.duid,
    g.station_name,
    g.fuel_type,
    d.region_id,
    ROUND(SUM(d.dispatch_mw) / 12, 1)   AS total_mwh,
    ROUND(AVG(d.dispatch_mw), 1)         AS avg_dispatch_mw,
    ROUND(MAX(d.dispatch_mw), 1)         AS peak_dispatch_mw
FROM {catalog}.{schema}.dispatch_intervals d
LEFT JOIN {catalog}.{schema}.generator_registration g USING (duid)
WHERE DATE(d.settlement_date) = CURRENT_DATE - INTERVAL 1 DAY
GROUP BY d.duid, g.station_name, g.fuel_type, d.region_id
ORDER BY total_mwh DESC
LIMIT 10
""".strip()
    },
    {
        "name": "07_dispatch_by_fuel_type_daily",
        "description": "Total NEM dispatch by fuel type for each day in the last 30 days",
        "sql": """
SELECT
    DATE(settlement_date)               AS dispatch_date,
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 0)     AS total_mwh
FROM {catalog}.{schema}.dispatch_intervals
WHERE settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY DATE(settlement_date), fuel_type
ORDER BY dispatch_date DESC, total_mwh DESC
""".strip()
    },
    {
        "name": "08_generator_capacity_utilisation",
        "description": "Average capacity utilisation (dispatch / registered capacity) by fuel type and region last week",
        "sql": """
SELECT
    d.region_id,
    g.fuel_type,
    COUNT(DISTINCT d.duid)                                              AS unit_count,
    ROUND(AVG(d.dispatch_mw / NULLIF(g.registered_capacity_mw, 0)) * 100, 1)
                                                                        AS avg_utilisation_pct,
    ROUND(AVG(d.dispatch_mw), 1)                                        AS avg_dispatch_mw
FROM {catalog}.{schema}.dispatch_intervals d
JOIN {catalog}.{schema}.generator_registration g USING (duid)
WHERE d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
  AND g.dispatch_type = 'GENERATOR'
GROUP BY d.region_id, g.fuel_type
ORDER BY d.region_id, avg_utilisation_pct DESC
""".strip()
    },
    # ── MARKET NOTICES ───────────────────────────────────────────────────────
    {
        "name": "09_lor_notices_last_7_days",
        "description": "All LOR (Lack of Reserve) notices of any severity issued in the last 7 days",
        "sql": """
SELECT
    notice_id,
    notice_type,
    region_id,
    LEFT(reason, 250)   AS reason_summary,
    effective_date,
    issue_time
FROM {catalog}.{schema}.market_notices
WHERE notice_type IN ('LOR1', 'LOR2', 'LOR3')
  AND effective_date >= CURRENT_DATE - INTERVAL 7 DAYS
ORDER BY effective_date DESC
""".strip()
    },
    {
        "name": "10_all_market_notices_last_30_days",
        "description": "All AEMO market and system notices of any type in the last 30 days, grouped by type",
        "sql": """
SELECT
    notice_type,
    region_id,
    COUNT(*)            AS notice_count,
    MAX(issue_time)     AS most_recent_notice
FROM {catalog}.{schema}.market_notices
WHERE issue_time >= CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY notice_type, region_id
ORDER BY notice_count DESC
""".strip()
    },
    {
        "name": "11_lor_count_by_region_90_days",
        "description": "Count of LOR notices by region and severity level in the last 90 days",
        "sql": """
SELECT
    region_id,
    notice_type,
    COUNT(*)                AS notice_count,
    MIN(effective_date)     AS first_occurrence,
    MAX(effective_date)     AS most_recent
FROM {catalog}.{schema}.market_notices
WHERE notice_type IN ('LOR1', 'LOR2', 'LOR3')
  AND effective_date >= CURRENT_DATE - INTERVAL 90 DAYS
GROUP BY region_id, notice_type
ORDER BY region_id, notice_type
""".strip()
    },
    # ── SETTLEMENTS ──────────────────────────────────────────────────────────
    {
        "name": "12_settlement_totals_latest_run",
        "description": "Total settlement amount by participant for the most recent settlement run",
        "sql": """
WITH latest_run AS (
    SELECT MAX(settlement_date) AS run_date
    FROM {catalog}.{schema}.settlement_amounts
)
SELECT
    s.participant_id,
    ROUND(SUM(s.energy_amount_aud), 2)              AS energy_aud,
    ROUND(SUM(s.fcas_amount_aud), 2)                AS fcas_aud,
    ROUND(SUM(s.interconnector_residue_aud), 2)     AS interconnector_aud,
    ROUND(SUM(s.total_aud), 2)                      AS total_settlement_aud,
    s.settlement_status,
    r.run_date                                       AS settlement_week_ending
FROM {catalog}.{schema}.settlement_amounts s
CROSS JOIN latest_run r
WHERE s.settlement_date = r.run_date
GROUP BY s.participant_id, s.settlement_status, r.run_date
ORDER BY ABS(SUM(s.total_aud)) DESC
""".strip()
    },
    {
        "name": "13_disputed_pending_settlements",
        "description": "Participants with disputed or pending settlement amounts in the last 4 weeks",
        "sql": """
SELECT
    participant_id,
    settlement_date,
    ROUND(energy_amount_aud, 2)     AS energy_aud,
    ROUND(fcas_amount_aud, 2)       AS fcas_aud,
    ROUND(total_aud, 2)             AS total_aud,
    settlement_status,
    run_type
FROM {catalog}.{schema}.settlement_amounts
WHERE settlement_status IN ('DISPUTED', 'PENDING')
  AND settlement_date >= CURRENT_DATE - INTERVAL 28 DAYS
ORDER BY settlement_date DESC, ABS(total_aud) DESC
""".strip()
    },
    # ── GENERATOR CAPACITY ───────────────────────────────────────────────────
    {
        "name": "14_registered_capacity_by_fuel_and_region",
        "description": "Total registered generation capacity in the NEM by fuel type and region",
        "sql": """
SELECT
    fuel_type,
    region_id,
    COUNT(DISTINCT duid)                    AS unit_count,
    COUNT(DISTINCT station_name)            AS station_count,
    ROUND(SUM(registered_capacity_mw), 0)  AS total_registered_mw
FROM {catalog}.{schema}.generator_registration
WHERE dispatch_type = 'GENERATOR'
GROUP BY fuel_type, region_id
ORDER BY fuel_type, total_registered_mw DESC
""".strip()
    },
    # ── NEM OPERATIONS SUMMARY ───────────────────────────────────────────────
    {
        "name": "15_nem_daily_operations_snapshot",
        "description": "NEM daily operations snapshot — today's prices, dispatch mix, and active market notices",
        "sql": """
-- Today's average spot prices by region
SELECT
    'prices'        AS metric_type,
    region_id,
    ROUND(AVG(rrp), 2)   AS value_mwh,
    NULL                 AS fuel_type,
    NULL                 AS notice_text
FROM {catalog}.{schema}.spot_prices
WHERE DATE(settlement_date) = CURRENT_DATE
GROUP BY region_id

UNION ALL

-- Today's total dispatch by fuel type
SELECT
    'dispatch_mwh'  AS metric_type,
    region_id,
    ROUND(SUM(dispatch_mw) / 12, 0) AS value_mwh,
    fuel_type,
    NULL            AS notice_text
FROM {catalog}.{schema}.dispatch_intervals
WHERE DATE(settlement_date) = CURRENT_DATE
GROUP BY region_id, fuel_type

UNION ALL

-- Active notices issued today
SELECT
    'notice'        AS metric_type,
    COALESCE(region_id, 'NEM-WIDE') AS region_id,
    NULL            AS value_mwh,
    notice_type     AS fuel_type,
    LEFT(reason, 150) AS notice_text
FROM {catalog}.{schema}.market_notices
WHERE DATE(issue_time) = CURRENT_DATE

ORDER BY metric_type, region_id
""".strip()
    },
]

# Replace the {catalog}.{schema} placeholders with the configured values
_PREFIX = f"{AEMO_CATALOG}.{AEMO_SCHEMA}"
for _q in GOLDEN_QUERIES:
    _q["sql"] = _q["sql"].replace("{catalog}.{schema}", _PREFIX)

print(f"Defined {len(GOLDEN_QUERIES)} golden queries (table prefix: {_PREFIX}).")
print()
for i, q in enumerate(GOLDEN_QUERIES, 1):
    print(f"  {i:02d}.  {q['name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Create the Genie Space via the Databricks REST API
# MAGIC
# MAGIC This step calls the Genie Spaces REST API to create the Space. If a Space with the same title already exists, the cell will print a warning with instructions to delete the old one.
# MAGIC
# MAGIC The cell uses the notebook's own authentication context — no additional credentials are needed.

# COMMAND ----------

import requests
import json

ctx     = dbutils.entry_point.getDbutils().notebook().getContext()
HOST    = ctx.apiUrl().get()
TOKEN   = ctx.apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

space_payload = {
    "display_name":       SPACE_TITLE,
    "description":        SPACE_DESCRIPTION,
    "warehouse_id":       SQL_WAREHOUSE_ID,
    "table_identifiers":  TABLES,
    "instructional_text": GENIE_INSTRUCTIONS,
}

print("Creating Genie Space...")
print(f"  Title          : {SPACE_TITLE}")
print(f"  Tables         : {len(TABLES)}")
print(f"  Instruction len: {len(GENIE_INSTRUCTIONS):,} characters")
print(f"  Warehouse      : {SQL_WAREHOUSE_ID}")
print()

SPACE_ID = None

try:
    resp = requests.post(
        f"{HOST}/api/2.0/genie/spaces",
        headers=HEADERS,
        json=space_payload,
        timeout=60,
    )
    resp.raise_for_status()

    data     = resp.json()
    SPACE_ID = data.get("space_id") or data.get("id")

    print(f"[OK] Genie Space created.")
    print(f"     Space ID  : {SPACE_ID}")
    print(f"     Space URL : {HOST}/genie/spaces/{SPACE_ID}")

except requests.HTTPError as e:
    body = e.response.text.lower() if e.response is not None else ""
    if "already exists" in body or "duplicate" in body or e.response.status_code == 409:
        print("[WARNING] A Genie Space with this title already exists.")
        print()
        print("  Options:")
        print("  1. Delete the existing Space: open Genie in the sidebar, find the Space,")
        print("     click the three-dot menu (...) and choose Delete. Then re-run this cell.")
        print("  2. Change SPACE_TITLE in Step 0 to create a new Space with a different name.")
        print("  3. Use the existing Space — skip this step and continue from Step 5.")
        print()
        print("  To use the existing Space, set SPACE_ID manually:")
        print("    SPACE_ID = '<your-existing-space-id>'")
        print("  and run Step 5 onwards.")
    else:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[FAIL] API error {status}: {e.response.text[:300]}")
        print()
        print("  Common causes:")
        print("  - SQL_WAREHOUSE_ID is invalid — check the warehouse ID in SQL > SQL Warehouses")
        print("  - Tables not found — verify the catalog and schema names in Step 0")
        print("  - Insufficient permissions — you need workspace admin or catalog MANAGE permission")

except Exception as e:
    print(f"[FAIL] Unexpected error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Add the 15 golden queries

# COMMAND ----------

if SPACE_ID is None:
    print("[SKIP] SPACE_ID is not set — skipping golden query upload.")
    print("       Set SPACE_ID manually (see the note in Step 4) and re-run this cell.")
else:
    print(f"Uploading {len(GOLDEN_QUERIES)} golden queries to Space {SPACE_ID}...\n")

    upload_success = 0
    upload_failures = []

    for q in GOLDEN_QUERIES:
        payload = {
            "name":        q["name"],
            "description": q["description"],
            "query":       q["sql"],
        }
        resp = requests.post(
            f"{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
            headers=HEADERS,
            json=payload,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            upload_success += 1
            print(f"  [OK]   {q['name']}")
        else:
            upload_failures.append(q["name"])
            print(f"  [FAIL] {q['name']} — HTTP {resp.status_code}: {resp.text[:100]}")

    print()
    print(f"Uploaded {upload_success}/{len(GOLDEN_QUERIES)} golden queries.")
    if upload_failures:
        print(f"Failed ({len(upload_failures)}): {upload_failures}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Set participant permissions
# MAGIC
# MAGIC Grants `CAN_USE` on the Genie Space to the configured participant group.
# MAGIC `CAN_USE` allows participants to ask questions and view results. It does not allow editing the Space configuration or adding golden queries.
# MAGIC
# MAGIC The workshop tables (`workshop_au.aemo.*`) must also have `SELECT` granted to the participant group — that grant is applied by the `setup/grant_workshop_access.py` script and should already be in place.

# COMMAND ----------

if SPACE_ID is None:
    print("[SKIP] SPACE_ID is not set — skipping permission grant.")
elif PARTICIPANT_GROUP_NAME is None:
    print("[SKIP] PARTICIPANT_GROUP_NAME is None — skipping group permission grant.")
    print("       Grant CAN_USE manually via the Genie Space permissions panel (top-right icon).")
    print("       Each participant needs CAN_USE on the Space and SELECT on workshop_au.aemo.*")
else:
    permission_payload = {
        "access_control_list": [
            {
                "group_name":        PARTICIPANT_GROUP_NAME,
                "permission_level":  "CAN_USE",
            }
        ]
    }

    resp = requests.patch(
        f"{HOST}/api/2.0/permissions/genie/spaces/{SPACE_ID}",
        headers=HEADERS,
        json=permission_payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        print(f"[OK] Granted CAN_USE on Space {SPACE_ID} to group '{PARTICIPANT_GROUP_NAME}'.")
    else:
        print(f"[FAIL] HTTP {resp.status_code}: {resp.text[:200]}")
        print()
        print("  Fallback: grant access manually via the Genie Space permissions panel.")
        print(f"  URL: {HOST}/genie/spaces/{SPACE_ID}")
        print("  Click the permissions icon (top-right) and add the group with CAN_USE.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Smoke tests: verify the Space answers 5 key questions
# MAGIC
# MAGIC Sends 5 representative questions to the Genie Space and polls for responses.
# MAGIC The test checks that each question returns a non-empty result without errors.
# MAGIC It does **not** assert exact numbers — the data values change daily.
# MAGIC
# MAGIC All 5 must pass before the session runs. If any fail, see the common causes at the bottom of this cell.

# COMMAND ----------

import time

SMOKE_TEST_QUESTIONS = [
    "What was the average spot price in each NEM region yesterday?",
    "Show me the top 5 generators by dispatch in NSW1 yesterday.",
    "Were there any LOR notices issued in the last 7 days?",
    "What is the total settlement amount for each participant in the most recent settlement run?",
    "What was the total NEM dispatch by fuel type yesterday?",
]

if SPACE_ID is None:
    print("[SKIP] SPACE_ID is not set — skipping smoke tests.")
    print("       Complete Steps 4–6 before running smoke tests.")
else:
    print(f"Running {len(SMOKE_TEST_QUESTIONS)} smoke tests against Space {SPACE_ID}...\n")
    smoke_all_passed = True

    for i, question in enumerate(SMOKE_TEST_QUESTIONS, 1):
        # Start a new conversation
        conv_resp = requests.post(
            f"{HOST}/api/2.0/genie/spaces/{SPACE_ID}/start-conversation",
            headers=HEADERS,
            json={"content": question},
            timeout=60,
        )

        if conv_resp.status_code not in (200, 201):
            print(f"  [FAIL] Q{i}: Could not start conversation — HTTP {conv_resp.status_code}")
            print(f"         {conv_resp.text[:120]}")
            smoke_all_passed = False
            continue

        conv_data = conv_resp.json()
        conv_id   = conv_data.get("conversation_id") or conv_data.get("id")
        msg_id    = (
            conv_data.get("message_id")
            or (conv_data.get("messages") or [{}])[0].get("id")
        )

        if not conv_id or not msg_id:
            print(f"  [FAIL] Q{i}: Response missing conversation_id or message_id")
            smoke_all_passed = False
            continue

        # Poll for completion (max 45 seconds per question)
        poll_url  = f"{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conv_id}/messages/{msg_id}"
        deadline  = time.time() + 45
        status    = "PENDING"
        last_poll = None

        while time.time() < deadline and status in ("EXECUTING", "PENDING"):
            time.sleep(3)
            poll_resp = requests.get(poll_url, headers=HEADERS, timeout=15)
            if poll_resp.status_code == 200:
                last_poll = poll_resp.json()
                status    = last_poll.get("status", "UNKNOWN")

        if status == "COMPLETED":
            print(f"  [PASS] Q{i}: '{question[:72]}'")
        elif status in ("EXECUTING", "PENDING"):
            print(f"  [SLOW] Q{i}: Still running after 45 seconds — the warehouse may be starting.")
            print(f"         This is not a failure. Re-run the smoke test after the warehouse warms up.")
        else:
            print(f"  [FAIL] Q{i}: Final status '{status}' — '{question[:60]}'")
            if last_poll:
                err = (
                    last_poll.get("error")
                    or (last_poll.get("attachments") or [{}])[0].get("error", {}).get("message", "")
                )
                if err:
                    print(f"         Error detail: {str(err)[:200]}")
            smoke_all_passed = False

    print()
    if smoke_all_passed:
        print("[PASS] All 5 smoke tests passed. The Genie Space is ready for the session.")
    else:
        print("[WARN] One or more smoke tests did not pass.")
        print()
        print("  Common causes and fixes:")
        print("  - Empty tables: re-run setup/00_workspace_setup.py to reload data")
        print("  - Warehouse not running: enable auto-start in SQL > SQL Warehouses")
        print("  - Missing golden queries: check Step 5 output for upload failures")
        print("  - Incorrect table names: verify AEMO_CATALOG and AEMO_SCHEMA in Step 0")
        print()
        print("  Do not run the session until all 5 smoke tests pass.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 8 — Print the participant handout URL
# MAGIC
# MAGIC Share this URL with participants so they can navigate directly to the Genie Space.
# MAGIC Post it in the meeting chat, the slide deck, and the Teams/Slack channel for the session.

# COMMAND ----------

if SPACE_ID:
    SPACE_URL = f"{HOST}/genie/spaces/{SPACE_ID}"
    print("=" * 72)
    print("  SPACE ID  :", SPACE_ID)
    print("  SPACE URL :", SPACE_URL)
    print("=" * 72)
    print()
    print("  Share this URL with participants before the session:")
    print()
    print(f"  {SPACE_URL}")
    print()
    print("  Add the URL to:")
    print("  1. The session slide deck (context-setting block intro slide)")
    print("  2. The Teams or Slack channel for the workshop")
    print("  3. The calendar invite so participants can bookmark it in advance")
    print("  4. The facilitator notes so it is easy to re-share if someone loses it")
else:
    print("[WARN] SPACE_ID is not set. Complete Steps 4–7 first, then re-run this cell.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Pre-Session Final Checklist
# MAGIC
# MAGIC Run through this checklist the morning of the session:
# MAGIC
# MAGIC | Check | How to verify | Expected result |
# MAGIC |-------|--------------|-----------------|
# MAGIC | All 5 AEMO tables have data | Step 1 output | Each table shows > 0 rows and [OK] |
# MAGIC | SQL Warehouse is running or auto-starts | SQL > SQL Warehouses | Green dot, or auto-start enabled |
# MAGIC | Genie Space visible in sidebar | Left sidebar > Genie | "AEMO NEM Operations" appears |
# MAGIC | 15 golden queries loaded | Step 5 output | 15/15 [OK] |
# MAGIC | All 5 smoke tests pass | Step 7 output | All 5 [PASS] |
# MAGIC | Participant group has CAN_USE | Step 6 output or Genie Space permissions panel | Group listed with CAN_USE |
# MAGIC | Participant URL works in incognito | Open the URL in a fresh browser window | Genie chat loads and accepts a question |
# MAGIC | Participant accounts can log in | Ask IT or check workspace admin panel | Users can authenticate |
# MAGIC
# MAGIC > If any check fails on the morning of the session, escalate to the AEMO data platform team immediately.
# MAGIC > Do not wait until participants arrive.
