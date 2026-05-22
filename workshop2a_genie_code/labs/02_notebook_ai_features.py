# Databricks notebook source

# MAGIC %md
# MAGIC # Lab 02: Notebook AI Features & Chat
# MAGIC **Workshop:** Genie Code for Developers — Australian Regulated Industries
# MAGIC **Estimated time:** 40–45 minutes
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## What you'll learn
# MAGIC
# MAGIC | Topic | Time |
# MAGIC |-------|------|
# MAGIC | Databricks Assistant chat panel overview | 5 min |
# MAGIC | Asking about your workspace (catalog, tables) | 10 min |
# MAGIC | Generating SQL via chat | 10 min |
# MAGIC | Context window and providing better context | 5 min |
# MAGIC | Genie Code Agent mode vs Chat mode | 10 min |
# MAGIC | Wrap-up exercises | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The two modes of Databricks Assistant
# MAGIC
# MAGIC | Mode | Behaviour | When to use |
# MAGIC |------|-----------|-------------|
# MAGIC | **Chat mode** | Single-step: answers one question at a time | Quick lookups, code snippets, schema questions |
# MAGIC | **Agent mode** | Multi-step: reasons, plans, calls tools, iterates | Complex refactoring, multi-file analysis, autonomous tasks |
# MAGIC
# MAGIC **AU East availability:**
# MAGIC - Chat mode: Azure AI Services, **in-region** ✓
# MAGIC - Agent mode: Anthropic Claude (`databricks-claude-sonnet-4-6`) via Databricks Provisioned Throughput, **in-region** ✓
# MAGIC
# MAGIC > Open the assistant now: click the **Assistant** icon in the top-right toolbar,
# MAGIC > or use `Ctrl+Shift+P` → "Open Databricks Assistant".

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup: Create Sample Tables in Unity Catalog
# MAGIC
# MAGIC We'll create tables that represent a real energy retailer's data landscape.
# MAGIC This lets you practise asking the Assistant questions about actual schema objects.
# MAGIC
# MAGIC **Before running:** update the catalog and schema names below.

# COMMAND ----------

# TODO: Update these to match your Unity Catalog setup
CATALOG = "main"         # TODO: replace with your catalog name
SCHEMA  = "workshop_lab" # TODO: replace with or create a schema you own

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"Using: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Create sample tables representing an energy retailer's operational data
# MAGIC -- Run this cell to set up the schema the Assistant will discover

# COMMAND ----------

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# ---- NEM meter register ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.meter_register (
    nmi              STRING  COMMENT 'National Meter Identifier — unique per connection point',
    customer_id      STRING  COMMENT 'Internal customer account reference',
    tariff_code      STRING  COMMENT 'Network tariff classification (e.g. TOU, FLAT)',
    meter_type       STRING  COMMENT 'Type: SMART (interval) or BASIC (accumulation)',
    install_date     DATE    COMMENT 'Date the meter was commissioned at this address',
    last_read_date   DATE    COMMENT 'Most recent successful meter read date',
    region           STRING  COMMENT 'NEM region: NSW1, VIC1, QLD1, SA1, TAS1',
    status           STRING  COMMENT 'ACTIVE | RETIRED | DISPUTED'
)
COMMENT 'NEM meter register — one row per connection point'
""")

# ---- Interval reads ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.interval_reads (
    nmi              STRING  COMMENT 'National Meter Identifier',
    read_date        DATE    COMMENT 'Calendar date of the reading',
    interval_number  INT     COMMENT '30-minute interval number within the day (1=00:00–00:30, 48=23:30–24:00)',
    read_kwh         DOUBLE  COMMENT 'Energy consumed in the interval, kilowatt-hours',
    quality_flag     STRING  COMMENT 'A=Actual, E=Estimated, S=Substituted',
    created_at       TIMESTAMP COMMENT 'When this record was loaded into the platform'
)
COMMENT 'NEM12 interval meter reads — 30-minute granularity'
PARTITIONED BY (read_date)
""")

