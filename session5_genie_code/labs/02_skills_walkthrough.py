# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 28px 32px; border-radius: 10px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 2em; font-family: 'DM Sans', sans-serif;">
# MAGIC     Lab 02: Skills Walkthrough
# MAGIC   </h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 1em;">
# MAGIC     Session 5: Extending Genie Code — AEMO Workshop · Australia East
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Duration</strong><br>30 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Lab 01 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Skills created</strong><br>energy-analytics, regulatory-compliance, genie-space-creator
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC ### What you will do
# MAGIC
# MAGIC | Step | Skill | Time |
# MAGIC |------|-------|------|
# MAGIC | 1 | Understand skills vs custom instructions | 5 min |
# MAGIC | 2 | Create `energy-analytics` skill | 7 min |
# MAGIC | 3 | Create `regulatory-compliance` skill | 8 min |
# MAGIC | 4 | Create `genie-space-creator` skill | 5 min |
# MAGIC | 5 | Test all three skills in Genie Code | 5 min |
# MAGIC
# MAGIC ### Skills vs custom instructions — the key difference
# MAGIC
# MAGIC | | Custom Instructions | Skills |
# MAGIC |-|---------------------|--------|
# MAGIC | Loaded | Every session, automatically | On demand — when query matches or you type `@skill-name` |
# MAGIC | Best for | Short domain context (< 2,000 chars) | Long reference guides, formulas, code patterns |
# MAGIC | Discovery | Always active | Auto-matched by keyword OR explicit `@name` invocation |
# MAGIC | Token cost | Paid every conversation | Paid only when loaded |
# MAGIC | Format | Plain Markdown | `SKILL.md` with YAML front-matter `description:` field |
# MAGIC
# MAGIC > **The `description` field is critical.** Genie Code reads the description to decide whether to load the skill.
# MAGIC > Write it as the exact phrases someone would use when they need this skill —
# MAGIC > not what the skill IS, but what they would SAY.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Skill Storage Paths
# MAGIC
# MAGIC Skills are `SKILL.md` files inside named folders. Two locations:
# MAGIC
# MAGIC | Location | Path | Visible to |
# MAGIC |----------|------|-----------|
# MAGIC | Personal | `/Users/{email}/.assistant/skills/{skill-name}/SKILL.md` | You only |
# MAGIC | Workspace | `Workspace/.assistant/skills/{skill-name}/SKILL.md` | All users (admin sets) |
# MAGIC
# MAGIC Genie Code scans both locations and merges the skill list. If a personal and workspace skill share the same name, personal wins.

# COMMAND ----------

username = spark.sql("SELECT current_user()").collect()[0][0]
skills_base = f"/Users/{username}/.assistant/skills"
print(f"Skills base path: {skills_base}")
print(f"\nThree skills we will create:")
print(f"  {skills_base}/energy-analytics/SKILL.md")
print(f"  {skills_base}/regulatory-compliance/SKILL.md")
print(f"  {skills_base}/genie-space-creator/SKILL.md")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Skill 1: `energy-analytics`
# MAGIC
# MAGIC This skill gives Genie Code deep NEM market knowledge: SAIDI/SAIFI/CAIDI formulas,
# MAGIC spot price ranges, region codes, and ready-to-use SQL patterns for the AEMO workshop tables.
# MAGIC
# MAGIC **When it loads:** any question mentioning SAIDI, SAIFI, CAIDI, spot price, dispatch, LOR, or NEM analysis.

# COMMAND ----------

