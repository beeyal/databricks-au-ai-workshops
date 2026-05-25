# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 36px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 03: Custom Instructions, Skills &amp; UC Function Tools
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">
# MAGIC     Workshop: Genie Code for Developers — Australian Regulated Industries
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>60 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01 and 02 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All execution: AU East
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Three concepts — clearly distinct
# MAGIC
# MAGIC | Concept | What it is | When it activates | Where it lives |
# MAGIC |---------|-----------|-------------------|----------------|
# MAGIC | **Custom Instructions** | Plain text injected into every conversation as the system prompt | Always — every session automatically | `.assistant_instructions.md` in your user folder or workspace |
# MAGIC | **Skills** | Markdown documents Genie Code loads when relevant | On demand — query match or `@skill-name` | `Workspace/.assistant/skills/<name>/SKILL.md` or your user folder |
# MAGIC | **Tools (UC Functions)** | Executable Python/SQL code registered in Unity Catalog | When the agent decides to call it — real code runs | Unity Catalog: `catalog.schema.function_name` |
# MAGIC
# MAGIC | Section | Topic | Time |
# MAGIC |---------|-------|------|
# MAGIC | 1 | Custom Instructions | 15 min |
# MAGIC | 2 | Skills | 15 min |
# MAGIC | 3 | UC Functions as Tools | 20 min |
# MAGIC | 4 | Skills + Tools together | 10 min |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

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
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 1 — Custom Instructions: Persistent Domain Knowledge
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Custom instructions are plain text loaded into every Genie Code conversation as the system prompt.
# MAGIC Without them, Genie has no awareness that `NMI` means National Metering Identifier, that `quality_flag = "A"` means Actual, or that outputs should use DD/MM/YYYY for AER reports.
# MAGIC
# MAGIC **Storage locations:**
# MAGIC
# MAGIC | Level | Path | Visible to |
# MAGIC |-------|------|-----------|
# MAGIC | Personal | `/Users/{email}/.assistant_instructions.md` | You only |
# MAGIC | Workspace | `Workspace/.assistant_workspace_instructions.md` | All users (admin only) |
# MAGIC | Project | `AGENTS.md` in any directory — Genie walks up from current notebook | That directory tree |
# MAGIC
# MAGIC Limit: 20,000 characters total across all loaded instruction files.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Create personal instructions

# COMMAND ----------

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
| SAIDI | System Average Interruption Duration Index — lower is better (mins/customer/year) |
| SAIFI | System Average Interruption Frequency Index — interruptions per customer per year |

## Data tables I work with

- `interval_reads`: 30-minute NEM12 interval data. Key columns: nmi, read_date, interval_number (1-48), read_kwh, quality_flag
- `outage_events`: SAIDI/SAIFI events. Key columns: event_id, asset_id, start_ts, duration_minutes, affected_customers, cause_category
- `energy_assets`: Network assets. Key columns: asset_id, asset_type, region, installation_date, rated_kva
- `asset_maintenance`: Work orders. Key columns: asset_id, maintenance_date, work_type, technician_id, outage_duration_minutes, cost_aud

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
- Peak demand window: 07:00-09:00 and 17:00-20:00 AEST

## Coding preferences

