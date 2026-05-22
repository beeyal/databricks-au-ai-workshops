# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 04: MCP Integration (Model Context Protocol)
# MAGIC **Workshop:** Genie Code for Developers — Australian Regulated Industries
# MAGIC **Estimated time:** 45 minutes
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What you'll learn
# MAGIC
# MAGIC | Topic | Time |
# MAGIC |-------|------|
# MAGIC | What MCP is and how Databricks implements it | 5 min |
# MAGIC | Connecting to Genie Space via MCP | 10 min |
# MAGIC | Connecting to Vector Search via MCP | 10 min |
# MAGIC | Connecting to UC Functions via MCP | 5 min |
# MAGIC | Building a multi-MCP energy operations agent | 10 min |
# MAGIC | Best practices for regulated environments | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What is MCP?
# MAGIC
# MAGIC **Model Context Protocol (MCP)** is an open standard (Anthropic, 2024) that lets AI agents
# MAGIC connect to data sources and tools through a uniform interface — similar to how REST APIs
# MAGIC standardise HTTP communication.
# MAGIC
# MAGIC In Databricks, MCP is exposed as authenticated HTTP endpoints:
# MAGIC
# MAGIC | MCP Endpoint | What it provides |
# MAGIC |--------------|-----------------|
# MAGIC | `/api/2.0/mcp/genie/{space_id}` | Natural language → SQL via a Genie Space |
# MAGIC | `/api/2.0/mcp/vector-search/{catalog.schema.index_name}` | Semantic search over a Vector Search index |
# MAGIC | `/api/2.0/mcp/functions/system/ai` | Calls UC functions as AI tools |
# MAGIC
# MAGIC ### Why MCP for regulated industries?
# MAGIC
# MAGIC | Concern | MCP answer |
# MAGIC |---------|-----------|
# MAGIC | **Data residency** | All Databricks MCP endpoints are workspace-local (AU East) |
# MAGIC | **Auth & access control** | Databricks PAT or OAuth — same as any API call |
# MAGIC | **Auditability** | Every MCP call is logged in Databricks audit logs |
# MAGIC | **No external dependencies** | Client library runs locally; server is your workspace |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Architecture for this lab
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────┐
# MAGIC │           Energy Operations Agent (AU East)          │
# MAGIC │                                                       │
# MAGIC │  User question                                        │
# MAGIC │       ↓                                               │
# MAGIC │  Claude Sonnet 4.6 (Provisioned Throughput)           │
# MAGIC │       ↓  decides which tool to call                   │
# MAGIC │  ┌────┴──────────┬───────────┬──────────────────┐    │
# MAGIC │  │  Genie MCP    │  VS MCP   │  UC Functions MCP│    │
# MAGIC │  │  NL→SQL over  │  Policy   │  calculate_peak  │    │
# MAGIC │  │  meter tables │  doc RAG  │  lookup_asset    │    │
# MAGIC │  └───────────────┴───────────┴──────────────────┘    │
# MAGIC │                   All in Australia East               │
# MAGIC └─────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup

# COMMAND ----------

%pip install openai databricks-sdk mlflow --quiet
dbutils.library.restartPython()

# COMMAND ----------

import os
import json
from databricks.sdk import WorkspaceClient

# TODO: Update these values for your workspace
WORKSPACE_URL  = "https://adb-XXXXXXXXXXXXXXXXX.X.azuredatabricks.net"  # TODO: your workspace URL
CATALOG        = "main"          # TODO: your catalog
SCHEMA         = "workshop_lab"  # TODO: your schema (from Lab 02 & 03)

# TODO: Fill in your Genie Space ID
# Find it: Go to Genie → open your space → copy the ID from the URL
# URL pattern: /genie/spaces/{GENIE_SPACE_ID}
GENIE_SPACE_ID = "XXXXXXXXXXXX"  # TODO: your Genie Space ID

# TODO: Fill in your Vector Search index name (full 3-part name)
# If you don't have one, Section 3 shows how to create a minimal one
VS_INDEX_NAME  = f"{CATALOG}.{SCHEMA}.policy_docs_index"  # TODO: adjust if different

