# Databricks notebook source
# MAGIC %md
# MAGIC # Workshop Setup — 00_workspace_setup
# MAGIC
# MAGIC **Run once as a workspace admin before the workshop.**
# MAGIC
# MAGIC This notebook:
# MAGIC 1. Validates all prerequisites
# MAGIC 2. Creates the workshop catalog and schemas in Unity Catalog
# MAGIC 3. Loads all sample datasets as Delta tables
# MAGIC 4. Creates a Vector Search endpoint and index on policy_documents
# MAGIC 5. Creates a Genie Space for the workshop
# MAGIC 6. Runs an end-to-end smoke test
# MAGIC
# MAGIC **Expected runtime: ~15 minutes** (most of the time is Vector Search index sync)
# MAGIC
# MAGIC **Re-runnable:** all steps are idempotent — safe to re-run after failures.

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Configuration — fill these in before running
# MAGIC Change these values to match your customer environment. Leave defaults for a Databricks Credit Program workspace.

# COMMAND ----------
dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",           "workshop_au",          "1. Catalog name")
dbutils.widgets.text("schema_energy",     "energy",               "2. Energy data schema")
dbutils.widgets.text("schema_governance", "ai_governance",        "3. Governance schema")
dbutils.widgets.text("vs_endpoint",       "workshop_vs",          "4. Vector Search endpoint name")
dbutils.widgets.text("pt_endpoint",       "au_east_llm_inregion", "5. PT endpoint name")

# COMMAND ----------
CATALOG           = dbutils.widgets.get("catalog")
SCHEMA_ENERGY     = dbutils.widgets.get("schema_energy")
SCHEMA_GOVERNANCE = dbutils.widgets.get("schema_governance")
VS_ENDPOINT       = dbutils.widgets.get("vs_endpoint")
PT_ENDPOINT       = dbutils.widgets.get("pt_endpoint")

print(f"Catalog:              {CATALOG}")
print(f"Energy schema:        {SCHEMA_ENERGY}")
print(f"Governance schema:    {SCHEMA_GOVERNANCE}")
print(f"Vector Search:        {VS_ENDPOINT}")
print(f"PT endpoint:          {PT_ENDPOINT}")
print()
print("If running in a customer environment, change these to avoid conflicts with production data.")
print("All resources created will be under the specified catalog and can be dropped via setup/99_teardown.py")

# COMMAND ----------

# MAGIC %md ## 0 — Configuration (derived variables)

# COMMAND ----------

# ── Derived from widgets — do not edit these directly ────────────────────────

# Schemas (audit is always fixed; energy and ai_governance come from widgets)
SCHEMAS = [SCHEMA_ENERGY, "audit", SCHEMA_GOVERNANCE]

# Location of the sample CSV files (relative to Databricks workspace, or DBFS/Volumes path)
# Adjust to where you uploaded the CSVs — e.g. after running:
#   databricks fs cp -r ./data/sample_data dbfs:/tmp/au_workshop/
SAMPLE_DATA_PATH = "dbfs:/tmp/au_workshop/sample_data"

# Vector Search endpoint name — sourced from widget VS_ENDPOINT
VS_ENDPOINT_NAME = VS_ENDPOINT

# Embedding model — in-region for Azure australiaeast
EMBEDDING_MODEL = "databricks-qwen3-embedding-0-6b"

# Genie Space name
GENIE_SPACE_NAME = "AU Energy Workshop — Regulated Data Assistant"

# LLM for FMAPI smoke test — must be a PT endpoint name, NOT a pay-per-token model.
# databricks-meta-llama-* models are cross-geo for AU East. Use Claude via PT only.
GENIE_LLM_MODEL = "databricks-claude-haiku-4-5"  # PT endpoint in AU East ✅

# ── End configuration ────────────────────────────────────────────────────────

print(f"Catalog:          {CATALOG}")
print(f"Schemas:          {', '.join(SCHEMAS)}")
print(f"Sample data path: {SAMPLE_DATA_PATH}")
print(f"VS endpoint:      {VS_ENDPOINT_NAME}")
print(f"Embedding model:  {EMBEDDING_MODEL}")

# COMMAND ----------

# MAGIC %md ## 1 — Prerequisites Check

# COMMAND ----------

import json
import time
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest, EmbeddingSourceColumn, PipelineType

w = WorkspaceClient()

print("=" * 60)
print("STEP 1 — PREREQUISITES CHECK")
print("=" * 60)

errors   = []
warnings = []

# 1a — Unity Catalog
print("\n[1/5] Checking Unity Catalog...")
try:
    catalogs = [c.name for c in w.catalogs.list()]
    if "system" in catalogs:
        print(f"  ✅ Unity Catalog enabled. Catalogs: {', '.join(catalogs[:6])}")
    else:
        errors.append("Unity Catalog does not appear to be enabled (no 'system' catalog found).")
        print(f"  ❌ Unity Catalog not enabled.")
