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
# MAGIC | ⏱️ **Duration** | 45 minutes |
# MAGIC | 👤 **Role** | Developer / Data Engineer / Data Scientist |
# MAGIC | ✅ **By the end** | You'll be able to generate, fix, explain, and optimise code using Genie Code |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What you'll learn
# MAGIC
# MAGIC | Topic | Time |
# MAGIC |-------|------|
# MAGIC | Where to find Genie Code in the notebook UI | 5 min |
# MAGIC | Code generation from natural language | 10 min |
# MAGIC | Code explanation & documentation | 10 min |
# MAGIC | Code debugging with the Fix action | 10 min |
# MAGIC | Document, Optimise, and best practices | 5 min |
# MAGIC | Independent wrap-up exercises | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Prerequisites
# MAGIC
# MAGIC - Access to a Databricks workspace in **Australia East**
# MAGIC - Unity Catalog enabled
# MAGIC - Genie Code (Databricks Assistant) is on by default — no setup needed
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### About Genie Code
# MAGIC
# MAGIC **Genie Code** is the AI-powered coding assistant embedded directly in Databricks notebooks.
# MAGIC It runs **in-region for Australia East** using Azure AI Services (Chat mode) and
# MAGIC Anthropic Claude via Databricks Provisioned Throughput (Agent mode).
# MAGIC
# MAGIC | Feature | How to access |
# MAGIC |---------|---------------|
# MAGIC | **Generate** code from a description | Click `+` → "Generate with AI", or press `G` in command mode |
# MAGIC | **Fix** broken code | Click the **Fix** button in the error output, or right-click a cell |
# MAGIC | **Explain** what code does | Right-click a cell → **Explain** |
# MAGIC | **Optimise** a cell | Right-click a cell → **Optimise** |
# MAGIC | **Document** a function | Right-click a cell → **Document** |
# MAGIC | **Chat panel** | Click the ✨ sparkle icon in the **top-right corner** of the workspace toolbar, press `Ctrl+I` (Windows) / `Cmd+I` (Mac), or click `Ctrl+Shift+P` / `Cmd+Shift+P` → "Assistant" |
# MAGIC
# MAGIC > 🔒 **Regulatory note:** All Genie Code completions are processed by Azure AI Services
# MAGIC > hosted in **Australia East**. Your code and data **do not leave the region**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before We Code: 5-Minute UI Orientation (do this first!)
# MAGIC
# MAGIC This lab is about using Genie Code — the AI assistant built into the notebook.
# MAGIC Before any setup cells run, spend 5 minutes exploring the UI in THIS notebook.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 1 — Find the sparkle icon on this very cell
# MAGIC
# MAGIC **What to do:**
# MAGIC ```
# MAGIC 1. Hover over this markdown cell
# MAGIC    → A small ✨ icon appears in the top-right corner
# MAGIC 2. Click it — a menu appears with options:
# MAGIC      Fix  /  Explain  /  Optimise  /  Document  /  Generate
# MAGIC 3. Click "Explain" — Genie Code will explain this cell to you
# MAGIC 4. Read the explanation, then close the panel
# MAGIC ```
# MAGIC
# MAGIC This is Genie Code's inline action mode. Every cell in every notebook has it.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 2 — Open the Assistant chat panel
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Top-right toolbar of this notebook
# MAGIC   → Look for the ✨ (sparkle) icon or "Assistant" button
# MAGIC   → Click it to open the side panel
# MAGIC ```
# MAGIC
# MAGIC **What you should see:**
# MAGIC ```
# MAGIC ┌──────────────────────────────────┐
# MAGIC │  Databricks Assistant            │
# MAGIC │  ──────────────────────────────  │
# MAGIC │                                  │
# MAGIC │  Chat mode  |  Agent mode        │
# MAGIC │                                  │
# MAGIC │  [ Ask me anything... ]  [Send]  │
# MAGIC └──────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC Type: `What tables are in the main catalog?`
# MAGIC and observe the response — Genie Code can already see your Unity Catalog.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 3 — See the "Generate with AI" cell creation button
# MAGIC
# MAGIC **What to do:**
# MAGIC ```
# MAGIC Hover between any two cells in this notebook
# MAGIC   → A "+" button appears
# MAGIC   → Click it and look for "Generate" or "AI Generate" option
# MAGIC ```
# MAGIC
# MAGIC This is how you ask Genie Code to write a completely new cell from scratch.
# MAGIC You will use this extensively in Part 1 of this lab.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Time check:** 5 minutes. Return here before continuing.
# MAGIC Part 0 below walks through all three access methods in detail.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🖱️ Part 0: Finding Genie Code in the Notebook UI
# MAGIC
# MAGIC Genie Code is embedded directly in the Databricks notebook interface.
# MAGIC There are three ways to access it — you should know all three.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Option 1 — The sparkle icon on a cell
# MAGIC
# MAGIC Every notebook cell has a small ✨ icon that appears when you hover over it.
# MAGIC Click it to open an inline action menu.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Notebook Cell ─────────────────────────────────────────────┐
# MAGIC │                                                               │
# MAGIC │   # Your code here                                            │
# MAGIC │                                                               │
# MAGIC │                         [✨]  ← appears top-right on hover   │
# MAGIC └───────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Clicking ✨ opens:
# MAGIC   ┌──────────────────────┐
# MAGIC   │  ✨ Generate         │  ← write new code from a description
# MAGIC   │  💬 Explain          │  ← explain what this cell does
# MAGIC   │  🔧 Fix              │  ← fix an error (active after a failure)
# MAGIC   │  📄 Document         │  ← add a docstring
# MAGIC   │  ⚡ Optimise         │  ← suggest performance improvements
# MAGIC   └──────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Option 2 — The Genie panel (right sidebar)
# MAGIC
# MAGIC The Genie panel is a persistent chat window docked to the right side of the notebook.
# MAGIC It supports multi-turn conversations and can see the cells in your notebook.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Notebook ───────────────────────────┬─── Genie Panel ────────────────┐
# MAGIC │  [Cell 1]                              │  ✨ Genie Code                 │
# MAGIC │  [Cell 2]                              │  ──────────────────────────    │
# MAGIC │  [Cell 3]                              │  [Chat ●] [Agent ○]  ← toggle │
# MAGIC │  ...                                   │                                │
# MAGIC │                                        │  Hello! Ask me anything about  │
# MAGIC │                                        │  your notebook or data.        │
# MAGIC │                                        │                                │
# MAGIC │                                        │  ┌──────────────────────────┐  │
# MAGIC │                                        │  │ Ask anything...          │  │
# MAGIC │                                        │  └──────────────────────────┘  │
# MAGIC └────────────────────────────────────────┴────────────────────────────────┘
# MAGIC
# MAGIC To open the panel: click the ✨ icon in the RIGHT SIDEBAR of the notebook
# MAGIC (the narrow icon strip on the far right edge of the screen)
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Option 3 — Keyboard shortcut
# MAGIC
# MAGIC | Platform | Shortcut |
# MAGIC |----------|----------|
# MAGIC | Mac | `Cmd+I` |
# MAGIC | Windows / Linux | `Ctrl+I` |
# MAGIC
# MAGIC Or click the ✨ sparkle icon in the **top-right corner** of the workspace (not the cell — it's in the main workspace toolbar).
# MAGIC Also available via command palette: `Ctrl+Shift+P` (Win) / `Cmd+Shift+P` (Mac) → type "Assistant"
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC > 💡 **If you don't see the Genie Code icon**, check that Notebook Assistant is enabled:
# MAGIC > **Workspace Settings → AI & Machine Learning → Notebook Assistant: ON**
# MAGIC >
# MAGIC > Ask your workspace admin if this setting is grayed out.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🧪 Try it now — UI familiarisation (no code required)
# MAGIC
# MAGIC Before running any code, spend 2 minutes getting comfortable with the interface:
# MAGIC
# MAGIC **Step 1 — Open the Genie panel**
# MAGIC - Press `Cmd+I` (Mac) / `Ctrl+I` (Windows), OR click the ✨ sparkle icon in the **top-right corner** of the workspace (not the cell — it's in the main workspace toolbar)
# MAGIC - The panel should slide open on the right
# MAGIC
# MAGIC **Step 2 — Find the mode toggle**
# MAGIC - At the top of the Genie panel, look for **[Chat] [Agent]**
# MAGIC - Make sure **Chat** is selected for now (we'll switch to Agent mode in Part 5)
# MAGIC
# MAGIC **Step 3 — Hover over this cell**
# MAGIC - Move your mouse over the code cell immediately below this one
# MAGIC - The ✨ icon should appear in the top-right corner of that cell
# MAGIC - Click the ✨ icon to see the action menu (Generate / Explain / Fix / Document / Optimise)
# MAGIC - Press `Esc` to close the menu without selecting anything
# MAGIC
# MAGIC **Step 4 — Try the keyboard shortcut**
# MAGIC - Click somewhere in the code cell below to select it (edit mode)
# MAGIC - Press `Esc` to enter command mode (the cell border turns blue)
# MAGIC - Press `G` — this should open the "Generate with AI" prompt inline
# MAGIC - Press `Esc` again to close it
# MAGIC
# MAGIC ✅ You're ready. Open the Genie panel and leave it open for the rest of the lab.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🔧 Section 1 — Setup
# MAGIC
# MAGIC Run this cell to create a sample energy dataset used throughout the lab.
# MAGIC This simulates National Electricity Market (NEM) interval meter data for
# MAGIC New South Wales and Victoria — two common NEM regions.
# MAGIC
# MAGIC > **What is NEM12?** NEM12 is the Australian standard file format for interval meter data.
# MAGIC > Each row is a 30-minute energy reading (kWh) identified by an NMI (National Meter Identifier).
# MAGIC > Quality flags: `A` = Actual read, `E` = Estimated.

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
# MAGIC ### ✅ Expected output after running setup
# MAGIC
# MAGIC ```
# MAGIC Created nem12_interval_reads with 672 rows
# MAGIC
# MAGIC +----------+-------------+---------------+--------+------------+------------+------+
# MAGIC |nmi       |interval_date|interval_number|read_kwh|quality_flag|meter_serial|region|
# MAGIC +----------+-------------+---------------+--------+------------+------------+------+
# MAGIC |6001234567|2024-07-01   |1              |0.783   |A           |METER-4567  |NSW1  |
# MAGIC |6001234567|2024-07-01   |2              |0.801   |A           |METER-4567  |NSW1  |
# MAGIC |6001234567|2024-07-01   |3              |0.822   |E           |METER-4567  |NSW1  |
# MAGIC ...
# MAGIC ```
# MAGIC
# MAGIC **Check:** 672 rows = 2 NMIs × 7 days × 48 intervals. If the count is different, re-run the cell.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✍️ Section 2 — Code Generation
# MAGIC
# MAGIC Genie Code can write PySpark and SQL from a plain English description.
# MAGIC The key to good output is a **specific prompt** — name your DataFrame, list the
# MAGIC columns, and describe the output shape.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### How to Generate code in a new cell
# MAGIC
# MAGIC ```
# MAGIC Method A — From the + button:
# MAGIC   1. Click the [+ Code] button below any cell
# MAGIC   2. An empty code cell appears
# MAGIC   3. In the empty cell, click the ✨ icon → "Generate"
# MAGIC      OR press G (command mode) to open the inline prompt
# MAGIC   4. Type your prompt and press Enter
# MAGIC   5. Genie writes the code inside the cell
# MAGIC   6. Click "Accept" to keep it, or "Discard" to try again
# MAGIC
# MAGIC Method B — From the Genie panel:
# MAGIC   1. Open the Genie panel (right sidebar ✨)
# MAGIC   2. Type your prompt in the chat box
# MAGIC   3. Genie replies with a code block
# MAGIC   4. Click "Insert into notebook" to add it as a new cell below the current one
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.1 — Generate a daily aggregation
# MAGIC
# MAGIC Use Genie Code to generate the cell below from a description.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Click into the code cell immediately below this one (it has a `# TODO` comment)
# MAGIC 2. Press `Esc` then `G` to open the Generate prompt
# MAGIC 3. Paste or type this prompt exactly:
# MAGIC
# MAGIC > *"Using the nem12_interval_reads temp view, calculate the total daily
# MAGIC > consumption in kWh for each NMI and region, ordered by nmi and
# MAGIC > interval_date ascending. Name the result df_daily."*
# MAGIC
# MAGIC 4. Press Enter and wait for Genie to write the code
# MAGIC 5. Click **Accept**, then run the cell
# MAGIC
# MAGIC > 💡 **If the generated code references a column that doesn't exist**, refine:
# MAGIC > *"The view has columns: nmi, interval_date, interval_number, read_kwh,
# MAGIC > quality_flag, meter_serial, region. Recalculate the daily total."*

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
# MAGIC ### ✅ Expected output — Exercise 2.1
# MAGIC
# MAGIC After a correct generation and run, `df_daily.show()` should produce something like:
# MAGIC
# MAGIC ```
# MAGIC +----------+------+-------------+---------+
# MAGIC |nmi       |region|interval_date|total_kwh|
# MAGIC +----------+------+-------------+---------+
# MAGIC |6001234567|NSW1  |2024-07-01   |38.42    |
# MAGIC |6001234567|NSW1  |2024-07-02   |37.98    |
# MAGIC ...
# MAGIC |6009876543|VIC1  |2024-07-07   |57.31    |
# MAGIC +----------+------+-------------+---------+
# MAGIC 14 rows
# MAGIC ```
# MAGIC
# MAGIC **Check:** 14 rows total (2 NMIs × 7 days). NSW1 values ~38 kWh/day, VIC1 ~57 kWh/day
# MAGIC because VIC1 has a higher base load in our simulated data.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.2 — Generate a more complex aggregation
# MAGIC
# MAGIC Now try a prompt that requires window functions and filtering.
# MAGIC Use the Genie panel (right sidebar) for this one rather than the inline `G` shortcut.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Open the Genie panel if it's not already open (✨ right sidebar)
# MAGIC 2. Make sure **Chat** mode is selected
# MAGIC 3. Type the prompt below and press Enter
# MAGIC 4. When the code block appears, click **"Insert into notebook"**
# MAGIC 5. Run the inserted cell
# MAGIC
# MAGIC > *"For each NMI and day in nem12_interval_reads, find the 30-minute interval
# MAGIC > with the highest actual (quality_flag = 'A') energy read. Return:
# MAGIC > nmi, interval_date, peak_interval_number (the interval_number at peak),
# MAGIC > and peak_kwh."*
# MAGIC
# MAGIC > 💡 **Tip:** Mention "use a window function with row_number()" if Genie doesn't
# MAGIC > produce a window-based solution on first try.

