# Databricks notebook source

# COMMAND ----------

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
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All MCP endpoints: AU East
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will build
# MAGIC
# MAGIC | Section | Topic | Time |
# MAGIC |---------|-------|------|
# MAGIC | 1 | MCP concepts, 5 server types, UI navigation | 10 min |
# MAGIC | 2 | UC Functions via `DatabricksMCPClient` | 10 min |
# MAGIC | 3 | Multi-MCP LangGraph agent (UC + Genie + Vector Search) | 15 min |
# MAGIC | 4 | OpenAI Agents SDK pattern with `McpServer` | 10 min |
# MAGIC | Bonus | Claude Desktop config, SQL MCP, audit trail | open |
# MAGIC
# MAGIC ## The five Databricks MCP server types
# MAGIC
# MAGIC All endpoints: `https://<workspace>/api/2.0/mcp/...` — all in-region for AU East.
# MAGIC
# MAGIC | MCP Server | URL pattern | Exposes |
# MAGIC |------------|-------------|---------|
# MAGIC | UC Functions (schema) | `.../mcp/functions/{catalog}/{schema}` | All UC functions in the schema |
# MAGIC | UC Functions (single) | `.../mcp/functions/{catalog}/{schema}/{function}` | One named UC function |
# MAGIC | Genie Space | `.../mcp/genie/{genie_space_id}` | One NL-to-SQL tool |
# MAGIC | Vector Search | `.../mcp/vector-search/{catalog}/{schema}/{index}` | One semantic search tool |
# MAGIC | Databricks SQL | `.../mcp/sql` | Direct SQL execution |
# MAGIC
# MAGIC **Tool naming convention:** UC function dots become double underscores in MCP tool names:
# MAGIC `workshop_au.workshop_lab.calculate_peak_demand` → `workshop_au__workshop_lab__calculate_peak_demand`
# MAGIC
# MAGIC **Three packages — do not mix them:**
# MAGIC
# MAGIC | Package | Gives you | Use for |
# MAGIC |---------|-----------|---------|
# MAGIC | `databricks-mcp` | `DatabricksMCPClient` | Tool discovery, direct calls |
# MAGIC | `databricks-langchain` | `DatabricksMCPServer`, `DatabricksMultiServerMCPClient` | LangGraph agents |
# MAGIC | `databricks-openai` | `McpServer` | OpenAI Agents SDK pattern |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

%pip install databricks-mcp databricks-langchain databricks-openai mlflow langgraph --quiet
dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",         "workshop_lab",         "Schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("genie_space_id", "",                     "Genie Space ID")
dbutils.widgets.text("vs_index",       "workshop_au.workshop_lab.policy_docs_index", "VS index (3-part name)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA         = dbutils.widgets.get("schema")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME  = dbutils.widgets.get("vs_index")

from databricks.sdk import WorkspaceClient
ws = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host : {HOST}")
print(f"Catalog.Schema : {CATALOG}.{SCHEMA}")
print(f"PT endpoint    : {PT_ENDPOINT}")
print(f"Genie Space ID : {GENIE_SPACE_ID}")
print(f"VS index       : {VS_INDEX_NAME}")

if GENIE_SPACE_ID == "":
    print("\nNOTE: Update 'genie_space_id' widget. Section 2 works without it.")

# COMMAND ----------

# MAGIC %md
# MAGIC **How to find your Genie Space ID:**
# MAGIC
# MAGIC Navigate: Left sidebar → Genie → open your space → look at browser URL bar
# MAGIC You should see: `.../genie/rooms/{space_id}` or `.../genie/spaces/{space_id}` — copy the ID after the last slash.
# MAGIC
# MAGIC **How to find MCP endpoints in AI Gateway:**
# MAGIC
# MAGIC Navigate: Left sidebar → Serving → AI Gateway → MCPs tab (AI Gateway v2 must be enabled in Account Console → Previews)
# MAGIC You should see: all registered MCP servers with their URLs and tool counts — copy any URL directly from this tab.
# MAGIC
# MAGIC **How to find your Vector Search index:**
# MAGIC
# MAGIC Navigate: Left sidebar → Catalog icon → workshop_au → workshop_lab → Vector Search Indexes
# MAGIC You should see: `policy_docs_index` with full 3-part name `workshop_au.workshop_lab.policy_docs_index`.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — UC Functions via MCP (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Discover tools with `DatabricksMCPClient`
# MAGIC
# MAGIC `DatabricksMCPClient` connects to a schema endpoint and discovers every UC function as an MCP tool.
# MAGIC The tool name, description, and parameter schema come directly from the UC function's `COMMENT` metadata.
# MAGIC Authentication is automatic — `WorkspaceClient()` reads credentials from the notebook context.

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient

ws = WorkspaceClient()

uc_mcp_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}"
print(f"UC Functions MCP endpoint:\n  {uc_mcp_url}\n")

