# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 04 SOLUTION: MCP Integration
# MAGIC **Reference solution — all exercises completed. Share with participants after the lab.**

# COMMAND ----------

%pip install databricks-mcp databricks-langchain databricks-openai mlflow --quiet
dbutils.library.restartPython()

# COMMAND ----------

import os, json, requests, asyncio, mlflow
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",         "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("genie_space_id", "FILL_IN",              "Genie Space ID")
dbutils.widgets.text("vs_index",       "workshop_au.energy.policy_docs_index", "VS index (3-part name)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA         = dbutils.widgets.get("schema")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
VS_INDEX_NAME  = dbutils.widgets.get("vs_index")

ws = WorkspaceClient()
HOST = ws.config.host.rstrip("/")
DATABRICKS_TOKEN = ws.config.token

print(f"Workspace host : {HOST}")
print(f"Catalog.Schema : {CATALOG}.{SCHEMA}")
print(f"PT endpoint    : {PT_ENDPOINT}")
print(f"Genie Space ID : {GENIE_SPACE_ID}")
print(f"VS index       : {VS_INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2 — UC Functions via MCP: SOLUTION

# COMMAND ----------

# SOLUTION 2.2: Discover tools with DatabricksMCPClient
from databricks_mcp import DatabricksMCPClient

uc_mcp_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}"
print(f"UC Functions MCP endpoint: {uc_mcp_url}\n")

client = DatabricksMCPClient(uc_mcp_url, ws)
tools = client.list_tools()

print(f"Discovered {len(tools)} tool(s) in {CATALOG}.{SCHEMA}:\n")
for t in tools:
    print(f"  Tool name  : {t.name}")
    print(f"  Description: {t.description[:120]}...")
    if hasattr(t, "inputSchema") and t.inputSchema:
        params = list(t.inputSchema.get("properties", {}).keys())
        print(f"  Parameters : {params}")
    print()

# COMMAND ----------

# SOLUTION 2.3: Call a UC function directly via DatabricksMCPClient
tool_name = f"{CATALOG}__{SCHEMA}__calculate_peak_demand"

print(f"Calling tool: {tool_name}")
result = client.call_tool(
    tool_name,
    {"nmi": "6001234567", "start_date": "2024-07-01", "end_date": "2024-07-07"},
)

print("Raw MCP response:")
print(json.dumps(result, indent=2, default=str))

# COMMAND ----------

# SOLUTION 2.4: Parse the MCP response
if result and "content" in result:
    raw_text = result["content"][0]["text"]
    parsed = json.loads(raw_text)
    print("Parsed function result:")
    for k, v in parsed.items():
        print(f"  {k:<25} {v}")

# COMMAND ----------

# SOLUTION 2.5: Single-function endpoint
single_fn_url = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}/calculate_peak_demand"
single_client = DatabricksMCPClient(single_fn_url, ws)
single_tools = single_client.list_tools()
print(f"Single-function endpoint exposes {len(single_tools)} tool(s):")
for t in single_tools:
    print(f"  {t.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3 — Multi-MCP Agent with LangGraph: SOLUTION

# COMMAND ----------

# SOLUTION 3.2: Create regulatory policy documents table + VS index setup
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

policy_docs = [
    (1, "SAIDI Reporting Requirements",
     "SAIDI measures the total duration of interruptions per customer per year. "
     "Under AER STPIS, the threshold for NSW is 250 minutes per customer per year. "
     "Breaches attract AUD 15,000 per customer per minute above threshold."),
    (2, "NEM12 Data Quality Standards",
     "NEM12 files must contain 48 interval records per day per meter. "
     "Estimated reads exceeding 5% of intervals in a billing period require mandatory "
     "customer notification under National Energy Retail Rules clause 46."),
    (3, "Critical Peak Demand Management",
     "AEMO may issue Emergency Backstop Mechanism directions. Retailers must curtail "
     "consumption by 10% within 30 minutes of an EBM notice."),
    (4, "Meter Data Retention Policy",
     "Under the Privacy Act 1988 and NERR, meter data must be retained for 7 years. "
     "Data must be stored in Australia (s.16C Privacy Act). Customer access within 5 business days."),
    (5, "Voltage Quality Compliance",
     "DNSPs must maintain supply voltage within -6% to +10% of nominal (230V). "
     "Persistent exceedances trigger network remediation within 12 months."),
    (6, "Critical Infrastructure Cybersecurity",
     "Under SOCI Act 2018, operators must implement a CIRMP. AEMO requires notification "
     "of significant cyber incidents within 12 hours."),
]

schema_struct = StructType([
    StructField("doc_id",  IntegerType(), False),
    StructField("title",   StringType(),  True),
    StructField("content", StringType(),  True),
])

df_docs = spark.createDataFrame(policy_docs, schema=schema_struct)
df_docs.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_policy_docs")
print(f"Created {CATALOG}.{SCHEMA}.regulatory_policy_docs with {df_docs.count()} documents")

# COMMAND ----------

# SOLUTION 3.3: Create Vector Search index
from databricks.sdk.service.vectorsearch import (
    EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn, PipelineType
)

VS_ENDPOINT_NAME = "workshop-vs-endpoint"

try:
    ws.vector_search_endpoints.create_endpoint(
        name=VS_ENDPOINT_NAME,
        endpoint_type=EndpointType.STANDARD,
    )
    print(f"Created VS endpoint: {VS_ENDPOINT_NAME}. Waiting ~5 minutes for ONLINE state...")
    ws.vector_search_endpoints.wait_get_endpoint_vector_search_endpoint_online(VS_ENDPOINT_NAME)
    print("Endpoint is ONLINE.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Endpoint '{VS_ENDPOINT_NAME}' already exists — skipping.")
    else:
        print(f"Endpoint note: {e}")

VS_INDEX_FULL = f"{CATALOG}.{SCHEMA}.policy_docs_index"

try:
    ws.vector_search_indexes.create_index(
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
                    # ✅ qwen3-embedding — in-region for AU East
                    embedding_model_endpoint_name="databricks-qwen3-embedding-0-6b",
                )
            ],
        ),
    )
    print(f"Created index: {VS_INDEX_FULL}. Sync in progress — wait 2-3 minutes.")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Index '{VS_INDEX_FULL}' already exists — triggering sync...")
        ws.vector_search_indexes.sync_index(VS_INDEX_FULL)
        print("Sync triggered.")
    else:
        print(f"Index note: {e}")

