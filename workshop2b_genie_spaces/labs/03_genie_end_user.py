# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">
# MAGIC     Lab 03: Genie Space — End User Experience
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); font-size: 1.1em; margin: 0;">
# MAGIC     Asking Good Questions, Iterative Exploration, and Verifying Answers
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="width:100%; border-collapse:collapse; margin-top:16px; font-family:'DM Sans',sans-serif;">
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px; width:25%"><b>Workshop</b></td><td style="padding:8px 16px;">Genie Spaces &amp; AI Features — Australian Regulated Industries</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Duration</b></td><td style="padding:8px 16px;">35–40 minutes</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Role</b></td><td style="padding:8px 16px;">Business Analyst / Data Consumer</td></tr>
# MAGIC   <tr><td style="padding:8px 16px; background:#f5f5f5; border-radius:6px;"><b>Prerequisites</b></td><td style="padding:8px 16px;">Labs 01 and 02 complete — Genie Space is configured with tables, instructions, and golden queries</td></tr>
# MAGIC </table>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F4FD; border-left:5px solid #1B3A6B; padding:20px 24px; border-radius:0 8px 8px 0; margin:16px 0;">
# MAGIC   <h2 style="color:#1B3A6B; margin-top:0;">Learning Objectives</h2>
# MAGIC   <ol style="line-height:2em;">
# MAGIC     <li>Navigate the Genie Space chat interface confidently</li>
# MAGIC     <li>Ask questions at 5 levels of quality — understand what makes the difference</li>
# MAGIC     <li>Use iterative questioning: follow-ups, filter changes, and drill-down patterns</li>
# MAGIC     <li>Verify Genie answers by running the underlying SQL directly in this notebook</li>
# MAGIC     <li>Apply 6 prompt engineering patterns for energy domain questions</li>
# MAGIC     <li>Understand Genie's limitations and the correct workaround patterns</li>
# MAGIC     <li>Use the Genie Conversation API for Teams and Slack integration</li>
# MAGIC     <li>Export Genie-generated SQL to AI/BI dashboards</li>
# MAGIC   </ol>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#FFF3E0; border-left:5px solid #FF6D00; padding:16px 20px; border-radius:0 8px 8px 0; margin:16px 0;">
# MAGIC   <h3 style="color:#E65100; margin-top:0;">How this lab is structured</h3>
# MAGIC   <p>This lab is primarily <strong>UI-driven</strong>. Each task below follows this pattern:</p>
# MAGIC   <ol>
# MAGIC     <li>Navigate to the Genie Space chat interface in the UI</li>
# MAGIC     <li>Type the question shown into Genie Chat</li>
# MAGIC     <li>Observe what Genie generates (SQL + result)</li>
# MAGIC     <li>Run the <strong>verification SQL cell</strong> in this notebook to confirm Genie's answer is correct</li>
# MAGIC     <li>Try the "explore further" prompts to deepen your understanding</li>
# MAGIC   </ol>
# MAGIC   <p style="margin-bottom:0;">The API cells at the end show how to programmatically integrate Genie into applications.</p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests, time, json
from databricks.sdk import WorkspaceClient

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Workshop Configuration
# MAGIC > **Running in a customer environment?** Change the catalog name in the widget above to match
# MAGIC > what was set in `setup/00_workspace_setup.py` (default: `workshop_au`)

# COMMAND ----------
# Widget-based configuration — works in any customer Databricks environment
# These default values match what 00_workspace_setup.py creates
dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",      "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
PT_ENDPOINT  = dbutils.widgets.get("pt_endpoint")

print(f"Using catalog: {CATALOG}.{SCHEMA}")
print(f"PT endpoint:   {PT_ENDPOINT}")

# COMMAND ----------

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

# TODO: paste the SPACE_ID from Lab 01
SPACE_ID = ""  # e.g. "01ef1234-abcd-5678-efgh-000000000001"
# Configurable — change via widget above if running in customer environment
# CATALOG and SCHEMA are set by widgets above

assert SPACE_ID, "Paste your SPACE_ID from Lab 01 before proceeding."

def hdrs():
    t = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def genie_ask(question: str, mode: str = "CHAT", conversation_id: str = None) -> dict:
    """
    Ask a question in a Genie Space and return the completed message.
    If conversation_id is provided, continues an existing conversation.
    """
    if conversation_id:
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conversation_id}/messages",
            headers=hdrs(),
            json={"content": question}
        )
    else:
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/start-conversation",
            headers=hdrs(),
            json={"content": question, "mode": mode}
        )

    resp.raise_for_status()
    data            = resp.json()
    conversation_id = data.get("conversation_id", conversation_id)
    message_id      = data["message_id"]

    for _ in range(40):
        poll   = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conversation_id}/messages/{message_id}",
            headers=hdrs()
        )
        msg    = poll.json()
        status = msg.get("status", "UNKNOWN")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            msg["_conversation_id"] = conversation_id
            return msg
        time.sleep(2)

    return {"status": "TIMEOUT", "_conversation_id": conversation_id}


def print_genie_result(result: dict) -> None:
    """Pretty-print a Genie API response."""
    status = result.get("status", "UNKNOWN")
    print(f"Status: {status}")

    for att in result.get("attachments", []):
        if att.get("query"):
            q = att["query"]
            print(f"\nSQL Generated:\n{'-'*45}\n{q.get('query','')}\n{'-'*45}")
        if att.get("text"):
            print(f"\nNarrative: {att['text'].get('content','')}")
        if att.get("table"):
            rows = att["table"].get("rows", [])
            cols = att["table"].get("columns", [])
            if cols and rows:
                header = " | ".join(c.get("name","") for c in cols)
                print(f"\nResults ({len(rows)} rows):")
                print(f"  {header}")
                print(f"  {'-' * min(len(header), 80)}")
                for row in rows[:8]:
                    vals = [str(v) for v in row.get("values", [])]
                    print(f"  {' | '.join(vals)}")
                if len(rows) > 8:
                    print(f"  ... and {len(rows)-8} more rows")

