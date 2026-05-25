# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">✨ Lab 02: Notebook AI Features & Chat</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 2a: Developer Track · Australian Regulated Industries</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | 👤 **Role** | Developer / Data Engineer / Data Scientist |
# MAGIC | ✅ **By the end** | Use the chat panel, query your catalog via Genie, switch modes, and generate complex multi-table SQL |
# MAGIC
# MAGIC ### What you'll learn
# MAGIC
# MAGIC | Topic |
# MAGIC |-------|
# MAGIC | Chat panel layout, controls, and context |
# MAGIC | Chat mode vs Agent mode — how and when to switch |
# MAGIC | Asking Genie about your Unity Catalog schema |
# MAGIC | Generating multi-table SQL via multi-turn chat |
# MAGIC | Providing better context for more accurate output |
# MAGIC | Wrap-up exercises |
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Completed Lab 01, or comfortable with basic Genie Code cell actions (Generate, Fix, Explain)
# MAGIC - Unity Catalog enabled with permission to create tables in at least one schema

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Part 0: The Chat Panel — A Complete Tour
# MAGIC
# MAGIC **Navigate:** workspace top toolbar → ✨ sparkle icon (top-right area of the page)
# MAGIC **You should see:** the Genie Code panel open with a conversation thread in the centre, text input at the bottom, and a Chat/Agent toggle at the bottom-left next to the input box.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Genie Code Panel ─────────────────────────────────────┐
# MAGIC │  + (new thread)    ⚙️ (settings → Personal instructions) │
# MAGIC │  ────────────────────────────────────────────────────    │
# MAGIC │  (conversation thread — responses appear here)           │
# MAGIC │                                                           │
# MAGIC │  ┌──────────────────────────────────────────────────┐   │
# MAGIC │  │  Ask anything...                      [Send ▶]   │   │
# MAGIC │  └──────────────────────────────────────────────────┘   │
# MAGIC │  [Chat | Agent]  ← toggle at bottom-left of panel       │
# MAGIC └───────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Panel controls:**
# MAGIC - **+ icon** at the top: start a new conversation thread
# MAGIC - **⚙️ gear icon** at the top: open Settings → "Personal instructions" text box
# MAGIC - **Chat/Agent toggle** at the bottom-left: switch between modes
# MAGIC
# MAGIC **Attaching context with @ mention:**
# MAGIC Type `@` in the input box → a dropdown lists your recent cells → select one to attach its code to your message. Useful for: *"What's wrong with @cell3?"*
# MAGIC
# MAGIC | What Genie sees | Notes |
# MAGIC |---|---|
# MAGIC | Open notebook cells | Cell code (not output unless you attach it) |
# MAGIC | Unity Catalog metadata | Table names, column names, COMMENT strings |
# MAGIC | Chat history | Full conversation in the current thread |
# MAGIC | Cells you @ mention | Explicit cell attachment for precise reference |
# MAGIC
# MAGIC > 💡 Column COMMENTs are Genie's data dictionary. Richer comments = better output. You'll see this in Section 2.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Chat Mode vs Agent Mode
# MAGIC
# MAGIC **Navigate:** Genie Code panel → bottom-left → Chat/Agent toggle
# MAGIC **You should see:** Chat highlighted by default; clicking Agent switches the active mode.
# MAGIC
# MAGIC | | Chat mode | Agent mode |
# MAGIC |---|---|---|
# MAGIC | Provider | Azure AI Services (in-region ✅) | Anthropic Claude on Databricks (in-region ✅) |
# MAGIC | Code execution | Generates only, does NOT run | Can write and execute code, iterate on errors |
# MAGIC | Response speed | ~2–5 seconds | ~15–60 seconds |
# MAGIC | Best for | Quick generation, well-defined prompts | Complex analysis, schema unknowns, multi-step debugging |
# MAGIC
# MAGIC > ⚠️ **AU East note:** Agent mode requires "Partner-powered AI features" ON in workspace settings. Switching it OFF disables Genie Code entirely.
# MAGIC
# MAGIC **Try it now (UI exercise):** open the panel, confirm Chat mode is active, ask:
# MAGIC > *"What tables would a NEM electricity retailer typically need in a Databricks lakehouse?"*
# MAGIC
# MAGIC Note the response. Switch to Agent mode and ask the same question. Compare response time, structure, and whether Agent mode shows reasoning steps before the final answer.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Setup: Create Sample Tables in Unity Catalog
# MAGIC
# MAGIC We'll create tables representing a real energy retailer's data landscape. Every column has a COMMENT — the key technique for making Genie produce accurate domain-specific queries.
# MAGIC
# MAGIC > **Before running:** update the widgets below to match your workspace.

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",      "workshop_lab",         "Schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
PT_ENDPOINT  = dbutils.widgets.get("pt_endpoint")

