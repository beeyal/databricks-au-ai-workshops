# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 04: Genie Space -- Admin Setup &amp; Operating Model
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">
# MAGIC     Session 2: Technical Enablement · AEMO Australian Energy Operations
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="width:100%; border-collapse:collapse; margin-top:16px; font-family:'DM Sans',sans-serif;">
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px; width:25%"><b>Session</b></td><td style="padding:8px 16px;">Session 2: Technical Enablement</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Duration</b></td><td style="padding:8px 16px;">45 minutes</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Role</b></td><td style="padding:8px 16px;">Data Engineer / Platform Engineer</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Prerequisites</b></td><td style="padding:8px 16px;">Lab 02 complete -- AI Gateway endpoint running &nbsp;|&nbsp; <code>workshop_au.energy</code> tables exist &nbsp;|&nbsp; <code>workspace_admin</code> or <code>genie_admin</code> entitlement</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Output</b></td><td style="padding:8px 16px;">Production Genie Space live with 10+ golden queries &nbsp;|&nbsp; Certification registry record &nbsp;|&nbsp; Session 3 prerequisites checklist run</td></tr>
# MAGIC </table>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Learning Objectives
# MAGIC
# MAGIC | # | Objective |
# MAGIC |---|-----------|
# MAGIC | 1 | Navigate the Genie UI -- Configure tab, Instructions, SQL examples, Permissions |
# MAGIC | 2 | Create a production-ready Genie Space via REST API using principle of least privilege |
# MAGIC | 3 | Understand how Genie inherits Unity Catalog row and column filters |
# MAGIC | 4 | Apply the Exploratory vs Certified operating model |
# MAGIC | 5 | Set a `space_certification_status` registry record on a Genie Space programmatically |
# MAGIC | 6 | Run the Session 3 prerequisites checklist and produce a pass/fail readiness report |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0: UI Exploration (5 minutes -- do this before running any code)
# MAGIC
# MAGIC ### Navigate to Genie
# MAGIC
# MAGIC **Left sidebar -> Genie** (sparkle/wand icon near the bottom of the sidebar)
# MAGIC
# MAGIC ```
# MAGIC  Genie
# MAGIC  ─────────────────────────────────
# MAGIC  [+ New Space]
# MAGIC  My spaces: (none yet, or list of existing spaces)
# MAGIC ```
# MAGIC
# MAGIC If spaces exist, click one then open the **[Configure]** tab at the top. That is where all admin configuration lives.
# MAGIC
# MAGIC ### Configure tab structure
# MAGIC
# MAGIC ```
# MAGIC  [Chat]  [Configure]
# MAGIC  ┌── Instructions ──  system prompt, every conversation starts with this
# MAGIC  ├── Tables ────────  trusted assets -- Genie ONLY queries these tables
# MAGIC  ├── SQL queries ───  golden queries -- verified SQL examples
# MAGIC  └── Permissions ───  CAN_VIEW = chat  |  CAN_EDIT = edit config
# MAGIC ```
# MAGIC
# MAGIC **Key question:** Who in your organisation should own and maintain the Instructions text? (The data engineer who owns the tables -- not the business analyst.)
# MAGIC
# MAGIC Start the pip install cell below while you explore -- it runs in parallel.

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import os, json, time, requests
from databricks.sdk import WorkspaceClient

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

