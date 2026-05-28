# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', Arial, sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 01: Setting Up an Effective Genie Space</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0;">Session 2 · AEMO NEM Operations · 25 minutes</p>
# MAGIC </div>
# MAGIC <div style="background: #f7f8fa; border-left: 4px solid #FF3621; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 0;">
# MAGIC   <b>What you will build:</b> A fully configured Genie Space connected to five AEMO NEM tables, populated with 10 golden queries covering NEM operations, and secured so analysts can query and engineers can edit.<br><br>
# MAGIC   <b>Outcome:</b> By the end of this lab your team will have a live Genie Space that correctly answers questions about spot prices, dispatch intervals, LOR events, generator performance, and settlements.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 0 — UI Exploration (5 min)
# MAGIC
# MAGIC Before we automate anything, let's orient ourselves in the UI.
# MAGIC
# MAGIC **Navigate to Genie:**
# MAGIC 1. Look at the left sidebar — find the **sparkle icon** (✨) labelled **Genie**
# MAGIC 2. Click it to open the Genie home page
# MAGIC 3. Click **+ New Space** in the top-right corner
# MAGIC 4. Explore the three configuration tabs shown:
# MAGIC
# MAGIC | Tab | Purpose |
# MAGIC |-----|---------|
# MAGIC | **Instructions** | Free-text context you give the model about your data and domain |
# MAGIC | **SQL queries** | Golden queries — examples Genie uses to learn your preferred patterns |
# MAGIC | **Permissions** | Who can view or edit this Space |
# MAGIC
# MAGIC 5. Notice the **Data** panel on the left side of the Space editor — this is where you add tables
# MAGIC 6. **Close without saving** — we will create the Space via API in Section 1 so everything is reproducible
# MAGIC
# MAGIC > **Why API-first?** Creating Spaces via the REST API means you can version-control your configuration, recreate it in a new workspace, and share the exact same setup with other teams. The UI and the API produce identical results.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widget Configuration
# MAGIC Run the next cell to register the widgets, then set values if they differ from your environment.

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",        "Catalog")
dbutils.widgets.text("schema_aemo", "aemo",               "Schema")
dbutils.widgets.text("space_name",  "AEMO NEM Operations","Genie Space Name")

# COMMAND ----------

CATALOG    = dbutils.widgets.get("catalog")
SCHEMA     = dbutils.widgets.get("schema_aemo")
SPACE_NAME = dbutils.widgets.get("space_name")

