# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">Session 6 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Revokes participant grants only. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes:**
# MAGIC - `SELECT`, `USE SCHEMA`, and `USE CATALOG` grants for Session 6 participants on `workshop_au.aemo`
# MAGIC
# MAGIC **What this does NOT remove:**
# MAGIC - The `workshop_au.aemo` tables (shared with Session 2 — clean up via Session 2 cleanup)
# MAGIC - The AEMO Genie Space (remove via the Genie Space permissions panel or Session 2 cleanup)
# MAGIC - Any data, schemas, or catalogs
# MAGIC
# MAGIC Session 6 does not create any data resources — it only grants access to resources
# MAGIC created in Session 2. Run `session2_genie_space/setup/cleanup.py` to remove those.
# MAGIC
# MAGIC **`dry_run = true` by default** — prints what would be revoked without doing anything.
# MAGIC Set to `false` to actually revoke.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Configure widgets

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au", "Catalog")
dbutils.widgets.text("schema_aemo",    "aemo",        "AEMO schema")
dbutils.widgets.text("revoke_emails",  "",            "Emails to revoke (comma-separated)")
dbutils.widgets.dropdown("dry_run",    "true", ["true", "false"], "Dry run (true = preview only)")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA_AEMO = dbutils.widgets.get("schema_aemo")
raw_emails  = dbutils.widgets.get("revoke_emails")
DRY_RUN     = dbutils.widgets.get("dry_run") == "true"

revoke_list = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

mode = "DRY RUN — nothing will be revoked" if DRY_RUN else "LIVE — revocations will happen"
print(f"Mode        : {mode}")
print(f"Schema      : {CATALOG}.{SCHEMA_AEMO}")
print(f"Participants: {len(revoke_list)} email(s)")
if DRY_RUN:
    print()
    print("Change dry_run widget to 'false' to actually revoke.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Revoke participant grants

# COMMAND ----------

def do(label, fn):
    if DRY_RUN:
        print(f"  [DRY RUN] Would: {label}")
    else:
        try:
            fn()
            print(f"  OK  {label}")
        except Exception as e:
            print(f"  WARN  {label}: {e}")


if not revoke_list:
    print("No emails provided — skipping.")
    print("Enter emails in the 'revoke_emails' widget and re-run.")
else:
    revoke_statements = [
        f"REVOKE SELECT ON SCHEMA {CATALOG}.{SCHEMA_AEMO} FROM",
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_AEMO} FROM",
        f"REVOKE USE CATALOG ON CATALOG {CATALOG} FROM",
    ]

    print(f"Revoking grants for {len(revoke_list)} participant(s):\n")
    for email in revoke_list:
        for stmt_prefix in revoke_statements:
            stmt = f"{stmt_prefix} `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))
        print(f"  {'[DRY RUN] Would revoke' if DRY_RUN else 'OK  Revoked'}: {email}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Summary

# COMMAND ----------

print("=" * 55)
print(f"  Session 6 cleanup {'preview' if DRY_RUN else 'complete'}")
print("=" * 55)
print()

if DRY_RUN:
    print("Nothing was revoked. To run for real:")
    print("  1. Set 'dry_run' widget to 'false'")
    print("  2. Re-run all cells")
else:
    if revoke_list:
        print(f"Revoked grants for {len(revoke_list)} participant(s) on {CATALOG}.{SCHEMA_AEMO}")
    print()
    print("Not removed (shared with Session 2):")
    print(f"  - {CATALOG}.{SCHEMA_AEMO} tables and schema")
    print(f"  - AEMO Genie Space")
    print()
    print("To remove shared resources, run:")
    print("  session2_genie_space/setup/cleanup.py")
    print()
    print("To remove Genie Space access for individual users:")
    print("  Open the Genie Space > permissions panel > remove users")