print(f"Connected to : {HOST}")
print(f"Current user : {w.current_user.me().user_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Workshop Configuration

# COMMAND ----------

# Widget-based configuration -- works in any customer Databricks environment
dbutils.widgets.text("catalog",      "workshop_au",                   "Catalog name")
dbutils.widgets.text("schema",       "energy",                        "Schema name")
dbutils.widgets.text("pt_endpoint",  "au_east_llm_inregion",          "PT endpoint name (from Lab 02)")
dbutils.widgets.text("space_title",  "Workshop -- Energy Operations",  "Genie Space title")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
PT_ENDPOINT  = dbutils.widgets.get("pt_endpoint")
SPACE_TITLE  = dbutils.widgets.get("space_title")

print(f"Catalog / Schema : {CATALOG}.{SCHEMA}")
print(f"PT endpoint      : {PT_ENDPOINT}")
print(f"Space title      : {SPACE_TITLE}")

# COMMAND ----------

def get_headers():
    """Return auth headers for Databricks REST API calls."""
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1: Creating a Production-Ready Genie Space (15 minutes)
# MAGIC
# MAGIC The UI is good for exploration. The API is how you deploy consistently across dev/test/prod, version-control instructions in Git, and rebuild the space if something goes wrong. For a production-regulated environment, "click it in the UI" is not a repeatable or auditable deployment process.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a -- Serverless SQL Warehouse Selection
# MAGIC
# MAGIC Genie requires a SQL warehouse to run the SQL it generates. For production spaces, use serverless: starts in under 3 seconds, scales to zero between bursts, and all data stays in AU East.
# MAGIC
# MAGIC **UI path to find your serverless warehouse:**
# MAGIC ```
# MAGIC  Left sidebar -> SQL -> SQL Warehouses
# MAGIC    -> look for Type = "Serverless"
# MAGIC
# MAGIC  If none exists: [+ Create SQL warehouse] -> Type: Serverless -> Size: Small -> [Create]
# MAGIC ```

# COMMAND ----------

# Discover available SQL warehouses -- find serverless automatically
warehouses = list(w.warehouses.list())
print("Available SQL warehouses:")
print()
serverless_id = None
for wh in warehouses:
    wtype = wh.warehouse_type.value if wh.warehouse_type else "classic"
    print(f"  [{wtype.upper():12s}]  {wh.name}  (id: {wh.id},  state: {wh.state.value if wh.state else 'unknown'})")
    if wtype.lower() == "serverless" and not serverless_id:
        serverless_id = wh.id

if not serverless_id and warehouses:
    serverless_id = warehouses[0].id
    print(f"\nNo serverless warehouse found. Using first available: {warehouses[0].name}")
    print("For production use, create a serverless SQL warehouse.")
elif serverless_id:
    wh_name = next(wh.name for wh in warehouses if wh.id == serverless_id)
    print(f"\nSelected warehouse: {wh_name}  ({serverless_id})")

assert serverless_id, "No SQL warehouse found. Create one under SQL > SQL Warehouses before proceeding."

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b -- Principle of Least Privilege for Trusted Assets
# MAGIC
# MAGIC Trusted assets define what Genie **can** query -- this is an allow-list, not a filter. If a table is not in trusted assets, Genie cannot see it regardless of UC permissions. Add only tables for the specific domain this space serves.
# MAGIC
# MAGIC **How Genie inherits UC permissions:**
# MAGIC ```
# MAGIC  User asks question -> Genie generates SQL -> SQL runs against Unity Catalog
# MAGIC     -> UC row filters apply    <- automatically, no Genie config needed
# MAGIC     -> UC column masks apply   <- automatically
# MAGIC     -> ABAC tag policies apply <- automatically
# MAGIC  Results returned to user
# MAGIC ```
# MAGIC
# MAGIC One Genie Space can serve multiple DNSP teams -- control access at the UC layer, not by creating separate spaces per DNSP.

# COMMAND ----------

# Tables for this space -- energy operations domain only, not everything in the catalog
TRUSTED_TABLES = [
    f"{CATALOG}.{SCHEMA}.meter_readings",
    f"{CATALOG}.{SCHEMA}.assets",
    f"{CATALOG}.{SCHEMA}.outages",
    f"{CATALOG}.{SCHEMA}.regulatory_reports",
]

print("Tables added as trusted assets:")
for t in TRUSTED_TABLES:
    print(f"  {t}")

print()
print("Intentionally excluded:")
print("  workshop_au.hr.*        -- wrong domain")
print("  workshop_au.finance.*   -- needs its own governed space")
print("  information_schema.*    -- never add metadata tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c -- Create the Genie Space
# MAGIC
# MAGIC **UI equivalent:** Left sidebar -> Genie -> **[+ New Space]**
# MAGIC ```
# MAGIC  Title:       Workshop -- Energy Operations
# MAGIC  Description: Self-service analytics for NEM grid operations...
# MAGIC  Warehouse:   workshop-serverless  (must be a running SQL warehouse)
# MAGIC  [Create space ->]
# MAGIC ```

# COMMAND ----------

payload = {
    "title": SPACE_TITLE,
    "description": (
        "Self-service analytics for NEM grid operations, outage management, "
        "network asset health, and AER/AEMO regulatory reporting. "
        "Covers NEM12 interval meter data, network assets, outage events, "
        "and compliance document metadata. "
        "In-region for AU East -- safe for SOCI Act / critical infrastructure regulated data."
    ),
    "warehouse_id": serverless_id,
}

resp = requests.post(
    f"https://{HOST}/api/2.0/genie/spaces",
    headers=get_headers(),
    json=payload
)

if resp.status_code not in (200, 201):
    print(f"Error creating space: HTTP {resp.status_code}")
    print(resp.text[:500])
    raise RuntimeError("Space creation failed -- check error above before continuing.")

SPACE_ID = resp.json()["space_id"]

print("Genie Space created successfully.")
print()
print(f"  Title     : {SPACE_TITLE}")
print(f"  Space ID  : {SPACE_ID}")
print(f"  Warehouse : {serverless_id}")
print(f"  Space URL : https://{HOST}/genie/spaces/{SPACE_ID}")
print()
print("IMPORTANT: Copy the Space ID above. You will need it in the Session 3 prerequisites checklist.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1d -- Add Trusted Assets
# MAGIC
# MAGIC **UI equivalent:** Space -> Configure -> Tables tab -> **[+ Add tables]** -> select tables -> **[Add selected tables]**

# COMMAND ----------

print("Adding trusted assets (energy domain only)...")
print()
for table_fqn in TRUSTED_TABLES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/trusted-assets",
        headers=get_headers(),
        json={"asset_type": "TABLE", "asset_fqn": table_fqn}
    )
    status = "OK  " if resp.status_code in (200, 201) else f"WARN HTTP {resp.status_code}"
    print(f"  [{status}]  {table_fqn}")

print()
print("Trusted assets set. Genie can now query these 4 tables and nothing else.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1e -- Write the Instructions Block
# MAGIC
# MAGIC The instructions block is the most impactful configuration lever. It is the system prompt loaded at the start of every conversation. For AEMO it must cover domain vocabulary, data quality rules, aggregation formulas, Australian time conventions, and default filtering behaviour.

# COMMAND ----------

GENIE_INSTRUCTIONS = """
You are an energy data analyst assistant for an Australian Distribution Network Service Provider (DNSP)
and market participant in the National Electricity Market (NEM).
Your primary users are grid operations managers, regulatory analysts, and asset managers at AEMO.

## Domain Vocabulary
- NMI: National Metering Identifier -- the unique ID for each electricity connection point
- SAIDI: System Average Interruption Duration Index (minutes per customer per year) -- key AER reliability metric
- SAIFI: System Average Interruption Frequency Index (interruptions per customer per year)
- ENS: Energy Not Served (MWh) -- reported in AER STPIS submissions
- DNSP: Distribution Network Service Provider (e.g. AusNet, Jemena, Citipower, Powercor)
- ICP: Individually Controlled Point -- a customer connection point (synonym for NMI)
- NEM regions: QLD1, NSW1, VIC1, SA1, TAS1

## Time and Date Conventions
- "This year" or "current year" = current Australian financial year (July 1 - June 30)
- "Last year" = previous Australian financial year
- All timestamps are in Australian Eastern Standard Time (AEST / UTC+10) unless stated otherwise
- Australian summer (high demand season) = December, January, February
- Australian winter (second demand peak -- electric heating) = June, July, August
- "This financial year" SQL pattern: WHERE start_time >= DATE_TRUNC('year', ADD_MONTHS(CURRENT_DATE, -((MONTH(CURRENT_DATE)-7+12)%12)))

## meter_readings -- Critical Rules
- Each row is a 30-MINUTE interval. NEVER multiply by 2 to get hourly kWh.
- To get hourly totals: SUM(active_energy_kwh) grouped by DATE_TRUNC('hour', interval_datetime)
- Daily kWh for a meter: SUM(active_energy_kwh) WHERE nmi = X and DATE(interval_datetime) = date
- Monthly MWh for a zone: SUM(active_energy_kwh) / 1000 grouped by month and distribution_zone
- Always filter: WHERE quality_flag IN ('A', 'E') for reliable consumption analysis
- Never include quality_flag = 'S' (substituted) or 'N' (none) in consumption totals unless investigating data quality

## outages -- AER Regulatory Rules
- SAIDI formula: SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) / total_ICPs
- SAIFI formula: SUM(customers_affected) / total_ICPs
- ALWAYS filter outage_type = 'UNPLANNED' for AER regulatory metrics. PLANNED outages do not count.
- ALWAYS use COALESCE(energy_not_served_mwh, 0) in SUM aggregations -- NULL means < 1 min outage
- Duration in hours: ROUND(TIMESTAMPDIFF(MINUTE, start_time, end_time) / 60, 1)
- active outage = end_time IS NULL; completed outage = end_time IS NOT NULL

## Table Relationships
- outages.asset_id -> assets.asset_id (many outages per asset)
- meter_readings.distribution_zone maps to outages.region by zone-to-region mapping
- regulatory_reports is standalone (no FK relationships -- use for document search only)

## Default Behaviour
- Show data for ALL regions unless the user specifies one
- Sort results most-recent-first unless user asks for ranking by a metric
- Express outage durations in hours rounded to 1 decimal place
- For regulatory questions, always note whether the metric is AER-reportable or not
"""

resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=get_headers(),
    json={"instructions": GENIE_INSTRUCTIONS.strip()}
)
if resp.status_code == 200:
    print(f"Instructions written successfully ({len(GENIE_INSTRUCTIONS):,} chars).")
    print("These instructions are now the system prompt for every conversation in this space.")
else:
    print(f"WARN: HTTP {resp.status_code} -- {resp.text[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1f -- Seed the Knowledge Store with Golden Queries
# MAGIC
# MAGIC Golden queries teach Genie the correct SQL for the most common business questions. For a certified/production space, aim for 15-25 covering all major question types. We seed 10 here -- sufficient for Session 3. Every golden query must run without errors before you save it.

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Total unplanned outages by region -- current financial year",
        "description": "AER-relevant outage count and SAIDI numerator by NEM region for current Australian financial year. Only UNPLANNED outages with reported_to_aer = TRUE count toward regulatory metrics.",
        "sql": f"""
-- SAIDI-contributing outage summary by region for the current Australian financial year
SELECT
    region,
    COUNT(*)                                                           AS outage_count,
    SUM(customers_affected)                                            AS total_customer_interruptions,
    ROUND(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1)   AS total_outage_hours,
    SUM(COALESCE(energy_not_served_mwh, 0))                            AS total_ens_mwh
FROM {CATALOG}.{SCHEMA}.outages
WHERE outage_type = 'UNPLANNED'
  AND reported_to_aer = TRUE
GROUP BY region
ORDER BY total_customer_interruptions DESC
""",
    },
    {
        "name": "Top 10 problem assets by unplanned outage frequency",
        "description": "Asset reliability league table -- identifies chronic problem assets for maintenance investment prioritisation. Joins outages to the asset register.",
        "sql": f"""
SELECT
    a.asset_name,
    a.asset_type,
    a.owner_dnsp,
    a.region,
    COUNT(o.outage_id)                                                        AS outage_count,
    SUM(o.customers_affected)                                                 AS total_customers_affected,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time)) / 60, 2)       AS avg_outage_hours,
    a.last_maintenance
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id
   AND o.outage_type = 'UNPLANNED'
GROUP BY a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp, a.region, a.last_maintenance
ORDER BY outage_count DESC
LIMIT 10
""",
    },
    {
        "name": "Monthly energy consumption by distribution zone",
        "description": "Aggregates NEM12 interval meter data to monthly active energy per distribution zone. Excludes substituted (S) and missing (N) quality flags.",
        "sql": f"""
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
""",
    },
    {
        "name": "Assets overdue for maintenance inspection",
        "description": "Network assets in IN_SERVICE status whose last_maintenance date is more than 12 months ago. Used to prioritise maintenance scheduling and avoid AER compliance breaches.",
        "sql": f"""
SELECT
    a.asset_name,
    a.asset_type,
    a.owner_dnsp,
    a.region,
    a.voltage_kv,
    a.last_maintenance,
    DATEDIFF(CURRENT_DATE, a.last_maintenance)           AS days_since_maintenance,
    COUNT(o.outage_id)                                   AS outages_since_maintenance
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id
   AND o.start_time > a.last_maintenance
WHERE a.status = 'IN_SERVICE'
  AND a.last_maintenance < DATE_SUB(CURRENT_DATE, 365)
GROUP BY a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp, a.region, a.voltage_kv, a.last_maintenance
ORDER BY days_since_maintenance DESC
""",
    },
    {
        "name": "Outage cause breakdown for AER STPIS narrative",
        "description": "Root cause analysis of AER-reportable unplanned outages. Used to prepare the STPIS annual submission narrative explaining reliability outcomes.",
        "sql": f"""
SELECT
    cause_category,
    COUNT(*)                                            AS reportable_events,
    SUM(customers_affected)                             AS customers_affected,
    ROUND(SUM(COALESCE(energy_not_served_mwh, 0)), 2)   AS total_ens_mwh,
    ROUND(AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) AS avg_duration_hours
FROM {CATALOG}.{SCHEMA}.outages
WHERE reported_to_aer = TRUE
GROUP BY cause_category
ORDER BY reportable_events DESC
""",
    },
    {
        "name": "Outstanding regulatory submissions -- next 90 days",
        "description": "Compliance calendar showing reports in DRAFT or SUBMITTED status due within the next 90 days.",
        "sql": f"""
SELECT
    report_type,
    title,
    submitting_entity,
    period_end                               AS reporting_period_end,
    submission_date                          AS scheduled_submission_date,
    status,
    DATEDIFF(submission_date, CURRENT_DATE)  AS days_until_due
FROM {CATALOG}.{SCHEMA}.regulatory_reports
WHERE status IN ('DRAFT', 'SUBMITTED')
  AND submission_date BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, 90)
ORDER BY submission_date
""",
    },
    {
        "name": "Peak demand intervals by distribution zone -- summer vs winter",
        "description": "Top peak demand half-hour intervals per zone split by season. Used for network capacity planning and summer/winter readiness reporting.",
        "sql": f"""
WITH seasonal_peaks AS (
    SELECT
        distribution_zone,
        DATE(interval_datetime) AS reading_date,
        CASE
            WHEN MONTH(interval_datetime) IN (12, 1, 2) THEN 'SUMMER'
            WHEN MONTH(interval_datetime) IN (6, 7, 8)  THEN 'WINTER'
            ELSE 'SHOULDER'
        END                                     AS season,
        MAX(active_energy_kwh * 2)              AS peak_demand_kw,
        COUNT(DISTINCT nmi)                     AS active_meters
    FROM {CATALOG}.{SCHEMA}.meter_readings
    WHERE quality_flag IN ('A', 'E')
    GROUP BY distribution_zone, DATE(interval_datetime),
        CASE WHEN MONTH(interval_datetime) IN (12,1,2) THEN 'SUMMER'
             WHEN MONTH(interval_datetime) IN (6,7,8)  THEN 'WINTER'
             ELSE 'SHOULDER' END
)
SELECT distribution_zone, season, reading_date,
       ROUND(peak_demand_kw, 1)   AS peak_demand_kw,
       active_meters
FROM seasonal_peaks
ORDER BY distribution_zone, season, peak_demand_kw DESC
""",
    },
    {
        "name": "Data quality check -- meter readings with poor quality flags",
        "description": "Identifies NMIs with more than 5% substituted or missing readings in the last 30 days. Used for data quality monitoring and NEM12 validation.",
        "sql": f"""
WITH quality_summary AS (
    SELECT
        nmi,
        distribution_zone,
        COUNT(*) AS total_intervals,
        SUM(CASE WHEN quality_flag IN ('S', 'N') THEN 1 ELSE 0 END) AS poor_quality_intervals
    FROM {CATALOG}.{SCHEMA}.meter_readings
    WHERE interval_datetime >= DATE_SUB(CURRENT_DATE, 30)
    GROUP BY nmi, distribution_zone
)
SELECT
    nmi,
    distribution_zone,
    total_intervals,
    poor_quality_intervals,
    ROUND(100.0 * poor_quality_intervals / total_intervals, 1) AS poor_quality_pct
FROM quality_summary
WHERE poor_quality_intervals > 0.05 * total_intervals
ORDER BY poor_quality_pct DESC
""",
    },
    {
        "name": "SAIDI year-to-date by region",
        "description": "Year-to-date SAIDI numerator per NEM region using the AER formula. Uses a placeholder denominator of 1,000,000 ICPs -- replace with actual customer register count.",
        "sql": f"""
-- SAIDI = SUM(interruption_minutes x customers_affected) / total_ICPs
-- Denominator of 1,000,000 is a placeholder -- replace with actual ICP count
SELECT
    region,
    COUNT(*)                                                             AS outage_count,
    SUM(customers_affected)                                              AS total_customer_interruptions,
    SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_numerator,
    ROUND(
        SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) / 1000000.0
    , 2)                                                                 AS saidi_minutes_per_customer
FROM {CATALOG}.{SCHEMA}.outages
WHERE outage_type = 'UNPLANNED'
  AND reported_to_aer = TRUE
  AND end_time IS NOT NULL
  AND YEAR(start_time) = YEAR(CURRENT_DATE)
GROUP BY region
ORDER BY saidi_minutes_per_customer DESC
""",
    },
    {
        "name": "Published regulatory reports -- most recent by type",
        "description": "Latest published regulatory submission per report type. Used to answer 'when was our last STPIS submission' style questions.",
        "sql": f"""
SELECT
    report_type,
    title,
    submitting_entity,
    submission_date,
    status,
    document_url
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY report_type ORDER BY submission_date DESC) AS rn
    FROM {CATALOG}.{SCHEMA}.regulatory_reports
    WHERE status = 'PUBLISHED'
) ranked
WHERE rn = 1
ORDER BY report_type
""",
    },
]

print(f"Seeding {len(GOLDEN_QUERIES)} golden queries into the knowledge store...")
print()
success_count = 0
for q in GOLDEN_QUERIES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=get_headers(),
        json={"name": q["name"], "description": q["description"], "query": q["sql"].strip()}
    )
    icon = "OK  " if resp.status_code in (200, 201) else f"WARN HTTP {resp.status_code}"
    if resp.status_code in (200, 201):
        success_count += 1
    print(f"  [{icon}]  {q['name']}")

