# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 02: Genie Space Admin — Deep Dive
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">
# MAGIC     Configuration Quality, Time-Series Awareness, Agent Mode, and Troubleshooting
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="width:100%; border-collapse:collapse; margin-top:16px; font-family:'DM Sans',sans-serif;">
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px; width:25%"><b>Workshop</b></td><td style="padding:8px 16px;">Genie Spaces &amp; AI Features — Australian Regulated Industries</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Duration</b></td><td style="padding:8px 16px;">35–40 minutes</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Role</b></td><td style="padding:8px 16px;">Data Engineer / Platform Admin</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Prerequisites</b></td><td style="padding:8px 16px;">Lab 01 complete — <code>workshop.energy_nem</code> tables exist and you have a <code>SPACE_ID</code></td></tr>
# MAGIC </table>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F4FD; border-left:5px solid #1B3A6B; padding:20px 24px; border-radius:0 8px 8px 0; margin:16px 0;">
# MAGIC   <h2 style="color:#1B3A6B; margin-top:0;">Learning Objectives</h2>
# MAGIC   <ol style="line-height:2em;">
# MAGIC     <li>Write Unity Catalog table and column comments that directly improve Genie accuracy</li>
# MAGIC     <li>Navigate Catalog Explorer to add comments via the UI</li>
# MAGIC     <li>Add advanced golden SQL queries covering time-series and multi-table patterns</li>
# MAGIC     <li>Configure time-series awareness (financial year, peak/off-peak, Australian seasons)</li>
# MAGIC     <li>Enable and test Genie Agent mode vs Chat mode</li>
# MAGIC     <li>Connect SharePoint and Google Drive as Genie data sources (GA April 2026)</li>
# MAGIC     <li>Diagnose and fix the most common Genie accuracy issues using a structured checklist</li>
# MAGIC   </ol>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#FFF3CD; border-left:5px solid #FFC107; padding:16px 20px; border-radius:0 8px 8px 0; margin:12px 0;">
# MAGIC   <h3 style="color:#856404; margin-top:0;">Why Admin Configuration Drives Accuracy</h3>
# MAGIC   <p>Genie's accuracy is almost entirely determined by the quality of its configuration.
# MAGIC   The underlying model is fixed — what you control is the context you give it.</p>
# MAGIC
# MAGIC   <pre style="background:white; padding:14px; border-radius:6px; margin:8px 0;">
# MAGIC   Genie Accuracy Budget
# MAGIC   -------------------------------------------------------
# MAGIC    Table and column comments     ~30%  (schema understanding)
# MAGIC    Space instructions            ~25%  (domain + business rules)
# MAGIC    Golden SQL examples           ~30%  (correct query patterns)
# MAGIC    Question phrasing (user)      ~15%  (covered in Lab 03)
# MAGIC   -------------------------------------------------------
# MAGIC   </pre>
# MAGIC
# MAGIC   <p style="margin-bottom:0;">Every step in this lab targets one of the first three buckets.</p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before We Code: 6-Minute UI Tour (do this first!)
# MAGIC
# MAGIC This lab improves Genie accuracy through configuration.
# MAGIC Before writing any code, benchmark the current accuracy by asking a few questions
# MAGIC in the Genie Space — so you can see the improvement after applying the changes.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 1 — Open the Genie Space and ask baseline questions
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Genie → click "Energy Operations Assistant"
# MAGIC   → Chat tab
# MAGIC ```
# MAGIC
# MAGIC **Ask these questions and note the responses:**
# MAGIC ```
# MAGIC 1. "What was the total energy consumption last month?"
# MAGIC 2. "Which meter had the highest peak demand in the last 7 days?"
# MAGIC 3. "Show me outages longer than 30 minutes this quarter"
# MAGIC ```
# MAGIC
# MAGIC Write down any failures — Section 3 of this lab fixes time-series awareness.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 2 — Inspect current table comments in Unity Catalog
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Catalog → workshop → energy_nem
# MAGIC   → Click "meter_readings" table → Overview tab
# MAGIC     → Look at "Comment" field and column descriptions
# MAGIC ```
# MAGIC
# MAGIC Missing comments are why Genie struggles with domain-specific questions.
# MAGIC Section 1 of this lab adds rich comments that Genie reads at query time.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 3 — Check the space Configure tab
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Genie → your space → Configure tab
# MAGIC   → Instructions section (count lines)
# MAGIC   → SQL examples section (count examples)
# MAGIC ```
# MAGIC
# MAGIC After running this lab, come back and compare.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Time check:** 6 minutes. Start the pip install — it runs in parallel.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests
from databricks.sdk import WorkspaceClient

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

