# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 01: Genie Code Fundamentals
# MAGIC **Workshop:** Genie Code for Developers — Australian Regulated Industries
# MAGIC **Estimated time:** 40–45 minutes
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What you'll learn
# MAGIC
# MAGIC | Topic | Time |
# MAGIC |-------|------|
# MAGIC | What Genie Code is | 5 min |
# MAGIC | Code generation from natural language | 10 min |
# MAGIC | Code explanation & documentation | 10 min |
# MAGIC | Code debugging with Genie Code | 10 min |
# MAGIC | Best practices & keyboard shortcuts | 5 min |
# MAGIC | Wrap-up exercises | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - Access to a Databricks workspace in **Australia East**
# MAGIC - Unity Catalog enabled
# MAGIC - Genie Code (Databricks Assistant) is on by default — no setup needed
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## About Genie Code
# MAGIC
# MAGIC **Genie Code** is the AI-powered coding assistant embedded directly in Databricks notebooks.
# MAGIC It runs **in-region for Australia East** using Azure AI Services (Chat mode) and
# MAGIC Anthropic Claude via Databricks Provisioned Throughput (Agent mode).
# MAGIC
# MAGIC ### Key capabilities
# MAGIC
# MAGIC | Feature | How to access |
# MAGIC |---------|---------------|
# MAGIC | **Generate** code from a description | Click `+` → "Generate with AI", or press `G` in command mode |
# MAGIC | **Fix** broken code | Click the **Fix** button above an error, or right-click a cell |
# MAGIC | **Explain** what code does | Right-click a cell → **Explain** |
# MAGIC | **Optimise** a cell | Right-click a cell → **Optimise** |
# MAGIC | **Document** a function | Right-click a cell → **Document** |
# MAGIC | **Chat panel** | Click the Assistant icon (top right), or `Ctrl+Shift+P` → "Open Assistant" |
# MAGIC
# MAGIC > **Regulatory note:** All Genie Code completions are processed by Azure AI Services
# MAGIC > hosted in Australia East. Your code and data **do not leave the region**.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup
# MAGIC
# MAGIC Run this cell to create a sample energy dataset we'll use throughout the lab.
# MAGIC This simulates National Electricity Market (NEM) interval meter data for the
# MAGIC Australian Capital Territory and New South Wales.

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    TimestampType, IntegerType, DateType
)
from pyspark.sql import functions as F
import datetime

spark = SparkSession.builder.getOrCreate()

# ---------------------------------------------------------------------------
# Raw NEM12 interval reads — 30-minute intervals, 2 meters, 7 days
# NMI = National Meter Identifier (unique per connection point in Australia)
# ---------------------------------------------------------------------------
schema = StructType([
    StructField("nmi",             StringType(),   False),
    StructField("interval_date",   DateType(),     False),
    StructField("interval_number", IntegerType(),  False),   # 1-48 per day
    StructField("read_kwh",        DoubleType(),   True),    # energy in kWh
    StructField("quality_flag",    StringType(),   True),    # A=Actual, E=Estimated
    StructField("meter_serial",    StringType(),   True),
    StructField("region",          StringType(),   True),    # NEM region: NSW1, VIC1, etc.
])

import random
random.seed(42)

rows = []
base = datetime.date(2024, 7, 1)
nmis = ["6001234567", "6009876543"]
regions = {"6001234567": "NSW1", "6009876543": "VIC1"}

for nmi in nmis:
    for day_offset in range(7):
        d = base + datetime.timedelta(days=day_offset)
        for interval in range(1, 49):
            # Simulate a realistic half-hour demand profile (kWh)
            hour = (interval - 1) / 2.0
            base_load = 0.8 if nmi == "6001234567" else 1.2
            peak_factor = 2.5 if 7 <= hour <= 9 or 17 <= hour <= 20 else 1.0
            noise = random.gauss(0, 0.05)
            kwh = max(0.0, round(base_load * peak_factor + noise, 3))
            quality = "A" if random.random() > 0.05 else "E"
            rows.append((
                nmi,
                d,
                interval,
                kwh,
                quality,
                f"METER-{nmi[-4:]}",
                regions[nmi],
            ))

df_meters = spark.createDataFrame(rows, schema=schema)
df_meters.createOrReplaceTempView("nem12_interval_reads")

