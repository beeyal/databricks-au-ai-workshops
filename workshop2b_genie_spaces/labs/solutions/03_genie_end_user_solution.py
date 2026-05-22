# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 03: Genie Space — End User Experience — SOLUTION
# MAGIC
# MAGIC **Workshop:** Genie Spaces & AI Features — Australian Regulated Industries
# MAGIC **Duration:** 35–40 minutes
# MAGIC **Role:** Business Analyst / Data Consumer
# MAGIC **Prerequisite:** Labs 01 and 02 complete — Genie Space is configured
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC 1. Ask natural language questions effectively — understand what makes a good question
# MAGIC 2. Use iterative questioning: follow-up, filtering, and drill-down patterns
# MAGIC 3. Understand the difference between Chat mode and Agent mode outputs
# MAGIC 4. Export Genie results to AI/BI dashboards
# MAGIC 5. Use the Genie Conversation API for Teams / Slack integration
# MAGIC 6. Apply prompt engineering tips to get consistently better answers
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests, time, json
from databricks.sdk import WorkspaceClient

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")

# SOLUTION: paste your SPACE_ID from Lab 01 here
SPACE_ID = ""  # REQUIRED: copy from Lab 01 final output
CATALOG  = "workshop"
SCHEMA   = "energy_nem"

assert SPACE_ID, "Set SPACE_ID from Lab 01 before proceeding."

def hdrs():
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def genie_ask(question: str, mode: str = "CHAT", conversation_id: str = None) -> dict:
    """
    Ask a question in a Genie Space and return the completed message.
    If conversation_id is provided, continues an existing conversation.
    """
    if conversation_id:
        # Continue an existing conversation
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conversation_id}/messages",
            headers=hdrs(),
            json={"content": question}
        )
    else:
        # Start a new conversation
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/start-conversation",
            headers=hdrs(),
            json={"content": question, "mode": mode}
        )

    resp.raise_for_status()
    data = resp.json()
    conversation_id = data.get("conversation_id", conversation_id)
    message_id      = data["message_id"]

    # Poll for result
    for _ in range(40):
        poll = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conversation_id}/messages/{message_id}",
            headers=hdrs()
        )
        poll.raise_for_status()
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
            print(f"\nSQL Generated:\n{'-'*40}\n{q.get('query','')}\n{'-'*40}")
        if att.get("text"):
            print(f"\nNarrative: {att['text'].get('content','')}")
        if att.get("table"):
            rows = att["table"].get("rows", [])
            cols = att["table"].get("columns", [])
            if cols and rows:
                header = " | ".join(c.get("name","") for c in cols)
                print(f"\nResults ({len(rows)} rows):")
                print(f"  {header}")
                print(f"  {'-' * len(header)}")
                for row in rows[:5]:
                    vals = [str(v) for v in row.get("values", [])]
                    print(f"  {' | '.join(vals)}")
                if len(rows) > 5:
                    print(f"  ... and {len(rows)-5} more rows")

print("Helper functions loaded. Space ID:", SPACE_ID)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 1 — Question Quality: From Worst to Best
# MAGIC
# MAGIC The quality of your question directly affects the quality of Genie's answer.
# MAGIC We will test the same underlying question at 5 levels of quality.
# MAGIC
# MAGIC **The underlying question:** *What were the worst outage events in Victoria last year?*

# COMMAND ----------

# MAGIC %md
# MAGIC ### Level 1 — Vague (DO NOT DO THIS)
# MAGIC
# MAGIC **Why this fails:** Too ambiguous. "Worst" could mean duration, customers, or ENS.
# MAGIC "Last year" without a financial year convention is ambiguous. "Victoria" doesn't
# MAGIC tell Genie whether to filter by `region = 'VIC1'` or `suburb` or `owner_dnsp`.

# COMMAND ----------

# Demonstrates a poor question — for illustration only
BAD_Q1 = "show me bad outages"