print()
print(f"Golden queries added: {success_count} / {len(GOLDEN_QUERIES)}")
if success_count >= 10:
    print("  Session 3 minimum met (10+ queries).")
else:
    print(f"  WARNING: Need at least 10 queries for Session 3. Only {success_count} succeeded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2: The Operating Model -- Exploratory vs Certified (15 minutes)

# COMMAND ----------

# MAGIC %md
# MAGIC ### The Two-Speed Model for Genie Governance
# MAGIC
# MAGIC ```
# MAGIC  EXPLORATORY                    CERTIFIED
# MAGIC  ─────────────────────────────  ──────────────────────────────────
# MAGIC  Purpose: discovery, ideation   Purpose: production answers
# MAGIC  SQL quality: informal          SQL quality: peer-reviewed
# MAGIC  Golden queries: few/none       Golden queries: 20+ validated
# MAGIC  Audience: small team           Audience: whole business unit
# MAGIC  Monitoring: light              Monitoring: full AI Gateway
# MAGIC ```
# MAGIC
# MAGIC An exploratory space with informal SQL can give a regulatory analyst a plausible-looking but wrong SAIDI number. The certification gate prevents this by requiring that answers to the top regulatory questions have been verified before the space is shared.
# MAGIC
# MAGIC **Certification checklist** (before a space is opened to the business):
# MAGIC - [ ] All tables have column-level comments in Unity Catalog
# MAGIC - [ ] 10+ validated golden queries covering the main business questions
# MAGIC - [ ] Instructions tested against 20+ representative questions with expected answers recorded
# MAGIC - [ ] AI Gateway enabled on the warehouse the space uses (with rate limits and payload logging)
# MAGIC - [ ] UC permissions reviewed -- CAN_USE only for consumers, CAN_MANAGE only for maintainers
# MAGIC - [ ] Genie Space owner identified and named in the space description
# MAGIC - [ ] `certification_status` set to `certified` in the space registry table

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2a -- Space Certification Registry
# MAGIC
# MAGIC Genie Spaces are not yet first-class UC objects, so we track certification status in a Delta table. This gives a queryable, auditable record of which spaces are ready for business users. When Databricks exposes Spaces as UC assets (roadmap), this table migrates cleanly to native UC tags.

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.ai_governance")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.ai_governance.genie_space_registry (
    space_id              STRING    COMMENT 'Genie Space ID (UUID from the Genie REST API)',
    space_title           STRING    COMMENT 'Display title of the Genie Space',
    space_url             STRING    COMMENT 'Full URL to access the space in the Databricks UI',
    certification_status  STRING    COMMENT 'Operating model status. Values: exploratory, certified.',
    certified_by          STRING    COMMENT 'Email of the data engineer who certified the space. NULL for exploratory.',
    certified_at          TIMESTAMP COMMENT 'When certification status was set to certified. NULL for exploratory.',
    golden_query_count    INT       COMMENT 'Number of validated golden queries at certification time.',
    tables_in_scope       STRING    COMMENT 'Comma-separated list of fully-qualified table names as trusted assets.',
    target_audience       STRING    COMMENT 'Who is allowed to use this space.',
    space_owner           STRING    COMMENT 'Email of the data engineer responsible for maintaining this space.',
    notes                 STRING    COMMENT 'Free-text notes on data quality, known limitations, or next actions.',
    created_at            TIMESTAMP COMMENT 'When this record was first inserted.'
)
USING DELTA
COMMENT 'Registry of all Genie Spaces with certification status and ownership metadata. One row per space.'
""")

print("genie_space_registry table ready.")

# COMMAND ----------

from pyspark.sql import Row
from datetime import datetime

registry_row = Row(
    space_id             = SPACE_ID,
    space_title          = SPACE_TITLE,
    space_url            = f"https://{HOST}/genie/spaces/{SPACE_ID}",
    certification_status = "exploratory",   # starts exploratory -- promote after benchmark
    certified_by         = None,
    certified_at         = None,
    golden_query_count   = success_count,
    tables_in_scope      = ", ".join(TRUSTED_TABLES),
    target_audience      = "AEMO grid operations managers, regulatory analysts, asset managers",
    space_owner          = w.current_user.me().user_name,
    notes                = (
        "Created in Session 2 technical enablement. "
        "Status: exploratory -- 10 golden queries seeded. "
        "Promote to certified after running 20-question benchmark. "
        "Next action: benchmark against AEMO standard question set before Session 3."
    ),
    created_at           = datetime.utcnow()
)

spark.createDataFrame([registry_row]).write.mode("append").saveAsTable(f"{CATALOG}.ai_governance.genie_space_registry")

print("Registry record written.")
print()
print("Current certification status: exploratory")
print("To promote to certified:")
print("  1. Run the 20-question benchmark and verify answers")
print("  2. UPDATE ... SET certification_status = 'certified', certified_by = ..., certified_at = CURRENT_TIMESTAMP")

# COMMAND ----------

# Check certification status across all spaces
spark.sql(f"""
SELECT
    space_title,
    certification_status,
    golden_query_count,
    space_owner,
    certified_by,
    certified_at,
    notes