energy_analytics_skill = """---
name: energy-analytics
description: Australian energy market metrics — SAIDI/SAIFI/CAIDI calculations, NEM dispatch analysis, spot price statistics, LOR events, and AER performance benchmarks for AEMO operations
---

# Energy Analytics for AEMO

## Key Reliability Metrics

### SAIDI (System Average Interruption Duration Index)
Formula: SAIDI = Σ(interruption_duration_min × customers_affected) / total_customers
AER benchmark: typically < 25 minutes/year for urban networks; varies by network zone
Interpretation: lower is better — represents minutes of outage per customer per year
SQL pattern:
```sql
SELECT
    region,
    SUM(duration_minutes * affected_customers) / MAX(total_customers) AS saidi_minutes
FROM workshop_au.energy.outage_events
WHERE YEAR(start_time) = YEAR(CURRENT_DATE)
GROUP BY region
```

### SAIFI (System Average Interruption Frequency Index)
Formula: SAIFI = Σ(interruptions × customers_affected) / total_customers
AER benchmark: typically < 1.0 interruption/year for urban networks
SQL pattern:
```sql
SELECT
    region,
    COUNT(*) * AVG(affected_customers) / MAX(total_customers) AS saifi
FROM workshop_au.energy.outage_events
WHERE YEAR(start_time) = YEAR(CURRENT_DATE)
GROUP BY region
```

### CAIDI (Customer Average Interruption Duration Index)
Formula: CAIDI = SAIDI / SAIFI (= average minutes per interruption event)
Interpretation: lower = faster restoration; high CAIDI with low SAIFI = few but long outages

## NEM Spot Price Reference

| Metric | Value |
|--------|-------|
| Market Price Cap (MPC) | $15,300/MWh |
| Market Floor Price | -$1,000/MWh |
| Cumulative Price Threshold (CPT) | $254,900 over any 7-day rolling window |
| Typical off-peak range | $50–$120/MWh |
| High price event threshold | > $300/MWh |
| Administered Price Cap (APC) | $300/MWh — activates after CPT breach |

## Region Code Reference
NSW1, VIC1, QLD1, SA1, TAS1 — always use these exact identifiers in queries and text.

## Common SQL Patterns

### Daily average price by region
```sql
SELECT
    region_id,
    DATE(settlement_date)     AS trade_date,
    AVG(rrp)                  AS avg_price_mwh,
    MAX(rrp)                  AS max_price_mwh,
    MIN(rrp)                  AS min_price_mwh,
    COUNT(*)                  AS intervals
FROM workshop_au.aemo.spot_prices
WHERE region_id = 'VIC1'
GROUP BY region_id, DATE(settlement_date)
ORDER BY trade_date DESC
```

### Top dispatched generators (by fuel type)
```sql
SELECT
    gr.fuel_type,
    di.duid,
    gr.station_name,
    SUM(di.dispatch_mw)       AS total_mw,
    AVG(di.dispatch_mw)       AS avg_mw,
    COUNT(*)                  AS dispatch_intervals
FROM workshop_au.aemo.dispatch_intervals di
JOIN workshop_au.aemo.generator_registration gr USING (duid)
WHERE di.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY gr.fuel_type, di.duid, gr.station_name
ORDER BY total_mw DESC
```

### LOR event summary
```sql
SELECT
    notice_type,    -- LOR1 / LOR2 / LOR3
    region_id,
    COUNT(*)       AS event_count,
    MIN(issue_time)  AS earliest_notice,
    MAX(issue_time)  AS latest_notice
FROM workshop_au.aemo.market_notices
WHERE notice_type LIKE 'LOR%'
  AND issue_time >= CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY notice_type, region_id
ORDER BY notice_type, region_id
```

## 5-Minute Dispatch vs 30-Minute Settlement
As of October 2021, AEMO moved to 5-minute settlement (5MS).
- dispatch_intervals table: 5-minute resolution (288 records/day per DUID)
- spot_prices table: 30-minute trading intervals (48 records/day per region) — pre-5MS format retained for backward compatibility in this dataset
"""

skill_path = f"{skills_base}/energy-analytics/SKILL.md"
dbutils.fs.put(skill_path, energy_analytics_skill, overwrite=True)
print(f"Created: {skill_path}")
print(f"Size   : {len(energy_analytics_skill):,} characters")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Verify the skill file

# COMMAND ----------

