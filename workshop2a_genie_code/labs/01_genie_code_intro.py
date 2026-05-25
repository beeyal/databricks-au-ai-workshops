# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">✨ Lab 01: Genie Code Fundamentals</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 2a: Developer Track · Australian Regulated Industries</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | 👤 **Role** | Developer / Data Engineer / Data Scientist |
# MAGIC | ✅ **By the end** | Generate, fix, explain, document, and optimise code using Genie Code |
# MAGIC
# MAGIC ### What you'll learn
# MAGIC
# MAGIC | Topic |
# MAGIC |-------|
# MAGIC | Finding Genie Code in the notebook UI |
# MAGIC | Code generation from natural language |
# MAGIC | Code explanation and documentation |
# MAGIC | Debugging with Fix and Diagnose Error |
# MAGIC | Optimise and best practices |
# MAGIC | Wrap-up exercises |
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Access to a Databricks workspace in **Australia East**, Unity Catalog enabled
# MAGIC - Genie Code is on by default — no setup needed
# MAGIC
# MAGIC > 🔒 **Regulatory note:** All Genie Code completions run on Azure AI Services (Chat) and Anthropic Claude on Databricks (Agent) — both **in-region for Australia East**. Your code does not leave the region.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Part 0: Finding Genie Code in the Notebook UI
# MAGIC
# MAGIC There are three ways to access Genie Code — you need all three.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Access methods ────────────────────────────────────────┐
# MAGIC │  1. Sparkle icon in workspace top toolbar (top-right)     │
# MAGIC │     → opens / closes the Genie Code panel                 │
# MAGIC │                                                           │
# MAGIC │  2. Cmd+I (Mac) / Ctrl+I (Windows)                       │
# MAGIC │     → opens Genie Code inline within that specific cell   │
# MAGIC │                                                           │
# MAGIC │  3. Hover between two cells → click [+ Genie Code]        │
# MAGIC │     → Genie generates a brand-new cell from your prompt   │
# MAGIC └───────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Navigate:** workspace top toolbar → ✨ sparkle icon (top-right of page)
# MAGIC **You should see:** the Genie Code panel slide open on the right with a conversation thread in the centre, text input at the bottom, and a Chat/Agent toggle at the bottom-left.
# MAGIC
# MAGIC **Try it now (no code required):**
# MAGIC 1. Open the panel with the sparkle icon
# MAGIC 2. Confirm you see the Chat/Agent toggle at the **bottom** of the panel
# MAGIC 3. Hover over the code cell below → press **Cmd+I** (Mac) / **Ctrl+I** (Windows) → observe the inline prompt that opens inside the cell
# MAGIC 4. Press Esc to close, then hover between two cells to see the **+ Genie Code** button
# MAGIC
# MAGIC | Keyboard shortcut | Mac | Windows |
# MAGIC |---|---|---|
# MAGIC | Open Genie Code inline in cell | Cmd+I | Ctrl+I |
# MAGIC | Accept suggestion | Tab | Tab |
# MAGIC | Run cell | Cmd+Enter | Ctrl+Enter |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup
# MAGIC
# MAGIC Run this cell to create a sample NEM12 interval meter dataset used throughout the lab.
# MAGIC NEM12 is the Australian standard format for 30-minute interval meter reads, identified by NMI (National Meter Identifier). Quality flags: `A` = Actual, `E` = Estimated.

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    TimestampType, IntegerType, DateType
)
from pyspark.sql import functions as F
import datetime

spark = SparkSession.builder.getOrCreate()

