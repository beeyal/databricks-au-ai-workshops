# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 03: Adding Skills & UC Functions as AI Tools
# MAGIC **Workshop:** Genie Code for Developers — Australian Regulated Industries
# MAGIC **Estimated time:** 45 minutes
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What you'll learn
# MAGIC
# MAGIC | Topic | Time |
# MAGIC |-------|------|
# MAGIC | What "skills" are for AI agents | 5 min |
# MAGIC | Registering Python functions as UC functions | 10 min |
# MAGIC | Decorating for LLM discoverability | 5 min |
# MAGIC | Creating energy-domain tools | 10 min |
# MAGIC | Using UC functions with LangChain / agents SDK | 10 min |
# MAGIC | Wrap-up exercises | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What are "skills" in an AI agent context?
# MAGIC
# MAGIC In Databricks, **skills** (also called **tools** or **AI functions**) are Python functions
# MAGIC that an LLM can call at runtime. The agent:
# MAGIC 1. Sees a **description** of each tool (its docstring + type hints)
# MAGIC 2. Decides *when* to call it based on the user's query
# MAGIC 3. Passes typed arguments to the function
# MAGIC 4. Receives the result and incorporates it into its answer
# MAGIC
# MAGIC **In Databricks**, tools are registered as **Unity Catalog (UC) functions** —
# MAGIC which gives you governance, lineage, and discoverability across your organisation.
# MAGIC
# MAGIC ```
# MAGIC User query
# MAGIC     ↓
# MAGIC LLM reasons about which tool to call
# MAGIC     ↓
# MAGIC Calls UC function (e.g., calculate_peak_demand)
# MAGIC     ↓
# MAGIC Spark / Python executes the function
# MAGIC     ↓
# MAGIC Result returned to LLM → final response
# MAGIC ```
# MAGIC
# MAGIC > **AU East:** UC functions execute within your Databricks workspace in Australia East.
# MAGIC > No data leaves the region when a tool is called.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup

# COMMAND ----------

# Install required packages
# databricks-langchain provides UCFunctionToolkit for wrapping UC functions as LangChain tools
%pip install databricks-langchain mlflow langchain langchain-community --quiet
dbutils.library.restartPython()

# COMMAND ----------

# TODO: Update these values for your workspace
CATALOG    = "main"          # TODO: your catalog name
SCHEMA     = "workshop_lab"  # TODO: your schema name (must exist from Lab 02, or create it)
WORKSPACE_URL = "https://adb-XXXXXXXXXXXXXXXXX.X.azuredatabricks.net"  # TODO: your workspace URL

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"Using: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Writing Functions for LLM Use
# MAGIC
# MAGIC A function that an LLM can call well needs:
# MAGIC
# MAGIC | Requirement | Why it matters |
# MAGIC |-------------|----------------|
# MAGIC | **Clear name** (verb + noun) | LLM uses the name to decide whether to call the tool |
# MAGIC | **Typed parameters** | LLM generates arguments of the correct type |
# MAGIC | **Google-style docstring** | LLM reads this to understand purpose and parameters |
# MAGIC | **Simple return value** | String, float, or JSON-serialisable dict works best |
# MAGIC | **No side effects** | Tools should read/compute, not mutate state unexpectedly |
# MAGIC
# MAGIC ### Example: poorly described vs well described

# COMMAND ----------

# POOR: LLM would not know when to call this or what the parameters mean
def fn1(nmi, d1, d2):
    pass

# GOOD: LLM knows exactly when and how to call this
def calculate_peak_demand(nmi: str, start_date: str, end_date: str) -> str:
    """Calculate the peak 30-minute demand for a given meter (NMI) over a date range.

    Queries the NEM12 interval reads and returns the maximum half-hour demand
    recorded for the meter, along with the date and interval when it occurred.
    Use this when a user asks about peak demand, maximum load, or peak consumption
    for a specific meter or NMI.

    Args:
        nmi: National Meter Identifier — the unique connection point ID (e.g., '6001234567').
        start_date: Start of the analysis period in YYYY-MM-DD format (inclusive).
        end_date: End of the analysis period in YYYY-MM-DD format (inclusive).

    Returns:
        A JSON string with keys: nmi, peak_kwh, peak_date, peak_interval_number,
        and peak_time_approx (human-readable time of day).
    """
    pass  # implementation in the next section