except Exception as exc:
    errors.append(f"Cannot check Unity Catalog: {exc}")
    print(f"  ❌ Error: {exc}")

# 1b — Serverless SQL Warehouse
print("\n[2/5] Checking serverless SQL warehouse...")
try:
    warehouses = list(w.warehouses.list())
    serverless = [wh for wh in warehouses if getattr(wh, "enable_serverless_compute", False)]
    if serverless:
        print(f"  ✅ Found {len(serverless)} serverless warehouse(s): {', '.join(wh.name for wh in serverless)}")
    else:
        warnings.append("No serverless SQL warehouse found. Workshop notebooks recommend serverless.")
        print(f"  ⚠️  No serverless warehouses found (found {len(warehouses)} warehouse(s) total).")
except Exception as exc:
    warnings.append(f"Could not check warehouses: {exc}")
    print(f"  ⚠️  Could not check: {exc}")

# 1c — Foundation Model API
print("\n[3/5] Checking Foundation Model API...")
try:
    endpoints = {ep.name: ep for ep in w.serving_endpoints.list()}
    if EMBEDDING_MODEL in endpoints:
        print(f"  ✅ Embedding model '{EMBEDDING_MODEL}' is available.")
    else:
        warnings.append(f"Embedding model '{EMBEDDING_MODEL}' not found in serving endpoints. Vector Search index may use a different model.")
        print(f"  ⚠️  Embedding model '{EMBEDDING_MODEL}' not found.")
        print(f"      Available FMAPI endpoints: {', '.join(list(endpoints.keys())[:5])}")

    if GENIE_LLM_MODEL in endpoints:
        print(f"  ✅ LLM model '{GENIE_LLM_MODEL}' is available.")
    else:
        warnings.append(f"LLM model '{GENIE_LLM_MODEL}' not found. Genie space creation may need a different model.")
        print(f"  ⚠️  LLM model '{GENIE_LLM_MODEL}' not found.")
except Exception as exc:
    warnings.append(f"Could not check FMAPI: {exc}")
    print(f"  ⚠️  Could not check: {exc}")

# 1d — Sample data on DBFS
print("\n[4/5] Checking sample data files...")
expected_files = [
    "energy_assets.csv",
    "meter_readings.csv",
    "outage_events.csv",
    "maintenance_work_orders.csv",
    "regulatory_reports.csv",
    "policy_documents.csv",
]
try:
    existing = {f.name.split("/")[-1] for f in dbutils.fs.ls(SAMPLE_DATA_PATH)}
    missing  = [f for f in expected_files if f not in existing]
    if not missing:
        print(f"  ✅ All {len(expected_files)} CSV files found at {SAMPLE_DATA_PATH}")
    else:
        errors.append(
            f"Missing CSV files at {SAMPLE_DATA_PATH}: {', '.join(missing)}. "
            "Upload them first: databricks fs cp -r ./data/sample_data/ dbfs:/tmp/au_workshop/sample_data/"
        )
        print(f"  ❌ Missing files: {', '.join(missing)}")
except Exception as exc:
    errors.append(
        f"Cannot read {SAMPLE_DATA_PATH}: {exc}. "
        "Run: databricks fs cp -r ./data/sample_data/ dbfs:/tmp/au_workshop/sample_data/"
    )
    print(f"  ❌ Path not found: {exc}")

# 1e — Current user permissions
print("\n[5/5] Checking current user identity...")
try:
    me = w.current_user.me()
    print(f"  ✅ Running as: {me.user_name}")
    # Check if user is a workspace admin
    is_admin = any(g.display == "admins" for g in (me.groups or []))
    if is_admin:
        print("  ✅ User is a workspace admin.")
    else:
        warnings.append(
            f"User '{me.user_name}' is not in the 'admins' group. "
            "Some steps (catalog creation, Vector Search endpoint creation) require admin or sufficient privileges."
        )
        print("  ⚠️  User is NOT a workspace admin — some steps may fail on permission checks.")
except Exception as exc:
    print(f"  ⚠️  Could not determine current user: {exc}")

# Summary
print()
if errors:
    print(f"❌ {len(errors)} BLOCKING ERROR(S) — resolve before continuing:")
    for e in errors:
        print(f"   • {e}")
    raise RuntimeError(
        "Prerequisites not met. Resolve the errors above and re-run this cell."
    )
elif warnings:
    print(f"⚠️  {len(warnings)} warning(s) — non-blocking, but review before the workshop:")
    for w_msg in warnings:
        print(f"   • {w_msg}")
    print("\nContinuing with setup...")
else:
    print("✅ All prerequisites met. Proceeding with setup.")

# COMMAND ----------