# COMMAND ----------

# TODO: Use Genie Code (chat panel) to generate the peak interval calculation.
# Find peak 30-minute interval per NMI per day (actual reads only).
# Expected columns: nmi, interval_date, peak_interval_number, peak_kwh
# Expected rows: 14 (2 NMIs × 7 days — same shape as df_daily)

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Expected output — Exercise 2.2
# MAGIC
# MAGIC The generated code should look roughly like this (Genie may produce variants):
# MAGIC
# MAGIC ```python
# MAGIC from pyspark.sql import Window
# MAGIC from pyspark.sql import functions as F
# MAGIC
# MAGIC window = Window.partitionBy("nmi", "interval_date").orderBy(F.col("read_kwh").desc())
# MAGIC
# MAGIC df_peak = (
# MAGIC     spark.table("nem12_interval_reads")
# MAGIC     .filter(F.col("quality_flag") == "A")
# MAGIC     .withColumn("rank", F.row_number().over(window))
# MAGIC     .filter(F.col("rank") == 1)
# MAGIC     .select("nmi", "interval_date",
# MAGIC             F.col("interval_number").alias("peak_interval_number"),
# MAGIC             F.col("read_kwh").alias("peak_kwh"))
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC If Genie produces a `groupBy().agg(F.max(...))` approach instead of a window,
# MAGIC that also works but won't return the `interval_number` at peak — follow up with:
# MAGIC *"The current approach loses the interval_number at peak. Rewrite using a window function."*

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 💬 Section 3 — Code Explanation
# MAGIC
# MAGIC Genie Code can explain what unfamiliar code does — useful when onboarding to a
# MAGIC new codebase or reviewing a colleague's work.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### How to use "Explain" on a cell
# MAGIC
# MAGIC ```
# MAGIC Method A — Hover icon:
# MAGIC   1. Hover over the cell you want explained
# MAGIC   2. Click the ✨ icon (top-right of cell)
# MAGIC   3. Select "Explain"
# MAGIC   4. The explanation appears in the Genie panel on the right
# MAGIC
# MAGIC Method B — Right-click menu:
# MAGIC   1. Right-click anywhere in the cell
# MAGIC   2. Select "Explain with Genie" from the context menu
# MAGIC
# MAGIC Method C — Chat panel:
# MAGIC   1. Open the Genie panel
# MAGIC   2. Type: "Explain what the following code does:"
# MAGIC   3. Paste the code below your message
# MAGIC   4. Press Enter
# MAGIC
# MAGIC   This is useful when you want to ask follow-up questions like:
# MAGIC   "Why would a NEM retailer use this logic?"
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.1 — Explain a demand profiling transformation
# MAGIC
# MAGIC The cell below contains a PySpark transformation a colleague wrote.
# MAGIC It works, but the intent isn't immediately obvious.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Run the cell below first (so you can see the output)
# MAGIC 2. Hover over the cell → click ✨ → "Explain"
# MAGIC 3. Read the explanation in the Genie panel
# MAGIC
# MAGIC **Discussion question:** Does the explanation correctly identify that this is a
# MAGIC **demand period profiling** transformation used in NEM retail billing?
# MAGIC Does it identify the morning peak (7–9am) and evening peak (5–8pm) windows?

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
# MAGIC ### ✅ What a good Genie Explain response looks like
# MAGIC
# MAGIC A strong Genie Code explanation for the cell above will say something like:
# MAGIC
# MAGIC ```
# MAGIC This code performs demand period profiling on NEM12 interval meter data.
# MAGIC
# MAGIC Here's what each step does:
# MAGIC
# MAGIC 1. hour_of_day: Converts interval_number (1–48) into the actual hour of day.
# MAGIC    Interval 1 = midnight, interval 15 = 7am, etc.
# MAGIC
# MAGIC 2. period: Classifies each 30-minute interval into a demand period:
# MAGIC    - morning_peak: 7am–9am (common NEM peak tariff window)
# MAGIC    - evening_peak: 5pm–8pm (typical evening demand peak in AU)
# MAGIC    - off_peak: 10pm–5am
# MAGIC    - shoulder: all other hours
# MAGIC
# MAGIC 3. groupBy + agg: For each NMI, region, and period, calculates:
# MAGIC    - Average, maximum, and standard deviation of kWh readings
# MAGIC    - Count of intervals in that period
# MAGIC
# MAGIC Use case: A NEM retailer uses this to calculate time-of-use (TOU) charges,
# MAGIC identify demand patterns, and produce bills for customers on TOU tariffs.
# MAGIC ```
# MAGIC
# MAGIC If the explanation is generic (doesn't mention NEM or TOU), follow up in the chat:
# MAGIC *"Why would an Australian electricity retailer use this code specifically?"*

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.2 — Explain a SQL query
# MAGIC
# MAGIC Run the SQL cell below, then use the Genie chat panel to ask:
# MAGIC > *"What is this query doing, and why might a NEM retailer need it?"*
# MAGIC
# MAGIC After the explanation, follow up with:
# MAGIC > *"What does the HAVING clause filter for, and what threshold should a well-run
# MAGIC > meter data agent (MDA) aim for?"*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- What does this query do in a NEM retail context?
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
# MAGIC ### ✅ What a good Genie Explain response looks like — SQL version
# MAGIC
# MAGIC ```
# MAGIC This query is a data quality audit for NEM12 interval meter readings.
# MAGIC
# MAGIC For each NMI (meter) and day:
# MAGIC - It counts how many 30-minute intervals were estimated (quality_flag = 'E')
# MAGIC   rather than actual meter reads (quality_flag = 'A')
# MAGIC - It calculates pct_estimated: the percentage of that day's readings that
# MAGIC   are estimated rather than measured
# MAGIC
# MAGIC The HAVING clause filters to only show days where more than 5% of intervals
# MAGIC are estimated — these are the "problem" days.
# MAGIC
# MAGIC Why a NEM retailer needs this:
# MAGIC Under the National Energy Rules, excessive estimated readings can trigger
# MAGIC an obligation to back-substitute with actual data. A meter data agent (MDA)
# MAGIC is typically required to keep estimated reads below 5% on an annualised basis.
# MAGIC This query identifies which meters and dates are at risk of breaching that threshold.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🐛 Section 4 — Code Debugging
# MAGIC
# MAGIC The cells in this section contain **intentional bugs**.
# MAGIC Your task: run each cell, read the error, then use Genie Code to fix it.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### How to use "Fix" on a broken cell
# MAGIC
# MAGIC ```
# MAGIC Step 1 — Run the cell (it produces a red error output)
# MAGIC
# MAGIC Step 2 — Look at the error output at the bottom of the cell:
# MAGIC
# MAGIC   ┌─── Cell with error ────────────────────────────────────────┐
# MAGIC   │  display(df.groupby("region").agg({"kwh": "sum"}))         │
# MAGIC   ├────────────────────────────────────────────────────────────┤
# MAGIC   │  AnalysisException: Column 'kwh' not found. Did you mean   │
# MAGIC   │  one of the following? [read_kwh, total_kwh]               │
# MAGIC   │                                         [✨ Diagnose Error]│ ← click here
# MAGIC   └────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Step 3 — Click "✨ Diagnose Error" (appears in the error footer)
# MAGIC           OR right-click the cell → "Fix"
# MAGIC           OR hover over the cell → ✨ → Fix
# MAGIC
# MAGIC Step 4 — Genie reads BOTH the code AND the error message, then suggests a fix
# MAGIC           in the Genie panel on the right
# MAGIC
# MAGIC Step 5 — Review the fix. Ask yourself:
# MAGIC           - Does the suggested column name exist in the schema?
# MAGIC           - Does the logic still match the original intent?
# MAGIC
# MAGIC Step 6 — Click "Apply" to update the cell in place,
# MAGIC           or "Insert" to create a new cell with the fix
# MAGIC
# MAGIC Step 7 — Re-run the fixed cell
# MAGIC ```
# MAGIC
# MAGIC > ⚠️ **Always review AI-generated fixes before applying.**
# MAGIC > Genie reads the error, not your original intent — double check the logic is correct.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.1 — Fix a column name error