# TODO: paste the SPACE_ID from Lab 01 output
SPACE_ID = ""  # e.g. "01ef1234-abcd-5678-efgh-000000000001"
CATALOG  = "workshop"
SCHEMA   = "energy_nem"

assert SPACE_ID, "Paste your SPACE_ID from Lab 01 before proceeding."

def hdrs():
    """Return auth headers for Databricks REST API calls."""
    t = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}

print(f"Connected : {HOST}")
print(f"Space ID  : {SPACE_ID}")
print(f"Schema    : {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 1 — Writing Effective UC Table and Column Comments</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#F3F9FF; border:1px solid #90CAF9; padding:16px 20px; border-radius:8px; margin:12px 0;">
# MAGIC   Genie reads Unity Catalog metadata to understand the schema before generating SQL.
# MAGIC   Good comments directly reduce hallucinated column names and wrong joins.
# MAGIC
# MAGIC   <br><br>
# MAGIC   <strong>Principles:</strong>
# MAGIC   <ul>
# MAGIC     <li><strong>Table comment:</strong> describe the grain (one row = one what?), source system, update frequency</li>
# MAGIC     <li><strong>Column comment:</strong> define units, allowed values, business meaning — especially for codes and flags</li>
# MAGIC     <li><strong>Avoid generic comments</strong> like "the ID column" — state what the ID means and its format</li>
# MAGIC     <li><strong>Include example values</strong> for low-cardinality columns (enums, flags)</li>
# MAGIC     <li><strong>Document aggregation rules</strong> directly in comments: "daily total = SUM for a given NMI and day"</li>
# MAGIC   </ul>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a — Adding comments in Catalog Explorer (UI path)
# MAGIC
# MAGIC You can edit column comments directly in the Databricks UI without writing any SQL.
# MAGIC This is the preferred approach for one-off corrections or when reviewing schema quality.
# MAGIC
# MAGIC **Navigation:**
# MAGIC ```
# MAGIC Left sidebar --> Data (cylinder icon) --> Catalog Explorer
# MAGIC --> workshop --> energy_nem --> [table name] --> Columns tab
# MAGIC ```
# MAGIC
# MAGIC **What you see on the Columns tab:**
# MAGIC
# MAGIC ```
# MAGIC +-- Table: outages --------------------------------------------------+
# MAGIC |   [Overview]   [Columns]   [Sample Data]   [Details]   [Lineage]  |
# MAGIC |                 ^ click here                                       |
# MAGIC |                                                                    |
# MAGIC |   Column name          Type      Comment                          |
# MAGIC |   ---------------------------------------------------------------  |
# MAGIC |   outage_id            STRING    Unique outage event identifier   |
# MAGIC |   asset_id             STRING    FK -> assets.asset_id            |
# MAGIC |   outage_type          STRING    PLANNED or UNPLANNED             |
# MAGIC |   energy_not_served_mwh DOUBLE   [click pencil to edit] ✏️        |
# MAGIC |   reported_to_aer      BOOLEAN   [click pencil to edit] ✏️        |
# MAGIC |                                                                    |
# MAGIC +--------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC **Editing a comment — click the pencil icon next to any column:**
# MAGIC
# MAGIC ```
# MAGIC +-- Edit comment: energy_not_served_mwh ----------------------------+
# MAGIC |                                                                   |
# MAGIC |  Energy Not Served (ENS) in megawatt-hours for this outage event. |
# MAGIC |  Formula: estimated demand x outage duration hours.               |
# MAGIC |  NULL for outages < 1 minute.                                     |
# MAGIC |  Use COALESCE(energy_not_served_mwh, 0) in SUM aggregations.     |
# MAGIC |  Reported to AER as part of STPIS incentive scheme.               |
# MAGIC |                                                                   |
# MAGIC |                                  [Cancel]   [Save] ✓             |
# MAGIC +-------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC > **Tip:** Press **Save** then **refresh** the Catalog Explorer page to confirm the comment persisted.
# MAGIC > Genie picks up updated comments on the next conversation — no space restart required.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b — Enrich meter_readings comments via SQL (programmatic path)
# MAGIC
# MAGIC The SQL approach is better for bulk updates across many columns or for scripted deployments.

# COMMAND ----------

# Enrich the columns that most commonly confuse NL-to-SQL models in energy data

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
    COMMENT 'Start of the 30-minute measurement interval in Australian Eastern Standard Time (AEST, UTC+10).
CRITICAL: Do NOT multiply by 2 to convert to hourly — use SUM over the window instead.
To aggregate: SUM(active_energy_kwh) grouped by DATE_TRUNC(''hour'', interval_datetime).
Example value: 2024-06-01T07:00:00 means the 7:00am-7:30am interval on 1 June 2024.'
""")

spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.meter_readings
  ALTER COLUMN active_energy_kwh
    COMMENT 'Kilowatt-hours of active energy imported by the consumer during the 30-minute interval.
Typical residential range: 0.05–4.0 kWh per interval.
To get daily kWh for a meter: SUM(active_energy_kwh) for a given NMI and calendar day.
To get monthly MWh for a zone: SUM(active_energy_kwh) / 1000 grouped by month and distribution_zone.
Do NOT divide by 2 or multiply by 2 — the kWh value is already per-interval.'
""")

