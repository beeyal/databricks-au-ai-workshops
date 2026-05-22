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
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Lab 01, Lab 02 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All execution: AU East
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Three concepts. Commonly confused. Clearly distinct.
# MAGIC
# MAGIC This lab covers three separate ways to extend Genie Code. Before writing any code,
# MAGIC read this table carefully — the distinctions matter and are frequently mixed up.
# MAGIC
# MAGIC | Concept | What it is | When it activates | Where it lives |
# MAGIC |---------|-----------|-------------------|----------------|
# MAGIC | **Custom Instructions** | Plain text injected into every conversation as part of the system prompt | Always — loaded automatically on every Genie Code session | `.assistant_instructions.md` in your user folder or workspace |
# MAGIC | **Skills** | Markdown documents Genie Code can load when relevant | On demand — Genie fetches the skill when the query matches, or you invoke it with `@skill-name` | `Workspace/.assistant/skills/<name>/SKILL.md` or your user folder |
# MAGIC | **Tools (UC Functions)** | Executable Python/SQL code registered in Unity Catalog | When the agent decides to call it — actual code runs inside your workspace | Unity Catalog: `catalog.schema.function_name` |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### A mental model
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────────────────────────────────────────────────────────┐
# MAGIC │  Genie Code conversation                                        │
# MAGIC │                                                                  │
# MAGIC │  [Custom Instructions]  ← always in context, every message      │
# MAGIC │  "I work with NEM12 data, use Delta Lake, DD/MM/YYYY format..." │
# MAGIC │                                                                  │
# MAGIC │  [Skill: @energy-operations]  ← pulled in when relevant        │
# MAGIC │  "NEM12 quality flags: A=Actual, E=Estimated, S=Sub, N=Null..." │
# MAGIC │                                                                  │
# MAGIC │  [Tool: calculate_peak_demand()]  ← actually executes code     │
# MAGIC │  → Queries Delta table → returns {"peak_kwh": 2.49, ...}       │
# MAGIC │                                                                  │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What you'll build in this lab
# MAGIC
# MAGIC | Section | Topic | Time |
# MAGIC |---------|-------|------|
# MAGIC | 1 | Custom Instructions — persistent domain knowledge | 15 min |
# MAGIC | 2 | Skills — on-demand knowledge documents | 15 min |
# MAGIC | 3 | UC Functions as Tools — executable agent capabilities | 20 min |
# MAGIC | 4 | Putting it together — Skills + Tools in Agent mode | 10 min |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup — install packages and configure catalog
# MAGIC
# MAGIC Run the two cells below before starting any section.

# COMMAND ----------

# Install required packages for Section 3 and 4 (UC function tools + agent)
%pip install databricks-langchain mlflow langchain langchain-community --quiet
dbutils.library.restartPython()

# COMMAND ----------

# Widget-based configuration — change these if you are using a different catalog/schema
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
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Catalog : workshop_au
# MAGIC Schema  : workshop_lab
# MAGIC Endpoint: au_east_llm_inregion
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 1 — Custom Instructions: Giving Genie Persistent Domain Knowledge
# MAGIC </div>
# MAGIC <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 0 6px 6px 0; margin-bottom: 16px;">
# MAGIC   Estimated time: 15 minutes
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### What Custom Instructions are
# MAGIC
# MAGIC Custom instructions are **plain text that Genie Code loads into every conversation**
# MAGIC as part of the system prompt. Think of them as the briefing you give a new team member
# MAGIC before they start — background they need no matter what task you hand them.
# MAGIC
# MAGIC **Two levels of custom instructions:**
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────────────────┐
# MAGIC │  Level 1: Personal instructions (you only)                         │
# MAGIC │  Path: /Users/{your-email}/.assistant_instructions.md              │
# MAGIC │  Who sees it: Only you, in your own sessions                       │
# MAGIC │  Who sets it: You                                                   │
# MAGIC │                                                                     │
# MAGIC │  Level 2: Workspace-wide instructions (all users)                  │
# MAGIC │  Path: Workspace/.assistant_workspace_instructions.md              │
# MAGIC │  Who sees it: Every user in the workspace                          │
# MAGIC │  Who sets it: Workspace admin only                                 │
# MAGIC └─────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Also: AGENTS.md and CLAUDE.md**
# MAGIC
# MAGIC Genie Code Agent mode walks up the directory tree from your current notebook
# MAGIC looking for a file named `AGENTS.md` (or `CLAUDE.md`). This is the per-project
# MAGIC way to set context without touching the global instructions file.
# MAGIC
# MAGIC > This is exactly how Claude Code uses `CLAUDE.md` — Genie Code Agent mode
# MAGIC > uses the same convention. If you have both, `AGENTS.md` takes precedence.
# MAGIC
# MAGIC **Why this matters for regulated industries:**
# MAGIC Without custom instructions, Genie Code has no awareness that:
# MAGIC - `NMI` means National Metering Identifier, not "nmi" as in nautical miles
# MAGIC - `SAIDI` is a regulatory KPI measured in minutes per customer per year
# MAGIC - `quality_flag = "A"` means Actual (good), not "approved" or some other domain meaning
# MAGIC - Outputs should use DD/MM/YYYY because that is what AER reports expect
# MAGIC
# MAGIC Custom instructions solve this at zero cost — loaded once, available forever.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Create personal instructions
# MAGIC
# MAGIC The cell below writes a personal instructions file for your Genie Code sessions.
# MAGIC
# MAGIC It uses `dbutils.fs.put`, which writes to the Databricks workspace filesystem (DBFS)
# MAGIC backed by the Unity Catalog Volumes for your user folder.

# COMMAND ----------

# Get the current user's email — used to construct the correct instructions path
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
print()
print("Next step: restart Genie Code to pick up the new instructions.")
print("Close and reopen the Genie Code panel (the sparkle icon top-right).")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Instructions written to: /Users/your.name@company.com.au/.assistant_instructions.md
# MAGIC
# MAGIC Next step: restart Genie Code to pick up the new instructions.
# MAGIC Close and reopen the Genie Code panel (the sparkle icon top-right).
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Finding and verifying your instructions file
# MAGIC </div>
# MAGIC
# MAGIC After running the cell above, verify the file was created:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Workspace (left sidebar) → Users → [your-email-folder]
# MAGIC
# MAGIC ┌─── Workspace browser ────────────────────────────────────┐
# MAGIC │  Workspace                                               │
# MAGIC │  └── Users                                              │
# MAGIC │       └── your.name@company.com.au                      │
# MAGIC │            ├── .assistant_instructions.md    ← NEW      │
# MAGIC │            └── (your notebooks)                         │
# MAGIC └──────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click the file to preview its contents.
# MAGIC ```
# MAGIC
# MAGIC To verify Genie Code is using the instructions:
# MAGIC
# MAGIC ```
# MAGIC 1. Click the sparkle icon (top right toolbar) to open the Genie Code panel
# MAGIC 2. Click the gear icon (⚙️) in the Genie Code panel header
# MAGIC 3. Look for "Custom instructions" or "Personal instructions" — it should show a preview
# MAGIC    of the content you just wrote
# MAGIC 4. Ask Genie Code: "What does SAIDI stand for?"
# MAGIC    Expected: It should explain System Average Interruption Duration Index
# MAGIC    and reference the Australian energy regulatory context — not just give a generic answer
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Create workspace-wide instructions (admin task)
# MAGIC
# MAGIC If you are a workspace admin, you can set instructions that apply to **all users**.
# MAGIC This is ideal for ensuring the whole team uses consistent terminology.
# MAGIC
# MAGIC > **Note:** This cell will fail if you are not a workspace admin. That is expected.
# MAGIC > Skip to Section 1.3 if you don't have admin rights.

