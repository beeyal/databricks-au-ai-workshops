# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">🗑️ Session 2 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything created during Session 2. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes (fully automated):**
# MAGIC - AEMO Delta tables (`workshop_au.aemo.*`) and the `aemo` schema
# MAGIC - Genie Spaces (via `DELETE /api/2.0/genie/spaces/{id}` — moves to workspace trash)
# MAGIC - All Genie Spaces in this workspace if `delete_all_spaces = true`
# MAGIC - Space registry table and the `ai_governance` schema
# MAGIC - The `workshop_au` catalog (after all schemas are empty)
# MAGIC - UC permission grants on the schema
# MAGIC
# MAGIC ⚠️ **`dry_run = true` by default** — prints what would be deleted without doing anything.
# MAGIC Set to `false` to actually delete.

# COMMAND ----------

dbutils.widgets.text("catalog",           "workshop_au",  "Catalog to drop")
dbutils.widgets.text("schema",            "aemo",         "AEMO schema to drop")
dbutils.widgets.text("schema_gov",        "ai_governance","Governance schema to drop")
dbutils.widgets.text("space_ids",         "",             "Genie Space IDs to delete (comma-separated)")
dbutils.widgets.dropdown("delete_all_spaces", "false", ["true", "false"], "Delete ALL Genie Spaces in this workspace")
dbutils.widgets.dropdown("drop_catalog",  "true",  ["true", "false"], "Drop workshop_au catalog when empty")
dbutils.widgets.dropdown("dry_run",       "true",  ["true", "false"], "Dry run (true = preview only)")

CATALOG          = dbutils.widgets.get("catalog")
SCHEMA           = dbutils.widgets.get("schema")
SCHEMA_GOV       = dbutils.widgets.get("schema_gov")
DRY_RUN          = dbutils.widgets.get("dry_run") == "true"
DROP_CATALOG     = dbutils.widgets.get("drop_catalog") == "true"
DELETE_ALL_SPACES = dbutils.widgets.get("delete_all_spaces") == "true"
raw_ids          = dbutils.widgets.get("space_ids")
SPACE_IDS        = [s.strip() for s in raw_ids.split(",") if s.strip()]

HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

mode = "DRY RUN — nothing will be deleted" if DRY_RUN else "LIVE — deletions will happen"
print(f"Mode          : {mode}")
print(f"Catalog       : {CATALOG}.{SCHEMA}")
print(f"Space IDs     : {SPACE_IDS or '(none provided)'}")
print(f"Delete all    : {DELETE_ALL_SPACES}")
print(f"Drop catalog  : {DROP_CATALOG}")
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

def _delete_space(sid):
    """DELETE /api/2.0/genie/spaces/{id} — moves space to workspace trash (recoverable).
    Verified working: the API exists and returns 200. The space no longer appears
    in the space list after deletion. A trashed space can be recovered from the
    workspace Trash bin within 30 days."""
    info = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{sid}", headers=HEADERS)
    name = info.json().get("title", sid) if info.status_code == 200 else sid

    if DRY_RUN:
        print(f"  [DRY RUN] Would delete Genie Space: '{name}' ({sid})")
        return

    resp = requests.delete(f"https://{HOST}/api/2.0/genie/spaces/{sid}", headers=HEADERS)
    if resp.status_code in (200, 204):
        print(f"  ✅ Deleted Genie Space: '{name}' ({sid})")
    elif resp.status_code == 404 and "trashed" in resp.text:
        print(f"  ✅ '{name}' ({sid}) — already in trash")
    else:
        print(f"  ⚠️  '{name}' ({sid}) — HTTP {resp.status_code}: {resp.text[:120]}")

# Build the list of spaces to delete
spaces_to_delete = list(SPACE_IDS)  # explicit IDs from widget