print("meter_readings comments updated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c — Enrich outages comments

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
ALWAYS filter outage_type = UNPLANNED for AER regulatory metric calculations.
Updated in near-real-time from SCADA and field crew mobile app.'
""")

print("outages comments updated.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1d — Create a pre-computed SAIDI view (Genie can query views too)
# MAGIC
# MAGIC A powerful pattern: pre-compute complex business metrics as a view, then add the view
# MAGIC as a trusted Genie asset. This simplifies the SQL Genie has to generate and
# MAGIC eliminates one entire class of errors (wrong SAIDI formula).

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.v_saidi_monthly AS
-- Pre-calculated monthly SAIDI numerator per region
-- SAIDI (minutes) = SUM(interruption_minutes x customers_affected) / total_connected_customers
-- This view gives the NUMERATOR. Divide by your total ICP count to get final SAIDI minutes.
-- Source: outages table, UNPLANNED events only, with non-null end_time
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
print()
print("This view pre-computes the SAIDI numerator — Genie can now answer SAIDI questions")
print("without needing to derive the complex aggregation itself.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 2 — Time-Series Awareness Configuration</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#F3F9FF; border:1px solid #90CAF9; padding:16px 20px; border-radius:8px; margin:12px 0;">
# MAGIC   Energy data is inherently time-series. Without explicit guidance, Genie will:
# MAGIC   <ul>
# MAGIC     <li>Interpret "this year" as calendar year (Jan–Dec) instead of Australian financial year (Jul–Jun)</li>
# MAGIC     <li>Multiply 30-min interval kWh by 2 to try to get hourly values (wrong)</li>
# MAGIC     <li>Use Northern Hemisphere season definitions (summer = Jun–Aug instead of Dec–Feb)</li>
# MAGIC   </ul>
# MAGIC   We fix all of these by extending the instructions block.
# MAGIC </div>

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
- Never use end_time - start_time directly without TIMESTAMPDIFF

### Australian Seasons (Southern Hemisphere)
- Summer (peak demand season): December, January, February — MONTH(interval_datetime) IN (12, 1, 2)
- Autumn: March, April, May
- Winter (second demand peak, electric heating): June, July, August — MONTH(interval_datetime) IN (6, 7, 8)
- Spring: September, October, November
"""

# Fetch current instructions and append the time-series block
get_resp = requests.get(
    f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
    headers=hdrs()
)
current_config        = get_resp.json()
existing_instructions = current_config.get("instructions", "")
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
# MAGIC Lab 01 added 5 foundation queries. Now we add more complex patterns involving
# MAGIC window functions, seasonal aggregations, multi-table joins, and year-on-year comparisons.
# MAGIC These cover the question types that most commonly trip up Genie without examples.

# COMMAND ----------

ADVANCED_GOLDEN_QUERIES = [
    {
        "name": "Peak demand days by zone — summer vs winter comparison",
        "description": (
            "Identifies the top 5 peak demand days per distribution zone and season. "
            "Uses CTE + ROW_NUMBER window function. Used for network capacity planning."
        ),
        "sql": f"""
-- Peak demand analysis by season and distribution zone
-- Peak demand proxy: MAX(active_energy_kwh * 2) for the zone across all meters in the 30-min interval
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
    GROUP BY
        distribution_zone,
        DATE(interval_datetime),
        CASE WHEN MONTH(interval_datetime) IN (12,1,2) THEN 'SUMMER'
             WHEN MONTH(interval_datetime) IN (6,7,8)  THEN 'WINTER'
             ELSE 'SHOULDER' END
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY distribution_zone, season
               ORDER BY peak_demand_kw DESC
           ) AS rank_in_season
    FROM daily_peaks
)
SELECT
    distribution_zone,
    season,
    reading_date,
    ROUND(peak_demand_kw, 1)   AS peak_demand_kw,
    ROUND(daily_energy_kwh, 0) AS daily_energy_kwh,
    active_meters
FROM ranked
WHERE rank_in_season <= 5
ORDER BY distribution_zone, season, peak_demand_kw DESC
"""
    },
    {
        "name": "Assets overdue for maintenance inspection",
        "description": (
            "Assets in IN_SERVICE status whose last_maintenance date is more than 12 months ago. "
            "Includes count of outages since last maintenance. Used to prioritise maintenance scheduling."
        ),
        "sql": f"""
-- Assets overdue for inspection: IN_SERVICE and last_maintenance > 12 months ago
SELECT
    a.asset_id,
    a.asset_name,
    a.asset_type,
    a.owner_dnsp,
    a.region,
    a.voltage_kv,
    a.last_maintenance,
    DATEDIFF(CURRENT_DATE, a.last_maintenance)          AS days_since_maintenance,
    COUNT(o.outage_id)                                  AS outages_since_maintenance,
    ROUND(SUM(COALESCE(o.energy_not_served_mwh, 0)), 2) AS ens_since_maintenance_mwh
FROM {CATALOG}.{SCHEMA}.assets a
LEFT JOIN {CATALOG}.{SCHEMA}.outages o
    ON a.asset_id = o.asset_id
   AND o.start_time > a.last_maintenance
WHERE a.status = 'IN_SERVICE'
  AND a.last_maintenance < DATE_SUB(CURRENT_DATE, 365)
GROUP BY
    a.asset_id, a.asset_name, a.asset_type, a.owner_dnsp,
    a.region, a.voltage_kv, a.last_maintenance
ORDER BY days_since_maintenance DESC
"""
    },
    {
        "name": "SAIDI year-to-date vs same period prior year by region",
        "description": (
            "Year-on-year SAIDI comparison for AER reporting. Uses a fixed denominator of "
            "1,000,000 ICPs for this example — replace with your actual customer register count."
        ),
        "sql": f"""
-- YoY SAIDI comparison using FULL OUTER JOIN across two year CTEs
-- TODO: replace 1000000 with actual ICP count from your customer register
WITH params AS (
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
    COALESCE(c.region, p.region)                                         AS region,
    ROUND(COALESCE(c.saidi_numerator, 0) / params.total_icps, 2)         AS saidi_ytd_minutes,
    ROUND(COALESCE(p.saidi_numerator, 0) / params.total_icps, 2)         AS saidi_prior_year_minutes,
    ROUND(
        (COALESCE(c.saidi_numerator, 0) - COALESCE(p.saidi_numerator, 0))
        / NULLIF(p.saidi_numerator, 0) * 100
    , 1)                                                                 AS pct_change_vs_prior_year
FROM current_year c
FULL OUTER JOIN prior_year p ON c.region = p.region
CROSS JOIN params
ORDER BY region
"""
    },
]

print("Pushing advanced golden queries...")
print()
for q in ADVANCED_GOLDEN_QUERIES:
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=hdrs(),
        json={"name": q["name"], "description": q["description"], "query": q["sql"].strip()}
    )
    icon = "OK  " if resp.status_code in (200, 201) else f"ERROR {resp.status_code}: {resp.text[:60]}"
    print(f"  [{icon}]  {q['name']}")