# COMMAND ----------

# BUG: This cell has a column name typo. Run it to see the error, then use Genie Code → Fix.
df_bug1 = (
    df_meters
    .filter(F.col("quality_flg") == "A")          # <-- bug here: "quality_flg" should be "quality_flag"
    .groupBy("nmi", "region")
    .agg(F.sum("read_kwh").alias("total_kwh"))
)
df_bug1.show()

# Expected output after fix: 2 rows, one per NMI, total kWh for Actual reads only

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What Genie Fix should produce — Exercise 4.1
# MAGIC
# MAGIC After clicking Fix, the Genie panel should suggest:
# MAGIC
# MAGIC ```python
# MAGIC # Fix: corrected column name from "quality_flg" to "quality_flag"
# MAGIC df_bug1 = (
# MAGIC     df_meters
# MAGIC     .filter(F.col("quality_flag") == "A")   # ← corrected
# MAGIC     .groupBy("nmi", "region")
# MAGIC     .agg(F.sum("read_kwh").alias("total_kwh"))
# MAGIC )
# MAGIC df_bug1.show()
# MAGIC ```
# MAGIC
# MAGIC After applying and re-running, you should see 2 rows:
# MAGIC ```
# MAGIC +----------+------+---------+
# MAGIC |nmi       |region|total_kwh|
# MAGIC +----------+------+---------+
# MAGIC |6001234567|NSW1  |~252.0   |
# MAGIC |6009876543|VIC1  |~379.0   |
# MAGIC +----------+------+---------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.2 — Fix a logic error (silent bug)
# MAGIC
# MAGIC This cell runs without error but returns the **wrong rows**.
# MAGIC The comment describes what the intended behaviour should be.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Run the cell — it succeeds but the results are wrong
# MAGIC 2. Use the Genie chat panel and describe the problem:
# MAGIC    > *"This filter is wrong — I want meters where more than 5% of intervals
# MAGIC    > are estimated, but it's returning the opposite. Fix the filter condition."*
# MAGIC 3. Apply the fix and re-run