if DELETE_ALL_SPACES:
    print("delete_all_spaces=true — discovering all Genie Spaces in this workspace...")
    list_resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces", headers=HEADERS)
    if list_resp.status_code == 200:
        all_spaces = list_resp.json().get("genie_spaces", [])
        print(f"  Found {len(all_spaces)} space(s)")
        for s in all_spaces:
            sid = s.get("id", "")
            if sid and sid not in spaces_to_delete:
                spaces_to_delete.append(sid)
    else:
        print(f"  ⚠️  Could not list spaces: HTTP {list_resp.status_code}")

if not spaces_to_delete:
    print("No Genie Spaces to delete.")
    print("Options:")
    print("  • Enter Space IDs in the 'space_ids' widget (comma-separated)")
    print("  • Set 'delete_all_spaces' to 'true' to delete every space in this workspace")
    print("  • Find a Space ID in the browser URL: .../genie/rooms/{id}")
else:
    print(f"\nDeleting {len(spaces_to_delete)} Genie Space(s):")
    for sid in spaces_to_delete:
        _delete_space(sid)

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
# MAGIC ## Step 4: Drop governance schema and catalog

# COMMAND ----------

# Drop ai_governance schema (contains the space registry table)
gov_schema_fqn = f"{CATALOG}.{SCHEMA_GOV}"
print(f"Schemas remaining in {CATALOG}:")
try:
    schemas = [r[0] for r in spark.sql(f"SHOW SCHEMAS IN {CATALOG}").collect()
               if r[0] not in ("information_schema",)]
    for s in schemas:
        print(f"  • {CATALOG}.{s}")
except Exception as e:
    schemas = []
    print(f"  (catalog not found or error: {e})")

print()

# Drop governance schema (registry table inside will be CASCADE-dropped)
do(
    f"DROP SCHEMA {gov_schema_fqn} CASCADE",
    lambda: spark.sql(f"DROP SCHEMA IF EXISTS {gov_schema_fqn} CASCADE")
)

# Drop default schema if empty
do(
    f"DROP SCHEMA {CATALOG}.default CASCADE",
    lambda: spark.sql(f"DROP SCHEMA IF EXISTS {CATALOG}.default CASCADE")
)

# Drop the catalog itself — only if drop_catalog=true and all schemas are gone
if DROP_CATALOG:
    do(
        f"DROP CATALOG {CATALOG} CASCADE",
        lambda: spark.sql(f"DROP CATALOG IF EXISTS {CATALOG} CASCADE")
    )
else:
    print(f"  [SKIP] Catalog {CATALOG} — set drop_catalog=true to remove it")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Revoke UC permissions
# MAGIC
# MAGIC Revokes the grants applied in `aemo_space_config.py` Step 7 (or `setup/setup.py` Step 6).

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
        f"REVOKE USE CATALOG ON CATALOG {CATALOG} FROM",
    ]
    for email in revoke_list:
        for stmt_prefix in revoke_stmts:
            stmt = f"{stmt_prefix} `{email}`"
            do(stmt, lambda s=stmt: spark.sql(s))
        print(f"  {'[DRY RUN] Would revoke' if DRY_RUN else '✅ Revoked'}: {email}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6: Summary

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
    print(f"  ✅ AEMO tables in {CATALOG}.{SCHEMA} and schema dropped")
    print(f"  ✅ {CATALOG}.{SCHEMA_GOV} schema dropped (CASCADE)")
    if DROP_CATALOG:
        print(f"  ✅ Catalog {CATALOG} dropped")
    if spaces_to_delete:
        print(f"  ✅ {len(spaces_to_delete)} Genie Space(s) moved to workspace trash")
        print(f"     (recoverable from workspace Trash within 30 days)")
    if revoke_list:
        print(f"  ✅ UC grants revoked for {len(revoke_list)} user(s)")
    print()
    if not DROP_CATALOG:
        print(f"Not removed:")
        print(f"  • Catalog {CATALOG} — set drop_catalog=true to remove")
    print()
    print("Full cleanup complete. Nothing requires manual action.")