print(f"Created nem12_interval_reads with {df_meters.count():,} rows")
df_meters.show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Code Generation
# MAGIC
# MAGIC **Exercise 2.1 — Generate code from a description**
# MAGIC
# MAGIC Instead of writing PySpark yourself, use Genie Code to generate it:
# MAGIC
# MAGIC 1. Click the **`+`** icon below this cell to add a new cell
# MAGIC 2. Select **"Generate with AI"** (or press `G` in command mode on the empty cell)
# MAGIC 3. Type the following prompt and press Enter:
# MAGIC
# MAGIC > *"Using the nem12_interval_reads temp view, calculate the total daily consumption in kWh for each NMI and region, ordered by nmi and interval_date ascending. Name the result df_daily."*
# MAGIC
# MAGIC **Expected output:** A PySpark DataFrame with columns: `nmi`, `region`, `interval_date`, `total_kwh`
# MAGIC
# MAGIC After Genie generates the code, **accept** it, then run the cell.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC > **Tip:** If the generated code references a non-existent column, refine your prompt:
# MAGIC > *"The view has columns: nmi, interval_date, interval_number, read_kwh, quality_flag, meter_serial, region. Recalculate..."*

# COMMAND ----------

# TODO: Use Genie Code → Generate to write this cell.
# Prompt suggestion:
# "Using the nem12_interval_reads temp view, calculate the total daily consumption
#  in kWh for each NMI and region, ordered by nmi and interval_date ascending.
#  Name the result df_daily."
#
# Expected columns: nmi, region, interval_date, total_kwh
# Expected rows: 14 (2 NMIs × 7 days)

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 2.2 — Generate a more complex aggregation**
# MAGIC
# MAGIC Use Genie Code to generate code that:
# MAGIC - Identifies the **peak 30-minute interval** (highest read_kwh) for each NMI per day
# MAGIC - Only includes rows where `quality_flag = 'A'` (Actual reads)
# MAGIC - Returns: `nmi`, `interval_date`, `peak_interval_number`, `peak_kwh`
# MAGIC
# MAGIC Try prompting with business context — Genie Code responds well to domain language:
# MAGIC
# MAGIC > *"For each NMI and day in nem12_interval_reads, find the 30-minute interval with the
# MAGIC > highest actual (quality_flag = 'A') energy read. Return: nmi, interval_date,
# MAGIC > peak_interval_number (the interval_number at peak), and peak_kwh."*

# COMMAND ----------

# TODO: Use Genie Code → Generate to write this cell.
# Find peak 30-minute interval per NMI per day (actual reads only).
# Expected columns: nmi, interval_date, peak_interval_number, peak_kwh

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Code Explanation
# MAGIC
# MAGIC The cell below contains a PySpark transformation that a colleague wrote.
# MAGIC It works, but it's not immediately obvious what it does.
# MAGIC
# MAGIC **Exercise 3.1 — Ask Genie Code to explain it**
# MAGIC
# MAGIC 1. Click on the cell below to select it
# MAGIC 2. Right-click → **Explain**  (or use the cell toolbar → ✨ → Explain)
# MAGIC 3. Read the explanation in the chat panel on the right
# MAGIC
# MAGIC **Discussion question:** Does the explanation match what you expected?
# MAGIC Does it correctly identify the business logic (demand profiling)?

# COMMAND ----------

# Colleague's code — what does this do?
df_profile = (
    df_meters
    .withColumn("hour_of_day", ((F.col("interval_number") - 1) / 2).cast("int"))
    .withColumn("period",
        F.when(F.col("hour_of_day").between(7, 9), F.lit("morning_peak"))
         .when(F.col("hour_of_day").between(17, 20), F.lit("evening_peak"))
         .when(F.col("hour_of_day").between(22, 23) | F.col("hour_of_day").between(0, 5), F.lit("off_peak"))
         .otherwise(F.lit("shoulder"))
    )
    .groupBy("nmi", "region", "period")
    .agg(
        F.avg("read_kwh").alias("avg_kwh"),
        F.max("read_kwh").alias("max_kwh"),
        F.stddev("read_kwh").alias("stddev_kwh"),
        F.count("*").alias("interval_count")
    )
    .orderBy("nmi", "period")
)

