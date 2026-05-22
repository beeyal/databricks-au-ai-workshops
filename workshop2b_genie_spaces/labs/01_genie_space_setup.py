# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 01: Genie Space Setup
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">
# MAGIC     Admin Perspective — Australian Energy NEM Domain
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="width:100%; border-collapse:collapse; margin-top:16px; font-family:'DM Sans',sans-serif;">
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px; width:25%"><b>Workshop</b></td><td style="padding:8px 16px;">Genie Spaces &amp; AI Features — Australian Regulated Industries</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Duration</b></td><td style="padding:8px 16px;">35–40 minutes</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Role</b></td><td style="padding:8px 16px;">Platform Admin / Data Engineer</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Prerequisites</b></td><td style="padding:8px 16px;"><code>CREATE SCHEMA</code> privilege in your UC catalog &nbsp;|&nbsp; <code>workspace_admin</code> or <code>genie_admin</code> entitlement</td></tr>
# MAGIC </table>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F4FD; border-left:5px solid #1B3A6B; padding:20px 24px; border-radius:0 8px 8px 0; margin:16px 0;">
# MAGIC   <h2 style="color:#1B3A6B; margin-top:0;">Learning Objectives</h2>
# MAGIC   <ol style="line-height:2em;">
# MAGIC     <li>Create a Genie Space manually via the Databricks UI — step-by-step with UI diagrams</li>
# MAGIC     <li>Create a Genie Space programmatically using the REST API</li>
# MAGIC     <li>Build energy-sector sample tables in Unity Catalog with rich column comments</li>
# MAGIC     <li>Add trusted assets (Delta tables) to the space</li>
# MAGIC     <li>Write effective Genie Space <em>instructions</em> — the system prompt that shapes every conversation</li>
# MAGIC     <li>Seed the knowledge store with verified SQL examples (golden queries)</li>
# MAGIC     <li>Set per-role permissions so only authorised users can access the space</li>
# MAGIC     <li>Run a smoke-test via the Conversation API</li>
# MAGIC   </ol>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#F0F4FF; border-left:5px solid #4C6EF5; padding:20px 24px; border-radius:0 8px 8px 0; margin:16px 0;">
# MAGIC   <h2 style="color:#4C6EF5; margin-top:0;">Architecture Overview</h2>
# MAGIC   <pre style="background:white; padding:16px; border-radius:6px; font-size:0.95em; line-height:1.7;">
# MAGIC Business Analyst
# MAGIC      |  natural language question
# MAGIC      v
# MAGIC  +------------------------------------------+
# MAGIC  |             Genie Space                  |
# MAGIC  |   instructions + knowledge store         |
# MAGIC  |   trusted assets (tables / views)        |
# MAGIC  +--------------------+---------------------+
# MAGIC                       |  NL -> SQL
# MAGIC                       v
# MAGIC             Unity Catalog tables
# MAGIC    meter_readings | assets | outages | regulatory_reports
# MAGIC   </pre>
# MAGIC   <p style="margin-bottom:0;"><strong>AU East Note:</strong> Genie Spaces (Chat mode and Agent mode) are
# MAGIC   <span style="color:#2E7D32; font-weight:bold;">fully in-region for Australia East</span>.
# MAGIC   No data leaves the region for the NL-to-SQL inference step.</p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#FFF3E0; border-left:5px solid #FF6D00; padding:16px 20px; border-radius:0 8px 8px 0; margin:16px 0;">
# MAGIC   <h3 style="color:#E65100; margin-top:0;">Before You Start — Checklist</h3>
# MAGIC   <ul>
# MAGIC     <li>Confirm you have <code>CREATE SCHEMA</code> privilege in the <code>workshop</code> catalog (or change <code>CATALOG</code> below)</li>
# MAGIC     <li>Confirm you have <code>workspace_admin</code> or <code>genie_admin</code> entitlement</li>
# MAGIC     <li>Replace every <code># TODO:</code> value with your environment specifics</li>
# MAGIC   </ul>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before We Code: 5-Minute UI Tour (do this first!)
# MAGIC
# MAGIC In this lab you create a Genie Space via the SDK.
# MAGIC First, explore the Genie UI to understand what you are building —
# MAGIC so that when the space appears after the API call, you know where to find it.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 1 — Navigate to the Genie section
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Genie (sparkle/wand icon, usually near the bottom)
# MAGIC ```
# MAGIC
# MAGIC **What you should see:**
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────┐
# MAGIC │  Genie                                               │
# MAGIC │  ──────────────────────────────────────────────────  │
# MAGIC │                                                      │
# MAGIC │  [+ Create space]                                    │
# MAGIC │                                                      │
# MAGIC │  No spaces yet  (or a list of existing spaces)       │
# MAGIC └──────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC If spaces exist: click one to see the Chat interface.
# MAGIC If none exist: that is fine — you will create one in Step 2.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 2 — Explore the "Create Space" form (do not submit)
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Genie section → click "+ Create space" or "New Space"
# MAGIC ```
# MAGIC
# MAGIC **What to look for in the form:**
# MAGIC - Title and description fields
# MAGIC - "Data" tab: where you add trusted Delta tables
# MAGIC - "Instructions" tab: this is the system prompt (you'll write one in Step 5)
# MAGIC - "SQL examples" tab: where you add golden queries (Step 6)
# MAGIC - Permissions section: who can use vs manage the space
# MAGIC
# MAGIC **Click Cancel** — Step 2 creates the space via code.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 3 — Look at an existing Genie Space (if one exists)
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Genie → click any existing space → Configure tab (top of the space)
# MAGIC ```
# MAGIC
# MAGIC **Two tabs to explore:**
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────┐
# MAGIC │  [Chat]  [Configure]                                 │
# MAGIC │                                                      │
# MAGIC │  Configure shows:                                    │
# MAGIC │    • Space instructions (the system prompt)          │
# MAGIC │    • Trusted data assets (tables connected)          │
# MAGIC │    • SQL examples (golden queries)                   │
# MAGIC │    • Permissions (who can use / manage)              │
# MAGIC └──────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Time check:** 5 minutes. Start the pip install while you explore.