print(f"Using catalog: {CATALOG}.{SCHEMA}")
print(f"PT endpoint:   {PT_ENDPOINT}")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# ---- NEM meter register ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.meter_register (
    nmi              STRING  COMMENT 'National Meter Identifier — unique per connection point in the NEM',
    customer_id      STRING  COMMENT 'Internal customer account reference',
    tariff_code      STRING  COMMENT 'Network tariff classification (e.g. TOU=Time of Use, FLAT=flat rate)',
    meter_type       STRING  COMMENT 'Type: SMART (interval meter) or BASIC (accumulation meter)',
    install_date     DATE    COMMENT 'Date the meter was commissioned at this address',
    last_read_date   DATE    COMMENT 'Most recent successful meter read date',
    region           STRING  COMMENT 'NEM region: NSW1, VIC1, QLD1, SA1, TAS1',
    status           STRING  COMMENT 'ACTIVE | RETIRED | DISPUTED'
)
COMMENT 'NEM meter register — one row per connection point (NMI)'
""")

# ---- Interval reads ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.interval_reads (
    nmi              STRING    COMMENT 'National Meter Identifier — join key to meter_register',
    read_date        DATE      COMMENT 'Calendar date of the reading',
    interval_number  INT       COMMENT '30-minute interval within the day (1=00:00–00:30 ... 48=23:30–24:00)',
    read_kwh         DOUBLE    COMMENT 'Energy consumed in this 30-minute interval, kilowatt-hours',
    quality_flag     STRING    COMMENT 'A=Actual measured read, E=Estimated, S=Substituted',
    created_at       TIMESTAMP COMMENT 'Timestamp when this record was ingested into the lakehouse'
)
COMMENT 'NEM12 interval meter reads — 30-minute granularity, partitioned by read_date'
PARTITIONED BY (read_date)
""")

# ---- Asset maintenance log ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.asset_maintenance (
    asset_id                 STRING  COMMENT 'Unique asset identifier (transformer, line, switch)',
    asset_type               STRING  COMMENT 'TRANSFORMER | SWITCH | CABLE | METER',
    work_order_id            STRING  COMMENT 'SAP work order reference',
    maintenance_date         DATE    COMMENT 'Date maintenance was performed',
    technician_id            STRING  COMMENT 'Staff ID of the technician who performed the work',
    work_type                STRING  COMMENT 'PREVENTIVE | CORRECTIVE | EMERGENCY',
    outage_duration_minutes  INT     COMMENT 'Planned or actual customer outage duration in minutes (0 if no outage)',
    affected_nmis            INT     COMMENT 'Number of customer connection points (NMIs) affected by this outage',
    cost_aud                 DOUBLE  COMMENT 'Total cost of the work order in Australian dollars',
    notes                    STRING  COMMENT 'Free-text technician notes',
    region                   STRING  COMMENT 'NEM region: NSW1, VIC1, QLD1, SA1, TAS1'
)
COMMENT 'Asset maintenance work orders — primary source for AER SAIDI/SAIFI regulatory reporting'
""")

# ---- Regulatory thresholds ----
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.regulatory_thresholds (
    threshold_id   STRING  COMMENT 'Unique threshold rule identifier',
    region         STRING  COMMENT 'NEM region this threshold applies to (NSW1, VIC1, etc.)',
    threshold_type STRING  COMMENT 'SAIDI | SAIFI | VOLTAGE | FREQUENCY — performance measure type',
    limit_value    DOUBLE  COMMENT 'Regulatory limit value — performance must stay below this',
    unit           STRING  COMMENT 'Unit of measurement: minutes/year, outages/year, V, or Hz',
    effective_from DATE    COMMENT 'Date from which this threshold became enforceable',
    regulator      STRING  COMMENT 'Responsible regulator: AER | AEMO | ESC | QCA'
)
COMMENT 'Regulatory performance thresholds by region — sourced from AER distribution determinations'
""")