df_profile.show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 3.2 — Explain a SQL query**
# MAGIC
# MAGIC Run the cell below first, then use Genie Code → Explain on it.
# MAGIC Ask the chat panel: *"What is this query doing, and why might a NEM retailer use it?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- What does this query do in a NEM retail context?
# MAGIC SELECT
# MAGIC     nmi,
# MAGIC     interval_date,
# MAGIC     SUM(read_kwh)                                               AS daily_kwh,
# MAGIC     SUM(read_kwh) * 0.5                                         AS daily_kwh_check,
# MAGIC     COUNT(CASE WHEN quality_flag = 'E' THEN 1 END)              AS estimated_intervals,
# MAGIC     COUNT(*)                                                     AS total_intervals,
# MAGIC     ROUND(
# MAGIC         COUNT(CASE WHEN quality_flag = 'E' THEN 1 END) * 100.0
# MAGIC         / COUNT(*), 2
# MAGIC     )                                                            AS pct_estimated
# MAGIC FROM nem12_interval_reads
# MAGIC GROUP BY nmi, interval_date
# MAGIC HAVING pct_estimated > 5
# MAGIC ORDER BY pct_estimated DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Code Debugging
# MAGIC
# MAGIC The cells in this section contain **intentional bugs**.
# MAGIC Your task is to run each cell, observe the error, then use Genie Code to fix it.
# MAGIC
# MAGIC **How to use the Fix action:**
# MAGIC 1. Run the cell — it will produce an error
# MAGIC 2. Click the **Fix** button that appears in the error output
# MAGIC    (or right-click the cell → **Fix**)
# MAGIC 3. Review the suggested fix before accepting
# MAGIC 4. Accept and re-run
# MAGIC
# MAGIC > **Important:** Always **review** AI-generated fixes before accepting.
# MAGIC > Check: Does the logic match your intent? Are column names correct?

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 4.1 — Fix a column name error**

# COMMAND ----------

# BUG: This cell has a column name error. Run it, then use Genie Code → Fix.
df_bug1 = (
    df_meters
    .filter(F.col("quality_flg") == "A")          # <-- bug here
    .groupBy("nmi", "region")
    .agg(F.sum("read_kwh").alias("total_kwh"))
)
df_bug1.show()

# Expected output: 2 rows, one per NMI, total kWh for Actual reads only

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 4.2 — Fix a logic error**

# COMMAND ----------

# BUG: This cell runs without error but produces wrong results.
# It's supposed to flag meters that have MORE THAN 5% estimated readings.
# Use Genie Code → Explain first, then → Fix (or fix via chat).

df_bug2 = (
    df_meters
    .groupBy("nmi")
    .agg(
        F.count("*").alias("total_intervals"),
        F.sum(F.when(F.col("quality_flag") == "E", 1).otherwise(0)).alias("estimated_count")
    )
    .withColumn("pct_estimated", F.col("estimated_count") / F.col("total_intervals"))
    .filter(F.col("pct_estimated") < 0.05)   # <-- logic bug: should be > 0.05
)

df_bug2.show()
# With this bug, it returns meters BELOW the 5% threshold instead of above it.
# Ask Genie Code: "This filter is wrong — I want meters where >5% of intervals are estimated"

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 4.3 — Fix a schema error in a write operation**

# COMMAND ----------

# BUG: This cell tries to write the DataFrame but has a format error.
# Run it, then use Fix.

output_path = "/tmp/nem12_daily_output"

(
    df_meters
    .groupBy("nmi", "interval_date")
    .agg(F.sum("read_kwh").alias("total_kwh"))
    .write
    .format("dleta")          # <-- typo: "dleta" instead of "delta"
    .mode("overwrite")
    .save(output_path)
)

