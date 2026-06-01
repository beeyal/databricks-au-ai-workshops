# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">AEMO Reference Space — Facilitator Setup</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2 facilitator notebook — builds a complete reference Genie Space for demonstration</p>
# MAGIC </div>
# MAGIC
# MAGIC **Run this notebook as a workspace admin AFTER `setup/setup.py`.**
# MAGIC It configures a fully-instrumented reference Genie Space that the facilitator uses to demonstrate
# MAGIC what a well-built space looks like. Labs participants build their own spaces.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `setup/setup.py` has been run and all 6 AEMO tables are loaded in Unity Catalog
# MAGIC - A Pro or Serverless SQL warehouse is available
# MAGIC - Genie feature is enabled in the workspace
# MAGIC
# MAGIC Expected runtime: ~3 minutes

# COMMAND ----------

dbutils.widgets.text("catalog",      "workshop_au", "Catalog")
dbutils.widgets.text("schema",       "aemo",        "Schema")
dbutils.widgets.text("warehouse_id", "",            "SQL Warehouse ID (for Genie Space)")
dbutils.widgets.text("space_id",     "",            "Existing Space ID (leave blank to create new)")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id")
SPACE_ID     = dbutils.widgets.get("space_id")

HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print(f"Catalog  : {CATALOG}.{SCHEMA}")
print(f"Host     : {HOST}")
print(f"Space ID : {SPACE_ID or '(will create new)'}")
if not WAREHOUSE_ID:
    print("\n⚠️  Enter a warehouse_id in the widget above to create the Genie Space.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Verify AEMO tables are loaded
# MAGIC
# MAGIC Confirm all 6 tables exist before proceeding. If any are missing, run `setup/setup.py` first.

# COMMAND ----------

import pyspark.sql.utils

REQUIRED_TABLES = [
    "spot_prices",
    "dispatch_intervals",
    "market_notices",
    "generator_registration",
    "settlement_amounts",
    "constraint_sets",
]

all_present = True
for tbl in REQUIRED_TABLES:
    fqn = f"{CATALOG}.{SCHEMA}.{tbl}"
    try:
        count = spark.table(fqn).count()
        print(f"  ✅ {tbl}: {count:,} rows")
    except Exception as e:
        print(f"  ❌ {tbl}: {e}")
        all_present = False

if not all_present:
    raise RuntimeError("Some tables are missing. Run setup/setup.py first.")
else:
    print("\nAll tables present — proceeding.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Ensure column comments are set (idempotent)
# MAGIC
# MAGIC Re-applying comments here is safe — setup.py may already have done this.
# MAGIC These comments are the most important Genie tuning signal.

# COMMAND ----------

COLUMN_COMMENTS = {
    f"{CATALOG}.{SCHEMA}.spot_prices": {
        "settlement_date": "Trading interval end time. 30-minute intervals. AEST/AEDT timezone. Use DATE(settlement_date) to filter by day.",
        "region_id":       "NEM region. Must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix.",
        "rrp":             "Regional Reference Price in $/MWh. Normal range $50–$200. Market cap $15,300/MWh. Floor -$1,000/MWh. Negative = oversupply.",
        "raise_6sec":      "6-second raise FCAS price. Hide unless FCAS analysis is needed.",
        "lower_6sec":      "6-second lower FCAS price. Hide unless FCAS analysis is needed.",
        "total_demand_mw": "Total scheduled demand for the region in MW.",
        "net_interchange": "Net MW flow between regions. Positive = exporting.",
        "scheduled_generation": "Total scheduled generation in the region in MW.",
    },
    f"{CATALOG}.{SCHEMA}.dispatch_intervals": {
        "settlement_date": "5-minute dispatch interval end time. Sum dispatch_mw and divide by 12 to convert to MWh.",
        "region_id":       "NEM region where the unit dispatched. Must be NSW1, VIC1, QLD1, SA1, or TAS1.",
        "duid":            "Dispatchable Unit Identifier. Join to generator_registration.duid for station_name and fuel_type.",
        "dispatch_mw":     "Actual MW dispatched in this 5-minute interval. SUM(dispatch_mw)/12 = MWh.",
        "initial_mw":      "Initial MW target at interval start.",
        "available_mw":    "MW available for dispatch.",
        "ramp_rate":       "Maximum ramp rate in MW per minute.",
        "fuel_type":       "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "station_name":    "Human-readable station name e.g. Bayswater, Loy Yang A.",
        "state":           "Australian state the unit is located in.",
    },
    f"{CATALOG}.{SCHEMA}.market_notices": {
        "notice_id":     "Unique identifier for the market notice.",
        "notice_type":   "LOR1 = reserve watch. LOR2 = shortfall threatened. LOR3 = imminent critical shortage. Use LIKE 'LOR%' to match all LOR types.",
        "issue_time":    "When AEMO published the notice. Use to filter recent events.",
        "reason":        "Free-text description. Use SUBSTRING(reason, 1, 200) for summaries.",
        "effective_date":"When the notice takes effect.",
        "region_id":     "NEM region. NULL means NEM-wide notice.",
        "intervention":  "True if this is an AEMO market intervention.",
    },
    f"{CATALOG}.{SCHEMA}.generator_registration": {
        "duid":                   "Dispatchable Unit Identifier. Primary key. Join to dispatch_intervals.duid.",
        "station_name":           "Human-readable station name.",
        "participant_id":         "Market participant code.",
        "region_id":              "NEM region where registered.",
        "fuel_type":              "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "registered_capacity_mw": "Maximum registered capacity in MW.",
        "connection_point_id":    "NEM connection point identifier for the unit.",
        "dispatch_type":          "GENERATOR, LOAD, or BIDIRECTIONAL.",
        "max_ramp_rate":          "Maximum ramp rate in MW per minute.",
        "min_load":               "Minimum stable load in MW.",
    },
    f"{CATALOG}.{SCHEMA}.constraint_sets": {
        "constraint_id":         "Unique constraint identifier e.g. S_RADIAL_SA_1.",
        "constraint_type":       "Type of constraint: thermal, voltage, stability.",
        "activated_datetime":    "When the constraint became active.",
        "deactivated_datetime":  "When the constraint was lifted. NULL if still active.",
        "reason":                "Free-text description of why the constraint was activated.",
        "rhs_value":             "Right-hand side MW limit of the constraint equation.",
        "region_affected":       "NEM region impacted by this constraint.",
        "interconnector":        "True if this constraint involves an interconnector flow.",
    },
    f"{CATALOG}.{SCHEMA}.settlement_amounts": {
        "settlement_date":            "Settlement week end date.",
        "participant_id":             "Market participant code.",
        "run_type":                   "FINAL, REVISED, or PRELIMINARY.",
        "energy_amount_aud":          "Energy component of settlement in AUD.",
        "fcas_amount_aud":            "FCAS (ancillary services) component in AUD.",
        "interconnector_residue_aud": "Interconnector residue component in AUD.",
        "total_aud":                  "Net settlement amount in AUD.",
        "settlement_status":          "FINAL, PENDING, or DISPUTED.",
    },
}

ok = err = 0
for table_fqn, columns in COLUMN_COMMENTS.items():
    for col, comment in columns.items():
        try:
            safe_comment = comment.replace("'", "\\'")
            spark.sql(f"ALTER TABLE {table_fqn} ALTER COLUMN `{col}` COMMENT '{safe_comment}'")
            ok += 1
        except Exception as e:
            print(f"  ⚠️  {table_fqn.split('.')[-1]}.{col}: {e}")
            err += 1

print(f"✅ {ok} column comments set ({err} errors)")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Create the reference Genie Space (or reuse existing)
# MAGIC
# MAGIC If `space_id` widget is blank, a new space is created via the Genie API.
# MAGIC If you already have a reference space, paste its ID in the widget to skip creation.

# COMMAND ----------

import requests, json

if SPACE_ID:
    # Verify the existing space is reachable
    resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=HEADERS)
    if resp.status_code == 200:
        print(f"✅ Using existing space: {resp.json().get('title')} ({SPACE_ID})")
    else:
        print(f"⚠️  Space {SPACE_ID} not found ({resp.status_code}). Will create a new one.")
        SPACE_ID = ""

if not SPACE_ID:
    if not WAREHOUSE_ID:
        print("❌ warehouse_id is required to create a new Genie Space.")
        print("   Enter it in the widget above and re-run.")
    else:
        space_payload = {
            "title":       "AEMO NEM Operations — Reference Space",
            "description": (
                "Reference space for facilitators. Natural language access to NEM spot prices, "
                "dispatch intervals, market notices, generator registration, settlement amounts, "
                "and network constraint sets. Demonstrates a fully configured Genie Space."
            ),
            "warehouse_id": WAREHOUSE_ID,
            "datasets": [
                {"table_name": f"{CATALOG}.{SCHEMA}.spot_prices"},
                {"table_name": f"{CATALOG}.{SCHEMA}.dispatch_intervals"},
                {"table_name": f"{CATALOG}.{SCHEMA}.market_notices"},
                {"table_name": f"{CATALOG}.{SCHEMA}.generator_registration"},
                {"table_name": f"{CATALOG}.{SCHEMA}.settlement_amounts"},
                {"table_name": f"{CATALOG}.{SCHEMA}.constraint_sets"},
            ],
        }
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces",
            headers=HEADERS,
            json=space_payload,
        )
        if resp.status_code in (200, 201):
            SPACE_ID = resp.json().get("id", resp.json().get("space_id", ""))
            print(f"✅ Created Genie Space: {SPACE_ID}")
            print(f"   URL: https://{HOST}/genie/spaces/{SPACE_ID}")
            print(f"\n   Paste this Space ID into the 'space_id' widget so you can re-run cells without creating duplicates.")
        else:
            print(f"❌ Failed to create space: {resp.status_code}")
            print(resp.text[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Configure the join relationship
# MAGIC
# MAGIC `dispatch_intervals` ↔ `generator_registration` on `duid` (many-to-one).
# MAGIC This lets Genie resolve "Bayswater" or "Loy Yang A" as station names without the user knowing duids.

# COMMAND ----------

if not SPACE_ID:
    print("Skip — no Space ID. Complete Step 3 first.")
else:
    join_payload = {
        "joins": [{
            "left_table":        f"{CATALOG}.{SCHEMA}.dispatch_intervals",
            "right_table":       f"{CATALOG}.{SCHEMA}.generator_registration",
            "join_condition":    "dispatch_intervals.duid = generator_registration.duid",
            "relationship_type": "MANY_TO_ONE",
        }]
    }
    resp = requests.patch(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
        headers=HEADERS,
        json=join_payload,
    )
    if resp.status_code in (200, 204):
        print("✅ Join configured: dispatch_intervals ↔ generator_registration on duid")
    else:
        print(f"API returned {resp.status_code} — add the join manually:")
        print("  Configure → Instructions → Joins → + Add")
        print("  Left: dispatch_intervals  |  Right: generator_registration")
        print("  Condition: dispatch_intervals.duid = generator_registration.duid")
        print("  Relationship: Many-to-one")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Add text instructions
# MAGIC
# MAGIC Text instructions are universal rules Genie should always apply.
# MAGIC Keep these short and factual — Genie reads all of them on every query.

# COMMAND ----------

INSTRUCTIONS = [
    "All NEM regions must be referenced with the '1' suffix: NSW1, VIC1, QLD1, SA1, TAS1. Never use NSW, VIC, QLD, SA, or TAS alone.",
    "spot_prices intervals are 30 minutes. dispatch_intervals are 5 minutes (12 per hour). Always clarify which table when users ask about 'prices' vs 'dispatch'.",
    "dispatch_mw is MW per 5-minute interval. Multiply SUM(dispatch_mw) / 12 to convert to MWh.",
    "rrp above $300/MWh indicates a high-price event. rrp above $5,000/MWh is a spike worth investigating.",
    "LOR events escalate: LOR1 = reserve watch, LOR2 = shortfall threatened, LOR3 = imminent critical shortage. Always show all three in LOR summaries.",
    "settlement_amounts.run_type = FINAL means confirmed. PRELIMINARY is an estimate. Exclude PRELIMINARY unless the user asks for it.",
    "constraint_sets.deactivated_datetime IS NULL means the constraint is currently active.",
    "When users ask about 'renewables', include solar and wind. When they ask about 'fossil fuels', include coal and gas.",
]

if not SPACE_ID:
    print("Skip — no Space ID. Complete Step 3 first.")
else:
    ok = err = 0
    for instruction in INSTRUCTIONS:
        payload = {"content": instruction}
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/instructions",
            headers=HEADERS,
            json=payload,
        )
        if resp.status_code in (200, 201):
            ok += 1
        else:
            print(f"  ⚠️  Failed ({resp.status_code}): {instruction[:60]}...")
            err += 1

    print(f"✅ {ok} instructions added ({err} errors)")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6: Add golden queries
# MAGIC
# MAGIC Golden queries are routing rules. When a user's question matches the title exactly, Genie runs
# MAGIC the pre-written SQL and labels it **Trusted** — bypassing LLM generation entirely.
# MAGIC These are the most important quality lever after column comments.

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Current spot price by region",
        "description": "Latest rrp for each NEM region from the most recent settlement interval.",
        "sql": f"""
SELECT
    region_id,
    rrp AS spot_price_per_mwh,
    total_demand_mw,
    settlement_date AS latest_interval
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE settlement_date = (SELECT MAX(settlement_date) FROM {CATALOG}.{SCHEMA}.spot_prices)
ORDER BY region_id
""".strip(),
    },
    {
        "name": "Daily average spot price by region",
        "description": "Average rrp per region per day. Group by DATE(settlement_date) and region_id.",
        "sql": f"""
SELECT
    DATE(settlement_date) AS trading_date,
    region_id,
    ROUND(AVG(rrp), 2)          AS avg_rrp_per_mwh,
    ROUND(MAX(rrp), 2)          AS max_rrp_per_mwh,
    ROUND(MIN(rrp), 2)          AS min_rrp_per_mwh
FROM {CATALOG}.{SCHEMA}.spot_prices
GROUP BY 1, 2
ORDER BY 1 DESC, 2
""".strip(),
    },
    {
        "name": "Top generators by output today",
        "description": "Highest-output generating units for today ranked by total MWh dispatched.",
        "sql": f"""
SELECT
    gr.station_name,
    gr.fuel_type,
    gr.region_id,
    ROUND(SUM(di.dispatch_mw) / 12, 1) AS total_mwh_today
FROM {CATALOG}.{SCHEMA}.dispatch_intervals di
JOIN {CATALOG}.{SCHEMA}.generator_registration gr
    ON di.duid = gr.duid
WHERE DATE(di.settlement_date) = CURRENT_DATE
GROUP BY 1, 2, 3
ORDER BY total_mwh_today DESC
LIMIT 20
""".strip(),
    },
    {
        "name": "Generation mix by fuel type",
        "description": "Total MWh dispatched by fuel type for the most recent full day.",
        "sql": f"""
SELECT
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 0) AS total_mwh,
    ROUND(SUM(dispatch_mw) / 12 * 100.0 / SUM(SUM(dispatch_mw) / 12) OVER (), 1) AS pct_of_total
FROM {CATALOG}.{SCHEMA}.dispatch_intervals
WHERE DATE(settlement_date) = DATE_SUB(CURRENT_DATE, 1)
GROUP BY fuel_type
ORDER BY total_mwh DESC
""".strip(),
    },
    {
        "name": "Active LOR notices",
        "description": "All open LOR market notices — lack-of-reserve events still in effect.",
        "sql": f"""
SELECT
    notice_type,
    issue_time,
    effective_date,
    region_id,
    SUBSTRING(reason, 1, 300) AS reason_summary
FROM {CATALOG}.{SCHEMA}.market_notices
WHERE notice_type LIKE 'LOR%'
  AND effective_date >= CURRENT_DATE
ORDER BY notice_type DESC, issue_time DESC
""".strip(),
    },
    {
        "name": "High price events above threshold",
        "description": "Trading intervals where rrp exceeded $300/MWh, ordered by price descending.",
        "sql": f"""
SELECT
    settlement_date,
    region_id,
    ROUND(rrp, 2)          AS rrp_per_mwh,
    total_demand_mw,
    scheduled_generation
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE rrp > 300
ORDER BY rrp DESC
LIMIT 50
""".strip(),
    },
    {
        "name": "Active network constraints",
        "description": "Network constraints currently in effect — where deactivated_datetime is null.",
        "sql": f"""
SELECT
    constraint_id,
    constraint_type,
    region_affected,
    interconnector,
    rhs_value            AS mw_limit,
    activated_datetime,
    SUBSTRING(reason, 1, 200) AS reason_summary
FROM {CATALOG}.{SCHEMA}.constraint_sets
WHERE deactivated_datetime IS NULL
ORDER BY activated_datetime DESC
""".strip(),
    },
    {
        "name": "Settlement amounts by participant",
        "description": "Final net settlement amounts by participant for the most recent settlement run.",
        "sql": f"""
SELECT
    participant_id,
    run_type,
    ROUND(energy_amount_aud, 0)          AS energy_aud,
    ROUND(fcas_amount_aud, 0)            AS fcas_aud,
    ROUND(interconnector_residue_aud, 0) AS ic_residue_aud,
    ROUND(total_aud, 0)                  AS net_total_aud,
    settlement_status
FROM {CATALOG}.{SCHEMA}.settlement_amounts
WHERE run_type = 'FINAL'
  AND settlement_date = (SELECT MAX(settlement_date) FROM {CATALOG}.{SCHEMA}.settlement_amounts WHERE run_type = 'FINAL')
ORDER BY ABS(total_aud) DESC
""".strip(),
    },
]