# MAGIC %md ## 2 — Create Workshop Catalog and Schemas

# COMMAND ----------

print("=" * 60)
print("STEP 2 — CATALOG AND SCHEMA CREATION")
print("=" * 60)

# Create catalog (idempotent — IF NOT EXISTS)
print(f"\nCreating catalog '{CATALOG}'...")
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} COMMENT 'AU AI Workshops — energy sector sample data'")
print(f"  ✅ Catalog '{CATALOG}' ready.")

# Create schemas
for schema in SCHEMAS:
    full_name = f"{CATALOG}.{schema}"
    print(f"Creating schema '{full_name}'...")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {full_name} COMMENT 'AU AI Workshops — {schema} data'")
    print(f"  ✅ Schema '{full_name}' ready.")

# Set default catalog for the session
spark.sql(f"USE CATALOG {CATALOG}")
print(f"\nSession default catalog set to '{CATALOG}'.")

# COMMAND ----------

# MAGIC %md ## 3 — Load Sample Datasets as Delta Tables

# COMMAND ----------

print("=" * 60)
print("STEP 3 — LOADING SAMPLE DATA AS DELTA TABLES")
print("=" * 60)

# Table definitions: (csv_filename, target_schema.table, description, partition_by)
TABLE_DEFS = [
    (
        "energy_assets.csv",
        f"{CATALOG}.{SCHEMA_ENERGY}.energy_assets",
        "Network assets — transformers, substations, cables, poles, meters",
        ["region"],
    ),
    (
        "meter_readings.csv",
        f"{CATALOG}.{SCHEMA_ENERGY}.meter_readings",
        "30-minute interval meter readings (NEM12-style)",
        ["customer_type"],
    ),
    (
        "outage_events.csv",
        f"{CATALOG}.{SCHEMA_ENERGY}.outage_events",
        "Planned and unplanned network outage events with SAIDI/SAIFI",
        ["region", "event_type"],
    ),
    (
        "maintenance_work_orders.csv",
        f"{CATALOG}.{SCHEMA_ENERGY}.maintenance_work_orders",
        "Maintenance work orders linked to energy assets",
        ["work_type", "status"],
    ),
    (
        "regulatory_reports.csv",
        f"{CATALOG}.audit.regulatory_reports",
        "AER, AEMO, and ESC regulatory submissions",
        ["jurisdiction", "report_type"],
    ),
    (
        "policy_documents.csv",
        f"{CATALOG}.{SCHEMA_GOVERNANCE}.policy_documents",
        "Internal policy documents for Vector Search RAG demo",
        ["doc_type"],
    ),
]

loaded_tables = {}

for csv_file, table_name, description, partition_cols in TABLE_DEFS:
    csv_path = f"{SAMPLE_DATA_PATH}/{csv_file}"
    print(f"\nLoading {table_name}...")
    print(f"  Source: {csv_path}")

    # Read CSV — infer schema
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .option("multiLine", "true")       # handles embedded newlines in policy text
        .option("escape", '"')
        .csv(csv_path)
    )

    row_count = df.count()
    print(f"  Rows read: {row_count:,}")

    # Write as Delta, overwriting to make re-runs safe
    # Use partitionBy only for tables with enough rows to benefit
    writer = (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.enableChangeDataFeed", "true")   # required for VS delta sync
    )

    if row_count >= 5000 and partition_cols:
        writer = writer.partitionBy(*partition_cols)

    writer.saveAsTable(table_name)

    # Tag with a comment
    spark.sql(f"COMMENT ON TABLE {table_name} IS '{description}'")

    # Optimise Delta table for query performance
    spark.sql(f"OPTIMIZE {table_name}")

    row_final = spark.table(table_name).count()
    print(f"  ✅ Loaded {row_final:,} rows → {table_name}")
    loaded_tables[table_name] = row_final

print("\n" + "-" * 50)
print("Data load summary:")
for tbl, cnt in loaded_tables.items():
    print(f"  {tbl:<55} {cnt:>8,} rows")
total = sum(loaded_tables.values())
print(f"\n  {'TOTAL':<55} {total:>8,} rows")
print("✅ All tables loaded.")

# COMMAND ----------

# MAGIC %md ## 4 — Create a Vector Search Endpoint

# COMMAND ----------

print("=" * 60)
print("STEP 4 — VECTOR SEARCH ENDPOINT")
print("=" * 60)

from databricks.sdk.service.vectorsearch import EndpointStatusState