content = dbutils.fs.head(skill_path)
front_matter_end = content.find("---", 4)
print("--- YAML front-matter (what Genie reads for discovery) ---")
print(content[:front_matter_end + 3])
print(f"\n--- Full skill: {len(content):,} characters ---")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Test `energy-analytics` in Genie Code
# MAGIC
# MAGIC Open the Genie Code panel. Try the following prompts:
# MAGIC
# MAGIC **Prompt 1 — auto-discovery:**
# MAGIC ```
# MAGIC What was the average spot price in VIC1 last week? Show me the SQL.
# MAGIC ```
# MAGIC Expected: Genie auto-loads the skill (look for "Using skill: energy-analytics" in the panel)
# MAGIC and generates a query using `workshop_au.aemo.spot_prices` with `region_id = 'VIC1'`.
# MAGIC
# MAGIC **Prompt 2 — explicit invocation:**
# MAGIC ```
# MAGIC @energy-analytics Calculate SAIDI for SA1 for this year. Our network has 180,000 customers.
# MAGIC ```
# MAGIC Expected: Genie loads the skill via `@` prefix and generates the SAIDI SQL from the formula section.
# MAGIC
# MAGIC **Prompt 3 — price context:**
# MAGIC ```
# MAGIC We had a spot price of $12,500/MWh in QLD1 yesterday. Is that unusual? What are the regulatory thresholds?
# MAGIC ```
# MAGIC Expected: Genie references the spot price reference table from the skill — notes that $12,500 is below
# MAGIC the $15,300 MPC but above the CPT trigger conditions.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Skill 2: `regulatory-compliance`
# MAGIC
# MAGIC This skill gives Genie Code awareness of AEMO's specific regulatory obligations under the SOCI Act,
# MAGIC Privacy Act, and AER performance schemes — and provides compliance-oriented SQL patterns.
# MAGIC
# MAGIC **When it loads:** any mention of SOCI Act, Privacy Act, AER, compliance, NER, STPIS, obligations.

# COMMAND ----------

regulatory_compliance_skill = """---
name: regulatory-compliance
description: AEMO and AER regulatory compliance context — SOCI Act critical infrastructure obligations, Privacy Act NMI data handling, NER Chapter 7 retention, STPIS incentive scheme, and compliance SQL patterns for AEMO operations
---

# AEMO Regulatory Compliance Context

## SOCI Act 2018 (Security of Critical Infrastructure)
AEMO is designated as a critical infrastructure entity under the SOCI Act 2018.
Responsible entity: Australian Signals Directorate (ASD) for cybersecurity incidents.

### Incident reporting obligations
| Severity | Timeframe | Description |
|----------|-----------|-------------|
| Critical | 12 hours | Attack or incident affecting operational continuity of electricity market |
| Significant | 72 hours | Cybersecurity incident with material impact on AEMO systems |
| Periodic | Annually | System security plan update submitted to ASD |

### Data handling requirements
- Operational technology (OT) data must remain in Australia — use Azure Australia East exclusively
- Any external data transfer of market-sensitive data requires AEMO governance approval
- AI model inference on NEM operational data: must use in-region endpoints (AU East)

## Privacy Act 1988 — NMI Data
NMIs linked to physical addresses, account holders, or consumption patterns are personal information.
AEMO obligations as data holder:

| Principle | Obligation |
|-----------|-----------|
| APP 6 — use and disclosure | NMI data used only for market operations and billing — not analytics without consent |
| APP 11 — security | Reasonable steps to protect NMI data from misuse, loss, or unauthorised access |
| APP 12 — access | Customers can request access to their own NMI interval data |
| NER Chapter 7 | Meter data retention: minimum 7 years from date of reading |

### Anonymisation rule (for analytics)
NMI + address combinations are personal information. Aggregate to:
- Regional or network zone level for public reporting
- NMI level only for licensed data recipients (retailers, network businesses)

## AER Performance Obligations (STPIS)

### Service Target Performance Incentive Scheme (STPIS)
Financial incentives and penalties tied to SAIDI/SAIFI performance vs AER targets.
Applied to Transmission Network Service Providers (TNSPs) and Distribution NSPs (DNSPs).

| Network zone | Typical SAIDI target (urban) | Typical SAIFI target |
|--------------|------------------------------|----------------------|
| Urban | < 25 min/year | < 1.0/year |
| Short rural | < 80 min/year | < 1.5/year |
| Long rural | < 250 min/year | < 3.0/year |

### Major Event Day (MED) exclusions
Events caused by catastrophic weather conditions may be excluded from SAIDI/SAIFI calculations.
Threshold: daily SAIDI > median + 2.5 × standard deviation for that network zone.
Exclusions must be declared and submitted to AER within 30 business days.

## National Electricity Rules (NER) — Key Chapters for Data

| Chapter | Relevance |
|---------|-----------|
| Chapter 7 | Metering — NMI data, meter agent obligations, 5MS |
| Chapter 4 | Scheduling and dispatch — DUID obligations |
| Chapter 6 | Economic regulation of distribution services (SAIDI/SAIFI reporting) |
| Chapter 6A | Economic regulation of transmission services |

## Compliance SQL Patterns

### SAIDI performance vs AER target
```sql
SELECT
    region,
    SUM(saidi_minutes)                                          AS total_saidi,
    25.0                                                        AS aer_target_urban,
    SUM(saidi_minutes) - 25.0                                   AS variance,
    CASE
        WHEN SUM(saidi_minutes) < 25 THEN 'COMPLIANT'
        WHEN SUM(saidi_minutes) < 30 THEN 'WITHIN TOLERANCE'
        ELSE 'REVIEW REQUIRED'
    END                                                         AS compliance_status
FROM workshop_au.energy.outage_events
WHERE YEAR(start_time) = YEAR(CURRENT_DATE)
  AND is_major_event_day = FALSE   -- MED exclusion applied
GROUP BY region
```

### NMI data retention audit (7-year rule)
```sql
SELECT
    MIN(read_date)                                              AS oldest_record,
    MAX(read_date)                                             AS latest_record,
    DATEDIFF(CURRENT_DATE, MIN(read_date)) / 365.25             AS retention_years,
    CASE
        WHEN DATEDIFF(CURRENT_DATE, MIN(read_date)) / 365.25 >= 7 THEN 'RETENTION MET'
        ELSE 'CHECK ARCHIVING POLICY'
    END                                                         AS ner_chapter7_status
FROM workshop_au.aemo.interval_reads
```

### AI model inference compliance check
For any AI workload on AEMO data, verify the inference endpoint is in-region:
```python
# Confirm endpoint is Australia East before running inference on NEM data
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
endpoint = w.serving_endpoints.get("au_east_llm_inregion")
# Expected: config.traffic_config shows Azure Australia East deployment
```
"""