client = DatabricksMCPClient(uc_mcp_url, ws)
tools = client.list_tools()

print(f"Discovered {len(tools)} tool(s) in {CATALOG}.{SCHEMA}:\n")
for t in tools:
    print(f"  Tool name  : {t.name}")
    print(f"  Description: {(t.description or '')[:120]}...")
    if hasattr(t, "inputSchema") and t.inputSchema:
        params = list(t.inputSchema.get("properties", {}).keys())
        print(f"  Parameters : {params}")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Call a UC function directly via MCP

# COMMAND ----------

import json

tool_name = f"{CATALOG}__{SCHEMA}__calculate_peak_demand"
print(f"Calling: {tool_name}\n")

result = client.call_tool(
    tool_name,
    {"nmi": "6001234567", "start_date": "2024-07-01", "end_date": "2024-07-07"},
)

print("Raw MCP response:")
print(json.dumps(result, indent=2, default=str))

# COMMAND ----------

# Parse the nested JSON from the MCP text content
if result and "content" in result:
    raw_text = result["content"][0]["text"]
    parsed = json.loads(raw_text)
    print("Parsed function result:")
    for k, v in parsed.items():
        print(f"  {k:<25} {v}")
else:
    print("Unexpected response shape:", result)

# COMMAND ----------

# MAGIC %md
# MAGIC The MCP response wraps the UC function return value in a `content` array — every MCP server type (Genie, Vector Search, UC Functions) uses this same shape.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Single-function endpoint (least-privilege pattern)

# COMMAND ----------

# Single-function endpoint — exposes only one function instead of the whole schema
single_fn_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}/calculate_peak_demand"
single_client = DatabricksMCPClient(single_fn_url, ws)

single_tools = single_client.list_tools()
print(f"Single-function endpoint exposes {len(single_tools)} tool(s):")
for t in single_tools:
    print(f"  {t.name}")

print("\nUse this when you want least-privilege access or need to avoid the 15-tools-per-server limit.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #00843D; color: white; padding: 12px 18px; border-radius: 6px; margin: 16px 0;">
# MAGIC   <strong>Checkpoint — Section 2</strong><br>
# MAGIC   You can discover and call UC functions via <code>DatabricksMCPClient</code>.
# MAGIC   Auth is automatic via <code>WorkspaceClient()</code> — no token handling needed.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Multi-MCP Agent with LangGraph (15 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Create the regulatory policy documents table and Vector Search index

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
     "Rules clause 46. Meters with persistent quality issues require MDMA review within 10 days."),
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
     "nominal voltage (230V) at the customer connection point. Exceedances must be reported to "
     "AER quarterly. Persistent exceedances (> 5% of measured intervals in a month) trigger an "
     "obligation to invest in network remediation within 12 months."),
    (6, "Critical Infrastructure Cybersecurity",
     "Under the Security of Critical Infrastructure Act 2018, electricity network operators must "
     "implement a Critical Infrastructure Risk Management Program (CIRMP). AEMO requires notification "
     "of significant cyber incidents within 12 hours. OT systems including SCADA must be patched "
     "within 30 days of a critical vulnerability disclosure."),
]

schema = StructType([
    StructField("doc_id",  IntegerType(), False),
    StructField("title",   StringType(),  True),
    StructField("content", StringType(),  True),
])

df_docs = spark.createDataFrame(policy_docs, schema=schema)
df_docs.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_policy_docs")

print(f"Created {CATALOG}.{SCHEMA}.regulatory_policy_docs with {df_docs.count()} documents")
df_docs.select("doc_id", "title").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Create Vector Search endpoint and index

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn, PipelineType
)

w = WorkspaceClient()
VS_ENDPOINT_NAME = "workshop-vs-endpoint"

