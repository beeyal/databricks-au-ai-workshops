# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 28px 36px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 01: Genie Space Setup</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">Admin Perspective — Australian Energy NEM Domain</p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="width:100%; border-collapse:collapse; margin-top:16px; font-family:'DM Sans',sans-serif;">
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px; width:25%"><b>Workshop</b></td><td style="padding:8px 16px;">Genie Spaces &amp; AI Features — Australian Regulated Industries</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Role</b></td><td style="padding:8px 16px;">Platform Admin / Data Engineer</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Prerequisites</b></td><td style="padding:8px 16px;"><code>CREATE SCHEMA</code> privilege in your UC catalog &nbsp;|&nbsp; <code>workspace_admin</code> or <code>genie_admin</code> entitlement</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Objectives</b></td><td style="padding:8px 16px;">Create schema + tables with column comments → create Genie Space via API → add trusted assets, golden queries, instructions, permissions → smoke test</td></tr>
# MAGIC </table>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before the Code: UI Orientation
# MAGIC
# MAGIC Open the Genie interface before running any cells so you know where to look when the space appears.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Genie (sparkle icon) → [+ New Space] button (top right)
# MAGIC
# MAGIC New Space form fields:
# MAGIC   Title*       required
# MAGIC   Description  optional
# MAGIC   SQL Warehouse*  select your serverless warehouse
# MAGIC   Tables       click [+ Add tables] → browse Catalog → check boxes → Add
# MAGIC
# MAGIC After creation you land on the Configure tab:
# MAGIC   Instructions | SQL queries | Permissions
# MAGIC ```
# MAGIC
# MAGIC To find a Space ID later: open the space → look at the browser URL → copy the ID from `.../genie/rooms/{id}`.

# COMMAND ----------

# Install / confirm SDK version — Genie API requires >= 0.28
%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import os, requests, json, uuid, random
from datetime import datetime, date, timedelta
from pyspark.sql import Row
from databricks.sdk import WorkspaceClient

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