FROM {CATALOG}.ai_governance.genie_space_registry
ORDER BY created_at DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2b -- Promoting to Certified (reference SQL -- run when ready)
# MAGIC
# MAGIC ```sql
# MAGIC UPDATE workshop_au.ai_governance.genie_space_registry
# MAGIC SET
# MAGIC     certification_status = 'certified',
# MAGIC     certified_by         = 'your.name@aemo.com.au',
# MAGIC     certified_at         = CURRENT_TIMESTAMP,
# MAGIC     golden_query_count   = <final_count>,
# MAGIC     notes                = 'Benchmark complete: 20/20 questions correct. Approved for Session 3.'
# MAGIC WHERE space_id = '<SPACE_ID>'
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2c -- Setting Permissions
# MAGIC
# MAGIC **UI path:** Space -> Configure -> **Permissions** section -> **[+ Add]** -> search group -> choose level -> **[Save]**
# MAGIC
# MAGIC UC permissions on underlying tables are also enforced -- Genie inherits row/column filters automatically.
# MAGIC
# MAGIC | Permission | Who | What |
# MAGIC |---|---|---|
# MAGIC | `CAN_USE` | Business analysts, operational teams | Chat with the space |
# MAGIC | `CAN_MANAGE` | Data engineers | Edit instructions, add golden queries, change trusted assets |
# MAGIC | `IS_OWNER` | Creator (auto-assigned) | Full control including delete |
# MAGIC
# MAGIC Best practice: assign permissions to Unity Catalog **groups**, not individual users.