- Always use Delta Lake format for output tables
- Use Australian date format DD/MM/YYYY in comments and print statements
- Variable names: snake_case, domain-specific (e.g., `nmi`, `saidi_minutes`)
- Error handling: return structured JSON errors, never raise bare exceptions in UC functions
- Imports: put all imports at the top of functions (required inside UC LANGUAGE PYTHON blocks)
"""

dbutils.fs.put(instructions_path, instructions, overwrite=True)
print(f"Instructions written to: {instructions_path}")
print("Restart the Genie Code panel (close and reopen the sparkle icon) to pick these up.")

# COMMAND ----------

# MAGIC %md
# MAGIC Navigate: Genie Code panel → gear ⚙️ icon → "Personal instructions"
# MAGIC You should see: a preview of the instructions content you just wrote.
# MAGIC
# MAGIC Test: ask Genie Code "What does SAIDI stand for?" — it should reference energy regulatory context, not telecommunications.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Workspace-wide instructions (admin only — skip if not admin)

# COMMAND ----------

# ADMIN ONLY — uncomment if you have workspace admin rights
# workspace_instructions = """# Workspace: Energy Network Operations
#
# This workspace is used by the network operations data team.
# All notebooks work with Australian NEM (National Electricity Market) data.
# Default catalog: workshop_au, default schema: workshop_lab
# Date format: DD/MM/YYYY. NMI format: 10 digits, VIC prefix 61, NSW prefix 41.
# """
#
# dbutils.fs.put(
#     "dbfs:/Workspace/.assistant_workspace_instructions.md",
#     workspace_instructions,
#     overwrite=True
# )
# print("Workspace-wide instructions written.")

