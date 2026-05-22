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
# MAGIC | ⏱️ **Duration** | 45 minutes |
# MAGIC | 👤 **Role** | Developer / Data Engineer / Data Scientist |
# MAGIC | ✅ **By the end** | You'll be able to use the chat panel, query your catalog via Genie, switch modes, and generate complex multi-table SQL |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What you'll learn
# MAGIC
# MAGIC | Topic | Time |
# MAGIC |-------|------|
# MAGIC | The Chat panel: layout, controls, and context | 5 min |
# MAGIC | Chat mode vs Agent mode — how and when to switch | 10 min |
# MAGIC | Asking Genie about your Unity Catalog schema | 10 min |
# MAGIC | Generating multi-table SQL via chat | 10 min |
# MAGIC | Context window and providing better context | 5 min |
# MAGIC | Wrap-up exercises | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Prerequisites
# MAGIC
# MAGIC - Completed Lab 01, or comfortable with basic Genie Code cell actions (Generate, Fix, Explain)
# MAGIC - Unity Catalog enabled with permission to create tables in at least one schema

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🖱️ Part 0: The Chat Panel — A Complete Tour
# MAGIC
# MAGIC The Genie chat panel is the most powerful access point for Genie Code.
# MAGIC Before running any code, spend 3 minutes getting comfortable with what you're looking at.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Opening the panel
# MAGIC
# MAGIC ```
# MAGIC Three ways to open:
# MAGIC
# MAGIC   1. Click the ✨ sparkle icon in the RIGHT SIDEBAR
# MAGIC      (the narrow strip of icons on the far right edge of the Databricks UI)
# MAGIC
# MAGIC   2. Keyboard shortcut (opens Genie Code inline in a cell):
# MAGIC      Mac:            Cmd+I
# MAGIC      Windows/Linux:  Ctrl+I
# MAGIC
# MAGIC   Or click the ✨ sparkle icon in the **top-right corner** of the workspace
# MAGIC   (not the cell — it's in the main workspace toolbar)
# MAGIC
# MAGIC   3. Command palette — search "Assistant"
# MAGIC      Mac:            Cmd+Shift+P  then type "Assistant" and press Enter
# MAGIC      Windows/Linux:  Ctrl+Shift+P then type "Assistant" and press Enter
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Panel layout
# MAGIC
# MAGIC ```
# MAGIC ┌─── Genie Panel ──────────────────────────────────────────────┐
# MAGIC │                                                              │
# MAGIC │  ✨ Genie Code                          [Chat ●] [Agent ○]  │  ← mode toggle
# MAGIC │  ────────────────────────────────────────────────────────   │
# MAGIC │                                                              │
# MAGIC │  ┌──────────────────────────────────────────────────────┐   │
# MAGIC │  │  (conversation history appears here)                  │   │
# MAGIC │  │                                                        │   │
# MAGIC │  │  Genie:  Hello! I can help you with code, queries,    │   │
# MAGIC │  │          and questions about your data.               │   │
# MAGIC │  └──────────────────────────────────────────────────────┘   │
# MAGIC │                                                              │
# MAGIC │  ┌──────────────────────────────────────────────────────┐   │
# MAGIC │  │  @ Ask anything...                        [Send ▶]   │   │  ← input box
# MAGIC │  └──────────────────────────────────────────────────────┘   │
# MAGIC │                                                              │
# MAGIC │  [Clear conversation]                                        │  ← resets context
# MAGIC └──────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### The @ mention and cell attachment
# MAGIC
# MAGIC ```
# MAGIC Inside the chat input box, type @  to reference specific cells:
# MAGIC
# MAGIC   ┌──────────────────────────────────────────────────────────┐
# MAGIC   │  @                                                        │
# MAGIC   └──────────────────────────────────────────────────────────┘
# MAGIC        ↓
# MAGIC   ┌─── Dropdown ───────────────────────────────┐
# MAGIC   │  📄 Cell 1: from pyspark.sql import ...    │  ← select a cell to attach it
# MAGIC   │  📄 Cell 2: df_meters = spark.create...    │
# MAGIC   │  📄 Cell 3: df_profile = (df_meters...     │
# MAGIC   └────────────────────────────────────────────┘
# MAGIC
# MAGIC Selecting a cell attaches its code to your message — Genie sees the exact text.
# MAGIC Useful for: "What's wrong with @cell3?" or "Optimise @cell2 for large scale."
# MAGIC
# MAGIC You can also drag a cell's output section directly into the chat input box.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What Genie "sees" from your notebook
# MAGIC
# MAGIC | Context source | Notes |
# MAGIC |----------------|-------|
# MAGIC | **Open notebook cells** | Genie reads cell code (not output unless you attach it) |
# MAGIC | **Unity Catalog metadata** | Table names, column names, column COMMENT strings |
# MAGIC | **Your chat messages** | The full conversation history in the current session |
# MAGIC | **Cells you @ mention** | Explicit cell attachment for precise reference |
# MAGIC | **Workspace files** | In Agent mode, Genie can browse your workspace files |
# MAGIC
# MAGIC > 💡 **Column COMMENTs are your data dictionary.** When you write
# MAGIC > `COMMENT 'explanation'` on each column at table creation time, Genie reads those
# MAGIC > comments and produces much more accurate code. You'll see this in Section 3.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 💬 Chat Mode vs 🤖 Agent Mode
# MAGIC
# MAGIC Genie Code has two modes with different strengths.
# MAGIC You switch between them with the toggle at the top of the Genie panel.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Visual guide to switching modes
# MAGIC
# MAGIC ```
# MAGIC Default: Chat mode active
# MAGIC
# MAGIC   ✨ Genie Code                          [Chat ●] [Agent ○]
# MAGIC                                               ↑        ↑
# MAGIC                                            active   inactive
# MAGIC
# MAGIC Click [Agent] to switch:
# MAGIC
# MAGIC   ✨ Genie Code                          [Chat ○] [Agent ●]
# MAGIC                                               ↑        ↑
# MAGIC                                            inactive  active
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Comparison table
# MAGIC
# MAGIC | | Chat mode | Agent mode |
# MAGIC |---|---|---|
# MAGIC | **What it does** | Answers one question at a time | Plans, executes steps, iterates |
# MAGIC | **Code execution** | Generates code, does NOT run it | Can run cells and observe results |
# MAGIC | **Schema lookup** | Uses UC metadata it has indexed | Can actively browse and query UC |
# MAGIC | **Response speed** | Fast (~2–5 seconds) | Slower (~15–60 seconds) |
# MAGIC | **Best for** | Quick code generation, snippets | Complex analysis, unknowns, debugging |
# MAGIC | **Provider** | Azure AI Services (in-region ✅) | Anthropic Claude (in-region ✅) |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### When to use each
# MAGIC
# MAGIC ```
# MAGIC Use Chat mode when:
# MAGIC   ✓ You know exactly what you want
# MAGIC     (e.g. "write a filter for quality_flag = 'A'")
# MAGIC   ✓ You need a quick code snippet
# MAGIC   ✓ You're asking a single well-defined question
# MAGIC   ✓ You want the fastest possible response
# MAGIC
# MAGIC Use Agent mode when:
# MAGIC   ✓ You're not sure what's wrong ("why is this failing?")
# MAGIC   ✓ The task has multiple unknowns
# MAGIC     (e.g. "analyse this table and tell me what's odd")
# MAGIC   ✓ You want Genie to look up your actual schema before generating code
# MAGIC   ✓ You have a multi-step task
# MAGIC     (e.g. "understand, fix, and test this pipeline")
# MAGIC   ✓ You want Genie to iterate on errors automatically
# MAGIC ```
# MAGIC
# MAGIC > 💡 **Rule of thumb:** Start with Chat mode for speed. Switch to Agent mode when
# MAGIC > Chat mode gives you generic or incorrect answers.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🧪 Try it now — Mode comparison (UI exercise, no code required)
# MAGIC
# MAGIC Before running any cells, try the same question in both modes and observe the difference.
# MAGIC
# MAGIC **Step 1 — Open the Genie panel**
# MAGIC - Press `Cmd+I` (Mac) or `Ctrl+I` (Windows), or click the ✨ sparkle icon in the **top-right corner** of the workspace toolbar
# MAGIC
# MAGIC **Step 2 — Confirm Chat mode is active** (the toggle should show [Chat ●])
# MAGIC
# MAGIC **Step 3 — Ask in Chat mode:**
# MAGIC > *"What tables would a NEM electricity retailer typically need in a Databricks lakehouse?"*
# MAGIC
# MAGIC Note the response style: a single structured answer, no reasoning steps shown.
# MAGIC
# MAGIC **Step 4 — Switch to Agent mode** (click the [Agent] toggle)
# MAGIC
# MAGIC **Step 5 — Ask the same question in Agent mode:**
# MAGIC > *"What tables would a NEM electricity retailer typically need in a Databricks lakehouse?"*
# MAGIC
# MAGIC **Observe the differences:**
# MAGIC - Does Agent mode show a plan or steps before the final answer?
# MAGIC - Does it try to look up anything in your workspace?
# MAGIC - Is the response more or less structured?
# MAGIC - How does the response time compare?
# MAGIC
# MAGIC ✅ There's no right answer here — this is about experiencing the difference directly.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🔧 Section 1 — Setup: Create Sample Tables in Unity Catalog
# MAGIC
# MAGIC We'll create tables representing a real energy retailer's data landscape.
# MAGIC Each column has a COMMENT — this is the key technique for making Genie Code
# MAGIC produce accurate domain-specific queries.
# MAGIC
# MAGIC > **Before running:** update `CATALOG` and `SCHEMA` to match your workspace.