# COMMAND ----------

# BUG: This cell runs without error but returns meters BELOW the 5% threshold.
# It should return meters where MORE THAN 5% of intervals are estimated (data quality alert).
# The logic bug is in the .filter() condition.

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

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What Genie Fix should produce — Exercise 4.2
# MAGIC
# MAGIC Genie should change `< 0.05` to `> 0.05`. After fixing:
# MAGIC
# MAGIC ```
# MAGIC +----------+---------------+---------------+-------------+
# MAGIC |nmi       |total_intervals|estimated_count|pct_estimated|
# MAGIC +----------+---------------+---------------+-------------+
# MAGIC |6001234567|336            |~17            |~0.051       |
# MAGIC +----------+---------------+---------------+-------------+
# MAGIC ```
# MAGIC
# MAGIC (Approximately one NMI should appear — the sample data has ~5% estimated reads by design.
# MAGIC Exact results vary due to the random seed.)
# MAGIC
# MAGIC > 💡 **This is why "Fix" isn't enough for logic bugs** — Genie corrected the operator,
# MAGIC > but you needed to describe the intent. Logic bugs require you to be the domain expert.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.3 — Fix a write format typo

# COMMAND ----------

# BUG: This cell tries to write to Delta format but has a typo in the format string.
# Run it to see the error, then use Genie Code → Fix.

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
# MAGIC ### ✅ What Genie Fix should produce — Exercise 4.3
# MAGIC
# MAGIC ```python
# MAGIC # Fix: corrected format from "dleta" to "delta"
# MAGIC (
# MAGIC     df_meters
# MAGIC     .groupBy("nmi", "interval_date")
# MAGIC     .agg(F.sum("read_kwh").alias("total_kwh"))
# MAGIC     .write
# MAGIC     .format("delta")   # ← corrected
# MAGIC     .mode("overwrite")
# MAGIC     .save(output_path)
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC After applying and re-running:
# MAGIC ```
# MAGIC Written to /tmp/nem12_daily_output
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 📄 Section 5 — Document and Optimise
# MAGIC
# MAGIC Beyond generation and debugging, Genie Code can improve existing code:
# MAGIC - **Document** adds docstrings to functions
# MAGIC - **Optimise** rewrites anti-patterns (loops, collects, UDFs) with idiomatic Spark
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### How to use "Document" on a function
# MAGIC
# MAGIC ```
# MAGIC 1. Click the cell containing the function to select it
# MAGIC 2. Hover → click ✨ → select "Document"
# MAGIC    OR right-click the cell → "Document with Genie"
# MAGIC 3. Genie adds a docstring above or inside the function
# MAGIC 4. Review: does the docstring correctly describe parameters and return value?
# MAGIC 5. Accept if correct
# MAGIC ```
# MAGIC
# MAGIC ### How to use "Optimise" on a slow cell
# MAGIC
# MAGIC ```
# MAGIC 1. Click the cell with the anti-pattern
# MAGIC 2. Hover → click ✨ → select "Optimise"
# MAGIC    OR right-click → "Optimise with Genie"
# MAGIC 3. Genie suggests a rewritten version in the Genie panel
# MAGIC 4. Compare the original and suggested versions
# MAGIC 5. Accept or insert as a new cell
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.1 — Document a function
# MAGIC
# MAGIC The function below works correctly but has no docstring.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Hover over the cell → click ✨ → "Document"
# MAGIC 2. Read the generated docstring — does it correctly describe:
# MAGIC    - What `peak_kwh` and `total_kwh` represent?
# MAGIC    - What a load factor value near 0.5 means in NEM terms?
# MAGIC    - The edge case (peak_kwh <= 0)?
# MAGIC 3. Accept if correct, or follow up in chat with domain context

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
# MAGIC ### ✅ What a good Document response looks like
# MAGIC
# MAGIC ```python
# MAGIC def calculate_load_factor(peak_kwh: float, total_kwh: float, periods: int = 48) -> float:
# MAGIC     """
# MAGIC     Calculate the load factor for a NEM meter over a given period.
# MAGIC
# MAGIC     Load factor measures how evenly energy is consumed relative to peak demand.
# MAGIC     A value of 1.0 means perfectly flat consumption; lower values indicate
# MAGIC     significant peaks. Used in NEM network tariff calculations.
# MAGIC
# MAGIC     Args:
# MAGIC         peak_kwh (float): The highest single-interval energy read in kWh.
# MAGIC         total_kwh (float): Total energy consumed across all intervals in kWh.
# MAGIC         periods (int): Number of intervals in the period. Defaults to 48
# MAGIC                        (one full day of 30-minute NEM12 intervals).
# MAGIC
# MAGIC     Returns:
# MAGIC         float: Load factor rounded to 4 decimal places. Returns 0.0 if
# MAGIC                peak_kwh is zero or negative (to avoid division by zero).
# MAGIC
# MAGIC     Example:
# MAGIC         >>> calculate_load_factor(peak_kwh=2.8, total_kwh=68.4, periods=48)
# MAGIC         0.5089
# MAGIC     """
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.2 — Optimise a slow transformation
# MAGIC
# MAGIC The cell below uses a Python loop over collected Spark rows — a well-known anti-pattern
# MAGIC that will crash on real-scale NEM12 data (millions of rows per meter per year).
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Run the cell and note it works (sample data is small enough)
# MAGIC 2. Hover over the cell → click ✨ → "Optimise"
# MAGIC 3. Read the suggestion — does Genie recommend a vectorised Spark approach?
# MAGIC 4. Accept and re-run to verify the output matches
# MAGIC
# MAGIC > **Why this matters:** The original code calls `.collect()`, which loads all data
# MAGIC > into the driver process. For 1 million rows of NEM12 interval data (a typical
# MAGIC > large retailer), this would OOM the driver. Genie should suggest `.filter()` on
# MAGIC > the Spark DataFrame instead.

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
# MAGIC ### ✅ What a good Optimise response looks like
# MAGIC
# MAGIC Genie should produce something equivalent to:
# MAGIC
# MAGIC ```python
# MAGIC # Optimised: uses native Spark filter and collect only the final small result
# MAGIC df_flagged = (
# MAGIC     df_meters
# MAGIC     .filter((F.col("nmi") == "6001234567") & (F.col("read_kwh") > 2.0))
# MAGIC     .select("nmi", "interval_date", "interval_number", "read_kwh")
# MAGIC )
# MAGIC
# MAGIC count = df_flagged.count()
# MAGIC print(f"High-consumption intervals: {count}")
# MAGIC df_flagged.show(3, truncate=False)
# MAGIC ```
# MAGIC
# MAGIC **Key differences:**
# MAGIC - No `.collect()` until the result is small
# MAGIC - Filter is pushed down to Spark (runs distributed)
# MAGIC - Uses `display()` or `.show()` instead of a Python loop for output

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ⌨️ Section 6 — Best Practices & Keyboard Shortcuts
# MAGIC
# MAGIC ### Writing effective prompts for Genie Code
# MAGIC
# MAGIC | ✅ Do | ❌ Don't |
# MAGIC |-------|---------|
# MAGIC | Name the DataFrame / view you're working with | Say "write a query" without context |
# MAGIC | Specify exact column names | Assume Genie knows your schema |
# MAGIC | State the expected output shape (rows, columns) | Use vague terms like "transform the data" |
# MAGIC | Include domain terms (NMI, NEM12, kWh, SAIDI) | Use generic variable names like `df2` |
# MAGIC | Say what to avoid ("no UDFs", "use window functions") | Accept the first suggestion blindly |
# MAGIC | Provide units and types ("kWh as a double") | Let ambiguous types cause silent bugs |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Keyboard shortcuts
# MAGIC
# MAGIC | Action | Windows / Linux | Mac |
# MAGIC |--------|-----------------|-----|
# MAGIC | Open Genie Code inline (cell) | `Ctrl+I` | `Cmd+I` |
# MAGIC | Generate code (command mode) | `G` | `G` |
# MAGIC | Command palette | `Ctrl+Shift+P` | `Cmd+Shift+P` |
# MAGIC | Run cell + move to next | `Shift+Enter` | `Shift+Enter` |
# MAGIC | Enter command mode | `Esc` | `Esc` |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Providing context in the chat panel
# MAGIC
# MAGIC The chat panel supports several ways to give Genie more context:
# MAGIC
# MAGIC ```
# MAGIC 1. @ mention a cell:
# MAGIC    Type @  in the chat box → a dropdown shows your recent cells
# MAGIC    Select a cell to attach it to your message
# MAGIC
# MAGIC 2. Drag a cell output into chat:
# MAGIC    Click and drag the output section of a cell into the chat input box
# MAGIC    Useful for attaching schema outputs, error messages, or display() results
# MAGIC
# MAGIC 3. Describe your schema inline:
# MAGIC    "I have a table with columns: nmi (string), interval_date (date),
# MAGIC     interval_number (int, 1–48), read_kwh (double). Help me..."
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🏋️ Section 7 — Wrap-up Exercises
# MAGIC
# MAGIC Work through these independently using Genie Code.
# MAGIC Do **not** write the code by hand — the goal is practising effective prompting.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.1 — Rolling average with a window function
# MAGIC
# MAGIC Use the Genie panel to generate code that calculates a 7-day rolling average
# MAGIC of daily consumption per NMI.
# MAGIC
# MAGIC **Prompt to use:**
# MAGIC > *"Using df_meters (columns: nmi, interval_date, read_kwh), first group by nmi
# MAGIC > and interval_date to get a daily total, then calculate a 7-day rolling average
# MAGIC > of daily_kwh using a Spark window function partitioned by nmi and ordered by
# MAGIC > interval_date. Name the result df_rolling."*
# MAGIC
# MAGIC After generating, run the code and display the first 10 rows.