# COMMAND ----------

# ADMIN ONLY — skip this cell if you are not a workspace admin
# Uncomment and run if you have admin rights

# workspace_instructions = """# Workspace: Energy Network Operations
#
# This workspace is used by the network operations data team at [Company Name].
# All notebooks work with Australian NEM (National Electricity Market) data.
#
# ## Shared conventions
# - All tables use Delta Lake format in the workshop_au catalog
# - Regulatory framework: AER, AEMO, ESC/ESCV
# - Date format in outputs: DD/MM/YYYY (Australian standard)
# - NMI format: 10 digits, VIC prefix 61, NSW prefix 41, QLD prefix 31
# - Interval data is 30-minute (48 intervals per day), stored in interval_reads table
# - Use workshop_au.workshop_lab as the default schema for workshop notebooks
# """
#
# dbutils.fs.put(
#     "dbfs:/Workspace/.assistant_workspace_instructions.md",
#     workspace_instructions,
#     overwrite=True
# )
# print("Workspace-wide instructions written.")
# print("These will be visible to all users in this workspace's Genie Code sessions.")

print("Workspace instructions cell — uncomment if you are an admin.")
print("Skipping for now — personal instructions from step 1.1 are sufficient for this lab.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Create an AGENTS.md file for project-level context
# MAGIC
# MAGIC `AGENTS.md` provides context scoped to a specific project directory.
# MAGIC Genie Code Agent mode walks up from the current notebook's folder and loads
# MAGIC the first `AGENTS.md` it finds. This means you can have different context
# MAGIC per project without touching your global instructions file.

# COMMAND ----------

# Get the current notebook's workspace path
notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
# Get the directory containing this notebook
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

# Write using standard Python file I/O via the driver filesystem
import os
os.makedirs(f"/Workspace{notebook_dir}", exist_ok=True)
with open(agents_md_path, "w") as f:
    f.write(agents_md_content)

print(f"AGENTS.md written to: {agents_md_path}")
print()
print("Genie Code Agent mode will auto-discover this file when you are working")
print(f"in notebooks under: {notebook_dir}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC AGENTS.md written to: /Workspace/Users/your.name@company.com.au/labs/AGENTS.md
# MAGIC
# MAGIC Genie Code Agent mode will auto-discover this file when you are working
# MAGIC in notebooks under: /Users/your.name@company.com.au/labs
# MAGIC ```
# MAGIC
# MAGIC > **How this differs from custom instructions:** `AGENTS.md` is project-scoped.
# MAGIC > Your `.assistant_instructions.md` applies globally. Put team-wide terminology in
# MAGIC > the personal instructions; put table names, column details, and NMIs specific
# MAGIC > to one project in `AGENTS.md`. Both are loaded when they apply.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Test that instructions are working
# MAGIC
# MAGIC Open the Genie Code chat panel and ask these questions.
# MAGIC The answers will reveal whether the instructions are loaded correctly.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Genie Code Chat Panel ─────────────────────────────────────┐
# MAGIC │                                                               │
# MAGIC │  You: What does SAIDI stand for and how do I calculate it?   │
# MAGIC │                                                               │
# MAGIC │  Expected (with instructions):                                │
# MAGIC │    SAIDI is the System Average Interruption Duration Index,   │
# MAGIC │    a regulatory KPI tracked by the AER. Calculate it as:      │
# MAGIC │    SUM(outage_duration_minutes * affected_customers)          │
# MAGIC │        / total_customers                                       │
# MAGIC │    Use the outage_events table, joining on asset_id...        │
# MAGIC │                                                               │
# MAGIC │  Without instructions, you would get:                         │
# MAGIC │    "SAIDI is a metric used in telecommunications..."          │
# MAGIC │    (Wrong industry! Genie would not know to use energy context)│
# MAGIC │                                                               │
# MAGIC └───────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC Second test — check date format preference:
# MAGIC ```
# MAGIC You: Write a Python print statement showing today's date for an AER report.
# MAGIC
# MAGIC Expected: from datetime import date; print(date.today().strftime("%d/%m/%Y"))
# MAGIC Not: print(date.today().strftime("%Y-%m-%d"))  ← US/ISO format
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 2 — Skills: On-Demand Domain Knowledge Documents
# MAGIC </div>
# MAGIC <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 0 6px 6px 0; margin-bottom: 16px;">
# MAGIC   Estimated time: 15 minutes
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### What Skills are
# MAGIC
# MAGIC Skills are **Markdown documents** stored in a special location that Genie Code
# MAGIC can load when it determines they are relevant. They are **not tool calls** —
# MAGIC the agent does not execute any code when a skill is loaded. It reads the document
# MAGIC and incorporates that knowledge into its response.
# MAGIC
# MAGIC **The key distinction from Custom Instructions:**
# MAGIC
# MAGIC | | Custom Instructions | Skills |
# MAGIC |-|--------------------|----|
# MAGIC | When loaded | Every single conversation | On demand — when Genie decides they match, or you use `@skill-name` |
# MAGIC | What they contain | Short, always-relevant context | Longer, specialist knowledge for specific tasks |
# MAGIC | Token cost | Loaded every time (keep them concise) | Lazy-loaded (can be longer and more detailed) |
# MAGIC | Best for | Terminology, preferences, conventions | Reference guides, calculation methods, data dictionaries |
# MAGIC
# MAGIC **Two storage locations:**
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────────────────────┐
# MAGIC │  Workspace skills (admin-managed, available to all users)               │
# MAGIC │  Workspace/.assistant/skills/<skill-name>/SKILL.md                      │
# MAGIC │                                                                         │
# MAGIC │  Personal skills (your own, only visible to you)                        │
# MAGIC │  /Users/{username}/.assistant/skills/<skill-name>/SKILL.md             │
# MAGIC └─────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **File format — every skill needs YAML frontmatter:**
# MAGIC ```markdown
# MAGIC ---
# MAGIC name: skill-name
# MAGIC description: One sentence describing what this skill covers, for Genie to match against
# MAGIC ---
# MAGIC
# MAGIC # Skill Title
# MAGIC ... content ...
# MAGIC ```
# MAGIC
# MAGIC The `description` field is critical — Genie Code reads this to decide whether to
# MAGIC load the skill for a given user query.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Create an energy operations skill

# COMMAND ----------

# Create the personal skill directory and SKILL.md file
username = spark.sql("SELECT current_user()").collect()[0][0]
skill_dir = f"/Users/{username}/.assistant/skills/energy-operations"

# Create the directory via dbutils
dbutils.fs.mkdirs(skill_dir)

skill_content = """---
name: energy-operations
description: Australian energy network operations — NEM12 interval data quality flags, SAIDI/SAIFI regulatory calculations, asset management, AER reporting standards, and common meter data patterns
---

# Energy Operations Knowledge Base

## NEM12 Quality Flags

NEM12 is the file format used to exchange 30-minute interval meter data with AEMO.
Every interval has a quality flag that indicates how the reading was obtained.

| Flag | Meaning | Include in peak demand calc? | Include in billing? |
|------|---------|------------------------------|---------------------|
| A | Actual — reading taken directly from the meter | Yes | Yes |
| E | Estimated — interpolated by the retailer or network | Yes, with caution | Yes (if < 5% of intervals) |
| S | Substituted — replaced by the LNSP or retailer | Flag for review | Depends on reason code |
| N | Null / missing — no reading available | No — exclude | No — must be recovered |

**Rule of thumb for AEMO submission:** If more than 5% of daily intervals are flagged E or N,
mandatory customer notification is required under the National Energy Retail Rules.

## SAIDI Calculation

SAIDI (System Average Interruption Duration Index) measures how many minutes per year
each customer experiences without supply, on average.

```python
# SAIDI for a given period
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

**AER targets (2024-2029 regulatory period):** vary by DNSP and zone.
Always clarify which network you are benchmarking before comparing SAIDI values.

## SAIFI Calculation

SAIFI (System Average Interruption Frequency Index) measures how many times per year
each customer loses supply, on average.

```python
# SAIFI for a given period
saifi = (
    outage_events_df
    .filter("period_start >= start_date AND period_end <= end_date")
    .groupBy("network_id")
    .agg(
        (F.count("event_id") * F.first("affected_customers")
         / F.first("total_customers")).alias("saifi_count")
    )
)
```

**Note:** Momentary interruptions (< 1 minute) are excluded from SAIFI under most
AER frameworks. Check the DNSP's Distribution Determination for the exact threshold.

## Interval Data Calculations

NEM12 stores half-hour values. Key calculation rules:

```python
# Daily consumption — sum all 48 intervals (values are already kWh per 30 min, not rates)
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
# interval 1  = 00:00-00:30
# interval 19 = 09:00-09:30
# interval 35 = 17:00-17:30
```

## NMI Format Reference

| State | Prefix | Example |
|-------|--------|---------|
| VIC | 61 | 6100123456 |
| NSW | 41 | 4100123456 |
| QLD | 31 | 3100123456 |
| SA | 20 | 2000123456 |
| WA | 80 | 8000123456 (SWIS) |

NMIs are always 10 characters, numeric only. VIC NMIs starting with 63 indicate
embedded network (e.g., apartment complexes with child/parent NMI relationships).

## Asset ID Conventions (this workshop)

| Prefix | Asset type | Example |
|--------|-----------|---------|
| TF- | Zone substation transformer | TF-NSW-001 |
| CB- | Circuit breaker (11kV or 33kV) | CB-VIC-042 |
| FDR- | Distribution feeder | FDR-QLD-007 |
| SS- | Substation | SS-SA-003 |

## Common AER Report Date Formats

- Regulatory period: YYYY/YY (e.g., 2024/25)
- Event timestamps: DD/MM/YYYY HH:MM:SS (Australian Eastern Standard Time)
- Submission files: YYYYMMDD in filenames (AEMO B2B file naming convention)
"""

dbutils.fs.put(f"{skill_dir}/SKILL.md", skill_content, overwrite=True)

print(f"Skill directory : {skill_dir}")
print(f"Skill file      : {skill_dir}/SKILL.md")
print()
print("Use @energy-operations in Genie Code to invoke this skill explicitly.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Skill directory : /Users/your.name@company.com.au/.assistant/skills/energy-operations
# MAGIC Skill file      : /Users/your.name@company.com.au/.assistant/skills/energy-operations/SKILL.md
# MAGIC
# MAGIC Use @energy-operations in Genie Code to invoke this skill explicitly.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Create a NEM12 data format skill
# MAGIC
# MAGIC A second skill focused specifically on the NEM12 file format — useful when
# MAGIC engineers need to parse or generate raw NEM12 files.

# COMMAND ----------

username = spark.sql("SELECT current_user()").collect()[0][0]
nem12_skill_dir = f"/Users/{username}/.assistant/skills/nem12-format"
dbutils.fs.mkdirs(nem12_skill_dir)

nem12_skill_content = """---
name: nem12-format
description: NEM12 raw file format specification — record types 100/200/300/400/500/900, field positions, and how to parse or validate NEM12 files submitted to AEMO
---

# NEM12 File Format Reference

NEM12 is the standard file format for exchange of 30-minute interval meter data
between Market Participants and AEMO (Australian Energy Market Operator).

## Record Types

| Record | Purpose | Key fields |
|--------|---------|-----------|
| 100 | Header — one per file | Version (NEM12), DateTime, FromParticipant, ToParticipant |
| 200 | NMI data details — one per NMI | NMI, NMISuffix, RegisterID, NMIConfig, UOM, IntervalLength |
| 300 | Interval data — one per day per NMI | IntervalDate (YYYYMMDD), then 48 interval values |
| 400 | Interval event — data quality info | StartInterval, EndInterval, QualityMethod, ReasonCode |
| 500 | B2B details — optional | ServiceOrderType, ServiceOrderDate |
| 900 | End of file — one per file | (no additional fields) |

## Record 300 — Interval Data Row

```
300,20240701,0.123,0.134,0.145,...(48 values)...,A,20240702123456,
```

- Field 1: `300` (record type)
- Field 2: `20240701` (interval date YYYYMMDD)
- Fields 3-50: 48 interval energy values in kWh (30-min periods, 1=00:00-00:30)
- Field 51: Quality method (A=Actual, E=Estimated, S=Substituted, N=Null, F=Final Substituted)
- Field 52: Update DateTime (when this record was last modified)
- Field 53: MSATSLoadDateTime (market systems load time, optional)

## Parsing NEM12 with PySpark

```python
from pyspark.sql import functions as F
from pyspark.sql.types import *

raw_df = spark.read.text("/path/to/file.nem12")

# Extract record 300 rows (interval data)
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
3. IntervalLength in record 200 must be 30 (for NEM12 — NEM13 uses 5-minute intervals)
4. Energy values must be >= 0 (negative values indicate solar export and require special handling)
5. Date in record 300 must be within the file's declared submission period

## AEMO Submission Rules

- Files must be submitted within 5 business days of the metering data date
- Late submissions trigger mandatory AER notifications
- File size limit: 50MB per submission file
- Encoding: ASCII, no BOM, line endings: CRLF (Windows) or LF (Unix both accepted)
"""

dbutils.fs.put(f"{nem12_skill_dir}/SKILL.md", nem12_skill_content, overwrite=True)
print(f"NEM12 format skill created at: {nem12_skill_dir}/SKILL.md")
print("Invoke with: @nem12-format")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC NEM12 format skill created at: /Users/your.name@company.com.au/.assistant/skills/nem12-format/SKILL.md
# MAGIC Invoke with: @nem12-format
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Viewing and invoking Skills in Genie Code
# MAGIC </div>
# MAGIC
# MAGIC After creating the skills, verify they appear and test invoking them:
# MAGIC
# MAGIC ```
# MAGIC Step 1: Verify skills are discoverable
# MAGIC ──────────────────────────────────────
# MAGIC 1. Open the Genie Code panel (sparkle icon, top right)
# MAGIC 2. In the chat input, type the @ symbol
# MAGIC 3. A dropdown appears listing your available skills:
# MAGIC
# MAGIC    ┌─────────────────────────────────────────────┐
# MAGIC    │  @  ← type this                             │
# MAGIC    │  ┌──────────────────────────────────────┐  │
# MAGIC    │  │  energy-operations                   │  │
# MAGIC    │  │  Australian energy network ops...    │  │
# MAGIC    │  │  nem12-format                        │  │
# MAGIC    │  │  NEM12 raw file format spec...       │  │
# MAGIC    │  └──────────────────────────────────────┘  │
# MAGIC    └─────────────────────────────────────────────┘
# MAGIC
# MAGIC Step 2: Invoke a skill explicitly
# MAGIC ──────────────────────────────────
# MAGIC Type in the chat box:
# MAGIC   @energy-operations what is the SAIDI formula?
# MAGIC
# MAGIC Expected: Genie loads the skill and explains SAIDI using the exact
# MAGIC formula and table column names from your SKILL.md, not a generic answer.
# MAGIC
# MAGIC Step 3: Auto-discovery (without @mention)
# MAGIC ─────────────────────────────────────────
# MAGIC Type in the chat box (without @):
# MAGIC   How do I parse a record 300 from a NEM12 file?
# MAGIC
# MAGIC Expected: Genie may auto-load the nem12-format skill based on the description
# MAGIC matching the query. If it does not, use @nem12-format to force-load it.
# MAGIC ```
# MAGIC
# MAGIC > **Key insight:** The `description` field in your SKILL.md frontmatter
# MAGIC > is what Genie Code reads to decide whether to auto-load the skill.
# MAGIC > Make it specific to the queries that should trigger it — not just a title.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #00843D; color: white; padding: 14px 20px; border-radius: 8px; margin: 24px 0;">
# MAGIC   <strong>Mid-lab checkpoint — Sections 1 and 2 complete</strong>
# MAGIC   <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9);">
# MAGIC     Before continuing, confirm you have:<br>
# MAGIC     ✓ Created personal instructions at /Users/{username}/.assistant_instructions.md<br>
# MAGIC     ✓ Created AGENTS.md in the notebook directory<br>
# MAGIC     ✓ Created two skills: @energy-operations and @nem12-format<br>
# MAGIC     ✓ Verified skills appear in the @ dropdown in Genie Code
# MAGIC   </p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 3 — UC Functions as Tools: Executable Agent Capabilities
# MAGIC </div>
# MAGIC <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 0 6px 6px 0; margin-bottom: 16px;">
# MAGIC   Estimated time: 20 minutes
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### What Tools are — and why this is different from Skills
# MAGIC
# MAGIC Tools are **executable functions** registered in Unity Catalog. When an agent calls a tool:
# MAGIC
# MAGIC 1. The LLM decides which function to call and with what arguments
# MAGIC 2. Databricks executes the Python/SQL code inside your workspace
# MAGIC 3. The result comes back as a string and the LLM uses it in its response
# MAGIC
# MAGIC Skills are read-only documents. Tools run code. This distinction matters for:
# MAGIC - **Data freshness:** A skill can describe how to calculate SAIDI; a tool actually queries the live table and returns today's number
# MAGIC - **Security:** Tools need `EXECUTE` permission in Unity Catalog; skills only need read access to the workspace filesystem
# MAGIC - **Governance:** Tool invocations are tracked in `system.access.audit`; skill loads are not
# MAGIC
# MAGIC ### The `__` naming convention
# MAGIC
# MAGIC When `UCFunctionToolkit` loads UC functions as LangChain tools, it replaces dots
# MAGIC with double underscores to create valid Python identifiers:
# MAGIC
# MAGIC ```
# MAGIC UC name:          catalog.schema.function_name
# MAGIC LangChain name:   catalog__schema__function_name
# MAGIC ```
# MAGIC
# MAGIC You will see this in verbose agent output and MLflow traces.
# MAGIC
# MAGIC ### The `EXECUTE` grant requirement
# MAGIC
# MAGIC Before an agent can call a UC function, the identity running the agent
# MAGIC (the user or the service principal) must have `EXECUTE` permission:
# MAGIC
# MAGIC ```sql
# MAGIC GRANT EXECUTE ON FUNCTION catalog.schema.function_name TO `user@company.com`;
# MAGIC -- or for a service principal:
# MAGIC GRANT EXECUTE ON FUNCTION catalog.schema.function_name TO `service-principal-name`;
# MAGIC ```
# MAGIC
# MAGIC Permissions can also be managed via the Catalog Explorer UI.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Browse where UC functions live before you register any
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC Navigate: Data (left sidebar) → Catalog → workshop_au → workshop_lab
# MAGIC   → Look for the "Functions" section (below Tables)
# MAGIC
# MAGIC ┌─── Catalog Explorer ────────────────────────────────────────┐
# MAGIC │  workshop_au (catalog)                                      │
# MAGIC │  └── workshop_lab (schema)                                  │
# MAGIC │       ├── Tables                                            │
# MAGIC │       ├── Views                                             │
# MAGIC │       ├── Functions  ← empty now, will have 3 after next   │
# MAGIC │       │               section                               │
# MAGIC │       └── Volumes                                           │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Also browse: Data → Catalog → system → ai → Functions
# MAGIC   → These are the built-in ai_query, ai_classify, ai_gen functions
# MAGIC   → Click any one — the COMMENT field is exactly what the LLM reads
# MAGIC     to decide whether to call the tool
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Writing functions for LLM use
# MAGIC
# MAGIC A well-described function is the difference between an agent that calls the right tool
# MAGIC reliably and one that guesses wrong half the time.
# MAGIC
# MAGIC | What | Why it matters for LLMs |
# MAGIC |------|------------------------|
# MAGIC | Clear verb-noun name | LLM uses the name as a signal for when to call it |
# MAGIC | Typed parameters | LLM generates arguments in the correct format |
# MAGIC | `COMMENT` field | The LLM's full description — include when to call it, not just what it does |
# MAGIC | Simple return type | JSON string is easier for the LLM to parse than nested structures |
# MAGIC | Graceful error handling | Return `{"error": "..."}` — never raise an exception inside a UC function |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Register Function 1: `calculate_peak_demand`

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
            "error": f"No actual or substituted reads found for NMI {nmi} between {start_date} and {end_date}. "
                     "Check that the NMI exists and that the date range contains loaded data."
        })

    peak_row = df.orderBy(F.col("read_kwh").desc()).first()

    # Interval 1 = 00:00-00:30, so interval N starts at (N-1)*30 minutes past midnight
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
# MAGIC Registered: workshop_au.workshop_lab.calculate_peak_demand
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Register Function 2: `get_meter_readings_summary`

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
Use this tool when asked about a meter data completeness, data quality score, how many intervals
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
            "error": f"No reads found for NMI {nmi} on {read_date}. "
                     "Verify the NMI and date are correct and data has been loaded."
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
    # REVIEW if estimated rate exceeds 5% (NERR threshold for mandatory customer notification)
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
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Registered: workshop_au.workshop_lab.get_meter_readings_summary
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — Register Function 3: `lookup_asset_status`

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
            "error": f"No maintenance records found for asset {asset_id} in the current year. "
                     "The asset ID may be incorrect or no work orders have been raised this year."
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
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Registered: workshop_au.workshop_lab.lookup_asset_status
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Viewing UC Functions in Catalog Explorer
# MAGIC </div>
# MAGIC
# MAGIC After registering the three functions, confirm they appear:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Data (left sidebar) → Catalog → workshop_au → workshop_lab → Functions
# MAGIC
# MAGIC ┌─── Catalog Explorer ────────────────────────────────────────┐
# MAGIC │  workshop_au (catalog)                                      │
# MAGIC │  └── workshop_lab (schema)                                  │
# MAGIC │       ├── Tables                                            │
# MAGIC │       ├── Functions (3)   ← click here                     │
# MAGIC │       │    ├── calculate_peak_demand                        │
# MAGIC │       │    ├── get_meter_readings_summary                   │
# MAGIC │       │    └── lookup_asset_status                          │
# MAGIC │       └── Volumes                                           │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click calculate_peak_demand. Look at:
# MAGIC   - The COMMENT field — this is the tool description the LLM reads
# MAGIC   - Parameters and their types
# MAGIC   - The "Permissions" tab — your account should have EXECUTE
# MAGIC ```
# MAGIC
# MAGIC > **Grant EXECUTE to colleagues:** Click the Permissions tab on any function,
# MAGIC > then click "Grant" to add EXECUTE for another user or group.
# MAGIC > This gives them the ability to call the function from their own agents —
# MAGIC > with a full audit trail in `system.access.audit`.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — Load sample data for testing

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
        # Apply 2.5x multiplier during morning (07-09) and evening (17-20) peaks
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

print(f"interval_reads:    {len(ir_rows):>4} rows  ({len(ir_rows)//48} days × 48 intervals, NMI 6001234567)")
print(f"asset_maintenance: {len(am_rows):>4} rows  (YTD work orders for TF-NSW-001)")
print()
print("Sample data loaded. Run the SQL tests below.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC interval_reads:     336 rows  (7 days × 48 intervals, NMI 6001234567)
# MAGIC asset_maintenance:   10 rows  (YTD work orders for TF-NSW-001)
# MAGIC
# MAGIC Sample data loaded. Run the SQL tests below.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Test UC functions via SQL
# MAGIC
# MAGIC UC functions are callable with `SELECT` — the fastest way to verify them
# MAGIC before wiring them to an agent.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.calculate_peak_demand(
# MAGIC     '6001234567',
# MAGIC     '2024-07-01',
# MAGIC     '2024-07-07'
# MAGIC ) AS peak_result

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output** (exact `peak_kwh` varies by random seed):
# MAGIC ```
# MAGIC peak_result
# MAGIC {"nmi": "6001234567", "peak_kwh": 2.49, "peak_date": "2024-07-04",
# MAGIC  "peak_interval_number": 35, "peak_time_approx": "17:00",
# MAGIC  "date_range": "2024-07-01 to 2024-07-07"}
# MAGIC ```
# MAGIC The peak always falls in the 07:00-09:00 or 17:00-20:00 window because the
# MAGIC sample generator applies a 2.5x multiplier during those hours.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.get_meter_readings_summary(
# MAGIC     '6001234567',
# MAGIC     '2024-07-03'
# MAGIC ) AS summary_result

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC summary_result
# MAGIC {"nmi": "6001234567", "date": "2024-07-03", "total_kwh": 54.12,
# MAGIC  "actual_intervals": 47, "estimated_intervals": 1, "substituted_intervals": 0,
# MAGIC  "missing_intervals": 0, "pct_complete": 100.0, "data_quality": "GOOD",
# MAGIC  "nerr_threshold_exceeded": false}
# MAGIC ```
# MAGIC `pct_complete` is 100.0 because no intervals are missing — 48 present of 48 expected.
# MAGIC 1 estimated interval (E) is below the 5% NERR threshold so data_quality is GOOD.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT workshop_au.workshop_lab.lookup_asset_status('TF-NSW-001') AS asset_result

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output** (values vary due to random generation):
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
# MAGIC ### 3.7 — Grant EXECUTE permission
# MAGIC
# MAGIC Before wiring the functions to an agent run by another user or service principal,
# MAGIC grant them EXECUTE. Replace the placeholder with a real email or UC group name.

# COMMAND ----------

# Uncomment and replace GRANTEE to grant EXECUTE to a colleague or service principal
GRANTEE = "your-colleague@company.com.au"  # TODO: replace this

# spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.calculate_peak_demand TO `{GRANTEE}`")
# spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.get_meter_readings_summary TO `{GRANTEE}`")
# spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.lookup_asset_status TO `{GRANTEE}`")
# print(f"EXECUTE granted to: {GRANTEE}")
# print("Their agents can now call these tools. Invocations tracked in system.access.audit.")

print(f"GRANTEE is set to: {GRANTEE}")
print("Uncomment the GRANT lines above and re-run to apply.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Testing a UC Function Directly in Catalog Explorer
# MAGIC </div>
# MAGIC
# MAGIC You can run UC functions interactively from the UI without writing any code:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Data → Catalog → workshop_au → workshop_lab → Functions
# MAGIC   → Click calculate_peak_demand
# MAGIC   → Click the "Run" tab (top-right of the function detail panel)
# MAGIC
# MAGIC Fill in the parameter form:
# MAGIC   nmi:        6001234567
# MAGIC   start_date: 2024-07-01
# MAGIC   end_date:   2024-07-07
# MAGIC
# MAGIC Click Run → the result JSON appears inline
# MAGIC
# MAGIC ┌─── Function: calculate_peak_demand ─────────────────────────┐
# MAGIC │  Parameters          Run                                    │
# MAGIC │  ─────────────────────────────────────────────────────────  │
# MAGIC │  nmi:        [6001234567              ]                     │
# MAGIC │  start_date: [2024-07-01              ]                     │
# MAGIC │  end_date:   [2024-07-07              ]                     │
# MAGIC │                                    [Run]                    │
# MAGIC │                                                             │
# MAGIC │  Result:                                                    │
# MAGIC │  {"nmi": "6001234567", "peak_kwh": 2.49, ...}              │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC This is the fastest way to debug a function before building an agent around it.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.8 — Wire UC functions to a LangChain agent
# MAGIC
# MAGIC Now load the three registered functions as tools and build an agent that
# MAGIC decides autonomously which function to call.

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks_langchain import UCFunctionToolkit, ChatDatabricks
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

w = WorkspaceClient()

# Load the three UC functions as LangChain tools
# UCFunctionToolkit reads each function's COMMENT and parameters from the catalog
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
    # Print the LangChain name (dots replaced with __ per the naming convention)
    print(f"  {t.name}")
    print(f"    └─ {t.description[:90]}...")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Loaded 3 tools:
# MAGIC   workshop_au__workshop_lab__calculate_peak_demand
# MAGIC     └─ Calculate the peak 30-minute demand (kWh) for a given NEM meter over a date range...
# MAGIC   workshop_au__workshop_lab__get_meter_readings_summary
# MAGIC     └─ Get a completeness and quality summary of interval readings for a NMI on a given date...
# MAGIC   workshop_au__workshop_lab__lookup_asset_status
# MAGIC     └─ Look up the year-to-date maintenance history and operational status of a network asset...
# MAGIC ```
# MAGIC
# MAGIC Note the `__` separator (double underscore) in the tool names — this is the LangChain
# MAGIC convention for UC function identifiers. You will see this in verbose agent traces and
# MAGIC MLflow.

# COMMAND ----------

# Build the LLM — Claude via Databricks Provisioned Throughput (AU East in-region)
llm = ChatDatabricks(
    endpoint=PT_ENDPOINT,
    temperature=0.0,
    max_tokens=2048,
)

system_prompt = """You are an energy operations assistant for an Australian electricity network operator.
You have access to three tools that query live operational data in Unity Catalog:

- calculate_peak_demand: find the peak 30-minute demand for a NEM meter over a date range
- get_meter_readings_summary: check data completeness and NEM12 quality for a meter on a specific date
- lookup_asset_status: retrieve year-to-date maintenance history for a network asset

Rules:
- Always use the tools to answer questions about specific meters or assets — do not guess values
- Format numbers clearly: use kWh for energy, minutes for outage duration, AUD for costs
- Reference Australian regulatory frameworks where relevant (AER, AEMO, NERR)
- When a tool returns an error JSON, explain the issue clearly in plain language
- Use DD/MM/YYYY format when writing dates in your response"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,    # Shows tool call decisions in real time
    max_iterations=6,
)

print("Agent ready — verbose=True shows which tools the LLM calls and with what arguments.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Agent ready — verbose=True shows which tools the LLM calls and with what arguments.
# MAGIC ```

# COMMAND ----------

# Question 1: Peak demand lookup
result = agent_executor.invoke({
    "input": "What was the peak demand for meter 6001234567 during the first week of July 2024?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected verbose trace + final answer:**
# MAGIC ```
# MAGIC > Entering new AgentExecutor chain...
# MAGIC
# MAGIC Invoking: `workshop_au__workshop_lab__calculate_peak_demand` with
# MAGIC   {'nmi': '6001234567', 'start_date': '2024-07-01', 'end_date': '2024-07-07'}
# MAGIC
# MAGIC > Finished chain.
# MAGIC
# MAGIC === AGENT RESPONSE ===
# MAGIC The peak demand for meter 6001234567 during 01/07/2024 to 07/07/2024 was 2.49 kWh
# MAGIC in a single 30-minute interval. This peak occurred on 04/07/2024 at approximately 17:00
# MAGIC (interval 35), which corresponds to the early evening demand peak typical of residential
# MAGIC NEM connections.
# MAGIC ```

# COMMAND ----------

# Question 2: Data quality check (AEMO submission readiness)
result = agent_executor.invoke({
    "input": "Check the data quality for meter 6001234567 on 3 July 2024. "
             "Is it ready for AEMO submission?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected response:**
# MAGIC ```
# MAGIC === AGENT RESPONSE ===
# MAGIC For NMI 6001234567 on 03/07/2024:
# MAGIC   - Total consumption: 54.1 kWh
# MAGIC   - Actual reads (A): 47 of 48 intervals
# MAGIC   - Estimated reads (E): 1 interval (2.1%)
# MAGIC   - Missing intervals: 0
# MAGIC   - Data quality: GOOD
# MAGIC
# MAGIC This dataset is ready for AEMO submission. The estimated read rate (2.1%) is below
# MAGIC the 5% threshold under the National Energy Retail Rules that triggers mandatory customer
# MAGIC notification. No action is required before submission.
# MAGIC ```

# COMMAND ----------

# Question 3: Asset status — multi-year view
result = agent_executor.invoke({
    "input": "What is the current maintenance status of asset TF-NSW-001? "
             "How many outage minutes has it caused this year and what has it cost?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# Question 4: Multi-tool — agent must call TWO tools to answer
# Watch the verbose trace for two separate Invoking: lines
result = agent_executor.invoke({
    "input": "For our weekly operations report: what was the peak demand on meter 6001234567 "
             "during the week of 1-7 July 2024, and does the maintenance history for asset "
             "TF-NSW-001 show any events that might explain unusual consumption in that period?"
})
print("\n=== AGENT RESPONSE ===")
print(result["output"])

# COMMAND ----------

# MAGIC %md
# MAGIC **What to observe in the verbose trace for Question 4:**
# MAGIC
# MAGIC ```
# MAGIC > Entering new AgentExecutor chain...
# MAGIC
# MAGIC Invoking: `workshop_au__workshop_lab__calculate_peak_demand` with
# MAGIC   {'nmi': '6001234567', 'start_date': '2024-07-01', 'end_date': '2024-07-07'}
# MAGIC
# MAGIC Invoking: `workshop_au__workshop_lab__lookup_asset_status` with
# MAGIC   {'asset_id': 'TF-NSW-001'}
# MAGIC
# MAGIC > Finished chain.
# MAGIC ```
# MAGIC
# MAGIC Two separate `Invoking:` lines = two tool calls. The LLM decided independently
# MAGIC which functions to call in order to answer the compound question. No hardcoding
# MAGIC of tool selection in your code — the LLM reads the COMMENT fields and reasons.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #2E4057; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.0em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   UI — Viewing Tool Calls in MLflow Traces
# MAGIC </div>
# MAGIC
# MAGIC After running the agent exercises, inspect every tool call in the MLflow trace viewer:
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar) → Experiments
# MAGIC   → Click your experiment (likely named after this notebook)
# MAGIC   → Click a run → click the "Traces" tab
# MAGIC
# MAGIC ┌─── MLflow Trace View ───────────────────────────────────────┐
# MAGIC │  Run: 03_adding_skills_tools                                │
# MAGIC │  ─────────────────────────────────────────────────────────  │
# MAGIC │  Traces (4)                                                  │
# MAGIC │  ├── AgentRun (1,847ms) — "What was the peak demand..."     │
# MAGIC │  │    ├── LLMCall  (521ms) — decides to call tool           │
# MAGIC │  │    ├── ToolCall: calculate_peak_demand (203ms)            │
# MAGIC │  │    │    ├── Input:  {nmi: "6001234567", ...}             │
# MAGIC │  │    │    └── Output: {"peak_kwh": 2.49, ...}             │
# MAGIC │  │    └── LLMCall  (318ms) — synthesises final answer       │
# MAGIC │  ├── AgentRun (2,441ms) — "Check the data quality..."       │
# MAGIC │  ├── AgentRun (2,103ms) — "What is the current maint..."    │
# MAGIC │  └── AgentRun (3,256ms) — "For our weekly ops report..."    │
# MAGIC │       ├── LLMCall  (412ms)                                  │
# MAGIC │       ├── ToolCall: calculate_peak_demand (198ms)           │
# MAGIC │       ├── ToolCall: lookup_asset_status (211ms)             │  ← two tool calls
# MAGIC │       └── LLMCall  (621ms)                                  │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC What to check in the trace:
# MAGIC   - Which tool did the LLM choose, and with what exact arguments?
# MAGIC   - How long did UC function execution take vs LLM inference?
# MAGIC   - For Question 4: did you see two ToolCall nodes in one run?
# MAGIC ```
# MAGIC
# MAGIC > MLflow tracing is automatic for `ChatDatabricks` + `AgentExecutor` —
# MAGIC > no extra instrumentation code is needed.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exercise 3.9 — Write your own UC function: `calculate_demand_statistics`
# MAGIC
# MAGIC Register a new UC function that:
# MAGIC - Takes `nmi` (STRING) and `month` (STRING, format `YYYY-MM`)
# MAGIC - Queries `interval_reads`, groups by `read_date` to compute daily totals
# MAGIC - Returns a JSON string with: `avg_daily_kwh`, `max_daily_kwh`, `min_daily_kwh`, `std_daily_kwh`, `month_total_kwh`
# MAGIC - Handles the case where no data is found gracefully
# MAGIC
# MAGIC **Tip:** Use Genie Code to scaffold this. Suggested prompt:
# MAGIC > *"Write a Databricks UC function called calculate_demand_statistics that takes nmi (STRING)
# MAGIC > and month (STRING, YYYY-MM format). Query workshop_au.workshop_lab.interval_reads,
# MAGIC > group by read_date to get daily totals, then return aggregate statistics as JSON.
# MAGIC > Include avg_daily_kwh, max_daily_kwh, min_daily_kwh, std_daily_kwh, month_total_kwh.
# MAGIC > Match the error-handling and return format style of the existing functions in this notebook.
# MAGIC > The COMMENT field should explain when an LLM should call this tool."*

# COMMAND ----------

# TODO: Register calculate_demand_statistics as a UC function

# Uncomment and fill in the body:

# spark.sql(f"""
# CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.calculate_demand_statistics(
#     nmi   STRING COMMENT '...',
#     month STRING COMMENT 'Analysis month in YYYY-MM format (e.g., 2024-07)'
# )
# RETURNS STRING
# COMMENT 'Calculate daily demand statistics for a NEM meter over a calendar month.
# Returns JSON with avg_daily_kwh, max_daily_kwh, min_daily_kwh, std_daily_kwh, month_total_kwh.
# Use when asked about demand variability, monthly consumption statistics, or load profiling for a meter.'
# LANGUAGE PYTHON
# AS $$
# import json
# try:
#     from pyspark.sql import SparkSession
#     from pyspark.sql import functions as F
#     import math
#     spark = SparkSession.builder.getOrCreate()
#     # ... your implementation here ...
# except Exception as e:
#     return json.dumps({"error": str(e)})
# $$
# """)

# Then reload the toolkit and rebuild the agent to include the new function:
# toolkit_v2 = UCFunctionToolkit(
#     tools_names=[
#         f"{CATALOG}.{SCHEMA}.calculate_peak_demand",
#         f"{CATALOG}.{SCHEMA}.get_meter_readings_summary",
#         f"{CATALOG}.{SCHEMA}.lookup_asset_status",
#         f"{CATALOG}.{SCHEMA}.calculate_demand_statistics",
#     ]
# )
# tools_v2 = toolkit_v2.get_tools()
# agent_v2 = create_tool_calling_agent(llm, tools_v2, prompt)
# agent_executor_v2 = AgentExecutor(agent=agent_v2, tools=tools_v2, verbose=True)
# result = agent_executor_v2.invoke({"input": "What were the demand stats for meter 6001234567 in July 2024?"})
# print(result["output"])

print("Exercise 3.9: Implement calculate_demand_statistics — uncomment and fill in the body above.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Success criteria for Exercise 3.9:**
# MAGIC - `SELECT workshop_au.workshop_lab.calculate_demand_statistics('6001234567', '2024-07')` returns valid JSON
# MAGIC   with all five statistical fields
# MAGIC - The agent answers "What were the demand statistics for meter 6001234567 in July 2024?"
# MAGIC   using the new tool (visible as a `ToolCall` node in the MLflow trace)
# MAGIC - The COMMENT field explains *when* to call the tool, not just *what* it computes

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.1em; font-weight: bold; margin: 24px 0 4px 0;">
# MAGIC   Section 4 — Putting It Together: Skills + Tools in Agent Mode
# MAGIC </div>
# MAGIC <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 0 6px 6px 0; margin-bottom: 16px;">
# MAGIC   Estimated time: 10 minutes
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### The full picture — all three working together
# MAGIC
# MAGIC This section demonstrates how Custom Instructions, Skills, and Tools operate
# MAGIC simultaneously in an Agent mode conversation.
# MAGIC
# MAGIC ```
# MAGIC User query: "Using your energy operations knowledge, calculate the peak demand for VIC
# MAGIC              in Q1 2025 and explain if this is above or below normal for that region."
# MAGIC
# MAGIC ┌──────────────────────────────────────────────────────────────────────┐
# MAGIC │  Step 1: Custom Instructions (always loaded)                        │
# MAGIC │  → Agent knows: NEM12 format, SAIDI formula, quality flags,         │
# MAGIC │    AU date format, Delta Lake preference                             │
# MAGIC │                                                                      │
# MAGIC │  Step 2: @energy-operations Skill (loaded on demand)                │
# MAGIC │  → Agent reads: SAIDI calc, quality flag reference table,           │
# MAGIC │    NMI format reference, AER report date conventions                 │
# MAGIC │                                                                      │
# MAGIC │  Step 3: calculate_peak_demand Tool (executes real code)            │
# MAGIC │  → Queries interval_reads Delta table                               │
# MAGIC │  → Returns: {"peak_kwh": 2.49, "peak_date": "2025-01-15", ...}     │
# MAGIC │                                                                      │
# MAGIC │  Step 4: LLM synthesises the answer                                 │
# MAGIC │  → Uses domain context from instructions + skill                    │
# MAGIC │  → Grounds the number from the tool call                            │
# MAGIC │  → Interprets the result in regulatory context                      │
# MAGIC └──────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC None of these three steps replace each other:
# MAGIC - Custom Instructions give persistent vocabulary — but cannot run code
# MAGIC - Skills give deep reference knowledge — but only when loaded, and cannot run code
# MAGIC - Tools give live data — but they return raw JSON with no domain interpretation by themselves

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 — Capstone: Agent mode with explicit skill invocation
# MAGIC
# MAGIC Open the Genie Code chat panel (sparkle icon, top right).
# MAGIC Switch to **Agent mode** using the mode selector in the chat input bar.
# MAGIC
# MAGIC Then try this conversation sequence:
# MAGIC
# MAGIC ```
# MAGIC ┌─── Genie Code — Agent Mode ──────────────────────────────────────────┐
# MAGIC │                                                                      │
# MAGIC │  You: @energy-operations Using your energy operations knowledge,     │
# MAGIC │       calculate the peak demand for NMI 6001234567 in July 2024     │
# MAGIC │       and explain whether 17:00 is a typical peak time for a VIC    │
# MAGIC │       residential NMI.                                               │
# MAGIC │                                                                      │
# MAGIC │  Expected agent flow:                                                │
# MAGIC │    1. Loads @energy-operations skill (domain knowledge)              │
# MAGIC │    2. Calls workshop_au.workshop_lab.calculate_peak_demand tool      │
# MAGIC │       with nmi='6001234567', start_date='2024-07-01',               │
# MAGIC │       end_date='2024-07-31'                                          │
# MAGIC │    3. Reads result: {"peak_kwh": 2.49, "peak_time_approx": "17:00"} │
# MAGIC │    4. Synthesises: "17:00 falls within the standard evening peak    │
# MAGIC │       window (17:00-20:00 AEST) typical of residential VIC NMIs.   │
# MAGIC │       The 2.5x demand multiplier applied by the sample data         │
# MAGIC │       generator confirms this pattern is expected."                  │
# MAGIC │                                                                      │
# MAGIC └──────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC > **Why the result is more useful than tool-only or skill-only:**
# MAGIC > The tool provides the grounded number (2.49 kWh at 17:00).
# MAGIC > The skill provides the interpretation framework (17:00 is in the standard peak window).
# MAGIC > The custom instructions ensure the response uses Australian terminology and DD/MM/YYYY format.
# MAGIC > Without all three, you would get either a number with no context, or context with no number.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — Multi-turn conversation using all three layers
# MAGIC
# MAGIC Continue in the same Genie Code Agent mode session. The agent remembers the
# MAGIC previous exchange within a session.
# MAGIC
# MAGIC ```
# MAGIC Turn 1 (peak demand + skill context — done in 4.1 above):
# MAGIC   You:   @energy-operations calculate the peak demand for NMI 6001234567 in July 2024
# MAGIC   Agent: [calls calculate_peak_demand, reads skill, synthesises answer]
# MAGIC
# MAGIC Turn 2 (data quality — different tool, same session):
# MAGIC   You:   Now check the data quality for that meter on the date the peak occurred.
# MAGIC          Was the reading actual or estimated?
# MAGIC   Agent: [calls get_meter_readings_summary with the date from Turn 1 result]
# MAGIC          [answers using quality flag definitions from the skill already in context]
# MAGIC
# MAGIC Turn 3 (asset investigation — third tool):
# MAGIC   You:   Is there any maintenance history for asset TF-NSW-001 that might have
# MAGIC          affected supply to this meter in July 2024?
# MAGIC   Agent: [calls lookup_asset_status]
# MAGIC          [interprets result using asset type knowledge from the skill]
# MAGIC ```
# MAGIC
# MAGIC This is the pattern for a real operations review workflow — an analyst asking
# MAGIC progressively deeper questions, with the agent maintaining context and choosing
# MAGIC the right tool for each step.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Understanding what each layer contributes
# MAGIC
# MAGIC Run this cell to print a quick summary that you can copy into your notes or
# MAGIC share with the team as a reference card.

# COMMAND ----------

summary = """
╔══════════════════════════════════════════════════════════════════════════════╗
║       Genie Code Extension Patterns — Quick Reference                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  CUSTOM INSTRUCTIONS                                                         ║
║  Path:     /Users/{email}/.assistant_instructions.md                        ║
║  Format:   Any markdown — no frontmatter required                            ║
║  Loads:    Every session, automatically                                      ║
║  Use for:  Terminology, coding preferences, regulatory context               ║
║  Tip:      Keep concise — it uses tokens on every single message            ║
║                                                                              ║
║  AGENTS.md / CLAUDE.md                                                       ║
║  Path:     Any directory in your Workspace — Genie walks up from notebook   ║
║  Format:   Markdown — no frontmatter required                                ║
║  Loads:    When you are working in a notebook under that directory          ║
║  Use for:  Table names, NMIs, asset IDs, project-specific conventions       ║
║                                                                              ║
║  SKILLS                                                                      ║
║  Path:     /Users/{email}/.assistant/skills/{name}/SKILL.md                ║
║  Format:   Markdown WITH YAML frontmatter (name + description fields)       ║
║  Loads:    On demand — when query matches, or you use @skill-name           ║
║  Use for:  Deep reference guides, calculation methods, data dictionaries    ║
║  Tip:      Write description carefully — it drives auto-discovery           ║
║                                                                              ║
║  UC FUNCTION TOOLS                                                           ║
║  Location: Unity Catalog — catalog.schema.function_name                     ║
║  Requires: EXECUTE permission on the function                               ║
║  Runs:     Inside your workspace — no data leaves the region                ║
║  LangChain name: catalog__schema__function_name (dots → double underscore) ║
║  Use for:  Live queries, calculations, real data that changes over time     ║
║  Tip:      COMMENT field quality directly affects LLM tool-selection rate   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
print(summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 — Key decisions: which pattern to use?
# MAGIC
# MAGIC | Situation | What to use | Why |
# MAGIC |-----------|-------------|-----|
# MAGIC | Domain terminology the LLM should always know | Custom Instructions | Loaded every time, zero friction |
# MAGIC | A long reference guide (e.g., NEM12 field positions) | Skill | Too long for always-on instructions; loaded when needed |
# MAGIC | A formula that never changes (e.g., SAIDI) | Skill | Static knowledge, no code needed |
# MAGIC | The actual SAIDI value for this month | UC Function Tool | Requires querying live data |
# MAGIC | The latest asset status | UC Function Tool | Changes over time, needs real query |
# MAGIC | A calculation you always want done the same way | UC Function Tool | Codified logic, version-controlled, auditable |
# MAGIC | Context specific to one project directory | AGENTS.md | Scoped, does not pollute global instructions |
# MAGIC | Context for the whole team in the workspace | Workspace instructions | Admin sets once, applies to all users |
# MAGIC
# MAGIC ### Common mistakes to avoid
# MAGIC
# MAGIC | Mistake | Problem | Fix |
# MAGIC |---------|---------|-----|
# MAGIC | Putting table column names in Custom Instructions | Outdated if schema changes; tokens wasted every message | Put in AGENTS.md or a Skill instead |
# MAGIC | Skill with generic description: "Energy operations guide" | Genie cannot auto-match queries to it | Write description as a query: "Australian energy NEM12 quality flags SAIDI SAIFI AER" |
# MAGIC | UC function that raises an exception | Agent crashes with no useful error | Return `{"error": "..."}` and let LLM interpret |
# MAGIC | UC function COMMENT that only describes what it does | LLM doesn't know *when* to call it | Add a sentence: "Use this when asked about..." |
# MAGIC | Skills for data that changes daily | Stale data in context | Use a UC function that queries the live table |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 24px 28px; border-radius: 10px; margin-top: 24px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 03 Complete</h2>
# MAGIC   <p style="color: rgba(255,255,255,0.9); margin: 0 0 14px 0;">
# MAGIC     You built all three extension layers for Genie Code, wired them together in an
# MAGIC     agent that uses live Unity Catalog data, and saw how each layer contributes something
# MAGIC     the others cannot.
# MAGIC   </p>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; font-size: 0.97em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Custom Instructions</td>
# MAGIC       <td style="padding: 6px 10px;">Text loaded into every session — terminology, preferences, regulatory context</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Skills</td>
# MAGIC       <td style="padding: 6px 10px;">Markdown documents fetched on demand — deep reference guides, @invoked or auto-matched</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">UC Function Tools</td>
# MAGIC       <td style="padding: 6px 10px;">Executable code in Unity Catalog — live data, governed, audited, EXECUTE-gated</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">AGENTS.md</td>
# MAGIC       <td style="padding: 6px 10px;">Project-scoped context that Genie auto-discovers by walking up the directory tree</td>
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