print("Tables created successfully.")
print(f"\nExplore them in the Catalog Explorer: {CATALOG}.{SCHEMA}")
print("You should see: meter_register, interval_reads, asset_maintenance, regulatory_thresholds")

# COMMAND ----------

# MAGIC %md
# MAGIC **Navigate:** left sidebar → Catalog icon (stack-of-discs) → your catalog → workshop_lab → Tables
# MAGIC **You should see:** all 4 tables listed; click any table → Schema tab to confirm COMMENT text appears next to each column name.
# MAGIC
# MAGIC > Those column comments in the Catalog Explorer are exactly what Genie reads when you ask questions about your data. Writing good comments at table creation time is the single highest-impact technique for improving Genie output quality.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Asking Genie About Your Unity Catalog Schema
# MAGIC
# MAGIC The Genie chat panel looks up your actual tables and columns in Unity Catalog — not a generic guess, but your real metadata.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.1 — Schema discovery via chat
# MAGIC
# MAGIC **Navigate:** workspace top toolbar → ✨ sparkle icon → confirm **Chat** mode is active at the bottom-left of the panel.
# MAGIC **You should see:** an empty conversation thread ready for your prompt.
# MAGIC
# MAGIC Ask these three questions one at a time, reading each response before moving on:
# MAGIC
# MAGIC **Question 1:**
# MAGIC > *"What tables are in the workshop_lab schema?"*
# MAGIC
# MAGIC Does Genie list all 4 tables and describe what each is for?
# MAGIC
# MAGIC **Question 2:**
# MAGIC > *"What columns does the interval_reads table have?"*
# MAGIC
# MAGIC Does it include column types and the descriptions from the COMMENTs?
# MAGIC
# MAGIC **Question 3:**
# MAGIC > *"Which column in meter_register identifies the customer's network tariff?"*
# MAGIC
# MAGIC Does it correctly answer `tariff_code` and quote the COMMENT text?
# MAGIC
# MAGIC > 💡 If Genie says it can't find the table, provide the full path: *"In catalog `main`, schema `workshop_lab`, what columns does interval_reads have?"*

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.2 — Ask about join relationships and run the result
# MAGIC
# MAGIC Still in Chat mode, ask:
# MAGIC > *"In the workshop_lab schema, how would I join interval_reads to meter_register to get the tariff_code for each meter read? Write the SQL."*
# MAGIC
# MAGIC Check: does it identify `nmi` as the join key? When the code block appears, click **"Insert into notebook"** to add it as a new cell, then run it.

# COMMAND ----------

