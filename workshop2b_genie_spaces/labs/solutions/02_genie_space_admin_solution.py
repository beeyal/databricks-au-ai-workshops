# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 02: Genie Space — Admin Configuration Deep Dive — SOLUTION
# MAGIC
# MAGIC **Workshop:** Genie Spaces & AI Features — Australian Regulated Industries
# MAGIC **Duration:** 35–40 minutes
# MAGIC **Role:** Data Engineer / Platform Admin
# MAGIC **Prerequisite:** Lab 01 complete — `workshop.energy_nem` tables exist and you have a `SPACE_ID`
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC 1. Write Unity Catalog table and column comments that improve Genie accuracy
# MAGIC 2. Add more sophisticated golden SQL queries to the knowledge store
# MAGIC 3. Configure time-series awareness for energy interval data
# MAGIC 4. Enable and test Genie Agent mode
# MAGIC 5. Connect SharePoint / Google Drive as Genie data sources (GA April 2026)
# MAGIC 6. Diagnose and fix the most common Genie accuracy issues
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why Admin Configuration Matters
# MAGIC
# MAGIC Genie's accuracy is almost entirely determined by the quality of its configuration.
# MAGIC The model itself is fixed — what you control is the context you give it.
# MAGIC
# MAGIC ```
# MAGIC Genie Accuracy Budget
# MAGIC ─────────────────────────────────────────────────────────────
# MAGIC  Table & column comments        ~30%  (schema understanding)
# MAGIC  Space instructions             ~25%  (domain + business rules)
# MAGIC  Golden SQL examples            ~30%  (correct query patterns)
# MAGIC  Question phrasing (user)       ~15%  (covered in Lab 03)
# MAGIC ─────────────────────────────────────────────────────────────
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests
from databricks.sdk import WorkspaceClient

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

# SOLUTION: paste your SPACE_ID from Lab 01 output here
# To retrieve it, run: w.genie.list_spaces() or check the Lab 01 final cell output
SPACE_ID = ""  # REQUIRED: copy from Lab 01 final cell output — e.g. "01ef1234-abcd-5678-efgh-000000000001"
CATALOG  = "workshop"
SCHEMA   = "energy_nem"

assert SPACE_ID, "Set SPACE_ID from Lab 01 before proceeding."

def hdrs():
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print(f"Connected: {HOST}")
print(f"Space ID : {SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Writing Effective UC Table and Column Comments
# MAGIC
# MAGIC Genie reads Unity Catalog metadata to understand the schema.
# MAGIC Good comments directly reduce hallucinated column names and wrong joins.
# MAGIC
# MAGIC ### Principles
# MAGIC - **Table comment**: describe the grain (one row = one what?), source system, update frequency
# MAGIC - **Column comment**: define units, allowed values, business meaning — especially for codes and flags
# MAGIC - **Avoid generic comments** like "the ID column" — state what the ID means and its format
# MAGIC - **Include example values** for low-cardinality columns (enums)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a — Enrich meter_readings comments (columns we want to improve)

# COMMAND ----------

# Add richer column-level context for the columns that most confuse NL-to-SQL models

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN quality_flag
    COMMENT 'NEM12 quality flag governing data confidence.
Values: A=Actual (field reading), E=Estimated (based on history),
S=Substituted (manual correction), N=None (no read available).
Exclude N and S from consumption totals unless investigating data quality.'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN interval_datetime
    COMMENT 'Start of the 30-minute measurement interval in Australian Eastern Standard Time (AEST, UTC+10).
Do NOT multiply by 2 to convert to hourly — use DATE_TRUNC or SUM over the window instead.
Example value: 2024-06-01T07:00:00'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN active_energy_kwh
    COMMENT 'Kilowatt-hours of active energy imported by the consumer during the 30-minute interval.
Typical residential range: 0.05–4.0 kWh per interval.
To get daily kWh: SUM(active_energy_kwh) for a given NMI and calendar day.
To get monthly MWh: SUM(active_energy_kwh) / 1000 grouped by month.'
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
Formula: estimated demand at time of outage × duration in hours.
NULL means ENS was not calculated (usually very short outages < 1 minute).
Treat NULL as 0 in SUM() aggregations using COALESCE(energy_not_served_mwh, 0).
Reported to AER as part of STPIS incentive scheme annual submission.'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.outages
  ALTER COLUMN reported_to_aer
    COMMENT 'TRUE if this outage event met the AER threshold for inclusion in SAIDI/SAIFI statistics.
Threshold: any unplanned outage affecting ≥1 customer for ≥1 minute.
Planned outages do NOT count toward SAIDI/SAIFI regulatory metrics.'
""")

# Update the table-level comment with richer grain description
spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.outages
  SET TBLPROPERTIES (
    'comment' = 'Network outage event log. One row = one continuous supply interruption event on one asset.
SAIDI formula: SUM((end_time - start_time in minutes) × customers_affected) / total_connection_points.
SAIFI formula: SUM(customers_affected) / total_connection_points.
Excludes planned maintenance outages from AER regulatory metrics (filter outage_type = UNPLANNED).
Updated in near-real-time from SCADA and field crew mobile app.'
  )
""")

