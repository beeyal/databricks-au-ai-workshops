# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">🗑️ Session 2 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything created during Session 2. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes:**
# MAGIC - AEMO Delta tables (`workshop_au.aemo.*`)
# MAGIC - The `aemo` schema
# MAGIC - Genie Spaces created during the labs (by Space ID)
# MAGIC - Space registry table (`workshop_au.ai_governance.genie_space_registry`)
# MAGIC - UC permission grants on the schema
# MAGIC
# MAGIC **What this does NOT remove:**
# MAGIC - The `workshop_au` catalog (may be shared with other workshops)
# MAGIC - The `ai_governance` schema itself
# MAGIC - Any Genie Spaces not listed in the Space IDs widget
# MAGIC
# MAGIC ⚠️ **`dry_run = true` by default** — prints what would be deleted without doing anything.
# MAGIC Set to `false` to actually delete.

# COMMAND ----------

dbutils.widgets.text("catalog",      "workshop_au",  "Catalog")
dbutils.widgets.text("schema",       "aemo",         "Schema to drop")
dbutils.widgets.text("schema_gov",   "ai_governance","Governance schema")
dbutils.widgets.text("space_ids",    "",             "Genie Space IDs to delete (comma-separated)")
dbutils.widgets.dropdown("dry_run",  "true", ["true", "false"], "Dry run (true = preview only)")

CATALOG    = dbutils.widgets.get("catalog")
SCHEMA     = dbutils.widgets.get("schema")
SCHEMA_GOV = dbutils.widgets.get("schema_gov")
DRY_RUN    = dbutils.widgets.get("dry_run") == "true"
raw_ids    = dbutils.widgets.get("space_ids")
SPACE_IDS  = [s.strip() for s in raw_ids.split(",") if s.strip()]

HOST   = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN  = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

mode = "DRY RUN — nothing will be deleted" if DRY_RUN else "LIVE — deletions will happen"
print(f"Mode    : {mode}")
print(f"Catalog : {CATALOG}.{SCHEMA}")
print(f"Spaces  : {SPACE_IDS or '(none provided)'}")
if DRY_RUN:
    print("\n⚠️  Change dry_run widget to 'false' to actually delete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Drop AEMO schema and tables

# COMMAND ----------

import pyspark.sql.utils

def do(label, fn):
    if DRY_RUN:
        print(f"  [DRY RUN] Would: {label}")
    else:
        try:
            fn()
            print(f"  ✅ {label}")
        except Exception as e:
            print(f"  ⚠️  {label}: {e}")

# List tables that will be dropped
print(f"Tables in {CATALOG}.{SCHEMA}:")
try:
    tables = [r.tableName for r in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()]
    for t in tables:
        print(f"  • {CATALOG}.{SCHEMA}.{t}")
except:
    tables = []
    print("  (schema not found or already empty)")

print()

# Drop tables individually first (cleaner than CASCADE for audit purposes)
for t in tables:
    fqn = f"{CATALOG}.{SCHEMA}.{t}"
    do(f"DROP TABLE {fqn}", lambda f=fqn: spark.sql(f"DROP TABLE IF EXISTS {f}"))

# Drop schema
do(
    f"DROP SCHEMA {CATALOG}.{SCHEMA}",
    lambda: spark.sql(f"DROP SCHEMA IF EXISTS {CATALOG}.{SCHEMA} CASCADE")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Delete Genie Spaces

# COMMAND ----------

import requests

if not SPACE_IDS:
    print("No Space IDs provided — skipping Genie Space deletion.")
    print("To delete spaces, enter their IDs in the 'space_ids' widget (comma-separated).")
    print("Find Space IDs in the browser URL when you open a space: .../genie/spaces/{id}")
else:
    for sid in SPACE_IDS:
        # First get the space name so we know what we're deleting
        info = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{sid}", headers=HEADERS)
        name = info.json().get("title", sid) if info.status_code == 200 else sid

        if DRY_RUN:
            print(f"  [DRY RUN] Would delete Genie Space: '{name}' ({sid})")
        else:
            resp = requests.delete(f"https://{HOST}/api/2.0/genie/spaces/{sid}", headers=HEADERS)
            if resp.status_code in (200, 204):
                print(f"  ✅ Deleted Genie Space: '{name}' ({sid})")
            else:
                print(f"  ⚠️  Could not delete '{name}' ({sid}): {resp.status_code} {resp.text[:100]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Clean up space registry

# COMMAND ----------

registry_fqn = f"{CATALOG}.{SCHEMA_GOV}.genie_space_registry"

try:
    exists = spark.catalog.tableExists(registry_fqn)
except:
    exists = False

if exists:
    if SPACE_IDS:
        ids_list = ", ".join(f"'{s}'" for s in SPACE_IDS)
        do(
            f"Delete {len(SPACE_IDS)} rows from {registry_fqn}",
            lambda: spark.sql(f"DELETE FROM {registry_fqn} WHERE space_id IN ({ids_list})")
        )
        if not DRY_RUN:
            remaining = spark.table(registry_fqn).count()
            print(f"  Registry now has {remaining} entries")
    else:
        print(f"  No Space IDs provided — registry not modified")
        print(f"  To clear all entries: spark.sql(\"TRUNCATE TABLE {registry_fqn}\")")
else:
    print(f"  Registry table not found — nothing to clean up")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Revoke UC permissions
# MAGIC
# MAGIC Revokes the grants applied in `aemo_space_config.py` Step 6.

# COMMAND ----------

dbutils.widgets.text("revoke_emails", "", "Emails to revoke (comma-separated, leave blank to skip)")
raw_revoke = dbutils.widgets.get("revoke_emails")
revoke_list = [e.strip().lower() for e in raw_revoke.split(",") if e.strip()]

if not revoke_list:
    print("No emails provided — skipping permission revocation.")
    print("Enter emails in the 'revoke_emails' widget to revoke access.")
else:
    revoke_stmts = [
        f"REVOKE SELECT ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} FROM",
    ]
    for email in revoke_list:
        for stmt_prefix in revoke_stmts:
            stmt = f"{stmt_prefix} `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))
        print(f"  {'[DRY RUN] Would revoke' if DRY_RUN else '✅ Revoked'}: {email}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Summary

# COMMAND ----------

print("=" * 55)
print(f"  Cleanup {'preview' if DRY_RUN else 'complete'}")
print("=" * 55)
print()

if DRY_RUN:
    print("Nothing was deleted. To run for real:")
    print("  1. Set 'dry_run' widget to 'false'")
    print("  2. Re-run all cells")
else:
    print("Removed:")
    print(f"  • AEMO tables in {CATALOG}.{SCHEMA}")
    print(f"  • Schema {CATALOG}.{SCHEMA}")
    if SPACE_IDS:
        print(f"  • {len(SPACE_IDS)} Genie Space(s)")
    if revoke_list:
        print(f"  • UC grants for {len(revoke_list)} user(s)")
    print()
    print("Not removed (shared resources):")
    print(f"  • Catalog {CATALOG}")
    print(f"  • Schema {CATALOG}.{SCHEMA_GOV}")
    print(f"  • Any Genie Spaces not listed in the widget")