print(f"Written to {output_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Document and Optimise
# MAGIC
# MAGIC **Exercise 5.1 — Document a function**
# MAGIC
# MAGIC The function below works correctly but has no docstring.
# MAGIC
# MAGIC 1. Select the cell
# MAGIC 2. Right-click → **Document**
# MAGIC 3. Review the generated docstring — does it correctly describe the parameters
# MAGIC    and the NEM-specific business logic?
# MAGIC 4. Accept if correct

# COMMAND ----------

def calculate_load_factor(peak_kwh: float, total_kwh: float, periods: int = 48) -> float:
    if peak_kwh <= 0:
        return 0.0
    average_kwh = total_kwh / periods
    return round(average_kwh / peak_kwh, 4)


# Test the function
lf = calculate_load_factor(peak_kwh=2.8, total_kwh=68.4, periods=48)
print(f"Load factor: {lf}")
# Expected: ~0.5089 — a load factor near 0.5 means moderately efficient load usage

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 5.2 — Optimise a slow transformation**
# MAGIC
# MAGIC The cell below uses Python loops on a Spark DataFrame (an anti-pattern).
# MAGIC
# MAGIC 1. Run the cell and note it works but would be slow on real data
# MAGIC 2. Right-click → **Optimise**
# MAGIC 3. See if Genie Code suggests replacing the loop with native Spark functions
# MAGIC
# MAGIC > **Discussion:** The original code collects data to the driver. For 1 million rows of
# MAGIC > NEM12 data this would OOM. Genie Code should suggest a vectorised approach.

# COMMAND ----------

# SLOW: Uses Python loop over collected Spark rows — anti-pattern for large datasets
# Use Genie Code → Optimise to rewrite with native Spark operations

rows_collected = df_meters.filter(F.col("nmi") == "6001234567").collect()

flagged = []
for row in rows_collected:
    if row["read_kwh"] > 2.0:
        flagged.append({
            "nmi": row["nmi"],
            "interval_date": str(row["interval_date"]),
            "interval_number": row["interval_number"],
            "read_kwh": row["read_kwh"],
        })

print(f"High-consumption intervals: {len(flagged)}")
for f in flagged[:3]:
    print(f)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Best Practices & Shortcuts
# MAGIC
# MAGIC ### Writing effective prompts for Genie Code
# MAGIC
# MAGIC | Do | Don't |
# MAGIC |----|-------|
# MAGIC | Name the DataFrame / view you're working with | Say "write a query" without context |
# MAGIC | Specify exact column names | Assume Genie knows your schema |
# MAGIC | State the expected output shape | Use vague terms like "transform the data" |
# MAGIC | Include domain terms (NMI, NEM12, kWh) | Use generic variable names |
# MAGIC | Say what you want to *avoid* (e.g., "no UDFs") | Accept the first suggestion blindly |
# MAGIC
# MAGIC ### Keyboard shortcuts
# MAGIC
# MAGIC | Shortcut | Action |
# MAGIC |----------|--------|
# MAGIC | `G` (command mode) | Open Generate with AI for current cell |
# MAGIC | `Ctrl+Shift+P` | Command palette → search for AI actions |
# MAGIC | `Esc` then `G` | Same as above from edit mode |
# MAGIC | `Alt+Enter` | Run cell and move to next |
# MAGIC
# MAGIC ### Providing context in the chat panel
# MAGIC
# MAGIC When using the chat panel, you can drag cells into the chat or type `@cell` to reference
# MAGIC the current cell. You can also describe your **schema** in natural language:
# MAGIC
# MAGIC > *"I have a table with columns: nmi (string, NEM meter ID), interval_date (date),
# MAGIC > interval_number (int, 1–48 per day), read_kwh (double). Help me..."*

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Wrap-up Exercises
# MAGIC
# MAGIC Work through these independently. Use Genie Code for each one.
# MAGIC Do **not** write the code by hand — the goal is practising effective prompting.
# MAGIC
# MAGIC **Exercise 7.1** — Generate code to:
# MAGIC - Calculate the 7-day rolling average consumption per NMI
# MAGIC - Use a window function (hint: tell Genie Code "use a Spark window function ordered by interval_date")

# COMMAND ----------

# TODO: Use Genie Code to write a 7-day rolling average per NMI.
# Hint prompt: "Using df_meters grouped by nmi and interval_date to get daily totals,
#  calculate a 7-day rolling average of daily_kwh using a Spark window function
#  ordered by interval_date. Name the result df_rolling."

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 7.2** — Generate a function:
# MAGIC - `def flag_missing_intervals(df, nmi_col, date_col, interval_col):`
# MAGIC - Returns rows where `interval_number` jumps by more than 1 within an NMI+date group
# MAGIC   (i.e., missing 30-minute intervals — a data quality issue in NEM12 files)
# MAGIC
# MAGIC Use the chat panel for this one — it's a multi-step prompt.

# COMMAND ----------

# TODO: Use Genie Code (chat panel) to write flag_missing_intervals().
# Test it on df_meters — there should be no missing intervals in our sample data
# (all 48 intervals per day × 2 NMIs × 7 days are present).

# COMMAND ----------

# MAGIC %md
# MAGIC **Exercise 7.3 — Reflection**
# MAGIC
# MAGIC In the chat panel, ask:
# MAGIC
# MAGIC > *"I'm working with Australian NEM12 electricity meter data in Databricks.
# MAGIC > What are 3 common data quality issues I should watch for in interval reads,
# MAGIC > and how would I detect each one using PySpark?"*
# MAGIC
# MAGIC Discuss the response with the facilitator or a neighbour.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 01 Complete
# MAGIC
# MAGIC **Key takeaways:**
# MAGIC - Genie Code generates, explains, fixes, optimises, and documents code — all in-region for AU East
# MAGIC - Effective prompts name your DataFrame, specify columns, and include domain context
# MAGIC - Always review AI-generated code before accepting — especially fixes and writes
# MAGIC - The chat panel provides multi-turn context for complex problems
# MAGIC
# MAGIC **Next:** Lab 02 — Notebook AI Features & Chat Panel →