def get_or_create_vs_endpoint(endpoint_name: str) -> None:
    """Create a Vector Search endpoint if it doesn't exist, then wait for ONLINE."""
    existing = {ep.name: ep for ep in w.vector_search_endpoints.list_endpoints()}

    if endpoint_name in existing:
        ep = existing[endpoint_name]
        status = str(getattr(ep.endpoint_status, "state", "UNKNOWN")).upper()
        print(f"  Endpoint '{endpoint_name}' already exists (status: {status})")
        if "ONLINE" in status:
            print(f"  ✅ Endpoint is ONLINE.")
            return
        # If provisioning, wait
        print(f"  Waiting for endpoint to become ONLINE...")
    else:
        print(f"  Creating endpoint '{endpoint_name}'...")
        w.vector_search_endpoints.create_endpoint_and_wait(
            name=endpoint_name,
            endpoint_type=EndpointType.STANDARD,
        )
        print(f"  ✅ Endpoint '{endpoint_name}' created.")
        return

    # Poll until ONLINE
    deadline = time.time() + 900  # 15 min max
    while time.time() < deadline:
        ep = w.vector_search_endpoints.get_endpoint(endpoint_name)
        status = str(getattr(ep.endpoint_status, "state", "")).upper()
        if "ONLINE" in status:
            print(f"  ✅ Endpoint ONLINE.")
            return
        print(f"  Still provisioning (state: {status})... waiting 30s")
        time.sleep(30)

    raise TimeoutError(f"Vector Search endpoint '{endpoint_name}' did not become ONLINE within 15 minutes.")


print(f"\nEnsuring Vector Search endpoint '{VS_ENDPOINT_NAME}'...")
get_or_create_vs_endpoint(VS_ENDPOINT_NAME)

# COMMAND ----------

# MAGIC %md ## 5 — Create Vector Search Index on policy_documents

# COMMAND ----------

print("=" * 60)
print("STEP 5 — VECTOR SEARCH INDEX ON policy_documents")
print("=" * 60)

POLICY_TABLE   = f"{CATALOG}.{SCHEMA_GOVERNANCE}.policy_documents"
VS_INDEX_NAME  = f"{CATALOG}.{SCHEMA_GOVERNANCE}.policy_docs_index"

# Enable Change Data Feed on the source table (required for Delta Sync)
print(f"\nEnabling Change Data Feed on '{POLICY_TABLE}'...")
spark.sql(f"ALTER TABLE {POLICY_TABLE} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
print("  ✅ CDF enabled.")

# Create or update the Vector Search index
from databricks.sdk.service.vectorsearch import (
    VectorIndexType,
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    PipelineType,
)

print(f"\nCreating/updating Vector Search index '{VS_INDEX_NAME}'...")

existing_indexes = {}
try:
    for idx in w.vector_search_indexes.list_indexes(endpoint_name=VS_ENDPOINT_NAME):
        existing_indexes[idx.name] = idx
except Exception:
    pass  # empty if no indexes yet

if VS_INDEX_NAME in existing_indexes:
    print(f"  Index '{VS_INDEX_NAME}' already exists — triggering a sync to pick up latest data.")
    try:
        w.vector_search_indexes.sync_index(index_name=VS_INDEX_NAME)
        print("  ✅ Sync triggered.")
    except Exception as exc:
        print(f"  ⚠️  Sync trigger failed (may already be syncing): {exc}")
else:
    print(f"  Creating new Delta Sync index...")
    w.vector_search_indexes.create_index(
        endpoint_name=VS_ENDPOINT_NAME,
        index_type=VectorIndexType.DELTA_SYNC,
        name=VS_INDEX_NAME,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=POLICY_TABLE,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="content",                         # column to embed
                    embedding_model_endpoint_name=EMBEDDING_MODEL,
                )
            ],
            pipeline_type=PipelineType.TRIGGERED,          # sync on-demand; switch to CONTINUOUS in production
        ),
    )
    print(f"  ✅ Index creation initiated.")

# Wait for the index to finish its first sync
print(f"\nWaiting for index sync to complete (can take up to 10 minutes)...")
deadline = time.time() + 700
poll_interval = 20
while time.time() < deadline:
    try:
        idx = w.vector_search_indexes.get_index(VS_INDEX_NAME)
        status = str(getattr(idx, "status", "")).upper()
        sync_status = ""
        if hasattr(idx, "delta_sync_index_spec") and idx.delta_sync_index_spec:
            sync_status = str(getattr(idx.delta_sync_index_spec, "pipeline_id", ""))
        if "ONLINE" in status or "READY" in status:
            print(f"  ✅ Index is ONLINE/READY.")
            break
        elif "FAILED" in status or "ERROR" in status:
            print(f"  ❌ Index entered error state: {status}")
            raise RuntimeError(f"Vector Search index failed: {status}")
        else:
            print(f"  Status: {status or 'PROVISIONING'}... waiting {poll_interval}s")
    except RuntimeError:
        raise
    except Exception as exc:
        print(f"  Polling error (will retry): {exc}")
    time.sleep(poll_interval)
    poll_interval = min(poll_interval + 10, 60)
