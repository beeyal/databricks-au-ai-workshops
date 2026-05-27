# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 28px 36px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 02: Genie Space Admin — Deep Dive</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">Configuration Quality, Time-Series Awareness, Agent Mode, and Troubleshooting</p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="width:100%; border-collapse:collapse; margin-top:16px; font-family:'DM Sans',sans-serif;">
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px; width:25%"><b>Workshop</b></td><td style="padding:8px 16px;">Genie Spaces &amp; AI Features — Australian Regulated Industries</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Role</b></td><td style="padding:8px 16px;">Data Engineer / Platform Admin</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Prerequisites</b></td><td style="padding:8px 16px;">Lab 01 complete — <code>workshop_au.energy</code> tables exist and you have a <code>SPACE_ID</code></td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Objectives</b></td><td style="padding:8px 16px;">Enrich UC comments → add time-series instructions → add advanced golden queries → enable Agent mode → configure SharePoint/Drive connector → run health check</td></tr>
# MAGIC </table>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before the Code: UI Orientation
# MAGIC
# MAGIC Benchmark current accuracy before making changes so you can see the improvement.
# MAGIC
# MAGIC ```
# MAGIC Left sidebar → Genie → "NEM Grid Operations — Energy Analytics" → Chat tab
# MAGIC Ask: "What was the total energy consumption last month?"
# MAGIC      "Show me outages longer than 30 minutes this quarter"
# MAGIC Note any failures — Steps 2 and 3 fix time-series awareness.
# MAGIC
# MAGIC Then check column comments:
# MAGIC Left sidebar → Catalog → [catalog] → [schema] → meter_readings → Columns tab
# MAGIC Missing/thin comments = why Genie struggles with domain-specific questions.
# MAGIC ```

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests
from databricks.sdk import WorkspaceClient

# COMMAND ----------

# MAGIC %md
# MAGIC ### Workshop Configuration

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",         "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("genie_space_id", "",                     "Genie Space ID")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA         = dbutils.widgets.get("schema")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")

print(f"Using: {CATALOG}.{SCHEMA}  |  PT endpoint: {PT_ENDPOINT}")

# COMMAND ----------

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

# Genie Space ID — set in widget above (copy from Lab 01 output)
SPACE_ID = GENIE_SPACE_ID  # e.g. "01ef1234-abcd-5678-efgh-000000000001"

assert SPACE_ID, "Paste your Genie Space ID from Lab 01 into the 'genie_space_id' widget above."

def hdrs():
    t = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}