# COMMAND ----------

# TODO: Use Genie Code to write a 7-day rolling average per NMI.
# Expected columns: nmi, interval_date, daily_kwh, rolling_7d_avg
# Expected rows: 14 (same as df_daily — one row per NMI per day)

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Expected output — Exercise 7.1
# MAGIC
# MAGIC ```
# MAGIC +----------+-------------+---------+--------------+
# MAGIC |nmi       |interval_date|daily_kwh|rolling_7d_avg|
# MAGIC +----------+-------------+---------+--------------+
# MAGIC |6001234567|2024-07-01   |38.42    |38.42         |  ← only 1 day, avg = itself
# MAGIC |6001234567|2024-07-02   |37.98    |38.20         |  ← 2-day avg
# MAGIC |6001234567|2024-07-03   |38.11    |38.17         |
# MAGIC ...
# MAGIC |6001234567|2024-07-07   |38.03    |38.12         |  ← full 7-day window
# MAGIC ```
# MAGIC
# MAGIC Note: with only 7 days of data, the rolling window never reaches a full 7-day lookback
# MAGIC until the last row. That's expected with `rowsBetween(-6, 0)`.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.2 — Flag missing intervals
# MAGIC
# MAGIC Use the chat panel to generate a function that detects gaps in interval data.
# MAGIC This is a real data quality check for NEM12 processing pipelines.
# MAGIC
# MAGIC **Multi-step prompt (send each part as a separate message):**
# MAGIC
# MAGIC Message 1:
# MAGIC > *"I have a NEM12 DataFrame called df_meters with columns: nmi (string),
# MAGIC > interval_date (date), interval_number (int, 1–48 per day), read_kwh (double).
# MAGIC > I want to detect missing 30-minute intervals — days where some interval_numbers
# MAGIC > are absent for a given NMI."*
# MAGIC
# MAGIC Message 2 (follow-up):
# MAGIC > *"Write a function called flag_missing_intervals(df) that returns the NMI and date
# MAGIC > combinations where the count of interval_numbers is less than 48.
# MAGIC > Include the actual count so I know how many are missing."*