print()
print("Advanced golden queries added. Total in knowledge store: 5 (Lab01) + 3 (Lab02) = 8")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 4 — Enable and Test Genie Agent Mode</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#F3F9FF; border:1px solid #90CAF9; padding:16px 20px; border-radius:8px; margin:12px 0;">
# MAGIC
# MAGIC | Capability | Chat mode | Agent mode |
# MAGIC |---|---|---|
# MAGIC | Single-table queries | Yes | Yes |
# MAGIC | Multi-step reasoning | Limited | Yes |
# MAGIC | Automatic multi-table joins | Sometimes | Yes |
# MAGIC | Follow-up clarification questions | No | Yes |
# MAGIC | Tool use (search, compute) | No | Yes |
# MAGIC | Typical response time | ~3 seconds | 10–30 seconds |
# MAGIC
# MAGIC Agent mode is the right choice for operational users who ask complex multi-part questions.
# MAGIC Chat mode is better for dashboards or simpler analyst "show me this metric" workflows.
# MAGIC
# MAGIC **AU East availability:** Both modes are fully in-region for Australia East as of April 2026.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Enabling Agent mode in the UI
# MAGIC
# MAGIC **Navigation:** Open your Genie Space --> Chat tab --> look for the mode toggle
# MAGIC
# MAGIC ```
# MAGIC +-- NEM Grid Operations -- Energy Analytics --------------------------------+
# MAGIC |   [Chat]   [Configure]                                                    |
# MAGIC |                                                                           |
# MAGIC |   Chat                                                   [Chat | Agent]   |
# MAGIC |                                                            ^ toggle here  |
# MAGIC |   -----------------------------------------------------------------------  |
# MAGIC |   Hi! I can help you explore your energy data.                            |
# MAGIC |   What would you like to know?                                            |
# MAGIC |                                                                           |
# MAGIC |   [Type your question here...]                        [Ask ->]            |
# MAGIC +----------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC When you switch to **Agent** mode you will see a different greeting and the model will
# MAGIC ask clarifying questions before running SQL for complex multi-part questions.

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