print(f"Connected : {HOST}")
print(f"Space ID  : {SPACE_ID}")
print(f"Schema    : {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 1 — Enrich UC Table and Column Comments</h2>
# MAGIC </div>
# MAGIC
# MAGIC Genie reads Unity Catalog metadata before generating SQL — good comments directly reduce hallucinated column names and wrong joins. To edit comments in the UI: Left sidebar → Catalog → [catalog] → [schema] → [table] → **Columns tab** → click the pencil icon next to any column → type comment → Save.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a — Enrich meter_readings via SQL (programmatic path)

# COMMAND ----------

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN quality_flag
    COMMENT 'NEM12 data confidence flag governing data quality.
Values: A=Actual (field reading — highest confidence),
        E=Estimated (based on historical patterns),
        S=Substituted (manual correction by DNSP),
        N=None (no reading available).
IMPORTANT: Exclude S and N from consumption totals unless specifically investigating data quality.
For reliable demand analysis use: WHERE quality_flag IN (''A'', ''E'').'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN interval_datetime
    COMMENT 'Start of the 30-minute measurement interval in AEST (UTC+10).
CRITICAL: Do NOT multiply by 2 to convert to hourly — use SUM over the window instead.
To aggregate: SUM(active_energy_kwh) grouped by DATE_TRUNC(''hour'', interval_datetime).
Example value: 2024-06-01T07:00:00 means the 7:00am-7:30am interval on 1 June 2024.'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN active_energy_kwh
    COMMENT 'Kilowatt-hours of active energy imported by the consumer during the 30-minute interval.
Typical residential range: 0.05–4.0 kWh per interval.
Daily kWh for a meter: SUM(active_energy_kwh) for a given NMI and calendar day.
Monthly MWh for a zone: SUM(active_energy_kwh) / 1000 grouped by month and distribution_zone.
Do NOT divide or multiply by 2 — the kWh value is already per-interval.'
""")

print("meter_readings comments updated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b — Enrich outages comments

# COMMAND ----------

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.outages
  ALTER COLUMN energy_not_served_mwh
    COMMENT 'Energy Not Served (ENS) in megawatt-hours for this outage event.
Calculation: estimated network demand at time of outage (MW) x outage duration (hours).
NULL means ENS was not calculated — this occurs for outages shorter than 1 minute.
Always use COALESCE(energy_not_served_mwh, 0) in SUM() aggregations to treat NULL as zero.
This metric is reported to AER as part of the STPIS incentive scheme annual submission.
Do NOT sum ENS across PLANNED outages for AER reporting — PLANNED outages are excluded.'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.outages
  ALTER COLUMN reported_to_aer
    COMMENT 'TRUE if this outage event met the AER threshold for SAIDI/SAIFI statistics.
Reporting threshold: any UNPLANNED outage affecting >= 1 customer for >= 1 minute.
PLANNED outages (scheduled maintenance) do NOT count toward SAIDI/SAIFI regulatory metrics.
Filter: WHERE reported_to_aer = TRUE AND outage_type = ''UNPLANNED'' for official AER calculations.'
""")

spark.sql(f"""
COMMENT ON TABLE {CATALOG}.{SCHEMA}.outages IS
'Network outage event log. One row = one continuous supply interruption event on one asset.
SAIDI formula: SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) x customers_affected) / total_ICPs.
SAIFI formula: SUM(customers_affected) / total_ICPs.
ALWAYS filter outage_type = UNPLANNED for AER regulatory metric calculations.'
""")