VS_INDEX_NAME = VS_INDEX_FULL
print(f"\nUsing VS index: {VS_INDEX_NAME}")

# COMMAND ----------

# SOLUTION 3.4: Configure MCP servers
from databricks_langchain import (
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
    ChatDatabricks,
)

uc_server = DatabricksMCPServer.from_uc_function(
    catalog=CATALOG,
    schema=SCHEMA,
    name="uc-tools",
    timeout=30.0,
    handle_tool_error=True,
)

vs_server = DatabricksMCPServer(
    name="policy-docs-vs",
    url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
    timeout=30.0,
    handle_tool_error=True,
)

servers = [uc_server, vs_server]

if GENIE_SPACE_ID != "FILL_IN":
    genie_server = DatabricksMCPServer(
        name="energy-genie",
        url=f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
        timeout=60.0,
        handle_tool_error=True,
    )
    servers.append(genie_server)
    print("MCP servers configured: UC Functions + Vector Search + Genie Space")
else:
    print("NOTE: Genie Space ID not set — using UC Functions + Vector Search only.")

print(f"Total MCP servers: {len(servers)}: " + ", ".join(s.name for s in servers))

# COMMAND ----------

# SOLUTION 3.5: Inspect aggregated tools
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

# SOLUTION 3.6: Build the ReAct agent
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

mlflow.set_experiment("/Shared/workshop-lab04-mcp-agent")

llm = ChatDatabricks(
    endpoint=PT_ENDPOINT,
    temperature=0.0,
    max_tokens=2048,
)

system_prompt = (
    "You are an expert energy operations assistant for an Australian electricity network operator. "
    "Always use your tools to answer questions — never guess or estimate values. "
    "Reference specific numbers, dates, and regulatory requirements where relevant."
)

async def run_langgraph_agent(question: str, run_name: str = "agent_run") -> str:
    async with DatabricksMultiServerMCPClient(servers) as multi_client:
        agent_tools = await multi_client.get_tools()
        agent = create_react_agent(model=llm, tools=agent_tools, prompt=system_prompt)
        with mlflow.start_run(run_name=run_name):
            result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content

# COMMAND ----------

# SOLUTION 3.7: Question 1 — UC Function tool (peak demand)
q1 = "What was the peak demand for meter NMI 6001234567 during the first week of July 2024, and at what time of day did it occur?"
print(f"Question: {q1}\n")
answer1 = asyncio.run(run_langgraph_agent(q1, run_name="q1_peak_demand"))
print("=" * 65)
print("AGENT ANSWER:")
print("=" * 65)
print(answer1)

# COMMAND ----------

# SOLUTION 3.8: Question 2 — Vector Search tool
q2 = "Our meter for NMI 6001234567 has about 3% estimated reads this month. Does this comply with NEM12 standards?"
print(f"Question: {q2}\n")
answer2 = asyncio.run(run_langgraph_agent(q2, run_name="q2_nem12_compliance"))
print("=" * 65)
print("AGENT ANSWER:")
print("=" * 65)
print(answer2)

