# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">Session 4 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything created during Session 4. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this removes:**
# MAGIC - UC functions registered in `workshop_au.aemo`
# MAGIC - AEMO Delta tables (`workshop_au.aemo.*`)
# MAGIC - The `aemo` schema
# MAGIC - `/tmp/workshop2c_config.json` (driver-local config file)
# MAGIC - Vector Search index (`workshop_au.aemo.market_notices_index`) and endpoint (`workshop-vs-endpoint`)
# MAGIC - Databricks Apps created during the labs (you confirm by name)
# MAGIC - MLflow experiment `/Apps/aemo-operations-agent`
# MAGIC - UC permission grants on the schema (SELECT, CREATE TABLE, EXECUTE, USE SCHEMA, USE CATALOG)
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
DRY_RUN    = dbutils.widgets.get("dry_run") == "true"  # compare string; widget always returns str

# Pull workspace URL and PAT from the notebook execution context
ctx     = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST    = ctx.apiUrl().get().rstrip("/")  # strip trailing slash for clean URL joins
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
            print(f"  ⚠️  {label}: {e}")  # non-fatal: log and continue cleanup

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Drop AEMO schema and tables

# COMMAND ----------

# Drop UC functions in aemo schema before dropping schema
print(f"UC functions in {CATALOG}.{SCHEMA}:")
try:
    funcs = spark.sql(f"SHOW FUNCTIONS IN {CATALOG}.{SCHEMA}").collect()
    if funcs:
        for f in funcs:
            fn_fqn = f.function  # fully-qualified name e.g. workshop_au.aemo.fn
            # Default arg captures fq at loop time, avoiding closure-over-loop-var bug
            do(f"DROP FUNCTION IF EXISTS {fn_fqn}",
               lambda fq=fn_fqn: spark.sql(f"DROP FUNCTION IF EXISTS {fq}"))
    else:
        print("  (no functions found)")
except Exception as e:
    print(f"  (could not list functions: {e})")

print()

print(f"Tables in {CATALOG}.{SCHEMA}:")
try:
    # Collect table names only; schema may not exist if a previous run already dropped it
    tables = [r.tableName for r in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()]
    for t in tables:
        print(f"  • {CATALOG}.{SCHEMA}.{t}")
except Exception:
    tables = []
    print("  (schema not found or already empty)")

print()

# Drop tables individually first; CASCADE on schema is a safety net
for t in tables:
    fqn = f"{CATALOG}.{SCHEMA}.{t}"
    do(f"DROP TABLE {fqn}", lambda f=fqn: spark.sql(f"DROP TABLE IF EXISTS {f}"))