# COMMAND ----------

# Install / confirm SDK version — Genie API requires >= 0.28
%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import PermissionLevel
from pprint import pprint

# When running inside a Databricks notebook the SDK auto-configures from the
# cluster environment — no explicit host/token needed.
w = WorkspaceClient()

print(f"Connected to : {w.config.host}")
print(f"Current user : {w.current_user.me().user_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 1 — Create Unity Catalog Schema and Sample Tables</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#F3F9FF; border:1px solid #90CAF9; padding:16px 20px; border-radius:8px; margin:12px 0;">
# MAGIC We use an <strong>Australian energy NEM (National Electricity Market)</strong> domain throughout the workshop.
# MAGIC All tables live in <code>workshop.energy_nem</code>.
# MAGIC
# MAGIC | Table | Grain | Description |
# MAGIC |---|---|---|
# MAGIC | <code>meter_readings</code> | One row per NMI per 30-min interval | Half-hourly interval meter data (NEM12) |
# MAGIC | <code>assets</code> | One row per asset | Substation and feeder asset register |
# MAGIC | <code>outages</code> | One row per outage event | Planned and unplanned network events |
# MAGIC | <code>regulatory_reports</code> | One row per document | AEMO / AER compliance document metadata |
# MAGIC
# MAGIC <br>
# MAGIC <strong>Why column COMMENTs matter for Genie:</strong><br>
# MAGIC Genie reads Unity Catalog metadata before generating any SQL. Rich column comments teach it
# MAGIC correct units, allowed values, business meaning, and join keys — dramatically reducing
# MAGIC hallucinated column names and wrong aggregations. The comments we write are as important
# MAGIC as the table structure itself.
# MAGIC </div>

# COMMAND ----------

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Workshop Configuration
# MAGIC > **Running in a customer environment?** Change the catalog name in the widget above to match
# MAGIC > what was set in `setup/00_workspace_setup.py` (default: `workshop_au`)

# COMMAND ----------
# Widget-based configuration — works in any customer Databricks environment
# These default values match what 00_workspace_setup.py creates
dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",      "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
PT_ENDPOINT  = dbutils.widgets.get("pt_endpoint")

print(f"Using catalog: {CATALOG}.{SCHEMA}")
print(f"PT endpoint:   {PT_ENDPOINT}")

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA}")