print("QUESTION (Level 1 — Vague):")
print(f"  '{BAD_Q1}'")
print()
print("EXPECTED PROBLEMS:")
print("  - 'Bad' is undefined — Genie will guess a metric")
print("  - No region or time filter — full table scan")
print("  - No indication of sort order or row limit")
print()
print("Run the cell below to see how Genie handles this vs a better question.")
# result = genie_ask(BAD_Q1)
# print_genie_result(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Level 2 — Ambiguous entity reference

# COMMAND ----------

BAD_Q2 = "show me outages in Victoria last year sorted by worst"
print("QUESTION (Level 2 — Ambiguous):")
print(f"  '{BAD_Q2}'")
print()
print("EXPECTED PROBLEMS:")
print("  - 'Victoria' — Genie may filter on region='VIC1' OR suburb LIKE 'Victoria%'")
print("  - 'Last year' — calendar year or financial year?")
print("  - 'Worst' — still undefined")
# result = genie_ask(BAD_Q2)
# print_genie_result(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Level 3 — Specific but missing business logic

# COMMAND ----------

OK_Q3 = "Show me the top 10 unplanned outages in VIC1 in FY2024 ordered by customers affected"
print("QUESTION (Level 3 — OK):")
print(f"  '{OK_Q3}'")
print()
print("IMPROVEMENTS:")
print("  + 'VIC1' matches the region column exactly")
print("  + 'FY2024' triggers the financial year date logic from our instructions")
print("  + 'customers affected' is an actual column name")
print("  + Explicit sort order and row limit")
print()
print("STILL MISSING:")
print("  - Doesn't specify whether to include ENS or duration context")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Level 4 — Good question with context

# COMMAND ----------

GOOD_Q4 = (
    "Show me the top 10 worst unplanned outages in VIC1 during FY2024, "
    "ranked by customers affected. Include the outage duration in hours, "
    "energy not served, and the asset name."
)
print("QUESTION (Level 4 — Good):")
print(f"  '{GOOD_Q4}'")
print()
print("IMPROVEMENTS:")
print("  + Specifies exactly which columns to return")
print("  + Explicitly asks for a join to the assets table (asset name)")
print("  + Rank criterion is unambiguous (customers affected)")
print("  + Duration format specified (hours)")
print()
result_4 = genie_ask(GOOD_Q4)
print_genie_result(result_4)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Level 5 — Excellent: business context + output format

# COMMAND ----------