else:
    print("  ⚠️  Index sync timed out. Check status in Catalog Explorer > Vector Search tab.")
    print("      The workshop can continue — the index may still be syncing in the background.")

# COMMAND ----------

# MAGIC %md ## 6 — Create Genie Space

# COMMAND ----------

print("=" * 60)
print("STEP 6 — GENIE SPACE CREATION")
print("=" * 60)

GENIE_DESCRIPTION = """
You are a data assistant for an Australian regulated energy network operator.
You have access to:
- energy_assets: network infrastructure including transformers, substations, cables, poles, and meters
- meter_readings: 30-minute interval electricity consumption data (NEM12-style)
- outage_events: planned and unplanned network outage events with SAIDI/SAIFI metrics
- maintenance_work_orders: field maintenance activities and findings
- regulatory_reports: AER, AEMO, and ESC compliance and performance submissions
- policy_documents: internal governance and safety policy documents

Answer questions about network performance, asset health, maintenance history,
regulatory compliance, and energy consumption patterns.
Always cite the specific tables and fields you used to derive your answers.
Use Australian terminology (kWh, MVA, SAIDI, SAIFI, NMI, NER, AER, AEMO, ESC).
""".strip()

# Tables to expose in the Genie space
GENIE_TABLES = [
    f"{CATALOG}.{SCHEMA_ENERGY}.energy_assets",
    f"{CATALOG}.{SCHEMA_ENERGY}.meter_readings",
    f"{CATALOG}.{SCHEMA_ENERGY}.outage_events",
    f"{CATALOG}.{SCHEMA_ENERGY}.maintenance_work_orders",
    f"{CATALOG}.audit.regulatory_reports",
    f"{CATALOG}.{SCHEMA_GOVERNANCE}.policy_documents",
]

# Seed questions to pre-populate the Genie space
GENIE_INSTRUCTIONS = [
    "Which regions have the highest number of unplanned outage events in the last 12 months?",
    "What is the average SAIDI by cause category?",
    "Show the 10 assets with the lowest condition score that have not been inspected in the last 2 years.",
    "How many work orders are currently open or in progress, broken down by priority?",
    "What is the total cost of emergency maintenance work orders per region this year?",
    "List all regulatory reports that were submitted late or have a non-compliant status.",
    "Which customer types have the highest average interval_kwh demand?",
    "Show the trend in outage duration by month for the last 24 months.",
]

print("\nAttempting to create Genie Space via SDK...")

try:
    from databricks.sdk.service.dashboards import GenieSpaceRequest

    # Check if a space with the same name already exists
    existing_spaces = {}
    try:
        for sp in w.genie.list_spaces():
            existing_spaces[sp.title] = sp
    except Exception as exc:
        print(f"  ⚠️  Could not list existing Genie spaces: {exc}")

    if GENIE_SPACE_NAME in existing_spaces:
        sp = existing_spaces[GENIE_SPACE_NAME]
        print(f"  Genie Space '{GENIE_SPACE_NAME}' already exists (ID: {sp.id})")
        genie_space_id = sp.id
        print(f"  ✅ Using existing space.")
    else:
        # Create the Genie space
        created = w.genie.create_space(
            title=GENIE_SPACE_NAME,
            description=GENIE_DESCRIPTION,
        )
        genie_space_id = created.id
        print(f"  ✅ Genie Space created. ID: {genie_space_id}")

    # Add tables to the space
    print(f"\nAdding {len(GENIE_TABLES)} table(s) to the Genie Space...")
    for table_ref in GENIE_TABLES:
        try:
            w.genie.add_table_to_space(
                space_id=genie_space_id,
                table_name=table_ref,
            )
            print(f"  ✅ Added: {table_ref}")
        except Exception as exc:
            # May already be added — not fatal
            print(f"  ⚠️  Could not add '{table_ref}': {exc}")

    print(f"\nGenie Space ready.")
    print(f"  Space ID:  {genie_space_id}")
    print(f"  Open URL:  {w.config.host}/sql/genie/{genie_space_id}")

    # Print seed questions for participants
    print("\nSuggested workshop starter questions:")
    for i, q in enumerate(GENIE_INSTRUCTIONS, 1):
        print(f"  {i}. {q}")

except ImportError:
    print("  ⚠️  GenieSpaceRequest not available in this SDK version.")
    print("      Create the Genie Space manually:")
    print("        1. Go to Data Intelligence > Genie in the sidebar")
    print("        2. Click 'New Genie Space'")
    print(f"        3. Title: {GENIE_SPACE_NAME}")
    print("        4. Add the tables listed below:")
    for t in GENIE_TABLES:
        print(f"           - {t}")
    print("        5. Paste the description above into the 'Instructions' field")