skill_path = f"{skills_base}/regulatory-compliance/SKILL.md"
dbutils.fs.put(skill_path, regulatory_compliance_skill, overwrite=True)
print(f"Created: {skill_path}")
print(f"Size   : {len(regulatory_compliance_skill):,} characters")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Test `regulatory-compliance` in Genie Code
# MAGIC
# MAGIC **Prompt 1 — explicit invocation:**
# MAGIC ```
# MAGIC @regulatory-compliance What are AEMO's SOCI Act obligations for AI systems processing NEM data?
# MAGIC ```
# MAGIC Expected: Genie loads the skill via `@` and returns the SOCI Act section covering
# MAGIC incident reporting timelines, data residency requirement (AU East), and the AI inference note.
# MAGIC
# MAGIC **Prompt 2 — compliance check query:**
# MAGIC ```
# MAGIC Write a query to check if our SAIDI performance is compliant with AER targets for urban networks.
# MAGIC Exclude major event days.
# MAGIC ```
# MAGIC Expected: Genie generates the SAIDI compliance SQL with the 25-minute urban target,
# MAGIC MED exclusion filter, and three-tier compliance status.
# MAGIC
# MAGIC **Prompt 3 — NMI privacy question:**
# MAGIC ```
# MAGIC Can we include NMI-level consumption data in our public sustainability report?
# MAGIC ```
# MAGIC Expected: Genie surfaces APP 6 (use and disclosure) and recommends aggregating to
# MAGIC regional or network zone level for public reporting.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Skill 3: `genie-space-creator`
# MAGIC
# MAGIC This skill gives Genie Code the patterns to create and configure Genie Spaces via the REST API —
# MAGIC including AEMO-specific space instructions templates, golden query patterns, and permission conventions.
# MAGIC
# MAGIC **When it loads:** any question about creating a Genie Space, Genie Space API, golden queries, Genie configuration.

# COMMAND ----------