# COMMAND ----------

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Workshop Configuration
# MAGIC > **Running in a customer environment?** Change the catalog name in the widget above to match
# MAGIC > what was set in `setup/00_workspace_setup.py` (default: `workshop_au`)

# COMMAND ----------
# Widget-based configuration — works in any customer Databricks environment
# These default values match what 00_workspace_setup.py creates
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
print(f"Using: {CATALOG}.{SCHEMA}")

# COMMAND ----------

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
    notes                    STRING  COMMENT 'Free-text technician notes'
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
# MAGIC ### ✅ Expected output after setup
# MAGIC
# MAGIC ```
# MAGIC Tables created successfully.
# MAGIC
# MAGIC Explore them in the Catalog Explorer: main.workshop_lab
# MAGIC You should see: meter_register, interval_reads, asset_maintenance, regulatory_thresholds
# MAGIC ```
# MAGIC
# MAGIC **Verify in the Catalog Explorer (UI exercise):**
# MAGIC
# MAGIC ```
# MAGIC 1. Click the Catalog icon in the LEFT SIDEBAR
# MAGIC    (stack-of-discs icon, usually the third icon from the top)
# MAGIC
# MAGIC 2. Navigate: your_catalog → workshop_lab → Tables
# MAGIC    You should see all 4 tables listed
# MAGIC
# MAGIC 3. Click any table → go to the "Schema" tab
# MAGIC    Confirm the COMMENT text appears next to each column name
# MAGIC
# MAGIC 4. Note how column descriptions appear as tooltips — this is what Genie reads
# MAGIC ```
# MAGIC
# MAGIC > 💡 Those column comments you see in the Catalog Explorer are exactly what Genie Code
# MAGIC > reads when you ask questions about your data. Richer comments = better AI responses.
# MAGIC > This is the single highest-impact thing you can do to improve Genie output quality.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🔍 Section 2 — Asking Genie About Your Unity Catalog Schema
# MAGIC
# MAGIC The Genie chat panel can look up your actual tables and columns in Unity Catalog.
# MAGIC This is different from generic code generation — Genie is reading your real metadata.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### How Genie accesses the Catalog Explorer from chat
# MAGIC
# MAGIC ```
# MAGIC When you ask about a table in the chat panel, Genie:
# MAGIC
# MAGIC   1. Searches Unity Catalog for tables matching your description
# MAGIC      (by name, by schema, or by column content if you describe it)
# MAGIC
# MAGIC   2. Reads the table schema: column names, types, and COMMENT strings
# MAGIC
# MAGIC   3. Uses that metadata to write accurate queries — correct column names,
# MAGIC      correct join keys, correct filter conditions
# MAGIC
# MAGIC In Agent mode, Genie goes further:
# MAGIC   - Runs DESCRIBE TABLE or SHOW COLUMNS to inspect metadata dynamically
# MAGIC   - Can run SELECT * LIMIT 5 to understand actual data content
# MAGIC   - Shows you the schema lookup steps in its visible reasoning output
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Exercise 2.1 — Schema discovery via chat (UI exercise, no code)
# MAGIC
# MAGIC Open the Genie panel in **Chat mode** and ask these questions one at a time.
# MAGIC After each response, note whether Genie referenced the COMMENT text you wrote.
# MAGIC
# MAGIC **Question 1:**
# MAGIC > *"What tables are in the workshop_lab schema?"*
# MAGIC
# MAGIC Does Genie list all 4 tables? Does it describe what each table is for?
# MAGIC
# MAGIC **Question 2:**
# MAGIC > *"What columns does the interval_reads table have?"*
# MAGIC
# MAGIC Does it include the column types and the descriptions from the COMMENTs?
# MAGIC
# MAGIC **Question 3:**
# MAGIC > *"Which column in meter_register identifies the customer's network tariff?"*
# MAGIC
# MAGIC Does it correctly answer `tariff_code`? Does it quote the COMMENT text?
# MAGIC
# MAGIC > 💡 **If Genie says it can't find the table**, try giving the full path:
# MAGIC > *"In catalog `main`, schema `workshop_lab`, what columns does interval_reads have?"*

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What good schema discovery responses look like
# MAGIC
# MAGIC **Question 1 response (expected):**
# MAGIC ```
# MAGIC The workshop_lab schema contains 4 tables:
# MAGIC
# MAGIC   1. meter_register — NEM meter register, one row per connection point (NMI)
# MAGIC   2. interval_reads — NEM12 interval meter reads at 30-minute granularity
# MAGIC   3. asset_maintenance — Asset maintenance work orders for AER SAIDI/SAIFI reporting
# MAGIC   4. regulatory_thresholds — Regulatory performance thresholds by NEM region
# MAGIC ```
# MAGIC
# MAGIC **Question 2 response (expected):**
# MAGIC ```
# MAGIC interval_reads has these columns:
# MAGIC
# MAGIC   nmi             STRING     National Meter Identifier — join key to meter_register
# MAGIC   read_date       DATE       Calendar date of the reading
# MAGIC   interval_number INT        30-minute interval within the day (1=00:00–00:30 ... 48=23:30–24:00)
# MAGIC   read_kwh        DOUBLE     Energy consumed in this 30-minute interval, kilowatt-hours
# MAGIC   quality_flag    STRING     A=Actual measured read, E=Estimated, S=Substituted
# MAGIC   created_at      TIMESTAMP  Timestamp when this record was ingested into the lakehouse
# MAGIC ```
# MAGIC
# MAGIC **Question 3 response (expected):**
# MAGIC ```
# MAGIC The tariff_code column in meter_register identifies the network tariff.
# MAGIC Its description is: "Network tariff classification (e.g. TOU=Time of Use, FLAT=flat rate)"
# MAGIC ```
# MAGIC
# MAGIC > Notice how the COMMENT you wrote on each column appears verbatim in the response.
# MAGIC > This demonstrates why column documentation is the single most impactful technique
# MAGIC > for improving Genie Code quality on domain-specific data.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.2 — Ask about join relationships (UI exercise, no code)
# MAGIC
# MAGIC Still in **Chat mode**, ask:
# MAGIC > *"In the workshop_lab schema, how would I join interval_reads to meter_register
# MAGIC > to get the tariff_code for each meter read?"*
# MAGIC
# MAGIC Evaluate the response against these criteria:
# MAGIC - Does it correctly identify `nmi` as the join key?
# MAGIC - Does it produce SQL (not just a written description)?
# MAGIC - Does it reference the column COMMENT to justify why `nmi` is the join key?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 2.3 — Run a chat-generated query
# MAGIC
# MAGIC Ask Genie to generate the join query from Exercise 2.2.
# MAGIC When the code block appears in the chat panel, click **"Insert into notebook"**
# MAGIC to add it as a new cell — OR paste it into the cell below manually.
# MAGIC
# MAGIC The tables have no data yet — you're validating SQL syntax, not results.