print(f"Connected to : {w.config.host}")
print(f"Current user : {w.current_user.me().user_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Workshop Configuration

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",      "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA      = dbutils.widgets.get("schema")
PT_ENDPOINT = dbutils.widgets.get("pt_endpoint")

print(f"Using: {CATALOG}.{SCHEMA}  |  PT endpoint: {PT_ENDPOINT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 1 — Create Unity Catalog Schema and Sample Tables</h2>
# MAGIC </div>
# MAGIC
# MAGIC All tables live in `{catalog}.{schema}` and model the Australian NEM (National Electricity Market) domain.
# MAGIC Rich column comments are critical: Genie reads UC metadata before generating SQL, so comments teach it correct units, allowed values, and join keys.
# MAGIC
# MAGIC | Table | Grain | Description |
# MAGIC |---|---|---|
# MAGIC | `meter_readings` | One row per NMI per 30-min interval | Half-hourly interval meter data (NEM12) |
# MAGIC | `assets` | One row per asset | Substation and feeder asset register |
# MAGIC | `outages` | One row per outage event | Planned and unplanned network events |
# MAGIC | `regulatory_reports` | One row per document | AEMO / AER compliance document metadata |

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"Schema ready: {CATALOG}.{SCHEMA}")

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.meter_readings (
    nmi               STRING    COMMENT 'National Metering Identifier — unique ID for each electricity connection point. Format: state letter + 10 digits, e.g. Q0000000001.',
    interval_datetime TIMESTAMP COMMENT 'Start of the 30-minute measurement interval in AEST (UTC+10). Do NOT multiply by 2 to get hourly totals — use SUM over the window. Example: 2024-06-01T07:00:00',
    active_energy_kwh DOUBLE    COMMENT 'Active energy imported by the consumer during this 30-minute interval, in kilowatt-hours. Typical residential range: 0.05–4.0 kWh. Daily total = SUM for a given NMI and day. Monthly MWh = SUM / 1000.',
    quality_flag      STRING    COMMENT 'NEM12 data confidence flag. A=Actual (field reading), E=Estimated (history-based), S=Substituted (manual correction), N=None (missing). Exclude S and N from consumption totals unless investigating data quality.',
    meter_type        STRING    COMMENT 'Meter technology: SMART=Advanced Metering Infrastructure (AMI), BASIC=accumulation meter, CT=current-transformer metered (large commercial).',
    distribution_zone STRING    COMMENT 'DNSP distribution zone name, e.g. ENERGEX_NORTH, AUSNET_EAST, AUSGRID_SOUTH.',
    created_at        TIMESTAMP COMMENT 'UTC timestamp when this record was ingested into the data platform.'
)
USING DELTA
PARTITIONED BY (distribution_zone)
COMMENT 'Half-hourly interval meter readings sourced from AEMO NEM12 files. One row per NMI per 30-minute interval. For hourly or daily aggregations always SUM — never multiply intervals.'
TBLPROPERTIES ('delta.autoOptimize.autoCompact'='true','delta.autoOptimize.optimizeWrite'='true')
""")
print("meter_readings created.")

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.assets (
    asset_id           STRING  COMMENT 'Internal asset identifier (UUID). Primary key — referenced as FK in outages.asset_id.',
    asset_name         STRING  COMMENT 'Human-readable asset name, e.g. "Essendon Zone Substation 66kV".',
    asset_type         STRING  COMMENT 'Asset class. Values: ZONE_SUBSTATION, FEEDER, TRANSFORMER, CIRCUIT_BREAKER, CABLE.',
    voltage_kv         DOUBLE  COMMENT 'Rated voltage in kilovolts. Common values: 66, 110, 220, 500.',
    capacity_mva       DOUBLE  COMMENT 'Rated capacity in MVA. NULL for low-voltage assets below 11 kV.',
    commissioning_date DATE    COMMENT 'Date the asset was energised and placed into service. Used for age calculations.',
    last_maintenance   DATE    COMMENT 'Date of most recent maintenance inspection. Assets > 12 months since last_maintenance are overdue.',
    region             STRING  COMMENT 'NEM region code. Values: QLD1, NSW1, VIC1, SA1, TAS1.',
    latitude           DOUBLE  COMMENT 'WGS-84 latitude of asset location (decimal degrees, negative for Australia).',
    longitude          DOUBLE  COMMENT 'WGS-84 longitude of asset location (decimal degrees).',
    status             STRING  COMMENT 'Operational status. Values: IN_SERVICE, DECOMMISSIONED, UNDER_MAINTENANCE.',
    owner_dnsp         STRING  COMMENT 'Owning Distribution Network Service Provider. Values: AUSNET, JEMENA, CITIPOWER, POWERCOR, AUSGRID, ENERGEX.'
)
USING DELTA
COMMENT 'Network asset register for substations, feeders and major plant. One row per asset. Updated weekly from field maintenance system. Join to outages via asset_id.'
""")
print("assets created.")

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.outages (
    outage_id              STRING    COMMENT 'Unique outage event identifier (UUID). Primary key.',
    asset_id               STRING    COMMENT 'FK -> assets.asset_id. Identifies which network asset was affected.',
    outage_type            STRING    COMMENT 'Type of outage. Values: PLANNED (scheduled maintenance), UNPLANNED (fault). Only UNPLANNED events count toward AER SAIDI/SAIFI targets.',
    cause_category         STRING    COMMENT 'Root cause classification. Values: WEATHER, EQUIPMENT_FAILURE, VEGETATION, THIRD_PARTY, UNKNOWN. Used in AER STPIS narrative reporting.',
    start_time             TIMESTAMP COMMENT 'Actual start of supply interruption in AEST. Used in SAIDI duration calculations.',
    end_time               TIMESTAMP COMMENT 'Actual restoration of supply in AEST. NULL means outage is still active. Duration = TIMESTAMPDIFF(MINUTE, start_time, end_time).',
    customers_affected     INT       COMMENT 'Count of unique customer connection points (ICPs) interrupted. Used as the SAIDI/SAIFI numerator weight.',
    energy_not_served_mwh  DOUBLE    COMMENT 'Energy Not Served (ENS) in MWh. NULL for outages < 1 minute — use COALESCE(energy_not_served_mwh, 0) in SUM aggregations. Reported to AER in STPIS annual submission.',
    suburb                 STRING    COMMENT 'Suburb or locality name for community reporting.',
    region                 STRING    COMMENT 'NEM region code: QLD1, NSW1, VIC1, SA1, TAS1.',
    reported_to_aer        BOOLEAN   COMMENT 'TRUE if this event met AER reporting threshold (unplanned outage >= 1 customer for >= 1 minute). Only reported events count in official SAIDI/SAIFI statistics.',
    created_at             TIMESTAMP COMMENT 'Record creation timestamp (UTC).'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Network outage event log. One row = one continuous supply interruption on one asset. SAIDI formula: SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) x customers_affected) / total_ICPs. Filter outage_type = UNPLANNED for AER regulatory metrics.'