# Databricks token — uses the notebook token automatically inside Databricks
# For external clients, use a PAT from User Settings → Access Tokens
DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

print(f"Workspace: {WORKSPACE_URL}")
print(f"Catalog/Schema: {CATALOG}.{SCHEMA}")
print(f"Genie Space: {GENIE_SPACE_ID}")
print(f"VS Index: {VS_INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — MCP Client Setup
# MAGIC
# MAGIC We use the **OpenAI Agents SDK** as our MCP client. It is a client-side library only —
# MAGIC it never sends data to OpenAI servers. All API calls go to your Databricks workspace URL.
# MAGIC
# MAGIC > **Why OpenAI Agents SDK?**
# MAGIC > Databricks MCP endpoints implement the MCP spec, which the OpenAI Agents SDK
# MAGIC > supports natively. It works with any MCP-compatible server, including Databricks.

# COMMAND ----------

from openai import OpenAI

# Point the OpenAI client at your Databricks workspace
# The base_url tells it to use Databricks endpoints, not OpenAI's servers
client = OpenAI(
    base_url=f"{WORKSPACE_URL}/serving-endpoints",
    api_key=DATABRICKS_TOKEN,
)

# Verify connectivity by listing available models
try:
    models = client.models.list()
    model_ids = [m.id for m in models.data]
    print(f"Connected to workspace. Available models ({len(model_ids)}):")
    for m in model_ids[:5]:
        print(f"  - {m}")
    if len(model_ids) > 5:
        print(f"  ... and {len(model_ids) - 5} more")
except Exception as e:
    print(f"Connection error: {e}")
    print("Check WORKSPACE_URL and DATABRICKS_TOKEN above.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — MCP Tool 1: Genie Space (NL → SQL)
# MAGIC
# MAGIC The Genie MCP endpoint lets an agent ask natural-language questions against a Genie Space.
# MAGIC The Genie Space handles the NL → SQL translation and executes the query.
# MAGIC
# MAGIC ### Endpoint format
# MAGIC ```
# MAGIC GET/POST {WORKSPACE_URL}/api/2.0/mcp/genie/{space_id}
# MAGIC ```
# MAGIC
# MAGIC ### Setting up a Genie Space (if you don't have one)
# MAGIC
# MAGIC A Genie Space needs at least one table. We'll create a minimal one using the
# MAGIC meter tables from Lab 02.
# MAGIC
# MAGIC **Steps (manual, in the UI):**
# MAGIC 1. Go to Databricks → Genie (sidebar)
# MAGIC 2. Click "New Genie Space"
# MAGIC 3. Add `{CATALOG}.{SCHEMA}.interval_reads` and `{CATALOG}.{SCHEMA}.meter_register`
# MAGIC 4. Add a description: "NEM meter consumption and register data for NSW and VIC regions"
# MAGIC 5. Copy the Space ID from the URL and update `GENIE_SPACE_ID` above

# COMMAND ----------

import requests

def call_genie_mcp(question: str, space_id: str, workspace_url: str, token: str) -> dict:
    """Call the Genie Space MCP endpoint with a natural language question.

    Args:
        question: Natural language question to ask the Genie Space.
        space_id: The Genie Space ID (from the URL in the Genie UI).
        workspace_url: Full Databricks workspace URL (no trailing slash).
        token: Databricks personal access token.

    Returns:
        Dictionary with 'answer', 'sql' (the generated query), and 'rows' (result preview).
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
# (Requires a valid GENIE_SPACE_ID — see Section 3 setup above)
if GENIE_SPACE_ID != "XXXXXXXXXXXX":
    result = call_genie_mcp(
        question="What is the total consumption in kWh for each NMI in the dataset?",
        space_id=GENIE_SPACE_ID,
        workspace_url=WORKSPACE_URL,
        token=DATABRICKS_TOKEN,
    )
    print(json.dumps(result, indent=2, default=str))
else:
    print("GENIE_SPACE_ID not set — update the TODO above and re-run.")
    print("Continuing with a mock response for demonstration...")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Understanding the Genie MCP response
# MAGIC
# MAGIC The response contains:
# MAGIC - `content`: The natural language answer Genie generated
# MAGIC - The underlying SQL Genie used to answer the question
# MAGIC - Result rows (configurable limit)
# MAGIC
# MAGIC **Why use Genie MCP instead of raw SQL?**
# MAGIC - Operators can ask questions in plain English without knowing table names
# MAGIC - Genie handles schema changes automatically
# MAGIC - Genie Space context window includes business descriptions you've added

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — MCP Tool 2: Vector Search (Semantic Doc Search)
# MAGIC
# MAGIC The Vector Search MCP endpoint enables semantic search over a Databricks Vector Search index.
# MAGIC We'll use it to search regulatory policy documents.
# MAGIC
# MAGIC ### Create a minimal Vector Search index for the lab
# MAGIC
# MAGIC If you don't have a Vector Search index, run the cells below to create one
# MAGIC using a synthetic regulatory document corpus.

# COMMAND ----------

# Create a small regulatory documents table for Vector Search
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

policy_docs = [
    (1, "SAIDI Reporting Requirements",
     "SAIDI (System Average Interruption Duration Index) measures the total duration of interruptions per customer per year. Under AER Service Target Performance Incentive Scheme (STPIS), distributors must report SAIDI annually. The threshold for NSW distribution networks is 250 minutes per customer per year. Breaches attract financial penalties calculated at AUD 15,000 per customer per minute above threshold."),
    (2, "NEM12 Data Quality Standards",
     "NEM12 files must contain 48 interval records per day per meter. Quality flags must be: A (Actual) for meter-read data, E (Estimated) for data substituted by estimation, S (Substituted) for data replaced by MDMA. Estimated reads exceeding 5% of intervals in a billing period require mandatory customer notification under National Energy Retail Rules clause 46."),
    (3, "Critical Peak Demand Management",
     "During network emergencies, AEMO may issue an Emergency Backstop Mechanism (EBM) direction. Retailers must curtail consumption by 10% within 30 minutes of an EBM notice. Non-compliance incurs penalties under National Electricity Rules clause 4.10.3. Smart meters with interval data are mandatory for EBM-eligible customers above 160 MWh per year."),
    (4, "Meter Data Retention Policy",
     "Under the Privacy Act 1988 and the National Energy Retail Rules, meter data must be retained for a minimum of 7 years. Data must be stored in Australia (s.16C Privacy Act). Access by third parties requires customer explicit consent via a signed metering data authorisation form. Retailers must provide customers with access to their own data within 5 business days of request."),
    (5, "Voltage Quality Compliance",
     "Distribution network service providers must maintain supply voltage within -6% to +10% of nominal voltage (230V) at the customer's connection point. Monitoring is required at representative points across the network. Exceedances must be reported to AER quarterly. Persistent exceedances (>5% of measured intervals in a month) trigger an obligation to invest in network remediation within 12 months."),
]

schema = StructType([
    StructField("doc_id",   IntegerType(), False),
    StructField("title",    StringType(),  True),
    StructField("content",  StringType(),  True),
])

df_docs = spark.createDataFrame(policy_docs, schema=schema)
df_docs.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_policy_docs")

print(f"Created {CATALOG}.{SCHEMA}.regulatory_policy_docs with {df_docs.count()} documents")
df_docs.select("doc_id", "title").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Create the Vector Search endpoint and index
# MAGIC
# MAGIC **Option A — Use the UI (recommended for the lab):**
# MAGIC 1. Compute → Vector Search → Create Endpoint (name: `workshop-vs-endpoint`)
# MAGIC 2. Catalog → your table → Create Vector Search Index
# MAGIC    - Source table: `{CATALOG}.{SCHEMA}.regulatory_policy_docs`
# MAGIC    - Index type: Delta Sync (or Direct Vector Access for manual)
# MAGIC    - Embedding column: `content`
# MAGIC    - Embedding model: `databricks-gte-large-en`
# MAGIC    - Primary key: `doc_id`
# MAGIC
# MAGIC **Option B — Use SDK:**

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn, PipelineType
)

w = WorkspaceClient()

VS_ENDPOINT_NAME = "workshop-vs-endpoint"  # TODO: change if you have an existing endpoint

# Create endpoint (skip if already exists)
try:
    w.vector_search_endpoints.create_endpoint(
        name=VS_ENDPOINT_NAME,
        endpoint_type=EndpointType.STANDARD,
    )
    print(f"Created VS endpoint: {VS_ENDPOINT_NAME}")
    print("Waiting for endpoint to be ONLINE (this takes ~5 minutes on first creation)...")
    w.vector_search_endpoints.wait_get_endpoint_vector_search_endpoint_online(VS_ENDPOINT_NAME)
    print("Endpoint is ONLINE.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Endpoint {VS_ENDPOINT_NAME} already exists — skipping creation.")
    else:
        print(f"Endpoint creation note: {e}")

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
    print("Syncing index — check status in the Catalog UI or with:")
    print(f"  w.vector_search_indexes.get_index('{CATALOG}.{SCHEMA}.policy_docs_index')")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Index already exists — triggering sync...")
        w.vector_search_indexes.sync_index(f"{CATALOG}.{SCHEMA}.policy_docs_index")
    else:
        print(f"Index note: {e}")

# COMMAND ----------

def search_policy_docs(query: str, index_name: str, num_results: int = 3) -> list[dict]:
    """Search regulatory policy documents using Vector Search semantic similarity.

    Args:
        query: The natural language search query.
        index_name: Full 3-part Unity Catalog name of the Vector Search index.
        num_results: Number of documents to return (default 3).

    Returns:
        List of dicts with 'doc_id', 'title', 'content', and 'score'.
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


# Test the Vector Search MCP tool
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
# MAGIC ---
# MAGIC ## Section 5 — MCP Tool 3: UC Functions via MCP
# MAGIC
# MAGIC The UC Functions MCP endpoint exposes Unity Catalog functions as MCP tools.
# MAGIC This means any MCP-compatible client can call your UC functions.
# MAGIC
# MAGIC ### Endpoint format
# MAGIC ```
# MAGIC {WORKSPACE_URL}/api/2.0/mcp/functions/{catalog}/{schema}
# MAGIC ```
# MAGIC
# MAGIC For AI tools registered in `system.ai` (built-in Databricks AI functions):
# MAGIC ```
# MAGIC {WORKSPACE_URL}/api/2.0/mcp/functions/system/ai
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
        arguments: Dict of argument name → value.
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
# MAGIC ---
# MAGIC ## Section 6 — Building the Multi-MCP Energy Operations Agent
# MAGIC
# MAGIC Now we combine all three MCP tools into a single agent using the OpenAI Agents SDK.
# MAGIC The agent uses `databricks-claude-sonnet-4-6` (provisioned throughput, AU East).

# COMMAND ----------

from openai import OpenAI
import json

# Databricks endpoint for Claude Sonnet 4.6 (provisioned throughput, AU East in-region)
llm_client = OpenAI(
    base_url=f"{WORKSPACE_URL}/serving-endpoints",
    api_key=DATABRICKS_TOKEN,
)

# ---- Tool definitions (OpenAI function-calling format) ----
tools_spec = [
    {
        "type": "function",
        "function": {
            "name": "query_genie_space",
            "description": (
                "Ask a natural language question about meter consumption data, NMI registers, "
                "or billing data. The Genie Space will translate your question to SQL and execute it. "
                "Use this for questions about consumption trends, totals, averages, or comparisons "
                "across meters or time periods."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the energy data (e.g., 'What is the total consumption for NMI 6001234567 in July 2024?')",
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
                "Use this when asked about AER requirements, SAIDI/SAIFI limits, NEM12 standards, "
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
                "Look up the maintenance history and operational status of a network asset "
                "(transformer, switch, cable, or meter). Returns work orders year-to-date, "
                "total outage minutes, and cost. Use for questions about asset condition, "
                "maintenance history, or contribution to network SAIDI."
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

# COMMAND ----------

# ---- Tool execution router ----
def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Route a tool call to the appropriate MCP endpoint or function."""

    if tool_name == "query_genie_space":
        if GENIE_SPACE_ID == "XXXXXXXXXXXX":
            # Mock response when Genie Space is not configured
            return json.dumps({
                "answer": "Genie Space not configured. Update GENIE_SPACE_ID and re-run.",
                "note": "In production, this would return SQL results from your Genie Space."
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
            return json.dumps({"error": results[0]["error"],
                               "note": "Vector Search index may still be syncing. Wait 2-3 minutes."})
        # Return titles + excerpts (not full content) to keep token usage low
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
        verbose: If True, print tool calls as they happen (useful for debugging).

    Returns:
        The agent's final answer as a string.
    """
    system_message = {
        "role": "system",
        "content": (
            "You are an expert energy operations assistant for an Australian electricity "
            "network operator. You help operations staff with:\n"
            "- Meter data analysis (NEM12 interval reads, NMI registers)\n"
            "- Regulatory compliance (AER, AEMO, SAIDI/SAIFI reporting)\n"
            "- Asset maintenance and reliability analysis\n\n"
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

        # Add assistant message to history
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

        # Execute each tool call
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

    return "Max iterations reached — partial answer: " + (message.content or "")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Testing the Multi-MCP Agent
# MAGIC
# MAGIC ### Exercise 7.1 — Meter data question (Genie + UC Function)

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
# MAGIC ### Exercise 7.2 — Regulatory compliance question (Vector Search)

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
# MAGIC ### Exercise 7.3 — Asset and compliance cross-reference

# COMMAND ----------

answer = run_energy_agent(
    "Asset TF-NSW-001 has had several maintenance events this year. "
    "How much outage time has it caused? "
    "Based on AER SAIDI requirements, should we be concerned about this level of outages?",
    verbose=True,
)
print("\n" + "="*60)
print("FINAL ANSWER:")
print("="*60)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.4 — Multi-tool chain question

# COMMAND ----------

answer = run_energy_agent(
    "I need a complete operations briefing for NMI 6001234567 and asset TF-NSW-001: "
    "1. What was the peak demand in the first week of July 2024? "
    "2. What is the maintenance status of the transformer? "
    "3. Are there any regulatory data retention obligations I should be aware of for this meter data?",
    verbose=True,
)
print("\n" + "="*60)
print("FINAL ANSWER:")
print("="*60)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 8 — Best Practices for MCP in Regulated Environments
# MAGIC
# MAGIC ### Authentication
# MAGIC
# MAGIC | Method | Use case | Recommendation |
# MAGIC |--------|----------|----------------|
# MAGIC | PAT (Personal Access Token) | Development / notebooks | OK for dev; rotate regularly |
# MAGIC | Service Principal + OAuth | Production agents | **Preferred** for production |
# MAGIC | Notebook token (`apiToken`) | In-notebook only | Only works inside Databricks |
# MAGIC
# MAGIC ```python
# MAGIC # Production: use Service Principal with OAuth
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks.sdk.credentials_provider import OAuthCredentialsProvider
# MAGIC
# MAGIC w = WorkspaceClient(
# MAGIC     host=WORKSPACE_URL,
# MAGIC     client_id="your-sp-client-id",        # From Azure App Registration
# MAGIC     client_secret="your-sp-client-secret", # Store in a secret scope
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC ### Data minimisation
# MAGIC
# MAGIC MCP tool results should return only what the agent needs — not full table scans.
# MAGIC The `search_policy_documents` function above truncates content to 300 characters.
# MAGIC This matters for:
# MAGIC - Token cost (less output = cheaper)
# MAGIC - Privacy (don't return PII unless required)
# MAGIC - Latency (smaller payloads = faster responses)
# MAGIC
# MAGIC ### Audit logging
# MAGIC
# MAGIC Every MCP call is logged in Databricks audit logs:
# MAGIC ```sql
# MAGIC SELECT *
# MAGIC FROM system.access.audit
# MAGIC WHERE service_name = 'vectorSearch'
# MAGIC   AND event_time > current_timestamp() - INTERVAL 1 HOUR
# MAGIC ORDER BY event_time DESC
# MAGIC ```
# MAGIC
# MAGIC ### Secrets management
# MAGIC
# MAGIC Never hardcode tokens. Use Databricks Secret Scopes:
# MAGIC ```python
# MAGIC # Store once: databricks secrets put-secret --scope workshop --key genie-token
# MAGIC token = dbutils.secrets.get(scope="workshop", key="genie-token")
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 9 — Exercise: Add a Custom MCP Tool
# MAGIC
# MAGIC ### Exercise 9.1 — Add `check_regulatory_compliance`
# MAGIC
# MAGIC Create a new UC function from Lab 03 and add it to the agent as a fourth MCP tool:
# MAGIC
# MAGIC ```python
# MAGIC # The function should:
# MAGIC # - Take: region (str), metric (str: 'SAIDI' or 'SAIFI'), actual_value (float)
# MAGIC # - Query regulatory_thresholds table (from Lab 02)
# MAGIC # - Return: JSON with threshold, actual, breach (bool), penalty_estimate_aud
# MAGIC # - Penalty formula: (actual_value - threshold) * 15000 if breach else 0
# MAGIC ```
# MAGIC
# MAGIC After registering, add it to `tools_spec` and `execute_tool`, then test with:
# MAGIC > *"The NSW network had 278 minutes of SAIDI this year. Are we in breach of AER thresholds?"*

# COMMAND ----------

# TODO: Implement check_regulatory_compliance

# Step 1: Register as a UC function
# spark.sql("""
# CREATE OR REPLACE FUNCTION main.workshop_lab.check_regulatory_compliance(
#     region STRING, metric STRING, actual_value DOUBLE
# ) ...
# """)

# Step 2: Add to tools_spec list
# Step 3: Add handler in execute_tool()
# Step 4: Test with the query above

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 04 Complete — Workshop Wrap-up
# MAGIC
# MAGIC ### What we covered today
# MAGIC
# MAGIC | Lab | Core skill | AU East status |
# MAGIC |-----|-----------|----------------|
# MAGIC | Lab 01 | Genie Code fundamentals — generate, explain, fix, document | In-region ✓ |
# MAGIC | Lab 02 | Notebook AI chat — schema discovery, SQL generation, agent mode | In-region ✓ |
# MAGIC | Lab 03 | UC functions as AI tools — register, test, govern | In-region ✓ |
# MAGIC | Lab 04 | MCP integration — Genie + Vector Search + UC Functions | In-region ✓ |
# MAGIC
# MAGIC ### Architecture pattern for regulated environments
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────┐
# MAGIC │  Regulated AI Agent on Databricks (Australia East)           │
# MAGIC │                                                              │
# MAGIC │  User (operator / analyst)                                   │
# MAGIC │       ↓ natural language                                     │
# MAGIC │  LLM: databricks-claude-sonnet-4-6 (Provisioned Throughput) │
# MAGIC │       ↓ tool calls (all local)                               │
# MAGIC │  ┌──────────────┬──────────────────┬───────────────────┐    │
# MAGIC │  │ Genie MCP    │ Vector Search MCP │ UC Functions MCP  │    │
# MAGIC │  │ (structured  │ (unstructured     │ (custom domain    │    │
# MAGIC │  │  data NL→SQL)│  doc search)      │  calculations)    │    │
# MAGIC │  └──────────────┴──────────────────┴───────────────────┘    │
# MAGIC │                                                              │
# MAGIC │  Governance: Unity Catalog permissions + audit logs          │
# MAGIC │  Data residency: All endpoints in Australia East             │
# MAGIC └──────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### Next steps
# MAGIC
# MAGIC - **Lab 05 (optional):** Deploying agents to Model Serving endpoints for production
# MAGIC - **Genie Spaces workshop (Workshop 2B):** Building no-code NL-to-SQL for business users
# MAGIC - **Production checklist:** Service Principal auth, secret scopes, monitoring with MLflow Tracing