# ---- Asset maintenance log ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.asset_maintenance (
    asset_id         STRING  COMMENT 'Unique asset identifier (transformer, line, switch)',
    asset_type       STRING  COMMENT 'TRANSFORMER | SWITCH | CABLE | METER',
    work_order_id    STRING  COMMENT 'SAP work order reference',
    maintenance_date DATE    COMMENT 'Date maintenance was performed',
    technician_id    STRING  COMMENT 'Staff ID of the technician',
    work_type        STRING  COMMENT 'PREVENTIVE | CORRECTIVE | EMERGENCY',
    outage_duration_minutes INT COMMENT 'Planned or actual customer outage in minutes (0 if none)',
    affected_nmis    INT     COMMENT 'Number of customer connections affected',
    cost_aud         DOUBLE  COMMENT 'Total cost of work order in AUD',
    notes            STRING  COMMENT 'Free-text technician notes'
)
COMMENT 'Asset maintenance work orders — regulatory reporting source for SAIDI/SAIFI'
""")

# ---- Regulatory thresholds ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.regulatory_thresholds (
    threshold_id     STRING  COMMENT 'Unique threshold rule ID',
    region           STRING  COMMENT 'NEM region this rule applies to',
    threshold_type   STRING  COMMENT 'SAIDI | SAIFI | VOLTAGE | FREQUENCY',
    limit_value      DOUBLE  COMMENT 'Regulatory limit value',
    unit             STRING  COMMENT 'Unit: minutes/year, outages/year, V, Hz',
    effective_from   DATE    COMMENT 'Date from which this threshold is enforceable',
    regulator        STRING  COMMENT 'Regulator: AER | AEMO | ESC | QCA'
)
COMMENT 'Regulatory performance thresholds by region — sourced from AER determinations'
""")