print("Helper functions ready.")
print(f"Connected to Genie Space: https://{HOST}/genie/spaces/{SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Navigate to the Genie Space</h2>
# MAGIC </div>
# MAGIC
# MAGIC **Before starting the tasks, open your Genie Space in a separate browser tab:**
# MAGIC
# MAGIC ```
# MAGIC Left sidebar --> Genie (diamond icon) --> NEM Grid Operations -- Energy Analytics
# MAGIC ```
# MAGIC
# MAGIC You should see the Chat interface:
# MAGIC
# MAGIC ```
# MAGIC +-- NEM Grid Operations -- Energy Analytics ---------------------------------+
# MAGIC |   [Chat]   [Configure]                         Mode: [Chat | Agent]       |
# MAGIC |                                                                            |
# MAGIC |   --------------------------------------------------------------------    |
# MAGIC |                                                                            |
# MAGIC |   Genie: Hi! I can help you explore your energy network data.              |
# MAGIC |          What would you like to know?                                      |
# MAGIC |                                                                            |
# MAGIC |   --------------------------------------------------------------------    |
# MAGIC |                                                                            |
# MAGIC |   [Type your question here...                              ]   [Ask ->]   |
# MAGIC |                                                                            |
# MAGIC +----------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC Keep this browser tab open alongside this notebook. You will type questions into Genie
# MAGIC and then run the verification SQL cells below to confirm the answers are correct.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 1 — Question Quality: From Worst to Best</h2>
# MAGIC </div>
# MAGIC
# MAGIC The quality of your question directly determines the quality of Genie's answer.
# MAGIC We test the same underlying question at 5 levels of quality.
# MAGIC
# MAGIC **The underlying question:** What were the worst outage events in Victoria last year?

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Level 1 — Vague (do not do this)
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC ```
# MAGIC show me bad outages
# MAGIC ```
# MAGIC
# MAGIC **What Genie will do:**
# MAGIC - Guess what "bad" means — probably picks `customers_affected` but might pick `energy_not_served_mwh`
# MAGIC - Return all regions and all time periods (full table scan)
# MAGIC - May or may not filter to UNPLANNED outages
# MAGIC
# MAGIC **Why it fails:**
# MAGIC - "Bad" is undefined — Genie has to guess the ranking metric
# MAGIC - No time filter — could return thousands of rows
# MAGIC - No region filter — not actionable for a VIC operations manager

# COMMAND ----------

# Verification SQL for Level 1 — shows what "bad outages" could legitimately mean
# This helps you understand why the question is ambiguous
print("Level 1 question is deliberately vague.")
print("There are at least 3 different interpretations of 'bad':")
print()

for metric, label in [
    ("customers_affected", "customers affected"),
    ("energy_not_served_mwh", "energy not served (MWh)"),
    ("TIMESTAMPDIFF(MINUTE, start_time, end_time) / 60.0", "duration (hours)")
]:
    count = spark.sql(f"""
        SELECT COUNT(*) as cnt
        FROM {CATALOG}.{SCHEMA}.outages
        WHERE {metric} IS NOT NULL
    """).collect()[0]["cnt"]
    print(f"  If 'bad' = highest {label}: {count} eligible rows")

print()
print("Genie has to guess which metric you mean.")
print("A Level 5 question eliminates the ambiguity entirely.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Level 2 — Ambiguous entity reference
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC ```
# MAGIC show me outages in Victoria last year sorted by worst
# MAGIC ```
# MAGIC
# MAGIC **What Genie might do (incorrectly):**
# MAGIC - Filter on `suburb LIKE '%Victoria%'` instead of `region = 'VIC1'`
# MAGIC - Use calendar year (Jan–Dec) instead of Australian financial year (Jul–Jun)
# MAGIC - Still guess "worst" metric
# MAGIC
# MAGIC **Problems to spot in Genie's SQL:** Look at the WHERE clause — does it use `region = 'VIC1'`
# MAGIC or a suburb-based filter? Check the date range.

# COMMAND ----------

# Verification SQL — correct interpretation of "Victoria last year"
# The correct filter is region = 'VIC1', not suburb LIKE '%Victoria%'
print("Correct SQL for 'Victoria last year' (financial year interpretation):")
print()
result = spark.sql(f"""
SELECT
    region,
    MIN(start_time) AS earliest_event,
    MAX(start_time) AS latest_event,
    COUNT(*)        AS event_count
FROM {CATALOG}.{SCHEMA}.outages
WHERE region = 'VIC1'
  AND start_time >= '2023-07-01'
  AND start_time <  '2024-07-01'
GROUP BY region
""")
result.show(truncate=False)
print("If Genie's answer showed the same date range and event count, it interpreted correctly.")
print("If it returned 0 rows or filtered on suburb, it got it wrong.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Level 3 — Specific but missing business logic
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC ```
# MAGIC Show me the top 10 unplanned outages in VIC1 in FY2024 ordered by customers affected
# MAGIC ```
# MAGIC
# MAGIC **Improvements over Level 2:**
# MAGIC - `VIC1` matches the region column exactly — no ambiguity
# MAGIC - `FY2024` triggers the financial year logic from the instructions
# MAGIC - `customers affected` maps directly to the column name
# MAGIC - Explicit sort order and row limit
# MAGIC
# MAGIC **What is still missing:** No specification of which columns to return.
# MAGIC Genie will choose columns based on what it thinks is useful.

# COMMAND ----------

# Verification SQL for Level 3 question
print("Verification: Top 10 unplanned outages in VIC1, FY2024, by customers affected")
print()
spark.sql(f"""
SELECT
    outage_id,
    cause_category,
    suburb,
    start_time,
    customers_affected,
    ROUND(TIMESTAMPDIFF(MINUTE, start_time, end_time) / 60.0, 1) AS duration_hours
FROM {CATALOG}.{SCHEMA}.outages
WHERE outage_type = 'UNPLANNED'
  AND region = 'VIC1'
  AND start_time >= '2023-07-01'
  AND start_time <  '2024-07-01'
ORDER BY customers_affected DESC
LIMIT 10
""").show(truncate=False)
print()
print("Compare this result table to what Genie returned.")
print("Count: if counts differ, Genie may have used calendar year instead of financial year.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Level 4 — Good question with explicit column list
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC ```
# MAGIC Show me the top 10 worst unplanned outages in VIC1 during FY2024,
# MAGIC ranked by customers affected. Include the outage duration in hours,
# MAGIC energy not served in MWh, and the asset name.
# MAGIC ```
# MAGIC
# MAGIC **Why this is better:**
# MAGIC - Explicitly asks for columns from two tables (outages + assets)
# MAGIC - Genie must generate a JOIN — the question forces the correct pattern
# MAGIC - Duration format specified (hours)
# MAGIC - Rank criterion is unambiguous (customers affected)
# MAGIC
# MAGIC **What to observe in Genie's SQL:** Verify it JOINs `outages` to `assets` on `asset_id`.

# COMMAND ----------

# Verification SQL for Level 4 — requires JOIN to assets table
print("Verification: Top 10 VIC1 FY2024 unplanned outages with asset name")
print()
spark.sql(f"""
SELECT
    a.asset_name,
    a.asset_type,
    o.cause_category,
    o.suburb,
    o.customers_affected,
    ROUND(TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time) / 60.0, 1) AS duration_hours,
    ROUND(COALESCE(o.energy_not_served_mwh, 0), 2)                    AS ens_mwh
FROM {CATALOG}.{SCHEMA}.outages o
JOIN {CATALOG}.{SCHEMA}.assets a ON o.asset_id = a.asset_id
WHERE o.outage_type = 'UNPLANNED'
  AND o.region = 'VIC1'
  AND o.start_time >= '2023-07-01'
  AND o.start_time <  '2024-07-01'
ORDER BY o.customers_affected DESC
LIMIT 10
""").show(truncate=False)
print()
print("Key check: Does Genie's SQL include a JOIN to assets?")
print("If Genie returned asset_name, it must have joined — verify the JOIN key it used.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Level 5 — Excellent question with business context and output format
# MAGIC
# MAGIC **Type this into Genie:**
# MAGIC ```
# MAGIC I need to prepare the AER SAIDI narrative for FY2024 in VIC1.
# MAGIC Show me the 10 unplanned outages that contributed the most
# MAGIC customer-interruption-minutes (customers_affected x duration in minutes).
# MAGIC Include asset name, cause category, suburb, and whether each event
# MAGIC was reported to the AER.
# MAGIC Order by customer-interruption-minutes descending.
# MAGIC ```
# MAGIC
# MAGIC **Why this works:**
# MAGIC - Business context (AER SAIDI narrative) signals the SAIDI formula from the instructions
# MAGIC - The derived metric is spelled out explicitly: `customers_affected x duration_minutes`
# MAGIC - Every column needed is listed — Genie knows exactly what to SELECT and JOIN
# MAGIC - Sort order maps to a computable expression, not a vague word like "worst"
# MAGIC - `reported to the AER` maps directly to the `reported_to_aer` boolean column

# COMMAND ----------

# Verification SQL for Level 5 — SAIDI-weighted worst events for AER narrative
print("Verification: Top 10 SAIDI-contributing unplanned outages in VIC1, FY2024")
print()
spark.sql(f"""
SELECT
    a.asset_name,
    o.cause_category,
    o.suburb,
    o.customers_affected,
    TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time)           AS duration_minutes,
    (o.customers_affected *
     TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time))         AS customer_interruption_minutes,
    o.reported_to_aer
FROM {CATALOG}.{SCHEMA}.outages o
JOIN {CATALOG}.{SCHEMA}.assets a ON o.asset_id = a.asset_id
WHERE o.outage_type = 'UNPLANNED'
  AND o.region = 'VIC1'
  AND o.start_time >= '2023-07-01'
  AND o.start_time <  '2024-07-01'
  AND o.end_time IS NOT NULL
ORDER BY customer_interruption_minutes DESC
LIMIT 10
""").show(truncate=False)
print()
print("This is the ground-truth answer.")
print("Compare Genie's output — specifically the customer_interruption_minutes column values.")

# Run via API and capture conversation_id for follow-up tasks
GREAT_Q5 = (
    "I need to prepare the AER SAIDI narrative for FY2024 in VIC1. "
    "Show me the 10 unplanned outages that contributed the most customer-interruption-minutes "
    "(customers_affected x duration in minutes). Include asset name, cause category, "
    "suburb, and whether each event was reported to the AER. "
    "Order by customer-interruption-minutes descending."
)
result_5 = genie_ask(GREAT_Q5)
print_genie_result(result_5)
CONVERSATION_ID = result_5.get("_conversation_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 2 — Iterative Questioning and Drill-Down</h2>
# MAGIC </div>
# MAGIC
# MAGIC Genie remembers conversation context within a session. You can refine the previous result
# MAGIC with follow-up questions **in the same conversation** — you do not need to repeat context.
# MAGIC
# MAGIC In the Genie Chat UI, each follow-up message goes in the same thread:
# MAGIC
# MAGIC ```
# MAGIC +-- Chat -----------------------------------------------------------------------+
# MAGIC |                                                                               |
# MAGIC |   You: I need to prepare the AER SAIDI narrative... [Level 5 question]       |
# MAGIC |                                                                               |
# MAGIC |   Genie: Here are the top 10 outages... [table result]                       |
# MAGIC |                                                                               |
# MAGIC |   You: [Type your follow-up here -- Genie remembers the previous context]    |
# MAGIC |                                                         [Ask ->]             |
# MAGIC +-------------------------------------------------------------------------------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Task 1 — Drill down on the top result
# MAGIC
# MAGIC **In Genie Chat (continue the same conversation), type:**
# MAGIC ```
# MAGIC For the top outage in that list, show me all other outages on the same asset in the last 3 years.
# MAGIC ```
# MAGIC
# MAGIC **What to observe:**
# MAGIC - Genie should reference `asset_id` from the previous result without you re-specifying it
# MAGIC - The date range should span back 3 years from today

# COMMAND ----------

# Verification SQL — you need to know which asset was top in the Level 5 result
# First let's find the top asset ID
top_asset = spark.sql(f"""
SELECT o.asset_id, a.asset_name,
       (o.customers_affected * TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time)) AS cim
FROM {CATALOG}.{SCHEMA}.outages o
JOIN {CATALOG}.{SCHEMA}.assets a ON o.asset_id = a.asset_id
WHERE o.outage_type = 'UNPLANNED'
  AND o.region = 'VIC1'
  AND o.start_time >= '2023-07-01'
  AND o.end_time IS NOT NULL
ORDER BY cim DESC
LIMIT 1
""").collect()

if top_asset:
    top_asset_id   = top_asset[0]["asset_id"]
    top_asset_name = top_asset[0]["asset_name"]
    print(f"Top asset from Level 5 result: {top_asset_name} (ID: {top_asset_id})")
    print()
    print("Verification: All outages on this asset in the last 3 years:")
    spark.sql(f"""
        SELECT
            outage_type,
            cause_category,
            start_time,
            ROUND(TIMESTAMPDIFF(MINUTE, start_time, end_time) / 60.0, 1) AS duration_hours,
            customers_affected
        FROM {CATALOG}.{SCHEMA}.outages
        WHERE asset_id = '{top_asset_id}'
          AND start_time >= DATE_SUB(CURRENT_DATE, 1095)
        ORDER BY start_time DESC
    """).show(truncate=False)
else:
    print("No top asset found — verify your sample data was loaded in Lab 01.")

# API follow-up (continues the same conversation)
if CONVERSATION_ID:
    FU1 = "For the top outage in that list, show me all other outages on the same asset in the last 3 years."
    print(f"\nAsking Genie: '{FU1}'")
    result_fu1 = genie_ask(FU1, conversation_id=CONVERSATION_ID)
    print_genie_result(result_fu1)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Task 2 — Change the filter, keep the query structure
# MAGIC
# MAGIC **In Genie Chat (same conversation), type:**
# MAGIC ```
# MAGIC Now do the same SAIDI analysis but for QLD1 instead of VIC1.
# MAGIC ```
# MAGIC
# MAGIC **What to observe:**
# MAGIC - Genie should swap `VIC1` for `QLD1` in the WHERE clause
# MAGIC - All other structure (columns, join, sort) should remain the same
# MAGIC - This is a powerful pattern for regional comparison without rewriting the full question

# COMMAND ----------

# Verification SQL for QLD1
print("Verification: SAIDI-contributing outages in QLD1, FY2024")
print()
spark.sql(f"""
SELECT
    a.asset_name,
    o.cause_category,
    o.suburb,
    o.customers_affected,
    (o.customers_affected * TIMESTAMPDIFF(MINUTE, o.start_time, o.end_time)) AS customer_interruption_minutes,
    o.reported_to_aer
FROM {CATALOG}.{SCHEMA}.outages o
JOIN {CATALOG}.{SCHEMA}.assets a ON o.asset_id = a.asset_id
WHERE o.outage_type = 'UNPLANNED'
  AND o.region = 'QLD1'
  AND o.start_time >= '2023-07-01'
  AND o.start_time <  '2024-07-01'
  AND o.end_time IS NOT NULL
ORDER BY customer_interruption_minutes DESC
LIMIT 10
""").show(truncate=False)

if CONVERSATION_ID:
    FU2 = "Now do the same SAIDI analysis but for QLD1 instead of VIC1."
    print(f"\nAsking Genie: '{FU2}'")
    result_fu2 = genie_ask(FU2, conversation_id=CONVERSATION_ID)
    print_genie_result(result_fu2)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Task 3 — Add a percentage calculation
# MAGIC
# MAGIC **In Genie Chat (same conversation), type:**
# MAGIC ```
# MAGIC Add a column showing what percentage of total QLD1 ENS each outage represents.
# MAGIC ```
# MAGIC
# MAGIC **What to observe:**
# MAGIC - Genie should add a subquery or window function to calculate total ENS
# MAGIC - It should not start the query from scratch — it should modify the existing structure
# MAGIC - The percentage column should sum to ~100% across all rows

# COMMAND ----------

# Verification SQL — ENS percentage contribution by outage
print("Verification: ENS percentage by outage for QLD1, FY2024")
print()
spark.sql(f"""
WITH ens_totals AS (
    SELECT SUM(COALESCE(energy_not_served_mwh, 0)) AS total_ens_mwh
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED'
      AND region = 'QLD1'
      AND start_time >= '2023-07-01'
      AND start_time <  '2024-07-01'
)
SELECT
    o.cause_category,
    o.suburb,
    ROUND(COALESCE(o.energy_not_served_mwh, 0), 2)               AS ens_mwh,
    ROUND(COALESCE(o.energy_not_served_mwh, 0)
          / NULLIF(t.total_ens_mwh, 0) * 100, 1)                  AS pct_of_total_ens
FROM {CATALOG}.{SCHEMA}.outages o
CROSS JOIN ens_totals t
WHERE o.outage_type = 'UNPLANNED'
  AND o.region = 'QLD1'
  AND o.start_time >= '2023-07-01'
  AND o.start_time <  '2024-07-01'
ORDER BY pct_of_total_ens DESC
LIMIT 10
""").show(truncate=False)

if CONVERSATION_ID:
    FU3 = "Add a column showing what percentage of total QLD1 ENS each outage represents."
    print(f"\nAsking Genie: '{FU3}'")
    result_fu3 = genie_ask(FU3, conversation_id=CONVERSATION_ID)
    print_genie_result(result_fu3)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 3 — Guided Tasks with Verification</h2>
# MAGIC </div>
# MAGIC
# MAGIC These are stand-alone tasks you complete independently in the Genie Chat UI.
# MAGIC After asking each question, run the verification cell in this notebook
# MAGIC to confirm Genie's answer is correct.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Task 4 — Asset maintenance overdue list
# MAGIC
# MAGIC **Navigate to your Genie Space and start a new conversation.**
# MAGIC
# MAGIC **Type this question:**
# MAGIC ```
# MAGIC Show me all IN_SERVICE assets that have not had a maintenance inspection
# MAGIC in the last 12 months. Include asset name, type, region, owner DNSP,
# MAGIC and how many days since their last maintenance. Order by days overdue descending.
# MAGIC ```
# MAGIC
# MAGIC **What you should see in Genie:**
# MAGIC - Genie shows the SQL it generated (click "Show SQL" if it is collapsed)
# MAGIC - A table of assets with a calculated `days_since_maintenance` column
# MAGIC - Genie may narrate how many assets are overdue

# COMMAND ----------

# Verification SQL for Task 4
print("Verification: IN_SERVICE assets with maintenance > 12 months ago")
print()
result_task4 = spark.sql(f"""
SELECT
    asset_name,
    asset_type,
    region,
    owner_dnsp,
    last_maintenance,
    DATEDIFF(CURRENT_DATE, last_maintenance) AS days_since_maintenance
FROM {CATALOG}.{SCHEMA}.assets
WHERE status = 'IN_SERVICE'
  AND last_maintenance < DATE_SUB(CURRENT_DATE, 365)
ORDER BY days_since_maintenance DESC
""")
result_task4.show(truncate=False)
print(f"Expected: {result_task4.count()} assets overdue for maintenance.")
print()
print("Compare your Genie result to this table:")
print("  - Does Genie's row count match?")
print("  - Does Genie use DATEDIFF(CURRENT_DATE, last_maintenance) or something equivalent?")
print("  - Did Genie filter status = 'IN_SERVICE'?")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Task 5 — Smart meter data quality summary
# MAGIC
# MAGIC **In a new Genie conversation, type:**
# MAGIC ```
# MAGIC In the AUSNET_EAST distribution zone, what percentage of meter readings
# MAGIC in the last 30 days have each quality flag (A, E, S, N)?
# MAGIC Show count and percentage for each flag, ordered by count descending.
# MAGIC ```
# MAGIC
# MAGIC **What to observe in Genie's SQL:**
# MAGIC - Check whether Genie filters `distribution_zone = 'AUSNET_EAST'` correctly
# MAGIC - Check whether Genie uses a date filter for "last 30 days"
# MAGIC - Check whether percentage is calculated correctly (count / total * 100)

# COMMAND ----------

# Verification SQL for Task 5
print("Verification: Quality flag distribution for AUSNET_EAST, last 30 days")
print()
spark.sql(f"""
WITH total AS (
    SELECT COUNT(*) AS total_reads
    FROM {CATALOG}.{SCHEMA}.meter_readings
    WHERE distribution_zone = 'AUSNET_EAST'
      AND interval_datetime >= DATE_SUB(CURRENT_DATE, 30)
)
SELECT
    quality_flag,
    COUNT(*)                                  AS read_count,
    ROUND(COUNT(*) / t.total_reads * 100, 1)  AS pct_of_total
FROM {CATALOG}.{SCHEMA}.meter_readings
CROSS JOIN total t
WHERE distribution_zone = 'AUSNET_EAST'
  AND interval_datetime >= DATE_SUB(CURRENT_DATE, 30)
GROUP BY quality_flag, t.total_reads
ORDER BY read_count DESC
""").show(truncate=False)
print()
print("Note: Our sample data only covers June 2024, so 'last 30 days' from today may return 0.")
print("If Genie returns 0, tell it: 'Use June 2024 as the date range instead of last 30 days.'")
print("This is a good demonstration of how date filters interact with sample data.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Task 6 — SAIDI year-to-date vs prior year
# MAGIC
# MAGIC **In a new Genie conversation, type:**
# MAGIC ```
# MAGIC Compare SAIDI year-to-date for each NEM region against the same period
# MAGIC last year. Assume 1,000,000 total connected customers across all regions.
# MAGIC Show: region, SAIDI this year (minutes), SAIDI last year (minutes),
# MAGIC and percentage change. Order by percentage change ascending
# MAGIC so I can see which regions have improved the most.
# MAGIC ```
# MAGIC
# MAGIC **What makes this a Level 5 question:**
# MAGIC - Provides the denominator explicitly (1,000,000 customers) — Genie cannot look this up
# MAGIC - Defines the comparison period precisely (YTD vs same period last year)
# MAGIC - Lists every column needed and the sort order
# MAGIC - "Percentage change ascending" = best performing regions (most improved) first

# COMMAND ----------

# Verification SQL for Task 6
print("Verification: SAIDI YTD vs prior year by region (1M customers denominator)")
print()
spark.sql(f"""
WITH current_year AS (
    SELECT region,
           SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_num
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED'
      AND reported_to_aer = TRUE
      AND end_time IS NOT NULL
      AND YEAR(start_time) = YEAR(CURRENT_DATE)
      AND MONTH(start_time) <= MONTH(CURRENT_DATE)
    GROUP BY region
),
prior_year AS (
    SELECT region,
           SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected) AS saidi_num
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE outage_type = 'UNPLANNED'
      AND reported_to_aer = TRUE
      AND end_time IS NOT NULL
      AND YEAR(start_time) = YEAR(CURRENT_DATE) - 1
      AND MONTH(start_time) <= MONTH(CURRENT_DATE)
    GROUP BY region
)
SELECT
    COALESCE(c.region, p.region)                                   AS region,
    ROUND(COALESCE(c.saidi_num, 0) / 1000000.0, 2)                 AS saidi_this_year_minutes,
    ROUND(COALESCE(p.saidi_num, 0) / 1000000.0, 2)                 AS saidi_prior_year_minutes,
    ROUND(
        (COALESCE(c.saidi_num, 0) - COALESCE(p.saidi_num, 0))
        / NULLIF(COALESCE(p.saidi_num, 0), 0) * 100
    , 1)                                                           AS pct_change
FROM current_year c
FULL OUTER JOIN prior_year p ON c.region = p.region
ORDER BY pct_change ASC
""").show(truncate=False)
print()
print("Note: Our sample data is all from 2024. Prior year (2023) will be empty -> pct_change = NULL.")
print("This is expected with sample data. In production this would show meaningful YoY changes.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 4 — Prompt Engineering Patterns for Energy Domain</h2>
# MAGIC </div>
# MAGIC
# MAGIC Six patterns that reliably improve Genie answer quality for energy and regulated industry data.

# COMMAND ----------

PROMPT_PATTERNS = {
    "1. Reference golden queries by name": {
        "description": "If you know there is a golden query for your question, name it explicitly.",
        "good_example": "Using the 'SAIDI year-to-date vs same period prior year' query, show me VIC1 data.",
        "why": "Genie checks the knowledge store first when it recognises the query name. This bypasses NL-to-SQL generation entirely and uses the pre-verified query.",
    },
    "2. Specify units explicitly": {
        "description": "Always state the unit you want for numeric results.",
        "bad_example":  "How much energy was consumed last month?",
        "good_example": "What was the total active energy consumption last month in GWh (gigawatt-hours)?",
        "why": "Without a unit, Genie may return kWh when you wanted MWh, or MWh when you wanted GWh.",
    },
    "3. Use the exact column value, not a display label": {
        "description": "Use values that appear in the data, not the label you would put in a report.",
        "bad_example":  "Show me weather-related outages",
        "good_example": "Show me outages where cause_category = 'WEATHER'",
        "why": "Exact matches eliminate the mapping step. 'Weather-related' could match WEATHER, VEGETATION, or THIRD_PARTY depending on Genie's interpretation.",
    },
    "4. State the join explicitly when you need cross-table data": {
        "description": "If you need columns from two tables, mention both table names.",
        "bad_example":  "Show me outage counts by zone",
        "good_example": "Join outages to assets on asset_id, then show unplanned outage count per distribution zone.",
        "why": "Genie sometimes picks the wrong join key or skips the join entirely. Naming both tables forces the correct pattern.",
    },
    "5. Ask for the output format you need": {
        "description": "Specify whether you want a table, a single number, or a narrative summary.",
        "examples": [
            "Give me a summary sentence, not a table.",
            "Return just the total as a single number.",
            "Format as a table with columns: region, outage_count, saidi_minutes.",
        ],
        "why": "Controls whether you get raw data or an explanatory response. Matters for embedding in reports or dashboards.",
    },
    "6. Provide the denominator for rate calculations": {
        "description": "For SAIDI, SAIFI, or per-customer rates, always provide the denominator in the question.",
        "good_example": "Calculate SAIDI for VIC1 in FY2024. Use 450,000 as the total connected customers for VIC1.",
        "why": "Genie cannot look up customer counts it does not have in the trusted assets. If you do not provide the denominator, it either guesses or refuses to calculate.",
    },
}

print("PROMPT ENGINEERING PATTERNS FOR ENERGY DOMAIN")
print("=" * 65)
for name, details in PROMPT_PATTERNS.items():
    print(f"\n{name}")
    print(f"  {details['description']}")
    if "good_example" in details:
        print(f"  Good : \"{details['good_example']}\"")
    if "bad_example" in details:
        print(f"  Avoid: \"{details['bad_example']}\"")
    if "examples" in details:
        for ex in details["examples"]:
            print(f"  e.g.   \"{ex}\"")
    print(f"  Why  : {details['why']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 5 — What Genie Cannot Do</h2>
# MAGIC </div>
# MAGIC
# MAGIC Understanding these limits prevents frustration and helps you design better workflows.

# COMMAND ----------

print("""
WHAT GENIE CANNOT DO (as of May 2026)
======================================

1. WRITE DATA
   Genie is read-only. It generates SELECT queries only.
   Cannot: INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE.
   Workaround: Use a Databricks job or notebook to write data;
   expose the result as a Delta table; Genie can then query the result.

2. CALL EXTERNAL APIs
   Cannot call REST APIs, send emails, or trigger workflows.
   Workaround: Use a Databricks App with tool-calling capabilities
   or a Mosaic AI Agent with function tools.

3. REMEMBER PREVIOUS SESSIONS
   Each conversation starts fresh. Genie has no memory across
   separate conversation sessions — only within the current thread.
   Workaround: Put persistent context in the instructions block,
   or ask the user to re-state their context at the start of each session.

4. INTERPRET CHARTS OR IMAGES
   Genie works with structured tabular data only. It cannot read PDFs,
   chart screenshots, or images unless the content has been extracted
   to a Delta table or connected via a SharePoint/Drive source.

5. EXECUTE ARBITRARY PYTHON
   Genie runs SQL only (via NL-to-SQL). For Python transformations,
   use notebooks or jobs, materialise the result as a Delta table,
   and add that table as a trusted Genie asset.

6. FORECAST FUTURE VALUES
   Genie can show historical trends and patterns but it cannot
   predict future values. That requires a ML model — surface
   model predictions as a Delta table, then Genie can query them.

7. HANDLE VERY COMPLEX MULTI-STEP CALCULATIONS IN ONE QUERY
   Long chains of calculations with many dependencies may degrade.
   Pattern: pre-compute intermediate results as Delta views,
   add the views as trusted assets, and Genie queries the views.

THE UNIVERSAL WORKAROUND PATTERN
---------------------------------
If Genie cannot answer a question:
  1. Ask Genie anyway — copy the SQL it generates
  2. Fix the SQL in a notebook cell
  3. Save the result as a Delta view
  4. Add that view as a trusted Genie asset
  5. Now Genie can query the pre-computed result cleanly
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 6 — Genie Conversation API: Teams and Slack Integration</h2>
# MAGIC </div>
# MAGIC
# MAGIC The Genie Conversation API lets you embed Genie in any application.
# MAGIC Common patterns: Microsoft Teams bot, Slack slash command, SharePoint embedded widget.

# COMMAND ----------

def genie_full_conversation_cycle(space_id: str, question: str) -> dict:
    """
    Full three-step Genie API pattern for application integration:
    1. Start conversation (returns conversation_id + message_id)
    2. Poll until COMPLETED
    3. Optionally fetch result data rows
    """
    # Step 1: Start conversation
    print(f"Step 1: Posting question...")
    start = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{space_id}/start-conversation",
        headers=hdrs(),
        json={"content": question}
    )
    start.raise_for_status()
    d       = start.json()
    conv_id = d["conversation_id"]
    msg_id  = d["message_id"]
    print(f"  conversation_id : {conv_id}")
    print(f"  message_id      : {msg_id}")

    # Step 2: Poll for completion
    print("\nStep 2: Polling for result...")
    for i in range(30):
        poll   = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}",
            headers=hdrs()
        )
        msg    = poll.json()
        status = msg.get("status")
        print(f"  [{i+1:2d}] {status}")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)

    # Step 3: Fetch result rows if available
    query_result_id = None
    for att in msg.get("attachments", []):
        if att.get("query") and att["query"].get("query_result_metadata_id"):
            query_result_id = att["query"]["query_result_metadata_id"]
            break

    rows = []
    if query_result_id:
        print(f"\nStep 3: Fetching data rows (result_id={query_result_id})")
        rr = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}"
            f"/messages/{msg_id}/query-result/{query_result_id}",
            headers=hdrs()
        )
        if rr.status_code == 200:
            rows = rr.json().get("statement_response", {}).get("result", {}).get("data_array", [])
            print(f"  Received {len(rows)} data rows")

    return {
        "conversation_id": conv_id,
        "message_id":      msg_id,
        "status":          msg.get("status"),
        "message":         msg,
        "data_rows":       rows
    }


# Integration test question
INTEGRATION_Q = "What was the total energy not served across all unplanned outages by region?"

print("GENIE CONVERSATION API — APPLICATION INTEGRATION EXAMPLE")
print("=" * 65)
print(f"Question: {INTEGRATION_Q}\n")

integration_result = genie_full_conversation_cycle(SPACE_ID, INTEGRATION_Q)
print("\nFINAL RESULT")
print("-" * 45)
print_genie_result(integration_result["message"])

# COMMAND ----------

# MAGIC %md
# MAGIC ### Teams Bot / Slack App pseudocode
# MAGIC
# MAGIC The three-step pattern above maps directly to a bot handler:

# COMMAND ----------

TEAMS_BOT_PSEUDOCODE = '''
# Microsoft Teams Bot (Python + Azure Functions)
# -----------------------------------------------

@app.activity_handler.on_message_activity
async def on_message(context: TurnContext):
    user_question = context.activity.text

    # Step 1: Post to Genie
    start = await genie_client.start_conversation(
        space_id = GENIE_SPACE_ID,
        question = user_question
    )

    # Step 2: Poll until done (Genie may take 3-30 seconds)
    result = await genie_client.wait_for_result(
        space_id        = GENIE_SPACE_ID,
        conversation_id = start.conversation_id,
        message_id      = start.message_id,
        timeout_seconds = 60
    )

    # Step 3: Format and send back to Teams
    if result.narrative:
        await context.send_activity(result.narrative)

    if result.data_rows:
        # Render as an Adaptive Card table (max 10 rows for Teams readability)
        card = build_adaptive_card_table(result.columns, result.data_rows[:10])
        await context.send_activity(
            MessageFactory.attachment(CardFactory.adaptive_card(card))
        )

    if result.sql:
        # Show the generated SQL for power users who want to verify it
        await context.send_activity(f"Generated SQL:\n```sql\n{result.sql}\n```")
'''

print(TEAMS_BOT_PSEUDOCODE)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 7 — Exporting to AI/BI Dashboards</h2>
# MAGIC </div>
# MAGIC
# MAGIC Genie is an exploration tool. Once you have found a useful query, the best practice is
# MAGIC to pin it to an AI/BI dashboard for recurring use.
# MAGIC
# MAGIC ### The recommended pattern: Genie -> Delta View -> Dashboard
# MAGIC
# MAGIC ```
# MAGIC 1. Ask Genie the question   -->  Genie generates SQL
# MAGIC 2. Copy Genie's SQL         -->  Paste into a CREATE VIEW statement
# MAGIC 3. Add the view to a dashboard as a dataset
# MAGIC 4. Dashboard refreshes on schedule; users query the view directly
# MAGIC 5. Genie stays as the exploration and drill-down tool
# MAGIC ```
# MAGIC
# MAGIC **Why not just call the Genie API on every dashboard load?**
# MAGIC - Dashboard refresh should be deterministic and fast (< 1 second)
# MAGIC - Genie API calls take 3–30 seconds and are not idempotent
# MAGIC - Delta views are cacheable; Genie API responses are not
# MAGIC - A Delta view can be shared across multiple dashboards and reports

# COMMAND ----------

# Example: materialise a Genie-derived query as a dashboard view
DASHBOARD_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.v_dashboard_outage_summary AS
-- Source: derived from Genie conversation -- "monthly outages by region with SAIDI component"
-- Refreshed: daily via scheduled Databricks job
-- Denominator: 450,000 ICPs for VIC1 (update per actual customer register)
SELECT
    region,
    DATE_TRUNC('month', start_time)                                           AS month,
    SUM(CASE WHEN outage_type = 'UNPLANNED' THEN 1 ELSE 0 END)               AS unplanned_count,
    SUM(CASE WHEN outage_type = 'PLANNED'   THEN 1 ELSE 0 END)               AS planned_count,
    SUM(customers_affected)                                                   AS total_customer_interruptions,
    ROUND(SUM(COALESCE(energy_not_served_mwh, 0)), 2)                         AS total_ens_mwh,
    ROUND(
        SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time) * customers_affected)
        / 450000.0
    , 2)                                                                      AS saidi_component_minutes
FROM {CATALOG}.{SCHEMA}.outages
WHERE end_time IS NOT NULL
GROUP BY region, DATE_TRUNC('month', start_time)
"""

spark.sql(DASHBOARD_VIEW_SQL)
print("Dashboard view created: v_dashboard_outage_summary")
print()
spark.table(f"{CATALOG}.{SCHEMA}.v_dashboard_outage_summary").show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Creating the AI/BI Dashboard in the UI
# MAGIC
# MAGIC ```
# MAGIC Navigation: Left sidebar --> SQL --> Dashboards --> [+ New Dashboard]
# MAGIC
# MAGIC +-- New Dashboard --------------------------------------------------------+
# MAGIC |                                                                         |
# MAGIC |   Name: NEM Grid Operations Dashboard                                   |
# MAGIC |                                                                         |
# MAGIC |   [+ Add Dataset]                                                       |
# MAGIC |    --> search for: workshop.energy_nem.v_dashboard_outage_summary       |
# MAGIC |    --> click [Add]                                                      |
# MAGIC |                                                                         |
# MAGIC |   [+ Add Widget]                                                        |
# MAGIC |    --> Bar chart: unplanned_count by month, coloured by region           |
# MAGIC |    --> KPI tile: SUM(total_ens_mwh) for last 12 months                  |
# MAGIC |    --> Line chart: saidi_component_minutes trend by region               |
# MAGIC |    --> Genie widget: embeds a chat interface on the dashboard            |
# MAGIC |      (the Genie widget lets users ask follow-up questions in context)    |
# MAGIC |                                                                         |
# MAGIC |                                         [Publish dashboard] ✓          |
# MAGIC +-------------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC The **Genie widget** is a special AI/BI dashboard component that embeds the Genie chat
# MAGIC interface directly on the dashboard. Users can ask questions about what they see
# MAGIC without leaving the dashboard view.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background:#1B3A6B; color:white; padding:10px 20px; border-radius:6px; margin:8px 0;">
# MAGIC   <h2 style="margin:0; color:white;">Part 8 — Question Quality Challenge (Your Turn)</h2>
# MAGIC </div>
# MAGIC
# MAGIC Write a Level 5 question for each scenario. Then test your question in Genie Chat
# MAGIC and verify it with the SQL cell below.

# COMMAND ----------

EXERCISE_SCENARIOS = [
    {
        "number": 1,
        "scenario": (
            "Asset management team wants to identify which ZONE_SUBSTATION assets "
            "in NSW1 have not had maintenance in over 18 months AND have had at least "
            "one unplanned outage in the last 3 years."
        ),
        "your_question": "",  # TODO: write your Level 5 question here
        "verification_sql": f"""
            SELECT
                a.asset_name,
                a.last_maintenance,
                DATEDIFF(CURRENT_DATE, a.last_maintenance)   AS days_since_maintenance,
                COUNT(o.outage_id)                           AS recent_outages,
                SUM(o.customers_affected)                    AS total_customers_affected
            FROM {CATALOG}.{SCHEMA}.assets a
            JOIN {CATALOG}.{SCHEMA}.outages o
                ON a.asset_id = o.asset_id
               AND o.outage_type = 'UNPLANNED'
               AND o.start_time >= DATE_SUB(CURRENT_DATE, 1095)
            WHERE a.asset_type = 'ZONE_SUBSTATION'
              AND a.region = 'NSW1'
              AND a.status = 'IN_SERVICE'
              AND a.last_maintenance < DATE_SUB(CURRENT_DATE, 548)
            GROUP BY a.asset_name, a.last_maintenance
            HAVING COUNT(o.outage_id) >= 1
            ORDER BY days_since_maintenance DESC
        """
    },
    {
        "number": 2,
        "scenario": (
            "Regulatory team needs total ENS (MWh) for weather-related outages in each "
            "region for the last two financial years, formatted for an AER submission table."
        ),
        "your_question": "",  # TODO
        "verification_sql": f"""
            SELECT
                region,
                CASE
                    WHEN start_time BETWEEN '2022-07-01' AND '2023-06-30' THEN 'FY2023'
                    WHEN start_time BETWEEN '2023-07-01' AND '2024-06-30' THEN 'FY2024'
                END                                              AS financial_year,
                ROUND(SUM(COALESCE(energy_not_served_mwh, 0)), 2) AS total_ens_mwh
            FROM {CATALOG}.{SCHEMA}.outages
            WHERE cause_category = 'WEATHER'
              AND outage_type = 'UNPLANNED'
              AND start_time BETWEEN '2022-07-01' AND '2024-06-30'
            GROUP BY region,
                CASE WHEN start_time BETWEEN '2022-07-01' AND '2023-06-30' THEN 'FY2023'
                     WHEN start_time BETWEEN '2023-07-01' AND '2024-06-30' THEN 'FY2024'
                END
            ORDER BY financial_year, region
        """
    },
    {
        "number": 3,
        "scenario": (
            "Operations team wants to know if meter readings in AUSNET_EAST zone have "
            "any obvious data quality issues (estimated or missing flags) in June 2024."
        ),
        "your_question": "",  # TODO
        "verification_sql": f"""
            SELECT
                quality_flag,
                COUNT(*)                                  AS read_count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct_of_total
            FROM {CATALOG}.{SCHEMA}.meter_readings
            WHERE distribution_zone = 'AUSNET_EAST'
              AND interval_datetime >= '2024-06-01'
              AND interval_datetime <  '2024-07-01'
            GROUP BY quality_flag
            ORDER BY read_count DESC
        """
    },
]

print("QUESTION QUALITY CHALLENGE")
print("=" * 65)
for ex in EXERCISE_SCENARIOS:
    print(f"\nScenario {ex['number']}:")
    print(f"  {ex['scenario']}")
    if ex["your_question"]:
        print(f"\n  Your question: {ex['your_question']}")
    else:
        print("\n  TODO: Write your Level 5 question in the your_question field above.")
    print()

# COMMAND ----------

# Verification SQL for Scenario 1
print("Verification SQL — Scenario 1")
print()
spark.sql(EXERCISE_SCENARIOS[0]["verification_sql"]).show(truncate=False)

# COMMAND ----------

# Verification SQL for Scenario 2
print("Verification SQL — Scenario 2")
print()
spark.sql(EXERCISE_SCENARIOS[1]["verification_sql"]).show(truncate=False)

# COMMAND ----------

# Verification SQL for Scenario 3
print("Verification SQL — Scenario 3")
print()
spark.sql(EXERCISE_SCENARIOS[2]["verification_sql"]).show(truncate=False)

# COMMAND ----------

# Reference answers (uncomment to reveal)
REFERENCE_ANSWERS = {
    "1": (
        "Show me all ZONE_SUBSTATION assets in NSW1 (region = 'NSW1') in IN_SERVICE status "
        "where last_maintenance is more than 18 months (548 days) before today, "
        "AND the asset has had at least one unplanned outage in the last 3 years. "
        "Include: asset name, last_maintenance date, owner_dnsp, days since last maintenance, "
        "outage count, and total customers affected. "
        "Order by days since last maintenance descending."
    ),
    "2": (
        "For weather-related unplanned outages (cause_category = 'WEATHER'), show the total "
        "energy not served in MWh (SUM of energy_not_served_mwh, treating NULL as 0) "
        "grouped by region and Australian financial year. "
        "FY2023 = July 2022 to June 2023, FY2024 = July 2023 to June 2024. "
        "Format as a table with columns: region, financial_year, total_ens_mwh. "
        "Order by financial_year, then region."
    ),
    "3": (
        "In the AUSNET_EAST distribution zone, for meter readings in June 2024, "
        "show the count of readings by quality_flag (A, E, S, N). "
        "Also show the percentage of total readings each flag represents. "
        "Order by count descending so I can see the most common quality issues first."
    ),
}

# for k, v in REFERENCE_ANSWERS.items():
#     print(f"\nReference answer {k}:\n  {v}\n")
print("Reference answers are stored in REFERENCE_ANSWERS dict — uncomment the loop above to reveal.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 03 — Review Questions
# MAGIC
# MAGIC <div style="background:#F5F5F5; padding:20px 24px; border-radius:8px; margin:12px 0;">
# MAGIC
# MAGIC 1. A user complains that Genie keeps returning kWh totals when they want MWh.
# MAGIC    What is the simplest fix in the question they are asking — without changing
# MAGIC    any Genie Space configuration?
# MAGIC
# MAGIC 2. You are building a Teams bot using the Genie Conversation API. After calling
# MAGIC    `/start-conversation`, the response comes back with `status: EXECUTING_QUERY`.
# MAGIC    What should your bot do next and why?
# MAGIC
# MAGIC 3. A business analyst wants Genie to "remember" that they always work on VIC1 data.
# MAGIC    Can Genie do this across sessions? If not, what are two practical workarounds?
# MAGIC
# MAGIC 4. Why is it better to pin Genie-generated SQL to a Delta view for dashboard use,
# MAGIC    rather than calling the Genie Conversation API on every dashboard refresh?
# MAGIC
# MAGIC 5. You ask Genie a question and it returns correct SQL but the numbers are 50% lower
# MAGIC    than you expected. Looking at the SQL, you notice it is not filtering for
# MAGIC    `quality_flag IN ('A', 'E')`. What admin action fixes this going forward?
# MAGIC
# MAGIC </div>
# MAGIC
# MAGIC **Lab 03 complete. Proceed to Lab 04 when ready.**
