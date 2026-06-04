# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Session 1 — Platform Admin Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Pre-requisite — run this BEFORE the Session 1 labs</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 1.**
# MAGIC It creates the catalog and schemas, generates the energy sample data using SQL (no CSV files required),
# MAGIC adds column comments, and grants participant access.
# MAGIC The labs handle AI Gateway config, audit policies, and compliance evidence collection.
# MAGIC
# MAGIC Expected runtime: ~5–8 minutes

# COMMAND ----------

dbutils.widgets.text("catalog",          "workshop_au",          "Catalog")
dbutils.widgets.text("schema_energy",    "energy",               "Energy schema")
dbutils.widgets.text("schema_governance","ai_governance",        "Governance schema")
dbutils.widgets.text("pt_endpoint",      "au_east_llm_inregion", "Pay-per-token endpoint name")
dbutils.widgets.text("vs_endpoint",      "workshop_vs",          "Vector Search endpoint name")

CATALOG    = dbutils.widgets.get("catalog")
SCHEMA_E   = dbutils.widgets.get("schema_energy")
SCHEMA_GOV = dbutils.widgets.get("schema_governance")
PT_EP      = dbutils.widgets.get("pt_endpoint")
VS_EP      = dbutils.widgets.get("vs_endpoint")

print(f"Catalog          : {CATALOG}")
print(f"Energy schema    : {CATALOG}.{SCHEMA_E}")
print(f"Governance schema: {CATALOG}.{SCHEMA_GOV}")
print(f"PT endpoint      : {PT_EP}")
print(f"VS endpoint      : {VS_EP}")
print()
print("Data is generated via SQL — no CSV upload required.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create catalog and schemas

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA_E}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA_GOV}")
print(f"✅ {CATALOG}.{SCHEMA_E} ready")
print(f"✅ {CATALOG}.{SCHEMA_GOV} ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Generate energy tables using SQL
# MAGIC
# MAGIC All six tables are generated entirely in-cluster using `SEQUENCE`, `RAND`, and `CASE` expressions.
# MAGIC No CSV files or DBFS uploads are required.

# COMMAND ----------

results = []

# ── energy_assets ────────────────────────────────────────────────────────────
try:
    fqn = f"{CATALOG}.{SCHEMA_E}.energy_assets"
    spark.sql(f"""
        CREATE OR REPLACE TABLE {fqn} AS
        SELECT
            CONCAT('AST-', LPAD(CAST(id AS STRING), 5, '0'))                     AS asset_id,
            CASE (id % 5)
                WHEN 0 THEN 'TRANSFORMER'
                WHEN 1 THEN 'LINE'
                WHEN 2 THEN 'SUBSTATION'
                WHEN 3 THEN 'SWITCH'
                ELSE        'METER'
            END                                                                   AS asset_type,
            CASE (id % 5)
                WHEN 0 THEN 'NSW'
                WHEN 1 THEN 'VIC'
                WHEN 2 THEN 'QLD'
                WHEN 3 THEN 'SA'
                ELSE        'TAS'
            END                                                                   AS region,
            CAST(10 + FLOOR(RAND(id)  * 91)  AS INT)                             AS condition_score,
            DATE_ADD('2015-01-01', CAST(FLOOR(RAND(id + 1) * 3650) AS INT))      AS installation_date,
            CONCAT('SUB-', LPAD(CAST((id % 20) AS STRING), 3, '0'))              AS substation_id,
            ROUND(11 + RAND(id + 2) * 121, 1)                                    AS voltage_kv,
            CASE WHEN RAND(id + 3) < 0.15 THEN true ELSE false END               AS is_critical
        FROM (SELECT EXPLODE(SEQUENCE(1, 100)) AS id)
    """)
    count = spark.table(fqn).count()
    results.append(("✅", "energy_assets", f"{count:,} rows"))
except Exception as e:
    results.append(("❌", "energy_assets", str(e)[:120]))

# ── meter_readings ────────────────────────────────────────────────────────────
try:
    fqn = f"{CATALOG}.{SCHEMA_E}.meter_readings"
    spark.sql(f"""
        CREATE OR REPLACE TABLE {fqn} AS
        SELECT
            CONCAT('NMI', LPAD(CAST(nmi_id AS STRING), 10, '0'))                    AS nmi,
            TIMESTAMP(DATE_ADD('2024-01-01', CAST(day_offset AS INT)))
                + MAKE_INTERVAL(0, 0, 0, 0, interval_num * 30, 0, 0)                AS reading_datetime,
            ROUND(0.5 + RAND(nmi_id * 1000 + day_offset * 48 + interval_num) * 4.5,
                  3)                                                                 AS interval_kwh,
            CASE WHEN RAND(nmi_id + day_offset + interval_num) < 0.03 THEN 'E'
                 WHEN RAND(nmi_id + day_offset + interval_num + 1) < 0.01 THEN 'S'
                 ELSE 'A'
            END                                                                      AS quality_flag,
            ROUND(220 + RAND(nmi_id + interval_num) * 20, 1)                        AS voltage_v,
            ROUND(0.95 + RAND(nmi_id + day_offset) * 0.04, 3)                       AS power_factor
        FROM (
            SELECT
                nmi.id  AS nmi_id,
                day.d   AS day_offset,
                ivl.i   AS interval_num
            FROM (SELECT EXPLODE(SEQUENCE(1, 50))  AS id)  nmi
            CROSS JOIN (SELECT EXPLODE(SEQUENCE(0, 6))   AS d)   day
            CROSS JOIN (SELECT EXPLODE(SEQUENCE(0, 47))  AS i)   ivl
        )
    """)
    count = spark.table(fqn).count()
    results.append(("✅", "meter_readings", f"{count:,} rows"))
except Exception as e:
    results.append(("❌", "meter_readings", str(e)[:120]))

# ── outage_events ─────────────────────────────────────────────────────────────
# NOTE: MAKE_INTERVAL returns a microsecond-resolution interval and cannot be added
# to a DATE. The TIMESTAMP() call converts the DATE to a timestamp first; the interval
# addition is then applied to the resulting TIMESTAMP value on the next line.
try:
    fqn = f"{CATALOG}.{SCHEMA_E}.outage_events"
    spark.sql(f"""
        CREATE OR REPLACE TABLE {fqn} AS
        SELECT
            CONCAT('EVT-', LPAD(CAST(id AS STRING), 6, '0'))            AS event_id,
            CONCAT('AST-', LPAD(CAST((id % 100 + 1) AS STRING), 5, '0')) AS asset_id,
            CASE (id % 2) WHEN 0 THEN 'PLANNED' ELSE 'UNPLANNED' END    AS event_type,
            CASE (id % 5)
                WHEN 0 THEN 'EQUIPMENT_FAILURE'
                WHEN 1 THEN 'WEATHER'
                WHEN 2 THEN 'VEGETATION'
                WHEN 3 THEN 'THIRD_PARTY'
                ELSE        'UNKNOWN'
            END                                                          AS cause_category,
            TIMESTAMP(DATE_ADD('2024-01-01', CAST(FLOOR(RAND(id) * 365) AS INT)))
                                                                         AS start_time,
            TIMESTAMP(DATE_ADD('2024-01-01', CAST(FLOOR(RAND(id) * 365) AS INT)))
                + MAKE_INTERVAL(0, 0, 0, 0, CAST(FLOOR(30 + RAND(id+1)*330) AS INT), 0, 0)
                                                                         AS end_time,
            CAST(10 + FLOOR(RAND(id + 2) * 590) AS INT)                 AS affected_customers,
            ROUND(1 + RAND(id + 3) * 119, 2)                            AS saidi_minutes,
            ROUND(0.0001 + RAND(id + 4) * 0.0099, 6)                    AS saifi_count,
            CASE (id % 5)
                WHEN 0 THEN 'NSW'
                WHEN 1 THEN 'VIC'
                WHEN 2 THEN 'QLD'
                WHEN 3 THEN 'SA'
                ELSE        'TAS'
            END                                                          AS region
        FROM (SELECT EXPLODE(SEQUENCE(1, 500)) AS id)
    """)
    count = spark.table(fqn).count()
    results.append(("✅", "outage_events", f"{count:,} rows"))
except Exception as e:
    results.append(("❌", "outage_events", str(e)[:120]))

# ── maintenance_work_orders ───────────────────────────────────────────────────
try:
    fqn = f"{CATALOG}.{SCHEMA_E}.maintenance_work_orders"
    spark.sql(f"""
        CREATE OR REPLACE TABLE {fqn} AS
        SELECT
            CONCAT('WO-', LPAD(CAST(id AS STRING), 7, '0'))             AS work_order_id,
            CONCAT('AST-', LPAD(CAST((id % 100 + 1) AS STRING), 5, '0')) AS asset_id,
            CASE (id % 5)
                WHEN 0 THEN 'INSPECTION'
                WHEN 1 THEN 'REPAIR'
                WHEN 2 THEN 'REPLACEMENT'
                WHEN 3 THEN 'UPGRADE'
                ELSE        'EMERGENCY'
            END                                                          AS work_type,
            CASE (id % 4)
                WHEN 0 THEN 'CRITICAL'
                WHEN 1 THEN 'HIGH'
                WHEN 2 THEN 'MEDIUM'
                ELSE        'LOW'
            END                                                          AS priority,
            DATE_ADD('2024-01-01', CAST(FLOOR(RAND(id) * 365) AS INT))  AS scheduled_date,
            DATE_ADD('2024-01-01',
                CAST(FLOOR(RAND(id) * 365) AS INT) + CAST(FLOOR(RAND(id+1)*7) AS INT))
                                                                         AS completed_date,
            ROUND(500 + RAND(id + 2) * 49500, 2)                        AS cost_aud,
            CASE (id % 3)
                WHEN 0 THEN 'COMPLETED'
                WHEN 1 THEN 'IN_PROGRESS'
                ELSE        'SCHEDULED'
            END                                                          AS status,
            CONCAT('CREW-', LPAD(CAST((id % 20 + 1) AS STRING), 2, '0')) AS assigned_crew
        FROM (SELECT EXPLODE(SEQUENCE(1, 500)) AS id)
    """)
    count = spark.table(fqn).count()
    results.append(("✅", "maintenance_work_orders", f"{count:,} rows"))
except Exception as e:
    results.append(("❌", "maintenance_work_orders", str(e)[:120]))

# ── regulatory_reports ────────────────────────────────────────────────────────
try:
    fqn = f"{CATALOG}.{SCHEMA_E}.regulatory_reports"
    spark.sql(f"""
        CREATE OR REPLACE TABLE {fqn} AS
        SELECT
            CONCAT('RPT-', LPAD(CAST(id AS STRING), 5, '0'))            AS report_id,
            CASE (id % 4)
                WHEN 0 THEN 'ANNUAL_SAIDI'
                WHEN 1 THEN 'RELIABILITY_ASSESSMENT'
                WHEN 2 THEN 'ASSET_CONDITION'
                ELSE        'INCIDENT_SUMMARY'
            END                                                          AS report_type,
            DATE_ADD('2020-01-01', CAST(FLOOR(RAND(id) * 1825) AS INT)) AS report_date,
            CASE (id % 4)
                WHEN 0 THEN 'AER'
                WHEN 1 THEN 'AEMC'
                WHEN 2 THEN 'AEMO'
                ELSE        'STATE_REGULATOR'
            END                                                          AS regulator,
            CASE (id % 5)
                WHEN 0 THEN 'NSW'
                WHEN 1 THEN 'VIC'
                WHEN 2 THEN 'QLD'
                WHEN 3 THEN 'SA'
                ELSE        'TAS'
            END                                                          AS region,
            CASE WHEN RAND(id + 1) < 0.85 THEN 'SUBMITTED'
                 WHEN RAND(id + 1) < 0.95 THEN 'UNDER_REVIEW'
                 ELSE 'OVERDUE'
            END                                                          AS status,
            ROUND(RAND(id + 2) * 10, 2)                                 AS saidi_reported,
            ROUND(RAND(id + 3), 4)                                       AS saifi_reported,
            CASE WHEN RAND(id + 4) < 0.9 THEN 'COMPLIANT' ELSE 'NON_COMPLIANT' END
                                                                         AS compliance_status
        FROM (SELECT EXPLODE(SEQUENCE(1, 100)) AS id)
    """)
    count = spark.table(fqn).count()
    results.append(("✅", "regulatory_reports", f"{count:,} rows"))
except Exception as e:
    results.append(("❌", "regulatory_reports", str(e)[:120]))

# ── policy_documents ──────────────────────────────────────────────────────────
try:
    fqn = f"{CATALOG}.{SCHEMA_E}.policy_documents"
    spark.sql(f"""
        CREATE OR REPLACE TABLE {fqn} AS
        SELECT
            CONCAT('POL-', LPAD(CAST(id AS STRING), 4, '0'))            AS policy_id,
            CASE (id % 6)
                WHEN 0 THEN 'Asset Management Policy'
                WHEN 1 THEN 'Outage Management Procedure'
                WHEN 2 THEN 'Safety Management System'
                WHEN 3 THEN 'Environmental Compliance Policy'
                WHEN 4 THEN 'Cybersecurity Framework'
                ELSE        'Customer Hardship Policy'
            END                                                          AS title,
            CASE (id % 3)
                WHEN 0 THEN 'OPERATIONAL'
                WHEN 1 THEN 'COMPLIANCE'
                ELSE        'SAFETY'
            END                                                          AS category,
            DATE_ADD('2020-01-01', CAST(FLOOR(RAND(id) * 1825) AS INT)) AS effective_date,
            DATE_ADD('2020-01-01',
                CAST(FLOOR(RAND(id) * 1825) AS INT) + 365)              AS review_date,
            CASE WHEN RAND(id + 1) < 0.8 THEN 'ACTIVE' ELSE 'UNDER_REVIEW' END
                                                                         AS status,
            CASE (id % 4)
                WHEN 0 THEN 'AER'
                WHEN 1 THEN 'AEMC'
                WHEN 2 THEN 'INTERNAL'
                ELSE        'STATE_REGULATOR'
            END                                                          AS governing_body,
            CONCAT('v', CAST(1 + (id % 5) AS STRING), '.', CAST(id % 10 AS STRING))
                                                                         AS version
        FROM (SELECT EXPLODE(SEQUENCE(1, 50)) AS id)
    """)
    count = spark.table(fqn).count()
    results.append(("✅", "policy_documents", f"{count:,} rows"))
except Exception as e:
    results.append(("❌", "policy_documents", str(e)[:120]))

print("Table generation results:")
for icon, tbl, msg in results:
    print(f"  {icon} {tbl}: {msg}")

# Expose table list for downstream cells
TABLES = [
    "energy_assets",
    "meter_readings",
    "outage_events",
    "maintenance_work_orders",
    "regulatory_reports",
    "policy_documents",
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Add column comments

# COMMAND ----------

COLUMN_COMMENTS = {
    f"{CATALOG}.{SCHEMA_E}.energy_assets": {
        "asset_id":       "Primary key. Unique identifier for each network asset (transformer, line, substation, switch, meter).",
        "asset_type":     "Asset class: TRANSFORMER, LINE, SUBSTATION, SWITCH, METER. Use exact values for filtering.",
        "region":         "Geographic region where the asset is installed (e.g. NSW, VIC, QLD, SA, TAS).",
        "condition_score":"Numeric health score 0-100. Score < 40 indicates poor condition and maintenance priority. Higher = better.",
    },
    f"{CATALOG}.{SCHEMA_E}.outage_events": {
        "event_id":           "Primary key. Unique identifier for the outage event.",
        "event_type":         "PLANNED or UNPLANNED. Planned outages are scheduled maintenance; unplanned are faults or failures.",
        "cause_category":     "Root cause category: EQUIPMENT_FAILURE, WEATHER, VEGETATION, THIRD_PARTY, UNKNOWN.",
        "saidi_minutes":      "System Average Interruption Duration Index contribution in minutes. Regulatory KPI — sum across events for total SAIDI.",
        "saifi_count":        "System Average Interruption Frequency Index contribution. Each event contributes affected_customers / total_customers.",
        "affected_customers": "Number of customers without power during this event.",
        "start_time":         "Outage start timestamp. Use DATE(start_time) to filter by day.",
        "end_time":           "Outage restoration timestamp. NULL if event is ongoing. Duration = end_time - start_time.",
    },
    f"{CATALOG}.{SCHEMA_E}.meter_readings": {
        "nmi":              "National Metering Identifier. Primary key for a customer connection point. Join to energy_assets on asset_id.",
        "reading_datetime": "Interval end timestamp. 30-minute intervals. AEST/AEDT timezone.",
        "interval_kwh":     "Energy consumed in this 30-minute interval in kWh. Multiply by 2 for kW average.",
        "quality_flag":     "Data quality indicator: A = Actual, E = Estimated, S = Substituted. Filter to quality_flag = A for clean data.",
    },
    f"{CATALOG}.{SCHEMA_E}.maintenance_work_orders": {
        "work_order_id": "Primary key. Unique identifier for the work order.",
        "asset_id":      "Foreign key to energy_assets.asset_id. Links the work order to the asset being maintained.",
        "work_type":     "Type of work: INSPECTION, REPAIR, REPLACEMENT, UPGRADE, EMERGENCY.",
        "priority":      "Work priority: CRITICAL, HIGH, MEDIUM, LOW. CRITICAL work orders should be completed within 24 hours.",
        "cost_aud":      "Estimated or actual cost of the work order in AUD.",
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
# MAGIC ## Step 4: Grant participant access
# MAGIC
# MAGIC Enter participant emails as a comma-separated list.
# MAGIC
# MAGIC Grants applied per user:
# MAGIC - `USE CATALOG` on `workshop_au`
# MAGIC - `USE SCHEMA` + `SELECT` on both `energy` and `ai_governance` schemas
# MAGIC - `CREATE TABLE` on `ai_governance` (required for AI Gateway payload logging labs)

# COMMAND ----------

dbutils.widgets.text("participant_emails", "", "Participant emails (comma-separated)")
raw_emails   = dbutils.widgets.get("participant_emails")
participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

if not participants:
    print("Enter participant emails in the widget above, then re-run this cell.")
else:
    print(f"Granting access to {len(participants)} participant(s):\n")

    grants = [
        f"GRANT USE CATALOG  ON CATALOG {CATALOG}              TO",
        f"GRANT USE SCHEMA   ON SCHEMA  {CATALOG}.{SCHEMA_E}   TO",
        f"GRANT SELECT       ON SCHEMA  {CATALOG}.{SCHEMA_E}   TO",
        f"GRANT USE SCHEMA   ON SCHEMA  {CATALOG}.{SCHEMA_GOV} TO",
        f"GRANT SELECT       ON SCHEMA  {CATALOG}.{SCHEMA_GOV} TO",
        f"GRANT CREATE TABLE ON SCHEMA  {CATALOG}.{SCHEMA_GOV} TO",
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
    print(f"  • Query all tables in {CATALOG}.{SCHEMA_E}")
    print(f"  • Read and write payload log tables in {CATALOG}.{SCHEMA_GOV}")
    print(f"  • Run all Session 1 labs")

# COMMAND ----------

# Verify grants
if participants:
    print(f"Current grants on {CATALOG}.{SCHEMA_E}:")
    display(spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.{SCHEMA_E}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Check endpoint availability
# MAGIC
# MAGIC Verifies that the pay-per-token serving endpoint and Vector Search endpoint named in the
# MAGIC widgets actually exist in this workspace. If either is missing, the step prints which
# MAGIC endpoints ARE available so you can either create the named endpoint or update the widget
# MAGIC defaults before running the labs.
# MAGIC
# MAGIC **AU East cross-Geo note:** Pay-per-token Foundation Model API endpoints marked with `*`
# MAGIC in the Databricks docs require cross-Geo processing to be enabled on the workspace.
# MAGIC This includes models such as Claude Haiku/Sonnet and Llama 3.3 70B Instruct.
# MAGIC If geography enforcement is active (Step 6), confirm with your account team that the
# MAGIC model you plan to use is available in-region before the workshop.

# COMMAND ----------

import requests

HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def _get_endpoint(path):
    """Return (ok, data_or_error_str) for a GET against the serving API."""
    resp = requests.get(f"https://{HOST}{path}", headers=HEADERS, timeout=15)
    if resp.status_code == 200:
        return True, resp.json()
    return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

# ── Pay-per-token serving endpoint ────────────────────────────────────────────
pt_ok, pt_data = _get_endpoint(f"/api/2.0/serving-endpoints/{PT_EP}")
if pt_ok:
    state = pt_data.get("state", {}).get("ready", "UNKNOWN")
    print(f"✅ PT endpoint '{PT_EP}' found — state: {state}")
else:
    print(f"⚠️  PT endpoint '{PT_EP}' not found: {pt_data}")
    print()
    # List available serving endpoints to help the admin pick one
    list_ok, list_data = _get_endpoint("/api/2.0/serving-endpoints")
    if list_ok:
        endpoints = list_data.get("endpoints", [])
        print(f"   Available serving endpoints in this workspace ({len(endpoints)} total):")
        for ep in endpoints:
            state = ep.get("state", {}).get("ready", "?")
            print(f"     • {ep['name']} [{state}]")
    print()
    print("   ACTION REQUIRED: Either —")
    print(f"     (a) Create a serving endpoint named '{PT_EP}' pointing to a foundation model, OR")
    print(f"     (b) Update the 'pt_endpoint' widget to match an existing endpoint name above.")
    print("   Labs that reference this endpoint by name will fail until this is resolved.")

print()

# ── Vector Search endpoint ────────────────────────────────────────────────────
vs_ok, vs_data = _get_endpoint(f"/api/2.0/vector-search/endpoints/{VS_EP}")
if vs_ok:
    state = vs_data.get("endpoint_status", {}).get("state", "UNKNOWN")
    print(f"✅ VS endpoint '{VS_EP}' found — state: {state}")
else:
    print(f"⚠️  VS endpoint '{VS_EP}' not found: {vs_data}")
    print()
    list_ok, list_data = _get_endpoint("/api/2.0/vector-search/endpoints")
    if list_ok:
        vs_eps = list_data.get("endpoints", [])
        print(f"   Available Vector Search endpoints in this workspace ({len(vs_eps)} total):")
        for ep in vs_eps:
            state = ep.get("endpoint_status", {}).get("state", "?")
            print(f"     • {ep['name']} [{state}]")
    print()
    print("   ACTION REQUIRED: Either —")
    print(f"     (a) Create a Vector Search endpoint named '{VS_EP}', OR")
    print(f"     (b) Update the 'vs_endpoint' widget to match an existing endpoint name above.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Check geography enforcement

# COMMAND ----------

# NOTE: Geography enforcement does not have a single reliable public API path across all
# workspace tiers. This step uses the typed settings API path for a quick pre-workshop
# smoke test. The labs use different approaches:
#
#   setup.py (here):  typed settings API — enforce_workspace_feature_on_network_setting
#                     May return 404 or RESOURCE_DOES_NOT_EXIST on some workspace tiers.
#                     Handled below — a 404 here does not block the labs.
#
#   Lab 01:           No API call. Documents that there is no confirmed public REST API to
#                     read or set the geography enforcement toggle. Directs admins to verify
#                     via Account Console → Workspaces → Security and compliance tab.
#                     Audit evidence is available via system.access.audit
#                     (action_name = 'updateWorkspaceConfiguration').
#
#   Lab 05:           workspace conf key — enableDataProcessingWithinGeography
#                     Attempted via workspace_conf.get_status() — valid on some workspace
#                     tiers, returns BadRequest on others. Falls back to CANNOT_VERIFY
#                     with a clear message to verify via Account Console UI.
#
# If this path returns 404 or RESOURCE_DOES_NOT_EXIST, verify the setting manually in the UI
# and proceed — it does not block the labs from running.
setting_url = (
    f"https://{HOST}/api/2.0/settings/types/"
    f"enforce_workspace_feature_on_network_setting/names/default"
)

try:
    resp = requests.get(setting_url, headers=HEADERS, timeout=10)
    if resp.status_code == 200:
        data     = resp.json()
        enabled  = data.get("enforce_workspace_feature_on_network_setting", {}).get("enforce_workspace_feature_on_network", False)
        icon     = "✅" if enabled else "⚠️ "
        status   = "ENABLED" if enabled else "NOT ENABLED"
        print(f"{icon} Geography enforcement: {status}")
        if not enabled:
            print()
            print("  WARN: Geography enforcement is not active on this workspace.")
            print("  For AU data residency labs, enable it under:")
            print("  Admin Console → Security → Network → Enforce geography")
    elif resp.status_code == 404:
        print("⚠️  Geography enforcement setting not found.")
        print("   This API path may not be available in this region or workspace tier.")
        print("   Check Admin Console → Security → Network to verify the setting manually.")
    else:
        print(f"⚠️  Could not retrieve geography setting: HTTP {resp.status_code}")
        print(f"    {resp.text[:200]}")
except Exception as e:
    print(f"⚠️  Request failed: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7: Smoke test — row counts

# COMMAND ----------

EXPECTED_MIN_ROWS = {
    "energy_assets":           50,
    "meter_readings":       5_000,
    "outage_events":          200,
    "maintenance_work_orders":200,
    "regulatory_reports":      50,
    "policy_documents":        20,
}

print("Table row counts:")
all_ok = True

for table_name, min_rows in EXPECTED_MIN_ROWS.items():
    fqn = f"{CATALOG}.{SCHEMA_E}.{table_name}"
    try:
        count = spark.table(fqn).count()
        ok    = count >= min_rows
        icon  = "✅" if ok else "⚠️ "
        print(f"  {icon} {table_name}: {count:,} rows (min expected: {min_rows:,})")
        if not ok:
            all_ok = False
    except Exception as e:
        print(f"  ❌ {table_name}: {e}")
        all_ok = False

print()
if all_ok:
    print("✅ All tables loaded. Ready for Session 1 labs.")
    print()
    print("Next steps:")
    print("  1. Share the catalog/schema names with participants")
    print("  2. Open Lab 01: session1_platform_admin/labs/01_workspace_ai_settings.py")
    print(f"  3. Confirm endpoint names: PT={PT_EP}, VS={VS_EP}")
    if not pt_ok or not vs_ok:
        print()
        print("  ⚠️  One or both endpoints were not found (see Step 5 above).")
        print("     Resolve endpoint names before participants run Labs 02–04.")
else:
    print("⚠️  One or more tables are below the expected row count.")
    print("   Re-run Step 2 to regenerate the synthetic data.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What this notebook does NOT do
# MAGIC
# MAGIC The following are handled by the labs — do not add them here:
# MAGIC
# MAGIC - Workspace AI settings, geography enforcement, UC grants for AI assets → **Lab 01**
# MAGIC - AI Gateway configuration (route creation, rate limits, guardrails) → **Lab 02**
# MAGIC - Rate limit tuning and AU PII guardrail testing → **Lab 03**
# MAGIC - Usage tracking, cost attribution, and system table queries → **Lab 04**
# MAGIC - Compliance evidence collection and audit log export → **Lab 05**