GREAT_Q5 = (
    "I need to prepare the AER SAIDI narrative for FY2024 in VIC1. "
    "Show me the 10 unplanned outages that contributed the most customer-interruption-minutes "
    "(customers_affected × duration in minutes). Include asset name, cause category, "
    "suburb, and whether each was reported to the AER. "
    "Order by customer-interruption-minutes descending."
)
print("QUESTION (Level 5 — Excellent):")
print(f"  '{GREAT_Q5}'")
print()
print("WHY THIS WORKS:")
print("  + Business context (AER narrative) triggers the SAIDI formula from instructions")
print("  + Explicitly defines the metric: customers_affected × duration_minutes")
print("  + Lists every column needed for the table")
print("  + Sort order is explicit and matches a computable expression")
print("  + 'reported to the AER' maps to the reported_to_aer boolean column")
print()
result_5 = genie_ask(GREAT_Q5)
print_genie_result(result_5)
CONVERSATION_ID = result_5.get("_conversation_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 2 — Iterative Questioning (Follow-up and Drill-Down)
# MAGIC
# MAGIC Genie maintains conversation context. You can refine the previous result
# MAGIC with follow-up questions in the same conversation.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Follow-up 1: Drill down on the top result

# COMMAND ----------

if CONVERSATION_ID:
    FOLLOWUP_1 = "For the top outage in that list, show me all other outages on the same asset in the last 3 years."
    print(f"Follow-up: '{FOLLOWUP_1}'")
    print()
    result_f1 = genie_ask(FOLLOWUP_1, conversation_id=CONVERSATION_ID)
    print_genie_result(result_f1)
else:
    print("Run the Level 5 question first to get CONVERSATION_ID.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Follow-up 2: Change the filter, keep the structure

# COMMAND ----------

if CONVERSATION_ID:
    FOLLOWUP_2 = "Now do the same analysis but for QLD1 instead of VIC1."
    print(f"Follow-up: '{FOLLOWUP_2}'")
    print()
    result_f2 = genie_ask(FOLLOWUP_2, conversation_id=CONVERSATION_ID)
    print_genie_result(result_f2)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Follow-up 3: Add a calculation

# COMMAND ----------

if CONVERSATION_ID:
    FOLLOWUP_3 = "Add a column showing the percentage of total VIC1 ENS that each outage represents."
    print(f"Follow-up: '{FOLLOWUP_3}'")
    print()
    result_f3 = genie_ask(FOLLOWUP_3, conversation_id=CONVERSATION_ID)
    print_genie_result(result_f3)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 3 — Prompt Engineering Patterns for Energy Domain
# MAGIC
# MAGIC The following patterns reliably improve Genie answer quality.

# COMMAND ----------

PROMPT_PATTERNS = {

    "1. Reference your golden queries by name": {
        "description": "If you know there's a golden query for your question, name it.",
        "good_example": "Using the 'SAIDI year-to-date vs prior year same period' query, show me VIC1 data.",
        "why": "Genie checks the knowledge store first when it recognises the query name."
    },

    "2. Specify units explicitly": {
        "description": "Always state the unit you want for numbers.",
        "bad_example":  "How much energy was consumed last month?",
        "good_example": "What was the total active energy consumption last month in GWh (gigawatt-hours)?",
        "why": "Prevents Genie returning kWh when you wanted MWh or vice versa."
    },

    "3. Use the exact column value, not the user-facing label": {
        "description": "Use values that appear in the data, not display-layer labels.",
        "bad_example":  "Show me weather-related outages",
        "good_example": "Show me outages where cause_category = 'WEATHER'",
        "why": "Genie maps your words to SQL — exact matches remove ambiguity."
    },

    "4. State the join explicitly when you need cross-table data": {
        "description": "If you need columns from two tables, mention both.",
        "bad_example":  "Show me outage counts by zone",
        "good_example": "Join outages to assets on asset_id, then show outage count per distribution zone.",
        "why": "Genie sometimes picks the wrong join key without guidance."
    },

    "5. Ask for the format you need": {
        "description": "Specify if you want a table, a single number, or a narrative summary.",
        "examples": [
            "Give me a summary sentence, not a table.",
            "Return just the total as a single number.",
            "Format as a table with columns: region, outage_count, saidi_minutes"
        ],
        "why": "Controls whether you get a data table or an explanatory response."
    },

    "6. Give Genie the denominator for rate calculations": {
        "description": "For metrics like SAIDI, SAIFI, or per-customer rates, provide the denominator.",
        "good_example": (
            "Calculate SAIDI for VIC1 in FY2024. "
            "Use 450,000 as the total connected customer count for VIC1."
        ),
        "why": "Genie cannot look up customer counts it doesn't have — give it the number."
    },
}

print("PROMPT ENGINEERING PATTERNS FOR ENERGY DOMAIN")
print("=" * 60)
for pattern_name, details in PROMPT_PATTERNS.items():
    print(f"\n{pattern_name}")
    print(f"  {details['description']}")
    if "good_example" in details:
        print(f"  Example: \"{details['good_example']}\"")
    if "bad_example" in details:
        print(f"  Avoid:   \"{details['bad_example']}\"")
    if "examples" in details:
        for ex in details["examples"]:
            print(f"  Example: \"{ex}\"")
    print(f"  Why: {details['why']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 4 — What Genie Cannot Do
# MAGIC
# MAGIC Understanding Genie's limits prevents frustration and helps you design better workflows.

# COMMAND ----------

GENIE_LIMITATIONS = """
WHAT GENIE CANNOT DO (as of May 2026)
======================================

1. WRITE DATA
   Genie is read-only. It generates SELECT queries only.
   Cannot: INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE.

2. CALL EXTERNAL APIs
   Cannot call REST APIs, send emails, or trigger workflows.
   For that: use a Databricks App or an AI Agent with tools.

3. REMEMBER PREVIOUS SESSIONS
   Each conversation starts fresh. Genie has no memory of past
   conversations (only context within the current conversation thread).

4. INTERPRET CHARTS OR IMAGES
   Genie works with structured table data. It cannot read PDFs, images,
   or chart screenshots unless you've loaded their text content into a
   Delta table or connected a SharePoint/Drive source.

5. EXECUTE ARBITRARY PYTHON
   Genie runs SQL only (via NL-to-SQL). For Python-based transformations,
   use notebooks or jobs, then surface the results as Delta tables.

6. ANSWER QUESTIONS ABOUT FUTURE DATA
   Genie cannot forecast. It can show trends and ask "what was the pattern"
   but it will not predict future values (that's a ML model job).

7. HANDLE VERY COMPLEX CALCULATIONS IN ONE STEP
   Multi-step calculations with many dependencies may degrade.
   Solution: pre-compute them as views and add the view as a trusted asset.

WORKAROUND PATTERN
──────────────────
If Genie can't answer a question: extract the SQL that Genie generates,
run it in a notebook, save the result as a Delta table, and add THAT table
as a trusted Genie asset. Genie can then query the pre-computed result.
"""
print(GENIE_LIMITATIONS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 5 — Genie Conversation API: Teams and Slack Integration
# MAGIC
# MAGIC The Genie Conversation API lets you embed Genie in any application.
# MAGIC Common integration patterns:
# MAGIC - Microsoft Teams bot that answers NEM data questions
# MAGIC - Slack slash command that queries outage data
# MAGIC - SharePoint page with an embedded Genie chat widget

# COMMAND ----------

# MAGIC %md
# MAGIC ### Conversation API — Full Pattern
# MAGIC
# MAGIC The three API calls required for a complete integration:

# COMMAND ----------

# PATTERN: Genie Conversation API integration
# This shows the full request/response cycle your Teams or Slack bot would use.

def genie_full_conversation_cycle(space_id: str, question: str) -> dict:
    """
    Demonstrates the three-step API pattern for embedding Genie in an application:
    1. Start conversation (returns conversation_id + message_id)
    2. Poll until complete
    3. Fetch the SQL result data (optional — for rendering a table in the app)
    """
    # Step 1: Start conversation
    print(f"Step 1: Posting question to Genie Space {space_id}")
    start = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{space_id}/start-conversation",
        headers=hdrs(),
        json={"content": question}
    )
    start.raise_for_status()
    d = start.json()
    conv_id = d["conversation_id"]
    msg_id  = d["message_id"]
    print(f"  conversation_id: {conv_id}")
    print(f"  message_id:      {msg_id}")

    # Step 2: Poll for completion
    print("\nStep 2: Polling for result...")
    for i in range(30):
        poll = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}",
            headers=hdrs()
        )
        msg    = poll.json()
        status = msg.get("status")
        print(f"  [{i+1}] {status}")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)

    # Step 3: If there's a query result, fetch the data rows
    query_result_id = None
    for att in msg.get("attachments", []):
        if att.get("query") and att["query"].get("query_result_metadata_id"):
            query_result_id = att["query"]["query_result_metadata_id"]
            break

    rows = []
    if query_result_id:
        print(f"\nStep 3: Fetching query result rows (result_id={query_result_id})")
        result_resp = requests.get(
            f"https://{HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}"
            f"/messages/{msg_id}/query-result/{query_result_id}",
            headers=hdrs()
        )
        if result_resp.status_code == 200:
            rows = result_resp.json().get("statement_response", {}).get("result", {}).get("data_array", [])
            print(f"  Received {len(rows)} data rows")

    return {
        "conversation_id": conv_id,
        "message_id":      msg_id,
        "status":          msg.get("status"),
        "message":         msg,
        "data_rows":       rows
    }


