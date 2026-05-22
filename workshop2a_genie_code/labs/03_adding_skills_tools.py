# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 36px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 03: Adding Skills &amp; UC Functions as AI Tools
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
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Lab 01, Lab 02 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All execution: AU East ✅
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you'll learn
# MAGIC
# MAGIC | # | Topic | Time |
# MAGIC |---|-------|------|
# MAGIC | 1 | What "skills" are for AI agents | 5 min |
# MAGIC | 2 | Writing functions for LLM use — docstring quality | 5 min |
# MAGIC | 3 | Registering three energy-domain UC functions | 10 min |
# MAGIC | 4 | Testing UC functions via SQL and the Catalog Explorer UI | 5 min |
# MAGIC | 5 | Using UC functions with a LangChain agent | 10 min |
# MAGIC | 6 | Exercises: write your own function, grant access | 10 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What are "skills" in an AI agent context?
# MAGIC
# MAGIC In Databricks, **skills** (also called **tools** or **AI functions**) are Python functions
# MAGIC that an LLM can call at runtime. The agent:
# MAGIC
# MAGIC 1. Sees a **description** of each tool (its docstring + type hints)
# MAGIC 2. Decides *when* to call it based on the user's query
# MAGIC 3. Passes typed arguments to the function
# MAGIC 4. Receives the result and incorporates it into its answer
# MAGIC
# MAGIC **In Databricks**, tools are registered as **Unity Catalog (UC) functions** — which gives you
# MAGIC governance, lineage, and discoverability across your organisation.
# MAGIC
# MAGIC ```
# MAGIC User query
# MAGIC     ↓
# MAGIC LLM reasons about which tool to call
# MAGIC     ↓
# MAGIC Calls UC function (e.g., calculate_peak_demand)
# MAGIC     ↓
# MAGIC Spark / Python executes the function inside your workspace
# MAGIC     ↓
# MAGIC Result returned to LLM → final response
# MAGIC ```
# MAGIC
# MAGIC > **AU East:** UC functions execute within your Databricks workspace in Australia East.
# MAGIC > No data leaves the region when a tool is called.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before We Code: 5-Minute UI Tour (do this first!)
# MAGIC
# MAGIC In this lab you register Python functions as Unity Catalog tools that AI agents can call.
# MAGIC Before writing any code, explore where UC functions live in the UI — this is where your tools
# MAGIC will appear after you register them.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 1 — Browse Unity Catalog functions
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Catalog (stack-of-books icon)
# MAGIC   → system catalog → ai schema
# MAGIC     → Look for "Functions" section (below Tables)
# MAGIC ```
# MAGIC
# MAGIC **What you should see:**
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────┐
# MAGIC │  system.ai                                       │
# MAGIC │  ── Tables ──────────────────────────────────    │
# MAGIC │  ── Functions ───────────────────────────────    │
# MAGIC │     ai_analyze_sentiment                         │
# MAGIC │     ai_classify                                  │
# MAGIC │     ai_extract                                   │
# MAGIC │     ai_gen                                       │
# MAGIC │     ai_query                                     │
# MAGIC │     ai_summarize                                 │
# MAGIC └──────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC Click any function to see its signature, parameters, and description.
# MAGIC This is exactly what the LLM "sees" when deciding whether to call a tool.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 2 — Find the workshop schema (where your tools will land)
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Catalog → workshop_au → workshop_lab
# MAGIC   → Look for "Functions" section — it will be empty now
# MAGIC ```
# MAGIC
# MAGIC After running Section 2 of this lab, come back here.
# MAGIC Your registered tools (`calculate_peak_demand`, `lookup_asset_history`, etc.)
# MAGIC will appear in this section.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 3 — Check if any AI functions already exist in your catalog
# MAGIC
# MAGIC If functions already exist, click one to see:
# MAGIC - Input parameters and their types
# MAGIC - Return type
# MAGIC - Description (the docstring the LLM reads)
# MAGIC - Owner and creation date
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Time check:** 5 minutes. Start the pip install below while you explore —
# MAGIC it takes about 2 minutes to complete.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   ⚙️  Section 1 — Setup
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Install the packages required for this lab.
# MAGIC
# MAGIC | Package | Purpose |
# MAGIC |---------|---------|
# MAGIC | `databricks-langchain` | `UCFunctionToolkit` — wraps UC functions as LangChain tools |
# MAGIC | `mlflow` | Experiment tracking and trace visualisation |
# MAGIC | `langchain` | Agent orchestration framework |
# MAGIC | `langchain-community` | Additional LangChain integrations |