# Create VS endpoint (idempotent)
try:
    w.vector_search_endpoints.create_endpoint(name=VS_ENDPOINT_NAME, endpoint_type=EndpointType.STANDARD)
    print(f"Created VS endpoint: {VS_ENDPOINT_NAME}")
    print("Waiting for endpoint to come ONLINE (first creation: ~5 min)...")
    w.vector_search_endpoints.wait_get_endpoint_vector_search_endpoint_online(VS_ENDPOINT_NAME)
    print("Endpoint is ONLINE.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Endpoint '{VS_ENDPOINT_NAME}' already exists — skipping.")
    else:
        print(f"Endpoint note: {e}")

# COMMAND ----------

VS_INDEX_FULL = f"{CATALOG}.{SCHEMA}.policy_docs_index"

try:
    w.vector_search_indexes.create_index(
        name=VS_INDEX_FULL,
        endpoint_name=VS_ENDPOINT_NAME,
        primary_key="doc_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=f"{CATALOG}.{SCHEMA}.regulatory_policy_docs",
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="content",
                    # Use qwen3 — it is in-region for AU East. gte-large-en is cross-geo.
                    embedding_model_endpoint_name="databricks-qwen3-embedding-0-6b",
                )
            ],
        ),
    )
    print(f"Created index: {VS_INDEX_FULL}")
    print("Wait 2-3 minutes for the index to sync before querying it.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Index '{VS_INDEX_FULL}' already exists — triggering sync...")
        w.vector_search_indexes.sync_index(VS_INDEX_FULL)
        print("Sync triggered.")
    else:
        print(f"Index note: {e}")

VS_INDEX_NAME = VS_INDEX_FULL
print(f"\nUsing VS index: {VS_INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Configure MCP servers
# MAGIC
# MAGIC `DatabricksMCPServer` is a declarative config object — it describes a server but does not connect yet.
# MAGIC `DatabricksMultiServerMCPClient` takes a list and manages connections, tool aggregation, and dispatch.

# COMMAND ----------

import asyncio
import mlflow
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import (
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
    ChatDatabricks,
)

# Server 1: UC Functions (all functions in the energy schema)
uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG,
    schema=SCHEMA,
    name="uc-tools",
    timeout=30.0,
    handle_tool_error=True,
)

servers = [uc_server]

# Server 2: Genie Space (skip if not configured)
if GENIE_SPACE_ID != "":
    genie_server = DatabricksMCPServer(
        name="energy-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0,           # Genie runs actual SQL — allow more time
        handle_tool_error=True,
    )
    servers.append(genie_server)
    print("Added: Genie Space MCP server")
else:
    print("NOTE: Genie Space ID not set — skipping. Set widget and re-run to include it.")

# Server 3: Vector Search (policy documents)
vs_server = DatabricksMCPServer(
    name="policy-docs-vs",
    url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
    timeout=30.0,
    handle_tool_error=True,
)
servers.append(vs_server)

print(f"\nMCP servers configured ({len(servers)} total): " + ", ".join(s.name for s in servers))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — Inspect aggregated tools from all servers

# COMMAND ----------

async def inspect_aggregated_tools():
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        tools = await multi_client.get_tools()
        print(f"Total tools across all MCP servers: {len(tools)}\n")
        for t in tools:
            print(f"  [{t.name}]")
            print(f"    {(t.description or '')[:80]}...")
            print()
        return tools

tools = asyncio.run(inspect_aggregated_tools())

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Build the ReAct agent and run three questions

# COMMAND ----------

mlflow.set_experiment("/Shared/workshop-lab04-mcp-agent")

llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=2048)

system_prompt = (
    "You are an expert energy operations assistant for an Australian electricity network operator. "
    "You help with meter data analysis (NEM12 interval reads), regulatory compliance (AER, AEMO, "
    "SAIDI/SAIFI thresholds), and asset maintenance. "
    "Always use your tools to answer questions — never guess or estimate values. "
    "Provide clear, actionable summaries with specific numbers and regulatory references."
)

async def run_langgraph_agent(question: str, run_name: str = "agent_run") -> str:
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        agent_tools = await multi_client.get_tools()
        agent = create_react_agent(model=llm, tools=agent_tools, prompt=system_prompt)
        with mlflow.start_run(run_name=run_name):
            result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content

# COMMAND ----------

# Question 1: UC Function tool — peak demand
q1 = "What was the peak demand for meter NMI 6001234567 during the first week of July 2024, and at what time of day did it occur?"
print(f"Q1: {q1}\n")
answer1 = asyncio.run(run_langgraph_agent(q1, run_name="q1_peak_demand"))
print("=" * 65)
print(answer1)