print("outages comments updated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c — Create a pre-computed SAIDI view (Genie can query views too)
# MAGIC
# MAGIC Pre-computing complex business metrics as a view is a powerful pattern: it eliminates an entire class of formula errors and speeds up Genie responses.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.v_saidi_monthly AS
-- Pre-calculated monthly SAIDI numerator per region
-- SAIDI (minutes) = SUM(interruption_minutes x customers_affected) / total_connected_customers
-- This view gives the NUMERATOR. Divide by your actual ICP count to get final SAIDI minutes.
SELECT
    region,
    DATE_TRUNC('month', start_time)                              AS month,
    COUNT(outage_id)                                             AS outage_count,
    SUM(customers_affected)                                      AS customer_interruptions,
    SUM(
        COALESCE(TIMESTAMPDIFF(MINUTE, start_time, end_time), 0)
        * customers_affected
    )                                                            AS saidi_numerator_minutes,
    SUM(COALESCE(energy_not_served_mwh, 0))                      AS ens_mwh
FROM {CATALOG}.{SCHEMA}.outages
WHERE outage_type = 'UNPLANNED'
  AND end_time IS NOT NULL
GROUP BY region, DATE_TRUNC('month', start_time)
""")

# Add the view as a trusted asset so Genie can query it
resp = requests.post(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/trusted-assets",
    headers=hdrs(),
    json={"asset_type": "TABLE", "asset_fqn": f"{CATALOG}.{SCHEMA}.v_saidi_monthly"}
)
print(f"v_saidi_monthly created and added as trusted asset: HTTP {resp.status_code}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 2 — Time-Series Awareness Configuration</h2>
# MAGIC </div>
# MAGIC
# MAGIC Without explicit guidance, Genie defaults to calendar year (Jan–Dec) rather than the Australian financial year (Jul–Jun), and may multiply 30-min kWh by 2 for hourly totals. This addendum to the instructions block fixes those behaviours.

# COMMAND ----------

TIMESERIES_INSTRUCTIONS_ADDENDUM = """

## Time-Series and Date Handling

### Australian Financial Year
- "This year" or "current year" = current Australian financial year (July 1 – June 30)
- "Last year" = previous Australian financial year
- FY2024 = July 1, 2023 to June 30, 2024
- SQL: WHERE start_time BETWEEN '2023-07-01' AND '2024-06-30' for FY2024

### Interval Data (meter_readings)
- Each row is a 30-MINUTE interval — NEVER multiply by 2 to get hourly kWh
- To get hourly: SUM(active_energy_kwh) WHERE interval_datetime >= hour AND interval_datetime < hour + 1 hour
- Peak demand proxy = MAX(active_energy_kwh * 2) for any single 30-min interval in a day (kW equivalent)
- Daily energy (kWh)  = SUM(active_energy_kwh) for that NMI and day
- Monthly energy (MWh) = SUM(active_energy_kwh) / 1000 for that NMI and month

### Peak vs Off-Peak (residential network tariff definition)
- Peak hours: 7am–11pm weekdays: HOUR(interval_datetime) BETWEEN 7 AND 22 AND DAYOFWEEK(interval_datetime) NOT IN (1,7)
- Off-peak: 11pm–7am and all day weekends

### Outage Duration
- Always express in hours: ROUND(TIMESTAMPDIFF(MINUTE, start_time, end_time) / 60, 1)

### Australian Seasons (Southern Hemisphere)
- Summer (peak demand season): December, January, February — MONTH(interval_datetime) IN (12, 1, 2)
- Autumn: March, April, May
- Winter (second demand peak, electric heating): June, July, August — MONTH(interval_datetime) IN (6, 7, 8)
- Spring: September, October, November
"""

# Fetch current instructions and append the time-series block
get_resp             = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=hdrs())
existing_instructions = get_resp.json().get("instructions", "")
updated_instructions  = existing_instructions + "\n" + TIMESERIES_INSTRUCTIONS_ADDENDUM

patch_resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs(),
    json={"instructions": updated_instructions.strip()}
)
print(f"Instructions updated: HTTP {patch_resp.status_code}")
print(f"Total instruction length: {len(updated_instructions):,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 3 — Advanced Golden Queries</h2>
# MAGIC </div>
# MAGIC
# MAGIC Lab 01 added 5 foundation queries. These cover the complex patterns — window functions, seasonal aggregations, and year-on-year comparisons — that most commonly trip up Genie without examples.

# COMMAND ----------

ADVANCED_GOLDEN_QUERIES = [
    {
        "name": "Peak demand days by zone — summer vs winter comparison",
        "description": "Top 5 peak demand days per distribution zone and season. Uses CTE + ROW_NUMBER. Used for network capacity planning.",
        "sql": f"""
WITH daily_peaks AS (
    SELECT
        distribution_zone,
        DATE(interval_datetime)                               AS reading_date,
        CASE
            WHEN MONTH(interval_datetime) IN (12, 1, 2) THEN 'SUMMER'
            WHEN MONTH(interval_datetime) IN (6, 7, 8)  THEN 'WINTER'
            ELSE 'SHOULDER'
        END                                                   AS season,
        MAX(active_energy_kwh * 2)                            AS peak_demand_kw,
        SUM(active_energy_kwh)                                AS daily_energy_kwh,
        COUNT(DISTINCT nmi)                                   AS active_meters
    FROM {CATALOG}.{SCHEMA}.meter_readings
    WHERE quality_flag IN ('A', 'E')
    GROUP BY distribution_zone, DATE(interval_datetime),
        CASE WHEN MONTH(interval_datetime) IN (12,1,2) THEN 'SUMMER'
             WHEN MONTH(interval_datetime) IN (6,7,8)  THEN 'WINTER'
             ELSE 'SHOULDER' END
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY distribution_zone, season ORDER BY peak_demand_kw DESC) AS rank_in_season
    FROM daily_peaks
)
SELECT distribution_zone, season, reading_date,
       ROUND(peak_demand_kw, 1) AS peak_demand_kw,
       ROUND(daily_energy_kwh, 0) AS daily_energy_kwh, active_meters