# COMMAND ----------

# TODO: Use Genie Code (chat panel, multi-step) to write flag_missing_intervals().
# Test it on df_meters — there should be no missing intervals in our sample data
# (all 48 intervals per day × 2 NMIs × 7 days are present → function returns 0 rows).

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.3 — Reflection via chat
# MAGIC
# MAGIC In the Genie chat panel, send this question:
# MAGIC
# MAGIC > *"I'm working with Australian NEM12 electricity meter data in Databricks.
# MAGIC > What are 3 common data quality issues I should watch for in interval reads,
# MAGIC > and how would I detect each one using PySpark?"*
# MAGIC
# MAGIC Discuss the response with the facilitator or a neighbour.
# MAGIC
# MAGIC **Good answers will mention at least:**
# MAGIC - Missing intervals (gaps in interval_number sequence)
# MAGIC - Excessive estimated reads (quality_flag = 'E' above threshold)
# MAGIC - Duplicate records (same NMI + interval_date + interval_number twice)
# MAGIC - Out-of-range values (negative kWh, unrealistically high reads)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 💬 Chat Mode vs 🤖 Agent Mode
# MAGIC
# MAGIC Before finishing Lab 01, understand the two modes you've been using:
# MAGIC
# MAGIC ```
# MAGIC ┌─── Genie Panel ──────────────────────────────────────┐
# MAGIC │  ✨ Genie Code              [Chat ●] [Agent ○]        │ ← toggle here
# MAGIC │  ──────────────────────────────────────────────────  │
# MAGIC │                                                       │
# MAGIC │  [Chat mode]:  Single response per question           │
# MAGIC │    - Faster, good for "generate this code" tasks      │
# MAGIC │    - Provider: Azure AI Services (in-region ✅)       │
# MAGIC │    - Does NOT execute code                            │
# MAGIC │                                                       │
# MAGIC │  [Agent mode]: Multi-step reasoning, uses tools       │
# MAGIC │    - Can look up your UC catalog, query schemas        │
# MAGIC │    - Can write + execute code + iterate on errors     │
# MAGIC │    - Provider: Anthropic Claude (in-region ✅)        │
# MAGIC │    - Slower but handles ambiguous tasks               │
# MAGIC └──────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Try both modes on the same task** in Lab 02 to feel the difference.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">⚙️ Section 4: Personalising Genie Code</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~5 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC ## Custom Instructions — Teaching Genie Your Domain
# MAGIC
# MAGIC Genie Code can be given **persistent domain knowledge** that applies to every conversation:
# MAGIC
# MAGIC | File | Scope | Who sets it |
# MAGIC |------|-------|-------------|
# MAGIC | `/Users/{you}/.assistant_instructions.md` | Personal only | You |
# MAGIC | `Workspace/.assistant_workspace_instructions.md` | All workspace users | Admin |
# MAGIC | `AGENTS.md` in notebook folder | That project only | You (auto-discovered) |
# MAGIC
# MAGIC > 💡 **Note:** These work the same way as `CLAUDE.md` in Claude Code —
# MAGIC > Genie Code's Agent mode walks up your directory tree looking for `AGENTS.md` files.
# MAGIC
# MAGIC ## Skills — On-Demand Knowledge Documents
# MAGIC
# MAGIC Skills are Markdown files stored in `Workspace/.assistant/skills/<name>/SKILL.md`.
# MAGIC Unlike custom instructions (always loaded), skills are loaded on-demand.
# MAGIC Invoke a skill with `@skill-name` in the Genie Code chat panel.
# MAGIC
# MAGIC **→ We cover this in depth in Lab 03.**
# MAGIC
# MAGIC ## Where to Find These Settings in the UI
# MAGIC
# MAGIC ```
# MAGIC Genie Code panel (right sidebar) → ⚙️ gear icon → Personal instructions
# MAGIC
# MAGIC ┌─── Genie Code Settings ─────────────────────────────────┐
# MAGIC │  ⚙️ Settings                                             │
# MAGIC │  ─────────────────────────────────────────────────────  │
# MAGIC │  Personal instructions                                   │
# MAGIC │  ┌─────────────────────────────────────────────────┐   │
# MAGIC │  │ Add context about your role, preferences, and   │   │
# MAGIC │  │ the projects you work on...                      │   │
# MAGIC │  └─────────────────────────────────────────────────┘   │
# MAGIC │                                    [Save]               │
# MAGIC └──────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC > ⚠️ **Note:** Instructions added via the UI settings panel are stored differently
# MAGIC > from the `.assistant_instructions.md` file. The file-based approach (Lab 03)
# MAGIC > is recommended for teams as it can be version-controlled.