""")
print("outages created.")

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.regulatory_reports (
    report_id          STRING    COMMENT 'Unique report identifier (UUID).',
    report_type        STRING    COMMENT 'Report category. Values: ANNUAL_PLANNING, RELIABILITY_REPORT, CPEC_SUBMISSION, RIT_T, STPIS.',
    title              STRING    COMMENT 'Full document title as published on the AER or AEMO website.',
    period_start       DATE      COMMENT 'First day of the regulatory reporting period covered by this document.',
    period_end         DATE      COMMENT 'Last day of the regulatory reporting period.',
    submission_date    DATE      COMMENT 'Date submitted to AEMO or AER.',
    submitting_entity  STRING    COMMENT 'Entity that submitted. Values: AEMO, AUSNET, JEMENA, TRANSGRID, CITIPOWER.',
    document_url       STRING    COMMENT 'URL to the published PDF on the regulator website.',
    document_text      STRING    COMMENT 'Full extracted plain text of the document for AI summarisation and search. May contain minor OCR artefacts from PDF extraction.',
    status             STRING    COMMENT 'Lifecycle status. Values: DRAFT, SUBMITTED, PUBLISHED, SUPERSEDED.',
    created_at         TIMESTAMP COMMENT 'Record ingestion timestamp (UTC).'
)
USING DELTA
COMMENT 'Regulatory document register for AEMO / AER compliance submissions. One row per document. Standalone table — no FK relationships. document_text holds extracted PDF content for Genie search workflows.'
""")
print("regulatory_reports created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1e — Seed sample data

# COMMAND ----------

random.seed(42)

# meter_readings — 3 NMIs x 5 days x 24 intervals = 360 rows
zones = ["ENERGEX_NORTH", "AUSNET_EAST", "AUSGRID_SOUTH"]
rows  = []
for nmi_idx in range(3):
    nmi  = f"Q{1000000 + nmi_idx:08d}"
    zone = zones[nmi_idx]
    for day_offset in range(5):
        base = datetime(2024, 6, 1) + timedelta(days=day_offset)
        for interval in range(24):
            rows.append(Row(
                nmi=nmi, interval_datetime=base + timedelta(hours=interval),
                active_energy_kwh=round(random.uniform(0.5, 4.2), 4),
                quality_flag=random.choice(["A", "A", "A", "E"]),
                meter_type="SMART", distribution_zone=zone, created_at=datetime.now()
            ))
spark.createDataFrame(rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.meter_readings")

# assets — 20 rows
asset_types = ["ZONE_SUBSTATION", "FEEDER", "TRANSFORMER", "CIRCUIT_BREAKER"]
dnsps       = ["AUSNET", "JEMENA", "CITIPOWER", "POWERCOR"]
asset_rows  = []
for i in range(20):
    asset_rows.append(Row(
        asset_id=str(uuid.uuid4()),
        asset_name=f"{'Substation' if i % 3 == 0 else 'Feeder'} {i+1:03d}",
        asset_type=asset_types[i % 4], voltage_kv=float(random.choice([66, 110, 220, 500])),
        capacity_mva=float(random.choice([30, 60, 120, 250])) if i % 5 != 0 else None,
        commissioning_date=date(random.randint(1985, 2020), random.randint(1, 12), 1),
        last_maintenance=date(2024, random.randint(1, 6), random.randint(1, 28)),
        region=random.choice(["VIC1", "NSW1", "QLD1"]),
        latitude=-37.8 + random.uniform(-1, 1), longitude=145.0 + random.uniform(-2, 2),
        status=random.choice(["IN_SERVICE", "IN_SERVICE", "IN_SERVICE", "UNDER_MAINTENANCE"]),
        owner_dnsp=dnsps[i % 4]
    ))
spark.createDataFrame(asset_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.assets")

# outages — 30 rows
causes      = ["WEATHER", "EQUIPMENT_FAILURE", "VEGETATION", "THIRD_PARTY", "UNKNOWN"]
outage_rows = []
for i in range(30):
    start      = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))
    duration_h = random.uniform(0.5, 8)
    outage_rows.append(Row(
        outage_id=str(uuid.uuid4()), asset_id=asset_rows[i % 20].asset_id,
        outage_type=random.choice(["PLANNED", "UNPLANNED", "UNPLANNED"]),
        cause_category=random.choice(causes), start_time=start,
        end_time=start + timedelta(hours=duration_h),
        customers_affected=random.randint(10, 5000),
        energy_not_served_mwh=round(random.uniform(0.1, 50.0), 3),
        suburb=random.choice(["Essendon", "Footscray", "Sunshine", "Broadmeadows", "Ringwood"]),
        region=random.choice(["VIC1", "NSW1", "QLD1"]),
        reported_to_aer=random.choice([True, False]), created_at=datetime.now()
    ))
spark.createDataFrame(outage_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.outages")

# regulatory_reports — 10 rows
report_types = ["ANNUAL_PLANNING", "RELIABILITY_REPORT", "CPEC_SUBMISSION", "RIT_T", "STPIS"]
report_rows  = []
for i in range(10):
    report_rows.append(Row(
        report_id=str(uuid.uuid4()), report_type=report_types[i % 5],
        title=f"NEM {report_types[i % 5].replace('_', ' ').title()} FY2{23 + (i // 5)}",
        period_start=date(2023, 7, 1), period_end=date(2024, 6, 30),
        submission_date=date(2024, random.randint(7, 10), random.randint(1, 28)),
        submitting_entity=random.choice(["AUSNET", "AEMO", "TRANSGRID", "JEMENA"]),
        document_url=f"https://www.aer.gov.au/documents/report-{i+1:04d}",
        document_text=(
            f"Regulatory report {i+1}. Network reliability targets were "
            f"{'met' if i % 2 == 0 else 'partially met'}. "
            f"SAIDI for the period was {random.uniform(60, 120):.1f} minutes. "
            f"Capital expenditure totalled ${random.randint(20, 200)}M."
        ),
        status=random.choice(["PUBLISHED", "PUBLISHED", "SUBMITTED", "DRAFT"]),
        created_at=datetime.now()
    ))
spark.createDataFrame(report_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_reports")

print("Sample data loaded.")
for tbl in ["meter_readings", "assets", "outages", "regulatory_reports"]:
    count = spark.table(f"{CATALOG}.{SCHEMA}.{tbl}").count()
    print(f"  {CATALOG}.{SCHEMA}.{tbl:30s}  {count:>6,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 2 — Create a Genie Space via API</h2>
# MAGIC </div>
# MAGIC
# MAGIC The REST API path is preferred for repeatable deployments (CI/CD, Asset Bundles). The UI path (Left sidebar → Genie → + New Space) produces the same result but is manual.

# COMMAND ----------

def get_headers():
    t = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}

resp = requests.post(
    f"https://{HOST}/api/2.0/genie/spaces",
    headers=get_headers(),
    json={
        "title": "NEM Grid Operations — Energy Analytics",
        "description": (
            "Self-service analytics for NEM grid operations, outage management, "
            "asset health and regulatory reporting."
        )
    }
)
resp.raise_for_status()
SPACE_ID = resp.json()["space_id"]

print(f"Genie Space created.")
print(f"  Space ID  : {SPACE_ID}")
print(f"  Space URL : https://{HOST}/genie/spaces/{SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 3 — Add Tables as Trusted Assets</h2>
# MAGIC </div>
# MAGIC
# MAGIC Trusted assets are a security control: Genie only queries tables explicitly added here, even if the workspace credential could access others. UI equivalent: Configure tab → click **[+ Add tables]** → browse to your schema → select all 4 tables.

# COMMAND ----------

TABLES_TO_ADD = [
    f"{CATALOG}.{SCHEMA}.meter_readings",
    f"{CATALOG}.{SCHEMA}.assets",
    f"{CATALOG}.{SCHEMA}.outages",
    f"{CATALOG}.{SCHEMA}.regulatory_reports",
]

for table_fqn in TABLES_TO_ADD:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/trusted-assets",
        headers=get_headers(),
        json={"asset_type": "TABLE", "asset_fqn": table_fqn}
    )
    icon = "OK  " if resp.status_code in (200, 201) else f"WARN {resp.status_code}"
    print(f"  [{icon}]  {table_fqn}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 4 — Seed the Knowledge Store with Golden Queries</h2>
# MAGIC </div>
# MAGIC
# MAGIC Golden queries are the single most impactful configuration lever: they teach Genie the correct SQL and aggregation formulas for your most important business questions. UI equivalent: Configure tab → SQL queries → **[+ Add query]** → enter question + SQL → Save.

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Total outage duration by region — current financial year",
        "description": "SAIDI-contributing outage hours by NEM region for the current Australian financial year (July 1–June 30). Excludes planned outages.",
        "sql": f"""
-- SAIDI numerator by region for the current Australian financial year
-- Only UNPLANNED outages count toward AER SAIDI/SAIFI regulatory metrics
SELECT
    region,
    COUNT(*)                                                         AS outage_count,
    SUM(customers_affected)                                          AS total_customer_interruptions,
    ROUND(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) AS total_outage_hours,
    SUM(COALESCE(energy_not_served_mwh, 0))                          AS total_ens_mwh
FROM {CATALOG}.{SCHEMA}.outages
WHERE outage_type = 'UNPLANNED'
  AND start_time >= DATE_TRUNC('year', ADD_MONTHS(CURRENT_DATE, -((MONTH(CURRENT_DATE) - 7 + 12) % 12)))
GROUP BY region
ORDER BY total_customer_interruptions DESC
"""
    },
    {
        "name": "Top 10 worst assets by cumulative unplanned outage frequency",
        "description": "Asset reliability league table — identifies chronic problem assets. Joins outages to the asset register on asset_id.",
        "sql": f"""
SELECT
    a.asset_name, a.asset_type, a.owner_dnsp, a.region,
    COUNT(o.outage_id)                                               AS outage_count,
    SUM(o.customers_affected)                                        AS total_customers_affected,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time))/60,2) AS avg_outage_hours,
    a.last_maintenance
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id AND o.outage_type = 'UNPLANNED'
GROUP BY a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp, a.region, a.last_maintenance
ORDER BY outage_count DESC
LIMIT 10
"""
    },
    {
        "name": "Monthly meter reading totals by distribution zone",
        "description": "Aggregates smart meter interval data to monthly active energy consumption per zone. Excludes poor-quality flags.",
        "sql": f"""
-- Exclude quality_flag S (substituted) and N (missing) from totals
SELECT
    distribution_zone,
    DATE_TRUNC('month', interval_datetime) AS month,
    COUNT(DISTINCT nmi)                    AS unique_meters,
    ROUND(SUM(active_energy_kwh), 1)       AS total_energy_kwh,
    ROUND(AVG(active_energy_kwh), 4)       AS avg_interval_kwh
FROM {CATALOG}.{SCHEMA}.meter_readings
WHERE quality_flag IN ('A', 'E')
GROUP BY distribution_zone, DATE_TRUNC('month', interval_datetime)
ORDER BY month DESC, distribution_zone
"""
    },
    {
        "name": "Outstanding regulatory submissions due in the next 90 days",
        "description": "Compliance calendar showing DRAFT/SUBMITTED reports with submission_date within 90 days.",
        "sql": f"""
SELECT
    report_type, title, submitting_entity,
    period_end                              AS reporting_period_end,
    submission_date                         AS scheduled_submission_date,
    status,
    DATEDIFF(submission_date, CURRENT_DATE) AS days_until_due
FROM {CATALOG}.{SCHEMA}.regulatory_reports
WHERE status IN ('DRAFT', 'SUBMITTED')
  AND submission_date BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, 90)
ORDER BY submission_date
"""
    },
    {
        "name": "AER-reportable outages broken down by cause category",
        "description": "Cause analysis for AER-reportable events. Used for STPIS narrative sections.",
        "sql": f"""
SELECT
    cause_category,
    COUNT(*)                                           AS reportable_events,
    SUM(customers_affected)                            AS customers_affected,
    ROUND(SUM(COALESCE(energy_not_served_mwh, 0)), 2)  AS total_ens_mwh,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) AS avg_duration_hours
FROM {CATALOG}.{SCHEMA}.outages
WHERE reported_to_aer = TRUE
GROUP BY cause_category
ORDER BY reportable_events DESC
"""
    },
]

for q in GOLDEN_QUERIES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=get_headers(),
        json={"name": q["name"], "description": q["description"], "query": q["sql"].strip()}
    )
    icon = "OK  " if resp.status_code in (200, 201) else f"ERROR {resp.status_code}"
    print(f"  [{icon}]  {q['name']}")

print(f"\nTotal golden queries added: {len(GOLDEN_QUERIES)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 5 — Write Instructions to the Space</h2>
# MAGIC </div>
# MAGIC
# MAGIC Instructions act as the system prompt: every conversation starts with this text in context. UI equivalent: Configure tab → Instructions → paste text → Save.

# COMMAND ----------

GENIE_INSTRUCTIONS = """
You are an energy data analyst assistant for an Australian Distribution Network Service Provider (DNSP).
Your primary users are grid operations managers, regulatory analysts, and asset managers.

## Domain Context
- Data covers the National Electricity Market (NEM): QLD1, NSW1, VIC1, SA1, TAS1
- All timestamps are in Australian Eastern Standard Time (AEST / UTC+10) unless otherwise stated
- NMI = National Metering Identifier — unique ID for each electricity connection point
- SAIDI = System Average Interruption Duration Index (minutes per customer per year) — key AER reliability metric
- SAIFI = System Average Interruption Frequency Index (interruptions per customer per year)
- ENS   = Energy Not Served (MWh) — reported in AER STPIS submissions
- DNSP  = Distribution Network Service Provider (e.g. AusNet, Jemena, Citipower)

## Default Behaviour
- Unless the user specifies a region, show data for ALL regions (no default filter)
- When calculating SAIDI: SUM((end_time - start_time in minutes) * customers_affected) / total_customers
- "This year" = current Australian financial year (July 1 – June 30)
- "Last year" = previous Australian financial year
- Express outage durations in hours rounded to 1 decimal place
- Sort results most-recent-first unless the user asks for ranking by a metric
- Always use COALESCE(energy_not_served_mwh, 0) in SUM aggregations

## Key Relationships
- outages.asset_id -> assets.asset_id (many outages per asset)
- regulatory_reports is standalone (document repository, no FK relationships)

## Important Limitations
- meter_readings contains 30-minute intervals; do NOT multiply by 2 to get hourly totals
- energy_not_served_mwh may be NULL for outages < 1 minute; treat NULL as 0 in aggregations
- Only UNPLANNED outages count toward AER SAIDI/SAIFI regulatory reporting
"""

resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=get_headers(),
    json={"instructions": GENIE_INSTRUCTIONS.strip()}
)
if resp.status_code == 200:
    print(f"Instructions updated successfully. Length: {len(GENIE_INSTRUCTIONS):,} chars")
else:
    print(f"WARN: {resp.status_code} — {resp.text[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 6 — Set Permissions</h2>
# MAGIC </div>
# MAGIC
# MAGIC Assign `CAN_USE` (chat only) to analyst groups and `CAN_MANAGE` (edit instructions/queries) to data engineers. Best practice: assign to UC groups, not individual users. UI: Configure tab → Permissions → **[+ Add]** → search group → choose level → Save.

# COMMAND ----------

# TODO: replace group names with groups that exist in your workspace
PERMISSION_GRANTS = [
    # {"group_name": "grid-operations-analysts", "permission_level": "CAN_USE"},
    # {"group_name": "regulatory-reporting-team", "permission_level": "CAN_USE"},
    # {"group_name": "data-platform-engineers",   "permission_level": "CAN_MANAGE"},
]

for grant in PERMISSION_GRANTS:
    resp = requests.patch(
        f"https://{HOST}/api/2.0/permissions/genie/spaces/{SPACE_ID}",
        headers=get_headers(),
        json={"access_control_list": [
            {"group_name": grant["group_name"], "permission_level": grant["permission_level"]}
        ]}
    )
    icon = "OK  " if resp.status_code == 200 else f"ERROR {resp.status_code}"
    print(f"  [{icon}]  {grant['group_name']} -> {grant['permission_level']}")

if not PERMISSION_GRANTS:
    print("No grants configured — uncomment entries in PERMISSION_GRANTS to apply.")
    print("Space is currently accessible only to the creator (IS_OWNER).")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 7 — Smoke Test via Conversation API</h2>
# MAGIC </div>
# MAGIC
# MAGIC Start a programmatic conversation to confirm the space is wired up before sharing with users.

# COMMAND ----------

def genie_ask(space_id: str, question: str) -> dict:
    import time
    start_resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{space_id}/start-conversation",
        headers=get_headers(),
        json={"content": question}
    )
    start_resp.raise_for_status()
    data            = start_resp.json()
    conversation_id = data["conversation_id"]
    message_id      = data["message_id"]
    print(f"  Conversation started: {conversation_id}")

    for attempt in range(30):
        poll  = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}",
            headers=get_headers()
        )
        msg   = poll.json()
        state = msg.get("status", "UNKNOWN")
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            return msg
        print(f"  [{attempt+1}/30]  Status: {state} — waiting 2s...")
        time.sleep(2)

    return {"status": "TIMEOUT"}