# Teams/Slack bot integration example
INTEGRATION_QUESTION = "What was the total energy not served in unplanned outages last month?"

print("GENIE CONVERSATION API — TEAMS/SLACK INTEGRATION EXAMPLE")
print("=" * 60)
print(f"Question: {INTEGRATION_QUESTION}\n")

integration_result = genie_full_conversation_cycle(SPACE_ID, INTEGRATION_QUESTION)

print("\nFINAL RESULT")
print("-" * 40)
print_genie_result(integration_result["message"])

# COMMAND ----------

# MAGIC %md
# MAGIC ### Teams Bot Pseudocode
# MAGIC
# MAGIC The pattern above maps directly to a Teams bot or Slack app:

# COMMAND ----------

TEAMS_BOT_PSEUDOCODE = '''
# Microsoft Teams Bot (Python / Azure Functions)
# ──────────────────────────────────────────────

@app.activity_handler.on_message_activity
async def on_message(context: TurnContext):
    user_question = context.activity.text

    # Call Genie API (same pattern as above)
    genie_client = GenieChatClient(
        host    = DATABRICKS_HOST,
        token   = DATABRICKS_TOKEN,
        space_id = GENIE_SPACE_ID
    )

    result = await genie_client.ask(user_question)

    # Format for Teams
    if result.narrative:
        await context.send_activity(result.narrative)

    if result.data_rows:
        # Render as an Adaptive Card table
        card = build_adaptive_card_table(result.columns, result.data_rows[:10])
        await context.send_activity(MessageFactory.attachment(CardFactory.adaptive_card(card)))

    if result.sql:
        # Optionally include the SQL for power users
        await context.send_activity(f"Generated SQL:\\n```sql\\n{result.sql}\\n```")
'''

