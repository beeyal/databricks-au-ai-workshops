# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 36px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 04: MCP Integration (Model Context Protocol)
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">
# MAGIC     Workshop: Genie Code for Developers — Australian Regulated Industries
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>45 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01, 02, 03 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All endpoints: AU East
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you'll learn
# MAGIC
# MAGIC | # | Topic | Time |
# MAGIC |---|-------|------|
# MAGIC | 1 | What MCP is and how Databricks implements it | 5 min |
# MAGIC | 2 | Connecting to Genie Space via MCP | 10 min |
# MAGIC | 3 | Connecting to Vector Search via MCP | 10 min |
# MAGIC | 4 | Calling UC Functions via MCP | 5 min |
# MAGIC | 5 | Building a multi-MCP energy operations agent | 10 min |
# MAGIC | 6 | Best practices for regulated environments | 5 min |
# MAGIC | 7 | Try it yourself — extend the agent | open-ended |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What is MCP?
# MAGIC
# MAGIC **Model Context Protocol (MCP)** is an open standard (Anthropic, 2024) that lets AI agents
# MAGIC connect to data sources and tools through a uniform HTTP interface — similar to how REST
# MAGIC standardises API communication.
# MAGIC
# MAGIC In Databricks, MCP is exposed as authenticated HTTP endpoints on your workspace:
# MAGIC
# MAGIC | MCP Endpoint | What it provides |
# MAGIC |--------------|-----------------|
# MAGIC | `/api/2.0/mcp/genie/{space_id}` | Natural language → SQL via a Genie Space |
# MAGIC | `/api/2.0/mcp/vector-search/{catalog}/{schema}/{index_name}` | Semantic search over a Vector Search index |
# MAGIC | `/api/2.0/mcp/functions/{catalog}/{schema}` | Calls UC functions as AI tools |
# MAGIC
# MAGIC ### Why MCP matters for regulated industries
# MAGIC
# MAGIC | Concern | MCP answer |
# MAGIC |---------|-----------|
# MAGIC | **Data residency** | All Databricks MCP endpoints are workspace-local (AU East) |
# MAGIC | **Auth and access control** | Databricks PAT or OAuth — same controls as any API call |
# MAGIC | **Auditability** | Every MCP call is logged in Databricks audit logs |
# MAGIC | **No external dependencies** | Client library runs locally; server is your workspace |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Architecture for this lab
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────┐
# MAGIC │           Energy Operations Agent (AU East)              │
# MAGIC │                                                          │
# MAGIC │  User question (natural language)                        │
# MAGIC │       ↓                                                  │
# MAGIC │  Claude Sonnet 4.6 (Provisioned Throughput)             │
# MAGIC │       ↓  decides which tool to call                      │
# MAGIC │  ┌────┴──────────┬───────────┬──────────────────────┐   │
# MAGIC │  │  Genie MCP    │  VS MCP   │  UC Functions MCP    │   │
# MAGIC │  │  NL→SQL over  │  Policy   │  calculate_peak      │   │
# MAGIC │  │  meter tables │  doc RAG  │  lookup_asset        │   │
# MAGIC │  └───────────────┴───────────┴──────────────────────┘   │
# MAGIC │              All endpoints in Australia East             │
# MAGIC └─────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   ⚙️  Section 1 — Setup
# MAGIC </div>

# COMMAND ----------

%pip install openai databricks-sdk mlflow --quiet
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Configure workspace settings
# MAGIC
# MAGIC > **TODO:** Update the four variables below before running this cell.

# COMMAND ----------

import os
import json
import requests
from databricks.sdk import WorkspaceClient

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Workshop Configuration
# MAGIC > **Running in a customer environment?** Change the catalog name in the widget above to match
# MAGIC > what was set in `setup/00_workspace_setup.py` (default: `workshop_au`)

# COMMAND ----------
# Widget-based configuration — works in any customer Databricks environment
# These default values match what 00_workspace_setup.py creates
dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",      "workshop_lab",         "Schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
PT_ENDPOINT  = dbutils.widgets.get("pt_endpoint")

print(f"Using catalog: {CATALOG}.{SCHEMA}")
print(f"PT endpoint:   {PT_ENDPOINT}")

# COMMAND ----------

# TODO: Update these values for your workspace
WORKSPACE_URL  = "https://adb-XXXXXXXXXXXXXXXXX.X.azuredatabricks.net"  # TODO: your workspace URL
# Configurable — change via widget above if running in customer environment
# CATALOG and SCHEMA are set by widgets above

# TODO: Fill in your Genie Space ID — see Section 2 UI guide below for how to find it
GENIE_SPACE_ID = "XXXXXXXXXXXX"  # TODO: your Genie Space ID

# TODO: Fill in your Vector Search index name (full 3-part name)
# If you don't have one, Section 3 shows how to create one
VS_INDEX_NAME  = f"{CATALOG}.{SCHEMA}.policy_docs_index"  # adjust if different

# Databricks token — uses the notebook token automatically inside Databricks
# For external clients, use a PAT from User Settings > Access Tokens
DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