FROM ranked WHERE rank_in_season <= 5
ORDER BY distribution_zone, season, peak_demand_kw DESC
"""
    },
    {
        "name": "Assets overdue for maintenance inspection",
        "description": "IN_SERVICE assets with last_maintenance > 12 months ago, including outage count since last maintenance.",
        "sql": f"""
SELECT
    a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp, a.region, a.voltage_kv,
    a.last_maintenance,
    DATEDIFF(CURRENT_DATE, a.last_maintenance)          AS days_since_maintenance,
    COUNT(o.outage_id)                                  AS outages_since_maintenance,
    ROUND(SUM(COALESCE(o.energy_not_served_mwh, 0)), 2) AS ens_since_maintenance_mwh
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id AND o.start_time > a.last_maintenance
WHERE a.status = 'IN_SERVICE'
  AND a.last_maintenance < DATE_SUB(CURRENT_DATE, 365)
GROUP BY a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp, a.region, a.voltage_kv, a.last_maintenance
ORDER BY days_since_maintenance DESC
"""
    },
    {
        "name": "SAIDI year-to-date vs same period prior year by region",
        "description": "Year-on-year SAIDI comparison. Replace 1000000 with your actual ICP count.",
        "sql": f"""
-- TODO: replace 1000000 with actual ICP count from your customer register
WITH params AS (SELECT 1000000 AS total_icps),
current_year AS (
    SELECT region,
           SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_numerator
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED' AND reported_to_aer = TRUE AND end_time IS NOT NULL
      AND YEAR(start_time) = YEAR(CURRENT_DATE) AND MONTH(start_time) <= MONTH(CURRENT_DATE)
    GROUP BY region
),
prior_year AS (
    SELECT region,
           SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_numerator
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED' AND reported_to_aer = TRUE AND end_time IS NOT NULL
      AND YEAR(start_time) = YEAR(CURRENT_DATE) - 1 AND MONTH(start_time) <= MONTH(CURRENT_DATE)
    GROUP BY region
)
SELECT
    COALESCE(c.region, p.region)                                        AS region,
    ROUND(COALESCE(c.saidi_numerator, 0) / params.total_icps, 2)        AS saidi_ytd_minutes,
    ROUND(COALESCE(p.saidi_numerator, 0) / params.total_icps, 2)        AS saidi_prior_year_minutes,
    ROUND((COALESCE(c.saidi_numerator, 0) - COALESCE(p.saidi_numerator, 0))
          / NULLIF(p.saidi_numerator, 0) * 100, 1)                      AS pct_change_vs_prior_year