genie_space_creator_skill = """---
name: genie-space-creator
description: Create and configure Databricks Genie Spaces via the REST API — setup steps, AEMO space instructions template, golden query patterns, and permission settings for energy sector NL-to-SQL data exploration
---

# Genie Space Creation for AEMO Energy Data

## Quick Setup Pattern (REST API)

### Step 1 — Create the space
```python
from databricks.sdk import WorkspaceClient
import json

w = WorkspaceClient()

space = w.api_client.do(
    "POST",
    "/api/2.0/genie/spaces",
    body={
        "title": "AEMO NEM Operations",
        "warehouse_id": "<your-sql-warehouse-id>",
        "description": "NL-to-SQL access to NEM spot prices, dispatch, and market notices",
        "instructions": '''This Genie Space provides access to AEMO NEM operational data.

REGION CODES: Always use NSW1, VIC1, QLD1, SA1, TAS1 (never NSW, VIC, etc.)
PRICES: Express in $/MWh. Market price cap is $15,300/MWh. Floor is -$1,000/MWh.
ENERGY: Express in MWh or GWh (not MW unless discussing capacity).
DATES: Use YYYY-MM-DD for query filters. Display dates as DD/MM/YYYY in results.
LOR events: LOR1 = watch, LOR2 = threatened, LOR3 = imminent lack of reserve.
SAIDI = minutes of outage per customer per year (lower is better).

Available tables:
- workshop_au.aemo.spot_prices (30-min interval, column rrp = $/MWh)
- workshop_au.aemo.dispatch_intervals (5-min generator dispatch by DUID)
- workshop_au.aemo.market_notices (LOR and intervention events)
- workshop_au.aemo.generator_registration (DUID metadata, fuel_type, capacity)'''
    }
)
space_id = space["space_id"]
print(f"Created Genie Space: {space_id}")
```

### Step 2 — Add tables
```python
tables = [
    "workshop_au.aemo.spot_prices",
    "workshop_au.aemo.dispatch_intervals",
    "workshop_au.aemo.market_notices",
    "workshop_au.aemo.generator_registration",
]
for table in tables:
    w.api_client.do(
        "POST",
        f"/api/2.0/genie/spaces/{space_id}/datasets",
        body={"table_name": table}
    )
    print(f"  Added: {table}")
```

### Step 3 — Add golden queries (5 minimum recommended by AEMO)
```python
golden_queries = [
    {
        "name": "Average spot price by region last 7 days",
        "question": "What was the average spot price by region over the last 7 days?",
        "sql": '''SELECT region_id, ROUND(AVG(rrp), 2) AS avg_price_mwh
FROM workshop_au.aemo.spot_prices
WHERE settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY region_id ORDER BY avg_price_mwh DESC'''
    },
    {
        "name": "Top generators by dispatch last week",
        "question": "Which generators dispatched the most electricity last week?",
        "sql": '''SELECT di.duid, gr.station_name, gr.fuel_type,
    ROUND(SUM(di.dispatch_mw) / 1000, 1) AS total_gwh
FROM workshop_au.aemo.dispatch_intervals di
JOIN workshop_au.aemo.generator_registration gr USING (duid)
WHERE di.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY di.duid, gr.station_name, gr.fuel_type
ORDER BY total_gwh DESC LIMIT 10'''
    },
    {
        "name": "High price events this month",
        "question": "How many high price events above $300/MWh occurred this month?",
        "sql": '''SELECT region_id, COUNT(*) AS high_price_intervals,
    ROUND(MAX(rrp), 2) AS peak_price_mwh
FROM workshop_au.aemo.spot_prices
WHERE rrp > 300
  AND DATE_TRUNC('month', settlement_date) = DATE_TRUNC('month', CURRENT_DATE)
GROUP BY region_id ORDER BY high_price_intervals DESC'''
    },
    {
        "name": "LOR events last 30 days",
        "question": "Show me all LOR events in the last 30 days",
        "sql": '''SELECT notice_id, notice_type, region_id, issue_time, effective_date,
    LEFT(reason, 250) AS reason_preview
FROM workshop_au.aemo.market_notices
WHERE notice_type LIKE 'LOR%'
  AND issue_time >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY issue_time DESC'''
    },
    {
        "name": "Renewable vs fossil fuel dispatch mix",
        "question": "What is the renewable vs fossil fuel dispatch mix this week?",
        "sql": '''SELECT
    CASE WHEN gr.fuel_type IN ('WIND','SOLAR','HYDRO','BIOMASS') THEN 'Renewable'
         ELSE 'Fossil / Other' END AS generation_type,
    gr.fuel_type,
    ROUND(SUM(di.dispatch_mw) / 1000, 1) AS total_gwh
FROM workshop_au.aemo.dispatch_intervals di
JOIN workshop_au.aemo.generator_registration gr USING (duid)
WHERE di.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY generation_type, gr.fuel_type
ORDER BY total_gwh DESC'''
    },
]

for gq in golden_queries:
    w.api_client.do(
        "POST",
        f"/api/2.0/genie/spaces/{space_id}/sql-queries",
        body={
            "name":        gq["name"],
            "description": gq["question"],
            "query":       gq["sql"],
        }
    )
    print(f"  Added golden query: {gq['name']}")
```

### Step 4 — Set permissions
```python
# CAN_VIEW for analysts, CAN_EDIT for data engineers
permissions = [
    {"user_name": "analyst@aemo.com.au",       "permission_level": "CAN_VIEW"},
    {"user_name": "data-engineer@aemo.com.au", "permission_level": "CAN_EDIT"},
    {"group_name": "aemo-analysts",            "permission_level": "CAN_VIEW"},
]
for p in permissions:
    w.api_client.do(
        "PUT",
        f"/api/2.0/permissions/genie/spaces/{space_id}",
        body={"access_control_list": [p]}
    )
print("Permissions set.")
```

## Genie Space Instructions Writing Guide

Good instructions are short, specific, and prescriptive. Three rules:
1. Tell Genie what to use ("region_id column") not what NOT to use ("don't use region")
2. Include units and format expectations — Genie defaults to generic output otherwise
3. List table names explicitly — Genie will pick the most relevant one from the list

## MCP Endpoint for Genie Space
Once created, the space is accessible as an MCP server:
`https://{workspace-host}/api/2.0/mcp/genie/{space_id}`
Tools exposed: one `ask_question` tool that runs NL-to-SQL in the space.
See Lab 03 for how to connect this endpoint from a notebook.
"""

