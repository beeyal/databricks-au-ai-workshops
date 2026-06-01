# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">Session 4 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything created during Session 4. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes:**
# MAGIC - AEMO Delta tables (`workshop_au.aemo.*`)
# MAGIC - The `aemo` schema
# MAGIC - Databricks Apps created during the labs (you confirm by name)
# MAGIC - UC permission grants on the schema
# MAGIC - Session registry row (if present)
# MAGIC
# MAGIC **What this does NOT remove:**
# MAGIC - The `workshop_au` catalog (shared with other sessions)
# MAGIC - The Provisioned Throughput endpoint (shared resource — may be used by other sessions)
# MAGIC - Any apps you choose not to confirm
# MAGIC
# MAGIC ⚠️ **`dry_run = true` by default** — prints what would be deleted without doing anything.
# MAGIC Set to `false` to actually delete.

# COMMAND ----------

dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",       "workshop_au",  "Catalog")
dbutils.widgets.text("schema_aemo",   "aemo",         "AEMO schema to drop")
dbutils.widgets.text("schema_gov",    "ai_governance","Governance schema (for registry)")
dbutils.widgets.text("revoke_emails", "",             "Emails to revoke (comma-separated)")
dbutils.widgets.dropdown("dry_run",   "true", ["true", "false"], "Dry run (true = preview only)")

CATALOG    = dbutils.widgets.get("catalog")
SCHEMA     = dbutils.widgets.get("schema_aemo")
SCHEMA_GOV = dbutils.widgets.get("schema_gov")
DRY_RUN    = dbutils.widgets.get("dry_run") == "true"

ctx     = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST    = ctx.apiUrl().get().replace("https://", "")
TOKEN   = ctx.apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

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
# MAGIC ## Step 1: Drop AEMO schema and tables

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
# MAGIC ## Step 2: Remove Databricks Apps created during labs
# MAGIC
# MAGIC Lists all apps in the workspace. You will be asked to confirm which ones to delete.
# MAGIC Enter the app names to delete in the widget, then re-run this cell.

# COMMAND ----------

import requests

print("Fetching Databricks Apps in this workspace...")

apps_resp = requests.get(f"https://{HOST}/api/2.0/apps", headers=HEADERS)

if apps_resp.status_code != 200:
    print(f"⚠️  Could not list apps: HTTP {apps_resp.status_code} {apps_resp.text[:200]}")
    all_apps = []
else:
    all_apps = apps_resp.json().get("apps", [])

if not all_apps:
    print("  No Databricks Apps found in this workspace.")
else:
    print(f"\nFound {len(all_apps)} app(s):\n")
    print(f"  {'Name':<40} {'Status':<15} {'Creator'}")
    print(f"  {'-'*40} {'-'*15} {'-'*30}")
    for app in all_apps:
        name    = app.get("name", "?")
        status  = app.get("compute_status", {}).get("state", "?")
        creator = app.get("creator", "?")
        print(f"  {name:<40} {status:<15} {creator}")
    print()
    print("Enter the names to delete in the 'apps_to_delete' widget below, then re-run the NEXT cell.")

# COMMAND ----------

dbutils.widgets.text("apps_to_delete", "", "App names to delete (comma-separated, exact match)")
raw_apps      = dbutils.widgets.get("apps_to_delete")
apps_to_delete = [a.strip() for a in raw_apps.split(",") if a.strip()]

if not apps_to_delete:
    print("No app names specified — skipping app deletion.")
    print("Enter app names in the 'apps_to_delete' widget and re-run this cell.")
else:
    for app_name in apps_to_delete:
        # Look up the app to confirm it exists
        info_resp = requests.get(f"https://{HOST}/api/2.0/apps/{app_name}", headers=HEADERS)
        if info_resp.status_code == 404:
            print(f"  ⚠️  App '{app_name}' not found — skipping.")
            continue

        if DRY_RUN:
            print(f"  [DRY RUN] Would delete app: '{app_name}'")
        else:
            del_resp = requests.delete(f"https://{HOST}/api/2.0/apps/{app_name}", headers=HEADERS)
            if del_resp.status_code in (200, 204):
                print(f"  ✅ Deleted app: '{app_name}'")
            else:
                print(f"  ⚠️  Could not delete '{app_name}': HTTP {del_resp.status_code} {del_resp.text[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Revoke UC permission grants

# COMMAND ----------

raw_revoke  = dbutils.widgets.get("revoke_emails")
revoke_list = [e.strip().lower() for e in raw_revoke.split(",") if e.strip()]

if not revoke_list:
    print("No emails provided — skipping permission revocation.")
    print("Enter emails in the 'revoke_emails' widget to revoke access.")
else:
    revoke_stmts = [
        f"REVOKE SELECT ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} FROM",
    ]
    for email in revoke_list:
        for stmt_prefix in revoke_stmts:
            stmt = f"{stmt_prefix} `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))
        print(f"  {'[DRY RUN] Would revoke' if DRY_RUN else '✅ Revoked'}: {email}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Remove session registry row (if present)

# COMMAND ----------

registry_fqn = f"{CATALOG}.{SCHEMA_GOV}.genie_space_registry"

try:
    exists = spark.catalog.tableExists(registry_fqn)
except Exception:
    exists = False

if exists:
    do(
        f"Delete Session 4 row from {registry_fqn}",
        lambda: spark.sql(
            f"DELETE FROM {registry_fqn} WHERE session = '4' OR session_name LIKE '%MCP%'"
        ),
    )
    if not DRY_RUN:
        remaining = spark.table(registry_fqn).count()
        print(f"  Registry now has {remaining} entries")
else:
    print(f"  Registry table not found — nothing to clean up")

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
    if apps_to_delete:
        print(f"  • {len(apps_to_delete)} Databricks App(s)")
    if revoke_list:
        print(f"  • UC grants for {len(revoke_list)} user(s)")
    print()
    print("Not removed (shared resources):")
    print(f"  • Catalog {CATALOG}")
    print(f"  • Provisioned Throughput endpoint (shared — check with other sessions before deleting)")
    print(f"  • Any apps not listed in the 'apps_to_delete' widget")