# COMMAND ----------

# Question 2: Vector Search tool — regulatory compliance
q2 = "Our meter for NMI 6001234567 has about 3% estimated reads this month. Does this comply with NEM12 standards, and do we need to notify the customer?"
print(f"Q2: {q2}\n")
answer2 = asyncio.run(run_langgraph_agent(q2, run_name="q2_nem12_compliance"))
print("=" * 65)
print(answer2)

# COMMAND ----------

# Question 3: multi-tool chain — three tools in one question
q3 = (
    "Morning operations briefing:\n"
    "1. Peak demand for meter 6001234567 in the first week of July 2024.\n"
    "2. Maintenance status of asset TF-NSW-001.\n"
    "3. What are the regulatory data retention obligations for our meter data?"
)
print(f"Q3 (multi-tool):\n{q3}\n")
answer3 = asyncio.run(run_langgraph_agent(q3, run_name="q3_multi_tool_briefing"))
print("=" * 65)
print(answer3)

# COMMAND ----------

# MAGIC %md
# MAGIC Navigate: Machine Learning → Experiments → /Shared/workshop-lab04-mcp-agent → click "q3_multi_tool_briefing" → Traces tab
# MAGIC You should see: three separate ToolCall spans in one AgentRun — calculate_peak_demand, lookup_asset_status, and search_policy_docs_index. Click any span to see exact arguments and latency.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #00843D; color: white; padding: 12px 18px; border-radius: 6px; margin: 16px 0;">
# MAGIC   <strong>Checkpoint — Section 3</strong><br>
# MAGIC   LangGraph ReAct agent connects to UC Functions, Genie, and Vector Search simultaneously.
# MAGIC   Tool selection is automatic — the LLM reads descriptions and routes each sub-question to the correct server.
# MAGIC   All calls traced in MLflow automatically.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — OpenAI Agents SDK Pattern (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — LangGraph vs OpenAI Agents SDK
# MAGIC
# MAGIC | | LangGraph (`databricks-langchain`) | OpenAI Agents SDK (`databricks-openai`) |
# MAGIC |---|---|---|
# MAGIC | Best for | Complex stateful / conditional workflows | Simple to mid-complexity tool-using agents |
# MAGIC | MCP integration | `DatabricksMultiServerMCPClient` | `McpServer.from_uc_function()` or `McpServer(url=...)` |
# MAGIC | Async pattern | `async with` context manager | `async with` context manager |
# MAGIC | MLflow tracing | Automatic via LangChain callbacks | Manual `mlflow.start_run()` or autolog |
# MAGIC
# MAGIC The OpenAI Agents SDK does **not** send data to OpenAI. All calls go to your Databricks PT endpoint — `base_url` controls the destination.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — UC Functions MCP with `McpServer`

# COMMAND ----------

import asyncio
import mlflow
from agents import Agent, Runner
from databricks_openai.agents import McpServer

MODEL = f"databricks/{PT_ENDPOINT}"

async def run_openai_agents_uc_demo(question: str) -> str:
    # McpServer.from_uc_function() builds the correct URL and handles auth automatically.
    async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA, timeout=30.0) as uc_server:
        agent = Agent(
            name="energy-ops-agent",
            instructions=(
                "You are an expert energy operations assistant for an Australian electricity "
                "network operator. Use your tools to answer questions about meter data and "
                "asset maintenance. Always cite specific numbers from tool results."
            ),
            model=MODEL,
            mcp_servers=[uc_server],
        )
        result = await Runner.run(agent, [{"role": "user", "content": question}])
    return result.final_output

question_uc = "What was the peak demand for NMI 6001234567 during July 2024?"
print(f"Question: {question_uc}\n")
answer_uc = asyncio.run(run_openai_agents_uc_demo(question_uc))
print("=" * 65)
print("AGENT ANSWER (OpenAI Agents SDK + UC Functions MCP):")
print("=" * 65)
print(answer_uc)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Combining UC Functions + Vector Search

# COMMAND ----------

