# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 04 SOLUTION: MCP Integration
# MAGIC **For facilitator use — share with participants after the lab.**

# COMMAND ----------

%pip install openai databricks-sdk mlflow --quiet
dbutils.library.restartPython()

# COMMAND ----------

import os, json, requests
from databricks.sdk import WorkspaceClient

CATALOG        = "main"
SCHEMA         = "workshop_lab"
WORKSPACE_URL  = "https://adb-XXXXXXXXXXXXXXXXX.X.azuredatabricks.net"  # TODO: update
GENIE_SPACE_ID = "XXXXXXXXXXXX"  # TODO: update
VS_INDEX_NAME  = f"{CATALOG}.{SCHEMA}.policy_docs_index"

DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

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
excess_over_limit, and penalty_estimate_aud. Penalty formula: excess * 15000 AUD per unit.
Use when asked about regulatory compliance, AER performance, SAIDI/SAIFI breaches, or penalties.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("main.workshop_lab.regulatory_thresholds")
        .filter(F.col("region") == region)
        .filter(F.upper(F.col("threshold_type")) == metric.upper())
        .orderBy(F.col("effective_from").desc())
    )

    if df.count() == 0:
        # No threshold configured — return reference values for NSW1/VIC1 SAIDI
        reference = {
            "NSW1": {"SAIDI": 250.0, "SAIFI": 2.5},
            "VIC1": {"SAIDI": 230.0, "SAIFI": 2.2},
            "QLD1": {"SAIDI": 260.0, "SAIFI": 2.8},
            "SA1":  {"SAIDI": 240.0, "SAIFI": 2.4},
        }
        limit = reference.get(region, {}).get(metric.upper(), 250.0)
        unit = "minutes/year" if metric.upper() == "SAIDI" else "outages/year"
    else:
        row = df.first()
        limit = float(row["limit_value"])
        unit = row["unit"]

    breach = actual_value > limit
    excess = max(0.0, actual_value - limit)
    # AER STPIS penalty: AUD 15,000 per customer per minute/outage above threshold
    # Simplified here — real penalty involves customer count and incentive rate
    penalty = round(excess * 15000.0, 2) if breach else 0.0

    result = {
        "region": region,
        "metric": metric.upper(),
        "actual_value": actual_value,
        "threshold_limit": limit,
        "unit": unit,
        "breach": breach,
        "excess_over_limit": round(excess, 2),
        "penalty_estimate_aud": penalty,
        "assessment": (
            f"BREACH — {metric.upper()} of {actual_value} {unit} exceeds limit of {limit}. "
            f"Indicative penalty: AUD {penalty:,.0f}."
            if breach else
            f"COMPLIANT — {metric.upper()} of {actual_value} {unit} is within limit of {limit}."
        ),
    }
    return json.dumps(result)

except Exception as e:
    return json.dumps({"error": str(e)})
$$
""")

print(f"Registered: {CATALOG}.{SCHEMA}.check_regulatory_compliance")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test: NSW1 with 278 minutes SAIDI (exceeds 250 limit)
# MAGIC SELECT main.workshop_lab.check_regulatory_compliance('NSW1', 'SAIDI', 278.0) AS compliance_result

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test: compliant case
# MAGIC SELECT main.workshop_lab.check_regulatory_compliance('VIC1', 'SAIDI', 210.0) AS compliance_result

# COMMAND ----------

# MAGIC %md
# MAGIC ## Full agent with the new compliance tool added

# COMMAND ----------

from openai import OpenAI

llm_client = OpenAI(
    base_url=f"{WORKSPACE_URL}/serving-endpoints",
    api_key=DATABRICKS_TOKEN,
)

# Helper functions from the main lab
def call_genie_mcp(question, space_id, workspace_url, token):
    if space_id == "XXXXXXXXXXXX":
        return {"answer": "Genie Space not configured — update GENIE_SPACE_ID.", "sql": "N/A", "rows": []}
    endpoint = f"{workspace_url}/api/2.0/mcp/genie/{space_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"method": "tools/call", "params": {"name": "genie_query", "arguments": {"question": question}}}
    r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}

def search_policy_docs(query, index_name, num_results=3):
    w = WorkspaceClient()
    try:
        results = w.vector_search_indexes.query_index(
            index_name=index_name, columns=["doc_id", "title", "content"],
            query_text=query, num_results=num_results)
        docs = []
        if results.result and results.result.data_array:
            col_names = [c.name for c in results.result.manifest.columns]
            for row in results.result.data_array:
                docs.append(dict(zip(col_names, row)))
        return docs
    except Exception as e:
        return [{"error": str(e)}]

def call_uc_function_via_mcp(function_name, arguments, catalog, schema, workspace_url, token):
    endpoint = f"{workspace_url}/api/2.0/mcp/functions/{catalog}/{schema}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"method": "tools/call", "params": {"name": function_name, "arguments": arguments}}
    r = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}

# COMMAND ----------

# Updated tool spec includes check_regulatory_compliance
tools_spec_v2 = [
    {
        "type": "function",
        "function": {
            "name": "query_genie_space",
            "description": "Ask a natural language question about meter consumption data.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy_documents",
            "description": "Search regulatory policy and compliance documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "num_results": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
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
                "AER regulatory limits. Returns breach status, excess over threshold, and "
                "indicative penalty estimate in AUD."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "NEM region (e.g. NSW1, VIC1)"},
                    "metric": {"type": "string", "description": "SAIDI or SAIFI"},
                    "actual_value": {"type": "number", "description": "Measured value this year"},
                },
                "required": ["region", "metric", "actual_value"],
            },
        },
    },
]

def execute_tool_v2(tool_name: str, tool_args: dict) -> str:
    if tool_name == "query_genie_space":
        return json.dumps(call_genie_mcp(tool_args["question"], GENIE_SPACE_ID, WORKSPACE_URL, DATABRICKS_TOKEN), default=str)
    elif tool_name == "search_policy_documents":
        results = search_policy_docs(tool_args["query"], VS_INDEX_NAME, tool_args.get("num_results", 3))
        if results and "error" in results[0]:
            return json.dumps({"error": results[0]["error"]})
        return json.dumps([{"title": r.get("title",""), "excerpt": str(r.get("content",""))[:300]} for r in results])
    elif tool_name == "calculate_peak_demand":
        return json.dumps(call_uc_function_via_mcp("calculate_peak_demand", tool_args, CATALOG, SCHEMA, WORKSPACE_URL, DATABRICKS_TOKEN), default=str)
    elif tool_name == "check_regulatory_compliance":
        return json.dumps(call_uc_function_via_mcp("check_regulatory_compliance", tool_args, CATALOG, SCHEMA, WORKSPACE_URL, DATABRICKS_TOKEN), default=str)
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

# COMMAND ----------

def run_agent_v2(user_question, verbose=True):
    messages = [
        {"role": "system", "content": "You are an energy operations assistant for an Australian electricity network operator. Use your tools to answer questions. Never guess values."},
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
            "tool_calls": [{"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in (msg.tool_calls or [])] or None,
        })
        if not msg.tool_calls:
            return msg.content or ""
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            if verbose:
                print(f"\n[Tool] {name}({args})")
            result = execute_tool_v2(name, args)
            if verbose:
                print(f"[Result] {result[:200]}...")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "Max iterations reached."

# COMMAND ----------

# Test the compliance tool via the agent
answer = run_agent_v2(
    "The NSW1 network had 278 minutes of SAIDI this year. "
    "Are we in breach of AER thresholds, and what is the indicative penalty?"
)
print("\n=== SOLUTION AGENT RESPONSE ===")
print(answer)