# COMMAND ----------

# TODO: Paste the SQL query generated by the Assistant here and run it.
# It should join interval_reads to meter_register on nmi.
# Expected: the query runs without error (returns 0 rows — no data loaded yet).

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What the generated SQL should look like
# MAGIC
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     i.nmi,
# MAGIC     i.read_date,
# MAGIC     i.interval_number,
# MAGIC     i.read_kwh,
# MAGIC     i.quality_flag,
# MAGIC     m.tariff_code,
# MAGIC     m.region
# MAGIC FROM main.workshop_lab.interval_reads AS i
# MAGIC INNER JOIN main.workshop_lab.meter_register AS m
# MAGIC     ON i.nmi = m.nmi
# MAGIC ORDER BY i.nmi, i.read_date, i.interval_number
# MAGIC ```
# MAGIC
# MAGIC **Check:** Does it use `i.nmi = m.nmi` as the join condition?
# MAGIC If Genie used `meter_id` or another column, the COMMENT didn't propagate correctly —
# MAGIC try re-asking with the full table path (`main.workshop_lab.interval_reads`).

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 📝 Section 3 — Generating SQL via Chat
# MAGIC
# MAGIC The Genie chat panel can write complex multi-table SQL when given enough context.
# MAGIC The key is being specific about schema name, business intent, and expected output shape.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Exercise 3.1 — Multi-table aggregation query
# MAGIC
# MAGIC Use the chat panel in **Chat mode** to generate the query below.
# MAGIC Copy this prompt exactly (the specificity is intentional):
# MAGIC
# MAGIC > *"Write a SQL query against the tables in the workshop_lab schema.
# MAGIC > I want a daily reliability report that shows: region, maintenance_date,
# MAGIC > total outage minutes (sum of outage_duration_minutes), total affected NMIs
# MAGIC > (sum of affected_nmis), number of emergency work orders, and number of
# MAGIC > preventive work orders. Use only the asset_maintenance table.
# MAGIC > Order by region and maintenance_date."*
# MAGIC
# MAGIC When the code block appears, click **"Insert into notebook"**, then replace the
# MAGIC placeholder in the SQL cell below and run it.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO: Replace this with the SQL generated by the Assistant for Exercise 3.1
# MAGIC -- TODO: if running in customer env, replace main.workshop_lab with your catalog.schema (use CATALOG/SCHEMA variables from widget above)
# MAGIC SELECT 'replace me' AS placeholder

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What the generated query should look like — Exercise 3.1
# MAGIC
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     region,
# MAGIC     maintenance_date,
# MAGIC     SUM(outage_duration_minutes)                           AS total_outage_minutes,
# MAGIC     SUM(affected_nmis)                                     AS total_affected_nmis,
# MAGIC     COUNT(CASE WHEN work_type = 'EMERGENCY'   THEN 1 END)  AS emergency_work_orders,
# MAGIC     COUNT(CASE WHEN work_type = 'PREVENTIVE'  THEN 1 END)  AS preventive_work_orders
# MAGIC FROM main.workshop_lab.asset_maintenance
# MAGIC GROUP BY region, maintenance_date
# MAGIC ORDER BY region, maintenance_date
# MAGIC ```
# MAGIC
# MAGIC **Check:** Does it reference the correct catalog/schema path?
# MAGIC Does it use the actual column names from the table (not invented ones)?
# MAGIC The table is empty so 0 rows is expected — a successful run with 0 rows is the goal.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.2 — Regulatory threshold query
# MAGIC
# MAGIC Ask the Assistant:
# MAGIC > *"Using the asset_maintenance and regulatory_thresholds tables in workshop_lab,
# MAGIC > write a query that checks whether each region's annual SAIDI (total outage
# MAGIC > minutes per year) exceeds its regulatory limit. Include: region,
# MAGIC > actual_saidi_minutes, limit_minutes, and a flag column 'breach' (true/false).
# MAGIC > Assume the maintenance data covers exactly one calendar year."*
# MAGIC
# MAGIC After generating, examine the join condition Genie chose.
# MAGIC Is it correct? (It should join on `region` AND filter `threshold_type = 'SAIDI'`.)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- TODO: Replace with the regulatory threshold breach query from the Assistant
# MAGIC -- TODO: if running in customer env, replace main.workshop_lab with your catalog.schema (use CATALOG/SCHEMA variables from widget above)
# MAGIC SELECT 'replace me' AS placeholder

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What the regulatory breach query should look like
# MAGIC
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     am.region,
# MAGIC     SUM(am.outage_duration_minutes)         AS actual_saidi_minutes,
# MAGIC     rt.limit_value                          AS limit_minutes,
# MAGIC     CASE
# MAGIC         WHEN SUM(am.outage_duration_minutes) > rt.limit_value THEN TRUE
# MAGIC         ELSE FALSE
# MAGIC     END                                     AS breach
# MAGIC FROM main.workshop_lab.asset_maintenance AS am
# MAGIC JOIN main.workshop_lab.regulatory_thresholds AS rt
# MAGIC     ON am.region = rt.region
# MAGIC    AND rt.threshold_type = 'SAIDI'
# MAGIC GROUP BY am.region, rt.limit_value
# MAGIC ORDER BY am.region
# MAGIC ```
# MAGIC
# MAGIC **Key check:** Does the join include `AND rt.threshold_type = 'SAIDI'`?
# MAGIC Without this, the query joins to all threshold types (SAIFI, VOLTAGE, FREQUENCY too)
# MAGIC and produces a cartesian-style inflation of the results.
# MAGIC
# MAGIC If Genie omitted the threshold_type filter, follow up in the chat:
# MAGIC > *"The regulatory_thresholds table has multiple rows per region — SAIDI, SAIFI,
# MAGIC > and VOLTAGE. Add a filter to only join on SAIDI rows."*

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.3 — Refining with follow-up prompts (multi-turn)
# MAGIC
# MAGIC After completing Exercise 3.2, **continue the conversation in the same chat session**
# MAGIC (do NOT click "Clear conversation" — the context of the previous query must persist).
# MAGIC
# MAGIC Send these follow-ups one at a time, waiting for each response before sending the next:
# MAGIC
# MAGIC **Follow-up 1:**
# MAGIC > *"Add a column showing how many individual work orders contributed to the SAIDI total."*
# MAGIC
# MAGIC **Follow-up 2:**
# MAGIC > *"Now filter to only show regions that are currently breaching the limit."*
# MAGIC
# MAGIC **Follow-up 3:**
# MAGIC > *"Format the actual_saidi_minutes and limit_minutes values rounded to 2 decimal places."*
# MAGIC
# MAGIC Each follow-up builds on the previous response — this is the **chat context window** at work.
# MAGIC Genie remembers the query it wrote and modifies it incrementally.
# MAGIC
# MAGIC > ⚠️ **If Genie gives a generic response** that doesn't reference your previous query,
# MAGIC > the context was lost (panel was closed and reopened, or "Clear" was clicked).
# MAGIC > In that case, paste the query from Exercise 3.2 into the chat and ask again.

