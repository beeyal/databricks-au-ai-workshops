# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Session 1 — Platform Admin Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Pre-requisite — run this BEFORE the Session 1 labs</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 1.**
# MAGIC It creates the catalog and schemas, loads the energy sample data into Unity Catalog,
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

DATA_PATH  = "dbfs:/tmp/au_workshop/sample_data"

print(f"Catalog          : {CATALOG}")
print(f"Energy schema    : {CATALOG}.{SCHEMA_E}")
print(f"Governance schema: {CATALOG}.{SCHEMA_GOV}")
print(f"PT endpoint      : {PT_EP}")
print(f"VS endpoint      : {VS_EP}")
print(f"CSV source       : {DATA_PATH}/")
print()
print("Upload CSVs first if not already on DBFS:")
print(f"  databricks fs cp -r ./data/sample_data/ {DATA_PATH}/")

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
# MAGIC ## Step 2: Load energy tables from CSV

# COMMAND ----------

# Table name → csv filename (all under DATA_PATH/)
TABLES = [
    "energy_assets",
    "meter_readings",
    "outage_events",
    "maintenance_work_orders",
    "regulatory_reports",
    "policy_documents",
]

results = []
for table_name in TABLES:
    fqn  = f"{CATALOG}.{SCHEMA_E}.{table_name}"
    path = f"{DATA_PATH}/{table_name}.csv"
    try:
        df = (spark.read.format("csv")
              .option("header", "true")
              .option("inferSchema", "true")
              .load(path))

        (df.write
           .format("delta")
           .mode("overwrite")
           .option("overwriteSchema", "true")
           .saveAsTable(fqn))

        count = spark.table(fqn).count()
        results.append(("✅", table_name, f"{count:,} rows"))
    except Exception as e:
        results.append(("❌", table_name, str(e)[:120]))

for icon, tbl, msg in results:
    print(f"{icon} {tbl}: {msg}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Add column comments

# COMMAND ----------

COLUMN_COMMENTS = {
    f"{CATALOG}.{SCHEMA_E}.energy_assets": {
        "asset_id":       "Primary key. Unique identifier for each network asset (transformer, line, substation, switch, meter).",
        "asset_type":     "Asset class: TRANSFORMER, LINE, SUBSTATION, SWITCH, METER. Use exact values for filtering.",
        "region":         "Geographic region where the asset is installed (e.g. NSW, VIC, QLD, SA, TAS).",
        "condition_score":"Numeric health score 0–100. Score < 40 indicates poor condition and maintenance priority. Higher = better.",
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
        "quality_flag":     "Data quality indicator: A = Actual, E = Estimated, S = Substituted. Filter to quality_flag = ''A'' for clean data.",
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
            spark.sql(f"ALTER TABLE {table_fqn} ALTER COLUMN `{col}` COMMENT '{comment}'")
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
# MAGIC ## Step 5: Check geography enforcement

# COMMAND ----------

import requests

HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

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
        print("⚠️  Geography enforcement setting not found (feature may not be available in this region/tier).")
    else:
        print(f"⚠️  Could not retrieve geography setting: HTTP {resp.status_code}")
        print(f"    {resp.text[:200]}")
except Exception as e:
    print(f"⚠️  Request failed: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Smoke test — row counts

# COMMAND ----------

print("Table row counts:")
all_ok = True

for table_name in TABLES:
    fqn = f"{CATALOG}.{SCHEMA_E}.{table_name}"
    try:
        count = spark.table(fqn).count()
        icon  = "✅" if count > 0 else "⚠️ "
        print(f"  {icon} {table_name}: {count:,} rows")
        if count == 0:
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
else:
    print("⚠️  One or more tables are empty or missing.")
    print(f"   Upload CSVs to {DATA_PATH}/ and re-run Step 2.")

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