# COMMAND ----------

# SOLUTION 3.9: Question 3 — Multi-tool chain
q3 = (
    "Morning operations briefing — three things:\n"
    "1. Peak demand for meter 6001234567 in the first week of July 2024.\n"
    "2. Maintenance status of asset TF-NSW-001.\n"
    "3. What are the regulatory data retention obligations for our meter data?"
)
print(f"Question:\n{q3}\n")
answer3 = asyncio.run(run_langgraph_agent(q3, run_name="q3_multi_tool_briefing"))
print("=" * 65)
print("AGENT ANSWER:")
print("=" * 65)
print(answer3)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4 — OpenAI Agents SDK Pattern: SOLUTION

# COMMAND ----------

# SOLUTION 4.2: McpServer with UC Functions
from agents import Agent, Runner
from databricks_openai.agents import McpServer

MODEL = f"databricks/{PT_ENDPOINT}"

async def run_openai_agents_uc_demo(question: str) -> str:
    async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA, timeout=30.0) as uc_server:
        agent = Agent(
            name="energy-ops-agent",
            instructions=(
                "You are an expert energy operations assistant for an Australian electricity "
                "network operator. Use your tools to answer questions about meter data and "
                "asset maintenance. Always cite specific numbers from the tool results."
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

# SOLUTION 4.3: UC Functions + Vector Search MCP
async def run_openai_agents_multi_mcp(question: str) -> str:
    async with McpServer.from_uc_function(catalog=CATALOG, schema=SCHEMA, timeout=30.0) as uc_server:
        async with McpServer(
            url=f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA}/policy_docs_index",
            timeout=30.0,
        ) as vs_server:
            agent = Agent(
                name="energy-ops-multi-agent",
                instructions=(
                    "You are an expert energy operations assistant. "
                    "Use UC functions for meter calculations and asset lookups. "
                    "Use the policy document search for regulatory questions. "
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

# SOLUTION 4.4: Three MCP servers including Genie
async def run_openai_agents_with_genie(question: str) -> str:
    if GENIE_SPACE_ID == "FILL_IN":
        print("NOTE: Genie Space ID not configured — running with UC + VS only.")
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
                        "For meter data totals or trends, use the Genie tool. "
                        "For individual meter calculations, use UC functions. "
                        "For regulatory questions, use the policy search tool. "
                        "Cite specific numbers and regulatory references."
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
# MAGIC ## Exercise 9.1 SOLUTION — `check_regulatory_compliance` UC Function

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.check_regulatory_compliance(
    region       STRING COMMENT 'NEM region to check (e.g. NSW1, VIC1, QLD1, SA1)',
    metric       STRING COMMENT 'Reliability metric: SAIDI or SAIFI',
    actual_value DOUBLE COMMENT 'The actual measured value for the metric this year'
)
RETURNS STRING
COMMENT 'Check whether a NEM region''s reliability metric is within AER regulatory limits.
Returns JSON with: region, metric, actual_value, threshold_limit, unit, breach (bool),
excess_over_limit, penalty_estimate_aud, and assessment. Penalty: excess * 15000 AUD per unit.
Use when asked about regulatory compliance, AER performance, SAIDI/SAIFI breaches, or penalties.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("{CATALOG}.{SCHEMA}.regulatory_thresholds")
        .filter(F.col("region") == region)
        .filter(F.upper(F.col("threshold_type")) == metric.upper())
        .orderBy(F.col("effective_from").desc())
    )

    if df.count() == 0:
        reference = {{
            "NSW1": {{"SAIDI": 250.0, "SAIFI": 2.5}},
            "VIC1": {{"SAIDI": 230.0, "SAIFI": 2.2}},
            "QLD1": {{"SAIDI": 260.0, "SAIFI": 2.8}},
            "SA1":  {{"SAIDI": 240.0, "SAIFI": 2.4}},
        }}
        limit = reference.get(region, {{}}).get(metric.upper(), 250.0)
        unit = "minutes/year" if metric.upper() == "SAIDI" else "outages/year"
    else:
        row = df.first()
        limit = float(row["limit_value"])
        unit = row["unit"]

    breach = actual_value > limit
    excess = max(0.0, actual_value - limit)
    penalty = round(excess * 15000.0, 2) if breach else 0.0

    result = {{
        "region": region,
        "metric": metric.upper(),
        "actual_value": actual_value,
        "threshold_limit": limit,
        "unit": unit,
        "breach": breach,
        "excess_over_limit": round(excess, 2),
        "penalty_estimate_aud": penalty,
        "assessment": (
            f"BREACH — {{metric.upper()}} of {{actual_value}} {{unit}} exceeds limit of {{limit}}. "
            f"Indicative penalty: AUD {{penalty:,.0f}}."
            if breach else
            f"COMPLIANT — {{metric.upper()}} of {{actual_value}} {{unit}} is within limit of {{limit}}."
        ),
    }}
    return json.dumps(result)

except Exception as e:
    return json.dumps({{"error": str(e)}})
$$
""".format(CATALOG=CATALOG, SCHEMA=SCHEMA))

print(f"Registered: {CATALOG}.{SCHEMA}.check_regulatory_compliance")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test: NSW1 with 278 minutes SAIDI (exceeds 250 limit)
# MAGIC SELECT workshop_au.energy.check_regulatory_compliance('NSW1', 'SAIDI', 278.0) AS compliance_result

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test: compliant case
# MAGIC SELECT workshop_au.energy.check_regulatory_compliance('VIC1', 'SAIDI', 210.0) AS compliance_result

# COMMAND ----------

# SOLUTION: Run the updated agent with the compliance tool added
from openai import OpenAI

llm_client = OpenAI(
    base_url=f"{HOST}/serving-endpoints",
    api_key=DATABRICKS_TOKEN,
)

def call_uc_function_via_mcp(function_name, arguments, catalog, schema, workspace_url, token):
    endpoint = f"{workspace_url}/api/2.0/mcp/functions/{catalog}/{schema}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"method": "tools/call", "params": {"name": function_name, "arguments": arguments}}
    r = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}

tools_spec_v2 = [
    {
        "type": "function",
        "function": {
            "name": "calculate_peak_demand",
            "description": "Calculate peak 30-minute demand for a NEM meter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nmi": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["nmi", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_regulatory_compliance",
            "description": (
                "Check whether a NEM region's reliability metric (SAIDI or SAIFI) is within "
                "AER regulatory limits. Returns breach status and indicative penalty in AUD."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string"},
                    "metric": {"type": "string"},
                    "actual_value": {"type": "number"},
                },
                "required": ["region", "metric", "actual_value"],
            },
        },
    },
]

def execute_tool_v2(tool_name: str, tool_args: dict) -> str:
    if tool_name == "calculate_peak_demand":
        return json.dumps(call_uc_function_via_mcp("calculate_peak_demand", tool_args, CATALOG, SCHEMA, HOST, DATABRICKS_TOKEN), default=str)
    elif tool_name == "check_regulatory_compliance":
        return json.dumps(call_uc_function_via_mcp("check_regulatory_compliance", tool_args, CATALOG, SCHEMA, HOST, DATABRICKS_TOKEN), default=str)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run_agent_v2(user_question, verbose=True):
    messages = [
        {"role": "system", "content": "You are an energy operations assistant. Use your tools to answer questions accurately."},
        {"role": "user", "content": user_question},
    ]
    for _ in range(6):
        response = llm_client.chat.completions.create(
            model="databricks-claude-sonnet-4-6",
            messages=messages,
            tools=tools_spec_v2,
            tool_choice="auto",
            temperature=0.0,
            max_tokens=2048,
        )
        msg = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in (msg.tool_calls or [])
            ] or None,
        })
        if not msg.tool_calls:
            return msg.content or ""
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            if verbose:
                print(f"\n[Tool] {name}({args})")
            result_str = execute_tool_v2(name, args)
            if verbose:
                print(f"[Result] {result_str[:200]}...")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})
    return "Max iterations reached."


# Test the compliance tool via the agent
answer = run_agent_v2(
    "The NSW1 network had 278 minutes of SAIDI this year. "
    "Are we in breach of AER thresholds, and what is the indicative penalty?"
)
print("\n=== SOLUTION AGENT RESPONSE ===")
print(answer)

# COMMAND ----------

print("=" * 60)
print("Lab 04 SOLUTION — Complete")
print("=" * 60)
print()
print("  [DONE] Section 2: DatabricksMCPClient tool discovery + direct call")
print("  [DONE] Section 2: Single-function endpoint demonstrated")
print("  [DONE] Section 3: Regulatory policy docs table + VS index created")
print("  [DONE] Section 3: Multi-MCP server config (UC + VS + Genie)")
print("  [DONE] Section 3: Tool aggregation inspected")
print("  [DONE] Section 3: LangGraph ReAct agent — 3 questions tested")
print("  [DONE] Section 4: OpenAI Agents SDK — UC + VS + Genie patterns")
print("  [DONE] Exercise 9.1: check_regulatory_compliance registered + agent tested")