print("Tables created successfully.")
print(f"Explore them in the Catalog: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Asking About Your Workspace
# MAGIC
# MAGIC ### Exercise 2.1 — Discover schemas via the Assistant
# MAGIC
# MAGIC With the Assistant chat panel open, try these questions:
# MAGIC
# MAGIC 1. *"What tables are in the `workshop_lab` schema?"*
# MAGIC 2. *"What columns does the `interval_reads` table have?"*
# MAGIC 3. *"Which column in `meter_register` identifies the customer's network tariff?"*
# MAGIC
# MAGIC > **How it works:** The Assistant reads Unity Catalog metadata (table names, column names,
# MAGIC > comments). This is why good column comments matter — they become the AI's context.
# MAGIC
# MAGIC ### Exercise 2.2 — Ask about relationships
# MAGIC
# MAGIC Ask the Assistant:
# MAGIC > *"In the workshop_lab schema, how would I join interval_reads to meter_register
# MAGIC > to get the tariff_code for each meter read?"*
# MAGIC
# MAGIC Does the response correctly identify `nmi` as the join key? Does it produce runnable SQL?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.3 — Run a chat-generated query
# MAGIC
# MAGIC Ask the Assistant to generate the join query from Exercise 2.2,
# MAGIC then paste the result into the cell below and run it.
# MAGIC
# MAGIC (The tables have no data yet — you're validating the SQL syntax, not the results.)

# COMMAND ----------

# TODO: Paste the SQL query generated by the Assistant here and run it.
# It should join interval_reads to meter_register on nmi.
# Expected: the query runs without error (returns 0 rows — no data loaded yet).

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Generating SQL via Chat
# MAGIC
# MAGIC The Assistant can write complex SQL when you give it enough context.
# MAGIC The key is being specific about **schema**, **intent**, and **output shape**.
# MAGIC
# MAGIC ### Exercise 3.1 — Multi-table query
# MAGIC
# MAGIC Use the chat panel to generate the following query. Copy the prompt exactly:
# MAGIC
# MAGIC > *"Write a SQL query against the tables in the workshop_lab schema.
# MAGIC > I want a daily reliability report that shows: region, maintenance_date,
# MAGIC > total outage minutes (sum of outage_duration_minutes), total affected NMIs
# MAGIC > (sum of affected_nmis), number of emergency work orders, and number of
# MAGIC > preventive work orders. Use only the asset_maintenance table.
# MAGIC > Order by region and maintenance_date."*

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO: Replace this with the SQL generated by the Assistant for Exercise 3.1
# MAGIC SELECT 'replace me' AS placeholder

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.2 — Regulatory threshold query
# MAGIC
# MAGIC Ask the Assistant:
# MAGIC > *"Using the asset_maintenance and regulatory_thresholds tables in workshop_lab,
# MAGIC > write a query that checks whether each region's annual SAIDI (total outage
# MAGIC > minutes per year) exceeds its regulatory limit. Include: region, actual_saidi_minutes,
# MAGIC > limit_minutes, and a flag column 'breach' (true/false).*
# MAGIC > *Assume the maintenance data covers exactly one calendar year."*
# MAGIC
# MAGIC After generating, identify the join condition the Assistant chose.
# MAGIC Is it correct? (Hint: `regulatory_thresholds.threshold_type = 'SAIDI'` and join on `region`)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO: Replace with the regulatory threshold breach query from the Assistant
# MAGIC SELECT 'replace me' AS placeholder

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.3 — Refining a query with follow-up prompts
# MAGIC
# MAGIC After completing Exercise 3.2, continue the conversation in the chat panel:
# MAGIC
# MAGIC 1. *"Add a column showing how many work orders contributed to the SAIDI breach."*
# MAGIC 2. *"Now filter to only show regions that are breaching."*
# MAGIC 3. *"Format the actual_saidi_minutes as a decimal rounded to 2 places."*
# MAGIC
# MAGIC Each follow-up builds on the previous response — this is the **chat context window** at work.
# MAGIC
# MAGIC > **Key insight:** The Assistant remembers the conversation history in the current session.
# MAGIC > If you close and reopen the chat, the context resets.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Context Window and Better Context
# MAGIC
# MAGIC ### What the Assistant "sees"
# MAGIC
# MAGIC | Context source | How it helps |
# MAGIC |----------------|-------------|
# MAGIC | **Open notebook cells** | The Assistant reads cell contents in the current notebook |
# MAGIC | **Unity Catalog metadata** | Table names, column names, column comments |
# MAGIC | **Your chat messages** | The conversation history in the current session |
# MAGIC | **Cells you drag into chat** | Explicit cell attachment for precise reference |
# MAGIC
# MAGIC ### Tips for better context
# MAGIC
# MAGIC 1. **Reference cell outputs** — If a cell produces a schema (`.printSchema()`), drag it into chat
# MAGIC 2. **Name your DataFrames clearly** — `df_daily_reads` is better than `df2`
# MAGIC 3. **Add column comments to tables** — They become the AI's "data dictionary"
# MAGIC 4. **Use the `@` mention** — Type `@` in the chat box to reference a specific cell
# MAGIC
# MAGIC ### Exercise 4.1 — Improve schema documentation
# MAGIC
# MAGIC Run the cell below to print the schema of `df_profile` (from Lab 01, or create it fresh).
# MAGIC Then drag the output into the chat panel and ask:
# MAGIC > *"Based on this schema, write a function that calculates the load factor
# MAGIC > for the evening_peak period."*

# COMMAND ----------

# Re-create the profile DataFrame for context demonstration
from pyspark.sql import functions as F

# Simulate a small meter DataFrame for this lab
import datetime, random
from pyspark.sql.types import *

random.seed(0)
rows = []
for day in range(7):
    d = datetime.date(2024, 7, 1) + datetime.timedelta(days=day)
    for interval in range(1, 49):
        hour = (interval - 1) / 2.0
        period = (
            "morning_peak" if 7 <= hour <= 9 else
            "evening_peak" if 17 <= hour <= 20 else
            "off_peak"     if hour >= 22 or hour <= 5 else
            "shoulder"
        )
        rows.append(("6001234567", "NSW1", period, d, round(random.uniform(0.5, 3.0), 3), interval))

schema = StructType([
    StructField("nmi",        StringType(), False),
    StructField("region",     StringType(), True),
    StructField("period",     StringType(), True),
    StructField("read_date",  DateType(),   True),
    StructField("read_kwh",   DoubleType(), True),
    StructField("interval_number", IntegerType(), True),
])

df_profile = spark.createDataFrame(rows, schema=schema)
df_profile.printSchema()

# TODO: Drag this output (the schema) into the Assistant chat and ask it to
# write a load factor function for the evening_peak period.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Chat Mode vs Agent Mode
# MAGIC
# MAGIC ### The difference in practice
# MAGIC
# MAGIC **Chat mode** answers one question at a time. It generates code but does not execute it.
# MAGIC
# MAGIC **Agent mode** can:
# MAGIC - Break a task into steps and execute them sequentially
# MAGIC - Read cells, modify code, run cells, and observe results
# MAGIC - Iterate if a step fails
# MAGIC - Use tools (search docs, run SQL, call UC functions)
# MAGIC
# MAGIC > To switch to Agent mode: in the Assistant panel, look for the mode selector
# MAGIC > (Chat / Agent toggle at the top of the panel).
# MAGIC
# MAGIC ### Exercise 5.1 — Single-step (Chat mode)
# MAGIC
# MAGIC In **Chat mode**, ask:
# MAGIC > *"Write a PySpark function that reads interval_reads from Unity Catalog,
# MAGIC > calculates SAIDI for a given region and year, and returns a single float."*
# MAGIC
# MAGIC Note: the response is a single code block. Paste it below.

# COMMAND ----------

# TODO: Paste the Chat mode response here and review it.
# Is the function complete? Does it handle edge cases (no data, null outage_duration)?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.2 — Multi-step (Agent mode)
# MAGIC
# MAGIC Switch to **Agent mode** and give it this more open-ended task:
# MAGIC
# MAGIC > *"I have a table called `asset_maintenance` in Unity Catalog.
# MAGIC > Help me: (1) understand its structure, (2) write a query that calculates
# MAGIC > SAIDI per region per year, and (3) identify any data quality issues
# MAGIC > (nulls, negative values) I should address before using this for AER reporting."*
# MAGIC
# MAGIC **Observe:** Does Agent mode produce a plan first? Does it call schema inspection tools?
# MAGIC Does it iterate or ask clarifying questions?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.3 — Comparing response quality
# MAGIC
# MAGIC Ask the **same question** in both modes and compare:
# MAGIC
# MAGIC > *"The asset_maintenance table has an `outage_duration_minutes` column.
# MAGIC > How should I handle nulls in this column when calculating SAIDI,
# MAGIC > given AER reporting requirements?"*
# MAGIC
# MAGIC | Dimension | Chat mode | Agent mode |
# MAGIC |-----------|-----------|------------|
# MAGIC | Steps in response | Single answer | May break into sub-steps |
# MAGIC | Regulatory accuracy | Generic | May look up AER rules |
# MAGIC | Code produced | Usually yes | Sometimes, after investigation |
# MAGIC | Time to response | Fast | Slower (multi-step) |
# MAGIC
# MAGIC > **When to use each:**
# MAGIC > - Chat mode: quick code generation, single-step questions
# MAGIC > - Agent mode: complex analysis, debugging workflows, tasks with unknowns

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Documentation Lookup via Chat
# MAGIC
# MAGIC The Assistant can answer questions about Databricks features without leaving the notebook.
# MAGIC
# MAGIC ### Exercise 6.1 — Ask about Databricks features
# MAGIC
# MAGIC In the chat panel, ask:
# MAGIC
# MAGIC 1. *"What is the difference between a Streaming Table and a Materialized View in Databricks?"*
# MAGIC 2. *"How do I enable Auto Loader to ingest NEM12 files from Azure Data Lake Storage?"*
# MAGIC 3. *"What does `OPTIMIZE ZORDER BY` do, and when should I use it for meter reads data?"*
# MAGIC
# MAGIC These are documentation-style questions. The Assistant pulls from Databricks docs.
# MAGIC
# MAGIC ### Exercise 6.2 — Verify an answer
# MAGIC
# MAGIC After asking question 3 above, run the cell below to test what the Assistant recommended.

# COMMAND ----------

# After asking about ZORDER, paste the OPTIMIZE command the Assistant suggested.
# Example of what it might suggest:
# OPTIMIZE <catalog>.<schema>.interval_reads ZORDER BY (nmi, read_date)
#
# Since our table has no data, this will run but affect 0 files — that's fine.

# TODO: Replace with the OPTIMIZE command the Assistant generated
# spark.sql("OPTIMIZE ...")
print("OPTIMIZE command would go here — paste from Assistant response")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Wrap-up Exercises
# MAGIC
# MAGIC ### Exercise 7.1 — Full pipeline generation
# MAGIC
# MAGIC Use the chat panel (your choice of mode) to generate a complete PySpark pipeline:
# MAGIC
# MAGIC > *"Write a Databricks notebook cell that:*
# MAGIC > *1. Reads `interval_reads` from Unity Catalog (catalog=main, schema=workshop_lab)*
# MAGIC > *2. Filters to the last 30 days*
# MAGIC > *3. Calculates total kWh per NMI*
# MAGIC > *4. Joins to `meter_register` to get the region and tariff_code*
# MAGIC > *5. Writes the result back to a new table `monthly_consumption_summary`*
# MAGIC > *Use delta format and overwrite mode."*

# COMMAND ----------

# TODO: Paste the full pipeline generated by the Assistant and review it.
# Check: Does it use the correct catalog/schema? Does the join key match? Is the filter correct?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.2 — Error analysis
# MAGIC
# MAGIC Run the cell below — it will produce an AnalysisException.
# MAGIC
# MAGIC Then ask the Assistant (in Agent mode):
# MAGIC > *"This cell is failing. Can you diagnose why and fix it?"*
# MAGIC
# MAGIC Observe whether Agent mode reads the error, the cell code, and the schema before answering.

# COMMAND ----------

# This cell has a deliberate error — use the Assistant to diagnose it
try:
    df_test = spark.table(f"{CATALOG}.{SCHEMA}.interval_reads")
    result = (
        df_test
        .join(
            spark.table(f"{CATALOG}.{SCHEMA}.meter_register"),
            on="meter_id",     # <-- BUG: column should be "nmi", not "meter_id"
            how="inner"
        )
        .select("nmi", "region", "read_date", "read_kwh")
    )
    result.show(5)
except Exception as e:
    print(f"ERROR: {type(e).__name__}")
    print(str(e)[:500])
    print("\n--- Ask the Assistant in Agent mode to fix this cell ---")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 02 Complete
# MAGIC
# MAGIC **Key takeaways:**
# MAGIC - The Assistant reads Unity Catalog metadata — good column comments improve AI responses
# MAGIC - Chat mode is fast for single-step code generation; Agent mode handles complex tasks
# MAGIC - The chat context window persists within a session — use follow-up prompts to refine
# MAGIC - Providing explicit context (schema, domain terms) dramatically improves output quality
# MAGIC
# MAGIC **Next:** Lab 03 — Adding Skills & UC Functions →