# COMMAND ----------

# TODO: replace group names with groups that exist in your workspace
# Uncomment and populate before Session 3
PERMISSION_GRANTS = [
    # {"group_name": "aemo-genie-users",         "permission_level": "CAN_USE"},
    # {"group_name": "aemo-data-engineers",      "permission_level": "CAN_MANAGE"},
    # {"group_name": "aemo-regulatory-analysts", "permission_level": "CAN_USE"},
]

if not PERMISSION_GRANTS:
    print("No permission grants configured yet.")
    print("Before Session 3, uncomment the PERMISSION_GRANTS entries above and run this cell.")
    print("The space is currently accessible only to the creator (IS_OWNER).")
else:
    for grant in PERMISSION_GRANTS:
        resp = requests.patch(
            f"https://{HOST}/api/2.0/permissions/genie/spaces/{SPACE_ID}",
            headers=get_headers(),
            json={"access_control_list": [
                {"group_name": grant["group_name"], "permission_level": grant["permission_level"]}
            ]}
        )
        icon = "OK  " if resp.status_code == 200 else f"WARN HTTP {resp.status_code}"
        print(f"  [{icon}]  {grant['group_name']} -> {grant['permission_level']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3: Prerequisites Checklist Before Business User Enablement (10 minutes)
# MAGIC
# MAGIC This checklist is the formal gate between Session 2 and Session 3. Run it at the end of Session 2 to confirm all technical prerequisites are met. Every check calls a live API -- not just asserting variables.

# COMMAND ----------

def run_s3_readiness_checklist(space_id: str, pt_endpoint_name: str, catalog: str, schema: str) -> None:
    """
    Run the Session 3 prerequisites checklist.
    Checks every technical requirement before opening Genie to business users.
    Prints a pass/fail HTML report with remediation guidance for each failed item.
    """
    checks   = []  # list of (label, passed, detail, remediation)
    all_pass = True

    # Check 1: Geography enforcement (manual verify -- API check for awareness)
    try:
        requests.get(
            f"https://{HOST}/api/2.0/settings/types/aibi_genie_data_access_standard/etag/default",
            headers=get_headers()
        )
        checks.append((
            "Geography enforcement",
            True,
            "Verify shield_csp_enforcement_account_setting is ENABLED in Account Console",
            "Account Console > Settings > Security > 'Enforce data processing within workspace Geography'"
        ))
    except Exception as e:
        checks.append((
            "Geography enforcement",
            False,
            f"Could not verify: {str(e)[:80]}",
            "Manually verify: Account Console > Settings > Security > Geography enforcement = ENABLED"
        ))

    # Check 2: PT endpoint deployed and running
    try:
        endpoints = list(w.serving_endpoints.list())
        pt_ep     = next((e for e in endpoints if e.name == pt_endpoint_name), None)
        if pt_ep is None:
            checks.append((
                "PT endpoint deployed",
                False,
                f"Endpoint '{pt_endpoint_name}' not found. Found: {[e.name for e in endpoints[:5]]}",
                f"Deploy the PT endpoint named '{pt_endpoint_name}' via Serving > [Create endpoint]"
            ))
        else:
            state = pt_ep.state.ready.value if pt_ep.state and pt_ep.state.ready else "unknown"
            passed = state.upper() == "READY"
            checks.append((
                "PT endpoint deployed",
                passed,
                f"Endpoint '{pt_endpoint_name}' found, state: {state}",
                "Wait for endpoint to reach READY state (10-15 minutes)." if not passed else ""
            ))
    except Exception as e:
        checks.append((
            "PT endpoint deployed",
            False,
            f"Could not list serving endpoints: {str(e)[:80]}",
            "Ensure you have ML permissions. Run Lab 02 first."
        ))

    # Check 3: AI Gateway enabled on PT endpoint
    try:
        gw_resp = requests.get(
            f"https://{HOST}/api/2.0/serving-endpoints/{pt_endpoint_name}/ai-gateway",
            headers=get_headers()
        )
        if gw_resp.status_code == 200:
            gw_cfg = gw_resp.json()
            usage_tracking = gw_cfg.get("usage_tracking_config", {}).get("enabled", False)
            checks.append((
                "AI Gateway on PT endpoint",
                True,
                f"AI Gateway configured on '{pt_endpoint_name}'. Usage tracking: {usage_tracking}",
                "" if usage_tracking else "Enable usage tracking in AI Gateway config for cost attribution in Lab 05."
            ))
        else:
            checks.append((
                "AI Gateway on PT endpoint",
                False,
                f"No AI Gateway config found on '{pt_endpoint_name}' (HTTP {gw_resp.status_code})",
                "Run Lab 02 to configure AI Gateway on the PT endpoint before Session 3."
            ))
    except Exception as e:
        checks.append((
            "AI Gateway on PT endpoint",
            False,
            f"Could not check AI Gateway: {str(e)[:80]}",
            "Run Lab 02 first."
        ))

    # Check 4: Genie Space exists
    try:
        sp_resp = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}",
            headers=get_headers()
        )
        if sp_resp.status_code == 200:
            sp_data = sp_resp.json()
            checks.append((
                "Genie Space exists",
                True,
                f"Space '{sp_data.get('title')}' found (ID: {space_id})",
                ""
            ))
        else:
            checks.append((
                "Genie Space exists",
                False,
                f"Space not found: HTTP {sp_resp.status_code}",
                "Run Section 1 of this lab to create the Genie Space."
            ))
    except Exception as e:
        checks.append(("Genie Space exists", False, str(e)[:80], "Run Section 1 of this lab."))

    # Check 5: Golden query count
    try:
        qr = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/sql-queries",
            headers=get_headers()
        )
        if qr.status_code == 200:
            n_queries = len(qr.json().get("sql_queries", []))
            passed    = n_queries >= 10
            checks.append((
                "Golden queries (>= 10)",
                passed,
                f"{n_queries} golden queries in knowledge store",
                "Run Section 1f of this lab to seed additional golden queries." if not passed else ""
            ))
        else:
            checks.append((
                "Golden queries (>= 10)",
                False,
                f"Could not check: HTTP {qr.status_code}",
                "Verify the Space ID is correct and you have access."
            ))
    except Exception as e:
        checks.append(("Golden queries (>= 10)", False, str(e)[:80], "Run Section 1f."))

    # Check 6: Trusted assets
    try:
        ar = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/trusted-assets",
            headers=get_headers()
        )
        if ar.status_code == 200:
            n_assets = len(ar.json().get("trusted_assets", []))
            passed   = n_assets >= 1
            checks.append((
                "Trusted assets added",
                passed,
                f"{n_assets} trusted asset(s) in space",
                "Run Section 1d of this lab to add trusted tables." if not passed else ""
            ))
        else:
            checks.append((
                "Trusted assets added",
                False,
                f"Could not check: HTTP {ar.status_code}",
                "Verify the Space ID and your access."
            ))
    except Exception as e:
        checks.append(("Trusted assets added", False, str(e)[:80], "Run Section 1d."))

    # Check 7: Certification registry record
    try:
        reg = spark.sql(f"""
            SELECT certification_status, golden_query_count
            FROM {catalog}.ai_governance.genie_space_registry
            WHERE space_id = '{space_id}'
        """).collect()
        if reg:
            status = reg[0]["certification_status"]
            gqc    = reg[0]["golden_query_count"]
            passed = status in ("exploratory", "certified")
            checks.append((
                "Space in certification registry",
                passed,
                f"Status: {status}, golden queries recorded: {gqc}",
                "Run Section 2a of this lab to create the registry record." if not passed else ""
            ))
        else:
            checks.append((
                "Space in certification registry",
                False,
                "No registry record found for this space",
                "Run Section 2a of this lab."
            ))
    except Exception as e:
        checks.append(("Space in certification registry", False, str(e)[:80], "Run Section 2a."))

    # Check 8: Tables have column comments
    tables_without_comments = []
    for tbl in ["meter_readings", "assets", "outages", "regulatory_reports"]:
        try:
            desc = spark.sql(f"DESCRIBE EXTENDED {catalog}.{schema}.{tbl}").collect()
            comment_row = next((r for r in desc if r["col_name"] == "Comment"), None)
            if not comment_row or not str(comment_row["data_type"]).strip():
                tables_without_comments.append(tbl)
        except Exception:
            tables_without_comments.append(f"{tbl} (not found)")

    checks.append((
        "Energy tables have comments",
        len(tables_without_comments) == 0,
        "All 4 tables have table-level comments" if not tables_without_comments else f"Missing comments: {tables_without_comments}",
        "Add COMMENT ON TABLE statements for each table -- see Lab 01 setup for examples." if tables_without_comments else ""
    ))

    # Print HTML report
    passed_count = sum(1 for _, p, _, _ in checks if p)
    failed_count = len(checks) - passed_count

    display_html = f"""
    <div style="font-family:'DM Sans',sans-serif; max-width:800px;">
      <div style="background:#1B3A6B; color:white; padding:16px 24px; border-radius:8px 8px 0 0;">
        <h2 style="margin:0; font-size:1.3em;">Session 3 Prerequisites Checklist</h2>
        <p style="margin:4px 0 0 0; opacity:0.85; font-size:0.9em;">
          Run at the end of Session 2 -- must pass all critical checks before opening Genie to business users
        </p>
      </div>
      <table style="width:100%; border-collapse:collapse; border: 1px solid #ddd;">
        <tr style="background:#f5f5f5;">
          <th style="padding:10px 16px; text-align:left; width:5%;">Status</th>
          <th style="padding:10px 16px; text-align:left; width:30%;">Check</th>
          <th style="padding:10px 16px; text-align:left;">Detail</th>
        </tr>
    """

    for label, passed, detail, remediation in checks:
        bg     = "#E8F5E9" if passed else "#FFEBEE"
        badge  = "<span style='color:#2E7D32; font-weight:bold;'>PASS</span>" if passed else "<span style='color:#C62828; font-weight:bold;'>FAIL</span>"
        extra  = f"<br><em style='color:#C62828; font-size:0.85em;'>Action: {remediation}</em>" if (not passed and remediation) else ""
        if not passed:
            all_pass = False
        display_html += f"""
        <tr style="background:{bg};">
          <td style="padding:10px 16px;">{badge}</td>
          <td style="padding:10px 16px;"><strong>{label}</strong></td>
          <td style="padding:10px 16px;">{detail}{extra}</td>
        </tr>
        """

    summary_color = "#2E7D32" if all_pass else "#C62828"
    summary_text  = "All checks passed -- ready to open Genie to business users in Session 3." if all_pass else f"{failed_count} check(s) failed. Resolve the items above before Session 3."

    display_html += f"""
      </table>
      <div style="background:{summary_color}; color:white; padding:14px 24px; border-radius:0 0 8px 8px;">
        <strong>{passed_count}/{len(checks)} checks passed.</strong> {summary_text}
      </div>
      <div style="background:#F5F5F5; padding:12px 24px; border-radius:0 0 8px 8px; margin-top:2px; font-size:0.85em;">
        Space ID: {space_id} &nbsp;|&nbsp;
        Space URL: <a href="https://{HOST}/genie/spaces/{space_id}">https://{HOST}/genie/spaces/{space_id}</a>
      </div>
    </div>
    """

    displayHTML(display_html)


