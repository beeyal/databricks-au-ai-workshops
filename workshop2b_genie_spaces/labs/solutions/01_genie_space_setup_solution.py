# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 01: Genie Space Setup (Admin Perspective) — SOLUTION
# MAGIC
# MAGIC **Workshop:** Genie Spaces & AI Features — Australian Regulated Industries
# MAGIC **Duration:** 35–40 minutes
# MAGIC **Role:** Platform Admin / Data Engineer
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC By the end of this lab you will be able to:
# MAGIC
# MAGIC 1. Create a Genie Space programmatically using the Databricks SDK
# MAGIC 2. Build the energy-sector sample tables in Unity Catalog
# MAGIC 3. Add trusted assets (Delta tables and dashboards) to the space
# MAGIC 4. Write effective Genie Space instructions — the "system prompt" that shapes every conversation
# MAGIC 5. Seed the knowledge store with verified SQL examples (golden queries)
# MAGIC 6. Set per-role permissions so only authorised users can converse with the space
# MAGIC 7. Run a smoke-test via the Conversation API to confirm the space is working
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Architecture Overview
# MAGIC
# MAGIC ```
# MAGIC Business Analyst
# MAGIC      │  natural language question
# MAGIC      ▼
# MAGIC  ┌──────────────────────────────────────┐
# MAGIC  │          Genie Space                 │
# MAGIC  │  instructions + knowledge store      │
# MAGIC  │  trusted assets (tables/dashboards)  │
# MAGIC  └───────────────┬──────────────────────┘
# MAGIC                  │  NL → SQL
# MAGIC                  ▼
# MAGIC          Unity Catalog tables
# MAGIC  (meter_readings, assets, outages,
# MAGIC   regulatory_reports)
# MAGIC ```
# MAGIC
# MAGIC ## AU East Note
# MAGIC
# MAGIC Genie Spaces (Chat mode and Agent mode) are **fully in-region for Australia East**.
# MAGIC No data leaves the region for the NL-to-SQL inference step.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC **Before you start:**
# MAGIC - Confirm you have `CREATE SCHEMA` privilege in the `workshop` catalog
# MAGIC - Confirm you have the `workspace_admin` or `genie_admin` entitlement
# MAGIC   (Genie Space create API requires account-level admin or delegated space admin)
# MAGIC - Replace every `# TODO:` value with your environment specifics

# COMMAND ----------

# Install / confirm SDK version — Genie API requires ≥ 0.28
%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import dashboards as genie_service
from databricks.sdk.service.iam import PermissionLevel
from pprint import pprint

# TODO: replace with your workspace URL if not running inside the workspace
# When running inside a Databricks notebook the SDK auto-configures from the
# cluster environment; no explicit host/token needed.
w = WorkspaceClient()

