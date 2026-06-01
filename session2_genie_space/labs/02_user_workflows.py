# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 02: Benchmarks, Golden Queries & Instructions</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 35 minutes |
# MAGIC | **Prerequisites** | Lab 01 complete — Genie Space created, Space ID pasted in widget |
# MAGIC | **Covers** | Slides 25, 28–29 — Benchmarks first, then Example SQL, then Text |
# MAGIC
# MAGIC > *"Create benchmarks before you iterate on instructions. Run them as a regression test with every change."*

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID")
SPACE_ID = dbutils.widgets.get("genie_space_id")
CATALOG  = "workshop_au"
SCHEMA   = "aemo"
HOST     = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN    = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS  = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
if not SPACE_ID:
    raise RuntimeError(
        "Space ID is empty. Paste your Genie Space ID into the 'genie_space_id' widget above "
        "(copy it from the browser URL bar while viewing your space)."
    )
print(f"Space: {SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Add Benchmarks
# MAGIC
# MAGIC **Important distinction:** benchmarks are an *evaluation tool*, not instructions to Genie.
# MAGIC They measure whether Genie generates the SQL you expect — they do not change how Genie behaves.
# MAGIC Run your baseline score now, before adding any golden queries or text instructions,
# MAGIC so you can see what each addition actually moves.
# MAGIC
# MAGIC **How the API works:** all space configuration (benchmarks, golden queries, text instructions)
# MAGIC lives inside a single `serialized_space` JSON blob. There are no separate endpoints for each type.
# MAGIC Every automated cell in this lab follows the same pattern:
# MAGIC 1. `GET /api/2.0/genie/spaces/{id}?include_serialized_space=true` — fetch current config
# MAGIC 2. Parse and update the relevant section of the JSON
# MAGIC 3. `PATCH /api/2.0/genie/spaces/{id}` — write it back
# MAGIC
# MAGIC **🖱️ UI:** **Benchmarks** tab (top-level, alongside About/Data/Instructions) → **+ Add benchmark** → paste title → add expected SQL
# MAGIC
# MAGIC **⚡ Automated:** run the cell below to replace the benchmark question set in one go.

# COMMAND ----------

import requests, json

BENCHMARKS = [
    {
        "title": "What was the average spot price in NSW1 yesterday?",
        "sql":   f"SELECT region_id, ROUND(AVG(rrp), 2) AS avg_price_mwh FROM {CATALOG}.{SCHEMA}.spot_prices WHERE region_id = 'NSW1' AND DATE(settlement_date) = CURRENT_DATE - 1 GROUP BY region_id"
    },
    {
        "title": "Show me yesterday's regional reference price for NSW",
        "sql":   f"SELECT region_id, ROUND(AVG(rrp), 2) AS avg_price_mwh FROM {CATALOG}.{SCHEMA}.spot_prices WHERE region_id = 'NSW1' AND DATE(settlement_date) = CURRENT_DATE - 1 GROUP BY region_id"
    },
    {
        "title": "How many 5-minute intervals exceeded $300 per MWh in VIC last week?",
        "sql":   f"SELECT COUNT(*) AS spike_count FROM {CATALOG}.{SCHEMA}.spot_prices WHERE region_id = 'VIC1' AND rrp > 300 AND settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS"
    },
    {
        "title": "Show price spike events above $1000 per MWh this month by region",
        "sql":   f"SELECT region_id, COUNT(*) AS spikes FROM {CATALOG}.{SCHEMA}.spot_prices WHERE rrp > 1000 AND settlement_date >= DATE_TRUNC('month', CURRENT_DATE) GROUP BY region_id ORDER BY spikes DESC"
    },
    {
        "title": "Which generators dispatched the most MW in QLD last week?",
        "sql":   f"SELECT d.duid, g.station_name, g.fuel_type, ROUND(SUM(d.dispatch_mw)/12, 1) AS total_mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals d LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid WHERE d.region_id = 'QLD1' AND d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS GROUP BY d.duid, g.station_name, g.fuel_type ORDER BY total_mwh DESC LIMIT 10"
    },
    {
        "title": "Show top 10 generators by total dispatch in South Australia this month",
        "sql":   f"SELECT d.duid, g.station_name, g.fuel_type, ROUND(SUM(d.dispatch_mw)/12, 1) AS total_mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals d LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid WHERE d.region_id = 'SA1' AND d.settlement_date >= DATE_TRUNC('month', CURRENT_DATE) GROUP BY d.duid, g.station_name, g.fuel_type ORDER BY total_mwh DESC LIMIT 10"
    },
    {
        "title": "What was the fuel mix for dispatch in SA today?",
        "sql":   f"SELECT fuel_type, ROUND(SUM(dispatch_mw)/12, 0) AS total_mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals WHERE region_id = 'SA1' AND DATE(settlement_date) = CURRENT_DATE GROUP BY fuel_type ORDER BY total_mwh DESC"
    },
    {
        "title": "Show renewable generation as a percentage of total dispatch this quarter",
        "sql":   f"SELECT ROUND(SUM(CASE WHEN fuel_type IN ('solar','wind') THEN dispatch_mw ELSE 0 END) * 100.0 / NULLIF(SUM(dispatch_mw), 0), 1) AS renewable_pct FROM {CATALOG}.{SCHEMA}.dispatch_intervals WHERE settlement_date >= DATE_TRUNC('quarter', CURRENT_DATE)"
    },
    {
        "title": "Were there any LOR events in the last fortnight?",
        "sql":   f"SELECT notice_type, issue_time, region_id, SUBSTRING(reason, 1, 200) AS summary FROM {CATALOG}.{SCHEMA}.market_notices WHERE notice_type LIKE 'LOR%' AND issue_time >= CURRENT_TIMESTAMP - INTERVAL 14 DAYS ORDER BY issue_time DESC"
    },
    {
        "title": "List all lack of reserve notices from the past 30 days",
        "sql":   f"SELECT notice_type, issue_time, region_id, SUBSTRING(reason, 1, 200) AS summary FROM {CATALOG}.{SCHEMA}.market_notices WHERE notice_type LIKE 'LOR%' AND issue_time >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS ORDER BY issue_time DESC"
    },
]

def _get_serialized_space(host, space_id, headers):
    """Fetch the current space and return (space_dict, config_dict).
    serialized_space is a JSON string nested inside the space response — parse it here."""
    resp = requests.get(
        f"https://{host}/api/2.0/genie/spaces/{space_id}",
        params={"include_serialized_space": "true"},
        headers=headers
    )
    resp.raise_for_status()
    space = resp.json()
    raw = space.get("serialized_space") or "{}"
    config = json.loads(raw)
    return space, config

def _patch_space(host, space_id, headers, config, etag=None):
    """Write the updated config back. Returns the response object."""
    body = {"serialized_space": json.dumps(config)}
    if etag:
        body["etag"] = etag
    return requests.patch(
        f"https://{host}/api/2.0/genie/spaces/{space_id}",
        headers=headers,
        json=body
    )

# Upload benchmarks via serialized_space PATCH
space, config = _get_serialized_space(HOST, SPACE_ID, HEADERS)
etag = space.get("etag")

config["benchmark_questions"] = [
    {"title": bm["title"], "expected_sql": bm["sql"]}
    for bm in BENCHMARKS
]

patch_resp = _patch_space(HOST, SPACE_ID, HEADERS, config, etag)
if patch_resp.status_code in (200, 204):
    print(f"✅ {len(BENCHMARKS)} benchmarks written to space")
    print(f"\nNow run them: Benchmarks tab (top-level, not under Configure) → Run benchmarks")
    print(f"Note your baseline score before adding any golden queries.")
else:
    print(f"❌ PATCH failed: {patch_resp.status_code}")
    print(patch_resp.text[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Add Golden Queries
# MAGIC
# MAGIC **🖱️ UI:** Configure → Instructions → SQL Queries → + Add → paste title + SQL
# MAGIC
# MAGIC **⚡ Automated:** run the cell below to replace all golden queries at once.
# MAGIC Same pattern as Step 1: reads serialized_space, replaces the sql_queries array, PATCHes back.

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Average spot price by region for a date",
        "description": "Use when asking about price levels or averages for a specific day. The :date parameter accepts a date value.",
        "query": f"""SELECT
    region_id,
    ROUND(AVG(rrp), 2)  AS avg_price_mwh,
    ROUND(MIN(rrp), 2)  AS min_price_mwh,
    ROUND(MAX(rrp), 2)  AS max_price_mwh,
    COUNT(*)            AS interval_count
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE DATE(settlement_date) = :date_period
GROUP BY region_id
ORDER BY avg_price_mwh DESC"""
    },
    {
        "name": "Price spikes above threshold in a region",
        "description": "Use when asking about high price events, price spikes, or prices exceeding a threshold. :region is the NEM region (e.g. VIC1). :threshold is the $/MWh threshold (default 300).",
        "query": f"""SELECT
    region_id,
    DATE(settlement_date)  AS spike_date,
    settlement_date        AS interval_time,
    ROUND(rrp, 2)          AS price_mwh
FROM {CATALOG}.{SCHEMA}.spot_prices
WHERE region_id = :region
  AND rrp > :threshold
  AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY rrp DESC"""
    },
    {
        "name": "Top generators by dispatch in a region",
        "description": "Use when asking which generators dispatched most, top generators, or generation output. :region is the NEM region (e.g. QLD1).",
        "query": f"""SELECT
    d.duid,
    g.station_name,
    g.fuel_type,
    ROUND(SUM(d.dispatch_mw) / 12, 1)  AS total_mwh,
    ROUND(AVG(d.dispatch_mw), 1)        AS avg_dispatch_mw
FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid
WHERE d.region_id = :region
  AND d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY d.duid, g.station_name, g.fuel_type
ORDER BY total_mwh DESC
LIMIT 15"""
    },
    {
        "name": "Fuel mix by region",
        "description": "Use when asking about generation mix, renewable versus fossil fuel, or fuel type breakdown. :region is the NEM region.",
        "query": f"""SELECT
    CASE
        WHEN fuel_type IN ('solar', 'wind') THEN 'Renewable'
        WHEN fuel_type IN ('coal', 'gas')   THEN 'Fossil Fuel'
        ELSE 'Other'
    END                              AS generation_type,
    fuel_type,
    ROUND(SUM(dispatch_mw) / 12, 0) AS total_mwh
FROM {CATALOG}.{SCHEMA}.dispatch_intervals
WHERE region_id = :region
  AND settlement_date >= CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY generation_type, fuel_type
ORDER BY total_mwh DESC"""
    },
    {
        "name": "LOR and market notices in last N days",
        "description": "Use when asking about LOR events, lack-of-reserve notices, market interventions, or reserve warnings. :days is the lookback period in days (default 14).",
        "query": f"""SELECT
    notice_type,
    issue_time,
    effective_date,
    region_id,
    SUBSTRING(reason, 1, 250) AS summary
FROM {CATALOG}.{SCHEMA}.market_notices
WHERE notice_type LIKE 'LOR%'
  AND issue_time >= CURRENT_TIMESTAMP - INTERVAL :days DAYS
ORDER BY issue_time DESC"""
    },
]

# Upload golden queries via serialized_space PATCH
space, config = _get_serialized_space(HOST, SPACE_ID, HEADERS)
etag = space.get("etag")

config["sql_queries"] = [
    {"name": gq["name"], "description": gq["description"], "query": gq["query"]}
    for gq in GOLDEN_QUERIES
]

patch_resp = _patch_space(HOST, SPACE_ID, HEADERS, config, etag)
if patch_resp.status_code in (200, 204):
    print(f"✅ {len(GOLDEN_QUERIES)} golden queries written to space")
else:
    print(f"❌ PATCH failed: {patch_resp.status_code}")
    print(patch_resp.text[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Text Instructions — last resort only
# MAGIC
# MAGIC **🖱️ UI:** Configure → Instructions → **Text** → type in the text box → **Save** (there is no + Add button, just a text field and Save)
# MAGIC
# MAGIC **⚡ Automated:** replaces the text instructions array in one PATCH call.

# COMMAND ----------

TEXT_INSTRUCTIONS = [
    "Always express prices in $/MWh with 2 decimal places.",
    "Region codes must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix. Never use NSW, VIC, QLD, SA, or TAS without the suffix.",
    "LOR1 = first reserve watch warning. LOR2 = reserve shortfall threatened. LOR3 = imminent critical shortage. Always use LIKE 'LOR%' to match all LOR types.",
    "When asked about 'today' with no data available, say so and suggest yesterday instead.",
]

# Upload text instructions via serialized_space PATCH
space, config = _get_serialized_space(HOST, SPACE_ID, HEADERS)
etag = space.get("etag")

config["text_instructions"] = TEXT_INSTRUCTIONS

patch_resp = _patch_space(HOST, SPACE_ID, HEADERS, config, etag)
if patch_resp.status_code in (200, 204):
    print(f"✅ {len(TEXT_INSTRUCTIONS)} text instructions written to space")
else:
    print(f"❌ PATCH failed: {patch_resp.status_code}")
    print(patch_resp.text[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 02 Checkpoint
# MAGIC - [ ] 10 benchmarks uploaded (automated) — **run them now and note baseline score**
# MAGIC - [ ] 5 golden queries uploaded (automated)
# MAGIC - [ ] 4 text instructions uploaded (automated)
# MAGIC
# MAGIC **→ Next: Lab 03 — Run Benchmarks, Monitor & Iterate**