print(f"Schema ready: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a — meter_readings

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
TBLPROPERTIES (
    'delta.autoOptimize.autoCompact'   = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true'
)
""")
print("meter_readings created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b — assets

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

# MAGIC %md
# MAGIC ### 1c — outages

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

# MAGIC %md
# MAGIC ### 1d — regulatory_reports

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
print()
print("All 4 tables created with column-level comments.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1e — Seed with realistic sample data

# COMMAND ----------

from pyspark.sql import Row
from datetime import datetime, date, timedelta
import random, uuid

random.seed(42)

# --- meter_readings (360 rows: 3 NMIs x 5 days x 24 intervals) ---
zones = ["ENERGEX_NORTH", "AUSNET_EAST", "AUSGRID_SOUTH"]
rows  = []
for nmi_idx in range(3):
    nmi  = f"Q{1000000 + nmi_idx:08d}"
    zone = zones[nmi_idx]
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
dnsps       = ["AUSNET", "JEMENA", "CITIPOWER", "POWERCOR"]
asset_rows  = []
for i in range(20):
    asset_rows.append(Row(
        asset_id=str(uuid.uuid4()),
        asset_name=f"{'Substation' if i % 3 == 0 else 'Feeder'} {i+1:03d}",
        asset_type=asset_types[i % 4],
        voltage_kv=float(random.choice([66, 110, 220, 500])),
        capacity_mva=float(random.choice([30, 60, 120, 250])) if i % 5 != 0 else None,
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
causes      = ["WEATHER", "EQUIPMENT_FAILURE", "VEGETATION", "THIRD_PARTY", "UNKNOWN"]
outage_rows = []
for i in range(30):
    start      = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))
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
report_rows  = []
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
        document_text=(
            f"This is the full regulatory report text for submission {i+1}. "
            f"Network reliability targets were {'met' if i % 2 == 0 else 'partially met'}. "
            f"SAIDI for the period was {random.uniform(60, 120):.1f} minutes. "
            f"Capital expenditure totalled ${random.randint(20, 200)}M."
        ),
        status=random.choice(["PUBLISHED", "PUBLISHED", "SUBMITTED", "DRAFT"]),
        created_at=datetime.now()
    ))

spark.createDataFrame(report_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_reports")

print("Sample data loaded.")
print()
print("Row counts:")
for tbl in ["meter_readings", "assets", "outages", "regulatory_reports"]:
    count = spark.table(f"{CATALOG}.{SCHEMA}.{tbl}").count()
    print(f"  {CATALOG}.{SCHEMA}.{tbl:30s}  {count:>6,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 2 — Create a Genie Space</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#F3E5F5; border-left:5px solid #7B1FA2; padding:16px 20px; border-radius:0 8px 8px 0; margin:12px 0;">
# MAGIC   There are <strong>two ways</strong> to create a Genie Space.<br>
# MAGIC   We recommend doing <strong>Option A (UI) first</strong> to understand the interface,
# MAGIC   then use <strong>Option B (API)</strong> for repeatable deployments and CI/CD.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Option A — Create via UI (do this first to understand the interface)
# MAGIC
# MAGIC **Navigation:** Left sidebar → Genie (diamond icon) → + New Space
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### What you see when you first open Genie
# MAGIC
# MAGIC ```
# MAGIC +-- Genie ---------------------------------------------------------------+
# MAGIC |                                                                         |
# MAGIC |   [+ New Space]                                          Search [    ]  |
# MAGIC |   -------------------------------------------------------------------   |
# MAGIC |   My spaces:                                                            |
# MAGIC |   (none yet)                                                            |
# MAGIC |                                                                         |
# MAGIC |              Click [+ New Space] to create your first space             |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### Step 1 — Fill in the creation form
# MAGIC
# MAGIC ```
# MAGIC +-- New Genie Space ------------------------------------------------------+
# MAGIC |                                                                         |
# MAGIC |   Title*:        [ NEM Grid Operations -- Energy Analytics        ]    |
# MAGIC |                                                                         |
# MAGIC |   Description:   [ Self-service analytics for grid ops, outage        ]|
# MAGIC |                   [ management and AER regulatory reporting.          ] |
# MAGIC |                                                                         |
# MAGIC |   Warehouse*:    [ workshop-sql-warehouse                    v ]       |
# MAGIC |                    ^ choose a running SQL warehouse                     |
# MAGIC |                                                                         |
# MAGIC |   Tables:                                     [+ Add tables]           |
# MAGIC |   (none added yet)                                                      |
# MAGIC |                                                                         |
# MAGIC |                                  [Cancel]   [Create space ->]          |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### Step 2 — Add tables to the space
# MAGIC
# MAGIC Click **"+ Add tables"** — a Data Explorer popup appears:
# MAGIC
# MAGIC ```
# MAGIC +-- Add Tables -----------------------------------------------------------+
# MAGIC |   Catalogs          Schemas         Tables                             |
# MAGIC |   +-----------+     +----------+    +------------------------+         |
# MAGIC |   | workshop  |  -> | energy.. |  ->| [x] meter_readings     |         |
# MAGIC |   |           |     |          |    | [x] assets             |         |
# MAGIC |   |           |     |          |    | [x] outages            |         |
# MAGIC |   |           |     |          |    | [x] regulatory_reports |         |
# MAGIC |   +-----------+     +----------+    +------------------------+         |
# MAGIC |                                                                         |
# MAGIC |                                  [Add selected tables (4) ->]          |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### Step 3 — After creation you land on the Configure view
# MAGIC
# MAGIC ```
# MAGIC +-- NEM Grid Operations -- Energy Analytics ------------------------------+
# MAGIC |   [Chat]   [Configure]   <-- you start here after creation             |
# MAGIC |                                                                         |
# MAGIC |   Configure                                                             |
# MAGIC |   +-- Instructions  <-- write your domain system prompt here           |
# MAGIC |   +-- Tables (4)    <-- manage which tables Genie can query            |
# MAGIC |   +-- SQL queries   <-- add verified example queries (golden)          |
# MAGIC |   +-- Permissions   <-- who can access this space                      |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### Writing instructions in the UI
# MAGIC
# MAGIC Navigate to: **Configure --> Instructions tab**
# MAGIC
# MAGIC This is where you give Genie its "personality" for the space.
# MAGIC Think of it as the system prompt — every conversation starts with these instructions in context.
# MAGIC
# MAGIC ```
# MAGIC +-- Instructions ---------------------------------------------------------+
# MAGIC |                                                                         |
# MAGIC |   You are an energy data analyst assistant for an Australian            |
# MAGIC |   Distribution Network Service Provider (DNSP).                        |
# MAGIC |   Your users are grid operations managers, regulatory analysts,        |
# MAGIC |   and asset managers.                                                   |
# MAGIC |                                                                         |
# MAGIC |   ## Domain Context                                                     |
# MAGIC |   - SAIDI = System Average Interruption Duration Index                  |
# MAGIC |   - SAIFI = System Average Interruption Frequency Index                 |
# MAGIC |   - ENS   = Energy Not Served (MWh)                                     |
# MAGIC |   - "This year" = Australian financial year (Jul 1 -- Jun 30)          |
# MAGIC |                                                                         |
# MAGIC |   ## Default Behaviour                                                  |
# MAGIC |   - Show data for ALL regions unless the user specifies one             |
# MAGIC |   - Express durations in hours rounded to 1 decimal place               |
# MAGIC |   - Use COALESCE(energy_not_served_mwh, 0) in SUM aggregations         |
# MAGIC |                                                                         |
# MAGIC |                                      [Save instructions]               |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC #### Adding golden queries in the UI
# MAGIC
# MAGIC Navigate to: **Configure --> SQL queries tab --> [+ Add query]**
# MAGIC
# MAGIC Golden queries are teaching examples — they show Genie the correct SQL for your
# MAGIC most common business questions. Add at least 3-5 before sharing the space with users.
# MAGIC
# MAGIC ```
# MAGIC +-- Add verified query ---------------------------------------------------+
# MAGIC |                                                                         |
# MAGIC |   Question: "What is the SAIDI performance by region?"                 |
# MAGIC |                                                                         |
# MAGIC |   SQL:   SELECT region,                                                |
# MAGIC |                  SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)        |
# MAGIC |                      * customers_affected)   AS saidi_numerator,       |
# MAGIC |                  COUNT(*)                    AS event_count             |
# MAGIC |           FROM workshop.energy_nem.outages                              |
# MAGIC |           WHERE outage_type = 'UNPLANNED'                               |
# MAGIC |             AND reported_to_aer = TRUE                                  |
# MAGIC |             AND YEAR(start_time) = YEAR(CURRENT_DATE)                   |
# MAGIC |           GROUP BY region                                               |
# MAGIC |           ORDER BY saidi_numerator DESC;                                |
# MAGIC |                                                                         |
# MAGIC |                                             [Save query]               |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC Once you have explored the UI, proceed to **Option B** below to create the same space via API.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Option B — Create via API (repeatable, scriptable, CI/CD-friendly)
# MAGIC
# MAGIC Use this path for deploying across dev -> test -> prod environments,
# MAGIC version-controlling instructions in Git, and automating setup in Databricks Asset Bundles.

# COMMAND ----------

# MAGIC %md
# MAGIC #### 2a — Define the Instructions block
# MAGIC
# MAGIC The instructions block is the most important configuration lever.
# MAGIC Think of it as the system prompt for the Genie space.
# MAGIC
# MAGIC A good instructions block:
# MAGIC 1. Declares the domain (who uses this, what data is in scope)
# MAGIC 2. Explains key business terms and abbreviations
# MAGIC 3. Specifies default filters ("unless told otherwise, show all regions")
# MAGIC 4. Defines preferred units and date formats
# MAGIC 5. Lists common aggregation formulas (ENS, SAIDI, SAIFI)
# MAGIC 6. Notes data freshness and known limitations

# COMMAND ----------

GENIE_INSTRUCTIONS = """
You are an energy data analyst assistant for an Australian Distribution Network Service Provider (DNSP).
Your primary users are grid operations managers, regulatory analysts, and asset managers.

## Domain Context
- Data covers the National Electricity Market (NEM): QLD1, NSW1, VIC1, SA1, TAS1
- All timestamps are in Australian Eastern Standard Time (AEST / UTC+10) unless otherwise stated
- "NMI" = National Metering Identifier — the unique ID for each electricity connection point
- "SAIDI" = System Average Interruption Duration Index (minutes per customer per year) — key AER reliability metric
- "SAIFI" = System Average Interruption Frequency Index (interruptions per customer per year)
- "ENS"   = Energy Not Served (MWh) — reported in AER STPIS submissions
- "DNSP"  = Distribution Network Service Provider (e.g. AusNet, Jemena, Citipower)
- "ICP"   = Individually Controlled Point — a customer connection point (synonym for NMI)

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
- meter_readings is a fact table; join to assets via distribution_zone <-> region mapping
- regulatory_reports is standalone (document repository, no FK relationships)

## Important Limitations
- meter_readings contains 30-minute intervals; do NOT multiply by 2 to get hourly totals
- energy_not_served_mwh may be NULL for outages < 1 minute; treat NULL as 0 in aggregations
- document_text in regulatory_reports is plain text extracted from PDFs; may contain OCR artefacts
- Only UNPLANNED outages count toward AER SAIDI/SAIFI regulatory reporting
"""

print("Instructions block defined.")
print(f"Length: {len(GENIE_INSTRUCTIONS):,} characters")

# COMMAND ----------

# MAGIC %md
# MAGIC #### 2b — Create the space via REST API

# COMMAND ----------

import requests, json

HOST = spark.conf.get("spark.databricks.workspaceUrl")

def get_headers():
    """Return auth headers for Databricks REST API calls."""
    t = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}

payload = {
    "title": "NEM Grid Operations — Energy Analytics",
    "description": (
        "Self-service analytics for NEM grid operations, outage management, "
        "asset health and regulatory reporting. Covers meter readings, network "
        "assets, outages, and AER/AEMO compliance documents."
    )
}

resp = requests.post(
    f"https://{HOST}/api/2.0/genie/spaces",
    headers=get_headers(),
    json=payload
)
resp.raise_for_status()
SPACE_ID = resp.json()["space_id"]

print("Genie Space created successfully.")
print(f"  Space ID  : {SPACE_ID}")
print(f"  Space URL : https://{HOST}/genie/spaces/{SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 3 — Add Tables as Trusted Assets</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:5px solid #F9A825; padding:14px 18px; border-radius:0 6px 6px 0; margin:12px 0;">
# MAGIC   <strong>Trusted assets are a security control.</strong><br>
# MAGIC   Genie will only query tables that have been explicitly added as trusted assets.
# MAGIC   This prevents accidental exposure of other Unity Catalog tables even if the workspace
# MAGIC   credential could technically access them.
# MAGIC </div>
# MAGIC
# MAGIC **UI equivalent:** Configure --> Tables tab --> [+ Add tables] --> browse to workshop.energy_nem --> select all 4 tables

# COMMAND ----------

TABLES_TO_ADD = [
    f"{CATALOG}.{SCHEMA}.meter_readings",
    f"{CATALOG}.{SCHEMA}.assets",
    f"{CATALOG}.{SCHEMA}.outages",
    f"{CATALOG}.{SCHEMA}.regulatory_reports",
]

print("Adding trusted assets to Genie Space...")
print()
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
# MAGIC <div style="background:#E8F5E9; border-left:5px solid #2E7D32; padding:16px 20px; border-radius:0 8px 8px 0; margin:12px 0;">
# MAGIC   <strong>Golden queries are the single most impactful improvement you can make to a Genie Space.</strong><br>
# MAGIC   They teach Genie the correct SQL for your most important business questions — both the
# MAGIC   table/join pattern and the correct metric formula.
# MAGIC
# MAGIC   <br><br><strong>Rules for effective golden queries:</strong>
# MAGIC   <ol>
# MAGIC     <li>Cover the top 10–20 questions users will ask most often</li>
# MAGIC     <li>Use exact column names from your tables — helps Genie learn aliases</li>
# MAGIC     <li>Include SQL comments explaining non-obvious logic (especially aggregation formulas)</li>
# MAGIC     <li>Every query must run without errors before you save it</li>
# MAGIC     <li>Keep each query focused on one business question</li>
# MAGIC   </ol>
# MAGIC
# MAGIC   <strong>UI path:</strong>
# MAGIC   Configure --> SQL queries --> [+ Add query] --> paste question + SQL --> [Save query]
# MAGIC </div>

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Total outage duration by region — current financial year",
        "description": (
            "SAIDI-contributing outage hours by NEM region for the current Australian financial year "
            "(July 1 to June 30). Excludes planned outages from the reliability calculation."
        ),
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
        "description": (
            "Asset reliability league table — identifies chronic problem assets that need "
            "maintenance or replacement investment. Joins outages to the asset register on asset_id."
        ),
        "sql": f"""
-- Asset reliability ranking — join outages to assets on asset_id
SELECT
    a.asset_name,
    a.asset_type,
    a.owner_dnsp,
    a.region,
    COUNT(o.outage_id)                                                       AS outage_count,
    SUM(o.customers_affected)                                                AS total_customers_affected,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time)) / 60, 2)      AS avg_outage_hours,
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
-- Monthly energy consumption per distribution zone
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
        "description": (
            "Compliance calendar showing reports in DRAFT or SUBMITTED status "
            "with a submission_date within the next 90 days."
        ),
        "sql": f"""
SELECT
    report_type,
    title,
    submitting_entity,
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
        "description": (
            "Breakdown of AER-reportable events by root cause. Used to prepare STPIS narrative "
            "sections explaining unusual reliability outcomes."
        ),
        "sql": f"""