# TODO: Paste the SQL query generated by the Assistant here and run it.
# It should join interval_reads to meter_register on nmi.
# Expected: query runs without error (returns 0 rows — no data loaded yet).

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Generating SQL via Multi-Turn Chat
# MAGIC
# MAGIC Specific prompts — naming the schema, describing business intent, and stating the expected output shape — produce much more accurate multi-table SQL than vague requests.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.1 — Daily reliability report
# MAGIC
# MAGIC Use Chat mode. Copy this prompt exactly:
# MAGIC
# MAGIC > *"Write a SQL query against the tables in the workshop_lab schema. I want a daily reliability report that shows: region, maintenance_date, total outage minutes (sum of outage_duration_minutes), total affected NMIs (sum of affected_nmis), number of emergency work orders, and number of preventive work orders. Use only the asset_maintenance table. Order by region and maintenance_date."*
# MAGIC
# MAGIC Click **"Insert into notebook"**, paste into the SQL cell below, and run it.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO: Replace with the SQL generated by the Assistant for Exercise 3.1
# MAGIC -- If running in a customer environment, replace main.workshop_lab with your CATALOG.SCHEMA values from the widget above
# MAGIC SELECT 'replace me' AS placeholder

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.2 — Regulatory threshold breach query
# MAGIC
# MAGIC Ask the Assistant:
# MAGIC > *"Using the asset_maintenance and regulatory_thresholds tables in workshop_lab, write a query that checks whether each region's annual SAIDI (total outage minutes per year) exceeds its regulatory limit. Include: region, actual_saidi_minutes, limit_minutes, and a flag column 'breach' (true/false). Assume the maintenance data covers exactly one calendar year."*
# MAGIC
# MAGIC After generating, check: does the join include `AND rt.threshold_type = 'SAIDI'`? Without it the query joins to all threshold types and inflates results.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO: Replace with the regulatory threshold breach query from the Assistant
# MAGIC -- If running in a customer environment, replace main.workshop_lab with your CATALOG.SCHEMA values from the widget above
# MAGIC SELECT 'replace me' AS placeholder

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.3 — Refining with follow-up prompts (multi-turn)
# MAGIC
# MAGIC **Continue the same chat thread from Exercise 3.2** — do NOT click + for a new thread. The query context must persist.
# MAGIC
# MAGIC Send these follow-ups one at a time, waiting for each response:
# MAGIC
# MAGIC **Follow-up 1:** *"Add a column showing how many individual work orders contributed to the SAIDI total."*
# MAGIC
# MAGIC **Follow-up 2:** *"Now filter to only show regions that are currently breaching the limit."*
# MAGIC
# MAGIC **Follow-up 3:** *"Format actual_saidi_minutes and limit_minutes rounded to 2 decimal places."*
# MAGIC
# MAGIC > If Genie gives a generic response that doesn't reference your previous query, the thread context was lost — paste the query from 3.2 and ask again.

# COMMAND ----------

# TODO: After follow-up 3, paste the final refined query here and run it.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Providing Better Context
# MAGIC
# MAGIC Genie's output quality scales directly with the quality of context you provide.
# MAGIC
# MAGIC | Technique | Example |
# MAGIC |---|---|
# MAGIC | Name DataFrames clearly | `df_daily_reads` not `df2` |
# MAGIC | Add column COMMENTs to tables | `COMMENT 'A=Actual, E=Estimated'` |
# MAGIC | Use the `@` mention for cells | `@cell3 — what's wrong with this?` |
# MAGIC | Provide units and value ranges | `"interval_number ranges from 1 to 48"` |
# MAGIC | State what to avoid | `"no UDFs, use window functions"` |
# MAGIC | Describe business intent | `"this is for AER SAIDI compliance reporting"` |

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.1 — Attach schema as context with @ mention
# MAGIC
# MAGIC Run the cell below to print a schema, then use it as context.
# MAGIC
# MAGIC **Navigate:** Genie Code panel → text input → type `@` → select this cell from the dropdown
# MAGIC **You should see:** the cell attached as a context card in your message.
# MAGIC
# MAGIC Ask:
# MAGIC > *"Based on this schema, write a PySpark function that calculates the load factor for the evening_peak period. Load factor = average_kwh / max_kwh for that period."*

# COMMAND ----------

from pyspark.sql import functions as F
import datetime, random
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, DateType, IntegerType
)

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
    StructField("nmi",             StringType(),  False),
    StructField("region",          StringType(),  True),
    StructField("period",          StringType(),  True),
    StructField("read_date",       DateType(),    True),
    StructField("read_kwh",        DoubleType(),  True),
    StructField("interval_number", IntegerType(), True),
])