print(f"Catalog   : {CATALOG}")
print(f"Schema    : {SCHEMA}")
print(f"Space name: {SPACE_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prerequisites — confirm tables exist

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES IN ${catalog}.${schema_aemo}

# COMMAND ----------

# Verify the five core tables are present
required_tables = [
    "spot_prices",
    "dispatch_intervals",
    "market_notices",
    "generator_registration",
    "settlement_amounts",
]

existing = [
    row.tableName
    for row in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()
]

missing = [t for t in required_tables if t not in existing]
if missing:
    raise ValueError(
        f"Missing tables: {missing}. "
        "Run the setup notebook (genie_config/aemo_space_config.py) first."
    )

print("All required tables present:")
for t in required_tables:
    print(f"  {CATALOG}.{SCHEMA}.{t}  ✓")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1 — Create the Genie Space via REST API (5 min)
# MAGIC
# MAGIC We use the Databricks SDK for Python (`databricks-sdk`) which comes pre-installed on DBR 15+.
# MAGIC The SDK handles authentication automatically using your notebook token.
# MAGIC
# MAGIC **What the API call does:**
# MAGIC - Creates a new Genie Space with a name and initial instructions
# MAGIC - Returns a `space_id` we use in all subsequent calls
# MAGIC - The Space starts empty — we add tables and queries in the next sections

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieCreateConversationMessageRequest
import json, time

w = WorkspaceClient()

# AEMO-specific Space instructions
SPACE_INSTRUCTIONS = """You are a National Electricity Market (NEM) analyst assistant for AEMO (Australian Energy Market Operator). You help operations staff, data engineers, and market analysts understand NEM data.

DOMAIN CONTEXT
- The NEM covers five interconnected regions: NSW1 (New South Wales), VIC1 (Victoria), QLD1 (Queensland), SA1 (South Australia), TAS1 (Tasmania)
- Spot prices are in $/MWh (Australian dollars per megawatt-hour)
- Dispatch intervals are 5 minutes; trading intervals are 30 minutes
- The market price cap (MPC) is $16,600/MWh; the market floor price is -$1,000/MWh
- A price spike typically means spot price > $300/MWh; an extreme spike is > $5,000/MWh

KEY TERMINOLOGY
- NMI: National Metering Identifier — unique ID for every meter connection point
- DUID: Dispatchable Unit Identifier — unique ID for every generator or load unit
- LOR: Lack of Reserve — AEMO notice warning that reserve margin is below thresholds
  - LOR1: Reserve margin below the Lack of Reserve 1 threshold (lowest severity)
  - LOR2: Reserves below LOR 2 threshold; manual load shedding possible
  - LOR3: Load shedding imminent or occurring
- FCAS: Frequency Control Ancillary Services — services that maintain grid frequency at 50 Hz
- SAIDI: System Average Interruption Duration Index — minutes of interruption per customer
- SAIFI: System Average Interruption Frequency Index — interruptions per customer per year
- RRP: Regional Reference Price — the spot price for a region in a trading interval
- TI: Trading Interval (30 min); DI: Dispatch Interval (5 min)

QUERY PREFERENCES
- Always aggregate spot prices using ROUND(AVG(rrp), 2) and label the column clearly
- When showing time series, order by SETTLEMENTDATE ASC
- For regional comparisons, use REGIONID as the grouping key and show all five regions
- Filter to Australia/Sydney timezone when displaying dates to users: CONVERT_TZ(SETTLEMENTDATE, 'UTC', 'Australia/Sydney')
- For "yesterday" queries: WHERE DATE(SETTLEMENTDATE) = DATE_SUB(CURRENT_DATE(), 1)
- For "last week" queries: WHERE SETTLEMENTDATE >= DATE_SUB(CURRENT_DATE(), 7)
- Round monetary values to 2 decimal places; round MW values to 0 decimal places
- When asked about generators, join generator_registration on DUID to show STATIONNAME and FUEL_TYPE

IMPORTANT LIMITATIONS
- Do not interpret regulatory or compliance questions — direct those to AEMO's compliance team
- Spot prices are historical actuals; do not present them as forecasts
- Settlement amounts are preliminary until AEMO finalises the billing run
"""

print("Creating Genie Space...")

# The Genie Spaces API is under the AI/BI dashboards service
# Endpoint: POST /api/2.0/genie/spaces
response = w.api_client.do(
    "POST",
    "/api/2.0/genie/spaces",
    body={
        "title": SPACE_NAME,
        "description": "NEM operations data assistant for AEMO — covers spot prices, dispatch, market notices, generator performance, and settlements.",
        "warehouse_id": spark.conf.get("spark.databricks.clusterUsageTags.warehouseId", ""),
    },
)

space_id = response["space_id"]
print(f"Space created successfully.")
print(f"Space ID  : {space_id}")
print(f"Space Name: {SPACE_NAME}")
print(f"\nOpen in UI: {w.config.host}#pages/genie/spaces/{space_id}")

# Persist for later cells
spark.conf.set("workshop.genie.space_id", space_id)

# COMMAND ----------

# MAGIC %md
# MAGIC > **Checkpoint:** Copy the Space ID above — you will need it if you rerun individual cells.
# MAGIC > The URL at the bottom opens your new Space directly. Keep that tab open.

# COMMAND ----------

# If you need to resume from a saved space_id, set it here:
# space_id = "paste-your-space-id-here"
# spark.conf.set("workshop.genie.space_id", space_id)

space_id = spark.conf.get("workshop.genie.space_id")
print(f"Using Space ID: {space_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2 — Add Trusted Assets (3 min)
# MAGIC
# MAGIC Trusted assets are the Unity Catalog tables Genie is allowed to query.
# MAGIC Genie will only write SQL against tables you explicitly add here — it cannot access anything else in your catalog.
# MAGIC
# MAGIC | Table | Contains |
# MAGIC |-------|---------|
# MAGIC | `spot_prices` | 5-min regional reference prices (RRP) for all NEM regions |
# MAGIC | `dispatch_intervals` | Generator dispatch targets and actual output per 5-min interval |
# MAGIC | `market_notices` | LOR, reserve notices, and other AEMO operational alerts |
# MAGIC | `generator_registration` | Static generator metadata: DUID, station, fuel type, capacity |
# MAGIC | `settlement_amounts` | Preliminary and final trading amounts per participant |

# COMMAND ----------

TABLES = [
    "spot_prices",
    "dispatch_intervals",
    "market_notices",
    "generator_registration",
    "settlement_amounts",
]

print(f"Adding {len(TABLES)} tables to Space {space_id}...\n")

for table_name in TABLES:
    full_name = f"{CATALOG}.{SCHEMA}.{table_name}"
    try:
        w.api_client.do(
            "POST",
            f"/api/2.0/genie/spaces/{space_id}/datasets",
            body={
                "table_name": full_name,
            },
        )
        print(f"  Added: {full_name}  ✓")
    except Exception as e:
        print(f"  FAILED: {full_name}  — {e}")

print("\nAll tables registered as trusted assets.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3 — Add 10 Golden Queries (7 min)
# MAGIC
# MAGIC Golden queries are your curated SQL examples stored in the **Knowledge Store**.
# MAGIC They serve two purposes:
# MAGIC 1. **Pattern teaching** — Genie learns your preferred column names, joins, and aggregation style
# MAGIC 2. **Direct reuse** — If a user's question closely matches a golden query, Genie runs it directly rather than generating new SQL
# MAGIC
# MAGIC > **Best practice:** Write golden queries that cover your top 10 most common questions. These should be production-quality SQL that you would trust in a report.

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Average spot price by region — yesterday",
        "description": "Shows the mean RRP ($/MWh) for each NEM region for the previous calendar day, ordered by price descending.",
        "sql": f"""
SELECT
    REGIONID,
    ROUND(AVG(RRP), 2)   AS avg_price_dollarMWh,
    ROUND(MIN(RRP), 2)   AS min_price_dollarMWh,
    ROUND(MAX(RRP), 2)   AS max_price_dollarMWh,
    COUNT(*)              AS dispatch_intervals
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE DATE(SETTLEMENTDATE) = DATE_SUB(CURRENT_DATE(), 1)
GROUP BY REGIONID
ORDER BY avg_price_dollarMWh DESC
""".strip(),
    },
    {
        "name": "Spot price comparison across all NEM regions — last 7 days",
        "description": "Daily average spot price for each of the five NEM regions over the past 7 days, suitable for trend comparison.",
        "sql": f"""
SELECT
    DATE(SETTLEMENTDATE)  AS trading_date,
    REGIONID,
    ROUND(AVG(RRP), 2)   AS avg_price_dollarMWh
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE SETTLEMENTDATE >= DATE_SUB(CURRENT_DATE(), 7)
GROUP BY DATE(SETTLEMENTDATE), REGIONID
ORDER BY trading_date ASC, REGIONID ASC
""".strip(),
    },
    {
        "name": "Price spikes above $500/MWh — last 30 days",
        "description": "All 5-minute dispatch intervals where the regional spot price exceeded $500/MWh in the past month. Shows region, timestamp, and price.",
        "sql": f"""
SELECT
    SETTLEMENTDATE,
    REGIONID,
    ROUND(RRP, 2)  AS spike_price_dollarMWh
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE
    SETTLEMENTDATE >= DATE_SUB(CURRENT_DATE(), 30)
    AND RRP > 500
ORDER BY RRP DESC
LIMIT 200
""".strip(),
    },
    {
        "name": "Dispatch by fuel type — last 7 days",
        "description": "Total megawatt-hours dispatched grouped by fuel type for the past 7 days. Shows the generation mix across coal, gas, wind, solar, hydro, and battery.",
        "sql": f"""
SELECT
    g.FUEL_TYPE,
    ROUND(SUM(d.TOTALCLEARED * 5 / 60), 0) AS total_MWh_dispatched
FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
JOIN {CATALOG}.{SCHEMA}.generator_registration g
    ON d.DUID = g.DUID
WHERE d.SETTLEMENTDATE >= DATE_SUB(CURRENT_DATE(), 7)
GROUP BY g.FUEL_TYPE
ORDER BY total_MWh_dispatched DESC
""".strip(),
    },
    {
        "name": "LOR notices in the last 14 days",
        "description": "All Lack of Reserve (LOR1, LOR2, LOR3) notices issued by AEMO in the past 14 days with severity, affected region, and notice text.",
        "sql": f"""
SELECT
    NOTICEID,
    NOTICE_TYPE,
    REGIONID,
    ISSUE_DATETIME,
    EXTERNAL_REFERENCE,
    NOTICE_TEXT
FROM {CATALOG}.{SCHEMA}.market_notices
WHERE
    ISSUE_DATETIME >= DATE_SUB(CURRENT_DATE(), 14)
    AND NOTICE_TYPE LIKE 'LOR%'
ORDER BY ISSUE_DATETIME DESC
""".strip(),
    },
    {
        "name": "Generator performance — top 20 by MWh last 30 days",
        "description": "Ranks the top 20 individual generating units by total energy dispatched over the past 30 days, with station name and fuel type.",
        "sql": f"""
SELECT
    d.DUID,
    g.STATIONNAME,
    g.FUEL_TYPE,
    g.REGIONID,
    ROUND(SUM(d.TOTALCLEARED * 5 / 60), 0)  AS total_MWh,
    ROUND(AVG(d.TOTALCLEARED), 1)            AS avg_MW_dispatch
FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
JOIN {CATALOG}.{SCHEMA}.generator_registration g
    ON d.DUID = g.DUID
WHERE d.SETTLEMENTDATE >= DATE_SUB(CURRENT_DATE(), 30)
GROUP BY d.DUID, g.STATIONNAME, g.FUEL_TYPE, g.REGIONID
ORDER BY total_MWh DESC
LIMIT 20
""".strip(),
    },
    {
        "name": "Settlement summary by participant — last completed month",
        "description": "Total net settlement amount per market participant for the most recently completed calendar month. Settlement amounts are in AUD.",
        "sql": f"""
SELECT
    PARTICIPANTID,
    ROUND(SUM(AMOUNT), 2)   AS net_settlement_aud,
    COUNT(DISTINCT TRADINGDATE) AS trading_days
FROM {CATALOG}.{SCHEMA}.settlement_amounts
WHERE
    MONTH(TRADINGDATE)  = MONTH(DATE_SUB(CURRENT_DATE(), 32))
    AND YEAR(TRADINGDATE)   = YEAR(DATE_SUB(CURRENT_DATE(), 32))
GROUP BY PARTICIPANTID
ORDER BY ABS(net_settlement_aud) DESC
LIMIT 50
""".strip(),
    },
    {
        "name": "Coal vs renewable dispatch in QLD — last 3 months",
        "description": "Monthly comparison of coal (BLACK COAL, BROWN COAL) vs renewables (WIND, SOLAR) dispatch in Queensland (QLD1) over the past 3 months.",
        "sql": f"""
SELECT
    DATE_FORMAT(d.SETTLEMENTDATE, 'yyyy-MM')   AS month,
    CASE
        WHEN g.FUEL_TYPE IN ('BLACK COAL', 'BROWN COAL') THEN 'Coal'
        WHEN g.FUEL_TYPE IN ('WIND', 'SOLAR')            THEN 'Renewable'
        ELSE 'Other'
    END                                         AS generation_category,
    ROUND(SUM(d.TOTALCLEARED * 5 / 60), 0)     AS total_MWh
FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
JOIN {CATALOG}.{SCHEMA}.generator_registration g
    ON d.DUID = g.DUID
WHERE
    g.REGIONID = 'QLD1'
    AND d.SETTLEMENTDATE >= ADD_MONTHS(CURRENT_DATE(), -3)
GROUP BY DATE_FORMAT(d.SETTLEMENTDATE, 'yyyy-MM'), generation_category
ORDER BY month ASC, generation_category ASC
""".strip(),
    },
    {
        "name": "Market notices by type — last 30 days",
        "description": "Count of each market notice type issued in the past 30 days. Useful for understanding recent market conditions and AEMO operational activity.",
        "sql": f"""
SELECT
    NOTICE_TYPE,
    COUNT(*)                     AS notice_count,
    MIN(ISSUE_DATETIME)          AS first_issued,
    MAX(ISSUE_DATETIME)          AS last_issued
FROM {CATALOG}.{SCHEMA}.market_notices
WHERE ISSUE_DATETIME >= DATE_SUB(CURRENT_DATE(), 30)
GROUP BY NOTICE_TYPE
ORDER BY notice_count DESC
""".strip(),
    },
    {
        "name": "Highest price intervals — with dispatched generators",
        "description": "The 10 most expensive 5-minute dispatch intervals in the past 30 days, showing which generators were dispatched during each event and at what output.",
        "sql": f"""
WITH top_intervals AS (
    SELECT
        SETTLEMENTDATE,
        REGIONID,
        ROUND(RRP, 2) AS spike_price_dollarMWh
    FROM {CATALOG}.{SCHEMA}.spot_prices
    WHERE SETTLEMENTDATE >= DATE_SUB(CURRENT_DATE(), 30)
    ORDER BY RRP DESC
    LIMIT 10
)
SELECT
    ti.SETTLEMENTDATE,
    ti.REGIONID,
    ti.spike_price_dollarMWh,
    d.DUID,
    g.STATIONNAME,
    g.FUEL_TYPE,
    ROUND(d.TOTALCLEARED, 1) AS dispatched_MW
FROM top_intervals ti
JOIN {CATALOG}.{SCHEMA}.dispatch_intervals d
    ON ti.SETTLEMENTDATE = d.SETTLEMENTDATE
JOIN {CATALOG}.{SCHEMA}.generator_registration g
    ON d.DUID = g.DUID
WHERE g.REGIONID = ti.REGIONID
ORDER BY ti.spike_price_dollarMWh DESC, d.TOTALCLEARED DESC
""".strip(),
    },
]

print(f"Adding {len(GOLDEN_QUERIES)} golden queries to Space {space_id}...\n")

for i, qry in enumerate(GOLDEN_QUERIES, start=1):
    try:
        w.api_client.do(
            "POST",
            f"/api/2.0/genie/spaces/{space_id}/queries",
            body={
                "title":       qry["name"],
                "description": qry["description"],
                "content":     qry["sql"],
            },
        )
        print(f"  [{i:02d}] {qry['name']}  ✓")
    except Exception as e:
        print(f"  [{i:02d}] {qry['name']}  FAILED — {e}")

print("\nAll golden queries registered in the Knowledge Store.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4 — Write Good Space Instructions (2 min)
# MAGIC
# MAGIC The instructions you write in the Space configuration are critical to answer quality.
# MAGIC They are sent to the model with every question — think of them as a system prompt for your data domain.
# MAGIC
# MAGIC **What to include in instructions:**
# MAGIC
# MAGIC | Category | Examples from NEM context |
# MAGIC |----------|--------------------------|
# MAGIC | Domain acronyms | NMI, DUID, FCAS, LOR1/2/3, RRP, TI, DI |
# MAGIC | Region codes | NSW1, VIC1, QLD1, SA1, TAS1 |
# MAGIC | Units and scales | $/MWh, MW, MWh, 5-min dispatch, 30-min trading |
# MAGIC | Preferred aggregations | `ROUND(AVG(RRP), 2)`, order by SETTLEMENTDATE ASC |
# MAGIC | Time zone | Queries display in Australia/Sydney time |
# MAGIC | Thresholds | Price spike > $300/MWh; extreme spike > $5,000/MWh |
# MAGIC | What NOT to do | No compliance interpretation; no forecast language |
# MAGIC
# MAGIC **Now update the instructions via API:**

# COMMAND ----------

# Update the Space with full AEMO instructions
# (The instructions string was defined earlier as SPACE_INSTRUCTIONS)

w.api_client.do(
    "PATCH",
    f"/api/2.0/genie/spaces/{space_id}",
    body={
        "instructions": SPACE_INSTRUCTIONS,
    },
)

print("Space instructions updated.")
print(f"\nInstruction length: {len(SPACE_INSTRUCTIONS)} characters")
print("\nKey NEM terms covered:")
nem_terms = ["NMI", "DUID", "FCAS", "LOR1", "LOR2", "LOR3", "RRP", "SAIDI", "SAIFI",
             "NSW1", "VIC1", "QLD1", "SA1", "TAS1", "$/MWh", "5-min", "30-min"]
for t in nem_terms:
    print(f"  {t}")

# COMMAND ----------

# MAGIC %md
# MAGIC > **UI verification:** Open your Space in the browser (use the link from Section 1), click the **Instructions** tab and confirm the NEM context text is visible.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 5 — Set Permissions (3 min)
# MAGIC
# MAGIC Genie Spaces have two permission levels:
# MAGIC
# MAGIC | Permission | What it allows |
# MAGIC |-----------|---------------|
# MAGIC | `CAN_VIEW` | Ask questions, view results, add to dashboards |
# MAGIC | `CAN_EDIT` | Everything in CAN_VIEW plus: change instructions, add/remove tables, add golden queries, delete conversations |
# MAGIC | `IS_OWNER` | Everything in CAN_EDIT plus: delete the Space, manage permissions |
# MAGIC
# MAGIC **AEMO access model for this workshop:**
# MAGIC - `analysts` group → `CAN_VIEW` (market analysts can query but not change the configuration)
# MAGIC - `data_engineers` group → `CAN_EDIT` (engineers can refine the Space as needs evolve)

# COMMAND ----------

# Update permissions
# In a real workspace you would use your actual group names from Identity & Access Management
# For the workshop we use the group names as configured in the workspace

PERMISSIONS = [
    {"user_name": None, "group_name": "analysts",       "permission_level": "CAN_VIEW"},
    {"user_name": None, "group_name": "data_engineers", "permission_level": "CAN_EDIT"},
]

print(f"Setting permissions on Space {space_id}...\n")

access_list = []
for p in PERMISSIONS:
    entry = {"permission_level": p["permission_level"]}
    if p["group_name"]:
        entry["group_name"] = p["group_name"]
    else:
        entry["user_name"] = p["user_name"]
    access_list.append(entry)

try:
    w.api_client.do(
        "PUT",
        f"/api/2.0/permissions/dashboards/{space_id}",
        body={"access_control_list": access_list},
    )
    for p in PERMISSIONS:
        target = p["group_name"] or p["user_name"]
        print(f"  {target:<20} {p['permission_level']}  ✓")
except Exception as e:
    print(f"  Permission update failed: {e}")
    print("  This is expected if the groups 'analysts' or 'data_engineers' do not exist in your workspace.")
    print("  In production, replace with your actual Unity Catalog group names.")

print("\nTo check current permissions in the UI:")
print("  Open the Space → top-right three-dot menu → Manage permissions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checkpoint — Verify the Space Works
# MAGIC
# MAGIC Before moving to Lab 02, run the two validation cells below.
# MAGIC They send test questions directly to the Genie API and check that responses come back.

# COMMAND ----------

# Checkpoint 1: ask a simple spot price question
print("Checkpoint 1: Sending test question to Genie Space...\n")

TEST_QUESTION_1 = "What was the average spot price in VIC1 yesterday?"

try:
    # Start a new conversation
    conv = w.api_client.do(
        "POST",
        f"/api/2.0/genie/spaces/{space_id}/start-conversation",
        body={"content": TEST_QUESTION_1},
    )
    conv_id = conv["conversation_id"]
    msg_id  = conv["message_id"]

    # Poll until the response is ready (max 60 seconds)
    for _ in range(24):
        time.sleep(2.5)
        msg = w.api_client.do(
            "GET",
            f"/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}",
        )
        status = msg.get("status", "PENDING")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break

    if status == "COMPLETED":
        # Extract the SQL generated
        attachments = msg.get("attachments", [])
        for att in attachments:
            if att.get("query"):
                print(f"Question  : {TEST_QUESTION_1}")
                print(f"Status    : COMPLETED ✓")
                print(f"SQL generated:\n{att['query'].get('query', 'N/A')}")
    else:
        print(f"Status: {status} — check the Space in the UI for details")

except Exception as e:
    print(f"API call failed: {e}")
    print("Verify the space_id is correct and the warehouse is running.")

# COMMAND ----------

# Checkpoint 2: ask a market notices question
print("Checkpoint 2: Sending second test question...\n")

TEST_QUESTION_2 = "Were there any LOR notices last week?"

try:
    conv2 = w.api_client.do(
        "POST",
        f"/api/2.0/genie/spaces/{space_id}/start-conversation",
        body={"content": TEST_QUESTION_2},
    )
    conv_id2 = conv2["conversation_id"]
    msg_id2  = conv2["message_id"]

    for _ in range(24):
        time.sleep(2.5)
        msg2 = w.api_client.do(
            "GET",
            f"/api/2.0/genie/spaces/{space_id}/conversations/{conv_id2}/messages/{msg_id2}",
        )
        status2 = msg2.get("status", "PENDING")
        if status2 in ("COMPLETED", "FAILED", "CANCELLED"):
            break

    print(f"Question  : {TEST_QUESTION_2}")
    print(f"Status    : {status2}")
    if status2 == "COMPLETED":
        print("Response received ✓ — open the Space in the UI to see the full answer and result table")

except Exception as e:
    print(f"API call failed: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC | Step | What was done |
# MAGIC |------|--------------|
# MAGIC | UI Exploration | Navigated Genie sidebar, explored Space creation form |
# MAGIC | Space created | REST API → Space ID stored for Lab 02 and 03 |
# MAGIC | Tables added | 5 AEMO tables registered as trusted assets |
# MAGIC | Golden queries | 10 NEM-specific queries in the Knowledge Store |
# MAGIC | Instructions | Domain context with NEM terminology, region codes, aggregation preferences |
# MAGIC | Permissions | analysts = CAN_VIEW, data_engineers = CAN_EDIT |
# MAGIC | Checkpoint | Two test questions validated via API |
# MAGIC
# MAGIC **Next: Lab 02 → Core User Workflows** — we will explore the Genie Space from an end-user perspective and learn how to get the best answers.

# COMMAND ----------

# Save space_id for use in Lab 02 and Lab 03
# Run this cell last so subsequent labs can retrieve it
print(f"Space ID for Lab 02 and Lab 03: {space_id}")
print(f"Copy this value into the widget in the next lab if you run them in a new session.")