print("Good docstring example defined — see next section for the full implementation.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Registering UC Functions
# MAGIC
# MAGIC We'll register three energy-domain functions as Unity Catalog SQL functions.
# MAGIC These can then be used by any AI agent, Genie Space, or notebook in the workspace.
# MAGIC
# MAGIC ### Function 1: `calculate_peak_demand`

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_peak_demand(
    nmi        STRING COMMENT 'National Meter Identifier — unique connection point ID',
    start_date STRING COMMENT 'Start of analysis period (YYYY-MM-DD, inclusive)',
    end_date   STRING COMMENT 'End of analysis period (YYYY-MM-DD, inclusive)'
)
RETURNS STRING
COMMENT 'Calculate the peak 30-minute demand for a meter over a date range.
Returns JSON with: nmi, peak_kwh, peak_date, peak_interval_number, peak_time_approx.
Use when a user asks about peak demand, maximum load, or peak consumption for a specific meter.'
LANGUAGE PYTHON
AS $$
import json

# Query the interval reads table
# In production, point this at your real interval reads table
try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("main.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.col("read_date").between(start_date, end_date))
        .filter(F.col("quality_flag").isin(["A", "S"]))  # Actual or Substituted
    )

    if df.count() == 0:
        return json.dumps({"error": f"No actual reads found for NMI {nmi} between {start_date} and {end_date}"})

    peak_row = df.orderBy(F.col("read_kwh").desc()).first()

    # Convert interval number to approximate time (each interval = 30 minutes, starting 00:00)
    start_minute = (peak_row["interval_number"] - 1) * 30
    peak_time = f"{start_minute // 60:02d}:{start_minute % 60:02d}"

    result = {
        "nmi": nmi,
        "peak_kwh": round(float(peak_row["read_kwh"]), 3),
        "peak_date": str(peak_row["read_date"]),
        "peak_interval_number": int(peak_row["interval_number"]),
        "peak_time_approx": peak_time,
        "date_range": f"{start_date} to {end_date}",
    }
    return json.dumps(result)

except Exception as e:
    return json.dumps({"error": str(e)})
$$
""")

print(f"Registered: {CATALOG}.{SCHEMA}.calculate_peak_demand")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Function 2: `get_meter_readings_summary`

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_meter_readings_summary(
    nmi        STRING COMMENT 'National Meter Identifier to retrieve readings for',
    read_date  STRING COMMENT 'The specific date to summarise readings for (YYYY-MM-DD)'
)
RETURNS STRING
COMMENT 'Get a summary of interval readings for a specific NMI on a given date.
Returns JSON with: total_kwh, actual_intervals, estimated_intervals, missing_intervals,
and pct_complete. Use when asked about a meter''s daily consumption, data completeness,
or data quality for a specific date.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("main.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.col("read_date") == read_date)
    )

    count = df.count()
    if count == 0:
        return json.dumps({"error": f"No reads found for NMI {nmi} on {read_date}"})

    summary = df.agg(
        F.sum("read_kwh").alias("total_kwh"),
        F.sum(F.when(F.col("quality_flag") == "A", 1).otherwise(0)).alias("actual"),
        F.sum(F.when(F.col("quality_flag") == "E", 1).otherwise(0)).alias("estimated"),
        F.sum(F.when(F.col("quality_flag") == "S", 1).otherwise(0)).alias("substituted"),
        F.count("*").alias("present_intervals"),
    ).first()

    missing = 48 - summary["present_intervals"]
    pct_complete = round(summary["present_intervals"] / 48 * 100, 1)

    result = {
        "nmi": nmi,
        "date": read_date,
        "total_kwh": round(float(summary["total_kwh"] or 0), 3),
        "actual_intervals": int(summary["actual"]),
        "estimated_intervals": int(summary["estimated"]),
        "substituted_intervals": int(summary["substituted"]),
        "missing_intervals": missing,
        "pct_complete": pct_complete,
        "data_quality": "GOOD" if summary["estimated"] / 48 < 0.05 else "REVIEW",
    }
    return json.dumps(result)

except Exception as e:
    return json.dumps({"error": str(e)})
$$
""")