except Exception as exc:
    print(f"  ⚠️  Genie Space creation encountered an error: {exc}")
    print("      You can create it manually (instructions printed above).")
    print("      The workshop notebooks do not depend on the Genie Space — it is a bonus demo.")

# COMMAND ----------

# MAGIC %md ## 7 — Smoke Test (End-to-End Validation)

# COMMAND ----------

print("=" * 60)
print("STEP 7 — END-TO-END SMOKE TEST")
print("=" * 60)

smoke_errors   = []
smoke_warnings = []


def smoke(name: str, fn) -> bool:
    """Run a smoke test, return True on success."""
    try:
        result = fn()
        print(f"  ✅ {name}: {result}")
        return True
    except Exception as exc:
        msg = f"{name}: {exc}"
        smoke_errors.append(msg)
        print(f"  ❌ {name}: {exc}")
        return False


print("\n[A] Catalog / Table checks")
smoke(
    "Workshop catalog exists",
    lambda: next(c for c in w.catalogs.list() if c.name == CATALOG).name,
)
smoke(
    "energy_assets row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_ENERGY}.energy_assets').count():,} rows",
)
smoke(
    "meter_readings row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_ENERGY}.meter_readings').count():,} rows",
)
smoke(
    "outage_events row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_ENERGY}.outage_events').count():,} rows",
)
smoke(
    "maintenance_work_orders row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_ENERGY}.maintenance_work_orders').count():,} rows",
)
smoke(
    "regulatory_reports row count",
    lambda: f"{spark.table(f'{CATALOG}.audit.regulatory_reports').count():,} rows",
)
smoke(
    "policy_documents row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_GOVERNANCE}.policy_documents').count():,} rows",
)

print("\n[B] Analytics queries")
smoke(
    "SAIDI by region (GROUP BY)",
    lambda: spark.sql(f"""
        SELECT region, ROUND(AVG(saidi_minutes), 4) AS avg_saidi
        FROM   {CATALOG}.{SCHEMA_ENERGY}.outage_events
        GROUP  BY region
        ORDER  BY avg_saidi DESC
        LIMIT  1
    """).collect()[0]["region"],
)
smoke(
    "Assets needing maintenance (condition_score < 4)",
    lambda: f"{spark.sql(f'SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA_ENERGY}.energy_assets WHERE condition_score < 4').collect()[0][0]} assets",
)
smoke(
    "Average interval kWh by customer_type",
    lambda: spark.sql(f"""
        SELECT customer_type, ROUND(AVG(interval_kwh), 4) AS avg_kwh
        FROM   {CATALOG}.{SCHEMA_ENERGY}.meter_readings
        GROUP  BY customer_type
        ORDER  BY avg_kwh DESC
        LIMIT  1
    """).collect()[0]["customer_type"],
)

print("\n[C] Vector Search")
smoke(
    "VS endpoint reachable",
    lambda: w.vector_search_endpoints.get_endpoint(VS_ENDPOINT_NAME).name,
)


def vs_query_test():
    from databricks.sdk.service.vectorsearch import QueryVectorIndexRequest
    results = w.vector_search_indexes.query_index(
        index_name=VS_INDEX_NAME,
        query_text="data governance and privacy requirements",
        columns=["doc_id", "title", "doc_type"],
        num_results=3,
    )
    hits = results.result.data_array if results.result and results.result.data_array else []
    return f"{len(hits)} document(s) returned"


try:
    smoke("VS index query (semantic search)", vs_query_test)
except Exception:
    smoke_warnings.append("Vector Search index query failed — index may still be syncing. Re-run this cell in 5 minutes.")
    print(f"  ⚠️  VS index query skipped (index may still be syncing).")

print("\n[D] Model API")