print("Workspace instructions cell — uncomment if you are an admin. Skipping.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Create an AGENTS.md for project-level context
# MAGIC
# MAGIC Genie Code Agent mode walks up the directory tree from your current notebook looking for `AGENTS.md` (same convention as Claude Code's `CLAUDE.md`).
# MAGIC Use it for table names, NMIs, and project-specific details — keep global instructions for terminology.

# COMMAND ----------

notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
notebook_dir  = "/".join(notebook_path.split("/")[:-1])
agents_md_path = f"/Workspace{notebook_dir}/AGENTS.md"

agents_md_content = """# Energy Workshop — Project Context for Genie Code

## Active tables (workshop_au.workshop_lab)

| Table | Description |
|-------|-------------|
| interval_reads | 30-min NEM12 interval data for workshop NMIs |
| asset_maintenance | YTD work orders for network assets |

## NMIs used in this workshop

| NMI | Description |
|-----|-------------|
| 6001234567 | Residential VIC, standard consumption profile |
| 6009999001 | Commercial NSW, large load, solar export enabled |

## Assets used in this workshop

| Asset ID | Type | Region |
|----------|------|--------|
| TF-NSW-001 | Zone substation transformer | NSW |
| CB-VIC-042 | 11kV circuit breaker | VIC |

## Rules

- Peak demand filter: quality_flag IN ('A', 'S') — exclude E and N
- SAIDI events: join outage_events on asset_id, aggregate duration_minutes * affected_customers
- 48 intervals = one complete day (30-min cadence)
- Do not modify tables directly — use the workshop UC functions instead.
"""

import os
os.makedirs(f"/Workspace{notebook_dir}", exist_ok=True)
with open(agents_md_path, "w") as f:
    f.write(agents_md_content)

print(f"AGENTS.md written to: {agents_md_path}")
print(f"Auto-discovered for all notebooks under: {notebook_dir}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 2 — Skills: On-Demand Knowledge Documents
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Skills are Markdown documents stored in a fixed path that Genie Code loads on demand.
# MAGIC Unlike custom instructions (always in context), skills are lazy-loaded — fetched only when the query matches the `description` frontmatter field, or when you type `@skill-name`.
# MAGIC
# MAGIC **Paths:**
# MAGIC - Personal: `/Users/{username}/.assistant/skills/{name}/SKILL.md`
# MAGIC - Workspace: `Workspace/.assistant/skills/{name}/SKILL.md`
# MAGIC
# MAGIC Every `SKILL.md` requires YAML frontmatter with `name` and `description`. The `description` field is what Genie reads to decide whether to auto-load the skill — write it as a list of trigger phrases, not a title.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Create an energy operations skill

# COMMAND ----------

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

If more than 5% of daily intervals are flagged E or N, mandatory customer notification is required under NERR.

## SAIDI Calculation

```python
saidi = (
    outage_events_df
    .groupBy("network_id")
    .agg(
        (F.sum(F.col("duration_minutes") * F.col("affected_customers"))
         / F.first("total_customers")).alias("saidi_minutes")
    )
)
```

## SAIFI Calculation

```python
saifi = (
    outage_events_df
    .groupBy("network_id")
    .agg(
        (F.count("event_id") * F.first("affected_customers")
         / F.first("total_customers")).alias("saifi_count")
    )
)
```

Momentary interruptions (< 1 minute) are excluded from SAIFI under most AER frameworks.

## Interval Data Calculations

```python
# Daily consumption — sum all 48 intervals (values are kWh per 30 min, not rates)
daily_kwh = interval_reads_df.groupBy("nmi", "read_date").agg(F.sum("read_kwh"))

# Peak demand — highest single 30-minute interval during peak window
peak_demand = (
    interval_reads_df
    .filter(F.col("quality_flag").isin(["A", "S"]))
    .filter(
        ((F.col("interval_number") >= 15) & (F.col("interval_number") <= 18)) |  # 07:00-09:00
        ((F.col("interval_number") >= 35) & (F.col("interval_number") <= 40))    # 17:00-20:00
    )
    .groupBy("nmi", "read_date")
    .agg(F.max("read_kwh").alias("peak_half_hour_kwh"))
)
# Convert interval number to time: (interval_number - 1) * 30 minutes from midnight
```

## NMI Format Reference

| State | Prefix | Example |
|-------|--------|---------|
| VIC | 61 | 6100123456 |
| NSW | 41 | 4100123456 |
| QLD | 31 | 3100123456 |
| SA | 20 | 2000123456 |

NMIs are always 10 characters, numeric only.
"""

dbutils.fs.put(f"{skill_dir}/SKILL.md", skill_content, overwrite=True)
print(f"Skill created: {skill_dir}/SKILL.md")
print("Invoke with: @energy-operations")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Create a NEM12 file format skill

# COMMAND ----------

username = spark.sql("SELECT current_user()").collect()[0][0]
nem12_skill_dir = f"/Users/{username}/.assistant/skills/nem12-format"
dbutils.fs.mkdirs(nem12_skill_dir)

nem12_skill_content = """---
name: nem12-format
description: NEM12 raw file format specification — record types 100/200/300/400/500/900, field positions, and how to parse or validate NEM12 files submitted to AEMO
---

# NEM12 File Format Reference

## Record Types

| Record | Purpose | Key fields |
|--------|---------|-----------|
| 100 | Header — one per file | Version (NEM12), DateTime, FromParticipant, ToParticipant |
| 200 | NMI data details — one per NMI | NMI, NMISuffix, RegisterID, UOM, IntervalLength |
| 300 | Interval data — one per day per NMI | IntervalDate (YYYYMMDD), then 48 interval values |
| 400 | Interval event — data quality info | StartInterval, EndInterval, QualityMethod, ReasonCode |
| 900 | End of file — one per file | (no additional fields) |

## Record 300 Structure

```
300,20240701,0.123,0.134,...(48 values)...,A,20240702123456,
```
Fields: record type, interval date (YYYYMMDD), 48 interval energy values (kWh), quality method, update datetime.

## Parsing NEM12 with PySpark

```python
raw_df = spark.read.text("/path/to/file.nem12")

record_300 = (
    raw_df
    .filter(F.col("value").startswith("300,"))
    .withColumn("fields", F.split(F.col("value"), ","))
    .withColumn("interval_date", F.to_date(F.col("fields")[1], "yyyyMMdd"))
    .select(
        F.col("interval_date"),
        *[F.col("fields")[i + 2].cast("double").alias(f"interval_{i+1:02d}")
          for i in range(48)],
        F.col("fields")[50].alias("quality_method"),
    )
)
```

## Common Validation Rules

1. Record 100 must be the first row; record 900 must be the last
2. Each NMI block must start with a 200 record before any 300 records
3. IntervalLength in record 200 must be 30 (NEM12 — NEM13 uses 5-minute intervals)
4. Energy values must be >= 0 (negative values indicate solar export)
5. Files must be submitted within 5 business days of the metering data date
"""

dbutils.fs.put(f"{nem12_skill_dir}/SKILL.md", nem12_skill_content, overwrite=True)
print(f"NEM12 format skill created: {nem12_skill_dir}/SKILL.md")
print("Invoke with: @nem12-format")

# COMMAND ----------

# MAGIC %md
# MAGIC Navigate: Genie Code panel → type `@` in the chat input
# MAGIC You should see: a dropdown listing `energy-operations` and `nem12-format` with their descriptions.
# MAGIC
# MAGIC Test: type `@energy-operations what is the SAIDI formula?` — Genie should explain it using your exact column names and table structure.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #00843D; color: white; padding: 14px 20px; border-radius: 8px; margin: 24px 0;">
# MAGIC   <strong>Checkpoint — Sections 1 and 2</strong><br>
# MAGIC   Confirm before continuing:<br>
# MAGIC   ✓ Personal instructions at /Users/{username}/.assistant_instructions.md<br>
# MAGIC   ✓ AGENTS.md in the notebook directory<br>
# MAGIC   ✓ Two skills: @energy-operations and @nem12-format<br>
# MAGIC   ✓ Skills appear in the @ dropdown in Genie Code
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 3 — UC Functions as Tools: Executable Agent Capabilities
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC Tools are **executable functions** registered in Unity Catalog. When an agent calls a tool, Databricks runs the Python/SQL code inside your workspace and returns the result as a string.
# MAGIC Skills give static reference knowledge — tools give live data. Tool invocations are tracked in `system.access.audit`.
# MAGIC
# MAGIC **Naming convention:** dots become double underscores in tool names:
# MAGIC `catalog.schema.function_name` → `catalog__schema__function_name`
# MAGIC
# MAGIC **EXECUTE grant:** before an agent can call a function, the running identity needs:
# MAGIC ```sql
# MAGIC GRANT EXECUTE ON FUNCTION catalog.schema.function_name TO `user@company.com`;
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC Navigate: Left sidebar → Catalog icon → workshop_au → workshop_lab → Functions
# MAGIC You should see: the Functions section (currently empty — will have 3 after the next cells).

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Register Function 1: `calculate_peak_demand`

# COMMAND ----------

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

# MAGIC %md
# MAGIC ### 3.2 — Register Function 2: `get_meter_readings_summary`

# COMMAND ----------

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
        return json.dumps({
            "error": f"No reads found for NMI {nmi} on {read_date}."
        })

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

# MAGIC %md
# MAGIC ### 3.3 — Register Function 3: `lookup_asset_status`

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.lookup_asset_status(
    asset_id STRING COMMENT 'The unique asset identifier to look up (e.g., TF-NSW-001, CB-VIC-042)'
)
RETURNS STRING
COMMENT 'Look up the year-to-date maintenance history and operational status of a network asset.
Returns JSON with: asset_id, asset_type, last_maintenance_date, last_work_type, last_technician,
total_work_orders_ytd, total_outage_minutes_ytd, total_affected_nmis_ytd, total_cost_aud_ytd.
Use this tool when asked about an asset maintenance history, outage record, YTD cost,
condition assessment, or when investigating what maintenance has been done on a specific
transformer, circuit breaker, feeder, or substation.'
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
        return json.dumps({
            "error": f"No maintenance records found for asset {asset_id} in the current year."
        })

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
# MAGIC Navigate: Left sidebar → Catalog icon → workshop_au → workshop_lab → Functions
# MAGIC You should see: three functions listed — calculate_peak_demand, get_meter_readings_summary, lookup_asset_status.
# MAGIC
# MAGIC Click any function to see its COMMENT field (what the LLM reads), parameter types, and the Permissions tab.
# MAGIC Test via SQL cell: `SELECT catalog.schema.function_name('param1', 'param2')` — there is no Run button in Catalog Explorer.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — Load sample data

# COMMAND ----------

import datetime, random, json
from pyspark.sql.types import *
from pyspark.sql import functions as F

random.seed(99)

# interval_reads — 7 days of 30-min NEM12-style data for NMI 6001234567
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

# asset_maintenance — YTD work orders for TF-NSW-001
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

print(f"interval_reads:    {len(ir_rows):>4} rows  ({len(ir_rows)//48} days × 48 intervals)")
print(f"asset_maintenance: {len(am_rows):>4} rows  (YTD work orders for TF-NSW-001)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Test UC functions via SQL

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.calculate_peak_demand(
# MAGIC     '6001234567', '2024-07-01', '2024-07-07'
# MAGIC ) AS peak_result

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.get_meter_readings_summary(
# MAGIC     '6001234567', '2024-07-03'
# MAGIC ) AS summary_result

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.lookup_asset_status('TF-NSW-001') AS asset_result

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Grant EXECUTE permission

# COMMAND ----------

# Uncomment and replace GRANTEE to grant EXECUTE to a colleague or service principal
GRANTEE = "your-colleague@company.com.au"  # TODO: replace this

# spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.calculate_peak_demand TO `{GRANTEE}`")
# spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.get_meter_readings_summary TO `{GRANTEE}`")
# spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.lookup_asset_status TO `{GRANTEE}`")
# print(f"EXECUTE granted to: {GRANTEE}. Invocations tracked in system.access.audit.")

print(f"GRANTEE set to: {GRANTEE} — uncomment the GRANT lines above and re-run to apply.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.7 — Wire UC functions to a LangChain agent

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks_langchain import UCFunctionToolkit, ChatDatabricks
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

w = WorkspaceClient()

toolkit = UCFunctionToolkit(
    warehouse_id=None,  # None = serverless SQL warehouse
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
    print(f"    {t.description[:90]}...")

# COMMAND ----------

llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=2048)

system_prompt = """You are an energy operations assistant for an Australian electricity network operator.
You have three tools: calculate_peak_demand, get_meter_readings_summary, lookup_asset_status.
Always use tools to answer questions about specific meters or assets — do not guess values.
Format numbers clearly: kWh for energy, minutes for outage duration, AUD for costs.
Use DD/MM/YYYY format when writing dates in responses."""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=6)

print("Agent ready — verbose=True shows tool call decisions in real time.")

# COMMAND ----------

# Question 1: peak demand
result = agent_executor.invoke({
    "input": "What was the peak demand for meter 6001234567 during the first week of July 2024?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 2: data quality / AEMO submission readiness
result = agent_executor.invoke({
    "input": "Check the data quality for meter 6001234567 on 3 July 2024. Is it ready for AEMO submission?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 3: asset status
result = agent_executor.invoke({
    "input": "What is the current maintenance status of asset TF-NSW-001? "
             "How many outage minutes has it caused this year and what has it cost?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 4: multi-tool — watch verbose trace for two separate Invoking: lines
result = agent_executor.invoke({
    "input": "For our weekly operations report: what was the peak demand on meter 6001234567 "
             "during the week of 1-7 July 2024, and does the maintenance history for asset "
             "TF-NSW-001 show any events that might explain unusual consumption in that period?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC Navigate: Machine Learning → Experiments → click your experiment → Traces tab
# MAGIC You should see: four AgentRun spans; Question 4 should show two ToolCall nodes in one run — the LLM called both calculate_peak_demand and lookup_asset_status.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #00843D; color: white; padding: 14px 20px; border-radius: 8px; margin: 24px 0;">
# MAGIC   <strong>Checkpoint — Section 3</strong><br>
# MAGIC   ✓ Three UC functions registered and tested via SQL<br>
# MAGIC   ✓ LangChain agent calls the right tool for each question type<br>
# MAGIC   ✓ Question 4 shows two tool calls in one agent run (visible in verbose trace)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 4 — Putting It Together: Skills + Tools in Agent Mode
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Capstone: Agent mode with explicit skill invocation
# MAGIC
# MAGIC Navigate: Genie Code panel → mode selector → Agent mode
# MAGIC You should see: the mode label change to "Agent" in the chat input bar.
# MAGIC
# MAGIC Try this conversation in order:
# MAGIC
# MAGIC **Turn 1** — skill + tool together:
# MAGIC ```
# MAGIC @energy-operations Using your energy operations knowledge, calculate the peak demand
# MAGIC for NMI 6001234567 in July 2024 and explain whether 17:00 is a typical peak time
# MAGIC for a VIC residential NMI.
# MAGIC ```
# MAGIC Expected: agent loads the skill, calls calculate_peak_demand, then interprets 17:00
# MAGIC against the peak window definition from the skill (17:00-20:00 AEST).
# MAGIC
# MAGIC **Turn 2** — different tool, same session context:
# MAGIC ```
# MAGIC Now check the data quality for that meter on the date the peak occurred.
# MAGIC Was the reading actual or estimated?
# MAGIC ```
# MAGIC Expected: agent calls get_meter_readings_summary using the date from Turn 1.
# MAGIC
# MAGIC **Turn 3** — third tool:
# MAGIC ```
# MAGIC Is there any maintenance history for asset TF-NSW-001 that might have
# MAGIC affected supply to this meter in July 2024?
# MAGIC ```
# MAGIC Expected: agent calls lookup_asset_status and interprets using skill context.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Decision guide: which pattern to use?
# MAGIC
# MAGIC | Situation | What to use | Why |
# MAGIC |-----------|-------------|-----|
# MAGIC | Domain terminology the LLM should always know | Custom Instructions | Loaded every time, zero friction |
# MAGIC | A long reference guide (e.g., NEM12 field positions) | Skill | Too long for always-on; loaded when needed |
# MAGIC | A formula that never changes (e.g., SAIDI) | Skill | Static knowledge, no code needed |
# MAGIC | The actual SAIDI value for this month | UC Function Tool | Requires querying live data |
# MAGIC | The latest asset status | UC Function Tool | Changes over time, needs real query |
# MAGIC | Context specific to one project directory | AGENTS.md | Scoped, does not pollute global instructions |
# MAGIC | Context for the whole team in the workspace | Workspace instructions | Admin sets once, applies to all users |
# MAGIC
# MAGIC **Common mistakes:**
# MAGIC
# MAGIC | Mistake | Fix |
# MAGIC |---------|-----|
# MAGIC | Putting table column names in Custom Instructions | Put in AGENTS.md — schema changes, tokens wasted every message |
# MAGIC | Skill description: "Energy operations guide" (too generic) | Write description as trigger phrases: "NEM12 quality flags SAIDI SAIFI AER" |
# MAGIC | UC function that raises an exception | Return `{"error": "..."}` — let the LLM interpret it |
# MAGIC | UC function COMMENT that only describes what it does | Add "Use this when asked about..." so the LLM knows when to call it |

# COMMAND ----------

summary = """
╔══════════════════════════════════════════════════════════════════════════════╗
║       Genie Code Extension Patterns — Quick Reference                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CUSTOM INSTRUCTIONS                                                         ║
║  Path:     /Users/{email}/.assistant_instructions.md                        ║
║  Loads:    Every session, automatically. Keep concise — uses tokens always. ║
║                                                                              ║
║  AGENTS.md / CLAUDE.md                                                       ║
║  Path:     Any directory — Genie walks up from the current notebook          ║
║  Loads:    When working in a notebook under that directory                   ║
║                                                                              ║
║  SKILLS                                                                      ║
║  Path:     /Users/{email}/.assistant/skills/{name}/SKILL.md                ║
║  Loads:    On demand — query match or @skill-name                            ║
║  Tip:      description field drives auto-discovery — make it specific        ║
║                                                                              ║
║  UC FUNCTION TOOLS                                                           ║
║  Location: Unity Catalog — catalog.schema.function_name                     ║
║  Requires: EXECUTE permission. Runs inside workspace. All calls audited.    ║
║  LangChain name: catalog__schema__function_name (dots → double underscore)  ║
║  Tip:      COMMENT quality is the #1 factor in correct tool selection        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
print(summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise — Write your own UC function: `calculate_demand_statistics`
# MAGIC
# MAGIC Register a new UC function that takes `nmi` (STRING) and `month` (STRING, format `YYYY-MM`),
# MAGIC queries `interval_reads` grouped by `read_date`, and returns JSON with:
# MAGIC `avg_daily_kwh`, `max_daily_kwh`, `min_daily_kwh`, `std_daily_kwh`, `month_total_kwh`.
# MAGIC
# MAGIC Use Genie Code to scaffold it — suggested prompt:
# MAGIC > *"Write a Databricks UC function called calculate_demand_statistics that takes nmi (STRING)
# MAGIC > and month (STRING, YYYY-MM). Query workshop_au.workshop_lab.interval_reads, group by read_date
# MAGIC > to get daily totals, return aggregate statistics as JSON. Match the error-handling and return
# MAGIC > format style of the existing functions in this notebook. COMMENT should explain when to call it."*

# COMMAND ----------

# TODO: Register calculate_demand_statistics as a UC function

# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_demand_statistics(
#     nmi   STRING COMMENT '...',
#     month STRING COMMENT 'Analysis month in YYYY-MM format (e.g., 2024-07)'
# )
# RETURNS STRING
# COMMENT 'Calculate daily demand statistics for a NEM meter over a calendar month.
# Returns JSON with avg_daily_kwh, max_daily_kwh, min_daily_kwh, std_daily_kwh, month_total_kwh.
# Use when asked about demand variability, monthly consumption statistics, or load profiling.'
# LANGUAGE PYTHON
# AS $$
# import json
# try:
#     from pyspark.sql import SparkSession
#     from pyspark.sql import functions as F
#     spark = SparkSession.builder.getOrCreate()
#     # ... your implementation ...
# except Exception as e:
#     return json.dumps({"error": str(e)})
# $$
# """)

# # Then reload the toolkit and rebuild the agent:
# # toolkit_v2 = UCFunctionToolkit(tools_names=[..., f"{CATALOG}.{SCHEMA}.calculate_demand_statistics"])
# # tools_v2 = toolkit_v2.get_tools()
# # agent_v2 = create_tool_calling_agent(llm, tools_v2, prompt)
# # agent_executor_v2 = AgentExecutor(agent=agent_v2, tools=tools_v2, verbose=True)
# # result = agent_executor_v2.invoke({"input": "What were the demand stats for meter 6001234567 in July 2024?"})

print("Exercise: implement calculate_demand_statistics — uncomment and fill in the body above.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 24px 28px; border-radius: 10px; margin-top: 24px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 03 Complete</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; font-size: 0.97em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Custom Instructions</td>
# MAGIC       <td style="padding: 6px 10px;">Text loaded into every session — terminology, preferences, regulatory context</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Skills</td>
# MAGIC       <td style="padding: 6px 10px;">Markdown documents fetched on demand — deep reference, @invoked or auto-matched</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">UC Function Tools</td>
# MAGIC       <td style="padding: 6px 10px;">Executable code in Unity Catalog — live data, governed, audited, EXECUTE-gated</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">COMMENT quality</td>
# MAGIC       <td style="padding: 6px 10px;">The single biggest factor in whether an LLM calls the right tool at the right time</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 14px 0 0 0; font-weight: bold;">
# MAGIC     Next: Lab 04 — MCP Integration
# MAGIC   </p>
# MAGIC </div>