# COMMAND ----------

# TODO: After follow-up 3, paste the final refined query here and run it.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What the final refined query should look like
# MAGIC
# MAGIC ```sql
# MAGIC SELECT
# MAGIC     am.region,
# MAGIC     ROUND(SUM(am.outage_duration_minutes), 2)    AS actual_saidi_minutes,
# MAGIC     ROUND(rt.limit_value, 2)                     AS limit_minutes,
# MAGIC     COUNT(am.work_order_id)                      AS work_order_count,
# MAGIC     TRUE                                         AS breach
# MAGIC FROM main.workshop_lab.asset_maintenance AS am
# MAGIC JOIN main.workshop_lab.regulatory_thresholds AS rt
# MAGIC     ON am.region = rt.region
# MAGIC    AND rt.threshold_type = 'SAIDI'
# MAGIC GROUP BY am.region, rt.limit_value
# MAGIC HAVING SUM(am.outage_duration_minutes) > rt.limit_value
# MAGIC ORDER BY actual_saidi_minutes DESC
# MAGIC ```
# MAGIC
# MAGIC The table is empty, so the query returns 0 rows — that's expected.
# MAGIC The goal here is producing correct SQL through multi-turn refinement, not data output.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🧠 Section 4 — Context Window and Providing Better Context
# MAGIC
# MAGIC The quality of Genie's output depends heavily on the quality of context you provide.
# MAGIC These techniques make the biggest practical difference.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What good context looks like
# MAGIC
# MAGIC ```
# MAGIC ❌ Poor context:
# MAGIC    "Write a query to calculate SAIDI"
# MAGIC
# MAGIC    Genie doesn't know your table names, column names, or what SAIDI
# MAGIC    means in your specific regulatory context.
# MAGIC
# MAGIC ✅ Good context:
# MAGIC    "Using the asset_maintenance table in main.workshop_lab (columns:
# MAGIC     region, maintenance_date, outage_duration_minutes as minutes per
# MAGIC     outage event, affected_nmis as number of customers affected),
# MAGIC     calculate annual SAIDI per region. SAIDI = sum of outage_duration_minutes
# MAGIC     per region for the year. I don't have a total_nmis_in_region column —
# MAGIC     use 1000 as a placeholder."
# MAGIC
# MAGIC    Genie has everything it needs: table, columns, formula, and an explicit
# MAGIC    decision about the missing data point.
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Tips for better context
# MAGIC
# MAGIC | Technique | Example |
# MAGIC |-----------|---------|
# MAGIC | Name DataFrames clearly | `df_daily_reads` not `df2` |
# MAGIC | Add column COMMENTs to tables | `COMMENT 'A=Actual, E=Estimated'` |
# MAGIC | Use the `@` mention for cells | `@cell3 — what's wrong with this?` |
# MAGIC | Provide units and value ranges | `"interval_number ranges from 1 to 48"` |
# MAGIC | State what to avoid | `"no UDFs, use window functions"` |
# MAGIC | Describe business intent | `"this is for AER SAIDI compliance reporting"` |

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 4.1 — Improve schema documentation impact
# MAGIC
# MAGIC Run the cell below to print the schema of a profile DataFrame.
# MAGIC Then use the schema output as context in the chat panel.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Run the cell to produce `.printSchema()` output
# MAGIC 2. Open the Genie panel
# MAGIC 3. In the chat input, type `@` and select this cell from the dropdown
# MAGIC    (OR copy-paste the schema text into your message)
# MAGIC 4. Ask:
# MAGIC    > *"Based on this schema, write a PySpark function that calculates the
# MAGIC    > load factor for the evening_peak period.
# MAGIC    > Load factor = average_kwh / max_kwh for that period."*