print("outages comments updated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c — Add a computed metric as a view (Genie can query views too)
# MAGIC
# MAGIC A common pattern: pre-compute complex business metrics as a view, then add
# MAGIC the view to the Genie Space as a trusted asset. This simplifies the SQL
# MAGIC that Genie has to generate.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.v_saidi_monthly AS
-- Pre-calculated monthly SAIDI component per region
-- SAIDI (minutes) = SUM(interruption_minutes × customers_affected) / total_served
-- This view gives the numerator; divide by your total customer count to get SAIDI.
SELECT
    region,
    DATE_TRUNC('month', start_time)                                      AS month,
    COUNT(outage_id)                                                     AS outage_count,
    SUM(customers_affected)                                              AS customer_interruptions,
    SUM(
        COALESCE(TIMESTAMPDIFF(MINUTE, start_time, end_time), 0)
        * customers_affected
    )                                                                    AS saidi_numerator_minutes,
    SUM(COALESCE(energy_not_served_mwh, 0))                              AS ens_mwh
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
print(f"v_saidi_monthly added as trusted asset: {resp.status_code}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Time-Series Awareness Configuration
# MAGIC
# MAGIC Energy data is inherently time-series. Genie needs explicit guidance on:
# MAGIC - How to interpret relative date references ("last quarter", "this year")
# MAGIC - The correct granularity for interval data (30-minute, not hourly)
# MAGIC - How to aggregate across intervals without double-counting
# MAGIC
# MAGIC We encode this in the instructions block.

# COMMAND ----------

TIMESERIES_INSTRUCTIONS_ADDENDUM = """

## Time-Series and Date Handling

### Financial Year
- "This year" or "current year" = current Australian financial year (July 1 – June 30)
- "Last year" = previous financial year
- Use: WHERE start_time BETWEEN '2023-07-01' AND '2024-06-30' for FY2024

### Interval Data (meter_readings)
- Each row is a 30-MINUTE interval — never multiply by 2 to get hourly kWh
- To get hourly: SUM(active_energy_kwh) WHERE interval_datetime >= hour AND interval_datetime < hour + 1h
- Peak demand = MAX of any single 30-min interval in a day (not the daily average)
- Daily energy (kWh) = SUM(active_energy_kwh) for that day
- Monthly energy (MWh) = SUM(active_energy_kwh) / 1000 for that month

### Peak vs Off-Peak
- Peak hours (residential): 7am–11pm weekdays
- Off-peak: 11pm–7am and weekends (for network tariff comparisons)
- To identify peak: HOUR(interval_datetime) BETWEEN 7 AND 22 AND DAYOFWEEK(interval_datetime) NOT IN (1,7)

### Outage Duration
- Express in hours rounded to 1 decimal: ROUND(TIMESTAMPDIFF(MINUTE, start_time, end_time) / 60, 1)
- Never use end_time - start_time directly in minutes without TIMESTAMPDIFF

### Seasons in Australia
- Summer: December, January, February (peak demand season)
- Winter: June, July, August (second demand peak for electric heating)
- Use MONTH(interval_datetime) IN (12, 1, 2) for summer
"""

# Fetch current instructions and append
get_resp = requests.get(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs()
)
current = get_resp.json()
existing_instructions = current.get("instructions", "")

updated_instructions = existing_instructions + "\n" + TIMESERIES_INSTRUCTIONS_ADDENDUM

patch_resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs(),
    json={"instructions": updated_instructions.strip()}
)
print(f"Instructions updated: {patch_resp.status_code}")
print(f"Total instruction length: {len(updated_instructions):,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Advanced Golden Queries
# MAGIC
# MAGIC The previous lab added 5 basic queries. Now we add more complex patterns
# MAGIC that involve multi-table joins, window functions, and seasonal aggregations.

# COMMAND ----------

ADVANCED_GOLDEN_QUERIES = [
    {
        "name": "Peak demand days by zone (summer vs winter comparison)",
        "description": (
            "Identifies the top 5 peak demand days per distribution zone and season. "
            "Used for network capacity planning and demand response targeting."
        ),
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
        -- Peak = maximum single 30-min interval demand proxy
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
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY distribution_zone, season
                              ORDER BY peak_demand_kw DESC) AS rank_in_season
    FROM daily_peaks
)
SELECT
    distribution_zone,
    season,
    reading_date,
    ROUND(peak_demand_kw, 1)    AS peak_demand_kw,
    ROUND(daily_energy_kwh, 0)  AS daily_energy_kwh,
    active_meters
FROM ranked
WHERE rank_in_season <= 5
ORDER BY distribution_zone, season, peak_demand_kw DESC
"""
    },
    {
        "name": "Assets overdue for maintenance inspection",
        "description": (
            "Assets whose last_maintenance date is more than 12 months ago and that are "
            "currently IN_SERVICE. Used to prioritise maintenance scheduling."
        ),
        "sql": f"""
SELECT
    a.asset_id,
    a.asset_name,
    a.asset_type,
    a.owner_dnsp,
    a.region,
    a.voltage_kv,
    a.last_maintenance,
    DATEDIFF(CURRENT_DATE, a.last_maintenance)              AS days_since_maintenance,
    COUNT(o.outage_id)                                      AS outages_since_maintenance,
    ROUND(SUM(COALESCE(o.energy_not_served_mwh, 0)), 2)     AS ens_since_maintenance_mwh
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id
   AND o.start_time > a.last_maintenance
WHERE a.status = 'IN_SERVICE'
  AND a.last_maintenance < DATE_SUB(CURRENT_DATE, 365)
GROUP BY a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp,
         a.region, a.voltage_kv, a.last_maintenance
ORDER BY days_since_maintenance DESC
"""
    },
    {
        "name": "SAIDI year-to-date vs prior year same period",
        "description": (
            "Year-on-year SAIDI comparison for AER reporting. Assumes a fixed "
            "denominator of 1,000,000 connected customers for this example — replace "
            "with your actual ICP count from the customer register."
        ),
        "sql": f"""
WITH params AS (
    -- TODO: replace 1000000 with actual ICP count from your customer register
    SELECT 1000000 AS total_icps
),
current_year AS (
    SELECT
        region,
        SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_numerator
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED'
      AND reported_to_aer = TRUE
      AND end_time IS NOT NULL
      AND YEAR(start_time) = YEAR(CURRENT_DATE)
      AND MONTH(start_time) <= MONTH(CURRENT_DATE)
    GROUP BY region
),
prior_year AS (
    SELECT
        region,
        SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_numerator
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED'
      AND reported_to_aer = TRUE
      AND end_time IS NOT NULL
      AND YEAR(start_time) = YEAR(CURRENT_DATE) - 1
      AND MONTH(start_time) <= MONTH(CURRENT_DATE)
    GROUP BY region
)
SELECT
    COALESCE(c.region, p.region)                                          AS region,
    ROUND(COALESCE(c.saidi_numerator, 0) / params.total_icps, 2)          AS saidi_ytd_minutes,
    ROUND(COALESCE(p.saidi_numerator, 0) / params.total_icps, 2)          AS saidi_prior_year_minutes,
    ROUND(
        (COALESCE(c.saidi_numerator, 0) - COALESCE(p.saidi_numerator, 0))
        / NULLIF(p.saidi_numerator, 0) * 100
    , 1)                                                                  AS pct_change_vs_prior_year
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
    status = "OK" if resp.status_code in (200, 201) else f"ERROR {resp.status_code}: {resp.text[:80]}"
    print(f"  [{status}] {q['name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Enable Genie Agent Mode
# MAGIC
# MAGIC **Agent mode** vs **Chat mode**:
# MAGIC
# MAGIC | Capability | Chat mode | Agent mode |
# MAGIC |---|---|---|
# MAGIC | Single-table queries | Yes | Yes |
# MAGIC | Multi-step reasoning | Limited | Yes |
# MAGIC | Automatic table joins | Sometimes | Yes |
# MAGIC | Follow-up clarification | No | Yes |
# MAGIC | Tool use (search, compute) | No | Yes |
# MAGIC | Response time | ~3s | ~10–30s |
# MAGIC
# MAGIC Agent mode is the right choice for operational users who ask complex multi-part questions.
# MAGIC Chat mode is better for dashboards embedded in notebooks or simpler analyst workflows.
# MAGIC
# MAGIC **AU East availability:** Both modes are fully in-region for Australia East as of April 2026.

# COMMAND ----------

# Enable Agent mode on the existing Genie Space
resp = requests.patch(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs(),
    json={"enable_agent_mode": True}
)
if resp.status_code == 200:
    print("Agent mode enabled.")
    print("Users can now toggle between Chat and Agent mode in the Genie UI.")
else:
    print(f"Note: {resp.status_code} — Agent mode may already be enabled or requires UI toggle.")
    print(f"Detail: {resp.text[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Testing Agent Mode Programmatically
# MAGIC
# MAGIC Agent mode accepts the same Conversation API — just add `"mode": "AGENT"` to the start request.

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
    data = resp.json()
    conv_id = data["conversation_id"]
    msg_id  = data["message_id"]

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        poll = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}",
            headers=hdrs()
        )
        poll.raise_for_status()
        msg    = poll.json()
        status = msg.get("status", "UNKNOWN")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            return msg
        print(f"  Agent status: {status}")
        time.sleep(3)

    return {"status": "TIMEOUT"}


# Agent mode excels at multi-step questions that require joins
AGENT_TEST_QUESTION = (
    "Which distribution zones had the highest peak demand in summer 2024, "
    "and did any of those zones also have above-average outage frequency?"
)

print(f"Agent mode question:\n  {AGENT_TEST_QUESTION}\n")
# Uncomment to run (takes 10–30 seconds)
# result = genie_ask_agent(SPACE_ID, AGENT_TEST_QUESTION)
# print(f"Status: {result.get('status')}")
# for att in result.get("attachments", []):
#     if att.get("query"):
#         print(f"SQL: {att['query']['query'][:500]}")
print("(Commented out to avoid long wait — uncomment to test)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — SharePoint and Google Drive as Genie Data Sources
# MAGIC
# MAGIC **GA from April 2026 (in-region for AU East)**
# MAGIC
# MAGIC Genie can now query unstructured documents (PDFs, Word docs, spreadsheets) stored in
# MAGIC SharePoint or Google Drive directly, without needing to ingest them into Delta tables first.
# MAGIC
# MAGIC This is delivered via the **UC AI Gateway + Genie RAG** path announced April 26, 2026.
# MAGIC
# MAGIC ### When to use this vs ingesting to Delta
# MAGIC
# MAGIC | Approach | Use when |
# MAGIC |---|---|
# MAGIC | SharePoint/Drive connector | Documents change frequently, owners maintain in SharePoint |
# MAGIC | Ingest to Delta + Genie | Need SQL aggregation over document metadata; large volumes |
# MAGIC | Both | Best coverage: structured data in Delta, documents via connector |
# MAGIC
# MAGIC ### Setup (UI path — API coming soon)
# MAGIC
# MAGIC 1. Open the Genie Space → Settings → Data Sources
# MAGIC 2. Click "Add Data Source" → SharePoint or Google Drive
# MAGIC 3. Authenticate with your M365 / Google credentials
# MAGIC 4. Select the SharePoint site or Drive folder to connect
# MAGIC 5. Genie indexes the documents and makes them searchable
# MAGIC
# MAGIC The embedding model used for indexing is **databricks-qwen3-embedding-0-6b** (in-region AU East).
# MAGIC Do NOT select databricks-gte-large-en — that model is cross-geo for AU.

# COMMAND ----------

# Demonstrate the pattern: check which embedding models are available in AU East
try:
    serving_endpoints = list(w.serving_endpoints.list())
    embed_endpoints = [e for e in serving_endpoints if "embed" in e.name.lower()]
    print("Embedding endpoints in this workspace:")
    for ep in embed_endpoints:
        print(f"  {ep.name} — state: {ep.state.ready if ep.state else 'unknown'}")
    if not embed_endpoints:
        print("  No embedding endpoints found.")
        print("  For Genie RAG: deploy databricks-qwen3-embedding-0-6b (in-region AU East)")
        print("  Do NOT use databricks-gte-large-en (cross-geo for AU)")
except Exception as e:
    print(f"Could not list endpoints: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Document RAG Pattern (if ingesting to Delta rather than using the native connector)
# MAGIC
# MAGIC If you prefer to ingest PDFs to Delta and use Vector Search for RAG,
# MAGIC use the in-region embedding model.

# COMMAND ----------

# Embedding model selection for AU East
# In-region:   databricks-qwen3-embedding-0-6b  ← USE THIS
# Cross-geo:   databricks-gte-large-en           ← DO NOT USE for regulated data

IN_REGION_EMBED_MODEL = "databricks-qwen3-embedding-0-6b"

# Example: embed regulatory report text for Vector Search
# (full Vector Search setup is out of scope for this lab — see Lab 05)
example_texts = [
    "The SAIDI for the VIC1 region in FY2024 was 89.3 minutes, which is below the AER target of 95 minutes.",
    "Capital expenditure for network augmentation totalled $47.2M in FY2024, including the Essendon substation upgrade.",
    "Vegetation management remains the primary cause of unplanned outages, accounting for 34% of all events."
]

print(f"Would embed {len(example_texts)} documents using: {IN_REGION_EMBED_MODEL}")
print("This model runs on AU East compute — no data leaves the region.")
print()
print("To embed via API:")
print(f"  POST /serving-endpoints/{IN_REGION_EMBED_MODEL}/invocations")
print('  {"input": ["your text here"]}')

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Troubleshooting: Why Genie Gives Wrong Answers
# MAGIC
# MAGIC ### Diagnostic Framework
# MAGIC
# MAGIC When a user reports a wrong Genie answer, work through this checklist:

# COMMAND ----------

GENIE_TROUBLESHOOTING_GUIDE = """
GENIE ACCURACY TROUBLESHOOTING GUIDE
=====================================

SYMPTOM 1: Genie uses the wrong table for a query
─────────────────────────────────────────────────
Root cause: Table comments are missing or ambiguous.
Fix:
  ALTER TABLE t ALTER COLUMN c COMMENT '...'
  Make table-level comments describe the grain clearly.
  Add a golden query that demonstrates the correct table to use.

SYMPTOM 2: Genie generates correct SQL but wrong numbers
────────────────────────────────────────────────────────
Root cause: Aggregation logic is wrong (e.g. counting rows instead of summing metric).
Fix:
  Add a golden query that shows the EXACT aggregation formula.
  In instructions, spell out: "SAIDI = SUM(duration_minutes × customers) / total_icps"

SYMPTOM 3: Genie joins tables incorrectly (cartesian or wrong key)
──────────────────────────────────────────────────────────────────
Root cause: FK relationships not documented in comments.
Fix:
  Add COMMENT to FK columns: "FK → parent_table.pk_column"
  Add a golden query that demonstrates the correct join.

SYMPTOM 4: Genie uses wrong date range for "this year" / "last month"
──────────────────────────────────────────────────────────────────────
Root cause: Instructions don't specify financial year convention.
Fix:
  Add to instructions: "This year = current Australian financial year (Jul 1 – Jun 30)"
  Add golden queries that show the correct date arithmetic.

SYMPTOM 5: Genie hallucinates column names that don't exist
────────────────────────────────────────────────────────────
Root cause: Genie is guessing based on question wording, not schema.
Fix:
  Run: DESCRIBE TABLE your_table  — confirm columns exist.
  Add aliases that match user language:
    SELECT active_energy_kwh AS consumption_kwh FROM meter_readings
  Add a golden query that uses the correct column with a user-friendly alias.

SYMPTOM 6: Genie answers correctly but very slowly (>30s)
──────────────────────────────────────────────────────────
Root cause: Full table scan on a large partitioned table.
Fix:
  Ensure questions include a date filter — document this in instructions.
  Add ZORDER BY on common filter columns.
  Create pre-aggregated views for common queries.

SYMPTOM 7: Genie says "I cannot answer this question"
───────────────────────────────────────────────────────
Root cause: Table not in trusted assets, or instructions are too restrictive.
Fix:
  Confirm the table is in trusted assets.
  Check instructions don't contain "do not query X" accidentally.
  Add a golden query for the question pattern.
"""

print(GENIE_TROUBLESHOOTING_GUIDE)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Diagnostic Query: Inspect Your Space Configuration

# COMMAND ----------

# Fetch and display the current Genie Space configuration summary
resp = requests.get(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs()
)
space_config = resp.json()

print("CURRENT GENIE SPACE CONFIGURATION")
print("=" * 50)
print(f"Title:              {space_config.get('title')}")
print(f"Space ID:           {space_config.get('space_id')}")
print(f"Instructions chars: {len(space_config.get('instructions', '')):,}")
print(f"Agent mode:         {space_config.get('enable_agent_mode', 'not set')}")
print()

# List trusted assets
assets_resp = requests.get(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/trusted-assets",
    headers=hdrs()
)
if assets_resp.status_code == 200:
    assets = assets_resp.json().get("trusted_assets", [])
    print(f"Trusted assets ({len(assets)}):")
    for a in assets:
        print(f"  - {a.get('asset_fqn')} ({a.get('asset_type')})")
else:
    print(f"Could not fetch trusted assets: {assets_resp.status_code}")

print()

# List golden queries
queries_resp = requests.get(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
    headers=hdrs()
)
if queries_resp.status_code == 200:
    queries = queries_resp.json().get("sql_queries", [])
    print(f"Golden queries ({len(queries)}):")
    for q in queries:
        print(f"  - {q.get('name')}")
else:
    print(f"Could not fetch queries: {queries_resp.status_code}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Space Health Checklist
# MAGIC
# MAGIC Run this cell to auto-check your Genie Space configuration quality.

# COMMAND ----------

def check_genie_space_health(space_id: str, catalog: str, schema: str) -> None:
    """
    Runs a series of heuristic checks against a Genie Space configuration
    and prints a health report.
    """
    issues  = []
    ok_msgs = []

    # Check 1: Instructions length
    s = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}", headers=hdrs()).json()
    instr_len = len(s.get("instructions", ""))
    if instr_len < 200:
        issues.append(f"WARN: Instructions too short ({instr_len} chars). Aim for 500–3000 chars.")
    elif instr_len > 6000:
        issues.append(f"WARN: Instructions very long ({instr_len} chars). May hit token limits.")
    else:
        ok_msgs.append(f"OK: Instructions length = {instr_len} chars")

    # Check 2: Agent mode enabled
    if s.get("enable_agent_mode"):
        ok_msgs.append("OK: Agent mode is enabled")
    else:
        issues.append("INFO: Agent mode not enabled (fine for simple use cases)")

    # Check 3: Trusted assets
    ar = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}/trusted-assets", headers=hdrs())
    if ar.status_code == 200:
        n_assets = len(ar.json().get("trusted_assets", []))
        if n_assets == 0:
            issues.append("ERROR: No trusted assets — Genie cannot query anything!")
        elif n_assets < 2:
            issues.append(f"WARN: Only {n_assets} trusted asset(s). Consider adding more tables.")
        else:
            ok_msgs.append(f"OK: {n_assets} trusted asset(s) configured")

    # Check 4: Golden queries
    qr = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}/sql-queries", headers=hdrs())
    if qr.status_code == 200:
        n_queries = len(qr.json().get("sql_queries", []))
        if n_queries == 0:
            issues.append("WARN: No golden queries. Add at least 5 for common questions.")
        elif n_queries < 5:
            issues.append(f"WARN: Only {n_queries} golden quer(ies). Aim for 10+.")
        else:
            ok_msgs.append(f"OK: {n_queries} golden quer(ies) in knowledge store")

    # Check 5: Tables have comments
    no_comment_tables = []
    for tbl in ["meter_readings", "assets", "outages", "regulatory_reports"]:
        try:
            result = spark.sql(f"DESCRIBE TABLE EXTENDED {catalog}.{schema}.{tbl}")
            detail = result.filter("col_name = 'Comment'").collect()
            if not detail or not detail[0]["data_type"].strip():
                no_comment_tables.append(tbl)
        except Exception:
            no_comment_tables.append(tbl)

    if no_comment_tables:
        issues.append(f"WARN: Tables without comments: {no_comment_tables}")
    else:
        ok_msgs.append("OK: All tables have table-level comments")

    # Report
    print("GENIE SPACE HEALTH CHECK")
    print("=" * 50)
    for msg in ok_msgs:
        print(f"  {msg}")
    if issues:
        print()
        for msg in issues:
            print(f"  {msg}")
    else:
        print()
        print("  All checks passed.")
    print("=" * 50)


check_genie_space_health(SPACE_ID, CATALOG, SCHEMA)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab 02 — Review Questions
# MAGIC
# MAGIC 1. You have a column `quality_flag` with values A, E, S, N. A business analyst is getting
# MAGIC    inflated consumption totals. What comment would you add to help Genie exclude bad data?
# MAGIC
# MAGIC 2. A user asks Genie "show me peak demand for summer" but the result is wrong because
# MAGIC    it multiplied 30-min intervals by 2. What two things would you fix?
# MAGIC
# MAGIC 3. Agent mode vs Chat mode: for a question like
# MAGIC    "Which substations had the most outages in zones with high consumption growth?"
# MAGIC    which mode is better and why?
# MAGIC
# MAGIC 4. For the SharePoint connector (GA April 2026), which embedding model should you use
# MAGIC    and why does it matter for an Australian regulated industry customer?
# MAGIC
# MAGIC 5. The health checker reports "Only 2 trusted assets". The user says "but we have 10 tables".
# MAGIC    What is the likely cause and how do you fix it?
# MAGIC
# MAGIC **Proceed to Lab 03 when ready.**