print(f"Workspace: {WORKSPACE_URL}")
print(f"Catalog/Schema: {CATALOG}.{SCHEMA}")
print(f"Genie Space: {GENIE_SPACE_ID}")
print(f"VS Index: {VS_INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workspace: https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC Catalog/Schema: main.workshop_lab
# MAGIC Genie Space: XXXXXXXXXXXX        (will show your ID once you fill it in)
# MAGIC VS Index: main.workshop_lab.policy_docs_index
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖥️  UI Guide — Understanding MCP Endpoints in Databricks
# MAGIC </div>
# MAGIC
# MAGIC MCP endpoints are standard authenticated HTTP endpoints on your workspace.
# MAGIC There is no separate UI configuration needed — just use your PAT for authentication.
# MAGIC
# MAGIC ```
# MAGIC Available MCP endpoints (replace {WORKSPACE_URL} with your workspace URL):
# MAGIC
# MAGIC ┌─────────────────────────────────────────────────────────────────┐
# MAGIC │  Genie:          POST {WORKSPACE_URL}/api/2.0/mcp/genie/        │
# MAGIC │                            {space_id}                           │
# MAGIC │                                                                 │
# MAGIC │  Vector Search:  POST {WORKSPACE_URL}/api/2.0/mcp/vector-search/│
# MAGIC │                            {catalog}/{schema}/{index_name}       │
# MAGIC │                                                                 │
# MAGIC │  UC Functions:   POST {WORKSPACE_URL}/api/2.0/mcp/functions/    │
# MAGIC │                            {catalog}/{schema}                   │
# MAGIC │                                                                 │
# MAGIC │  Authentication: Authorization: Bearer {your_pat_token}         │
# MAGIC │  Data stays in:  Australia East                                 │
# MAGIC └─────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **These endpoints receive and return MCP protocol messages** — JSON payloads with
# MAGIC `method` and `params` fields. The agent client formats them; you don't write the
# MAGIC raw MCP protocol yourself.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   💬  Section 2 — MCP Tool 1: Genie Space (Natural Language to SQL)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC The Genie MCP endpoint lets an agent ask natural-language questions against a Genie Space.
# MAGIC The Genie Space handles the NL to SQL translation and executes the query.
# MAGIC
# MAGIC ### Endpoint format
# MAGIC ```
# MAGIC POST {WORKSPACE_URL}/api/2.0/mcp/genie/{space_id}
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖥️  UI Guide — Finding Your Genie Space ID
# MAGIC </div>
# MAGIC
# MAGIC The Genie Space ID is in the browser URL when you open your Genie Space:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Genie (left sidebar) → click your "Energy Operations Workshop" space
# MAGIC           → look at the browser URL bar
# MAGIC
# MAGIC ┌─── How to find it ──────────────────────────────────────────┐
# MAGIC │  1. Click Genie in the left sidebar                         │
# MAGIC │  2. Click on your "Energy Operations Workshop" space        │
# MAGIC │  3. Look at the browser URL bar:                            │
# MAGIC │                                                             │
# MAGIC │     https://adb-xxxx.azuredatabricks.net/genie/spaces/      │
# MAGIC │                                              ↑ copy from here│
# MAGIC │     01jf3k2m9xyz456abc                                      │
# MAGIC │                                                             │
# MAGIC │  Your GENIE_SPACE_ID = "01jf3k2m9xyz456abc"                │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### If you do not have a Genie Space yet — create one (3 minutes)
# MAGIC
# MAGIC A Genie Space needs at least one table to query. Use the meter tables from Lab 03:
# MAGIC
# MAGIC ```
# MAGIC 1. Click Genie in the left sidebar
# MAGIC 2. Click "New Genie Space" (top right)
# MAGIC 3. Name it: "Energy Operations Workshop"
# MAGIC 4. Add tables:
# MAGIC      main.workshop_lab.interval_reads
# MAGIC      main.workshop_lab.asset_maintenance
# MAGIC 5. In the description box, add:
# MAGIC      "NEM meter interval reads and asset maintenance data for NSW and VIC operations."
# MAGIC 6. Click Save
# MAGIC 7. Copy the Space ID from the URL and paste it into GENIE_SPACE_ID above
# MAGIC ```

# COMMAND ----------

def call_genie_mcp(question: str, space_id: str, workspace_url: str, token: str) -> dict:
    """Call the Genie Space MCP endpoint with a natural language question.

    Args:
        question: Natural language question to ask the Genie Space.
        space_id: The Genie Space ID (from the URL in the Genie UI).
        workspace_url: Full Databricks workspace URL (no trailing slash).
        token: Databricks personal access token.

    Returns:
        Dictionary with the MCP response including the generated answer and SQL.
    """
    endpoint = f"{workspace_url}/api/2.0/mcp/genie/{space_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # MCP uses the standard tools/call protocol
    payload = {
        "method": "tools/call",
        "params": {
            "name": "genie_query",
            "arguments": {
                "question": question,
            }
        }
    }

    response = requests.post(endpoint, headers=headers, json=payload, timeout=60)

    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": f"HTTP {response.status_code}",
            "detail": response.text[:500],
        }


# Test: ask the Genie Space a question about meter data
if GENIE_SPACE_ID != "XXXXXXXXXXXX":
    result = call_genie_mcp(
        question="What is the total consumption in kWh for each NMI in the dataset?",
        space_id=GENIE_SPACE_ID,
        workspace_url=WORKSPACE_URL,
        token=DATABRICKS_TOKEN,
    )
    print(json.dumps(result, indent=2, default=str))