print(f"Registered: {CATALOG}.{SCHEMA}.get_meter_readings_summary")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Function 3: `lookup_asset_status`

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.lookup_asset_status(
    asset_id STRING COMMENT 'The unique asset identifier to look up (e.g., TF-NSW-001)'
)
RETURNS STRING
COMMENT 'Look up the maintenance history and current status of a network asset.
Returns JSON with: asset_id, asset_type, last_maintenance_date, last_work_type,
total_work_orders_ytd, total_outage_minutes_ytd. Use when asked about an asset''s
condition, maintenance history, or outage record.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("main.workshop_lab.asset_maintenance")
        .filter(F.col("asset_id") == asset_id)
        .filter(F.year(F.col("maintenance_date")) == F.year(F.current_date()))
    )

    count = df.count()
    if count == 0:
        return json.dumps({"error": f"No maintenance records found for asset {asset_id} this year"})

    # Latest work order
    latest = df.orderBy(F.col("maintenance_date").desc()).first()

    # YTD aggregates
    agg = df.agg(
        F.count("*").alias("work_orders"),
        F.sum("outage_duration_minutes").alias("total_outage_mins"),
        F.sum("affected_nmis").alias("total_affected_nmis"),
        F.sum("cost_aud").alias("total_cost_aud"),
    ).first()

    result = {
        "asset_id": asset_id,
        "asset_type": latest["asset_type"],
        "last_maintenance_date": str(latest["maintenance_date"]),
        "last_work_type": latest["work_type"],
        "last_technician": latest["technician_id"],
        "total_work_orders_ytd": int(agg["work_orders"]),
        "total_outage_minutes_ytd": int(agg["total_outage_mins"] or 0),
        "total_affected_nmis_ytd": int(agg["total_affected_nmis"] or 0),
        "total_cost_aud_ytd": round(float(agg["total_cost_aud"] or 0), 2),
    }
    return json.dumps(result)

except Exception as e:
    return json.dumps({"error": str(e)})