print(f"Connected to: {w.config.host}")
print(f"Current user: {w.current_user.me().user_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Create the Unity Catalog Schema and Sample Tables
# MAGIC
# MAGIC We use an **Australian energy NEM (National Electricity Market)** domain throughout
# MAGIC the workshop. All tables live in `workshop.energy_nem`.
# MAGIC
# MAGIC | Table | Description |
# MAGIC |-------|-------------|
# MAGIC | `meter_readings` | Half-hourly interval meter data (NMI + kWh) |
# MAGIC | `assets` | Substation and feeder asset register |
# MAGIC | `outages` | Planned and unplanned network events |
# MAGIC | `regulatory_reports` | AEMO / AER compliance document metadata |

# COMMAND ----------

# SOLUTION: catalog and schema pre-filled for workshop environment
CATALOG = "workshop"
SCHEMA  = "energy_nem"

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

print(f"Schema ready: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a — meter_readings
# MAGIC
# MAGIC Half-hourly Active Energy Import (AEI) readings following AEMO NEM12 conventions.

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.meter_readings (
    nmi               STRING        COMMENT 'National Metering Identifier — unique meter ID (e.g. QXXXXXXXXXX)',
    interval_datetime TIMESTAMP     COMMENT 'Start of the 30-minute measurement interval, AEST',
    active_energy_kwh DOUBLE        COMMENT 'Active energy imported in kWh for this interval',
    quality_flag      STRING        COMMENT 'NEM12 quality flag: A=Actual, E=Estimated, S=Substituted, N=None',
    meter_type        STRING        COMMENT 'Meter technology: SMART=AMI, BASIC=accumulation, CT=current-transformer',
    distribution_zone STRING        COMMENT 'DNSP distribution zone (e.g. ENERGEX_NORTH, AUSGRID_SOUTH)',
    created_at        TIMESTAMP     COMMENT 'Record ingestion timestamp'
)
USING DELTA
PARTITIONED BY (distribution_zone)
COMMENT 'Half-hourly interval meter readings sourced from AEMO NEM12 files. One row per NMI per interval.'
TBLPROPERTIES (
    'delta.autoOptimize.autoCompact'    = 'true',
    'delta.autoOptimize.optimizeWrite'  = 'true'
)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b — assets

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.assets (
    asset_id          STRING    COMMENT 'Internal asset identifier (UUID)',
    asset_name        STRING    COMMENT 'Human-readable name, e.g. "Essendon Zone Substation 66kV"',
    asset_type        STRING    COMMENT 'Type: ZONE_SUBSTATION, FEEDER, TRANSFORMER, CIRCUIT_BREAKER, CABLE',
    voltage_kv        DOUBLE    COMMENT 'Rated voltage in kilovolts',
    capacity_mva      DOUBLE    COMMENT 'Rated capacity in MVA; NULL for low-voltage assets',
    commissioning_date DATE     COMMENT 'Date the asset was energised and placed into service',
    last_maintenance  DATE      COMMENT 'Date of most recent maintenance inspection',
    region            STRING    COMMENT 'NEM region: QLD1, NSW1, VIC1, SA1, TAS1',
    latitude          DOUBLE    COMMENT 'WGS-84 latitude of asset location',
    longitude         DOUBLE    COMMENT 'WGS-84 longitude of asset location',
    status            STRING    COMMENT 'Operational status: IN_SERVICE, DECOMMISSIONED, UNDER_MAINTENANCE',
    owner_dnsp        STRING    COMMENT 'Owning Distribution Network Service Provider, e.g. JEMENA, AUSNET'
)
USING DELTA
COMMENT 'Network asset register for substations, feeders and major plant. Updated weekly from field maintenance systems.'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c — outages

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.outages (
    outage_id         STRING     COMMENT 'Unique outage event identifier',
    asset_id          STRING     COMMENT 'FK → assets.asset_id — which asset was affected',
    outage_type       STRING     COMMENT 'PLANNED or UNPLANNED',
    cause_category    STRING     COMMENT 'Root cause: WEATHER, EQUIPMENT_FAILURE, VEGETATION, THIRD_PARTY, UNKNOWN',
    start_time        TIMESTAMP  COMMENT 'Actual start of supply interruption (AEST)',
    end_time          TIMESTAMP  COMMENT 'Actual restoration of supply (AEST); NULL if still active',
    customers_affected INT       COMMENT 'Count of unique customer connection points interrupted',
    energy_not_served_mwh DOUBLE COMMENT 'MWh of demand that was not supplied (ENS metric for AER reporting)',
    suburb            STRING     COMMENT 'Suburb or locality name for reporting purposes',
    region            STRING     COMMENT 'NEM region',
    reported_to_aer   BOOLEAN    COMMENT 'Whether this event met the threshold for AER STPIS / SAIDI reporting',
    created_at        TIMESTAMP  COMMENT 'Record creation timestamp'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Network outage events including duration, customers affected, and energy-not-served. Used for SAIDI/SAIFI regulatory reporting to the AER.'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1d — regulatory_reports

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.regulatory_reports (
    report_id         STRING     COMMENT 'Unique report identifier',
    report_type       STRING     COMMENT 'Type: ANNUAL_PLANNING, RELIABILITY_REPORT, CPEC_SUBMISSION, RIT_T, STPIS',
    title             STRING     COMMENT 'Full document title',
    period_start      DATE       COMMENT 'Start of the regulatory reporting period',
    period_end        DATE       COMMENT 'End of the regulatory reporting period',
    submission_date   DATE       COMMENT 'Date submitted to AEMO or AER',
    submitting_entity STRING     COMMENT 'Entity that submitted: AEMO, AUSNET, JEMENA, TRANSGRID etc',
    document_url      STRING     COMMENT 'URL to the published PDF on the regulator website',
    document_text     STRING     COMMENT 'Full extracted plain text of the document (for AI processing)',
    status            STRING     COMMENT 'STATUS: DRAFT, SUBMITTED, PUBLISHED, SUPERSEDED',
    created_at        TIMESTAMP  COMMENT 'Record ingestion timestamp'
)
USING DELTA
COMMENT 'Regulatory document register for AEMO / AER compliance submissions. document_text holds extracted PDF content for AI summarisation and classification.'
""")

print("All 4 tables created with column-level comments.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1e — Seed with realistic sample data

# COMMAND ----------

from pyspark.sql import Row
from datetime import datetime, date, timedelta
import random, uuid

random.seed(42)

# --- meter_readings (360 rows: 3 NMIs × 5 days × 24 intervals) ---
regions = ["ENERGEX_NORTH", "AUSNET_EAST", "AUSGRID_SOUTH"]
rows = []
for nmi_idx in range(3):
    nmi = f"Q{1000000 + nmi_idx:08d}"
    zone = regions[nmi_idx]
    for day_offset in range(5):
        base = datetime(2024, 6, 1) + timedelta(days=day_offset)
        for interval in range(24):
            rows.append(Row(
                nmi=nmi,
                interval_datetime=base + timedelta(hours=interval),
                active_energy_kwh=round(random.uniform(0.5, 4.2), 4),
                quality_flag=random.choice(["A", "A", "A", "E"]),
                meter_type="SMART",
                distribution_zone=zone,
                created_at=datetime.now()
            ))

spark.createDataFrame(rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.meter_readings")

# --- assets (20 rows) ---
asset_types = ["ZONE_SUBSTATION", "FEEDER", "TRANSFORMER", "CIRCUIT_BREAKER"]
dnsps = ["AUSNET", "JEMENA", "CITIPOWER", "POWERCOR"]
asset_rows = []
for i in range(20):
    asset_rows.append(Row(
        asset_id=str(uuid.uuid4()),
        asset_name=f"{'Substation' if i % 3 == 0 else 'Feeder'} {i+1:03d}",
        asset_type=asset_types[i % 4],
        voltage_kv=float(random.choice([66, 110, 220, 500])),
        capacity_mva=float(random.choice([30, 60, 120, 250, None])) if i % 5 != 0 else None,
        commissioning_date=date(random.randint(1985, 2020), random.randint(1, 12), 1),
        last_maintenance=date(2024, random.randint(1, 6), random.randint(1, 28)),
        region=random.choice(["VIC1", "NSW1", "QLD1"]),
        latitude=-37.8 + random.uniform(-1, 1),
        longitude=145.0 + random.uniform(-2, 2),
        status=random.choice(["IN_SERVICE", "IN_SERVICE", "IN_SERVICE", "UNDER_MAINTENANCE"]),
        owner_dnsp=dnsps[i % 4]
    ))

spark.createDataFrame(asset_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.assets")

# --- outages (30 rows) ---
causes = ["WEATHER", "EQUIPMENT_FAILURE", "VEGETATION", "THIRD_PARTY", "UNKNOWN"]
outage_rows = []
for i in range(30):
    start = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))
    duration_h = random.uniform(0.5, 8)
    outage_rows.append(Row(
        outage_id=str(uuid.uuid4()),
        asset_id=asset_rows[i % 20].asset_id,
        outage_type=random.choice(["PLANNED", "UNPLANNED", "UNPLANNED"]),
        cause_category=random.choice(causes),
        start_time=start,
        end_time=start + timedelta(hours=duration_h),
        customers_affected=random.randint(10, 5000),
        energy_not_served_mwh=round(random.uniform(0.1, 50.0), 3),
        suburb=random.choice(["Essendon", "Footscray", "Sunshine", "Broadmeadows", "Ringwood"]),
        region=random.choice(["VIC1", "NSW1", "QLD1"]),
        reported_to_aer=random.choice([True, False]),
        created_at=datetime.now()
    ))

spark.createDataFrame(outage_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.outages")

# --- regulatory_reports (10 rows) ---
report_types = ["ANNUAL_PLANNING", "RELIABILITY_REPORT", "CPEC_SUBMISSION", "RIT_T", "STPIS"]
report_rows = []
for i in range(10):
    report_rows.append(Row(
        report_id=str(uuid.uuid4()),
        report_type=report_types[i % 5],
        title=f"NEM {report_types[i % 5].replace('_', ' ').title()} FY2{23 + (i // 5)}",
        period_start=date(2023, 7, 1),
        period_end=date(2024, 6, 30),
        submission_date=date(2024, random.randint(7, 10), random.randint(1, 28)),
        submitting_entity=random.choice(["AUSNET", "AEMO", "TRANSGRID", "JEMENA"]),
        document_url=f"https://www.aer.gov.au/documents/report-{i+1:04d}",
        document_text=f"This is the full regulatory report text for submission {i+1}. "
                      f"Network reliability targets were {'met' if i % 2 == 0 else 'partially met'}. "
                      f"SAIDI for the period was {random.uniform(60, 120):.1f} minutes. "
                      f"Capital expenditure totalled ${random.randint(20, 200)}M.",
        status=random.choice(["PUBLISHED", "PUBLISHED", "SUBMITTED", "DRAFT"]),
        created_at=datetime.now()
    ))

spark.createDataFrame(report_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_reports")

print("Sample data loaded. Row counts:")
for tbl in ["meter_readings", "assets", "outages", "regulatory_reports"]:
    count = spark.table(f"{CATALOG}.{SCHEMA}.{tbl}").count()
    print(f"  {CATALOG}.{SCHEMA}.{tbl}: {count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Create the Genie Space via API
# MAGIC
# MAGIC The Databricks SDK wraps the `/api/2.0/genie/spaces` REST endpoint.
# MAGIC We supply:
# MAGIC - **title** — displayed in the UI
# MAGIC - **description** — used by Genie for context
# MAGIC - **instructions** — the "system prompt" that shapes every NL-to-SQL interaction

# COMMAND ----------

# The instructions block is the most important configuration lever.
# Think of it as a system prompt for the Genie space.
# Good instructions:
#   1. Declare the domain (who uses this, what data is in scope)
#   2. Explain key business terms and abbreviations
#   3. Specify default filters (e.g. "unless told otherwise, show VIC1 data")
#   4. Define preferred units and date formats
#   5. List common aggregation rules (e.g. "ENS = SUM(energy_not_served_mwh)")
#   6. Note data freshness / known limitations

GENIE_INSTRUCTIONS = """
You are an energy data analyst assistant for an Australian Distribution Network Service Provider (DNSP).
Your primary users are grid operations managers, regulatory analysts, and asset managers.

## Domain Context
- Data covers the National Electricity Market (NEM): QLD1, NSW1, VIC1, SA1, TAS1
- All timestamps are in Australian Eastern Standard Time (AEST / UTC+10) unless otherwise stated
- "NMI" stands for National Metering Identifier — the unique ID for each electricity connection point
- "SAIDI" = System Average Interruption Duration Index (minutes per customer per year) — the key AER reliability metric
- "SAIFI" = System Average Interruption Frequency Index (interruptions per customer per year)
- "ENS" = Energy Not Served (MWh) — reported in AER STPIS submissions
- "DNSP" = Distribution Network Service Provider (e.g. AusNet, Jemena, Citipower)

## Default Behaviour
- Unless the user specifies a region, show data for ALL regions (no default filter)
- When calculating SAIDI, use: SUM((end_time - start_time in minutes) * customers_affected) / total_customers
- "This year" means the current financial year (July 1 – June 30)
- When showing outage durations, express in hours rounded to 1 decimal place
- Sort results by most recent first unless the user asks for ranking by a metric

## Key Relationships
- outages.asset_id → assets.asset_id (many outages per asset)
- meter_readings is fact table; join to assets via distribution_zone ↔ region mapping
- regulatory_reports is standalone (document repository, no FK relationships)

## Important Limitations
- meter_readings contains 30-minute intervals; do not calculate per-hour totals by multiplying by 2
- energy_not_served_mwh may be NULL for very short outages (< 1 minute); treat NULL as 0 in aggregations
- document_text in regulatory_reports is plain text extracted from PDFs; it may contain OCR artefacts
"""

# COMMAND ----------

# Create the Genie Space via REST API
# NOTE: The Databricks SDK's w.genie object exposes w.genie.create_space() but that method
#       requires a serialized_space payload (a full space definition blob) which is only
#       practical when cloning an existing space.  For creating a brand-new empty space from
#       scratch the direct REST POST to /api/2.0/genie/spaces is the correct path.

import requests, json

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host  = spark.conf.get("spark.databricks.workspaceUrl")

payload = {
    "title": "NEM Grid Operations — Energy Analytics",
    "description": (
        "Self-service analytics for NEM grid operations, outage management, "
        "asset health and regulatory reporting. Covers meter readings, network "
        "assets, outages, and AER/AEMO compliance documents."
    )
}
resp = requests.post(
    f"https://{host}/api/2.0/genie/spaces",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json=payload
)
resp.raise_for_status()
SPACE_ID = resp.json()["space_id"]
print(f"Genie Space created. space_id = {SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Add Tables as Trusted Assets
# MAGIC
# MAGIC Genie will only query tables that have been explicitly added as trusted assets.
# MAGIC This is a security control — it prevents accidental exposure of other UC tables.

# COMMAND ----------

# TODO: replace with your actual space_id if you captured it differently
# SPACE_ID = "your-space-id-here"

import requests, json

def get_headers():
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

HOST = spark.conf.get("spark.databricks.workspaceUrl")

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
    if resp.status_code in (200, 201):
        print(f"  Added: {table_fqn}")
    else:
        print(f"  WARN: {table_fqn} — {resp.status_code}: {resp.text[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Seed the Knowledge Store with Verified SQL (Golden Queries)
# MAGIC
# MAGIC Golden queries are the single most impactful improvement you can make to a Genie Space.
# MAGIC They teach Genie the *correct* SQL for your most important business questions.
# MAGIC
# MAGIC ### Rules for good golden queries
# MAGIC 1. Cover the top 10–20 questions users will ask most often
# MAGIC 2. Use the exact column names from your tables (helps Genie learn aliases)
# MAGIC 3. Include comments explaining non-obvious logic
# MAGIC 4. Each query must run without errors on the current schema
# MAGIC 5. Keep individual queries focused — one business question per query

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Total outage duration by region this financial year",
        "description": (
            "Shows SAIDI-contributing outage hours by NEM region for the current financial year "
            "(July 1 to June 30). Excludes planned outages from the reliability calculation."
        ),
        "sql": f"""
SELECT
    region,
    COUNT(*)                                                        AS outage_count,
    SUM(customers_affected)                                         AS total_customer_interruptions,
    ROUND(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) AS total_outage_hours,
    SUM(COALESCE(energy_not_served_mwh, 0))                         AS total_ens_mwh
FROM {CATALOG}.{SCHEMA}.outages
WHERE outage_type = 'UNPLANNED'
  AND start_time >= DATE_TRUNC('year', ADD_MONTHS(CURRENT_DATE, -((MONTH(CURRENT_DATE) - 7 + 12) % 12)))
GROUP BY region
ORDER BY total_customer_interruptions DESC
"""
    },
    {
        "name": "Top 10 worst assets by cumulative outage frequency",
        "description": (
            "Asset reliability league table — identifies chronic problem assets that need "
            "maintenance or replacement investment. Joins outages to the asset register."
        ),
        "sql": f"""
SELECT
    a.asset_name,
    a.asset_type,
    a.owner_dnsp,
    a.region,
    COUNT(o.outage_id)                                      AS outage_count,
    SUM(o.customers_affected)                               AS total_customers_affected,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time)) / 60, 2) AS avg_outage_hours,
    a.last_maintenance
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id
   AND o.outage_type = 'UNPLANNED'