-- Cause analysis for AER-reportable unplanned outages only
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

print("Pushing golden queries to Genie knowledge store...")
print()
for q in GOLDEN_QUERIES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=get_headers(),
        json={"name": q["name"], "description": q["description"], "query": q["sql"].strip()}
    )
    icon = "OK  " if resp.status_code in (200, 201) else f"ERROR {resp.status_code}"
    print(f"  [{icon}]  {q['name']}")

print()
print(f"Total golden queries added: {len(GOLDEN_QUERIES)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 5 — Write Instructions to the Space</h2>
# MAGIC </div>
# MAGIC
# MAGIC Now we patch the space with the full instructions block defined in Step 2a.
# MAGIC
# MAGIC **UI equivalent:** Configure --> Instructions tab --> paste text --> [Save instructions]

# COMMAND ----------

resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=get_headers(),
    json={"instructions": GENIE_INSTRUCTIONS.strip()}
)
if resp.status_code == 200:
    print("Instructions updated successfully.")
    print(f"  Length: {len(GENIE_INSTRUCTIONS):,} chars")
else:
    print(f"WARN: {resp.status_code} — {resp.text[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 6 — Set Permissions</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#F3F9FF; border:1px solid #90CAF9; padding:16px 20px; border-radius:8px; margin:12px 0;">
# MAGIC
# MAGIC | Permission Level | Who should have it | What they can do |
# MAGIC |---|---|---|
# MAGIC | <code>CAN_USE</code> | Business analysts, data consumers | Chat with the space |
# MAGIC | <code>CAN_MANAGE</code> | Data engineers who maintain the space | Edit instructions, add queries |
# MAGIC | <code>IS_OWNER</code> | Creator (auto-assigned) | Full control including delete |
# MAGIC
# MAGIC **Best practice:** Assign to Unity Catalog **groups**, not individual users.
# MAGIC Group membership is managed in one place — when someone joins or leaves a team,
# MAGIC their Genie Space access updates automatically.
# MAGIC
# MAGIC **UI path:** Configure --> Permissions tab --> [+ Add] --> search group --> choose level --> [Save]
# MAGIC </div>

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
    print("The space is currently accessible only to the creator (IS_OWNER).")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 7 — Smoke Test via Conversation API</h2>
# MAGIC </div>
# MAGIC
# MAGIC Programmatically start a conversation and ask a test question.
# MAGIC This confirms the space is wired up and returning results before you share it with users.

# COMMAND ----------

def genie_ask(space_id: str, question: str) -> dict:
    """
    Starts a Genie conversation and polls until a result is ready.
    Returns the full response dict.
    """
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

    # Poll for completion (up to 60 seconds)
    for attempt in range(30):
        poll = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}",
            headers=get_headers()
        )
        poll.raise_for_status()
        msg   = poll.json()
        state = msg.get("status", "UNKNOWN")
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            return msg
        print(f"  [{attempt+1}/30]  Status: {state} — waiting 2s...")
        time.sleep(2)

    return {"status": "TIMEOUT", "error": "Polling timed out after 60 seconds"}