# MAGIC %md
# MAGIC ### Testing Agent mode via the Conversation API
# MAGIC
# MAGIC Agent mode accepts the same API — add `"mode": "AGENT"` to the start-conversation request.

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
print("  3. Join the two results and compare to averages")
print("  => Multi-step reasoning — Agent mode handles this; Chat mode may struggle.")
print()

# Uncomment to run (takes 10-30 seconds)
# result = genie_ask_agent(SPACE_ID, AGENT_TEST_QUESTION)
# print(f"Status: {result.get('status')}")
# for att in result.get("attachments", []):
#     if att.get("query"):
#         print(f"SQL:\n{att['query'].get('query', '')[:400]}")
print("(Uncomment the result = genie_ask_agent(...) block above to run the test)")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 5 — SharePoint and Google Drive as Genie Data Sources</h2>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:5px solid #2E7D32; padding:16px 20px; border-radius:0 8px 8px 0; margin:12px 0;">
# MAGIC   <strong>GA from April 2026 — in-region for AU East</strong><br>
# MAGIC   Genie can now query unstructured documents (PDFs, Word docs, spreadsheets) stored in
# MAGIC   SharePoint or Google Drive directly, without needing to ingest them into Delta tables first.
# MAGIC   This is delivered via the UC AI Gateway + Genie RAG path announced April 26, 2026.
# MAGIC </div>
# MAGIC
# MAGIC ### When to use the native connector vs ingesting to Delta
# MAGIC
# MAGIC | Approach | Use when |
# MAGIC |---|---|
# MAGIC | **SharePoint/Drive connector** | Documents change frequently; document owners maintain them in SharePoint or Drive |
# MAGIC | **Ingest to Delta + Genie** | Need SQL aggregation over document metadata; large document volumes; structured extraction |
# MAGIC | **Both** | Best coverage: structured data in Delta + unstructured documents via connector |
# MAGIC
# MAGIC ### Setup steps in the UI
# MAGIC
# MAGIC ```
# MAGIC +-- Configure: Data Sources ------------------------------------------+
# MAGIC |                                                                     |
# MAGIC |   Genie Space --> Configure --> Data Sources tab                    |
# MAGIC |                                                                     |
# MAGIC |   [+ Add Data Source]                                               |
# MAGIC |                                                                     |
# MAGIC |   Choose source:                                                    |
# MAGIC |   [SharePoint]   [Google Drive]   [OneDrive]                       |
# MAGIC |                                                                     |
# MAGIC |   SharePoint setup:                                                 |
# MAGIC |   1. Authenticate with your M365 credentials                       |
# MAGIC |   2. Enter SharePoint site URL:                                     |
# MAGIC |      [ https://yourorg.sharepoint.com/sites/NetworkOps      ]      |
# MAGIC |   3. Choose folder or document library:                             |
# MAGIC |      [ Regulatory Reports / FY2024                          ]      |
# MAGIC |   4. Click [Index documents] -- Genie crawls and embeds files      |
# MAGIC |                                                                     |
# MAGIC |   Status: Indexing... (may take 2-5 minutes for large libraries)   |
# MAGIC |                                                                     |
# MAGIC |                                        [Done] ✓                   |
# MAGIC +---------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ### Embedding model selection — critical for AU data residency
# MAGIC
# MAGIC The embedding model used for indexing must be in-region to keep data in AU East.

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
print("Selecting the wrong model sends document embeddings to a non-AU region.")
print("For regulated industries (APRA, AER, AUSTRAC) this may breach data residency requirements.")