TEST_QUESTION = "How many unplanned outages occurred in VIC1 and what was the total energy not served?"
print(f"Smoke test question: \"{TEST_QUESTION}\"\n")

result = genie_ask(SPACE_ID, TEST_QUESTION)
print(f"\nStatus: {result.get('status')}")
for att in result.get("attachments", []):
    if att.get("query"):
        print(f"\nGenerated SQL:\n{'='*50}\n{att['query'].get('query','')}\n{'='*50}")
    if att.get("text"):
        print(f"\nNarrative: {att['text'].get('content','')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Checkpoint — Verify in the UI
# MAGIC
# MAGIC Before moving to Lab 02, confirm your space in the Databricks UI.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Genie → your space should appear under "My spaces"
# MAGIC
# MAGIC Configure tab should show:
# MAGIC   Instructions  → domain text (500+ chars)
# MAGIC   Tables (4)    → meter_readings, assets, outages, regulatory_reports
# MAGIC   SQL queries   → 5 golden queries
# MAGIC   Permissions   → your user as IS_OWNER
# MAGIC
# MAGIC Quick chat test: click [Chat] → type "How many unplanned outages are in the dataset?"
# MAGIC Expected answer: 30 (matches the sample rows inserted above)
# MAGIC ```

# COMMAND ----------

print("=" * 65)
print("  LAB 01 COMPLETE")
print("=" * 65)
print(f"  Catalog / Schema  :  {CATALOG}.{SCHEMA}")
print(f"  Genie Space ID    :  {SPACE_ID}")
print(f"  Genie Space URL   :  https://{HOST}/genie/spaces/{SPACE_ID}")
print()
print("  IMPORTANT: Copy the Space ID above.")
print("  You will paste it into SPACE_ID in Lab 02 and Lab 03.")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Review Questions
# MAGIC
# MAGIC 1. What is the difference between a **trusted asset** and a **golden query**? When does Genie use each one?
# MAGIC 2. The `instructions` field acts as a system prompt. What are **three things** you should always include for a regulated industry customer?
# MAGIC 3. Why add column-level `COMMENT` to tables **before** creating the Genie Space?
# MAGIC 4. A business analyst asks "what was our SAIDI last year?" and gets a wrong number. List **three possible causes** and the admin action to fix each.
# MAGIC 5. Which permission level should a read-only data consumer have — `CAN_USE` or `CAN_MANAGE`?
# MAGIC
# MAGIC **Proceed to Lab 02 when ready.**