else:
    print("GENIE_SPACE_ID not set — update the TODO in Section 1 and re-run this cell.")
    print("Continuing with mock Genie responses for the rest of the lab demonstration.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (with a valid Genie Space ID):**
# MAGIC ```json
# MAGIC {
# MAGIC   "content": [
# MAGIC     {
# MAGIC       "type": "text",
# MAGIC       "text": "The total consumption for NMI 6001234567 across all dates is 378.4 kWh."
# MAGIC     }
# MAGIC   ]
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC **If GENIE_SPACE_ID is not set yet:**
# MAGIC ```
# MAGIC GENIE_SPACE_ID not set — update the TODO in Section 1 and re-run this cell.
# MAGIC Continuing with mock Genie responses for the rest of the lab demonstration.
# MAGIC ```
# MAGIC
# MAGIC **Why use Genie MCP instead of raw SQL?**
# MAGIC - Operators ask questions in plain English without knowing table schemas
# MAGIC - Genie handles schema changes automatically — no query updates when columns are renamed
# MAGIC - Genie Space context window includes your business descriptions and instructions

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🔍  Section 3 — MCP Tool 2: Vector Search (Semantic Document Search)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC The Vector Search MCP endpoint enables semantic search over a Databricks Vector Search index.
# MAGIC We'll use it to search a corpus of regulatory policy documents.
# MAGIC
# MAGIC ### 3.1 — Create a regulatory documents table
# MAGIC
# MAGIC First, create the source table with synthetic AER/AEMO regulatory content.

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, IntegerType

policy_docs = [
    (1, "SAIDI Reporting Requirements",
     "SAIDI (System Average Interruption Duration Index) measures the total duration of "
     "interruptions per customer per year. Under AER Service Target Performance Incentive "
     "Scheme (STPIS), distributors must report SAIDI annually. The threshold for NSW "
     "distribution networks is 250 minutes per customer per year. Breaches attract financial "
     "penalties calculated at AUD 15,000 per customer per minute above threshold."),
    (2, "NEM12 Data Quality Standards",
     "NEM12 files must contain 48 interval records per day per meter. Quality flags must be: "
     "A (Actual) for meter-read data, E (Estimated) for data substituted by estimation, "
     "S (Substituted) for data replaced by MDMA. Estimated reads exceeding 5% of intervals "
     "in a billing period require mandatory customer notification under National Energy Retail "
     "Rules clause 46."),
    (3, "Critical Peak Demand Management",
     "During network emergencies, AEMO may issue an Emergency Backstop Mechanism (EBM) "
     "direction. Retailers must curtail consumption by 10% within 30 minutes of an EBM notice. "
     "Non-compliance incurs penalties under National Electricity Rules clause 4.10.3. Smart "
     "meters with interval data are mandatory for EBM-eligible customers above 160 MWh per year."),
    (4, "Meter Data Retention Policy",
     "Under the Privacy Act 1988 and the National Energy Retail Rules, meter data must be "
     "retained for a minimum of 7 years. Data must be stored in Australia (s.16C Privacy Act). "
     "Access by third parties requires customer explicit consent via a signed metering data "
     "authorisation form. Retailers must provide customers with access to their own data within "
     "5 business days of request."),
    (5, "Voltage Quality Compliance",
     "Distribution network service providers must maintain supply voltage within -6% to +10% of "
     "nominal voltage (230V) at the customer's connection point. Monitoring is required at "
     "representative points across the network. Exceedances must be reported to AER quarterly. "
     "Persistent exceedances (>5% of measured intervals in a month) trigger an obligation to "
     "invest in network remediation within 12 months."),
]

schema = StructType([
    StructField("doc_id",  IntegerType(), False),
    StructField("title",   StringType(),  True),
    StructField("content", StringType(),  True),
])

df_docs = spark.createDataFrame(policy_docs, schema=schema)
df_docs.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_policy_docs")

print(f"Created {CATALOG}.{SCHEMA}.regulatory_policy_docs with {df_docs.count()} documents:")
df_docs.select("doc_id", "title").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Created main.workshop_lab.regulatory_policy_docs with 5 documents:
# MAGIC +------+------------------------------------+
# MAGIC |doc_id|title                               |
# MAGIC +------+------------------------------------+
# MAGIC |1     |SAIDI Reporting Requirements        |
# MAGIC |2     |NEM12 Data Quality Standards        |
# MAGIC |3     |Critical Peak Demand Management     |
# MAGIC |4     |Meter Data Retention Policy         |
# MAGIC |5     |Voltage Quality Compliance          |
# MAGIC +------+------------------------------------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Create the Vector Search endpoint and index
# MAGIC
# MAGIC **Option A — Use the UI (recommended for the lab):**
# MAGIC ```
# MAGIC 1. Compute (left sidebar) → Vector Search → Create Endpoint
# MAGIC    - Name: workshop-vs-endpoint
# MAGIC    - Type: Standard
# MAGIC    - Click Create (takes ~5 minutes on first creation)
# MAGIC
# MAGIC 2. Data (left sidebar) → main → workshop_lab → regulatory_policy_docs
# MAGIC    → Click "Create Vector Search Index" button
# MAGIC    - Source table: main.workshop_lab.regulatory_policy_docs
# MAGIC    - Index type: Delta Sync
# MAGIC    - Embedding column: content
# MAGIC    - Embedding model: databricks-gte-large-en
# MAGIC    - Primary key: doc_id
# MAGIC    - Endpoint: workshop-vs-endpoint
# MAGIC    → Click Create
# MAGIC
# MAGIC 3. Wait for the index status to show "Online" before running Section 3.3
# MAGIC ```
# MAGIC
# MAGIC **Option B — Use the SDK (run the cells below):**

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn, PipelineType
)

w = WorkspaceClient()

VS_ENDPOINT_NAME = "workshop-vs-endpoint"  # change if you have an existing endpoint

# Create endpoint (skip if already exists)
try:
    w.vector_search_endpoints.create_endpoint(
        name=VS_ENDPOINT_NAME,
        endpoint_type=EndpointType.STANDARD,
    )
    print(f"Created VS endpoint: {VS_ENDPOINT_NAME}")
    print("Waiting for endpoint to come ONLINE (first creation takes ~5 minutes)...")
    w.vector_search_endpoints.wait_get_endpoint_vector_search_endpoint_online(VS_ENDPOINT_NAME)
    print("Endpoint is ONLINE.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Endpoint {VS_ENDPOINT_NAME} already exists — skipping creation.")
    else:
        print(f"Endpoint note: {e}")

# COMMAND ----------