print(TEAMS_BOT_PSEUDOCODE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 6 — Exporting to AI/BI Dashboards
# MAGIC
# MAGIC Genie results can be pinned directly to an AI/BI dashboard.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Export Pattern: Genie → Delta View → Dashboard
# MAGIC
# MAGIC The most reliable pattern for recurring dashboard data:
# MAGIC 1. Run the Genie query
# MAGIC 2. Copy the generated SQL into a Delta view
# MAGIC 3. Add the view to the dashboard as a dataset
# MAGIC 4. The dashboard refreshes on schedule; Genie stays the exploration tool

# COMMAND ----------

# Example: a common Genie question that becomes a dashboard tile
# Once you're happy with Genie's SQL, materialise it as a view.

DASHBOARD_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.v_dashboard_outage_summary AS
-- Source: derived from Genie conversation — "monthly outages by region"
-- Refreshed: daily via scheduled job
SELECT
    region,
    DATE_TRUNC('month', start_time)          AS month,
    SUM(CASE WHEN outage_type='UNPLANNED' THEN 1 ELSE 0 END) AS unplanned_count,
    SUM(CASE WHEN outage_type='PLANNED'   THEN 1 ELSE 0 END) AS planned_count,
    SUM(customers_affected)                                   AS total_customer_interruptions,
    ROUND(SUM(COALESCE(energy_not_served_mwh, 0)), 2)         AS total_ens_mwh,
    ROUND(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)
              * customers_affected) / 450000.0, 2)            AS saidi_component_minutes