GROUP BY a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp, a.region, a.last_maintenance
ORDER BY outage_count DESC
LIMIT 10
"""
    },
    {
        "name": "Monthly meter reading totals by distribution zone",
        "description": (
            "Aggregates smart meter interval data to monthly active energy consumption per zone. "
            "Useful for demand trend analysis and zone capacity planning."
        ),
        "sql": f"""
SELECT
    distribution_zone,
    DATE_TRUNC('month', interval_datetime)  AS month,
    COUNT(DISTINCT nmi)                     AS unique_meters,
    ROUND(SUM(active_energy_kwh), 1)        AS total_energy_kwh,
    ROUND(AVG(active_energy_kwh), 4)        AS avg_interval_kwh
FROM {CATALOG}.{SCHEMA}.meter_readings
WHERE quality_flag IN ('A', 'E')   -- exclude substituted and missing reads
GROUP BY distribution_zone, DATE_TRUNC('month', interval_datetime)
ORDER BY month DESC, distribution_zone
"""
    },
    {
        "name": "Outstanding regulatory submissions due in next 90 days",
        "description": (
            "Compliance calendar showing regulatory reports that are in DRAFT or SUBMITTED status "
            "with a period_end date within the next 90 days."
        ),
        "sql": f"""
SELECT
    report_type,
    title,
    submitting_entity,
    period_end              AS reporting_period_end,
    submission_date         AS scheduled_submission_date,
    status,
    DATEDIFF(submission_date, CURRENT_DATE) AS days_until_due