FROM current_year c
FULL OUTER JOIN prior_year p ON c.region = p.region
CROSS JOIN params
ORDER BY region
"""
    },
]

for q in ADVANCED_GOLDEN_QUERIES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=hdrs(),
        json={"name": q["name"], "description": q["description"], "query": q["sql"].strip()}
    )
    icon = "OK  " if resp.status_code in (200, 201) else f"ERROR {resp.status_code}: {resp.text[:60]}"
    print(f"  [{icon}]  {q['name']}")

print("\nAdvanced golden queries added. Total: 5 (Lab01) + 3 (Lab02) = 8")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 4 — Enable and Test Genie Agent Mode</h2>
# MAGIC </div>
# MAGIC
# MAGIC Agent mode supports multi-step reasoning, automatic multi-table joins, and follow-up clarification questions — at the cost of longer response times (10–30 s vs ~3 s for Chat mode). Both modes are fully in-region for Australia East as of April 2026.
# MAGIC
# MAGIC **UI toggle:** Open your Genie Space → Chat tab → toggle switch labelled "Chat | Agent" (top right of the chat panel).

# COMMAND ----------

# Enable Agent mode programmatically
resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs(),
    json={"enable_agent_mode": True}
)
if resp.status_code == 200:
    print("Agent mode enabled via API.")
    print("Users can now toggle between Chat and Agent mode in the Genie UI.")
else:
    print(f"Note: HTTP {resp.status_code} — Agent mode may already be enabled or requires UI toggle.")
    print(f"Detail: {resp.text[:200]}")

# COMMAND ----------

def genie_ask_agent(space_id: str, question: str, timeout_s: int = 120) -> dict:
    """Start an Agent-mode Genie conversation and poll for completion."""
    import time
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{space_id}/start-conversation",
        headers=hdrs(),
        json={"content": question, "mode": "AGENT"}
    )
    resp.raise_for_status()
    d       = resp.json()
    conv_id = d["conversation_id"]
    msg_id  = d["message_id"]

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        poll   = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}",
            headers=hdrs()
        )
        msg    = poll.json()
        status = msg.get("status", "UNKNOWN")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            return msg
        print(f"  Agent status: {status}")
        time.sleep(3)

    return {"status": "TIMEOUT"}


# Agent mode excels at multi-step questions that require joins across tables
AGENT_TEST_QUESTION = (
    "Which distribution zones had the highest peak demand in summer 2024, "
    "and did any of those zones also have above-average unplanned outage frequency?"
)

print("Agent mode test question:")
print(f"  {AGENT_TEST_QUESTION}")
print()
print("This question requires:")
print("  1. Query meter_readings for summer peak demand by zone")
print("  2. Query outages for frequency by region")
print("  3. Join and compare to averages — multi-step reasoning.")
print()

# Uncomment to run (takes 10-30 seconds)
# result = genie_ask_agent(SPACE_ID, AGENT_TEST_QUESTION)
# print(f"Status: {result.get('status')}")
# for att in result.get("attachments", []):
#     if att.get("query"):
#         print(f"SQL:\n{att['query'].get('query','')[:400]}")
print("(Uncomment the result = genie_ask_agent(...) block above to run the test)")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 5 — SharePoint and Google Drive as Genie Data Sources</h2>
# MAGIC </div>
# MAGIC
# MAGIC GA from April 2026 — Genie can query unstructured documents (PDFs, Word, spreadsheets) stored in SharePoint or Google Drive without ingesting them into Delta first. Uses qwen3-embedding-0-6b for in-region embeddings, keeping document content in AU East.
# MAGIC
# MAGIC **UI setup:** Configure tab → look for the Data Sources section → **[+ Add Data Source]** → choose SharePoint or Google Drive → authenticate → enter site/folder URL → click Index documents.

# COMMAND ----------

# Check which embedding endpoints are available in this workspace
try:
    serving_endpoints = list(w.serving_endpoints.list())
    embed_endpoints   = [e for e in serving_endpoints if "embed" in e.name.lower()]
    print("Embedding endpoints in this workspace:")
    for ep in embed_endpoints:
        print(f"  {ep.name}  —  state: {ep.state.ready if ep.state else 'unknown'}")
    if not embed_endpoints:
        print("  No embedding endpoints found.")
except Exception as e:
    print(f"Could not list endpoints: {e}")

print()
print("IMPORTANT — embedding model selection for AU East data residency:")
print()
print("  IN-REGION  (use this):  databricks-qwen3-embedding-0-6b")
print("  CROSS-GEO  (avoid):     databricks-gte-large-en")
print()
print("Selecting the wrong model sends document embeddings outside AU East.")
print("For regulated industries (SOCI Act, AER, Privacy Act) this may breach data residency requirements.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 6 — Troubleshooting: Why Genie Gives Wrong Answers</h2>
# MAGIC </div>
# MAGIC
# MAGIC Work through this checklist when a user reports a wrong answer.

# COMMAND ----------

TROUBLESHOOTING_GUIDE = """
GENIE ACCURACY TROUBLESHOOTING GUIDE
======================================