FROM {CATALOG}.{SCHEMA}.outages
WHERE end_time IS NOT NULL
GROUP BY region, DATE_TRUNC('month', start_time)
"""

spark.sql(DASHBOARD_VIEW_SQL)
print("Dashboard view created: v_dashboard_outage_summary")

# Verify
spark.table(f"{CATALOG}.{SCHEMA}.v_dashboard_outage_summary").show(5, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Dashboard Setup Steps (UI)
# MAGIC
# MAGIC 1. Go to **SQL → Dashboards → New Dashboard**
# MAGIC 2. Click **Add Dataset** → select `workshop.energy_nem.v_dashboard_outage_summary`
# MAGIC 3. Add visualisations:
# MAGIC    - Bar chart: `unplanned_count` by `month`, coloured by `region`
# MAGIC    - KPI tile: total `total_ens_mwh` for last 12 months
# MAGIC    - Line chart: `saidi_component_minutes` trend
# MAGIC 4. Add a **Genie widget** to the dashboard (AI/BI feature) — this embeds
# MAGIC    a chat interface so users can ask follow-up questions directly on the dashboard

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exercise: Question Quality Challenge
# MAGIC
# MAGIC **Instructions:**
# MAGIC For each scenario below, write a Level 5 question (excellent quality) that would
# MAGIC get a reliable answer from the Genie Space configured in this workshop.
# MAGIC Then test your questions using `genie_ask()`.

# COMMAND ----------

EXERCISE_SCENARIOS = [
    {
        "scenario": "1. Asset management team wants to identify which ZONE_SUBSTATION assets "
                    "in NSW1 haven't had maintenance in over 18 months and have had at least one outage.",
        "your_question": ""  # TODO: write your Level 5 question here
    },
    {
        "scenario": "2. Regulatory team needs the total ENS (MWh) for weather-related outages in each "
                    "region for the last two financial years, formatted for an AER submission table.",
        "your_question": ""  # TODO
    },
    {
        "scenario": "3. Operations team wants to know if meter readings in AUSNET_EAST zone have "
                    "any obvious data quality issues (estimated or missing flags) in the last 30 days.",
        "your_question": ""  # TODO
    },
]

for ex in EXERCISE_SCENARIOS:
    print(ex["scenario"])
    if ex["your_question"]:
        print(f"  Your question: {ex['your_question']}")
        # Uncomment to test:
        # result = genie_ask(ex["your_question"])
        # print_genie_result(result)
    else:
        print("  (TODO: write your Level 5 question and test it)")
    print()

# COMMAND ----------

# Reference answers — uncomment to reveal
REFERENCE_ANSWERS = {
    "1": (
        "Show me all ZONE_SUBSTATION assets in NSW1 (region = 'NSW1') where last_maintenance "
        "is more than 18 months before today AND the asset has had at least one unplanned outage "
        "in the last 3 years. Include asset name, last_maintenance date, owner_dnsp, outage count, "
        "and total customers affected. Order by outage count descending."
    ),
    "2": (
        "For weather-related unplanned outages (cause_category = 'WEATHER'), show the total energy "
        "not served in MWh (SUM of energy_not_served_mwh, treating NULL as 0) grouped by region and "
        "financial year. Financial years: FY2023 = Jul 2022 – Jun 2023, FY2024 = Jul 2023 – Jun 2024. "
        "Format as a table with columns: region, financial_year, total_ens_mwh. "
        "Order by financial_year, region."
    ),
    "3": (
        "In the AUSNET_EAST distribution zone, for meter readings in the last 30 days, show the count "
        "of readings by quality_flag (A, E, S, N). Also show what percentage of total readings each "
        "flag represents. Order by count descending so I can see the most common issues first."
    ),
}

# SOLUTION: reference answers revealed
for k, v in REFERENCE_ANSWERS.items():
    print(f"Reference answer {k}:\n  {v}\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab 03 — Review Questions
# MAGIC
# MAGIC 1. A user complains that Genie keeps returning kWh totals when they want MWh.
# MAGIC    What is the simplest fix in the question they're asking?
# MAGIC
# MAGIC 2. You're building a Teams bot using the Genie Conversation API. After calling
# MAGIC    `/start-conversation`, the response comes back with `status: EXECUTING_QUERY`.
# MAGIC    What should your bot do next?
# MAGIC
# MAGIC 3. A business analyst wants Genie to "remember" that they always work on VIC1 data.
# MAGIC    Can Genie do this across sessions? If not, what are two workarounds?
# MAGIC
# MAGIC 4. Why is it better to pin Genie-generated SQL to a Delta view for dashboard use,
# MAGIC    rather than running the Genie conversation API directly on each dashboard load?
# MAGIC
# MAGIC 5. What is the difference in response time between Chat mode and Agent mode,
# MAGIC    and when would you prefer each for an operational use case?
# MAGIC
# MAGIC **Proceed to Lab 04 when ready.**