# COMMAND ----------

# Re-create a profile DataFrame for context demonstration
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

# Use this schema output as context — attach with @ mention or copy-paste into chat

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What a good load factor function response looks like
# MAGIC
# MAGIC After attaching the schema as context, Genie should produce something like:
# MAGIC
# MAGIC ```python
# MAGIC from pyspark.sql import functions as F
# MAGIC
# MAGIC def evening_peak_load_factor(df):
# MAGIC     """
# MAGIC     Calculate the load factor for the evening_peak demand period.
# MAGIC
# MAGIC     Load factor = average_kwh / max_kwh for the evening_peak period,
# MAGIC     grouped by NMI. A value close to 1.0 means flat demand; lower
# MAGIC     values indicate sharp demand spikes during the peak window.
# MAGIC
# MAGIC     Args:
# MAGIC         df: Spark DataFrame with columns: nmi, period, read_kwh
# MAGIC
# MAGIC     Returns:
# MAGIC         Spark DataFrame with: nmi, avg_kwh, max_kwh, load_factor
# MAGIC     """
# MAGIC     return (
# MAGIC         df
# MAGIC         .filter(F.col("period") == "evening_peak")
# MAGIC         .groupBy("nmi")
# MAGIC         .agg(
# MAGIC             F.avg("read_kwh").alias("avg_kwh"),
# MAGIC             F.max("read_kwh").alias("max_kwh")
# MAGIC         )
# MAGIC         .withColumn("load_factor", F.round(F.col("avg_kwh") / F.col("max_kwh"), 4))
# MAGIC     )
# MAGIC
# MAGIC evening_peak_load_factor(df_profile).show()
# MAGIC ```
# MAGIC
# MAGIC **Key check:** Does the function filter to `period == "evening_peak"` specifically?
# MAGIC Does it use `read_kwh` (the actual column name from the schema you attached)?
# MAGIC This accuracy comes from attaching the schema — without it, Genie might guess `kwh`
# MAGIC or `energy_kwh` and produce code that fails on first run.