df_profile = spark.createDataFrame(rows, schema=schema)
df_profile.printSchema()
# Attach this cell with @ in the chat panel, then ask for a load factor function

# COMMAND ----------

# TODO: Paste the function generated by Genie (after attaching the schema) and run it.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Chat Mode vs Agent Mode in Practice
# MAGIC
# MAGIC **Navigate:** Genie Code panel → bottom-left → Chat/Agent toggle
# MAGIC **You should see:** the active mode highlighted; switch by clicking the other option.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.1 — Single-step task in Chat mode
# MAGIC
# MAGIC Switch to **Chat mode**. Ask:
# MAGIC > *"Write a PySpark function that reads interval_reads from Unity Catalog (catalog=main, schema=workshop_lab), calculates SAIDI for a given region and calendar year, and returns a single float value. Handle the case where there is no data for that region and year."*
# MAGIC
# MAGIC Note the response characteristics: single code block, no plan shown, no schema lookup, arrives in ~2–5 seconds.

# COMMAND ----------

# TODO: Paste the Chat mode response here and review it.
# Check: correct catalog/schema path, null/empty case handled, correct column name (outage_duration_minutes)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.2 — Multi-step task in Agent mode
# MAGIC
# MAGIC Switch to **Agent mode**. Give it this open-ended task:
# MAGIC > *"I have a table called `asset_maintenance` in Unity Catalog (main.workshop_lab). Help me: (1) understand its structure, (2) write a query that calculates SAIDI per region per year, and (3) identify any data quality issues (nulls, negative values) I should address before using this for AER reporting."*
# MAGIC
# MAGIC While it runs, observe: does Agent mode show a plan before executing? Does it call schema inspection tools (DESCRIBE TABLE)? Does it produce separate output for each sub-task?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.3 — Same question, both modes
# MAGIC
# MAGIC Ask in **Chat mode**, note the response, switch to **Agent mode**, ask the exact same question:
# MAGIC > *"The asset_maintenance table has an `outage_duration_minutes` column. How should I handle nulls in this column when calculating SAIDI, given AER reporting requirements?"*
# MAGIC
# MAGIC | Dimension | Chat mode | Agent mode |
# MAGIC |---|---|---|
# MAGIC | Response time (seconds) | ___ | ___ |
# MAGIC | References column COMMENT? | Yes / No | Yes / No |
# MAGIC | Mentions specific AER rules? | Yes / No | Yes / No |
# MAGIC | Produces runnable code? | Yes / No | Yes / No |
# MAGIC | Shows reasoning steps? | Yes / No | Yes / No |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Documentation Lookup via Chat

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 6.1 — Ask about Databricks features
# MAGIC
# MAGIC In Chat mode, ask each of the following:
# MAGIC
# MAGIC **Question 1:**
# MAGIC > *"What is the difference between a Streaming Table and a Materialized View in Databricks?"*
# MAGIC
# MAGIC **Question 2:**
# MAGIC > *"How do I enable Auto Loader to ingest NEM12 files from Azure Data Lake Storage?"*
# MAGIC
# MAGIC **Question 3:**
# MAGIC > *"What does `OPTIMIZE ZORDER BY` do, and when should I use it for interval meter reads data?"*
# MAGIC
# MAGIC For Question 3, look for Genie to recommend clustering on `nmi` and `read_date` — the most common filter and join columns for NEM meter data access patterns.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 6.2 — Verify the OPTIMIZE recommendation
# MAGIC
# MAGIC After Question 3 above, paste the OPTIMIZE command the Assistant suggested into the cell below and run it. The table has no data, so it will succeed but affect 0 files — that is the expected result.

# COMMAND ----------

