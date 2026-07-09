# Databricks notebook source

# MAGIC %pip install -q databricks-vectorsearch

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0 0 8px 0; font-size: 26px">Session 4 Cleanup</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 0; font-size: 13px">Removes everything <code>setup.py</code> created. Run after the workshop.</p>
# MAGIC </div>
# MAGIC
# MAGIC **Removes (exactly what setup created):**
# MAGIC 1. The 3 UC functions (`calculate_peak_demand`, `get_region_summary`, `lookup_duid_info`)
# MAGIC 2. The 6 AEMO tables in `workshop_au.aemo`
# MAGIC 3. The CSV staging volume `workshop_au.aemo.raw`
# MAGIC 4. The Vector Search index (`aemo_market_notices_index`) and endpoint (`workshop_vs`)
# MAGIC 5. The Databricks App (`aemo-operations-agent`)
# MAGIC 6. The MLflow experiments (`/Shared/session4-aemo-agent`, `/Shared/aemo-operations-agent`)
# MAGIC 7. UC grants on the schema (for the emails you list)
# MAGIC 8. The `aemo` schema itself (only if empty after the above)
# MAGIC
# MAGIC **Not removed (shared / pre-existing):** the `workshop_au` catalog and the PT serving endpoint.
# MAGIC
# MAGIC ⚠️ **`dry_run = true` by default** — preview only. Set to `false` to actually delete.

# COMMAND ----------

dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",       "workshop_au",           "Catalog")
dbutils.widgets.text("schema_aemo",   "aemo",                  "AEMO schema")
dbutils.widgets.text("vs_endpoint",   "workshop_vs",           "Vector Search endpoint")
dbutils.widgets.text("app_name",      "aemo-operations-agent", "Databricks App name")
dbutils.widgets.text("revoke_emails", "",                      "Emails to revoke (comma-separated)")
dbutils.widgets.dropdown("dry_run",   "true", ["true", "false"], "Dry run (true = preview only)")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA      = dbutils.widgets.get("schema_aemo")
VS_ENDPOINT = dbutils.widgets.get("vs_endpoint")
APP_NAME    = dbutils.widgets.get("app_name").strip()
DRY_RUN     = dbutils.widgets.get("dry_run") == "true"

VS_INDEX_NAME  = f"{CATALOG}.{SCHEMA}.aemo_market_notices_index"
VOLUME_NAME    = f"{CATALOG}.{SCHEMA}.raw"
UC_FUNCTIONS   = ["calculate_peak_demand", "get_region_summary", "lookup_duid_info"]
AEMO_TABLES    = ["dispatch_intervals", "spot_prices", "market_notices",
                  "generator_registration", "constraint_sets", "settlement_amounts"]
MLFLOW_EXPERIMENTS = ["/Shared/session4-aemo-agent", "/Shared/aemo-operations-agent"]

ctx     = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
HOST    = ctx.apiUrl().get().rstrip("/")
TOKEN   = ctx.apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print("Mode    :", "DRY RUN — nothing will be deleted" if DRY_RUN else "LIVE — deletions WILL happen")
print(f"Catalog : {CATALOG}.{SCHEMA}")
if DRY_RUN:
    print("\n⚠️  Set the 'dry_run' widget to 'false' to actually delete.")

# COMMAND ----------

def do(label: str, fn) -> None:
    """Run fn, or just print it in dry-run mode. Failures are logged, not fatal."""
    if DRY_RUN:
        print(f"  [DRY RUN] Would: {label}")
        return
    try:
        fn()
        print(f"  ✅ {label}")
    except Exception as e:  # keep cleaning up even if one step fails
        print(f"  ⚠️  {label}: {str(e)[:160]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: UC functions, tables, and the staging volume

# COMMAND ----------

for fn in UC_FUNCTIONS:
    fqn = f"{CATALOG}.{SCHEMA}.{fn}"
    do(f"DROP FUNCTION {fqn}", lambda f=fqn: spark.sql(f"DROP FUNCTION IF EXISTS {f}"))

for t in AEMO_TABLES:
    fqn = f"{CATALOG}.{SCHEMA}.{t}"
    do(f"DROP TABLE {fqn}", lambda f=fqn: spark.sql(f"DROP TABLE IF EXISTS {f}"))

do(f"DROP VOLUME {VOLUME_NAME}", lambda: spark.sql(f"DROP VOLUME IF EXISTS {VOLUME_NAME}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Vector Search index and endpoint

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient(disable_notice=True)

# Index must be deleted before the endpoint.
def _drop_index():
    vsc.delete_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX_NAME)
do(f"Delete VS index {VS_INDEX_NAME}", _drop_index)

def _drop_endpoint():
    vsc.delete_endpoint(name=VS_ENDPOINT)
do(f"Delete VS endpoint {VS_ENDPOINT}", _drop_endpoint)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Databricks App

# COMMAND ----------

import requests

if not APP_NAME:
    print("No app_name set — skipping app deletion.")
else:
    info = requests.get(f"{HOST}/api/2.0/apps/{APP_NAME}", headers=HEADERS)
    if info.status_code == 404:
        print(f"  App '{APP_NAME}' not found — already removed or never created.")
    else:
        do(f"Delete app '{APP_NAME}'",
           lambda: requests.delete(f"{HOST}/api/2.0/apps/{APP_NAME}", headers=HEADERS).raise_for_status())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: MLflow experiments

# COMMAND ----------

from mlflow.tracking import MlflowClient

client = MlflowClient()
for exp_name in MLFLOW_EXPERIMENTS:
    exp = client.get_experiment_by_name(exp_name)
    if exp is None:
        print(f"  MLflow experiment '{exp_name}' not found.")
    else:
        do(f"Delete MLflow experiment '{exp_name}' (soft-delete, restorable 30 days)",
           lambda e=exp: client.delete_experiment(e.experiment_id))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Revoke UC grants

# COMMAND ----------

revoke_list = [e.strip().lower() for e in dbutils.widgets.get("revoke_emails").split(",") if e.strip()]
if not revoke_list:
    print("No emails provided — skipping grant revocation.")
else:
    stmts = [
        f"REVOKE SELECT ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE EXECUTE ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} FROM",
        # USE CATALOG intentionally left in place — workshop_au is shared across sessions.
    ]
    for email in revoke_list:
        for prefix in stmts:
            do(f"{prefix} `{email}`", lambda s=f"{prefix} `{email}`": spark.sql(s))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Drop the schema (only if now empty)

# COMMAND ----------

# Non-CASCADE drop: succeeds only if we removed everything above. If the schema still
# holds objects this workshop didn't create, it is left in place (and we say so).
try:
    remaining = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").count()
except Exception:
    remaining = 0
if remaining:
    print(f"  {CATALOG}.{SCHEMA} still has {remaining} table(s) not created by this workshop — leaving the schema in place.")
else:
    do(f"DROP SCHEMA {CATALOG}.{SCHEMA}", lambda: spark.sql(f"DROP SCHEMA IF EXISTS {CATALOG}.{SCHEMA}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("=" * 55)
print("  Cleanup " + ("preview (dry run)" if DRY_RUN else "complete"))
print("=" * 55)
if DRY_RUN:
    print("\nNothing was deleted. Set 'dry_run' = 'false' and re-run to delete.")
else:
    print("\nRemoved (where present): UC functions, AEMO tables, staging volume,")
    print("Vector Search index + endpoint, the Databricks App, MLflow experiments,")
    print("listed UC grants, and the schema (if empty).")
    print("\nLeft in place (shared): the workshop_au catalog and the PT serving endpoint.")