SYMPTOM 1: Genie uses the wrong table
  Root cause: Table comments are missing or ambiguous.
  Fix: ALTER TABLE SET COMMENT with grain + source. Add a golden query that shows the correct table.

SYMPTOM 2: Correct SQL structure but wrong numbers
  Root cause: Wrong aggregation formula (e.g. not filtering UNPLANNED for SAIDI).
  Fix: Add a golden query with the exact formula and SQL comments explaining non-obvious logic.

SYMPTOM 3: Wrong JOIN key or cartesian product
  Root cause: FK relationships not documented in column comments.
  Fix: Add COMMENT to FK columns: "FK -> parent_table.pk_column". Add a golden query showing the JOIN.

SYMPTOM 4: "This year" returns wrong date range
  Root cause: Instructions do not specify Australian financial year convention.
  Fix: Add to instructions: "This year = current Australian financial year (July 1 – June 30)".

SYMPTOM 5: Genie hallucinates column names
  Root cause: Genie is guessing column names from question wording.
  Fix: Add golden queries that alias actual column names to business-friendly names.

SYMPTOM 6: Genie multiplies interval data by 2
  Root cause: Genie infers 30-min intervals should be doubled for hourly values.
  Fix: Column comment: "Do NOT multiply by 2." Instructions: "Each row is a 30-min interval, never multiply."

SYMPTOM 7: Genie says "I cannot answer this question"
  Root cause: Table not in trusted assets, or instructions are too restrictive.
  Fix: Verify the table is in Configure → Tables. Add a golden query for the question pattern.

SYMPTOM 8: Very slow responses (> 30 s)
  Root cause: Full table scan on a large table with no date filter.
  Fix: Instructions: "Always include a date filter when querying meter_readings."
       Create pre-aggregated views and add them as trusted assets.

