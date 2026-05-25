# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 03 SOLUTION: Custom Instructions, Skills & UC Function Tools
# MAGIC **Reference solution — all exercises completed. Share with participants after the lab.**

# COMMAND ----------

%pip install databricks-langchain mlflow langchain langchain-community --quiet
dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog",      "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",       "workshop_lab",         "Schema name")
dbutils.widgets.text("pt_endpoint",  "au_east_llm_inregion", "PT endpoint name")

CATALOG     = dbutils.widgets.get("catalog")
SCHEMA      = dbutils.widgets.get("schema")
PT_ENDPOINT = dbutils.widgets.get("pt_endpoint")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"Catalog : {CATALOG}")
print(f"Schema  : {SCHEMA}")
print(f"Endpoint: {PT_ENDPOINT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1 — Custom Instructions: SOLUTION

# COMMAND ----------

# SOLUTION 1.1: Write personal instructions file
username = spark.sql("SELECT current_user()").collect()[0][0]
instructions_path = f"/Users/{username}/.assistant_instructions.md"

instructions = """# Energy Operations Domain Context

I work with Australian electricity network data at a NEM participant (National Electricity Market).
All my code targets Databricks on Azure Australia East. All output tables use Delta Lake format.

## Terminology I use — learn these before responding

| Term | Meaning |
|------|---------|
| NMI | National Metering Identifier — 10-character string, format: 61XXXXXXXXXX for VIC |
| NEM | National Electricity Market (eastern and southern Australia) |
| NEM12 | The file format for 30-minute interval meter data submissions to AEMO |
| AEMO | Australian Energy Market Operator — the market body |
| AER | Australian Energy Regulator — sets performance targets (SAIDI, SAIFI) |
| ESC | Essential Services Commission (Victoria-specific regulator) |
| SAIDI | System Average Interruption Duration Index — lower is better (mins/customer/year) |
| SAIFI | System Average Interruption Frequency Index — interruptions per customer per year |
| ICP | Industry Connection Point — the physical connection to the network |
| DRP | Distribution Rules Project — asset hierarchy concept |

## Data tables I work with

- `interval_reads`: 30-minute NEM12 interval data. Key columns: nmi, read_date, interval_number (1-48), read_kwh, quality_flag
- `outage_events`: SAIDI/SAIFI events. Key columns: event_id, asset_id, start_ts, duration_minutes, affected_customers, cause_category
- `energy_assets`: Network assets (transformers, substations, cables, poles). Key columns: asset_id, asset_type, region, installation_date, rated_kva
- `asset_maintenance`: SAP-style work orders. Key columns: asset_id, maintenance_date, work_type, technician_id, outage_duration_minutes, cost_aud

## Data quality flags (NEM12 standard)

| Flag | Meaning | Include in calculations? |
|------|---------|--------------------------|
| A | Actual reading — meter read directly | Yes |
| E | Estimated — interpolated by retailer | Yes, with a note |
| S | Substituted — replaced by network | Flag for review |
| N | Null / missing | Exclude |

## Calculation rules

- SAIDI formula: SUM(outage_duration_minutes * affected_customers) / total_customers
- SAIFI formula: SUM(interruption_events * affected_customers) / total_customers
- Daily consumption from NEM12: SUM(interval_kwh) — intervals are already 30-min values, NOT half-hourly rates
- Peak demand window: 07:00-09:00 and 17:00-20:00 AEST (morning and evening peaks)

## Coding preferences

- Always use Delta Lake format for output tables (`.format("delta")`)
- Use Australian date format DD/MM/YYYY in comments, documentation, and print statements
- Variable names: use snake_case, domain-specific (e.g., `nmi`, `saidi_minutes`, not `id`, `value`)
- Error handling: return structured JSON errors, never raise bare exceptions in UC functions
- Imports: put all imports at the top of functions (required inside UC LANGUAGE PYTHON blocks)

## Regulatory context

- AER sets five-year regulatory periods (currently 2024-2029 for most DNSPs)
- SAIDI targets vary by network and zone — always clarify which network before benchmarking
- Data submitted to AEMO must meet NEM12 format requirements (B2B Procedure: Meter Data Provision Procedures)
"""

dbutils.fs.put(instructions_path, instructions, overwrite=True)
print(f"Instructions written to: {instructions_path}")
print("\nNext step: restart Genie Code to pick up the new instructions.")

# COMMAND ----------

# SOLUTION 1.3: Write AGENTS.md for project-level context
notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
notebook_dir  = "/".join(notebook_path.split("/")[:-1])
agents_md_path = f"/Workspace{notebook_dir}/AGENTS.md"

agents_md_content = """# Energy Workshop — Project Context for Genie Code

This directory contains the Australian Energy AI Workshop labs.

## Project: Meter Data Analytics

We are building AI-assisted analytics for NEM12 interval meter data.

### Active tables (workshop_au.workshop_lab)

| Table | Description |
|-------|-------------|
| interval_reads | 30-min NEM12 interval data for workshop NMIs |
| asset_maintenance | YTD work orders for network assets |

### NMIs used in this workshop

| NMI | Description |
|-----|-------------|
| 6001234567 | Residential VIC, standard consumption profile |
| 6009999001 | Commercial NSW, large load, solar export enabled |

### Assets used in this workshop

| Asset ID | Type | Region |
|----------|------|--------|
| TF-NSW-001 | Zone substation transformer | NSW |
| CB-VIC-042 | 11kV circuit breaker | VIC |

### Common queries in this project

- Peak demand analysis: always filter quality_flag IN ('A', 'S') — exclude E and N
- SAIDI events: join outage_events on asset_id, aggregate duration_minutes * affected_customers
- Data completeness: 48 intervals = one complete day (30-min cadence)

### Do not modify these tables directly — use the workshop UC functions instead.
"""

import os
os.makedirs(f"/Workspace{notebook_dir}", exist_ok=True)
with open(agents_md_path, "w") as f:
    f.write(agents_md_content)

print(f"AGENTS.md written to: {agents_md_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2 — Skills: SOLUTION

# COMMAND ----------

# SOLUTION 2.1: Create energy-operations skill
username = spark.sql("SELECT current_user()").collect()[0][0]
skill_dir = f"/Users/{username}/.assistant/skills/energy-operations"
dbutils.fs.mkdirs(skill_dir)

skill_content = """---
name: energy-operations
description: Australian energy network operations — NEM12 interval data quality flags, SAIDI/SAIFI regulatory calculations, asset management, AER reporting standards, and common meter data patterns
---

# Energy Operations Knowledge Base

## NEM12 Quality Flags

| Flag | Meaning | Include in peak demand calc? | Include in billing? |
|------|---------|------------------------------|---------------------|
| A | Actual — reading taken directly from the meter | Yes | Yes |
| E | Estimated — interpolated by the retailer or network | Yes, with caution | Yes (if < 5% of intervals) |
| S | Substituted — replaced by the LNSP or retailer | Flag for review | Depends on reason code |
| N | Null / missing — no reading available | No — exclude | No — must be recovered |

## SAIDI Calculation

```python
saidi = (
    outage_events_df
    .filter("period_start >= start_date AND period_end <= end_date")
    .groupBy("network_id")
    .agg(
        (F.sum(F.col("duration_minutes") * F.col("affected_customers"))
         / F.first("total_customers")).alias("saidi_minutes")
    )
)
```

## Interval Data Calculations

```python
# Peak demand — highest 30-min interval during peak window
peak_demand = (
    interval_reads_df
    .filter(F.col("quality_flag").isin(["A", "S"]))
    .filter(
        ((F.col("interval_number") >= 15) & (F.col("interval_number") <= 18)) |
        ((F.col("interval_number") >= 35) & (F.col("interval_number") <= 40))
    )
    .groupBy("nmi", "read_date")
    .agg(F.max("read_kwh").alias("peak_half_hour_kwh"))
)
```

## NMI Format Reference

| State | Prefix | Example |
|-------|--------|---------|
| VIC | 61 | 6100123456 |
| NSW | 41 | 4100123456 |
| QLD | 31 | 3100123456 |
"""

dbutils.fs.put(f"{skill_dir}/SKILL.md", skill_content, overwrite=True)
print(f"Skill written to: {skill_dir}/SKILL.md")
print("Invoke with: @energy-operations")

# COMMAND ----------

# SOLUTION 2.2: Create nem12-format skill
nem12_skill_dir = f"/Users/{username}/.assistant/skills/nem12-format"
dbutils.fs.mkdirs(nem12_skill_dir)

nem12_skill_content = """---
name: nem12-format
description: NEM12 raw file format specification — record types 100/200/300/400/500/900, field positions, and how to parse or validate NEM12 files submitted to AEMO
---

# NEM12 File Format Reference

| Record | Purpose | Key fields |
|--------|---------|-----------|
| 100 | Header — one per file | Version (NEM12), DateTime, FromParticipant, ToParticipant |
| 200 | NMI data details — one per NMI | NMI, NMISuffix, RegisterID, UOM, IntervalLength |
| 300 | Interval data — one per day per NMI | IntervalDate (YYYYMMDD), then 48 interval values |
| 400 | Interval event — data quality info | StartInterval, EndInterval, QualityMethod, ReasonCode |
| 900 | End of file — one per file | (no additional fields) |

## Common Validation Rules

1. Record 100 must be first; record 900 must be last
2. Each NMI block must start with a 200 record before any 300 records
3. IntervalLength in record 200 must be 30 (NEM12 standard)
4. Energy values must be >= 0 (negative = solar export, requires special handling)
5. Date in record 300 must be within the declared submission period
"""

dbutils.fs.put(f"{nem12_skill_dir}/SKILL.md", nem12_skill_content, overwrite=True)
print(f"NEM12 format skill written to: {nem12_skill_dir}/SKILL.md")
print("Invoke with: @nem12-format")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3 — UC Functions as Tools: SOLUTION

# COMMAND ----------

# SOLUTION 3.2: Register calculate_peak_demand
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_peak_demand(
    nmi        STRING COMMENT 'National Meter Identifier — unique connection point ID (10 digits, e.g. 6001234567)',
    start_date STRING COMMENT 'Start of analysis period in YYYY-MM-DD format (inclusive)',
    end_date   STRING COMMENT 'End of analysis period in YYYY-MM-DD format (inclusive)'
)
RETURNS STRING
COMMENT 'Calculate the peak 30-minute demand (kWh) for a given NEM meter over a date range.
Queries the interval_reads table for actual (A) and substituted (S) quality reads only.
Returns JSON with: nmi, peak_kwh, peak_date, peak_interval_number, peak_time_approx, date_range.
Use this tool when a user asks about peak demand, maximum load, highest consumption interval,
or peak reading for a specific NMI or meter connection point.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("workshop_au.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.col("read_date").between(start_date, end_date))
        .filter(F.col("quality_flag").isin(["A", "S"]))
    )

    if df.count() == 0:
        return json.dumps({
            "error": f"No actual or substituted reads found for NMI {nmi} between {start_date} and {end_date}."
        })

    peak_row = df.orderBy(F.col("read_kwh").desc()).first()

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

# SOLUTION 3.3: Register get_meter_readings_summary
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_meter_readings_summary(
    nmi       STRING COMMENT 'National Meter Identifier to retrieve readings for',
    read_date STRING COMMENT 'The specific date to summarise in YYYY-MM-DD format'
)
RETURNS STRING
COMMENT 'Get a completeness and quality summary of interval readings for a NMI on a given date.
Returns JSON with: total_kwh, actual_intervals, estimated_intervals, substituted_intervals,
missing_intervals, pct_complete, and data_quality (GOOD or REVIEW).
Use this tool when asked about meter data completeness, data quality score, how many intervals
are missing, whether data is ready for AEMO submission, or daily consumption for a specific date.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("workshop_au.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.col("read_date") == read_date)
    )

    count = df.count()
    if count == 0:
        return json.dumps({"error": f"No reads found for NMI {nmi} on {read_date}."})

    summary = df.agg(
        F.sum("read_kwh").alias("total_kwh"),
        F.sum(F.when(F.col("quality_flag") == "A", 1).otherwise(0)).alias("actual"),
        F.sum(F.when(F.col("quality_flag") == "E", 1).otherwise(0)).alias("estimated"),
        F.sum(F.when(F.col("quality_flag") == "S", 1).otherwise(0)).alias("substituted"),
        F.count("*").alias("present_intervals"),
    ).first()

    missing   = 48 - int(summary["present_intervals"])
    pct_compl = round(summary["present_intervals"] / 48 * 100, 1)
    est_rate  = int(summary["estimated"]) / 48
    quality   = "GOOD" if est_rate < 0.05 else "REVIEW"

    result = {
        "nmi": nmi,
        "date": read_date,
        "total_kwh": round(float(summary["total_kwh"] or 0), 3),
        "actual_intervals": int(summary["actual"]),
        "estimated_intervals": int(summary["estimated"]),
        "substituted_intervals": int(summary["substituted"]),
        "missing_intervals": missing,
        "pct_complete": pct_compl,
        "data_quality": quality,
        "nerr_threshold_exceeded": est_rate >= 0.05,
    }
    return json.dumps(result)

except Exception as e:
    return json.dumps({"error": str(e)})
$$
""")

print(f"Registered: {CATALOG}.{SCHEMA}.get_meter_readings_summary")

# COMMAND ----------

# SOLUTION 3.4: Register lookup_asset_status
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.lookup_asset_status(
    asset_id STRING COMMENT 'The unique asset identifier to look up (e.g., TF-NSW-001, CB-VIC-042)'
)
RETURNS STRING
COMMENT 'Look up the year-to-date maintenance history and operational status of a network asset.
Returns JSON with: asset_id, asset_type, last_maintenance_date, last_work_type, last_technician,
total_work_orders_ytd, total_outage_minutes_ytd, total_affected_nmis_ytd, total_cost_aud_ytd.
Use this tool when asked about asset maintenance history, outage record, YTD cost,
or when investigating maintenance done on a specific transformer, circuit breaker, or substation.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("workshop_au.workshop_lab.asset_maintenance")
        .filter(F.col("asset_id") == asset_id)
        .filter(F.year(F.col("maintenance_date")) == F.year(F.current_date()))
    )

    count = df.count()
    if count == 0:
        return json.dumps({"error": f"No maintenance records found for asset {asset_id} in the current year."})

    latest = df.orderBy(F.col("maintenance_date").desc()).first()
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

# SOLUTION 3.5: Load sample data
import datetime, random, json
from pyspark.sql.types import *
from pyspark.sql import functions as F

random.seed(99)

ir_rows = []
for day_offset in range(7):
    d = datetime.date(2024, 7, 1) + datetime.timedelta(days=day_offset)
    for interval in range(1, 49):
        hour = (interval - 1) / 2.0
        peak_factor = 2.5 if (7 <= hour < 9) or (17 <= hour < 20) else 1.0
        kwh     = round(max(0.1, random.gauss(1.0 * peak_factor, 0.1)), 3)
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

am_rows = []
work_types = ["PREVENTIVE", "CORRECTIVE", "EMERGENCY"]
for i in range(10):
    d = datetime.date(datetime.date.today().year, random.randint(1, 5), random.randint(1, 28))
    am_rows.append((
        "TF-NSW-001", "TRANSFORMER", f"WO-2024-{i:04d}", d,
        f"TECH-{random.randint(100, 999)}", random.choice(work_types),
        random.randint(0, 120), random.randint(0, 500),
        round(random.uniform(1000, 50000), 2), "Routine inspection completed",
    ))

am_schema = StructType([
    StructField("asset_id",                StringType(),  False),
    StructField("asset_type",              StringType(),  True),
    StructField("work_order_id",           StringType(),  True),
    StructField("maintenance_date",        DateType(),    True),
    StructField("technician_id",           StringType(),  True),
    StructField("work_type",               StringType(),  True),
    StructField("outage_duration_minutes", IntegerType(), True),
    StructField("affected_nmis",           IntegerType(), True),
    StructField("cost_aud",                DoubleType(),  True),
    StructField("notes",                   StringType(),  True),
])

(spark.createDataFrame(am_rows, am_schema)
     .write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true")
     .saveAsTable(f"{CATALOG}.{SCHEMA}.asset_maintenance"))

print(f"interval_reads:    {len(ir_rows):>4} rows  (7 days x 48 intervals, NMI 6001234567)")
print(f"asset_maintenance: {len(am_rows):>4} rows  (YTD work orders for TF-NSW-001)")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- SOLUTION 3.6: Test calculate_peak_demand
# MAGIC SELECT workshop_au.workshop_lab.calculate_peak_demand(
# MAGIC     '6001234567', '2024-07-01', '2024-07-07'
# MAGIC ) AS peak_result

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.get_meter_readings_summary('6001234567', '2024-07-03') AS summary_result

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.lookup_asset_status('TF-NSW-001') AS asset_result

# COMMAND ----------

# SOLUTION 3.8: Wire UC functions to a LangChain agent
from databricks.sdk import WorkspaceClient
from databricks_langchain import UCFunctionToolkit, ChatDatabricks
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

w = WorkspaceClient()

toolkit = UCFunctionToolkit(
    warehouse_id=None,
    tools_names=[
        f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
        f"{CATALOG}.{SCHEMA}.get_meter_readings_summary",
        f"{CATALOG}.{SCHEMA}.lookup_asset_status",
    ],
)
tools = toolkit.get_tools()

print(f"Loaded {len(tools)} tools:")
for t in tools:
    print(f"  {t.name}")
    print(f"    └─ {t.description[:90]}...")

# COMMAND ----------

llm = ChatDatabricks(
    endpoint=PT_ENDPOINT,
    temperature=0.0,
    max_tokens=2048,
)

system_prompt = """You are an energy operations assistant for an Australian electricity network operator.
You have access to three tools that query live operational data in Unity Catalog.
Always use the tools to answer questions about specific meters or assets — do not guess values.
Format numbers clearly: use kWh for energy, minutes for outage duration, AUD for costs.
Use DD/MM/YYYY format when writing dates in your response."""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=6)

# Question 1: Peak demand
result = agent_executor.invoke({"input": "What was the peak demand for meter 6001234567 during the first week of July 2024?"})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 2: Data quality check
result = agent_executor.invoke({
    "input": "Check the data quality for meter 6001234567 on 3 July 2024. Is it ready for AEMO submission?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 3: Asset status
result = agent_executor.invoke({
    "input": "What is the current maintenance status of asset TF-NSW-001? How many outage minutes has it caused this year?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 4: Multi-tool compound question (watch for two Invoking: lines in the trace)
result = agent_executor.invoke({
    "input": "For our weekly operations report: what was the peak demand on meter 6001234567 "
             "during the week of 1-7 July 2024, and does the maintenance history for asset "
             "TF-NSW-001 show any events that might explain unusual consumption in that period?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercise 3.9 SOLUTION — `calculate_demand_statistics` UC Function

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_demand_statistics(
    nmi   STRING COMMENT 'National Meter Identifier to analyse',
    month STRING COMMENT 'Month to analyse in YYYY-MM format (e.g. 2024-07)'
)
RETURNS STRING
COMMENT 'Calculate aggregate demand statistics for a NEM meter over a calendar month.
Returns JSON with: nmi, month, avg_daily_kwh, max_daily_kwh, min_daily_kwh,
std_daily_kwh, days_with_data, and month_total_kwh. Use when asked about consumption statistics,
average usage, variability, or monthly totals for a specific meter.'
LANGUAGE PYTHON
AS $$
import json

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    year, mon = month.split('-')

    df = (
        spark.table("workshop_au.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.year(F.col("read_date")) == int(year))
        .filter(F.month(F.col("read_date")) == int(mon))
        .filter(F.col("quality_flag").isin(["A", "S"]))
    )

    if df.count() == 0:
        return json.dumps({"error": f"No actual reads for NMI {nmi} in {month}"})

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
# MAGIC -- Test calculate_demand_statistics
# MAGIC SELECT workshop_au.workshop_lab.calculate_demand_statistics('6001234567', '2024-07') AS stats_result

# COMMAND ----------

# SOLUTION: Full agent with all 4 tools (including the new statistics tool)
toolkit_v2 = UCFunctionToolkit(
    warehouse_id=None,
    tools_names=[
        f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
        f"{CATALOG}.{SCHEMA}.get_meter_readings_summary",
        f"{CATALOG}.{SCHEMA}.lookup_asset_status",
        f"{CATALOG}.{SCHEMA}.calculate_demand_statistics",
    ],
)
tools_v2 = toolkit_v2.get_tools()

print(f"Loaded {len(tools_v2)} tools:")
for t in tools_v2:
    print(f"  - {t.name}")

agent_v2 = create_tool_calling_agent(llm, tools_v2, prompt)
agent_executor_v2 = AgentExecutor(agent=agent_v2, tools=tools_v2, verbose=True, max_iterations=5)

response = agent_executor_v2.invoke({
    "input": "What were the demand statistics for meter 6001234567 in July 2024?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

print("=" * 60)
print("Lab 03 SOLUTION — Complete")
print("=" * 60)
print()
print("  [DONE] Section 1: Personal instructions + AGENTS.md created")
print("  [DONE] Section 2: @energy-operations and @nem12-format skills created")
print("  [DONE] Section 3: 3 UC functions registered + sample data loaded")
print("  [DONE] Section 3: LangChain agent with 3 tools — all 4 questions tested")
print("  [DONE] Exercise 3.9: calculate_demand_statistics registered + agent updated to 4 tools")
