# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 03 SOLUTION: Adding Skills & UC Functions as AI Tools
# MAGIC **For facilitator use — share with participants after the lab.**

# COMMAND ----------

%pip install databricks-langchain mlflow langchain langchain-community --quiet
dbutils.library.restartPython()

# COMMAND ----------

CATALOG = "main"
SCHEMA  = "workshop_lab"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercise 6.1 SOLUTION — `calculate_demand_statistics` UC Function

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_demand_statistics(
    nmi   STRING COMMENT 'National Meter Identifier to analyse',
    month STRING COMMENT 'Month to analyse in YYYY-MM format (e.g. 2024-07)'
)
RETURNS STRING
COMMENT 'Calculate aggregate demand statistics for a NEM meter over a calendar month.
Returns JSON with: nmi, month, avg_daily_kwh, max_daily_kwh, min_daily_kwh,
std_daily_kwh, and month_total_kwh. Use when asked about consumption statistics,
average usage, variability, or monthly totals for a specific meter.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    # Build year/month filter from YYYY-MM input
    year, mon = month.split('-')

    df = (
        spark.table("main.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.year(F.col("read_date")) == int(year))
        .filter(F.month(F.col("read_date")) == int(mon))
        .filter(F.col("quality_flag").isin(["A", "S"]))
    )

    if df.count() == 0:
        return json.dumps({"error": f"No actual reads for NMI {nmi} in {month}"})

    # Daily totals
    daily = df.groupBy("read_date").agg(F.sum("read_kwh").alias("daily_kwh"))

    stats = daily.agg(
        F.round(F.avg("daily_kwh"), 3).alias("avg_daily_kwh"),
        F.round(F.max("daily_kwh"), 3).alias("max_daily_kwh"),
        F.round(F.min("daily_kwh"), 3).alias("min_daily_kwh"),
        F.round(F.stddev("daily_kwh"), 3).alias("std_daily_kwh"),
        F.round(F.sum("daily_kwh"), 3).alias("month_total_kwh"),
        F.count("*").alias("days_with_data"),
    ).first()

    result = {
        "nmi": nmi,
        "month": month,
        "avg_daily_kwh":   float(stats["avg_daily_kwh"]   or 0),
        "max_daily_kwh":   float(stats["max_daily_kwh"]   or 0),
        "min_daily_kwh":   float(stats["min_daily_kwh"]   or 0),
        "std_daily_kwh":   float(stats["std_daily_kwh"]   or 0),
        "month_total_kwh": float(stats["month_total_kwh"] or 0),
        "days_with_data":  int(stats["days_with_data"]),
    }
    return json.dumps(result)

except Exception as e:
    return json.dumps({"error": str(e)})
$$
""")

print(f"Registered: {CATALOG}.{SCHEMA}.calculate_demand_statistics")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test calculate_demand_statistics (requires data from the main lab section)
# MAGIC SELECT main.workshop_lab.calculate_demand_statistics('6001234567', '2024-07') AS stats_result

# COMMAND ----------

# MAGIC %md
# MAGIC ## Full agent with 4 tools (including the new one)

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks_langchain import UCFunctionToolkit, ChatDatabricks
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

w = WorkspaceClient()

# All 4 tools — the original 3 plus the new statistics tool
toolkit = UCFunctionToolkit(
    warehouse_id=None,
    tools_names=[
        f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
        f"{CATALOG}.{SCHEMA}.get_meter_readings_summary",
        f"{CATALOG}.{SCHEMA}.lookup_asset_status",
        f"{CATALOG}.{SCHEMA}.calculate_demand_statistics",  # new
    ],
)
tools = toolkit.get_tools()

print(f"Loaded {len(tools)} tools:")
for t in tools:
    print(f"  - {t.name}")

# COMMAND ----------

llm = ChatDatabricks(
    endpoint="databricks-claude-sonnet-4-6",
    temperature=0.0,
    max_tokens=2048,
)

system_prompt = """You are an energy operations assistant for an Australian electricity network operator.
You have access to tools for querying live operational data.
Always use the tools to answer questions — do not guess values."""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)

# Test the new statistics tool
response = agent_executor.invoke({
    "input": "What were the demand statistics for meter 6001234567 in July 2024?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])