# COMMAND ----------

# TODO: Paste the function generated by Genie (after attaching the schema) and run it.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🤖 Section 5 — Chat Mode vs Agent Mode in Practice
# MAGIC
# MAGIC This section compares the two modes on real tasks.
# MAGIC You'll run similar requests in both modes and compare quality.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Exercise 5.1 — Single-step task in Chat mode
# MAGIC
# MAGIC Switch to **Chat mode** (click [Chat] toggle in the Genie panel).
# MAGIC
# MAGIC Ask:
# MAGIC > *"Write a PySpark function that reads interval_reads from Unity Catalog
# MAGIC > (catalog=main, schema=workshop_lab), calculates SAIDI for a given region
# MAGIC > and calendar year, and returns a single float value.
# MAGIC > Handle the case where there is no data for that region and year."*
# MAGIC
# MAGIC Note the characteristics of the response:
# MAGIC - A single code block with no plan shown
# MAGIC - Generates code but does NOT run it
# MAGIC - Response arrives in ~2–5 seconds
# MAGIC
# MAGIC Paste the response into the cell below.

# COMMAND ----------

# TODO: Paste the Chat mode response here and review it.
# Check:
#   - Does it use the correct catalog/schema path (main.workshop_lab)?
#   - Does it handle the null/empty case (no data for that region/year)?
#   - Does it use the correct column name (outage_duration_minutes)?

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What a good Chat mode SAIDI function looks like
# MAGIC
# MAGIC ```python
# MAGIC from pyspark.sql import functions as F
# MAGIC
# MAGIC def calculate_saidi(region: str, year: int) -> float:
# MAGIC     """
# MAGIC     Calculate SAIDI (System Average Interruption Duration Index) for a
# MAGIC     given NEM region and calendar year.
# MAGIC
# MAGIC     SAIDI = total outage minutes across all events in the region for the year.
# MAGIC     Returns 0.0 if no data exists for the region/year combination.
# MAGIC     """
# MAGIC     df = spark.table("main.workshop_lab.asset_maintenance")
# MAGIC
# MAGIC     result = (
# MAGIC         df
# MAGIC         .filter(
# MAGIC             (F.col("region") == region) &
# MAGIC             (F.year("maintenance_date") == year)
# MAGIC         )
# MAGIC         .agg(F.sum("outage_duration_minutes").alias("total_saidi"))
# MAGIC         .collect()
# MAGIC     )
# MAGIC
# MAGIC     value = result[0]["total_saidi"]
# MAGIC     return float(value) if value is not None else 0.0
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.2 — Multi-step task in Agent mode
# MAGIC
# MAGIC Switch to **Agent mode** (click [Agent] toggle).
# MAGIC
# MAGIC Give it this more open-ended task:
# MAGIC > *"I have a table called `asset_maintenance` in Unity Catalog (main.workshop_lab).
# MAGIC > Help me: (1) understand its structure, (2) write a query that calculates
# MAGIC > SAIDI per region per year, and (3) identify any data quality issues
# MAGIC > (nulls, negative values) I should address before using this for AER reporting."*
# MAGIC
# MAGIC **While it runs, observe:**
# MAGIC - Does Agent mode show a plan before executing?
# MAGIC - Does it call any schema inspection tools (DESCRIBE TABLE)?
# MAGIC - Does it produce separate output for each of the 3 sub-tasks?
# MAGIC - Does it ask you clarifying questions?

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What a good Agent mode response looks like
# MAGIC
# MAGIC Agent mode typically shows reasoning steps before giving the final answer:
# MAGIC
# MAGIC ```
# MAGIC Genie (Agent mode):
# MAGIC
# MAGIC   Step 1 — Understanding the table structure
# MAGIC   ──────────────────────────────────────────
# MAGIC   Running: DESCRIBE TABLE main.workshop_lab.asset_maintenance
# MAGIC
# MAGIC   Result: [schema shown — 10 columns]
# MAGIC
# MAGIC   Key columns for SAIDI calculation:
# MAGIC     outage_duration_minutes — minutes per outage event
# MAGIC     affected_nmis           — number of customers affected
# MAGIC     region                  — NEM region
# MAGIC     maintenance_date        — when the outage occurred
# MAGIC
# MAGIC   Step 2 — SAIDI query
# MAGIC   ─────────────────────
# MAGIC   [generates SQL query using the exact column names from DESCRIBE output]
# MAGIC
# MAGIC   Step 3 — Data quality checks
# MAGIC   ─────────────────────────────
# MAGIC   For AER reporting I'd check:
# MAGIC   1. NULLs in outage_duration_minutes — would silently undercount SAIDI
# MAGIC   2. Negative values in outage_duration_minutes — physically impossible
# MAGIC   3. Duplicate work_order_ids — would double-count the same outage event
# MAGIC   4. Work orders with NULL region — excluded from regional reporting
# MAGIC
# MAGIC   Here are PySpark checks for each: [generates data quality code]
# MAGIC ```
# MAGIC
# MAGIC Compare to Chat mode: Agent mode is slower but broke the task into 3 explicit parts,
# MAGIC showed its schema lookup, and produced actionable quality checks without being asked
# MAGIC explicitly for them.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 5.3 — Same question, both modes (comparison exercise)
# MAGIC
# MAGIC Ask this question in **Chat mode**, note the response, then switch to **Agent mode**
# MAGIC and ask the exact same question. Fill in the comparison table after both responses.
# MAGIC
# MAGIC > *"The asset_maintenance table has an `outage_duration_minutes` column.
# MAGIC > How should I handle nulls in this column when calculating SAIDI,
# MAGIC > given AER reporting requirements?"*
# MAGIC
# MAGIC | Dimension | Chat mode | Agent mode |
# MAGIC |-----------|-----------|------------|
# MAGIC | Response time (seconds) | ___ | ___ |
# MAGIC | References column COMMENT? | Yes / No | Yes / No |
# MAGIC | Mentions specific AER rules? | Yes / No | Yes / No |
# MAGIC | Produces runnable code? | Yes / No | Yes / No |
# MAGIC | Shows reasoning steps? | Yes / No | Yes / No |
# MAGIC
# MAGIC > **Discussion point:** Neither mode is universally better. Chat mode is ~10x faster
# MAGIC > for well-defined prompts. Agent mode adds value when the problem has unknowns or
# MAGIC > requires multi-step reasoning about your actual schema. Pick the right tool for the task.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 📖 Section 6 — Documentation Lookup via Chat
# MAGIC
# MAGIC Genie Code can answer questions about Databricks features without leaving the notebook.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Exercise 6.1 — Ask about Databricks features (UI exercise, no code)
# MAGIC
# MAGIC In the chat panel in **Chat mode**, ask each of these questions:
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
# MAGIC For Question 3, look for Genie to recommend clustering on `nmi` and `read_date` —
# MAGIC the most common filter and join columns for meter data access patterns.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What a good ZORDER response looks like
# MAGIC
# MAGIC ```
# MAGIC OPTIMIZE ZORDER BY co-locates records with similar values in the specified
# MAGIC columns on disk, enabling Delta Lake to skip entire Parquet files when you
# MAGIC filter on those columns (data skipping).
# MAGIC
# MAGIC For interval meter reads data, I'd recommend:
# MAGIC
# MAGIC   OPTIMIZE main.workshop_lab.interval_reads
# MAGIC   ZORDER BY (nmi, read_date);
# MAGIC
# MAGIC Why nmi and read_date:
# MAGIC   - nmi: queries almost always filter to a specific meter or small set of meters
# MAGIC   - read_date: nearly all queries have a date range filter
# MAGIC
# MAGIC Combined ZORDER means that retrieving all reads for a single NMI over a date range
# MAGIC (the most common NEM billing access pattern) reads the minimum number of files.
# MAGIC
# MAGIC Note: the table is also partitioned by read_date (as you defined in the schema).
# MAGIC Partitioning handles coarse file elimination; ZORDER handles fine-grained skipping
# MAGIC within each partition. Both complement each other.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 6.2 — Verify the OPTIMIZE recommendation
# MAGIC
# MAGIC After asking about ZORDER (Question 3 above), paste the OPTIMIZE command
# MAGIC the Assistant suggested into the cell below and run it.
# MAGIC
# MAGIC Since the table has no data, the command succeeds but affects 0 files — that's correct.
# MAGIC The goal is confirming the syntax is valid and the command runs without error.