skill_path = f"{skills_base}/genie-space-creator/SKILL.md"
dbutils.fs.put(skill_path, genie_space_creator_skill, overwrite=True)
print(f"Created: {skill_path}")
print(f"Size   : {len(genie_space_creator_skill):,} characters")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Verify All Three Skills

# COMMAND ----------

import json

skill_names = ["energy-analytics", "regulatory-compliance", "genie-space-creator"]
print("Skill inventory:\n")
total_chars = 0
for name in skill_names:
    path = f"{skills_base}/{name}/SKILL.md"
    try:
        content = dbutils.fs.head(path)
        # Extract the description from the YAML front-matter
        lines = content.split("\n")
        desc_line = next((l for l in lines if l.startswith("description:")), "(not found)")
        size = len(content)
        total_chars += size
        print(f"  {name}")
        print(f"    Path   : {path}")
        print(f"    Size   : {size:,} chars")
        print(f"    Trigger: {desc_line.replace('description: ', '')[:80]}")
        print()
    except Exception as e:
        print(f"  {name}: ERROR — {e}\n")

print(f"Total across all skills: {total_chars:,} chars")
print(f"Remaining budget (20,000 total minus instructions): ~{20000 - total_chars:,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Live Demonstration in Genie Code
# MAGIC
# MAGIC Open the Genie Code panel (sparkle icon) and run these prompts in sequence.
# MAGIC Watch for the "Using skill:" indicator at the top of each response.
# MAGIC
# MAGIC ### Demonstration sequence
# MAGIC
# MAGIC **1. Auto-discovery — energy-analytics:**
# MAGIC ```
# MAGIC @energy-analytics What was the average spot price in VIC1 last week?
# MAGIC Write me the SQL and explain what the RRP column means.
# MAGIC ```
# MAGIC
# MAGIC **2. Auto-discovery — regulatory-compliance:**
# MAGIC ```
# MAGIC @regulatory-compliance Check our SAIDI performance against the AER urban target of 25 minutes.
# MAGIC Generate the SQL and mark each region as COMPLIANT or REVIEW REQUIRED.
# MAGIC ```
# MAGIC
# MAGIC **3. Genie Space creation — genie-space-creator:**
# MAGIC ```
# MAGIC Using @genie-space-creator, give me the Python code to create a Genie Space for our
# MAGIC NEM spot prices data with 3 golden queries: average price by region, high price events,
# MAGIC and a renewable vs fossil mix query.
# MAGIC ```
# MAGIC
# MAGIC **4. Multi-skill — both at once:**
# MAGIC ```
# MAGIC I need to build a Genie Space for our AER compliance reporting team.
# MAGIC The space should support SAIDI and SAIFI queries. What instructions should I put in the
# MAGIC space, and are there any regulatory constraints on who can access NMI-level data?
# MAGIC ```
# MAGIC Expected: Genie loads both `energy-analytics` (for SAIDI/SAIFI) and `regulatory-compliance`
# MAGIC (for NMI access rules) in the same response.

# COMMAND ----------

# MAGIC %md
# MAGIC ### What good skill output looks like
# MAGIC
# MAGIC | Indicator | Meaning |
# MAGIC |-----------|---------|
# MAGIC | "Using skill: energy-analytics" shown in panel | Auto-discovery worked — description matched the query |
# MAGIC | SQL uses `workshop_au.aemo.spot_prices` | Skill loaded its table path into context |
# MAGIC | Region filter uses `VIC1` not `VIC` | Skill's region code section was applied |
# MAGIC | Response cites `$15,300/MWh` price cap | Skill's price reference table was read |
# MAGIC | Compliance status shows `COMPLIANT` / `REVIEW REQUIRED` | Skill's SQL pattern was followed |
# MAGIC
# MAGIC ### Common issues and fixes
# MAGIC
# MAGIC | Issue | Likely cause | Fix |
# MAGIC |-------|-------------|-----|
# MAGIC | Skill not loaded automatically | `description:` too generic | Make description match exact phrases users will type |
# MAGIC | `@skill-name` not recognised | Folder or file name mismatch | Check `ls {skills_base}/` — folder name must match skill name |
# MAGIC | Skill loaded but wrong SQL | Skill content has syntax error | Validate SQL patterns in a notebook first |
# MAGIC | Two skills conflict | Both loaded; inconsistent guidance | Make descriptions non-overlapping; scope each skill narrowly |

# COMMAND ----------

summary = """
Skills installed:
  energy-analytics       → SAIDI/SAIFI/CAIDI, spot price ranges, NEM SQL patterns
  regulatory-compliance  → SOCI Act, Privacy Act, NER Chapter 7, STPIS, compliance SQL
  genie-space-creator    → REST API patterns, golden queries, permission setup, MCP endpoint

Discovery triggers (any matching phrase loads the skill automatically):
  energy-analytics       : SAIDI, SAIFI, CAIDI, spot price, RRP, dispatch, LOR, NEM analysis
  regulatory-compliance  : SOCI Act, Privacy Act, AER, compliance, NER, STPIS, obligations
  genie-space-creator    : Genie Space, create space, golden queries, NL-to-SQL, Genie API

Explicit invocation (always loads regardless of query):
  @energy-analytics <your question>
  @regulatory-compliance <your question>
  @genie-space-creator <your question>
"""
print(summary)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 20px 24px; border-radius: 10px; margin-top: 24px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 02 Complete — 30 minutes</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; font-size: 0.95em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold; width: 35%;">energy-analytics</td>
# MAGIC       <td style="padding: 6px 10px;">SAIDI/SAIFI formulas, price reference, 3 SQL patterns — auto-loads on NEM keywords</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">regulatory-compliance</td>
# MAGIC       <td style="padding: 6px 10px;">SOCI Act timelines, Privacy Act NMI rules, NER Chapter 7, STPIS benchmarks</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">genie-space-creator</td>
# MAGIC       <td style="padding: 6px 10px;">Full REST API pattern with tables, golden queries, permissions, and MCP endpoint note</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Key insight</td>
# MAGIC       <td style="padding: 6px 10px;">The <code style="color:#FF6B35;">description:</code> field is what Genie reads for auto-discovery — write it as trigger phrases</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 14px 0 0 0; font-weight: bold;">
# MAGIC     Next: Lab 03 — MCP Introduction (10 min)
# MAGIC   </p>
# MAGIC </div>