def fmapi_test():
    import urllib.request
    ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    host  = ctx.apiUrl().get()
    token = ctx.apiToken().get()

    # Try configured in-region Claude model first, fall back to any available endpoint
    endpoints = {ep.name: ep for ep in w.serving_endpoints.list()}
    test_ep   = GENIE_LLM_MODEL if GENIE_LLM_MODEL in endpoints else (list(endpoints.keys())[0] if endpoints else None)
    if not test_ep:
        return "No serving endpoints available — skipping"

    payload = json.dumps({
        "messages": [{"role": "user", "content": "Respond with only the word READY"}],
        "max_tokens": 5,
    }).encode()
    req = urllib.request.Request(
        f"{host}/serving-endpoints/{test_ep}/invocations",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
        reply = body["choices"][0]["message"]["content"].strip()[:30]
    return f"'{test_ep}' replied: '{reply}'"


smoke("Foundation Model API call", fmapi_test)

# Final summary
print()
print("=" * 60)
print("SMOKE TEST SUMMARY")
print("=" * 60)

if smoke_errors:
    print(f"\n❌ {len(smoke_errors)} test(s) failed:")
    for e in smoke_errors:
        print(f"   • {e}")
else:
    print("\n✅ All smoke tests passed.")

if smoke_warnings:
    print(f"\n⚠️  {len(smoke_warnings)} warning(s):")
    for w_msg in smoke_warnings:
        print(f"   • {w_msg}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## AEMO/NEM Data Tables (Session 3 — Optional)
# MAGIC
# MAGIC Run this section if you are running **Session 3 (AEMO Business User)** or **Workshop 2c (MCP Agents)**.
# MAGIC
# MAGIC This section loads six NEM/AEMO-specific tables into a dedicated `aemo` schema:
# MAGIC
# MAGIC | Table | Rows | Description |
# MAGIC |---|---|---|
# MAGIC | `dispatch_intervals` | 50,000 | 5-minute generator dispatch (coal/gas/wind/solar/hydro/battery) |
# MAGIC | `spot_prices` | 20,000 | 30-minute Regional Reference Prices + FCAS + demand |
# MAGIC | `market_notices` | 500 | LOR/market notices and system normal events |
# MAGIC | `generator_registration` | 200 | Registered NEM generators with capacity and ramp rates |
# MAGIC | `constraint_sets` | 2,000 | Constraint activations (thermal/voltage/stability) |
# MAGIC | `settlement_amounts` | 3,000 | Weekly settlement amounts by participant |
# MAGIC
# MAGIC **Pre-requisite:** upload the AEMO CSVs to DBFS before running:
# MAGIC ```bash
# MAGIC databricks fs cp -r ./data/sample_data/aemo/ dbfs:/tmp/au_workshop/sample_data/aemo/
# MAGIC ```

# COMMAND ----------

dbutils.widgets.text("schema_aemo", "aemo", "6. AEMO/NEM schema")

# COMMAND ----------

SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
AEMO_DATA_PATH = f"{SAMPLE_DATA_PATH}/aemo"

print(f"AEMO schema:      {SCHEMA_AEMO}")
print(f"AEMO data path:   {AEMO_DATA_PATH}")

# COMMAND ----------

print("=" * 60)
print("STEP A — CREATE AEMO SCHEMA")
print("=" * 60)

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA_AEMO} COMMENT 'AU AI Workshops — AEMO/NEM wholesale market data'")
print(f"  ✅ Schema '{CATALOG}.{SCHEMA_AEMO}' ready.")

# COMMAND ----------

print("=" * 60)
print("STEP B — LOAD AEMO TABLES")
print("=" * 60)

# Table definitions: (csv_filename, partition_cols, description)
AEMO_TABLES = [
    (
        "dispatch_intervals",
        ["region_id", "fuel_type"],
        "NEM 5-minute dispatch intervals — coal/gas/wind/solar/hydro/battery generators",
    ),
    (
        "spot_prices",
        ["region_id"],
        "NEM 30-minute spot prices (RRP) and FCAS prices per region",
    ),
    (
        "market_notices",
        [],
        "AEMO market notices including LOR1/LOR2/LOR3 reserve events and system normal",
    ),
    (
        "generator_registration",
        ["region_id", "fuel_type"],
        "NEM registered generator data — capacity, ramp rates, participant details",
    ),
    (
        "constraint_sets",
        ["constraint_type"],
        "NEM constraint activations — thermal, voltage and stability constraints",
    ),
    (
        "settlement_amounts",
        ["run_type"],
        "Weekly NEM settlement amounts by participant — energy, FCAS, interconnector residue",
    ),
]

aemo_loaded = {}

for table_name, partition_cols, description in AEMO_TABLES:
    full_table = f"{CATALOG}.{SCHEMA_AEMO}.{table_name}"
    csv_path   = f"{AEMO_DATA_PATH}/{table_name}.csv"
    print(f"\nLoading {full_table}...")
    print(f"  Source: {csv_path}")

    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .option("multiLine", "true")
        .option("escape", '"')
        .csv(csv_path)
    )

    row_count = df.count()
    print(f"  Rows read: {row_count:,}")

    writer = (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.enableChangeDataFeed", "true")
    )

    if row_count >= 2000 and partition_cols:
        writer = writer.partitionBy(*partition_cols)

    writer.saveAsTable(full_table)
    spark.sql(f"COMMENT ON TABLE {full_table} IS '{description}'")
    spark.sql(f"OPTIMIZE {full_table}")

    row_final = spark.table(full_table).count()
    print(f"  ✅ Loaded {row_final:,} rows → {full_table}")
    aemo_loaded[full_table] = row_final

print("\n" + "-" * 50)
print("AEMO data load summary:")
for tbl, cnt in aemo_loaded.items():
    print(f"  {tbl:<60} {cnt:>8,} rows")