if not SPACE_ID:
    print("Skip — no Space ID. Complete Step 3 first.")
else:
    ok = err = 0
    for gq in GOLDEN_QUERIES:
        payload = {
            "name":        gq["name"],
            "description": gq["description"],
            "sql":         gq["sql"],
        }
        resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/queries",
            headers=HEADERS,
            json=payload,
        )
        if resp.status_code in (200, 201):
            ok += 1
            print(f"  ✅ {gq['name']}")
        else:
            err += 1
            print(f"  ⚠️  {gq['name']}: {resp.status_code} {resp.text[:100]}")

    print(f"\n✅ {ok} golden queries added ({err} errors)")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 7: Grant participant access
# MAGIC
# MAGIC Enter participant emails as a comma-separated list. The script grants:
# MAGIC - `USE CATALOG` + `USE SCHEMA` + `SELECT` (so Genie can query tables)
# MAGIC - `CREATE TABLE` on the schema (so participants can save Genie Space assets)

# COMMAND ----------

dbutils.widgets.text("participant_emails", "", "Participant emails (comma-separated)")
raw_emails = dbutils.widgets.get("participant_emails")

participants = [e.strip().lower() for e in raw_emails.split(",") if e.strip()]

if not participants:
    print("Enter participant emails in the widget above, then re-run this cell.")