# Create the Vector Search index
try:
    w.vector_search_indexes.create_index(
        name=f"{CATALOG}.{SCHEMA}.policy_docs_index",
        endpoint_name=VS_ENDPOINT_NAME,
        primary_key="doc_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=f"{CATALOG}.{SCHEMA}.regulatory_policy_docs",
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="content",
                    embedding_model_endpoint_name="databricks-gte-large-en",
                )
            ],
        ),
    )
    print(f"Created index: {CATALOG}.{SCHEMA}.policy_docs_index")
    print("Index is syncing — check status in the Catalog UI.")
    print("Wait 2-3 minutes before running the search test below.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Index already exists — triggering sync...")
        w.vector_search_indexes.sync_index(f"{CATALOG}.{SCHEMA}.policy_docs_index")
        print("Sync triggered.")
    else:
        print(f"Index note: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Endpoint workshop-vs-endpoint already exists — skipping creation.
# MAGIC Index already exists — triggering sync...
# MAGIC Sync triggered.
# MAGIC ```
# MAGIC (Or "Created VS endpoint / Created index" if this is your first run.)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Test the Vector Search tool

# COMMAND ----------

def search_policy_docs(query: str, index_name: str, num_results: int = 3) -> list:
    """Search regulatory policy documents using Vector Search semantic similarity.

    Args:
        query: Natural language search query.
        index_name: Full 3-part Unity Catalog name of the Vector Search index.
        num_results: Number of documents to return (default 3).

    Returns:
        List of dicts with 'doc_id', 'title', 'content', and similarity score.
    """
    w = WorkspaceClient()

    try:
        results = w.vector_search_indexes.query_index(
            index_name=index_name,
            columns=["doc_id", "title", "content"],
            query_text=query,
            num_results=num_results,
        )

        docs = []
        if results.result and results.result.data_array:
            col_names = [c.name for c in results.result.manifest.columns]
            for row in results.result.data_array:
                doc = dict(zip(col_names, row))
                docs.append(doc)
        return docs

    except Exception as e:
        return [{"error": str(e)}]


# Test the Vector Search tool
test_query = "What are the penalties for exceeding SAIDI limits in NSW?"
results = search_policy_docs(test_query, VS_INDEX_NAME)

print(f"Query: '{test_query}'")
print(f"\nTop {len(results)} results:")
for i, r in enumerate(results, 1):
    if "error" in r:
        print(f"  {i}. ERROR: {r['error']}")
        print("     (Index may still be syncing — wait 2-3 minutes and retry)")
    else:
        print(f"  {i}. [{r.get('doc_id')}] {r.get('title')}")
        print(f"     {str(r.get('content', ''))[:120]}...")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Query: 'What are the penalties for exceeding SAIDI limits in NSW?'
# MAGIC
# MAGIC Top 3 results:
# MAGIC   1. [1] SAIDI Reporting Requirements
# MAGIC      SAIDI (System Average Interruption Duration Index) measures the total duration of
# MAGIC      interruptions per customer per year...
# MAGIC   2. [5] Voltage Quality Compliance
# MAGIC      Distribution network service providers must maintain supply voltage within -6% to +10%...
# MAGIC   3. [3] Critical Peak Demand Management
# MAGIC      During network emergencies, AEMO may issue an Emergency Backstop Mechanism (EBM)...
# MAGIC ```
# MAGIC
# MAGIC > If you see an error about the index not being ready, wait 2-3 minutes and re-run.
# MAGIC > Vector Search indexes need time to embed and sync the source table on first creation.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🔧  Section 4 — MCP Tool 3: UC Functions via MCP
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC The UC Functions MCP endpoint exposes Unity Catalog functions as MCP tools.
# MAGIC Any MCP-compatible client can call your UC functions using this standard interface.
# MAGIC
# MAGIC ### Endpoint format
# MAGIC ```
# MAGIC POST {WORKSPACE_URL}/api/2.0/mcp/functions/{catalog}/{schema}
# MAGIC ```
# MAGIC
# MAGIC For built-in Databricks AI functions registered in `system.ai`:
# MAGIC ```
# MAGIC POST {WORKSPACE_URL}/api/2.0/mcp/functions/system/ai
# MAGIC ```

# COMMAND ----------

def call_uc_function_via_mcp(
    function_name: str,
    arguments: dict,
    catalog: str,
    schema: str,
    workspace_url: str,
    token: str,
) -> dict:
    """Call a Unity Catalog function via the MCP functions endpoint.

    Args:
        function_name: The function name (without catalog.schema prefix).
        arguments: Dict of argument name to value.
        catalog: UC catalog containing the function.
        schema: UC schema containing the function.
        workspace_url: Databricks workspace URL.
        token: Databricks PAT or OAuth token.

    Returns:
        Dict with the function result or error information.
    """
    endpoint = f"{workspace_url}/api/2.0/mcp/functions/{catalog}/{schema}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "method": "tools/call",
        "params": {
            "name": function_name,
            "arguments": arguments,
        }
    }

    response = requests.post(endpoint, headers=headers, json=payload, timeout=30)

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"HTTP {response.status_code}", "detail": response.text[:400]}