FROM {CATALOG}.{SCHEMA}.regulatory_reports
WHERE status IN ('DRAFT', 'SUBMITTED')
  AND submission_date BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, 90)
ORDER BY submission_date
"""
    },
    {
        "name": "Outages reported to AER by cause category",
        "description": (
            "Breakdown of AER-reportable events by root cause. Used to prepare STPIS narrative "
            "sections explaining unusual reliability outcomes."
        ),
        "sql": f"""
SELECT
    cause_category,
    COUNT(*)                                          AS reportable_events,
    SUM(customers_affected)                           AS customers_affected,
    ROUND(SUM(COALESCE(energy_not_served_mwh, 0)), 2) AS total_ens_mwh,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) AS avg_duration_hours
FROM {CATALOG}.{SCHEMA}.outages
WHERE reported_to_aer = TRUE
GROUP BY cause_category
ORDER BY reportable_events DESC
"""
    },
]

# Push golden queries to the Genie knowledge store
for q in GOLDEN_QUERIES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=get_headers(),
        json={
            "name":        q["name"],
            "description": q["description"],
            "query":       q["sql"].strip()
        }
    )
    status = "OK" if resp.status_code in (200, 201) else f"ERROR {resp.status_code}"
    print(f"  [{status}] {q['name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Update Space Instructions
# MAGIC
# MAGIC Now that we have a space ID, patch it with the full instructions block.

# COMMAND ----------

resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=get_headers(),
    json={"instructions": GENIE_INSTRUCTIONS.strip()}
)
if resp.status_code == 200:
    print("Instructions updated successfully.")
else:
    print(f"WARN: {resp.status_code} — {resp.text[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Set Permissions
# MAGIC
# MAGIC Grant the appropriate groups access to the Genie Space.
# MAGIC
# MAGIC | Permission Level | Who should have it |
# MAGIC |--|--|
# MAGIC | `CAN_USE` | Business analysts, data consumers |
# MAGIC | `CAN_MANAGE` | Data engineers who maintain the space |
# MAGIC | `IS_OWNER` | Assigned automatically to the creator |
# MAGIC
# MAGIC > **Tip:** Assign to Unity Catalog groups, not individual users.
# MAGIC > That way, access is managed in one place (UC group membership).

# COMMAND ----------

# TODO: replace group names with groups that exist in your workspace
PERMISSION_GRANTS = [
    # SOLUTION: uncomment and replace with real group names in your workspace
    # {"group_name": "grid-operations-analysts", "permission_level": "CAN_USE"},
    # {"group_name": "regulatory-reporting-team", "permission_level": "CAN_USE"},
    # {"group_name": "data-platform-engineers",   "permission_level": "CAN_MANAGE"},
    # For the workshop, add yourself for testing:
    # {"user_name": "your.email@company.com.au", "permission_level": "CAN_USE"},
]

for grant in PERMISSION_GRANTS:
    resp = requests.patch(
        f"https://{HOST}/api/2.0/permissions/genie/spaces/{SPACE_ID}",
        headers=get_headers(),
        json={"access_control_list": [
            {
                "group_name":       grant["group_name"],
                "permission_level": grant["permission_level"]
            }
        ]}
    )
    status = "OK" if resp.status_code == 200 else f"ERROR {resp.status_code}"
    print(f"  [{status}] {grant['group_name']} → {grant['permission_level']}")

if not PERMISSION_GRANTS:
    print("No grants configured — uncomment entries in PERMISSION_GRANTS to apply.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Smoke Test via Conversation API
# MAGIC
# MAGIC Programmatically start a conversation and ask a test question.
# MAGIC This confirms that the space is wired up and returning results.

# COMMAND ----------

def genie_ask(space_id: str, question: str) -> dict:
    """
    Starts a Genie conversation and polls until a result is ready.
    Returns the full response dict.
    """
    import time

    # Start conversation
    start_resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{space_id}/start-conversation",
        headers=get_headers(),
        json={"content": question}
    )
    start_resp.raise_for_status()
    data = start_resp.json()
    conversation_id = data["conversation_id"]
    message_id      = data["message_id"]
    print(f"Conversation started: {conversation_id}")

    # Poll for completion (up to 60 seconds)
    for attempt in range(30):
        poll_resp = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}",
            headers=get_headers()
        )
        poll_resp.raise_for_status()
        msg = poll_resp.json()
        state = msg.get("status", "UNKNOWN")

        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            return msg

        print(f"  [{attempt+1}/30] Status: {state} — waiting 2s...")
        time.sleep(2)

    return {"status": "TIMEOUT", "error": "Polling timed out after 60 seconds"}


# Run a smoke test
TEST_QUESTION = "How many unplanned outages occurred in VIC1 and what was the total energy not served?"

print(f"\nQuestion: {TEST_QUESTION}\n")
result = genie_ask(SPACE_ID, TEST_QUESTION)

print(f"\nStatus: {result.get('status')}")
if result.get("attachments"):
    for att in result["attachments"]:
        if att.get("query"):
            print(f"\nGenerated SQL:\n{att['query'].get('query', '')}")
        if att.get("text"):
            print(f"\nNarrative: {att['text'].get('content', '')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 8 — Record the Space ID
# MAGIC
# MAGIC Save the space ID — you will need it in Lab 02 and Lab 03.

# COMMAND ----------

print("=" * 60)
print("LAB 01 COMPLETE")
print("=" * 60)
print(f"Catalog / Schema : {CATALOG}.{SCHEMA}")
print(f"Genie Space ID   : {SPACE_ID}")
print(f"Workspace URL    : https://{HOST}")
print(f"Genie URL        : https://{HOST}/genie/spaces/{SPACE_ID}")
print()
print("Save the Space ID — you will need it in Lab 02 and Lab 03.")
print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab 01 — Review Questions
# MAGIC
# MAGIC 1. What is the difference between "trusted assets" and "knowledge store" in a Genie Space?
# MAGIC 2. The `instructions` field acts like a system prompt. What are three things you should
# MAGIC    always include in a Genie Space instructions block for a regulated industry customer?
# MAGIC 3. Why do we add column-level `COMMENT` to tables before creating the Genie Space?
# MAGIC 4. A business analyst asks Genie "what was our SAIDI last year?" and gets a wrong answer.
# MAGIC    What is your first troubleshooting step?
# MAGIC 5. Which permission level should a read-only analyst have: `CAN_USE` or `CAN_MANAGE`?
# MAGIC
# MAGIC **Proceed to Lab 02 when ready.**
