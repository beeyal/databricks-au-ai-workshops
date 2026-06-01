# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Session 6 — AI Ideation Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Pre-requisite — run this BEFORE the session</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook once as a workspace admin before Session 6.**
# MAGIC
# MAGIC Session 6 shares the AEMO data and Genie Space built in Session 2.
# MAGIC This setup only grants participant access — it does not load data.
# MAGIC
# MAGIC > **Before running this notebook:** Run `session2_genie_space/setup/setup.py` first to load
# MAGIC > AEMO data if not done already. This session uses the same Genie Space built in Session 2.
# MAGIC
# MAGIC Expected runtime: ~2 minutes

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Configure widgets

# COMMAND ----------

dbutils.widgets.text("catalog",           "workshop_au",  "Catalog")
dbutils.widgets.text("schema_aemo",       "aemo",         "AEMO schema")
dbutils.widgets.text("participant_emails", "",             "Participant emails (comma-separated)")

CATALOG       = dbutils.widgets.get("catalog")
SCHEMA_AEMO   = dbutils.widgets.get("schema_aemo")
raw_emails    = dbutils.widgets.get("participant_emails")

participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

print(f"Catalog : {CATALOG}.{SCHEMA_AEMO}")
print(f"Participants: {len(participants)} email(s) provided")
print()
print("NOTE: Run session2_genie_space/setup/setup.py first to load AEMO data")
print("if not done already. This session uses the same Genie Space built in Session 2.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Verify AEMO tables exist (Session 2 prerequisite check)

# COMMAND ----------

REQUIRED_TABLES = [
    "spot_prices",
    "dispatch_intervals",
    "market_notices",
    "generator_registration",
    "settlement_amounts",
]

print(f"Checking {CATALOG}.{SCHEMA_AEMO} tables:\n")
all_present = True
for tbl in REQUIRED_TABLES:
    fqn = f"{CATALOG}.{SCHEMA_AEMO}.{tbl}"
    try:
        count = spark.table(fqn).count()
        print(f"  OK  {tbl}: {count:,} rows")
    except Exception as e:
        print(f"  MISSING  {tbl}: {e}")
        all_present = False

print()
if not all_present:
    print("One or more AEMO tables are missing.")
    print("Run session2_genie_space/setup/setup.py first, then re-run this notebook.")
    dbutils.notebook.exit("MISSING_TABLES")
else:
    print("All AEMO tables present. Proceeding to grant participant access.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Grant participant access

# COMMAND ----------

if not participants:
    print("No participant emails provided.")
    print("Enter comma-separated emails in the 'participant_emails' widget and re-run.")
else:
    print(f"Granting access to {len(participants)} participant(s):\n")

    grant_statements = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA_AEMO} TO",
    ]

    ok = err = 0
    for email in participants:
        for grant_prefix in grant_statements:
            stmt = f"{grant_prefix} `{email}`"
            try:
                spark.sql(stmt)
                ok += 1
            except Exception as e:
                print(f"  WARN  {email}: {e}")
                err += 1
        print(f"  OK  {email}")

    print(f"\n{ok} grants applied ({err} errors)")
    print()
    print("Participants can now:")
    print(f"  - Query all tables in {CATALOG}.{SCHEMA_AEMO}")
    print(f"  - Use the AEMO Genie Space built in Session 2")
    print()
    print("Genie Space access must be granted separately via the Genie Space")
    print("permissions panel — add participants with 'Can Use' access.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Smoke test

# COMMAND ----------

print("Smoke test — verifying participant query path:\n")

try:
    sample = spark.sql(f"""
        SELECT region_id, AVG(rrp) AS avg_rrp
        FROM {CATALOG}.{SCHEMA_AEMO}.spot_prices
        GROUP BY region_id
        ORDER BY region_id
        LIMIT 5
    """).collect()

    for row in sample:
        print(f"  {row.region_id}: avg RRP ${row.avg_rrp:.2f}/MWh")

    print()
    print("Smoke test passed. Session 6 is ready.")
    print()
    print("Next steps:")
    print("  1. Grant Genie Space 'Can Use' access to participants via the UI")
    print("  2. Verify 5 test questions in the Genie Space before participants arrive")
    print("  3. Print or share activities/01_use_case_canvas.md (one per participant)")
    print("  4. Share activities/02_question_starter_library.md on screen or via email")

except Exception as e:
    print(f"Smoke test failed: {e}")
    print("Check that session2_genie_space/setup/setup.py has been run successfully.")