total_aemo = sum(aemo_loaded.values())
print(f"\n  {'TOTAL':<60} {total_aemo:>8,} rows")
print("✅ All AEMO tables loaded.")

# COMMAND ----------

print("=" * 60)
print("STEP C — AEMO SMOKE TESTS")
print("=" * 60)

aemo_errors = []


def aemo_smoke(name: str, fn) -> bool:
    try:
        result = fn()
        print(f"  ✅ {name}: {result}")
        return True
    except Exception as exc:
        aemo_errors.append(f"{name}: {exc}")
        print(f"  ❌ {name}: {exc}")
        return False


aemo_smoke(
    "dispatch_intervals row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_AEMO}.dispatch_intervals').count():,} rows",
)
aemo_smoke(
    "spot_prices row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_AEMO}.spot_prices').count():,} rows",
)
aemo_smoke(
    "market_notices row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_AEMO}.market_notices').count():,} rows",
)
aemo_smoke(
    "generator_registration row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_AEMO}.generator_registration').count():,} rows",
)
aemo_smoke(
    "constraint_sets row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_AEMO}.constraint_sets').count():,} rows",
)
aemo_smoke(
    "settlement_amounts row count",
    lambda: f"{spark.table(f'{CATALOG}.{SCHEMA_AEMO}.settlement_amounts').count():,} rows",
)
aemo_smoke(
    "Spot price range (neg prices exist)",
    lambda: f"min={spark.sql(f'SELECT MIN(rrp) FROM {CATALOG}.{SCHEMA_AEMO}.spot_prices').collect()[0][0]:.2f}, "
            f"max={spark.sql(f'SELECT MAX(rrp) FROM {CATALOG}.{SCHEMA_AEMO}.spot_prices').collect()[0][0]:.2f}",
)
aemo_smoke(
    "Solar dispatch zero at night",
    lambda: (
        lambda n: f"{n} nighttime solar intervals correctly at 0 MW"
    )(
        spark.sql(
            f"SELECT COUNT(*) FROM {CATALOG}.{SCHEMA_AEMO}.dispatch_intervals "
            f"WHERE fuel_type='solar' AND HOUR(settlement_date) < 5 AND dispatch_mw = 0"
        ).collect()[0][0]
    ),
)
aemo_smoke(
    "LOR events in market_notices",
    lambda: str(spark.sql(f"SELECT COUNT(*) FROM {CATALOG}.{SCHEMA_AEMO}.market_notices WHERE notice_type LIKE 'LOR%'").collect()[0][0]) + " LOR notices",
)
aemo_smoke(
    "Top region by avg spot price",
    lambda: spark.sql(
        f"SELECT region_id, ROUND(AVG(rrp),2) AS avg_rrp "
        f"FROM {CATALOG}.{SCHEMA_AEMO}.spot_prices "
        f"GROUP BY region_id ORDER BY avg_rrp DESC LIMIT 1"
    ).collect()[0]["region_id"],
)

print()
if aemo_errors:
    print(f"❌ {len(aemo_errors)} AEMO smoke test(s) failed:")
    for e in aemo_errors:
        print(f"   • {e}")
else:
    print("✅ All AEMO smoke tests passed.")

# COMMAND ----------

# MAGIC %md ## 8 — Setup Complete

# COMMAND ----------

print()
print("=" * 60)
print("  WORKSHOP SETUP COMPLETE")
print(f"  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 60)
print()
print("Resources created:")
print(f"  Catalog:             {CATALOG}")
for s in SCHEMAS:
    print(f"  Schema:              {CATALOG}.{s}")
print()
print("  Delta tables:")
for csv_file, table_name, _, _ in TABLE_DEFS:
    count = loaded_tables.get(table_name, "?")
    count_str = f"{count:,}" if isinstance(count, int) else str(count)
    print(f"    {table_name:<55}  {count_str:>8} rows")
print()
print(f"  Vector Search endpoint: {VS_ENDPOINT_NAME}")
print(f"  Vector Search index:    {VS_INDEX_NAME}")
print(f"    Embedded column: content (policy_documents)")
print(f"    Model: {EMBEDDING_MODEL}")
print()
print("  Genie Space: (see Step 6 output for URL)")
print()
print("Next steps for facilitators:")
print("  1. Share the workspace URL with participants")
print("  2. Add participants to the 'workshop_participants' group (or grant UC SELECT)")
print("  3. Open the Genie Space and test a few starter questions")
print("  4. Confirm the Vector Search index status is ONLINE in Catalog Explorer")
print()
print("Workshop notebooks are in:")
print("  /Workspace/Repos/<your-repo>/databricks-au-ai-workshops/")
print()

if smoke_errors:
    print(f"⚠️  Note: {len(smoke_errors)} smoke test(s) failed. Review the errors in Step 7 before the workshop.")
else:
    print("✅ Ready for the workshop. All systems go.")