else:
    print(f"Granting access to {len(participants)} participants:\n")

    grants = [
        f"GRANT USE CATALOG ON CATALOG {CATALOG} TO",
        f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT SELECT ON SCHEMA {CATALOG}.{SCHEMA} TO",
        f"GRANT CREATE TABLE ON SCHEMA {CATALOG}.{SCHEMA} TO",  # needed to create Genie Space assets
    ]

    ok = err = 0
    for email in participants:
        for grant_prefix in grants:
            stmt = f"{grant_prefix} `{email}`"
            try:
                spark.sql(stmt)
                ok += 1
            except Exception as e:
                print(f"  ⚠️  {email}: {e}")
                err += 1
        print(f"  ✅ {email}")

    print(f"\n{ok} grants applied ({err} errors)")
    print()
    print("Participants can now:")
    print(f"  • Query all tables in {CATALOG}.{SCHEMA}")
    print(f"  • Create Genie Spaces backed by those tables")
    print(f"  • Run Lab 01–05")

# COMMAND ----------

# Verify grants were applied
if participants:
    print(f"Current grants on {CATALOG}.{SCHEMA}:")
    display(spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.{SCHEMA}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 8: Validate the reference space
# MAGIC
# MAGIC Run a test question against the space to confirm it is live and responding.

# COMMAND ----------

import time

if not SPACE_ID:
    print("Skip — no Space ID. Complete Step 3 first.")
else:
    test_question = "What is the current spot price in NSW1?"

    # Start a conversation
    conv_resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/start-conversation",
        headers=HEADERS,
        json={"content": test_question},
    )

    if conv_resp.status_code not in (200, 201):
        print(f"❌ Could not start conversation: {conv_resp.status_code} {conv_resp.text[:200]}")
    else:
        data        = conv_resp.json()
        conv_id     = data.get("conversation_id")
        message_id  = data.get("message_id")

        print(f"Question: {test_question}")
        print(f"Conv ID : {conv_id}")
        print(f"Waiting for response", end="")

        # Poll for completion (max 60s)
        for _ in range(30):
            time.sleep(2)
            print(".", end="", flush=True)
            msg_resp = requests.get(
                f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conv_id}/messages/{message_id}",
                headers=HEADERS,
            )
            if msg_resp.status_code == 200:
                msg = msg_resp.json()
                status = msg.get("status", "")
                if status in ("COMPLETED", "FAILED", "CANCELLED"):
                    print()
                    if status == "COMPLETED":
                        attachments = msg.get("attachments", [])
                        for att in attachments:
                            if att.get("query"):
                                print(f"✅ Genie generated SQL:\n{att['query'].get('query', '')}")
                            elif att.get("text"):
                                print(f"✅ Genie response: {att['text'].get('content', '')[:300]}")
                    else:
                        print(f"⚠️  Status: {status}")
                    break
        else:
            print("\n⚠️  Timed out waiting for response — space may still be initializing.")

    print(f"\nReference space URL: https://{HOST}/genie/spaces/{SPACE_ID}")
    print(f"Space ID (save this): {SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## What this notebook does NOT do
# MAGIC
# MAGIC The following are handled by labs — do not add them here:
# MAGIC
# MAGIC - ❌ Load CSV data → **`setup/setup.py`** (run that first)
# MAGIC - ❌ Have participants create their own Genie Space → **Lab 01** (UI)
# MAGIC - ❌ Walk through the instruction hierarchy → **Lab 02**
# MAGIC - ❌ Run benchmarks → **Lab 03**
# MAGIC - ❌ Monitor the space → **Lab 04**
# MAGIC - ❌ Set advanced permissions / operating model → **Lab 05**