$$
""")

print(f"Registered: {CATALOG}.{SCHEMA}.lookup_asset_status")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Testing UC Functions Directly
# MAGIC
# MAGIC Before wiring these to an AI agent, verify they work via SQL.
# MAGIC UC functions are callable with `SELECT` — this is how you test and debug them.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test calculate_peak_demand
# MAGIC -- Returns an error JSON since we have no data — that's expected behaviour
# MAGIC SELECT main.workshop_lab.calculate_peak_demand(
# MAGIC     '6001234567',
# MAGIC     '2024-07-01',
# MAGIC     '2024-07-07'
# MAGIC ) AS result

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test get_meter_readings_summary
# MAGIC SELECT main.workshop_lab.get_meter_readings_summary(
# MAGIC     '6001234567',
# MAGIC     '2024-07-01'
# MAGIC ) AS result

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test lookup_asset_status
# MAGIC SELECT main.workshop_lab.lookup_asset_status('TF-NSW-001') AS result

# COMMAND ----------

# MAGIC %md
# MAGIC ### Load sample data to make the functions return real results

# COMMAND ----------

import datetime, random, json
from pyspark.sql.types import *
from pyspark.sql import functions as F

random.seed(99)

# ---- interval_reads sample data ----
ir_rows = []
for day_offset in range(7):
    d = datetime.date(2024, 7, 1) + datetime.timedelta(days=day_offset)
    for interval in range(1, 49):
        hour = (interval - 1) / 2.0
        peak_factor = 2.5 if 7 <= hour <= 9 or 17 <= hour <= 20 else 1.0
        kwh = round(max(0.1, random.gauss(1.0 * peak_factor, 0.1)), 3)
        quality = "A" if random.random() > 0.03 else "E"
        ir_rows.append(("6001234567", d, interval, kwh, quality, datetime.datetime.now()))

ir_schema = StructType([
    StructField("nmi",             StringType(),    False),
    StructField("read_date",       DateType(),      False),
    StructField("interval_number", IntegerType(),   False),
    StructField("read_kwh",        DoubleType(),    True),
    StructField("quality_flag",    StringType(),    True),
    StructField("created_at",      TimestampType(), True),
])

(spark.createDataFrame(ir_rows, ir_schema)
     .write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.interval_reads"))

# ---- asset_maintenance sample data ----
am_rows = []
asset_types = ["TRANSFORMER", "SWITCH", "CABLE"]
work_types = ["PREVENTIVE", "CORRECTIVE", "EMERGENCY"]
for i in range(10):
    d = datetime.date(datetime.date.today().year, random.randint(1, 12), random.randint(1, 28))
    am_rows.append((
        "TF-NSW-001",
        random.choice(asset_types),
        f"WO-2024-{i:04d}",
        d,
        f"TECH-{random.randint(100, 999)}",
        random.choice(work_types),
        random.randint(0, 120),
        random.randint(0, 500),
        round(random.uniform(1000, 50000), 2),
        "Routine inspection completed",
    ))

am_schema = StructType([
    StructField("asset_id",                  StringType(),  False),
    StructField("asset_type",                StringType(),  True),
    StructField("work_order_id",             StringType(),  True),
    StructField("maintenance_date",          DateType(),    True),
    StructField("technician_id",             StringType(),  True),
    StructField("work_type",                 StringType(),  True),
    StructField("outage_duration_minutes",   IntegerType(), True),
    StructField("affected_nmis",             IntegerType(), True),
    StructField("cost_aud",                  DoubleType(),  True),
    StructField("notes",                     StringType(),  True),
])

(spark.createDataFrame(am_rows, am_schema)
     .write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.asset_maintenance"))

print("Sample data loaded.")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Re-test with real data
# MAGIC SELECT main.workshop_lab.calculate_peak_demand('6001234567', '2024-07-01', '2024-07-07') AS peak_result;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT main.workshop_lab.lookup_asset_status('TF-NSW-001') AS asset_result;

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Using UC Functions with an AI Agent
# MAGIC
# MAGIC Now we wire these tools to an LLM using `UCFunctionToolkit` from `databricks-langchain`.
# MAGIC The LLM will automatically decide which function to call based on user queries.

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks_langchain import UCFunctionToolkit, ChatDatabricks
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Databricks SDK uses the workspace URL and token from the environment automatically
# when running inside a Databricks notebook
w = WorkspaceClient()

# Load UC functions as LangChain tools
toolkit = UCFunctionToolkit(
    warehouse_id=None,  # None = use serverless SQL warehouse automatically
    tools_names=[
        f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
        f"{CATALOG}.{SCHEMA}.get_meter_readings_summary",
        f"{CATALOG}.{SCHEMA}.lookup_asset_status",
    ],
)
tools = toolkit.get_tools()

print(f"Loaded {len(tools)} tools:")
for t in tools:
    print(f"  - {t.name}: {t.description[:80]}...")

# COMMAND ----------

# Create the LLM — uses databricks-claude-sonnet-4-6 provisioned throughput (AU East in-region)
llm = ChatDatabricks(
    endpoint="databricks-claude-sonnet-4-6",  # Provisioned throughput endpoint
    temperature=0.0,                           # Deterministic for tool use
    max_tokens=2048,
)

# System prompt — explicitly describes the agent's role and available domain context
system_prompt = """You are an energy operations assistant for an Australian electricity network operator.
You have access to tools that query live operational data:
- calculate_peak_demand: find the peak consumption for a NEM meter
- get_meter_readings_summary: check data completeness and quality for a meter on a specific date
- lookup_asset_status: get maintenance history for a network asset