# CASCADE removes any remaining tables/views the explicit loop may have missed
do(
    f"DROP SCHEMA {CATALOG}.{SCHEMA} CASCADE",
    lambda: spark.sql(f"DROP SCHEMA IF EXISTS {CATALOG}.{SCHEMA} CASCADE"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1b: Remove /tmp/workshop2c_config.json

# COMMAND ----------

from pathlib import Path

config_path = Path("/tmp/workshop2c_config.json")
if config_path.exists():
    if DRY_RUN:
        print(f"  [DRY RUN] Would remove {config_path}")
    else:
        config_path.unlink()  # driver-local file; no distributed delete needed
        print(f"  ✅ Removed {config_path}")
else:
    print(f"  {config_path} not found — already removed or never created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1c: Delete Vector Search index and endpoint

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

VS_INDEX_NAME    = f"{CATALOG}.{SCHEMA}.market_notices_index"
VS_ENDPOINT_NAME = "workshop-vs-endpoint"

w = WorkspaceClient(host=HOST, token=TOKEN)

# Delete the index first (must be removed before the endpoint can be deleted)
print(f"Vector Search index: {VS_INDEX_NAME}")
try:
    w.vector_search_indexes.get(VS_INDEX_NAME)  # probe existence; raises NotFound if absent
    do(
        f"Delete VS index '{VS_INDEX_NAME}'",
        lambda: w.vector_search_indexes.delete(VS_INDEX_NAME),
    )
except NotFound:
    # SDK raises NotFound when the resource doesn't exist — treat as already clean
    print(f"  VS index '{VS_INDEX_NAME}' not found — already removed or never created.")
except Exception as e:
    print(f"  ⚠️  Could not check VS index: {e}")

print()

# Delete the endpoint (no-op if index deletion is dry-run — endpoint may still have the index)
print(f"Vector Search endpoint: {VS_ENDPOINT_NAME}")
try:
    w.vector_search_endpoints.get_endpoint(VS_ENDPOINT_NAME)  # probe before delete
    do(
        f"Delete VS endpoint '{VS_ENDPOINT_NAME}'",
        lambda: w.vector_search_endpoints.delete(VS_ENDPOINT_NAME),
    )
except NotFound:
    # Same NotFound pattern as index — idempotent cleanup
    print(f"  VS endpoint '{VS_ENDPOINT_NAME}' not found — already removed or never created.")
except Exception as e:
    print(f"  ⚠️  Could not check VS endpoint: {e}")

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

apps_resp = requests.get(f"{HOST}/api/2.0/apps", headers=HEADERS)  # list all workspace apps

if apps_resp.status_code != 200:
    print(f"⚠️  Could not list apps: HTTP {apps_resp.status_code} {apps_resp.text[:200]}")
    all_apps = []
else:
    all_apps = apps_resp.json().get("apps", [])  # default to empty list if key absent

if not all_apps:
    print("  No Databricks Apps found in this workspace.")
else:
    print(f"\nFound {len(all_apps)} app(s):\n")
    print(f"  {'Name':<40} {'Status':<15} {'Creator'}")
    print(f"  {'-'*40} {'-'*15} {'-'*30}")
    for app in all_apps:
        name    = app.get("name", "?")
        status  = app.get("compute_status", {}).get("state", "?")  # nested status field
        creator = app.get("creator", "?")
        print(f"  {name:<40} {status:<15} {creator}")
    print()
    print("Enter the names to delete in the 'apps_to_delete' widget below, then re-run the NEXT cell.")

# COMMAND ----------

dbutils.widgets.text("apps_to_delete", "", "App names to delete (comma-separated, exact match)")
raw_apps      = dbutils.widgets.get("apps_to_delete")
apps_to_delete = [a.strip() for a in raw_apps.split(",") if a.strip()]  # skip blank entries

if not apps_to_delete:
    print("No app names specified — skipping app deletion.")
    print("Enter app names in the 'apps_to_delete' widget and re-run this cell.")
else:
    for app_name in apps_to_delete:
        # Look up the app to confirm it exists
        info_resp = requests.get(f"{HOST}/api/2.0/apps/{app_name}", headers=HEADERS)
        if info_resp.status_code == 404:
            print(f"  ⚠️  App '{app_name}' not found — skipping.")
            continue

        if DRY_RUN:
            print(f"  [DRY RUN] Would delete app: '{app_name}'")
        else:
            del_resp = requests.delete(f"{HOST}/api/2.0/apps/{app_name}", headers=HEADERS)
            if del_resp.status_code in (200, 204):  # both codes indicate successful deletion
                print(f"  ✅ Deleted app: '{app_name}'")
            else:
                print(f"  ⚠️  Could not delete '{app_name}': HTTP {del_resp.status_code} {del_resp.text[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2b: Delete MLflow experiment

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient

EXPERIMENT_NAME = "/Apps/aemo-operations-agent"

mlflow_client = MlflowClient()
experiment = mlflow_client.get_experiment_by_name(EXPERIMENT_NAME)  # returns None if absent

if experiment is None:
    print(f"  MLflow experiment '{EXPERIMENT_NAME}' not found — nothing to delete.")
else:
    exp_id = experiment.experiment_id
    if DRY_RUN:
        print(f"  [DRY RUN] Would delete MLflow experiment '{EXPERIMENT_NAME}' (ID: {exp_id})")
    else:
        mlflow_client.delete_experiment(exp_id)  # soft-delete; recoverable for 30 days
        print(f"  ✅ Deleted MLflow experiment '{EXPERIMENT_NAME}' (ID: {exp_id})")
        print(f"     (Experiment is soft-deleted and can be restored within 30 days via client.restore_experiment())")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Revoke UC permission grants

# COMMAND ----------

raw_revoke  = dbutils.widgets.get("revoke_emails")
# Normalise to lowercase so email casing doesn't cause REVOKE to silently miss the principal
revoke_list = [e.strip().lower() for e in raw_revoke.split(",") if e.strip()]

if not revoke_list:
    print("No emails provided — skipping permission revocation.")
    print("Enter emails in the 'revoke_emails' widget to revoke access.")
else:
    revoke_stmts = [
        f"REVOKE SELECT ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE EXECUTE ON SCHEMA {CATALOG}.{SCHEMA} FROM",   # covers app SP grants from lab04
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        # NOTE: Only revoke USE CATALOG if no other sessions are still active
        # for the same participant (sessions 1–5 all share workshop_au catalog).
        f"REVOKE USE CATALOG ON CATALOG {CATALOG} FROM",
    ]
    for email in revoke_list:
        for stmt_prefix in revoke_stmts:
            stmt = f"{stmt_prefix} `{email}`"  # backtick-quote email to handle special chars
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
    exists = False  # governance schema absent in single-session workshops

if exists:
    # Match by session number OR name to handle registry rows written either way
    do(
        f"Delete Session 4 row from {registry_fqn}",
        lambda: spark.sql(
            f"DELETE FROM {registry_fqn} WHERE session = '4' OR session_name LIKE '%MCP%'"
        ),
    )
    if not DRY_RUN:
        remaining = spark.table(registry_fqn).count()  # confirm other sessions untouched
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
    print(f"  • UC functions in {CATALOG}.{SCHEMA}")
    print(f"  • AEMO tables in {CATALOG}.{SCHEMA}")
    print(f"  • Schema {CATALOG}.{SCHEMA}")
    print(f"  • /tmp/workshop2c_config.json (if present)")
    print(f"  • Vector Search index and endpoint (if present)")
    if apps_to_delete:
        print(f"  • {len(apps_to_delete)} Databricks App(s)")
    print(f"  • MLflow experiment /Apps/aemo-operations-agent (if present)")
    if revoke_list:
        print(f"  • UC grants (SELECT, CREATE TABLE, EXECUTE, USE SCHEMA, USE CATALOG) for {len(revoke_list)} user(s)")
    print()
    print("Not removed (shared resources):")
    print(f"  • Catalog {CATALOG}")
    print(f"  • Provisioned Throughput endpoint (shared — check with other sessions before deleting)")
    print(f"  • Any apps not listed in the 'apps_to_delete' widget")