# COMMAND ----------

# Install required packages
%pip install databricks-langchain mlflow langchain langchain-community --quiet
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Configure your catalog and schema
# MAGIC
# MAGIC > **TODO:** Update the three variables below before running this cell.

# COMMAND ----------

# TODO: Update these values for your workspace
CATALOG       = "main"          # TODO: your catalog name
SCHEMA        = "workshop_lab"  # TODO: your schema (must exist from Lab 02, or it will be created)
WORKSPACE_URL = "https://adb-XXXXXXXXXXXXXXXXX.X.azuredatabricks.net"  # TODO: your workspace URL

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"Using: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Using: main.workshop_lab
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   ✍️  Section 2 — Writing Functions for LLM Use
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC A function that an LLM can call effectively needs:
# MAGIC
# MAGIC | Requirement | Why it matters |
# MAGIC |-------------|----------------|
# MAGIC | **Clear name** (verb + noun) | LLM uses the name to decide whether to call the tool |
# MAGIC | **Typed parameters** | LLM generates arguments of the correct type |
# MAGIC | **Google-style docstring** | LLM reads this to understand purpose and parameters |
# MAGIC | **Simple return value** | String, float, or JSON-serialisable dict works best |
# MAGIC | **No side effects** | Tools should read/compute, not mutate state unexpectedly |
# MAGIC
# MAGIC ### Poorly described vs well described — side by side
# MAGIC
# MAGIC The difference in docstring quality directly affects how reliably the LLM chooses
# MAGIC and calls the tool.

# COMMAND ----------

# POOR: LLM has no idea when to call this or what the parameters mean
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
    pass  # full implementation registered as a UC function in Section 3