# Run the smoke test
TEST_QUESTION = "How many unplanned outages occurred in VIC1 and what was the total energy not served?"

print("Smoke test:")
print(f"  Question: \"{TEST_QUESTION}\"")
print()

result = genie_ask(SPACE_ID, TEST_QUESTION)
print()
print(f"Status: {result.get('status')}")

for att in result.get("attachments", []):
    if att.get("query"):
        print(f"\nGenerated SQL:\n{'='*50}")
        print(att["query"].get("query", ""))
        print("="*50)
    if att.get("text"):
        print(f"\nNarrative: {att['text'].get('content', '')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 8 — Verify in the UI and Save Your Space ID</h2>
# MAGIC </div>
# MAGIC
# MAGIC Before moving to Lab 02, confirm your space looks correct in the Databricks UI:
# MAGIC
# MAGIC ```
# MAGIC Navigation:  Left sidebar --> Genie --> your space should appear under "My spaces"
# MAGIC
# MAGIC +-- NEM Grid Operations -- Energy Analytics ------------------------------+
# MAGIC |   [Chat]   [Configure]                                                  |
# MAGIC |                                                                         |
# MAGIC |   Configure                                                             |
# MAGIC |   +-- Instructions    -> should show your domain text (400+ chars)     |
# MAGIC |   +-- Tables (4)      -> meter_readings, assets, outages,              |
# MAGIC |   |                      regulatory_reports                             |
# MAGIC |   +-- SQL queries (5) -> all five golden queries visible               |
# MAGIC |   +-- Permissions     -> your user listed as IS_OWNER                  |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC **Quick test in Chat mode:**
# MAGIC Click [Chat] and type: "How many unplanned outages are in the dataset?"
# MAGIC Genie should return 30 (the number of sample rows we inserted).

# COMMAND ----------

print("=" * 65)
print("  LAB 01 COMPLETE")
print("=" * 65)
print(f"  Catalog / Schema  :  {CATALOG}.{SCHEMA}")
print(f"  Genie Space ID    :  {SPACE_ID}")
print(f"  Workspace URL     :  https://{HOST}")
print(f"  Genie Space URL   :  https://{HOST}/genie/spaces/{SPACE_ID}")
print()
print("  IMPORTANT: Copy the Space ID above.")
print("  You will paste it into SPACE_ID in Lab 02 and Lab 03.")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 01 — Review Questions
# MAGIC
# MAGIC <div style="background:#F5F5F5; padding:20px 24px; border-radius:8px; margin:12px 0;">
# MAGIC
# MAGIC 1. What is the difference between a **trusted asset** and a **golden query** in a Genie Space?
# MAGIC    When does Genie use each one?
# MAGIC
# MAGIC 2. The `instructions` field acts like a system prompt. What are **three things** you should
# MAGIC    always include for a regulated industry customer?
# MAGIC
# MAGIC 3. Why do we add column-level `COMMENT` to tables **before** creating the Genie Space?
# MAGIC    What would happen if comments were added after the space was already in use?
# MAGIC
# MAGIC 4. A business analyst asks Genie "what was our SAIDI last year?" and gets a wrong number.
# MAGIC    List **three possible causes** and the admin action to fix each.
# MAGIC
# MAGIC 5. Which permission level should a read-only data consumer have — `CAN_USE` or `CAN_MANAGE`?
# MAGIC    What extra capabilities does `CAN_MANAGE` grant?
# MAGIC
# MAGIC </div>
# MAGIC
# MAGIC **Proceed to Lab 02 when ready.**
