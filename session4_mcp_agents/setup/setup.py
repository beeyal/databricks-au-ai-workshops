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

ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST  = ctx.apiUrl().get().replace("https://", "")
TOKEN = ctx.apiToken().get()

print(f"Catalog    : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint: {PT_ENDPOINT}")
print(f"VS endpoint: {VS_ENDPOINT}")
print(f"Data path  : {DATA_PATH}")
print()
print("Upload AEMO CSVs to DBFS first if not already there:")
print(f"  databricks fs cp -r ./data/sample_data/aemo/ {DATA_PATH}/")

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
        df = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "true")
            .option("multiLine", "true")
            .option("escape", '"')
            .csv(path)
        )
        row_count = df.count()

        writer = (
            df.write
            .format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .option("delta.enableChangeDataFeed", "true")
        )
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
    url     = f"https://{host}/api/2.0/serving-endpoints/{endpoint_name}"
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
    state = data.get("state", {}).get("ready", "UNKNOWN")
    model = None
    try:
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
        print(f"   Check: https://{host}/ml/endpoints/{endpoint_name}")


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
participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

if not participants:
    print("No participant emails provided — skipping grants.")
    print("Enter emails in the 'participant_emails' widget and re-run this cell.")
else:
    print(f"Granting access to {len(participants)} participant(s):\n")

    grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
        f"GRANT CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
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
# MAGIC ## Step 6: Smoke test — verify row counts

# COMMAND ----------

print("Table row counts:")
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

uc_mcp_url    = f"https://{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"
genie_mcp_url = (
    f"https://{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
    if GENIE_SPACE_ID
    else f"https://{HOST}/api/2.0/mcp/genie/<SPACE_ID>"
)

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
print(f"  Authentication for both:")
print(f"    Header: Authorization: Bearer <personal-access-token>")
print(f"    PAT:    User Settings → Developer → Access tokens → Generate new token")
print()
print(f"  Workspace:  https://{HOST}")
print(f"  PT endpoint: https://{HOST}/ml/endpoints/{PT_ENDPOINT}")
print()
print("=" * 70)
print("  Session 4 setup complete. Ready for labs.")
print("=" * 70)