async def run_openai_agents_multi_mcp(question: str) -> str:
    async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA, timeout=30.0) as uc_server:
        async with McpServer(
            url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
            timeout=30.0,
        ) as vs_server:
            agent = Agent(
                name="energy-ops-multi-agent",
                instructions=(
                    "You are an expert energy operations assistant. You have access to:\n"
                    "  - UC functions for meter calculations and asset lookups\n"
                    "  - A regulatory policy document search tool\n\n"
                    "Use the right tool for each part of the question. "
                    "Cite specific numbers, thresholds, and regulatory clauses."
                ),
                model=MODEL,
                mcp_servers=[uc_server, vs_server],
            )
            result = await Runner.run(agent, [{"role": "user", "content": question}])
    return result.final_output

question_multi = (
    "Asset TF-NSW-001 has had several maintenance events this year. "
    "How much outage time has it caused, and based on AER SAIDI requirements, "
    "should we be concerned about this asset's contribution to our reliability index?"
)
print(f"Question: {question_multi}\n")
answer_multi = asyncio.run(run_openai_agents_multi_mcp(question_multi))
print("=" * 65)
print("AGENT ANSWER (UC Functions + Vector Search MCP):")
print("=" * 65)
print(answer_multi)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Adding Genie (when Genie Space ID is configured)

# COMMAND ----------

async def run_openai_agents_with_genie(question: str) -> str:
    if GENIE_SPACE_ID == "":
        print("NOTE: Genie Space ID not configured — falling back to UC + VS.\n")
        return await run_openai_agents_multi_mcp(question)

    async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA, timeout=30.0) as uc_server:
        async with McpServer(url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}", timeout=60.0) as genie_server:
            async with McpServer(
                url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
                timeout=30.0,
            ) as vs_server:
                agent = Agent(
                    name="energy-ops-full-agent",
                    instructions=(
                        "You are an expert energy operations assistant. You have:\n"
                        "  - UC functions for peak demand calculations and asset lookups\n"
                        "  - A Genie Space for NL queries over meter consumption data\n"
                        "  - Regulatory policy document search\n\n"
                        "For meter data totals or trends, use Genie. "
                        "For individual meter calculations, use UC functions. "
                        "For regulations or compliance, use the policy search tool."
                    ),
                    model=MODEL,
                    mcp_servers=[uc_server, genie_server, vs_server],
                )
                result = await Runner.run(agent, [{"role": "user", "content": question}])
    return result.final_output

question_genie = "What is the total consumption in kWh for each NMI in the dataset?"
print(f"Question: {question_genie}\n")
answer_genie = asyncio.run(run_openai_agents_with_genie(question_genie))
print("=" * 65)
print("AGENT ANSWER (3 MCP servers incl. Genie):")
print("=" * 65)
print(answer_genie)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 — Production deployment: `get_databricks_resources()`
# MAGIC
# MAGIC When deploying to Databricks Model Serving, declare which resources the agent uses so Model Serving can inject service principal credentials at inference time.

# COMMAND ----------

# Production deployment pattern — reference only, do not run in the lab
#
# from databricks_openai.agents import McpServer
# from mlflow.models.resources import DatabricksResource
#
# async def build_agent_for_deployment():
#     async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA) as uc_server:
#         async with McpServer(
#             url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index"
#         ) as vs_server:
#             agent = Agent(name="energy-ops-prod", model=MODEL, mcp_servers=[uc_server, vs_server])
#
#             # Introspects MCP servers and returns resource declarations for Model Serving.
#             resources: list[DatabricksResource] = (
#                 await McpServer.get_databricks_resources([uc_server, vs_server])
#             )
#             return agent, resources
#
# # Then log to MLflow:
# # with mlflow.start_run():
# #     mlflow.pyfunc.log_model("agent", python_model=..., resources=resources)

print("get_databricks_resources() is required for Model Serving deployment — not needed in notebooks.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #00843D; color: white; padding: 12px 18px; border-radius: 6px; margin: 16px 0;">
# MAGIC   <strong>Checkpoint — Section 4</strong><br>
# MAGIC   OpenAI Agents SDK with <code>McpServer</code> async context managers connecting UC Functions,
# MAGIC   Vector Search, and Genie. Auth automatic. Saw <code>get_databricks_resources()</code> for production.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Bonus — Claude Desktop, SQL MCP, and Audit Trail
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 1 — Claude Desktop configuration
# MAGIC
# MAGIC Any MCP-compatible client connects to your workspace MCP servers using a PAT.
# MAGIC Config file: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
# MAGIC or `%APPDATA%\Claude\claude_desktop_config.json` (Windows). Restart Claude Desktop after editing.

# COMMAND ----------

config = {
    "mcpServers": {
        "databricks-uc-functions": {
            "command": "npx",
            "args": [
                "mcp-remote",
                f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}",
                "--header",
                "Authorization: Bearer <YOUR_PAT>"
            ]
        },
        "databricks-policy-docs": {
            "command": "npx",
            "args": [
                "mcp-remote",
                f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
                "--header",
                "Authorization: Bearer <YOUR_PAT>"
            ]
        }
    }
}