# Run the checklist
run_s3_readiness_checklist(
    space_id         = SPACE_ID,
    pt_endpoint_name = PT_ENDPOINT,
    catalog          = CATALOG,
    schema           = SCHEMA
)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Final Output -- Save Your Space ID

# COMMAND ----------

print("=" * 68)
print("  LAB 04 COMPLETE -- GENIE SPACE ADMIN SETUP & OPERATING MODEL")
print("=" * 68)
print()
print(f"  Catalog / Schema      :  {CATALOG}.{SCHEMA}")
print(f"  Genie Space ID        :  {SPACE_ID}")
print(f"  Genie Space title     :  {SPACE_TITLE}")
print(f"  Genie Space URL       :  https://{HOST}/genie/spaces/{SPACE_ID}")
print(f"  Golden queries loaded :  {success_count}")
print(f"  Certification status  :  exploratory")
print()
print("  IMPORTANT: Copy the Genie Space ID and URL above.")
print("  You will need the Space ID for:")
print("    Lab 05 -- to check AI Gateway usage on the space's warehouse")
print("    Lab 06 -- to include the space in the compliance evidence package")
print("    Session 3 -- to share the URL with business user participants")
print()
print("  Next steps before Session 3:")
print("    1. Uncomment PERMISSION_GRANTS in Section 2c and grant CAN_USE to participant group")
print("    2. Run the 20-question benchmark and update certification_status to 'certified'")
print("    3. Re-run the Session 3 checklist at the start of Session 3 to confirm all checks pass")
print("=" * 68)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 04 -- Review Questions
# MAGIC
# MAGIC **Q1.** A business analyst asks "Can I add the customer master table to our Genie Space so I can see NMI holder names?" The table has no row-level filters. As the data engineer, what is the right response and what controls would you apply if you agreed?
# MAGIC
# MAGIC **Q2.** The Session 3 checklist shows FAIL on "Golden queries (>= 10)" even though you added 10 queries in Section 1f. What are three possible causes and how do you diagnose each?
# MAGIC
# MAGIC **Q3.** Explain the difference between an exploratory and a certified Genie Space in terms that a regulatory affairs manager (not a data engineer) could understand. How would you communicate the risk of using an exploratory space for AER submission data?
# MAGIC
# MAGIC **Q4.** A Genie Space is currently certified for the grid operations team. The data engineer wants to add two new tables and 5 new golden queries. What is the correct process for doing this without disrupting the certified state?
# MAGIC
# MAGIC **Q5.** Why does Genie inherit Unity Catalog row and column filters automatically? Give a concrete example of how this benefits a DNSP with multiple licensed areas.
# MAGIC
# MAGIC **Proceed to Lab 05 (Usage Tracking) when ready -- it's in `workshop1_admin/labs/04_usage_tracking.py`.**