# Test: call calculate_peak_demand via MCP
result = call_uc_function_via_mcp(
    function_name="calculate_peak_demand",
    arguments={
        "nmi": "6001234567",
        "start_date": "2024-07-01",
        "end_date": "2024-07-07",
    },
    catalog=CATALOG,
    schema=SCHEMA,
    workspace_url=WORKSPACE_URL,
    token=DATABRICKS_TOKEN,
)
print("UC Function via MCP result:")
print(json.dumps(result, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```json
# MAGIC UC Function via MCP result:
# MAGIC {
# MAGIC   "content": [
# MAGIC     {
# MAGIC       "type": "text",
# MAGIC       "text": "{\"nmi\": \"6001234567\", \"peak_kwh\": 2.49, \"peak_date\": \"2024-07-04\",
# MAGIC                \"peak_interval_number\": 35, \"peak_time_approx\": \"17:00\",
# MAGIC                \"date_range\": \"2024-07-01 to 2024-07-07\"}"
# MAGIC     }
# MAGIC   ]
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC > The MCP response wraps the UC function's return value in a standard `content` array.
# MAGIC > This is the same MCP response format used by Genie and Vector Search endpoints.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🤖  Section 5 — Building the Multi-MCP Energy Operations Agent
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Now we combine all three MCP tools into a single agent using the OpenAI Agents SDK.
# MAGIC
# MAGIC > **Why OpenAI Agents SDK?** Databricks MCP endpoints implement the MCP specification,
# MAGIC > which the OpenAI Agents SDK supports natively. It is a client-side library only —
# MAGIC > it never sends data to OpenAI servers. All API calls go to your Databricks workspace URL.

# COMMAND ----------

from openai import OpenAI
import json

# Point the OpenAI client at your Databricks workspace
# base_url tells it to use Databricks endpoints, not OpenAI's servers
llm_client = OpenAI(
    base_url=f"{WORKSPACE_URL}/serving-endpoints",
    api_key=DATABRICKS_TOKEN,
)

# Verify connectivity
try:
    models = llm_client.models.list()
    model_ids = [m.id for m in models.data]
    print(f"Connected to workspace. Available models ({len(model_ids)}):")
    for m in model_ids[:5]:
        print(f"  - {m}")
    if len(model_ids) > 5:
        print(f"  ... and {len(model_ids) - 5} more")
except Exception as e:
    print(f"Connection error: {e}")
    print("Check WORKSPACE_URL and DATABRICKS_TOKEN in Section 1.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Connected to workspace. Available models (12):
# MAGIC   - databricks-claude-sonnet-4-6
# MAGIC   - databricks-claude-haiku-3-5
# MAGIC   - databricks-meta-llama-3-3-70b-instruct
# MAGIC   - databricks-mixtral-8x7b-instruct
# MAGIC   - databricks-gte-large-en
# MAGIC   ... and 7 more
# MAGIC ```

# COMMAND ----------

# ---- Tool definitions (OpenAI function-calling format) ----
tools_spec = [
    {
        "type": "function",
        "function": {
            "name": "query_genie_space",
            "description": (
                "Ask a natural language question about meter consumption data, NMI registers, "
                "or billing data. The Genie Space translates your question to SQL and executes it. "
                "Use for questions about consumption trends, totals, averages, or comparisons "
                "across meters or time periods."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the energy data "
                                       "(e.g., 'What is the total consumption for NMI 6001234567 in July 2024?')",
                    }
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy_documents",
            "description": (
                "Search regulatory policy and compliance documents using semantic similarity. "
                "Use when asked about AER requirements, SAIDI/SAIFI limits, NEM12 standards, "
                "data retention obligations, privacy rules, or any regulatory compliance question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The regulatory or compliance question to search for.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of relevant documents to retrieve (default 3).",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_peak_demand",
            "description": (
                "Calculate the peak 30-minute demand for a specific NEM meter (NMI) over a date range. "
                "Returns the maximum half-hour energy read and when it occurred. "
                "Use for questions about peak load, maximum demand, or demand profiling for a specific meter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nmi": {
                        "type": "string",
                        "description": "National Meter Identifier (10-digit, e.g., '6001234567')",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (inclusive)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (inclusive)",
                    },
                },
                "required": ["nmi", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_asset_status",
            "description": (
                "Look up the maintenance history and operational status of a network asset. "
                "Returns work orders year-to-date, total outage minutes, and cost. "
                "Use for questions about asset condition, maintenance history, or SAIDI contribution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {
                        "type": "string",
                        "description": "The unique asset identifier (e.g., 'TF-NSW-001')",
                    }
                },
                "required": ["asset_id"],
            },
        },
    },
]

print(f"Defined {len(tools_spec)} tool specifications.")

# COMMAND ----------

# ---- Tool execution router ----
def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Route a tool call from the LLM to the appropriate MCP endpoint or function."""

    if tool_name == "query_genie_space":
        if GENIE_SPACE_ID == "XXXXXXXXXXXX":
            # Mock response when Genie Space is not configured
            return json.dumps({
                "answer": "Genie Space not configured. Update GENIE_SPACE_ID in Section 1.",
                "note": "In production this returns SQL results from your Genie Space."
            })
        result = call_genie_mcp(
            question=tool_args["question"],
            space_id=GENIE_SPACE_ID,
            workspace_url=WORKSPACE_URL,
            token=DATABRICKS_TOKEN,
        )
        return json.dumps(result, default=str)

    elif tool_name == "search_policy_documents":
        results = search_policy_docs(
            query=tool_args["query"],
            index_name=VS_INDEX_NAME,
            num_results=tool_args.get("num_results", 3),
        )
        if results and "error" in results[0]:
            return json.dumps({
                "error": results[0]["error"],
                "note": "Vector Search index may still be syncing. Wait 2-3 minutes and retry."
            })
        # Return titles + excerpts — not full content — to keep token usage low
        return json.dumps([
            {"title": r.get("title", ""), "excerpt": str(r.get("content", ""))[:300]}
            for r in results
        ])

    elif tool_name == "calculate_peak_demand":
        result = call_uc_function_via_mcp(
            function_name="calculate_peak_demand",
            arguments=tool_args,
            catalog=CATALOG,
            schema=SCHEMA,
            workspace_url=WORKSPACE_URL,
            token=DATABRICKS_TOKEN,
        )
        return json.dumps(result, default=str)

    elif tool_name == "lookup_asset_status":
        result = call_uc_function_via_mcp(
            function_name="lookup_asset_status",
            arguments=tool_args,
            catalog=CATALOG,
            schema=SCHEMA,
            workspace_url=WORKSPACE_URL,
            token=DATABRICKS_TOKEN,
        )
        return json.dumps(result, default=str)

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

# COMMAND ----------

# ---- Agent loop ----
def run_energy_agent(user_question: str, verbose: bool = True) -> str:
    """Run the energy operations agent with multi-MCP tool access.

    Args:
        user_question: The operator's question in natural language.
        verbose: If True, print tool calls as they happen (useful for debugging and demos).

    Returns:
        The agent's final answer as a string.
    """
    system_message = {
        "role": "system",
        "content": (
            "You are an expert energy operations assistant for an Australian electricity "
            "network operator. You help operations staff with:\n"
            "  - Meter data analysis (NEM12 interval reads, NMI registers)\n"
            "  - Regulatory compliance (AER, AEMO, SAIDI/SAIFI reporting)\n"
            "  - Asset maintenance and reliability analysis\n\n"
            "Always use your tools to answer questions — never guess values. "
            "When you have results, provide a clear, actionable summary. "
            "Reference specific numbers, dates, and regulatory requirements where relevant."
        )
    }

    messages = [
        system_message,
        {"role": "user", "content": user_question},
    ]

    max_iterations = 6  # Prevent infinite tool loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = llm_client.chat.completions.create(
            model="databricks-claude-sonnet-4-6",
            messages=messages,
            tools=tools_spec,
            tool_choice="auto",
            temperature=0.0,
            max_tokens=2048,
        )

        choice = response.choices[0]
        message = choice.message

        # Add assistant message to conversation history
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in (message.tool_calls or [])
            ] or None,
        })

        # If no tool calls, we have the final answer
        if not message.tool_calls:
            return message.content or ""

        # Execute each tool call and feed results back
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            if verbose:
                print(f"\n[Tool call] {tool_name}({json.dumps(tool_args, indent=2)})")

            tool_result = execute_tool(tool_name, tool_args)

            if verbose:
                preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                print(f"[Tool result] {preview}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

    return "Max iterations reached. Partial answer: " + (message.content or "")

print("Multi-MCP agent defined and ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Multi-MCP agent defined and ready.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🧪  Section 6 — Testing the Multi-MCP Agent
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.1 — Meter data question (UC Function)

# COMMAND ----------

answer = run_energy_agent(
    "What was the peak demand for meter 6001234567 during the first week of July 2024, "
    "and at what time of day did it occur?",
    verbose=True,
)
print("\n" + "="*60)
print("FINAL ANSWER:")
print("="*60)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC [Tool call] calculate_peak_demand({
# MAGIC   "nmi": "6001234567",
# MAGIC   "start_date": "2024-07-01",
# MAGIC   "end_date": "2024-07-07"
# MAGIC })
# MAGIC [Tool result] {"content": [{"type": "text", "text": "{\"nmi\": \"6001234567\", \"peak_kwh\": 2.49...
# MAGIC
# MAGIC ============================================================
# MAGIC FINAL ANSWER:
# MAGIC ============================================================
# MAGIC The peak demand for meter 6001234567 during 1-7 July 2024 was 2.49 kWh in a single
# MAGIC 30-minute interval. This occurred on 4 July 2024 at approximately 17:00, which is
# MAGIC interval 35 in NEM12 notation (counting from midnight in 30-minute blocks).
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.2 — Regulatory compliance question (Vector Search)

# COMMAND ----------

answer = run_energy_agent(
    "Our meter for NMI 6001234567 has about 3% estimated reads this month. "
    "Does this comply with NEM12 standards, and do we need to notify the customer?",
    verbose=True,
)
print("\n" + "="*60)
print("FINAL ANSWER:")
print("="*60)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC [Tool call] search_policy_documents({
# MAGIC   "query": "NEM12 estimated reads compliance customer notification threshold"
# MAGIC })
# MAGIC [Tool result] [{"title": "NEM12 Data Quality Standards", "excerpt": "NEM12 files must contain...
# MAGIC
# MAGIC ============================================================
# MAGIC FINAL ANSWER:
# MAGIC ============================================================
# MAGIC A 3% estimated read rate complies with NEM12 standards. Under the National Energy Retail
# MAGIC Rules clause 46, customer notification is only required when estimated reads exceed 5% of
# MAGIC intervals in a billing period. At 3%, you are below this threshold and no notification is
# MAGIC required. However, it is good practice to investigate the cause of the estimated intervals
# MAGIC to prevent the rate climbing above 5% before the billing period closes.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.3 — Asset and compliance cross-reference

# COMMAND ----------

answer = run_energy_agent(
    "Asset TF-NSW-001 has had several maintenance events this year. "
    "How much outage time has it caused? "
    "Based on AER SAIDI requirements, should we be concerned about this asset?",
    verbose=True,
)
print("\n" + "="*60)
print("FINAL ANSWER:")
print("="*60)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.4 — Multi-tool chain (three tools, one question)

# COMMAND ----------

answer = run_energy_agent(
    "Operations briefing for my morning review — I need three things: "
    "1. Peak demand for meter 6001234567 in the first week of July 2024. "
    "2. Maintenance status of asset TF-NSW-001. "
    "3. Are there any regulatory data retention obligations I should be aware of for this meter data?",
    verbose=True,
)
print("\n" + "="*60)
print("FINAL ANSWER:")
print("="*60)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC **What to observe:** In the verbose trace you should see **three separate tool calls** —
# MAGIC one to `calculate_peak_demand`, one to `lookup_asset_status`, and one to
# MAGIC `search_policy_documents` — before the final synthesised answer. This is the LLM
# MAGIC reading the question, decomposing it into sub-problems, and routing each to the
# MAGIC appropriate MCP endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖥️  UI Check — Viewing MCP Agent Traces in MLflow
# MAGIC </div>
# MAGIC
# MAGIC After running the agent exercises, inspect the tool call sequence in MLflow:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar) → Experiments
# MAGIC           → [your experiment name, e.g., "energy-ops-agent"]
# MAGIC           → click a run → Traces tab
# MAGIC
# MAGIC You will see the agent's decision process for each question:
# MAGIC
# MAGIC   User question
# MAGIC       ↓
# MAGIC   LLM decides which tool(s) to call
# MAGIC       ↓
# MAGIC   MCP call to Genie / Vector Search / UC Functions
# MAGIC       ↓
# MAGIC   LLM processes the tool result
# MAGIC       ↓
# MAGIC   Final answer
# MAGIC
# MAGIC For the multi-tool question (6.4), the trace shows:
# MAGIC   AgentRun (total time)
# MAGIC   ├── LLMCall — "I need three things..." → decides to call tools
# MAGIC   ├── ToolCall: calculate_peak_demand (via MCP)
# MAGIC   ├── ToolCall: lookup_asset_status (via MCP)
# MAGIC   ├── ToolCall: search_policy_documents (via Vector Search MCP)
# MAGIC   └── LLMCall — synthesises final answer from three tool results
# MAGIC ```
# MAGIC
# MAGIC > **Why look at traces?** Traces show you exactly which tool the LLM chose to call,
# MAGIC > with what arguments, and how long each call took. This is essential for debugging
# MAGIC > unexpected agent behaviour and for demonstrating the agent's reasoning to stakeholders.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🔐  Section 7 — Best Practices for MCP in Regulated Environments
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Authentication
# MAGIC
# MAGIC | Method | Use case | Recommendation |
# MAGIC |--------|----------|----------------|
# MAGIC | PAT (Personal Access Token) | Development / notebooks | OK for dev; rotate every 90 days |
# MAGIC | Service Principal + OAuth | Production agents | **Preferred** for production |
# MAGIC | Notebook token (`apiToken`) | In-notebook only | Only works inside Databricks runtime |
# MAGIC
# MAGIC ```python
# MAGIC # Production: use Service Principal with OAuth (store secrets in a Secret Scope)
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC
# MAGIC w = WorkspaceClient(
# MAGIC     host=WORKSPACE_URL,
# MAGIC     client_id=dbutils.secrets.get(scope="workshop", key="sp-client-id"),
# MAGIC     client_secret=dbutils.secrets.get(scope="workshop", key="sp-client-secret"),
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC ### Data minimisation
# MAGIC
# MAGIC MCP tool results should return only what the agent needs — not full table scans.
# MAGIC The `search_policy_documents` function above truncates content to 300 characters.
# MAGIC This matters for three reasons:
# MAGIC
# MAGIC | Reason | Impact |
# MAGIC |--------|--------|
# MAGIC | Token cost | Less output = fewer tokens = lower inference cost |
# MAGIC | Privacy compliance | Do not return PII unless explicitly required |
# MAGIC | Latency | Smaller payloads = faster agent response times |
# MAGIC
# MAGIC ### Audit logging
# MAGIC
# MAGIC Every MCP call is logged in Databricks audit logs. You can query them in SQL:
# MAGIC ```sql
# MAGIC -- View recent Vector Search MCP calls
# MAGIC SELECT event_time, user_identity.email, request_params
# MAGIC FROM system.access.audit
# MAGIC WHERE service_name = 'vectorSearch'
# MAGIC   AND event_time > current_timestamp() - INTERVAL 1 HOUR
# MAGIC ORDER BY event_time DESC
# MAGIC ```
# MAGIC
# MAGIC ### Secrets management
# MAGIC
# MAGIC Never hardcode tokens or credentials. Use Databricks Secret Scopes:
# MAGIC ```python
# MAGIC # Store once via CLI: databricks secrets put-secret --scope workshop --key pat-token
# MAGIC token = dbutils.secrets.get(scope="workshop", key="pat-token")
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🛠️  Section 8 — Exercise: Add a Custom MCP Tool
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 8.1 — Add `check_regulatory_compliance`
# MAGIC
# MAGIC Create a new UC function from Lab 03 and add it to the multi-MCP agent as a fourth tool.
# MAGIC
# MAGIC The function should:
# MAGIC - Take: `region` (STRING), `metric` (STRING: 'SAIDI' or 'SAIFI'), `actual_value` (DOUBLE)
# MAGIC - Query a `regulatory_thresholds` table (which you create below)
# MAGIC - Return JSON with: `region`, `metric`, `threshold`, `actual_value`, `breach` (bool),
# MAGIC   `penalty_estimate_aud`
# MAGIC - Penalty formula: `(actual_value - threshold) * 15000` if in breach, else 0
# MAGIC
# MAGIC **Step 1:** Create the thresholds reference table.

# COMMAND ----------

# Create the regulatory_thresholds reference table
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

threshold_rows = [
    ("NSW", "SAIDI", 250.0),
    ("VIC", "SAIDI", 230.0),
    ("QLD", "SAIDI", 270.0),
    ("SA",  "SAIDI", 260.0),
    ("NSW", "SAIFI", 1.5),
    ("VIC", "SAIFI", 1.4),
    ("QLD", "SAIFI", 1.6),
    ("SA",  "SAIFI", 1.5),
]

threshold_schema = StructType([
    StructField("region",    StringType(), False),
    StructField("metric",    StringType(), False),
    StructField("threshold", DoubleType(), False),
])

(spark.createDataFrame(threshold_rows, threshold_schema)
     .write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_thresholds"))

print(f"Created {CATALOG}.{SCHEMA}.regulatory_thresholds with {len(threshold_rows)} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 2:** Register the UC function and add it to the agent.

# COMMAND ----------

# TODO: Register check_regulatory_compliance as a UC function

# Step 2a: Register the UC function
# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.check_regulatory_compliance(
#     region       STRING  COMMENT 'Australian state/territory code (NSW, VIC, QLD, SA)',
#     metric       STRING  COMMENT 'Reliability metric to check: SAIDI or SAIFI',
#     actual_value DOUBLE  COMMENT 'The actual measured value for the metric this period'
# )
# RETURNS STRING
# COMMENT 'Check whether a reliability metric is in breach of AER regulatory thresholds.
# Returns JSON with: region, metric, threshold, actual_value, breach (bool), penalty_estimate_aud.
# Use when asked whether a SAIDI or SAIFI value exceeds AER targets, or to estimate penalty exposure.'
# LANGUAGE PYTHON
# AS $$
# import json
# try:
#     from pyspark.sql import SparkSession
#     from pyspark.sql import functions as F
#     spark = SparkSession.builder.getOrCreate()
#
#     row = (
#         spark.table("main.workshop_lab.regulatory_thresholds")
#         .filter((F.col("region") == region) & (F.col("metric") == metric))
#         .first()
#     )
#     if row is None:
#         return json.dumps({"error": f"No threshold found for {metric} in {region}"})
#
#     threshold = float(row["threshold"])
#     breach = actual_value > threshold
#     penalty = round((actual_value - threshold) * 15000, 2) if breach else 0.0
#
#     return json.dumps({
#         "region": region,
#         "metric": metric,
#         "threshold": threshold,
#         "actual_value": actual_value,
#         "breach": breach,
#         "penalty_estimate_aud": penalty,
#     })
# except Exception as e:
#     return json.dumps({"error": str(e)})
# $$
# """)
# print(f"Registered: {CATALOG}.{SCHEMA}.check_regulatory_compliance")

# Step 2b: Add tool spec to tools_spec list (copy-paste and uncomment)
# {
#     "type": "function",
#     "function": {
#         "name": "check_regulatory_compliance",
#         "description": (
#             "Check whether a SAIDI or SAIFI reliability metric value is in breach of "
#             "AER regulatory thresholds for a given Australian state. Returns the threshold, "
#             "breach status, and estimated penalty exposure. Use when asked whether performance "
#             "targets have been met or what penalty exposure the network faces."
#         ),
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "region": {"type": "string", "description": "State code: NSW, VIC, QLD, or SA"},
#                 "metric": {"type": "string", "description": "SAIDI or SAIFI"},
#                 "actual_value": {"type": "number", "description": "Measured value this period"},
#             },
#             "required": ["region", "metric", "actual_value"],
#         },
#     },
# }

# Step 2c: Add handler in execute_tool() and re-run the agent
# Test with:
# answer = run_energy_agent(
#     "The NSW network had 278 minutes of SAIDI this year. Are we in breach of AER thresholds? "
#     "What is our estimated penalty exposure?"
# )
# print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC **Success criteria for Exercise 8.1:**
# MAGIC - SQL test returns correct breach status: `{"breach": true, "penalty_estimate_aud": 420000.0}` for NSW SAIDI = 278 (threshold 250, delta 28 × $15k)
# MAGIC - The agent answers *"The NSW network had 278 minutes of SAIDI — are we in breach?"* using the new tool (visible in verbose trace as `[Tool call] check_regulatory_compliance`)
# MAGIC - The tool description clearly states when the LLM should call it vs `search_policy_documents`

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🎯  Section 9 — Try It Yourself: Extend the Agent for a New Energy Question Type
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #fff8e1; border-left: 4px solid #f9a825; padding: 16px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #e65100;">Challenge:</strong> Add a new capability to the agent
# MAGIC   that does not exist yet — the ability to answer questions about <strong>voltage
# MAGIC   exceedances</strong> at connection points.
# MAGIC </div>
# MAGIC
# MAGIC ### Background
# MAGIC
# MAGIC The Voltage Quality Compliance policy document (doc_id 5) states that voltage must stay
# MAGIC within -6% to +10% of nominal (230V). You will build a tool that checks a connection
# MAGIC point's voltage readings against this band and reports exceedances.
# MAGIC
# MAGIC ### Your task — three steps
# MAGIC
# MAGIC **Step 1:** Create a `voltage_readings` sample table with connection point IDs,
# MAGIC timestamps, and voltage measurements (some outside the compliant band).
# MAGIC
# MAGIC **Step 2:** Register a UC function `check_voltage_compliance` that:
# MAGIC - Takes `connection_point_id` (STRING) and `analysis_month` (STRING, YYYY-MM)
# MAGIC - Queries `voltage_readings`, counts intervals outside the 216.2V–253.0V band
# MAGIC - Returns JSON with: `connection_point_id`, `total_intervals`, `exceedance_count`,
# MAGIC   `exceedance_pct`, `worst_voltage`, `compliant` (bool)
# MAGIC - Flags as non-compliant if exceedance_pct > 5% (per the Voltage Quality policy)
# MAGIC
# MAGIC **Step 3:** Add the tool to `tools_spec` and `execute_tool`, then test with this question:
# MAGIC
# MAGIC > *"Connection point CP-NSW-042 had some voltage issues last month. Are we within the
# MAGIC > AER voltage quality requirements?"*

# COMMAND ----------

# Step 1: Create a voltage_readings sample table
import datetime, random
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, DoubleType

random.seed(42)
NOMINAL_V = 230.0
LOW_BAND  = NOMINAL_V * 0.94   # -6%  = 216.2V
HIGH_BAND = NOMINAL_V * 1.10   # +10% = 253.0V

vr_rows = []
base_date = datetime.datetime(2024, 6, 1, 0, 0, 0)
for hour in range(720):  # 30 days x 24 hours
    ts = base_date + datetime.timedelta(hours=hour)
    # Most readings compliant; ~4% simulated exceedances
    if random.random() < 0.04:
        voltage = round(random.choice([
            random.uniform(205.0, 215.0),   # below -6%
            random.uniform(254.0, 265.0),   # above +10%
        ]), 2)
    else:
        voltage = round(random.uniform(220.0, 245.0), 2)
    vr_rows.append(("CP-NSW-042", ts, voltage))

vr_schema = StructType([
    StructField("connection_point_id", StringType(),   False),
    StructField("recorded_at",         TimestampType(), False),
    StructField("voltage_v",           DoubleType(),   True),
])

(spark.createDataFrame(vr_rows, vr_schema)
     .write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.voltage_readings"))

print(f"Created {CATALOG}.{SCHEMA}.voltage_readings with {len(vr_rows)} hourly readings")
print(f"Connection point: CP-NSW-042")
print(f"Compliant band: {LOW_BAND:.1f}V - {HIGH_BAND:.1f}V")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Created main.workshop_lab.voltage_readings with 720 hourly readings
# MAGIC Connection point: CP-NSW-042
# MAGIC Compliant band: 216.2V - 253.0V
# MAGIC ```

# COMMAND ----------

# TODO Step 2: Register check_voltage_compliance as a UC function
# Hint: the function body needs to:
# - Filter voltage_readings on connection_point_id and the analysis_month
# - Count rows where voltage_v < 216.2 OR voltage_v > 253.0
# - Calculate exceedance_pct = exceedance_count / total_intervals * 100
# - Return JSON with the fields listed in the task description above
# - Set compliant = True only when exceedance_pct <= 5.0

# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.check_voltage_compliance(
#     connection_point_id STRING COMMENT '...',
#     analysis_month      STRING COMMENT 'Month to analyse in YYYY-MM format'
# )
# RETURNS STRING
# COMMENT '...'
# LANGUAGE PYTHON
# AS $$
# ...
# $$
# """)

# COMMAND ----------

# TODO Step 3: Add to tools_spec, add handler in execute_tool, rebuild agent, test
# test_question = (
#     "Connection point CP-NSW-042 had some voltage issues last month (June 2024). "
#     "Are we within the AER voltage quality requirements?"
# )
# answer = run_energy_agent(test_question, verbose=True)
# print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Success criteria
# MAGIC
# MAGIC Your extension is complete when:
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | SQL test | `SELECT main.workshop_lab.check_voltage_compliance('CP-NSW-042', '2024-06')` returns JSON with `compliant` field and correct exceedance count |
# MAGIC | Agent routing | Verbose trace shows `[Tool call] check_voltage_compliance(...)` when asked the voltage question (not `search_policy_documents`) |
# MAGIC | Regulatory context | Agent answer references the AER -6%/+10% band from the policy document |
# MAGIC | Compliance verdict | Agent clearly states whether the reading is within the 5% exceedance threshold |
# MAGIC
# MAGIC ### Bonus challenge
# MAGIC
# MAGIC The policy document says persistent exceedances (>5% of intervals in a month) trigger
# MAGIC an **obligation to invest in network remediation within 12 months**.
# MAGIC
# MAGIC Modify the agent's system prompt to make it automatically include this regulatory
# MAGIC obligation in its answer when the `compliant` field is `false`. Verify the change
# MAGIC by re-running the voltage question and checking the agent's answer now includes
# MAGIC the remediation timeline.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 20px 24px; border-radius: 10px; margin-top: 16px;">
# MAGIC   <h2 style="color: white; margin: 0 0 8px 0;">Lab 04 Complete — Workshop Wrap-up</h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 12px 0;">
# MAGIC     You built a multi-MCP agent that combines Genie (NL-to-SQL), Vector Search (semantic
# MAGIC     document retrieval), and UC Functions (domain calculations) into a single interface —
# MAGIC     all running within Australia East.
# MAGIC   </p>
# MAGIC
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 12px;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 6px 8px;">Lab</th>
# MAGIC       <th style="text-align: left; padding: 6px 8px;">Core skill</th>
# MAGIC       <th style="text-align: left; padding: 6px 8px;">AU East</th>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 8px;">Lab 01</td>
# MAGIC       <td style="padding: 4px 8px;">Genie Code fundamentals — generate, explain, fix, document</td>
# MAGIC       <td style="padding: 4px 8px;">In-region</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 8px;">Lab 02</td>
# MAGIC       <td style="padding: 4px 8px;">Notebook AI chat — schema discovery, SQL generation, agent mode</td>
# MAGIC       <td style="padding: 4px 8px;">In-region</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 8px;">Lab 03</td>
# MAGIC       <td style="padding: 4px 8px;">UC functions as AI tools — register, test, govern</td>
# MAGIC       <td style="padding: 4px 8px;">In-region</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 8px;">Lab 04</td>
# MAGIC       <td style="padding: 4px 8px;">MCP integration — Genie + Vector Search + UC Functions</td>
# MAGIC       <td style="padding: 4px 8px;">In-region</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 8px 0; font-weight: bold;">Next steps:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0; padding-left: 20px;">
# MAGIC     <li>Lab 05 (optional): Deploying agents to Model Serving endpoints for production</li>
# MAGIC     <li>Workshop 2B: Building no-code NL-to-SQL Genie Spaces for business users</li>
# MAGIC     <li>Production checklist: Service Principal auth, secret scopes, monitoring with MLflow Tracing</li>
# MAGIC   </ul>
# MAGIC </div>