# COMMAND ----------

# Quick exercise: check if you have any instructions set
username = spark.sql("SELECT current_user()").collect()[0][0]
try:
    content = dbutils.fs.head(f"/Users/{username}/.assistant_instructions.md", 200)
    print(f"You have instructions set:\n{content[:200]}...")
except:
    print("No personal instructions file yet — we'll create one in Lab 03.")
    print(f"Path would be: /Users/{username}/.assistant_instructions.md")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 01 Complete
# MAGIC
# MAGIC <div style="background: #1B3139; padding: 16px; border-radius: 6px; border-left: 4px solid #FF6B35">
# MAGIC   <p style="color: #FFFFFF; margin: 0 0 8px 0; font-weight: bold">Key takeaways</p>
# MAGIC   <ul style="color: #AECBCC; margin: 0">
# MAGIC     <li>Genie Code has three access points: hover ✨, right-click menu, and the right-sidebar chat panel</li>
# MAGIC     <li>Generate, Explain, Fix, Document, and Optimise are all available from the ✨ icon on a cell</li>
# MAGIC     <li>Effective prompts name your DataFrame, specify column names, and include domain context (NMI, NEM12)</li>
# MAGIC     <li>Always review AI-generated fixes before accepting — especially for logic bugs and write operations</li>
# MAGIC     <li>The chat panel persists context across your conversation within a session</li>
# MAGIC     <li>All Genie Code completions run in-region for Australia East — no data leaves the region</li>
# MAGIC   </ul>
# MAGIC </div>
# MAGIC
# MAGIC **Next:** Lab 02 — Notebook AI Features & Chat Panel →