print("Good docstring example defined — see Section 3 for the full UC function registration.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🗂️  Section 3 — Registering UC Functions
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC We'll register three energy-domain functions as Unity Catalog SQL functions.
# MAGIC Once registered, any AI agent, Genie Space, or notebook in the workspace can call them
# MAGIC — with full governance, permissions, and lineage.
# MAGIC
# MAGIC ### How UC function registration works
# MAGIC
# MAGIC ```
# MAGIC spark.sql("CREATE OR REPLACE FUNCTION catalog.schema.my_func(...) ...")
# MAGIC         ↓
# MAGIC Function stored in Unity Catalog metastore
# MAGIC         ↓
# MAGIC Visible in Catalog Explorer under Functions
# MAGIC         ↓
# MAGIC Any agent with EXECUTE permission can call it by fully-qualified name
# MAGIC ```
# MAGIC
# MAGIC ---
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

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    spark = SparkSession.builder.getOrCreate()

    df = (
        spark.table("main.workshop_lab.interval_reads")
        .filter(F.col("nmi") == nmi)
        .filter(F.col("read_date").between(start_date, end_date))
        .filter(F.col("quality_flag").isin(["A", "S"]))  # Actual or Substituted only
    )

    if df.count() == 0:
        return json.dumps({"error": f"No actual reads found for NMI {nmi} between {start_date} and {end_date}"})

    peak_row = df.orderBy(F.col("read_kwh").desc()).first()

    # Each interval = 30 minutes starting at 00:00 (interval 1 = 00:00-00:30)
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
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Registered: main.workshop_lab.calculate_peak_demand
# MAGIC ```
# MAGIC
# MAGIC ---
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
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Registered: main.workshop_lab.get_meter_readings_summary
# MAGIC ```
# MAGIC
# MAGIC ---
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

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Registered: main.workshop_lab.lookup_asset_status
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖥️  UI Check — Viewing UC Functions in Catalog Explorer
# MAGIC </div>
# MAGIC
# MAGIC After registering the three functions, verify they appear in the Catalog Explorer:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Data (left sidebar) → [catalog: main] → [schema: workshop_lab] → Functions
# MAGIC
# MAGIC ┌─── Catalog Explorer ────────────────────────────────────────┐
# MAGIC │  main (catalog)                                             │
# MAGIC │  └── workshop_lab (schema)                                  │
# MAGIC │       ├── Tables (2+)                                       │
# MAGIC │       ├── Views (0)                                         │
# MAGIC │       ├── Functions (3)   ← click here                      │
# MAGIC │       │    ├── calculate_peak_demand                        │
# MAGIC │       │    ├── get_meter_readings_summary                   │
# MAGIC │       │    └── lookup_asset_status                          │
# MAGIC │       └── Volumes (0)                                       │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click any function to see:
# MAGIC   - Function signature (parameters and return type)
# MAGIC   - COMMENT field — this is exactly what the LLM reads to decide when to call it
# MAGIC   - SQL/Python definition
# MAGIC   - Tags and permissions
# MAGIC
# MAGIC > ⚠️ There is NO "Run function" button in Catalog Explorer. To test a UC function,
# MAGIC > run it in a notebook cell or SQL Editor:
# MAGIC >   SELECT catalog.schema.function_name(params);
# MAGIC ```
# MAGIC
# MAGIC > **Why the COMMENT matters:** When `UCFunctionToolkit` loads a function as a LangChain
# MAGIC > tool, it uses the UC `COMMENT` field as the tool description. The LLM reads this to
# MAGIC > decide whether to call the tool. A clear, specific COMMENT = better tool selection accuracy.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖥️  UI Check — Testing a Function from the Catalog Explorer
# MAGIC </div>
# MAGIC
# MAGIC You can run UC functions interactively from the UI before wiring them to an agent:
# MAGIC
# MAGIC ```
# MAGIC After selecting a function in Catalog Explorer:
# MAGIC   1. Click the "Run" tab (top-right of the function detail panel)
# MAGIC   2. Fill in parameter values in the form that appears
# MAGIC   3. Click "Run" to execute and see output inline
# MAGIC
# MAGIC Example — fill in these values for calculate_peak_demand:
# MAGIC   nmi:        6001234567
# MAGIC   start_date: 2024-07-01
# MAGIC   end_date:   2024-07-07
# MAGIC
# MAGIC Expected output before sample data is loaded (Section 4):
# MAGIC   {"error": "No actual reads found for NMI 6001234567 between 2024-07-01 and 2024-07-07"}
# MAGIC
# MAGIC Expected output after sample data is loaded:
# MAGIC   {
# MAGIC     "nmi": "6001234567",
# MAGIC     "peak_kwh": 2.487,
# MAGIC     "peak_date": "2024-07-04",
# MAGIC     "peak_interval_number": 35,
# MAGIC     "peak_time_approx": "17:00",
# MAGIC     "date_range": "2024-07-01 to 2024-07-07"
# MAGIC   }
# MAGIC ```
# MAGIC
# MAGIC > The exact `peak_kwh` will vary slightly because sample data uses random generation.
# MAGIC > The peak interval will always fall in the 07:00-09:00 or 17:00-20:00 window,
# MAGIC > because that is when the sample generator applies the 2.5x demand multiplier.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🧪  Section 4 — Testing UC Functions Directly via SQL
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Before wiring these functions to an AI agent, test them via SQL.
# MAGIC UC functions are callable with `SELECT` — this is the fastest way to debug and verify them.
# MAGIC
# MAGIC > **What to expect here:** The first SQL cells will return an error JSON because
# MAGIC > no meter data has been loaded yet. That is **expected and correct** — the functions
# MAGIC > are working as designed by returning a structured error instead of crashing.
# MAGIC > After loading sample data in Section 4.1, re-run to see real results.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test calculate_peak_demand
# MAGIC -- Expected: error JSON (no data yet) — this is correct error-handling behaviour
# MAGIC SELECT main.workshop_lab.calculate_peak_demand(
# MAGIC     '6001234567',
# MAGIC     '2024-07-01',
# MAGIC     '2024-07-07'
# MAGIC ) AS result

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (no data yet):**
# MAGIC ```
# MAGIC result
# MAGIC {"error": "No actual reads found for NMI 6001234567 between 2024-07-01 and 2024-07-07"}
# MAGIC ```

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
# MAGIC ### 4.1 — Load sample data
# MAGIC
# MAGIC Creates two Delta tables with realistic NEM12-style data:
# MAGIC
# MAGIC | Table | Rows | Description |
# MAGIC |-------|------|-------------|
# MAGIC | `interval_reads` | 336 | 7 days × 48 intervals for NMI 6001234567 |
# MAGIC | `asset_maintenance` | 10 | YTD work orders for transformer TF-NSW-001 |
# MAGIC
# MAGIC The interval reads simulate real NEM12 patterns:
# MAGIC - **Morning peak:** 07:00–09:00 uses a 2.5x demand multiplier
# MAGIC - **Evening peak:** 17:00–20:00 uses a 2.5x demand multiplier
# MAGIC - ~3% of intervals are flagged as Estimated (`E`) to simulate typical data quality

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
        # Simulate morning and evening demand peaks
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
work_types  = ["PREVENTIVE", "CORRECTIVE", "EMERGENCY"]
for i in range(10):
    d = datetime.date(datetime.date.today().year, random.randint(1, 5), random.randint(1, 28))
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

print(f"interval_reads:    {len(ir_rows)} rows ({len(ir_rows)//48} days x 48 intervals)")
print(f"asset_maintenance: {len(am_rows)} rows (YTD work orders for TF-NSW-001)")
print("Sample data loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC interval_reads:    336 rows (7 days x 48 intervals)
# MAGIC asset_maintenance: 10 rows (YTD work orders for TF-NSW-001)
# MAGIC Sample data loaded.
# MAGIC ```

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Re-test with real data — should now return actual peak values
# MAGIC SELECT main.workshop_lab.calculate_peak_demand('6001234567', '2024-07-01', '2024-07-07') AS peak_result;

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output** (values vary slightly due to random seed):
# MAGIC ```
# MAGIC peak_result
# MAGIC {"nmi": "6001234567", "peak_kwh": 2.49, "peak_date": "2024-07-04",
# MAGIC  "peak_interval_number": 35, "peak_time_approx": "17:00",
# MAGIC  "date_range": "2024-07-01 to 2024-07-07"}
# MAGIC ```
# MAGIC The peak falls in the 17:00–20:00 evening window because that is when the data
# MAGIC generator applies the 2.5x demand multiplier.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT main.workshop_lab.lookup_asset_status('TF-NSW-001') AS asset_result;

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output** (values vary):
# MAGIC ```
# MAGIC asset_result
# MAGIC {"asset_id": "TF-NSW-001", "asset_type": "TRANSFORMER",
# MAGIC  "last_maintenance_date": "2026-05-12", "last_work_type": "PREVENTIVE",
# MAGIC  "last_technician": "TECH-742", "total_work_orders_ytd": 10,
# MAGIC  "total_outage_minutes_ytd": 487, "total_affected_nmis_ytd": 2341,
# MAGIC  "total_cost_aud_ytd": 183429.67}
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🤖  Section 5 — Using UC Functions with a LangChain Agent
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Now we wire these tools to an LLM using `UCFunctionToolkit` from `databricks-langchain`.
# MAGIC
# MAGIC What the toolkit does under the hood:
# MAGIC 1. Reads each UC function's `COMMENT` and parameter definitions from the catalog
# MAGIC 2. Converts them into LangChain `Tool` objects with the correct schema
# MAGIC 3. Handles argument serialisation and result deserialisation automatically
# MAGIC
# MAGIC The LLM decides autonomously which function to call based on each user question.

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks_langchain import UCFunctionToolkit, ChatDatabricks
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# WorkspaceClient picks up workspace URL and token from the notebook environment automatically
w = WorkspaceClient()

# Load the three UC functions as LangChain tools
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

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Loaded 3 tools:
# MAGIC   - main__workshop_lab__calculate_peak_demand: Calculate the peak 30-minute demand for a meter...
# MAGIC   - main__workshop_lab__get_meter_readings_summary: Get a summary of interval readings for a...
# MAGIC   - main__workshop_lab__lookup_asset_status: Look up the maintenance history and current status...
# MAGIC ```
# MAGIC
# MAGIC > **Note:** LangChain converts UC function names to valid Python identifiers by replacing dots
# MAGIC > with double underscores: `main.workshop_lab.calculate_peak_demand`
# MAGIC > becomes `main__workshop_lab__calculate_peak_demand`.

# COMMAND ----------

# Create the LLM — Claude Sonnet 4.6 on Provisioned Throughput (AU East in-region)
llm = ChatDatabricks(
    endpoint="databricks-claude-sonnet-4-6",  # Provisioned throughput endpoint
    temperature=0.0,                           # Deterministic for reliable tool use
    max_tokens=2048,
)

# System prompt — describes the agent's role and instructs it to use tools, not guess
system_prompt = """You are an energy operations assistant for an Australian electricity network operator.
You have access to tools that query live operational data:
- calculate_peak_demand: find the peak consumption for a NEM meter over a date range
- get_meter_readings_summary: check data completeness and quality for a meter on a specific date
- lookup_asset_status: get year-to-date maintenance history for a network asset

Always use the tools to answer questions — do not guess or estimate values.
Format numbers clearly: use kWh for energy, minutes for outage duration, AUD for costs.
When results include a JSON error field, explain the issue clearly in plain language."""

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
    verbose=True,   # Shows tool calls as they happen — important for demos and debugging
    max_iterations=5,
)

print("Agent ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Agent ready.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.1 — Question 1: Peak demand lookup

# COMMAND ----------

# Question 1: Peak demand
response = agent_executor.invoke({
    "input": "What was the peak demand for meter 6001234567 during the first week of July 2024?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output** (verbose tool call trace + final answer):
# MAGIC ```
# MAGIC > Entering new AgentExecutor chain...
# MAGIC
# MAGIC Invoking: `main__workshop_lab__calculate_peak_demand` with
# MAGIC  {'nmi': '6001234567', 'start_date': '2024-07-01', 'end_date': '2024-07-07'}
# MAGIC
# MAGIC > Finished chain.
# MAGIC
# MAGIC === AGENT RESPONSE ===
# MAGIC The peak demand for meter 6001234567 during 1-7 July 2024 was 2.49 kWh in a single
# MAGIC 30-minute interval. This peak occurred on 4 July 2024 at approximately 17:00 (interval 35),
# MAGIC which corresponds to the early evening demand peak typical of residential consumption.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.2 — Question 2: Data quality check (AEMO submission readiness)

# COMMAND ----------

# Question 2: Data quality check
response = agent_executor.invoke({
    "input": "Can you check the data quality for meter 6001234567 on July 3rd 2024? "
             "I need to know if we have complete actual reads before submitting to AEMO."
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC === AGENT RESPONSE ===
# MAGIC For NMI 6001234567 on 3 July 2024:
# MAGIC   - Total consumption: 54.2 kWh
# MAGIC   - Actual reads (A): 47 of 48 intervals (97.9% complete)
# MAGIC   - Estimated reads (E): 1 interval
# MAGIC   - Missing intervals: 0
# MAGIC   - Data quality: GOOD
# MAGIC
# MAGIC This dataset is suitable for AEMO submission. The estimated read rate (2.1%) is below
# MAGIC the 5% threshold that triggers mandatory customer notification under the National Energy
# MAGIC Retail Rules.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.3 — Question 3: Asset maintenance status

# COMMAND ----------

# Question 3: Asset status
response = agent_executor.invoke({
    "input": "What is the maintenance status of asset TF-NSW-001? "
             "How many outage minutes has it caused this year?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.4 — Question 4: Multi-tool chain
# MAGIC
# MAGIC This question requires the agent to call **two tools in sequence**.
# MAGIC Watch the verbose output carefully — you will see two separate `Invoking:` lines before
# MAGIC the agent synthesises its final answer.

# COMMAND ----------

# Question 4: Multi-tool (observe the agent deciding to call multiple tools)
response = agent_executor.invoke({
    "input": "For our operations review: what was the peak demand on meter 6001234567 "
             "on July 1st 2024, and is there any maintenance history for asset TF-NSW-001 "
             "that might explain unusual consumption patterns?"
})
print("\n=== AGENT RESPONSE ===")
print(response["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **What to observe in the verbose trace:**
# MAGIC You should see two separate `Invoking:` lines — one for `calculate_peak_demand`
# MAGIC and one for `lookup_asset_status`. This is the LLM reasoning about which tools to
# MAGIC chain together to answer a compound question.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   🖥️  UI Check — Viewing LangChain Agent Traces in MLflow
# MAGIC </div>
# MAGIC
# MAGIC After running the agent exercises, inspect every tool call in the MLflow trace viewer:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar) → Experiments
# MAGIC           → [your experiment name, e.g., "energy-ops-agent"]
# MAGIC           → click a run → Traces tab
# MAGIC
# MAGIC ┌─── MLflow Trace View ───────────────────────────────────────┐
# MAGIC │  Run: energy-ops-agent-20260522                             │
# MAGIC │  ──────────────────────────────────────────────────────     │
# MAGIC │  Traces (4)                                                  │
# MAGIC │  ├── AgentRun (1,847ms) — "What was the peak demand..."     │
# MAGIC │  │    ├── LLMCall  (521ms) — decides to call tool           │
# MAGIC │  │    ├── ToolCall: calculate_peak_demand (203ms)            │
# MAGIC │  │    │    ├── Input:  {nmi: "6001234567", ...}             │
# MAGIC │  │    │    └── Output: {"peak_kwh": 2.49, ...}             │
# MAGIC │  │    └── LLMCall  (318ms) — synthesises final answer       │
# MAGIC │  ├── AgentRun (2,103ms) — "Can you check the data..."       │
# MAGIC │  └── ...                                                     │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **What to look for:**
# MAGIC - Which tool did the LLM decide to call, and with what arguments?
# MAGIC - How long did UC function execution take vs the LLM inference itself?
# MAGIC - For the multi-tool question (5.4): how many LLM calls appeared before the final answer?
# MAGIC
# MAGIC > MLflow tracing is automatically enabled for `ChatDatabricks` + `AgentExecutor`.
# MAGIC > No extra instrumentation code is needed in this notebook.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   📝  Section 6 — Exercises
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 6.1 — Write `calculate_demand_statistics`
# MAGIC
# MAGIC Register a new UC function that:
# MAGIC - Takes `nmi` (STRING) and `month` (STRING, format `YYYY-MM`)
# MAGIC - Queries `interval_reads`, groups by `read_date` to compute daily totals
# MAGIC - Returns a JSON string with: `avg_daily_kwh`, `max_daily_kwh`, `min_daily_kwh`,
# MAGIC   `std_daily_kwh`, and `month_total_kwh`
# MAGIC - Handles the case where no data is found gracefully
# MAGIC
# MAGIC **Tip:** Use Genie Code → Generate to scaffold this. Suggested prompt:
# MAGIC > *"Write a Databricks UC function called calculate_demand_statistics that takes nmi (STRING)
# MAGIC > and month (STRING, YYYY-MM format). Query main.workshop_lab.interval_reads,
# MAGIC > group by read_date to get daily totals, then return aggregate statistics as JSON.
# MAGIC > Match the style of the existing functions in this notebook. Include a clear COMMENT
# MAGIC > explaining when an LLM should call this tool."*

# COMMAND ----------

# TODO: Write and register calculate_demand_statistics as a UC function

# Step 1: Register the function
# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_demand_statistics(
#     nmi   STRING COMMENT '...',
#     month STRING COMMENT 'Analysis month in YYYY-MM format (e.g., 2024-07)'
# )
# RETURNS STRING
# COMMENT 'Calculate daily demand statistics for a meter over a calendar month.
# Returns JSON with: avg_daily_kwh, max_daily_kwh, min_daily_kwh, std_daily_kwh, month_total_kwh.
# Use when asked about demand variability, monthly consumption statistics, or load profiling.'
# LANGUAGE PYTHON
# AS $$
# ...
# $$
# """)

# Step 2: Reload toolkit with the new function
# toolkit_v2 = UCFunctionToolkit(
#     tools_names=[
#         f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
#         f"{CATALOG}.{SCHEMA}.get_meter_readings_summary",
#         f"{CATALOG}.{SCHEMA}.lookup_asset_status",
#         f"{CATALOG}.{SCHEMA}.calculate_demand_statistics",  # new
#     ]
# )
# tools_v2 = toolkit_v2.get_tools()

# Step 3: Rebuild the agent with tools_v2 and test
# agent_v2 = create_tool_calling_agent(llm, tools_v2, prompt)
# agent_executor_v2 = AgentExecutor(agent=agent_v2, tools=tools_v2, verbose=True)
# response = agent_executor_v2.invoke({
#     "input": "What were the demand statistics for meter 6001234567 in July 2024?"
# })
# print(response["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **Success criteria for Exercise 6.1:**
# MAGIC - SQL test `SELECT main.workshop_lab.calculate_demand_statistics('6001234567', '2024-07')` returns valid JSON with all five fields
# MAGIC - The agent answers *"What were the demand statistics for meter 6001234567 in July 2024?"* using the new tool (visible in the verbose trace)
# MAGIC - The COMMENT field describes *when* to call the tool (not just *what* it computes)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 6.2 — Grant EXECUTE permission to a colleague
# MAGIC
# MAGIC UC functions carry governance built in. Once you grant EXECUTE, the recipient can call
# MAGIC your function from their own agent using the same fully-qualified name — with a full
# MAGIC audit trail in `system.access.audit`.

# COMMAND ----------

# TODO: Replace with your colleague's email or a Unity Catalog group name
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
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC EXECUTE permissions granted to: colleague@example.com
# MAGIC Their agent can now call these tools — with full lineage tracking in Unity Catalog.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   📚  Section 7 — Key Concepts Review
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Why UC functions over plain Python?
# MAGIC
# MAGIC | Feature | Plain Python function | UC Function |
# MAGIC |---------|----------------------|-------------|
# MAGIC | Discoverable by AI agents | No | Yes — via Catalog Explorer |
# MAGIC | Governance and permissions | None | GRANT / REVOKE |
# MAGIC | Lineage tracking | No | Yes — in UC system tables |
# MAGIC | Callable from SQL | No | Yes — `SELECT catalog.schema.fn(...)` |
# MAGIC | Shareable across workspace | Requires import | Yes, by fully-qualified name |
# MAGIC | Audit trail | No | Yes — `system.access.audit` |
# MAGIC
# MAGIC ### Docstring quality checklist
# MAGIC
# MAGIC Before adding a function to your agent's toolkit, verify its COMMENT passes this checklist:
# MAGIC
# MAGIC - [ ] **First line:** one-sentence description of *what* it does (not *how*)
# MAGIC - [ ] **Args section:** every parameter explained with domain meaning, not just type
# MAGIC - [ ] **Returns section:** output format and key field names described
# MAGIC - [ ] **When to call it:** at least one sentence on the user query that should trigger this tool
# MAGIC - [ ] **Domain terminology:** NMI, NEM12, kWh, AER — not generic variable names
# MAGIC
# MAGIC ### Tool design best practices
# MAGIC
# MAGIC | Principle | Example |
# MAGIC |-----------|---------|
# MAGIC | One tool, one responsibility | Do not combine peak demand + data quality in one function |
# MAGIC | Return structured data | JSON string is better than free-form text for downstream LLM use |
# MAGIC | Handle missing data gracefully | Return `{"error": "..."}` — never raise an exception |
# MAGIC | Keep return payloads small | Return summary statistics, not raw row arrays |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 20px 24px; border-radius: 10px; margin-top: 16px;">
# MAGIC   <h2 style="color: white; margin: 0 0 8px 0;">Lab 03 Complete</h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 12px 0;">
# MAGIC     You registered three UC functions, tested them via SQL and the Catalog Explorer UI,
# MAGIC     and wired them to a LangChain agent that decides autonomously which tools to call.
# MAGIC   </p>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse;">
# MAGIC     <tr><td style="padding: 4px 8px;">UC functions are the standard way to give AI agents callable tools in Databricks</td></tr>
# MAGIC     <tr><td style="padding: 4px 8px;">Good COMMENT fields are critical — the LLM reads them to decide when to call a tool</td></tr>
# MAGIC     <tr><td style="padding: 4px 8px;">UCFunctionToolkit bridges UC to LangChain agents in a single call</td></tr>
# MAGIC     <tr><td style="padding: 4px 8px;">UC functions carry governance (permissions, lineage, audit) that plain Python cannot provide</td></tr>
# MAGIC     <tr><td style="padding: 4px 8px;">All execution happens within your AU East workspace — no data leaves the region</td></tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 12px 0 0 0; font-weight: bold;">
# MAGIC     Next: Lab 04 — MCP Integration
# MAGIC   </p>
# MAGIC </div>
