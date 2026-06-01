# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">Session 5 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything created during Session 5. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes:**
# MAGIC - 3 UC functions (`calculate_peak_demand`, `get_outage_summary`, `lookup_asset_status`)
# MAGIC - UC `EXECUTE` grants on those functions
# MAGIC - Energy Delta tables (`workshop_au.energy.*`)
# MAGIC - The `energy` schema
# MAGIC - Regulatory reports table in `workshop_au.audit` (if only Session 5 used it)
# MAGIC
# MAGIC **What this does NOT remove:**
# MAGIC - The `workshop_au` catalog (shared)
# MAGIC - The `audit` or `ai_governance` schemas (shared with Session 1)
# MAGIC - Skills files that participants created locally (personal workspace files)
# MAGIC
# MAGIC ⚠️ **`dry_run = true` by default** — prints what would be deleted without doing anything.
# MAGIC Set to `false` to actually delete.

# COMMAND ----------

dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",       "workshop_au",  "Catalog")
dbutils.widgets.text("schema",        "energy",       "Energy schema to drop")
dbutils.widgets.text("revoke_emails", "",             "Emails to revoke (comma-separated)")
dbutils.widgets.dropdown("dry_run",   "true", ["true", "false"], "Dry run (true = preview only)")

CATALOG  = dbutils.widgets.get("catalog")
SCHEMA   = dbutils.widgets.get("schema")
DRY_RUN  = dbutils.widgets.get("dry_run") == "true"

mode = "DRY RUN — nothing will be deleted" if DRY_RUN else "LIVE — deletions will happen"
print(f"Mode    : {mode}")
print(f"Catalog : {CATALOG}.{SCHEMA}")
if DRY_RUN:
    print("\n⚠️  Change dry_run widget to 'false' to actually delete.")

# COMMAND ----------

def do(label: str, fn) -> None:
    """Execute fn, or print what would happen in dry-run mode."""
    if DRY_RUN:
        print(f"  [DRY RUN] Would: {label}")
    else:
        try:
            fn()
            print(f"  ✅ {label}")
        except Exception as e:
            print(f"  ⚠️  {label}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Revoke UC grants

# COMMAND ----------

raw_revoke  = dbutils.widgets.get("revoke_emails")
revoke_list = [e.strip().lower() for e in raw_revoke.split(",") if e.strip()]

FUNCTIONS = [
    f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
    f"{CATALOG}.{SCHEMA}.get_outage_summary",
    f"{CATALOG}.{SCHEMA}.lookup_asset_status",
]

if not revoke_list:
    print("No emails provided — skipping permission revocation.")
    print("Enter emails in the 'revoke_emails' widget to revoke access.")
else:
    schema_revokes = [
        f"REVOKE SELECT ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE SELECT ON SCHEMA {CATALOG}.audit FROM",
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.audit FROM",
    ]

    for email in revoke_list:
        for stmt_prefix in schema_revokes:
            stmt = f"{stmt_prefix} `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))

        for fn_fqn in FUNCTIONS:
            stmt = f"REVOKE EXECUTE ON FUNCTION {fn_fqn} FROM `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))

        print(f"  {'[DRY RUN] Would revoke' if DRY_RUN else '✅ Revoked'}: {email}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Drop UC functions

# COMMAND ----------

print(f"UC functions to drop in {CATALOG}.{SCHEMA}:")
for fn in FUNCTIONS:
    print(f"  • {fn}")
print()

for fn_fqn in FUNCTIONS:
    do(
        f"DROP FUNCTION {fn_fqn}",
        lambda f=fn_fqn: spark.sql(f"DROP FUNCTION IF EXISTS {f}"),
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Drop energy schema and tables

# COMMAND ----------

print(f"Tables in {CATALOG}.{SCHEMA}:")
try:
    tables = [r.tableName for r in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()]
    for t in tables:
        print(f"  • {CATALOG}.{SCHEMA}.{t}")
except Exception:
    tables = []
    print("  (schema not found or already empty)")

print()

for t in tables:
    fqn = f"{CATALOG}.{SCHEMA}.{t}"
    do(f"DROP TABLE {fqn}", lambda f=fqn: spark.sql(f"DROP TABLE IF EXISTS {f}"))

do(
    f"DROP SCHEMA {CATALOG}.{SCHEMA} CASCADE",
    lambda: spark.sql(f"DROP SCHEMA IF EXISTS {CATALOG}.{SCHEMA} CASCADE"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Drop regulatory_reports from audit schema (conditional)
# MAGIC
# MAGIC Only drops `audit.regulatory_reports` if no other sessions are actively using the audit schema.
# MAGIC Check with other sessions before dropping.

# COMMAND ----------

audit_table = f"{CATALOG}.audit.regulatory_reports"

try:
    exists = spark.catalog.tableExists(audit_table)
except Exception:
    exists = False

if exists:
    print(f"Found: {audit_table}")
    print()
    print("⚠️  This table may also be used by Session 1.")
    print("   Only drop it if Session 1 has also been cleaned up.")
    print()
    print("   To drop manually, run:")
    print(f"     spark.sql(\"DROP TABLE IF EXISTS {audit_table}\")")
    print()
    print("   Skipping automatic drop to avoid breaking Session 1.")
else:
    print(f"  {audit_table} not found — nothing to drop.")

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
    print(f"  • UC functions: calculate_peak_demand, get_outage_summary, lookup_asset_status")
    print(f"  • Energy tables in {CATALOG}.{SCHEMA}")
    print(f"  • Schema {CATALOG}.{SCHEMA}")
    if revoke_list:
        print(f"  • EXECUTE grants for {len(revoke_list)} user(s)")
    print()
    print("Not removed (shared resources):")
    print(f"  • Catalog {CATALOG}")
    print(f"  • Schema {CATALOG}.audit (see Step 4 for manual drop instructions)")
    print(f"  • Participant skills files in /Users/.../.assistant/skills/")