schema = StructType([
    StructField("nmi",             StringType(),   False),
    StructField("interval_date",   DateType(),     False),
    StructField("interval_number", IntegerType(),  False),   # 1-48 per day
    StructField("read_kwh",        DoubleType(),   True),
    StructField("quality_flag",    StringType(),   True),    # A=Actual, E=Estimated
    StructField("meter_serial",    StringType(),   True),
    StructField("region",          StringType(),   True),
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
            hour = (interval - 1) / 2.0
            base_load = 0.8 if nmi == "6001234567" else 1.2
            peak_factor = 2.5 if 7 <= hour <= 9 or 17 <= hour <= 20 else 1.0
            noise = random.gauss(0, 0.05)
            kwh = max(0.0, round(base_load * peak_factor + noise, 3))
            quality = "A" if random.random() > 0.05 else "E"
            rows.append((
                nmi, d, interval, kwh, quality,
                f"METER-{nmi[-4:]}", regions[nmi],
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
# MAGIC Genie Code writes PySpark and SQL from a plain-English description. Specific prompts — naming your DataFrame, listing columns, describing the output shape — produce better results.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.1 — Generate a daily aggregation
# MAGIC
# MAGIC **Navigate:** hover between cells → click **+ Genie Code** (or press Cmd+I / Ctrl+I in the empty cell below)
# MAGIC **You should see:** an inline prompt field open inside the cell.
# MAGIC
# MAGIC Type this prompt exactly, then press Enter:
# MAGIC
# MAGIC > *"Using the nem12_interval_reads temp view, calculate the total daily consumption in kWh for each NMI and region, ordered by nmi and interval_date ascending. Name the result df_daily."*
# MAGIC
# MAGIC Click **Accept**, then run the cell. Expected: 14 rows (2 NMIs × 7 days), columns `nmi, region, interval_date, total_kwh`.
# MAGIC
# MAGIC > 💡 If the generated code references a missing column, refine: *"The view has columns: nmi, interval_date, interval_number, read_kwh, quality_flag, meter_serial, region."*

# COMMAND ----------

# TODO: Use Genie Code → Generate (+ Genie Code button or Cmd+I / Ctrl+I) to write this cell.
# Prompt: "Using the nem12_interval_reads temp view, calculate the total daily consumption
#  in kWh for each NMI and region, ordered by nmi and interval_date ascending. Name the result df_daily."
# Expected columns: nmi, region, interval_date, total_kwh
# Expected rows: 14 (2 NMIs × 7 days)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.2 — Generate a window function query
# MAGIC
# MAGIC **Navigate:** workspace top toolbar → ✨ sparkle icon → Genie Code panel opens → confirm **Chat** mode is active at the bottom of the panel.
# MAGIC **You should see:** the conversation thread with a text input at the bottom.
# MAGIC
# MAGIC Type this prompt and press Enter:
# MAGIC
# MAGIC > *"For each NMI and day in nem12_interval_reads, find the 30-minute interval with the highest actual (quality_flag = 'A') energy read. Return: nmi, interval_date, peak_interval_number, and peak_kwh. Use a window function with row_number()."*
# MAGIC
# MAGIC When the code block appears in the panel, click **"Insert into notebook"**, then run the inserted cell.

# COMMAND ----------

# TODO: Use Genie Code (chat panel) to generate the peak interval calculation.
# Expected columns: nmi, interval_date, peak_interval_number, peak_kwh
# Expected rows: 14 (2 NMIs × 7 days)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Code Explanation
# MAGIC
# MAGIC Genie Code can explain unfamiliar code — useful when onboarding to a new codebase or reviewing a colleague's work.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.1 — Explain a demand profiling transformation
# MAGIC
# MAGIC Run the cell below, then use Genie to explain it.
# MAGIC
# MAGIC **Navigate:** hover over the code cell → right-click → **Explain** (or open Genie Code panel → type `/explain`)
# MAGIC **You should see:** an explanation appear in the Genie Code panel describing each transformation step.
# MAGIC
# MAGIC Discussion question: does the explanation correctly identify the morning peak (7–9am) and evening peak (5–8pm) windows used in NEM retail billing?

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
# MAGIC ### Exercise 3.2 — Explain a SQL data quality query
# MAGIC
# MAGIC Run the SQL cell below, then ask in the Genie Code panel:
# MAGIC > *"What is this query doing, and why might a NEM retailer need it? What does the HAVING clause filter for?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     nmi,
# MAGIC     interval_date,
# MAGIC     SUM(read_kwh)                                               AS daily_kwh,
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
# MAGIC The cells below contain **intentional bugs**. Run each cell, then use Genie Code to fix it.
# MAGIC
# MAGIC **Navigate:** run a cell → error appears in output area → click the **"Diagnose Error"** button in the cell output
# MAGIC **You should see:** Genie Code read both the code and the error message, then suggest a fix in the panel. Click **Apply** (creates a diff view first) to accept.
# MAGIC
# MAGIC > Always review AI-generated fixes before applying — Genie reads the error, not your original intent.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.1 — Fix a column name error

# COMMAND ----------

# BUG: Column name typo. Run it → click "Diagnose Error" → apply fix.
df_bug1 = (
    df_meters
    .filter(F.col("quality_flg") == "A")          # <-- bug: "quality_flg" should be "quality_flag"
    .groupBy("nmi", "region")
    .agg(F.sum("read_kwh").alias("total_kwh"))
)
df_bug1.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.2 — Fix a logic error (silent bug)
# MAGIC
# MAGIC This cell runs without error but returns the **wrong rows**. Describe the problem to Genie:
# MAGIC > *"This filter is wrong — I want meters where more than 5% of intervals are estimated, but it's returning the opposite. Fix the filter condition."*

# COMMAND ----------

# BUG: Runs without error but returns meters BELOW the 5% threshold.
# Should return meters where MORE THAN 5% of intervals are estimated.

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

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.3 — Fix a write format typo

# COMMAND ----------

# BUG: Format string typo. Run it → click "Diagnose Error" → apply fix.

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
# MAGIC **Document** adds docstrings to functions. **Optimise** rewrites anti-patterns (loops, collects, UDFs) with idiomatic Spark.
# MAGIC
# MAGIC **Navigate:** hover over a cell → right-click → **Document** or **Optimise** (or open Genie Code panel → type `/document` or `/optimise`)
# MAGIC **You should see:** Genie suggest a docstring or a rewritten cell in the panel; click Accept to apply.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.1 — Document a function
# MAGIC
# MAGIC Hover over the cell below → right-click → **Document**. Check the generated docstring correctly identifies what `peak_kwh` and `total_kwh` represent and handles the edge case (`peak_kwh <= 0`).

# COMMAND ----------

def calculate_load_factor(peak_kwh: float, total_kwh: float, periods: int = 48) -> float:
    if peak_kwh <= 0:
        return 0.0
    average_kwh = total_kwh / periods
    return round(average_kwh / peak_kwh, 4)


lf = calculate_load_factor(peak_kwh=2.8, total_kwh=68.4, periods=48)
print(f"Load factor: {lf}")   # Expected: ~0.5089

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.2 — Optimise a slow transformation
# MAGIC
# MAGIC The cell below calls `.collect()` on a Spark DataFrame — a well-known anti-pattern that OOMs on large NEM12 datasets. Run it, then hover → right-click → **Optimise**. Verify Genie replaces the Python loop with a native Spark `.filter()`.

# COMMAND ----------

# SLOW: Python loop over collected Spark rows — anti-pattern for large datasets
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
# MAGIC ## Section 6 — Best Practices & Keyboard Shortcuts
# MAGIC
# MAGIC ### Writing effective prompts
# MAGIC
# MAGIC | Do | Don't |
# MAGIC |---|---|
# MAGIC | Name the DataFrame / view you're working with | Say "write a query" without context |
# MAGIC | Specify exact column names | Assume Genie knows your schema |
# MAGIC | State the expected output shape (rows, columns) | Use vague terms like "transform the data" |
# MAGIC | Include domain terms (NMI, NEM12, kWh, SAIDI) | Use generic variable names like `df2` |
# MAGIC | Say what to avoid ("no UDFs", "use window functions") | Accept the first suggestion blindly |
# MAGIC
# MAGIC ### Chat vs Agent mode
# MAGIC
# MAGIC **Navigate:** workspace top toolbar → ✨ sparkle icon → look at the **bottom of the Genie Code panel** for the toggle.
# MAGIC **You should see:** a Chat/Agent toggle next to the text input — Chat is the default.
# MAGIC
# MAGIC | | Chat mode | Agent mode |
# MAGIC |---|---|---|
# MAGIC | Provider | Azure AI Services (in-region ✅) | Anthropic Claude on Databricks (in-region ✅) |
# MAGIC | Code execution | Generates only | Can write and execute code |
# MAGIC | Speed | ~2–5 s | ~15–60 s |
# MAGIC | Best for | Quick generation, snippets | Complex analysis, debugging, unknowns |
# MAGIC
# MAGIC > ⚠️ **AU East note:** Agent mode requires "Partner-powered AI features" ON in workspace settings. Switching it OFF disables Genie Code entirely.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Wrap-up Exercises
# MAGIC
# MAGIC Work through these independently using Genie Code. Do **not** write the code by hand — the goal is practising effective prompting.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.1 — Rolling average with a window function
# MAGIC
# MAGIC Use the Genie panel to generate a 7-day rolling average of daily consumption per NMI.
# MAGIC
# MAGIC **Prompt:**
# MAGIC > *"Using df_meters (columns: nmi, interval_date, read_kwh), first group by nmi and interval_date to get a daily total, then calculate a 7-day rolling average of daily_kwh using a Spark window function partitioned by nmi and ordered by interval_date. Name the result df_rolling."*

# COMMAND ----------

# TODO: Use Genie Code to write a 7-day rolling average per NMI.
# Expected columns: nmi, interval_date, daily_kwh, rolling_7d_avg
# Expected rows: 14 (one per NMI per day)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.2 — Flag missing intervals
# MAGIC
# MAGIC Use the chat panel with these two messages (multi-turn):
# MAGIC
# MAGIC Message 1:
# MAGIC > *"I have a NEM12 DataFrame called df_meters with columns: nmi (string), interval_date (date), interval_number (int, 1–48 per day), read_kwh (double). I want to detect missing 30-minute intervals — days where some interval_numbers are absent for a given NMI."*
# MAGIC
# MAGIC Message 2:
# MAGIC > *"Write a function called flag_missing_intervals(df) that returns the NMI and date combinations where the count of interval_numbers is less than 48. Include the actual count so I know how many are missing."*

# COMMAND ----------

# TODO: Use Genie Code (chat panel, multi-step) to write flag_missing_intervals().
# Test on df_meters — should return 0 rows (all 48 intervals × 2 NMIs × 7 days are present).

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.3 — Reflection via chat
# MAGIC
# MAGIC In the Genie Code panel, send:
# MAGIC > *"I'm working with Australian NEM12 electricity meter data in Databricks. What are 3 common data quality issues I should watch for in interval reads, and how would I detect each one using PySpark?"*
# MAGIC
# MAGIC A good answer covers: missing intervals, excessive estimated reads (`quality_flag = 'E'`), duplicate records, and out-of-range values.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 01 Complete
# MAGIC
# MAGIC <div style="background: #1B3139; padding: 16px; border-radius: 6px; border-left: 4px solid #FF6B35">
# MAGIC   <p style="color: #FFFFFF; margin: 0 0 8px 0; font-weight: bold">Key takeaways</p>
# MAGIC   <ul style="color: #AECBCC; margin: 0">
# MAGIC     <li>Open Genie Code via the ✨ sparkle icon in the workspace top toolbar, or Cmd+I / Ctrl+I inline in a cell</li>
# MAGIC     <li>Hover between cells → [+ Genie Code] to generate a brand-new cell from a prompt</li>
# MAGIC     <li>Run a cell → click "Diagnose Error" in the output to let Genie read code + error together</li>
# MAGIC     <li>Effective prompts name your DataFrame, specify column names, and include domain context (NMI, NEM12)</li>
# MAGIC     <li>Chat/Agent toggle is at the bottom of the Genie Code panel; Agent mode can write and execute code</li>
# MAGIC     <li>All completions run in-region for Australia East — no data leaves the region</li>
# MAGIC   </ul>
# MAGIC </div>
# MAGIC
# MAGIC **Next:** Lab 02 — Notebook AI Features & Chat Panel →