Always use the tools to answer questions — do not guess values.
Format numbers clearly: use kWh for energy, minutes for outage duration.
When results include a JSON error field, explain the issue in plain language."""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Build the agent
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,       # Shows tool calls — important for demos and debugging
    max_iterations=5,
)

print("Agent ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.1 — Run the agent with energy domain questions

# COMMAND ----------

# Question 1: Peak demand
response = agent_executor.invoke({
    "input": "What was the peak demand for meter 6001234567 during the first week of July 2024?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# Question 2: Data quality check
response = agent_executor.invoke({
    "input": "Can you check the data quality for meter 6001234567 on July 3rd 2024? I need to know if we have complete actual reads before submitting to AEMO."
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# Question 3: Asset status
response = agent_executor.invoke({
    "input": "What is the maintenance status of asset TF-NSW-001? How many outage minutes has it caused this year?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# Question 4: Multi-tool (observe the agent deciding to call multiple tools)
response = agent_executor.invoke({
    "input": "For our operations review: what was the peak demand on meter 6001234567 on July 1st 2024, and is there any maintenance history for asset TF-NSW-001 that might explain it?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Exercise: Write Your Own UC Function
# MAGIC
# MAGIC ### Exercise 6.1 — `calculate_demand_statistics`
# MAGIC
# MAGIC Register a UC function that:
# MAGIC - Takes `nmi` (string) and `month` (string, format `YYYY-MM`)
# MAGIC - Returns a JSON string with: `avg_daily_kwh`, `max_daily_kwh`, `min_daily_kwh`,
# MAGIC   `std_daily_kwh`, and `month_total_kwh`
# MAGIC - Handles the case where no data is found
# MAGIC
# MAGIC **Tip:** Use Genie Code → Generate to scaffold this. Prompt suggestion:
# MAGIC > *"Write a UC function called calculate_demand_statistics that takes nmi (string)
# MAGIC > and month (string, YYYY-MM format). Query main.workshop_lab.interval_reads,
# MAGIC > group by read_date to get daily totals, then return aggregate statistics as JSON.
# MAGIC > Match the style of the existing functions in this notebook."*

# COMMAND ----------

# TODO: Write and register calculate_demand_statistics as a UC function
# Then add it to the agent_executor tools list and test with a question like:
# "What were the demand statistics for meter 6001234567 in July 2024?"

# Step 1: Register the function
# spark.sql("""
# CREATE OR REPLACE FUNCTION main.workshop_lab.calculate_demand_statistics(...)
# ...
# """)

# Step 2: Reload toolkit with the new function
# toolkit_v2 = UCFunctionToolkit(
#     tools_names=[
#         ...,
#         "main.workshop_lab.calculate_demand_statistics",
#     ]
# )

# Step 3: Re-build the agent and test

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 6.2 — Grant access to a colleague
# MAGIC
# MAGIC UC functions have governance built in. Use this cell to grant EXECUTE permission.
# MAGIC This is how a team shares tools across agents.

# COMMAND ----------

# TODO: Replace with your colleague's email or a group name
GRANTEE = "your-colleague@yourdomain.com"  # TODO

spark.sql(f"""
GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.calculate_peak_demand TO `{GRANTEE}`
""")

spark.sql(f"""
GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.get_meter_readings_summary TO `{GRANTEE}`
""")

print(f"EXECUTE permissions granted to: {GRANTEE}")
print("Their agent can now call these tools — with full lineage tracking in Unity Catalog.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Key Concepts Review
# MAGIC
# MAGIC ### Why UC functions over plain Python?
# MAGIC
# MAGIC | Feature | Plain Python function | UC Function |
# MAGIC |---------|----------------------|-------------|
# MAGIC | Discoverable by AI agents | No | Yes — via Catalog |
# MAGIC | Governance & permissions | None | GRANT/REVOKE |
# MAGIC | Lineage tracking | No | Yes |
# MAGIC | Callable from SQL | No | Yes |
# MAGIC | Shareable across workspace | Requires import | Yes, by name |
# MAGIC | Audit trail | No | Yes — system tables |
# MAGIC
# MAGIC ### Docstring quality checklist
# MAGIC
# MAGIC - [ ] First line: one-sentence description of what it does (not how)
# MAGIC - [ ] `Args:` section with every parameter and its meaning in the domain
# MAGIC - [ ] `Returns:` section describing the output format
# MAGIC - [ ] At least one sentence on *when* an LLM should use this tool
# MAGIC - [ ] Domain terminology (NMI, NEM, kWh) — not generic variable names

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 03 Complete
# MAGIC
# MAGIC **Key takeaways:**
# MAGIC - UC functions are the standard way to give AI agents callable tools in Databricks
# MAGIC - Good docstrings are critical — the LLM reads them to decide *when* to call a tool
# MAGIC - `UCFunctionToolkit` from `databricks-langchain` bridges UC to LangChain agents
# MAGIC - UC functions carry governance (permissions, lineage, audit) that plain Python can't
# MAGIC - All execution happens within your AU East workspace
# MAGIC
# MAGIC **Next:** Lab 04 — MCP Integration →