# COMMAND ----------

# After asking about ZORDER, paste the OPTIMIZE command the Assistant suggested.
# Since the table has no data, this will run but affect 0 files — that's expected.

# TODO: Replace with the OPTIMIZE command the Assistant generated.
# Example form:
#   spark.sql("OPTIMIZE main.workshop_lab.interval_reads ZORDER BY (nmi, read_date)")
print("OPTIMIZE command would go here — paste from the Assistant response")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🏋️ Section 7 — Wrap-up Exercises
# MAGIC
# MAGIC Work through these using Genie Code. Your choice of Chat or Agent mode.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.1 — Full pipeline generation
# MAGIC
# MAGIC Use the chat panel to generate a complete PySpark pipeline.
# MAGIC Try Chat mode first, then Agent mode, and compare the output quality.
# MAGIC
# MAGIC **Prompt:**
# MAGIC > *"Write a Databricks notebook cell that:*
# MAGIC > *1. Reads `interval_reads` from Unity Catalog (catalog=main, schema=workshop_lab)*
# MAGIC > *2. Filters to the last 30 days based on read_date*
# MAGIC > *3. Calculates total kWh per NMI*
# MAGIC > *4. Joins to `meter_register` to get the region and tariff_code (join on nmi)*
# MAGIC > *5. Writes the result back to a new table `monthly_consumption_summary`*
# MAGIC >    *in the same catalog and schema, using delta format and overwrite mode."*
# MAGIC
# MAGIC After generating, review the code for:
# MAGIC - Correct catalog/schema paths in both the reads and the write
# MAGIC - Correct join key (`nmi`)
# MAGIC - Correct date filter expression (`read_date >= current_date - 30`)
# MAGIC - Delta format and overwrite mode on the write

