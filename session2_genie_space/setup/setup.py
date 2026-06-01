# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">AEMO Data Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2 pre-requisite — run this BEFORE the labs</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 2.**
# MAGIC It loads the AEMO sample data into Unity Catalog and adds column comments.
# MAGIC The labs will create the Genie Space.
# MAGIC
# MAGIC Expected runtime: ~5 minutes

# COMMAND ----------

dbutils.widgets.text("catalog",      "workshop_au",             "Catalog")
dbutils.widgets.text("schema",       "aemo",                    "Schema")
dbutils.widgets.text("data_path",    "dbfs:/tmp/au_workshop/sample_data/aemo", "DBFS path to AEMO CSVs")

CATALOG   = dbutils.widgets.get("catalog")
SCHEMA    = dbutils.widgets.get("schema")
DATA_PATH = dbutils.widgets.get("data_path")

print(f"Catalog : {CATALOG}.{SCHEMA}")
print(f"Data    : {DATA_PATH}")
print()
print("Upload CSVs first if not already on DBFS:")
print(f"  databricks fs cp -r ./data/sample_data/aemo/ {DATA_PATH}/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create catalog and schema

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ {CATALOG}.{SCHEMA} ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Load AEMO tables from CSV

# COMMAND ----------

# Table definitions: name → (csv_filename, partition_columns)
TABLES = {
    "spot_prices":            ("spot_prices.csv",            ["region_id"]),
    "dispatch_intervals":     ("dispatch_intervals.csv",      ["region_id", "fuel_type"]),
    "market_notices":         ("market_notices.csv",          []),
    "generator_registration": ("generator_registration.csv",  ["region_id"]),
    "settlement_amounts":     ("settlement_amounts.csv",       ["run_type"]),
}

results = []
for table_name, (csv_file, partitions) in TABLES.items():
    fqn  = f"{CATALOG}.{SCHEMA}.{table_name}"
    path = f"{DATA_PATH}/{csv_file}"
    try:
        # Read CSV
        df = (spark.read.format("csv")
              .option("header", "true")
              .option("inferSchema", "true")
              .load(path))

        # Write as Delta — overwrite so this is safe to re-run
        writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        if partitions:
            writer = writer.partitionBy(*partitions)
        writer.saveAsTable(fqn)

        count = spark.table(fqn).count()
        results.append(("✅", table_name, f"{count:,} rows"))
    except Exception as e:
        results.append(("❌", table_name, str(e)[:120]))

for icon, tbl, msg in results:
    print(f"{icon} {tbl}: {msg}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Add column comments (all tables)

# COMMAND ----------

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
        "duid":            "Dispatchable Unit Identifier. Join to generator_registration.duid for station_name and fuel_type.",
        "dispatch_mw":     "Actual MW dispatched in this 5-minute interval. SUM(dispatch_mw)/12 = MWh.",
        "initial_mw":      "Initial MW target at interval start.",
        "available_mw":    "MW available for dispatch.",
        "ramp_rate":       "Maximum ramp rate in MW per minute.",
        "fuel_type":       "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "station_name":    "Human-readable station name e.g. Bayswater, Loy Yang A.",
        "state":           "Australian state the unit is located in.",
    },
    f"{CATALOG}.{SCHEMA}.market_notices": {
        "notice_id":     "Unique identifier for the market notice.",
        "notice_type":   "LOR1 = reserve watch. LOR2 = shortfall threatened. LOR3 = imminent critical shortage. Use LIKE 'LOR%' to match all LOR types.",
        "issue_time":    "When AEMO published the notice. Use to filter recent events.",
        "reason":        "Free-text description. Use SUBSTRING(reason, 1, 200) for summaries.",
        "effective_date":"When the notice takes effect.",
        "region_id":     "NEM region. NULL means NEM-wide notice.",
        "intervention":  "True if this is an AEMO market intervention.",
    },
    f"{CATALOG}.{SCHEMA}.generator_registration": {
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
    f"{CATALOG}.{SCHEMA}.settlement_amounts": {
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
# MAGIC ## Step 4: Add table descriptions

# COMMAND ----------

TABLE_DESCRIPTIONS = {
    f"{CATALOG}.{SCHEMA}.spot_prices":            "NEM 30-minute trading interval spot prices. Key column: rrp = Regional Reference Price in $/MWh. Regions: NSW1, VIC1, QLD1, SA1, TAS1.",
    f"{CATALOG}.{SCHEMA}.dispatch_intervals":     "NEM 5-minute generator dispatch data. Key columns: duid (join to generator_registration), dispatch_mw (divide by 12 for MWh), fuel_type. 12 intervals = 1 hour.",
    f"{CATALOG}.{SCHEMA}.market_notices":         "AEMO market and system notices including LOR events. Filter: WHERE notice_type LIKE 'LOR%' for LOR events. LOR1/LOR2/LOR3 = escalating reserve severity.",
    f"{CATALOG}.{SCHEMA}.generator_registration": "NEM registered generator details. Join to dispatch_intervals on duid to get station_name and fuel_type.",
    f"{CATALOG}.{SCHEMA}.settlement_amounts":     "Weekly NEM settlement amounts by participant. run_type: FINAL = confirmed, PRELIMINARY = estimate. total_aud = net amount.",
}

for fqn, desc in TABLE_DESCRIPTIONS.items():
    try:
        spark.sql(f"COMMENT ON TABLE {fqn} IS '{desc}'")
        print(f"✅ {fqn.split('.')[-1]}")
    except Exception as e:
        print(f"❌ {fqn.split('.')[-1]}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Smoke test — verify row counts and sample data

# COMMAND ----------

print("Table row counts:")
all_ok = True
expected = {
    "spot_prices":            1_000,
    "dispatch_intervals":     5_000,
    "market_notices":           100,
    "generator_registration":    50,
    "settlement_amounts":        100,
}
for tbl, min_rows in expected.items():
    try:
        count = spark.table(f"{CATALOG}.{SCHEMA}.{tbl}").count()
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
    print("✅ All tables loaded. Ready for Session 2 labs.")
    print()
    print("Next steps:")
    print("  1. Open Lab 01: session2_genie_space/labs/01_genie_space_setup.py")
    print("  2. Run Step 1 (column comments) — already done here, will be a no-op")
    print("  3. Create the Genie Space via UI and paste the Space ID into the widget")
else:
    print("⚠️  Some tables are empty or missing.")
    print(f"   Upload CSVs to {DATA_PATH}/ and re-run this notebook.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What this notebook does NOT do
# MAGIC
# MAGIC The following are handled by the labs — do not add them here:
# MAGIC
# MAGIC - ❌ Create the Genie Space → **Lab 01** (participants do this in the UI)
# MAGIC - ❌ Add golden queries → **Lab 02** (automated upload script)
# MAGIC - ❌ Add text instructions → **Lab 02**
# MAGIC - ❌ Add benchmarks → **Lab 02**
# MAGIC - ❌ Set permissions → **Lab 05**

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6: Grant participant access
# MAGIC
# MAGIC Enter participant emails as a comma-separated list. The script grants:
# MAGIC - `USE CATALOG` + `USE SCHEMA` + `SELECT` on the AEMO schema (so Genie can query tables)
# MAGIC - `CREATE` permission on the schema (so participants can create their own Genie Spaces)

# COMMAND ----------

dbutils.widgets.text("participant_emails", "", "Participant emails (comma-separated)")
raw_emails = dbutils.widgets.get("participant_emails")

participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

if not participants:
    print("Enter participant emails in the widget above, then re-run this cell.")
else:
    print(f"Granting access to {len(participants)} participants:\n")

    grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} TO",  # needed to create Genie Space assets
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
    print(f"  • Query all tables in {CATALOG}.{SCHEMA}")
    print(f"  • Create Genie Spaces backed by those tables")
    print(f"  • Run Lab 01–05")

# COMMAND ----------

# Verify grants were applied
if participants:
    print(f"Current grants on {CATALOG}.{SCHEMA}:")
    display(spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.{SCHEMA}"))