# COMMAND ----------

# Document the correct embedding model for this workshop
IN_REGION_EMBED_MODEL = "databricks-qwen3-embedding-0-6b"

print(f"In-region embedding model: {IN_REGION_EMBED_MODEL}")
print()
print("To embed documents via API:")
print(f"  POST https://{{host}}/serving-endpoints/{IN_REGION_EMBED_MODEL}/invocations")
print('  {"input": ["document text to embed"]}')
print()
print("This model runs on AU East compute — no document content leaves the region.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 6 — Troubleshooting: Why Genie Gives Wrong Answers</h2>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Diagnostic framework — work through this checklist when a user reports a wrong answer

# COMMAND ----------

TROUBLESHOOTING_GUIDE = """
GENIE ACCURACY TROUBLESHOOTING GUIDE
======================================

SYMPTOM 1: Genie uses the wrong table for a query
--------------------------------------------------
Root cause: Table comments are missing or ambiguous — Genie guesses from question wording.
Fix:
  ALTER TABLE t SET COMMENT 'One row = one X. Source system: Y. Updated: daily.'
  Make table-level comments describe grain and source clearly.
  Add a golden query that demonstrates the correct table to use.

SYMPTOM 2: Genie generates correct SQL structure but wrong numbers
-----------------------------------------------------------------
Root cause: Aggregation logic is incorrect (e.g. counting rows instead of summing metric,
            wrong SAIDI formula, not filtering to UNPLANNED outages only).
Fix:
  Add a golden query that shows the EXACT aggregation formula with SQL comments.
  In instructions, spell out: "SAIDI = SUM(duration_minutes x customers) / total_icps"
  Add: "Filter outage_type = 'UNPLANNED' for all AER regulatory calculations."

SYMPTOM 3: Genie joins tables with a cartesian product or wrong key
-------------------------------------------------------------------
Root cause: FK relationships are not documented in column comments.
Fix:
  Add COMMENT to FK columns: "FK -> parent_table.pk_column"
  Add a golden query that shows the correct JOIN syntax.

SYMPTOM 4: "This year" returns wrong date range
-----------------------------------------------
Root cause: Instructions do not specify Australian financial year convention.
Fix:
  Add to instructions: "This year = current Australian financial year (July 1 – June 30)"
  Add golden queries that use the correct financial year date arithmetic.

SYMPTOM 5: Genie hallucinates column names that don't exist
-----------------------------------------------------------
Root cause: Genie is guessing column names from question wording rather than schema.
Fix:
  Run: DESCRIBE TABLE your_catalog.your_schema.your_table
  Add column aliases in golden queries that map user language to actual columns:
    SELECT active_energy_kwh AS consumption_kwh FROM meter_readings
  Add a golden query that uses the real column name with a business-friendly alias.

SYMPTOM 6: Genie answers correctly but very slowly (> 30 seconds)
-----------------------------------------------------------------
Root cause: Full table scan on a large partitioned table; no date filter applied.
Fix:
  Document in instructions: "Always include a date filter when querying meter_readings."
  Add ZORDER BY on common filter columns (e.g. interval_datetime).
  Create pre-aggregated views for common question patterns.

SYMPTOM 7: Genie says "I cannot answer this question"
-----------------------------------------------------
Root cause: Table not in trusted assets, or instructions are accidentally too restrictive.
Fix:
  Verify the table is in trusted assets (Configure --> Tables tab).
  Check instructions don't contain "do not query X" accidentally.
  Add a golden query for the question pattern.

SYMPTOM 8: Genie multiplies interval data by 2 (wrong hourly totals)
--------------------------------------------------------------------
Root cause: Genie infers 30-min intervals should be doubled for hourly values.
Fix:
  Add to column comment: "Do NOT multiply by 2 to get hourly totals — use SUM over the window."
  Add to instructions: "Each meter_readings row is a 30-minute interval. Never multiply by 2."
  Add a golden query showing correct hourly aggregation with DATE_TRUNC.
"""

print(TROUBLESHOOTING_GUIDE)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 7 — Space Health Check</h2>
# MAGIC </div>
# MAGIC
# MAGIC Run this automated health check to assess the quality of your Genie Space configuration.

# COMMAND ----------

def check_genie_space_health(space_id: str, catalog: str, schema: str) -> None:
    """
    Heuristic health check for a Genie Space configuration.
    Checks instructions length, agent mode, trusted assets, golden queries, and table comments.
    """
    issues   = []
    ok_msgs  = []
    warnings = []

    # Check 1: Instructions length
    s         = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}", headers=hdrs()).json()
    instr_len = len(s.get("instructions", ""))
    if instr_len < 200:
        issues.append(f"ERROR: Instructions too short ({instr_len} chars). Aim for 500–3000 chars.")
    elif instr_len > 7000:
        warnings.append(f"WARN: Instructions very long ({instr_len} chars). May approach token limits.")
    else:
        ok_msgs.append(f"OK: Instructions length = {instr_len:,} chars (good range: 500–3000)")

    # Check 2: Agent mode
    if s.get("enable_agent_mode"):
        ok_msgs.append("OK: Agent mode is enabled (good for complex multi-step questions)")
    else:
        warnings.append("INFO: Agent mode not enabled (acceptable for simple analyst use cases)")

    # Check 3: Trusted assets
    ar = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}/trusted-assets", headers=hdrs())
    if ar.status_code == 200:
        n_assets = len(ar.json().get("trusted_assets", []))
        if n_assets == 0:
            issues.append("ERROR: No trusted assets — Genie cannot query anything!")
        elif n_assets < 2:
            warnings.append(f"WARN: Only {n_assets} trusted asset(s). Add more tables for richer coverage.")
        else:
            ok_msgs.append(f"OK: {n_assets} trusted asset(s) configured")
    else:
        warnings.append(f"WARN: Could not check trusted assets (HTTP {ar.status_code})")

    # Check 4: Golden queries
    qr = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{space_id}/sql-queries", headers=hdrs())
    if qr.status_code == 200:
        n_queries = len(qr.json().get("sql_queries", []))
        if n_queries == 0:
            issues.append("ERROR: No golden queries. Add at least 5 for common question patterns.")
        elif n_queries < 5:
            warnings.append(f"WARN: Only {n_queries} golden quer(ies). Aim for 10+ for production spaces.")
        else:
            ok_msgs.append(f"OK: {n_queries} golden quer(ies) in knowledge store")
    else:
        warnings.append(f"WARN: Could not check golden queries (HTTP {qr.status_code})")

    # Check 5: Tables have non-empty comments
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
        warnings.append(f"WARN: Tables missing comments: {no_comment_tables}")
    else:
        ok_msgs.append("OK: All 4 expected tables have table-level comments")

    # Print report
    print("GENIE SPACE HEALTH REPORT")
    print("=" * 55)
    print(f"  Space ID   : {space_id}")
    print(f"  Space title: {s.get('title', 'unknown')}")
    print()
    for msg in ok_msgs:
        print(f"  [OK ]  {msg.replace('OK: ', '')}")
    for msg in warnings:
        print(f"  [WARN]  {msg.replace('WARN: ', '').replace('INFO: ', '')}")
    for msg in issues:
        print(f"  [ERR]  {msg.replace('ERROR: ', '')}")
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
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Step 8 — Inspect Full Configuration via API</h2>
# MAGIC </div>
# MAGIC
# MAGIC Use this cell to print a summary of everything currently configured in the space.
# MAGIC Useful for auditing before handing over to business users.