# COMMAND ----------

# TODO: Paste the full pipeline generated by the Assistant.
# Check: catalog/schema paths, join key, date filter, write format and mode.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ What the pipeline should look like
# MAGIC
# MAGIC ```python
# MAGIC from pyspark.sql import functions as F
# MAGIC
# MAGIC # Read and filter to last 30 days
# MAGIC df_reads = (
# MAGIC     spark.table("main.workshop_lab.interval_reads")
# MAGIC     .filter(F.col("read_date") >= F.date_sub(F.current_date(), 30))
# MAGIC )
# MAGIC
# MAGIC # Aggregate to total kWh per NMI
# MAGIC df_totals = (
# MAGIC     df_reads
# MAGIC     .groupBy("nmi")
# MAGIC     .agg(F.sum("read_kwh").alias("total_kwh"))
# MAGIC )
# MAGIC
# MAGIC # Join to meter_register for region and tariff_code
# MAGIC df_meter = spark.table("main.workshop_lab.meter_register")
# MAGIC
# MAGIC df_result = (
# MAGIC     df_totals
# MAGIC     .join(df_meter.select("nmi", "region", "tariff_code"), on="nmi", how="inner")
# MAGIC )
# MAGIC
# MAGIC # Write to summary table
# MAGIC (
# MAGIC     df_result
# MAGIC     .write
# MAGIC     .format("delta")
# MAGIC     .mode("overwrite")
# MAGIC     .saveAsTable("main.workshop_lab.monthly_consumption_summary")
# MAGIC )
# MAGIC
# MAGIC print("Pipeline complete. Rows written:", df_result.count())
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 7.2 — Error analysis with Agent mode
# MAGIC
# MAGIC Run the cell below — it produces an AnalysisException.
# MAGIC
# MAGIC Switch to **Agent mode** and ask:
# MAGIC > *"This cell is failing. Can you diagnose why and fix it?"*
# MAGIC
# MAGIC **Observe whether Agent mode:**
# MAGIC 1. Reads the error message from the cell output
# MAGIC 2. Runs DESCRIBE TABLE on both tables before proposing a fix
# MAGIC 3. Identifies that `meter_id` is not a column in either table (the correct key is `nmi`)
# MAGIC 4. References the column COMMENT on `nmi` to confirm the correct join key

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
# MAGIC ### ✅ What a good Agent mode diagnosis looks like
# MAGIC
# MAGIC ```
# MAGIC Genie (Agent mode):
# MAGIC
# MAGIC   I see the error: AnalysisException — Resolved attribute(s) meter_id missing
# MAGIC   from interval_reads, meter_register.
# MAGIC
# MAGIC   Let me inspect both table schemas to find the correct join key.
# MAGIC
# MAGIC   Running: DESCRIBE TABLE main.workshop_lab.interval_reads
# MAGIC   Running: DESCRIBE TABLE main.workshop_lab.meter_register
# MAGIC
# MAGIC   Found the issue: neither table has a column called "meter_id".
# MAGIC
# MAGIC   The correct join key is "nmi" — it appears in both tables.
# MAGIC   The column COMMENT on interval_reads.nmi confirms it:
# MAGIC   "National Meter Identifier — join key to meter_register"
# MAGIC
# MAGIC   Fix:
# MAGIC     Change: on="meter_id"
# MAGIC     To:     on="nmi"
# MAGIC
# MAGIC   Corrected cell: [shows the full corrected code block]
# MAGIC ```
# MAGIC
# MAGIC **Key takeaway:** Agent mode read the error, actively queried both schemas, and
# MAGIC used the column COMMENT to confirm the correct join key. This is why (a) Agent mode
# MAGIC is the right choice for debugging tasks with schema ambiguity, and (b) writing good
# MAGIC column COMMENTs at table creation time pays dividends throughout the data lifecycle.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 02 Complete
# MAGIC
# MAGIC <div style="background: #1B3139; padding: 16px; border-radius: 6px; border-left: 4px solid #FF6B35">
# MAGIC   <p style="color: #FFFFFF; margin: 0 0 8px 0; font-weight: bold">Key takeaways</p>
# MAGIC   <ul style="color: #AECBCC; margin: 0">
# MAGIC     <li>The chat panel has a mode toggle — [Chat] for fast single-step tasks, [Agent] for complex multi-step work</li>
# MAGIC     <li>Column COMMENTs on Unity Catalog tables are Genie Code's data dictionary — the richer the comments, the better the output</li>
# MAGIC     <li>The @ mention lets you attach specific cells as context in the chat input box</li>
# MAGIC     <li>Chat context persists within a session — use follow-up prompts to refine instead of rewriting from scratch</li>
# MAGIC     <li>Agent mode actively inspects your schema before generating — it's slower but more accurate on unfamiliar tables</li>
# MAGIC     <li>All Genie Code completions (both modes) run in-region for Australia East</li>
# MAGIC   </ul>
# MAGIC </div>
# MAGIC
# MAGIC **Next:** Lab 03 — Adding Skills & UC Functions →