if GENIE_SPACE_ID != "":
    config["mcpServers"]["databricks-genie"] = {
        "command": "npx",
        "args": [
            "mcp-remote",
            f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            "--header",
            "Authorization: Bearer <YOUR_PAT>"
        ]
    }

print("claude_desktop_config.json snippet:")
print("=" * 65)
print(json.dumps(config, indent=2))
print("=" * 65)
print(f"\nGet a PAT at: {HOST}/settings/user/developer/access-tokens")
print("Use a short expiry (7-30 days). Never commit PATs to git.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 2 — SQL MCP server (reference)
# MAGIC
# MAGIC Exposes one `execute_sql` tool that runs arbitrary SQL. The LLM writes the SQL — unlike Genie which translates NL to SQL.
# MAGIC UC row-level security, column masks, and table grants still apply.
# MAGIC
# MAGIC ```python
# MAGIC sql_server = DatabricksMCPServer(
# MAGIC     name="databricks-sql",
# MAGIC     url=f"{HOST}/api/2.0/mcp/sql",
# MAGIC     timeout=30.0,
# MAGIC     handle_tool_error=True,
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC Use SQL MCP for technical agents with schema context in the system prompt.
# MAGIC Use Genie MCP for business user-facing agents where Genie handles schema discovery.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bonus 3 — Audit MCP calls in system tables

# COMMAND ----------

audit_query = f"""
SELECT
    event_time,
    user_identity.email         AS user_email,
    service_name,
    action_name,
    request_params              AS mcp_params
FROM system.access.audit
WHERE service_name IN ('vectorSearch', 'databricksSQL', 'genie', 'unityCatalog')
  AND event_time > current_timestamp() - INTERVAL 1 HOUR
ORDER BY event_time DESC
LIMIT 20
"""

print("SQL to audit recent MCP calls — run in any SQL cell:")
print("=" * 65)
print(audit_query)
print("=" * 65)
print("\nservice_name values: vectorSearch / genie / unityCatalog / databricksSQL")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Exercise — Add a Regulatory Compliance Tool
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Create a new UC function `check_regulatory_compliance` and add it to the multi-MCP agent.
# MAGIC
# MAGIC **Parameters:** `region` (STRING), `metric` (STRING: 'SAIDI' or 'SAIFI'), `actual_value` (DOUBLE)
# MAGIC **Returns JSON:** `region`, `metric`, `threshold`, `actual_value`, `breach` (bool), `penalty_estimate_aud`
# MAGIC **Penalty formula:** `(actual_value - threshold) * 15000` if in breach, else 0
# MAGIC
# MAGIC **Step 1:** Create the thresholds table.

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, DoubleType

threshold_rows = [
    ("NSW", "SAIDI", 250.0), ("VIC", "SAIDI", 230.0),
    ("QLD", "SAIDI", 270.0), ("SA",  "SAIDI", 260.0),
    ("NSW", "SAIFI", 1.5),   ("VIC", "SAIFI", 1.4),
    ("QLD", "SAIFI", 1.6),   ("SA",  "SAIFI", 1.5),
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

print(f"Created {CATALOG}.{SCHEMA}.regulatory_thresholds")
spark.table(f"{CATALOG}.{SCHEMA}.regulatory_thresholds").show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 2:** Register the UC function — uncomment and run.

# COMMAND ----------

# TODO: Uncomment the block below and run.
#
# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.check_regulatory_compliance(
#     region       STRING COMMENT 'Australian state code: NSW, VIC, QLD, or SA',
#     metric       STRING COMMENT 'Reliability metric to check: SAIDI or SAIFI',
#     actual_value DOUBLE COMMENT 'The actual measured value for the metric this period'
# )
# RETURNS STRING
# COMMENT 'Check whether a SAIDI or SAIFI reliability metric is in breach of AER regulatory
# thresholds for a given Australian state. Returns JSON with: region, metric, threshold,
# actual_value, breach (bool), and penalty_estimate_aud. Use when asked whether performance
# targets have been met or what financial penalty exposure the network faces.'
# LANGUAGE PYTHON
# AS $$
# import json
# try:
#     from pyspark.sql import SparkSession
#     from pyspark.sql import functions as F
#     spark = SparkSession.builder.getOrCreate()
#     row = (
#         spark.table("{CATALOG}.{SCHEMA}.regulatory_thresholds")
#         .filter((F.col("region") == region) & (F.col("metric") == metric))
#         .first()
#     )
#     if row is None:
#         return json.dumps({{"error": f"No threshold found for {{metric}} in {{region}}"}})
#     threshold = float(row["threshold"])
#     breach = actual_value > threshold
#     penalty = round((actual_value - threshold) * 15000, 2) if breach else 0.0
#     return json.dumps({{
#         "region": region, "metric": metric, "threshold": threshold,
#         "actual_value": actual_value, "breach": breach, "penalty_estimate_aud": penalty,
#     }})
# except Exception as e:
#     return json.dumps({{"error": str(e)}})
# $$
# """)
# print(f"Registered: {CATALOG}.{SCHEMA}.check_regulatory_compliance")

print("Exercise: uncomment the block above and run to register check_regulatory_compliance.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Step 3:** The new function is automatically discovered by the next call to `get_tools()` — no code changes to the agent needed.
# MAGIC
# MAGIC **Test question:**
# MAGIC ```python
# MAGIC answer = asyncio.run(run_langgraph_agent(
# MAGIC     "The NSW network had 278 minutes of SAIDI this year. "
# MAGIC     "Are we in breach of AER thresholds? What is our estimated penalty exposure?"
# MAGIC ))
# MAGIC print(answer)
# MAGIC ```
# MAGIC
# MAGIC **Success criteria:**
# MAGIC
# MAGIC | Check | What to verify |
# MAGIC |-------|---------------|
# MAGIC | SQL test | `SELECT workshop_au.workshop_lab.check_regulatory_compliance('NSW', 'SAIDI', 278)` returns `breach: true, penalty_estimate_aud: 420000.0` |
# MAGIC | MLflow trace | Tool call appears as `workshop_au__workshop_lab__check_regulatory_compliance` in the Traces tab |
# MAGIC | Tool routing | LLM routes to `check_regulatory_compliance`, not `search_policy_docs_index` |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 20px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 04 Complete</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; margin-bottom: 14px;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.3);">
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Lab</th>
# MAGIC       <th style="text-align: left; padding: 6px 10px;">Core skill</th>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 01</td>
# MAGIC       <td style="padding: 5px 10px;">Genie Code — generate, explain, fix, document</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 02</td>
# MAGIC       <td style="padding: 5px 10px;">Notebook AI chat — schema discovery, SQL gen, agent mode</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.15);">
# MAGIC       <td style="padding: 5px 10px;">Lab 03</td>
# MAGIC       <td style="padding: 5px 10px;">UC functions as AI tools — register, test, govern</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 5px 10px;">Lab 04</td>
# MAGIC       <td style="padding: 5px 10px;">MCP integration — UC Functions + Genie + Vector Search, all AU East</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 6px 0; font-weight: bold;">Key packages:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0 0 12px 0; padding-left: 20px;">
# MAGIC     <li><code>databricks-mcp</code> — <code>DatabricksMCPClient</code> for tool discovery and direct calls</li>
# MAGIC     <li><code>databricks-langchain</code> — <code>DatabricksMultiServerMCPClient</code> for LangGraph agents</li>
# MAGIC     <li><code>databricks-openai</code> — <code>McpServer</code> for the OpenAI Agents SDK pattern</li>
# MAGIC   </ul>
# MAGIC   <p style="color: rgba(255,255,255,0.9); font-weight: bold;">Next steps:</p>
# MAGIC   <ul style="color: rgba(255,255,255,0.85); margin: 0; padding-left: 20px;">
# MAGIC     <li>Lab 05 (optional): Deploy MCP agents to Model Serving using <code>get_databricks_resources()</code></li>
# MAGIC     <li>Workshop 2B: No-code NL-to-SQL Genie Spaces for business users</li>
# MAGIC     <li>Production checklist: Service Principal auth, Secret Scopes, MLflow Tracing in Model Serving</li>
# MAGIC   </ul>
# MAGIC </div>