# COMMAND ----------

# Fetch and display full configuration summary
space_resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=hdrs())
config     = space_resp.json()

print("CURRENT GENIE SPACE CONFIGURATION")
print("=" * 55)
print(f"  Title              : {config.get('title')}")
print(f"  Space ID           : {config.get('space_id')}")
print(f"  Instructions chars : {len(config.get('instructions', '')):,}")
print(f"  Agent mode         : {config.get('enable_agent_mode', False)}")
print()

# Trusted assets
ar = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/trusted-assets", headers=hdrs())
if ar.status_code == 200:
    assets = ar.json().get("trusted_assets", [])
    print(f"Trusted Assets ({len(assets)}):")
    for a in assets:
        print(f"  - {a.get('asset_fqn')}  ({a.get('asset_type')})")
else:
    print(f"Could not list trusted assets: HTTP {ar.status_code}")

print()

# Golden queries
qr = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries", headers=hdrs())
if qr.status_code == 200:
    queries = qr.json().get("sql_queries", [])
    print(f"Golden Queries ({len(queries)}):")
    for q in queries:
        print(f"  - {q.get('name')}")
else:
    print(f"Could not list golden queries: HTTP {qr.status_code}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 02 — Review Questions
# MAGIC
# MAGIC <div style="background:#F5F5F5; padding:20px 24px; border-radius:8px; margin:12px 0;">
# MAGIC
# MAGIC 1. You have a column `quality_flag` with values A, E, S, N. A business analyst is getting
# MAGIC    inflated consumption totals. Write the column comment you would add to help Genie
# MAGIC    automatically exclude bad quality data.
# MAGIC
# MAGIC 2. A user asks Genie "show me peak demand for summer" but the result is wrong because
# MAGIC    the model multiplied 30-min intervals by 2. What **two specific changes** would you make
# MAGIC    (one to a column comment, one to the instructions block)?
# MAGIC
# MAGIC 3. Agent mode vs Chat mode: for the question "Which substations had the most outages
# MAGIC    in zones with high consumption growth?" — which mode is better and why?
# MAGIC
# MAGIC 4. For the SharePoint connector (GA April 2026), which embedding model should you use
# MAGIC    for AU East data residency, and what is the risk of using the wrong model for an
# MAGIC    APRA-regulated institution?
# MAGIC
# MAGIC 5. The health checker reports "Only 2 trusted assets" but your schema has 10 tables.
# MAGIC    Walk through three steps to diagnose why the missing tables are not appearing.
# MAGIC
# MAGIC </div>
# MAGIC
# MAGIC **Proceed to Lab 03 when ready.**