THE UNIVERSAL FIX PATTERN
--------------------------
Ask Genie anyway → copy the SQL → fix in a notebook → CREATE VIEW → add view as trusted asset.
"""

print(TROUBLESHOOTING_GUIDE)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 7 — Space Health Check</h2>
# MAGIC </div>
# MAGIC
# MAGIC Automated heuristic check to assess configuration quality before sharing with users.

# COMMAND ----------

def check_genie_space_health(space_id: str, catalog: str, schema: str) -> None:
    issues = []; ok_msgs = []; warnings = []

    # Check 1: Instructions length
    s         = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}", headers=hdrs()).json()
    instr_len = len(s.get("instructions", ""))
    if instr_len < 200:
        issues.append(f"Instructions too short ({instr_len} chars). Aim for 500–3000 chars.")
    elif instr_len > 7000:
        warnings.append(f"Instructions very long ({instr_len} chars). May approach token limits.")
    else:
        ok_msgs.append(f"Instructions length = {instr_len:,} chars")

    # Check 2: Agent mode
    if s.get("enable_agent_mode"):
        ok_msgs.append("Agent mode is enabled")
    else:
        warnings.append("Agent mode not enabled (acceptable for simple analyst use cases)")

    # Check 3: Trusted assets
    ar = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}/trusted-assets", headers=hdrs())
    if ar.status_code == 200:
        n_assets = len(ar.json().get("trusted_assets", []))
        if n_assets == 0:
            issues.append("No trusted assets — Genie cannot query anything!")
        elif n_assets < 2:
            warnings.append(f"Only {n_assets} trusted asset(s). Add more tables for richer coverage.")
        else:
            ok_msgs.append(f"{n_assets} trusted asset(s) configured")
    else:
        warnings.append(f"Could not check trusted assets (HTTP {ar.status_code})")

    # Check 4: Golden queries
    qr = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}/sql-queries", headers=hdrs())
    if qr.status_code == 200:
        n_queries = len(qr.json().get("sql_queries", []))
        if n_queries == 0:
            issues.append("No golden queries. Add at least 5 for common question patterns.")
        elif n_queries < 5:
            warnings.append(f"Only {n_queries} golden quer(ies). Aim for 10+ for production spaces.")
        else:
            ok_msgs.append(f"{n_queries} golden quer(ies) in knowledge store")
    else:
        warnings.append(f"Could not check golden queries (HTTP {qr.status_code})")

    # Check 5: Table-level comments
    no_comment_tables = []
    for tbl in ["meter_readings", "assets", "outages", "regulatory_reports"]:
        try:
            result = spark.sql(f"DESCRIBE TABLE EXTENDED {catalog}.{schema}.{tbl}")
            detail = result.filter("col_name = 'Comment'").collect()
            if not detail or not detail[0]["data_type"].strip():
                no_comment_tables.append(tbl)
        except Exception:
            no_comment_tables.append(f"{tbl} (could not check)")
    if no_comment_tables:
        warnings.append(f"Tables missing comments: {no_comment_tables}")
    else:
        ok_msgs.append("All 4 expected tables have table-level comments")

    print("GENIE SPACE HEALTH REPORT")
    print("=" * 55)
    print(f"  Space ID   : {space_id}")
    print(f"  Space title: {s.get('title', 'unknown')}")
    print()
    for msg in ok_msgs:    print(f"  [OK  ]  {msg}")
    for msg in warnings:   print(f"  [WARN]  {msg}")
    for msg in issues:     print(f"  [ERR ]  {msg}")
    print()
    if not issues:
        print("  All critical checks passed.")
    else:
        print(f"  {len(issues)} critical issue(s) found — fix before sharing with users.")
    print("=" * 55)


check_genie_space_health(SPACE_ID, CATALOG, SCHEMA)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Checkpoint — Inspect Full Configuration via API

# COMMAND ----------

space_resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=hdrs())
config     = space_resp.json()

print("CURRENT GENIE SPACE CONFIGURATION")
print("=" * 55)
print(f"  Title              : {config.get('title')}")
print(f"  Space ID           : {config.get('space_id')}")
print(f"  Instructions chars : {len(config.get('instructions', '')):,}")
print(f"  Agent mode         : {config.get('enable_agent_mode', False)}")
print()

ar = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/trusted-assets", headers=hdrs())
if ar.status_code == 200:
    assets = ar.json().get("trusted_assets", [])
    print(f"Trusted Assets ({len(assets)}):")
    for a in assets:
        print(f"  - {a.get('asset_fqn')}  ({a.get('asset_type')})")

print()
qr = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries", headers=hdrs())
if qr.status_code == 200:
    queries = qr.json().get("sql_queries", [])
    print(f"Golden Queries ({len(queries)}):")
    for q in queries:
        print(f"  - {q.get('name')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Review Questions
# MAGIC
# MAGIC 1. You have a column `quality_flag` with values A, E, S, N. A business analyst is getting inflated consumption totals. Write the column comment you would add to help Genie automatically exclude bad-quality data.
# MAGIC 2. A user asks Genie "show me peak demand for summer" but the result is wrong because the model multiplied 30-min intervals by 2. What **two specific changes** would you make — one to a column comment, one to the instructions block?
# MAGIC 3. Agent mode vs Chat mode: for "Which substations had the most outages in zones with high consumption growth?" — which mode is better and why?
# MAGIC 4. For the SharePoint connector (GA April 2026), which embedding model should you use for AU East data residency, and what is the risk of using the wrong model for an APRA-regulated institution?
# MAGIC 5. The health checker reports "Only 2 trusted assets" but your schema has 10 tables. Walk through three steps to diagnose why the missing tables are not appearing.
# MAGIC
# MAGIC **Proceed to Lab 03 when ready.**
