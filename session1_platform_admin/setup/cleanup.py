# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">Session 1 — Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything created during Session 1. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes:**
# MAGIC - All Delta tables in `workshop_au.energy` and the `energy` schema itself
# MAGIC - AI Gateway payload log tables and other workshop artefacts in `ai_governance` (schema itself is kept)
# MAGIC - UC permission grants per participant email
# MAGIC
# MAGIC **What this does NOT remove:**
# MAGIC - The `workshop_au` catalog (may be shared with other workshops)
# MAGIC - The `ai_governance` schema itself
# MAGIC - Any AI Gateway routes or external endpoint configs (managed outside UC)
# MAGIC
# MAGIC ⚠️ **`dry_run = true` by default** — prints what would be deleted without doing anything.
# MAGIC Set to `false` to actually delete.

# COMMAND ----------

dbutils.widgets.text("catalog",          "workshop_au",   "Catalog")
dbutils.widgets.text("schema_energy",    "energy",        "Energy schema to drop")
dbutils.widgets.text("schema_governance","ai_governance", "Governance schema (tables only, schema kept)")
dbutils.widgets.text("revoke_emails",    "",              "Emails to revoke (comma-separated)")
dbutils.widgets.dropdown("dry_run",      "true", ["true", "false"], "Dry run (true = preview only)")

CATALOG    = dbutils.widgets.get("catalog")
SCHEMA_E   = dbutils.widgets.get("schema_energy")
SCHEMA_GOV = dbutils.widgets.get("schema_governance")
DRY_RUN    = dbutils.widgets.get("dry_run") == "true"

raw_emails   = dbutils.widgets.get("revoke_emails")
revoke_list  = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

mode = "DRY RUN — nothing will be deleted" if DRY_RUN else "LIVE — deletions will happen"
print(f"Mode              : {mode}")
print(f"Energy schema     : {CATALOG}.{SCHEMA_E}   (will be dropped)")
print(f"Governance schema : {CATALOG}.{SCHEMA_GOV} (tables cleared, schema kept)")
print(f"Revoke emails     : {revoke_list or '(none provided)'}")
if DRY_RUN:
    print()
    print("⚠️  Change dry_run widget to 'false' to actually delete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Drop energy schema and all tables

# COMMAND ----------

def do(label, fn):
    """Execute fn() or print a dry-run preview, with consistent formatting."""
    if DRY_RUN:
        print(f"  [DRY RUN] Would: {label}")
    else:
        try:
            fn()
            print(f"  ✅ {label}")
        except Exception as e:
            print(f"  ⚠️  {label}: {e}")

# List tables that exist in the energy schema
print(f"Tables in {CATALOG}.{SCHEMA_E}:")
try:
    energy_tables = [r.tableName for r in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA_E}").collect()]
    for t in energy_tables:
        print(f"  • {CATALOG}.{SCHEMA_E}.{t}")
except Exception:
    energy_tables = []
    print("  (schema not found or already empty)")

print()

# Drop tables individually before dropping the schema (cleaner audit trail)
for t in energy_tables:
    fqn = f"{CATALOG}.{SCHEMA_E}.{t}"
    do(f"DROP TABLE {fqn}", lambda f=fqn: spark.sql(f"DROP TABLE IF EXISTS {f}"))

# Drop the schema (CASCADE handles any stragglers)
do(
    f"DROP SCHEMA {CATALOG}.{SCHEMA_E}",
    lambda: spark.sql(f"DROP SCHEMA IF EXISTS {CATALOG}.{SCHEMA_E} CASCADE")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Clean up governance schema tables
# MAGIC
# MAGIC Drops `genie_space_registry` and any other workshop-created tables in `ai_governance`.
# MAGIC The schema itself is preserved as it may be shared across workshop sessions.

# COMMAND ----------

# Tables created by Session 1 labs that should be cleaned up
GOV_CLEANUP_TABLES = [
    "genie_space_registry",
    "ai_gateway_payload_log",
    "compliance_audit_log",
    "policy_violations",
]

print(f"Checking {CATALOG}.{SCHEMA_GOV} for workshop tables:")

try:
    existing_gov = {r.tableName for r in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA_GOV}").collect()}
except Exception:
    existing_gov = set()
    print("  (schema not found — nothing to clean up)")

found_any = False
for tbl in GOV_CLEANUP_TABLES:
    if tbl in existing_gov:
        fqn = f"{CATALOG}.{SCHEMA_GOV}.{tbl}"
        do(f"DROP TABLE {fqn}", lambda f=fqn: spark.sql(f"DROP TABLE IF EXISTS {f}"))
        found_any = True

if not found_any:
    print("  No workshop tables found in governance schema — nothing to clean up.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Revoke UC grants per participant

# COMMAND ----------

if not revoke_list:
    print("No emails provided — skipping permission revocation.")
    print("Enter emails in the 'revoke_emails' widget to revoke access.")
else:
    print(f"Revoking grants for {len(revoke_list)} user(s):\n")

    # Mirror the grants applied in setup.py Step 4
    revoke_stmts = [
        f"REVOKE SELECT       ON SCHEMA  {CATALOG}.{SCHEMA_E}   FROM",
        f"REVOKE USE SCHEMA   ON SCHEMA  {CATALOG}.{SCHEMA_E}   FROM",
        f"REVOKE SELECT       ON SCHEMA  {CATALOG}.{SCHEMA_GOV} FROM",
        f"REVOKE USE SCHEMA   ON SCHEMA  {CATALOG}.{SCHEMA_GOV} FROM",
        f"REVOKE CREATE TABLE ON SCHEMA  {CATALOG}.{SCHEMA_GOV} FROM",
        f"REVOKE USE CATALOG  ON CATALOG {CATALOG}              FROM",
    ]

    for email in revoke_list:
        for stmt_prefix in revoke_stmts:
            stmt = f"{stmt_prefix} `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))
        tag = "[DRY RUN] Would revoke" if DRY_RUN else "✅ Revoked"
        print(f"  {tag}: {email}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Summary

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
    if energy_tables:
        print(f"  • {len(energy_tables)} table(s) in {CATALOG}.{SCHEMA_E}")
    print(f"  • Schema {CATALOG}.{SCHEMA_E}")
    if found_any:
        print(f"  • Workshop tables in {CATALOG}.{SCHEMA_GOV}")
    if revoke_list:
        print(f"  • UC grants for {len(revoke_list)} user(s)")
    print()
    print("Not removed (shared resources):")
    print(f"  • Catalog {CATALOG}")
    print(f"  • Schema {CATALOG}.{SCHEMA_GOV}")
    print(f"  • AI Gateway routes and endpoint configurations")
    print(f"  • Any external data or configurations outside UC")