# TODO: Paste the OPTIMIZE command the Assistant generated.
# Example form:
#   spark.sql("OPTIMIZE main.workshop_lab.interval_reads ZORDER BY (nmi, read_date)")
print("OPTIMIZE command would go here — paste from the Assistant response")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 7 — Wrap-up Exercises
# MAGIC
# MAGIC Work through these using Genie Code. Your choice of Chat or Agent mode.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.1 — Full pipeline generation
# MAGIC
# MAGIC Use the chat panel to generate a complete PySpark pipeline. Try Chat mode first, then Agent mode, and compare output quality.
# MAGIC
# MAGIC **Prompt:**
# MAGIC > *"Write a Databricks notebook cell that: (1) reads `interval_reads` from Unity Catalog (catalog=main, schema=workshop_lab), (2) filters to the last 30 days based on read_date, (3) calculates total kWh per NMI, (4) joins to `meter_register` to get the region and tariff_code (join on nmi), (5) writes the result back to a new table `monthly_consumption_summary` in the same catalog and schema, using delta format and overwrite mode."*
# MAGIC
# MAGIC After generating, review for: correct catalog/schema paths in reads and write, correct join key (`nmi`), correct date filter, delta format and overwrite mode.

# COMMAND ----------

# TODO: Paste the full pipeline generated by the Assistant.
# Check: catalog/schema paths, join key, date filter, write format and mode.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.2 — Error analysis with Agent mode
# MAGIC
# MAGIC Run the cell below — it produces an AnalysisException.
# MAGIC
# MAGIC **Navigate:** workspace top toolbar → ✨ sparkle icon → Genie Code panel → switch to **Agent mode** at the bottom-left toggle.
# MAGIC **You should see:** Agent mode active; type the prompt and observe it show reasoning steps.
# MAGIC
# MAGIC Ask: *"This cell is failing. Can you diagnose why and fix it?"*
# MAGIC
# MAGIC Observe whether Agent mode: reads the error, runs DESCRIBE TABLE on both tables, identifies that `meter_id` is not a valid column (correct key is `nmi`), and references the column COMMENT to confirm.

# COMMAND ----------

# This cell has a deliberate error — use Agent mode to diagnose and fix it
try:
    df_test = spark.table(f"{CATALOG}.{SCHEMA}.interval_reads")
    result = (
        df_test
        .join(
            spark.table(f"{CATALOG}.{SCHEMA}.meter_register"),
            on="meter_id",     # <-- BUG: should be "nmi", not "meter_id"
            how="inner"
        )
        .select("nmi", "region", "read_date", "read_kwh")
    )
    result.show(5)
except Exception as e:
    print(f"ERROR: {type(e).__name__}")
    print(str(e)[:500])
    print("\n--- Ask the Assistant in Agent mode to fix this cell ---")
    print("Prompt: 'This cell is failing. Can you diagnose why and fix it?'")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 02 Complete
# MAGIC
# MAGIC <div style="background: #1B3139; padding: 16px; border-radius: 6px; border-left: 4px solid #FF6B35">
# MAGIC   <p style="color: #FFFFFF; margin: 0 0 8px 0; font-weight: bold">Key takeaways</p>
# MAGIC   <ul style="color: #AECBCC; margin: 0">
# MAGIC     <li>Open the Genie Code panel via the ✨ sparkle icon in the workspace top toolbar (top-right of the page)</li>
# MAGIC     <li>Chat/Agent toggle is at the bottom-left of the panel, next to the text input</li>
# MAGIC     <li>Start a new thread with the + icon at the top; open Settings with the ⚙️ gear icon → Personal instructions</li>
# MAGIC     <li>Column COMMENTs on Unity Catalog tables are Genie Code's data dictionary — the richer the comments, the better the output</li>
# MAGIC     <li>Use @ mention to attach specific cells as context; chat history persists within a thread</li>
# MAGIC     <li>Agent mode actively inspects your schema before generating — slower but more accurate on unfamiliar tables</li>
# MAGIC     <li>All Genie Code completions (both modes) run in-region for Australia East</li>
# MAGIC   </ul>
# MAGIC </div>
# MAGIC
# MAGIC **Next:** Lab 03 — Adding Skills & UC Functions →
