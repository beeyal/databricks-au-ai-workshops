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
print(f"Space: {SPACE_ID or 'not set'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Add Benchmarks
# MAGIC
# MAGIC **🖱️ UI:** Configure → Benchmarks → + Add benchmark → paste title → add expected SQL
# MAGIC
# MAGIC **⚡ Automated:** run the cell below to upload all 10 benchmarks at once.
# MAGIC Deletes and replaces any existing benchmark with the same title.

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

if not SPACE_ID:
    print("Enter Space ID in widget first.")
else:
    # 1. Get existing benchmarks
    existing = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-questions",
        headers=HEADERS
    )
    existing_ids = {}
    if existing.status_code == 200:
        for q in existing.json().get("benchmark_questions", []):
            existing_ids[q.get("title", "")] = q.get("id")

    added = deleted = errors = 0
    for bm in BENCHMARKS:
        # Delete existing if same title
        if bm["title"] in existing_ids:
            del_resp = requests.delete(
                f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-questions/{existing_ids[bm['title']]}",
                headers=HEADERS
            )
            if del_resp.status_code in (200, 204):
                deleted += 1

        # Add fresh
        add_resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-questions",
            headers=HEADERS,
            json={"title": bm["title"], "expected_sql": bm["sql"]}
        )
        if add_resp.status_code in (200, 201):
            added += 1
        else:
            errors += 1
            print(f"  ❌ {bm['title'][:60]}: {add_resp.status_code} {add_resp.text[:100]}")

    print(f"✅ {added} benchmarks added, {deleted} replaced, {errors} errors")
    print(f"\nNow run them: Configure → Benchmarks → Run benchmarks")
    print(f"Note your baseline score before adding any golden queries.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Add Golden Queries
# MAGIC
# MAGIC **🖱️ UI:** Configure → Instructions → SQL Queries → + Add → paste title + SQL
# MAGIC
# MAGIC **⚡ Automated:** run the cell below to upload all 5 queries at once.
# MAGIC Deletes and replaces any query with the same title.

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

if not SPACE_ID:
    print("Enter Space ID in widget first.")
else:
    # Get existing queries
    existing_resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
        headers=HEADERS
    )
    existing_qs = {}
    if existing_resp.status_code == 200:
        for q in existing_resp.json().get("sql_queries", []):
            existing_qs[q.get("name", "")] = q.get("id")

    added = deleted = errors = 0
    for gq in GOLDEN_QUERIES:
        if gq["name"] in existing_qs:
            del_resp = requests.delete(
                f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries/{existing_qs[gq['name']]}",
                headers=HEADERS
            )
            if del_resp.status_code in (200, 204):
                deleted += 1

        add_resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
            headers=HEADERS,
            json={"name": gq["name"], "description": gq["description"], "query": gq["query"]}
        )
        if add_resp.status_code in (200, 201):
            added += 1
        else:
            errors += 1
            print(f"  ❌ {gq['name']}: {add_resp.status_code} {add_resp.text[:100]}")

    print(f"✅ {added} golden queries added, {deleted} replaced, {errors} errors")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Text Instructions — last resort only
# MAGIC
# MAGIC **🖱️ UI:** Configure → Instructions → Text → + Add
# MAGIC
# MAGIC **⚡ Automated:** uploads 4 instructions, replacing any with the same content.

# COMMAND ----------

TEXT_INSTRUCTIONS = [
    "Always express prices in $/MWh with 2 decimal places.",
    "Region codes must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix. Never use NSW, VIC, QLD, SA, or TAS without the suffix.",
    "LOR1 = first reserve watch warning. LOR2 = reserve shortfall threatened. LOR3 = imminent critical shortage. Always use LIKE 'LOR%' to match all LOR types.",
    "When asked about 'today' with no data available, say so and suggest yesterday instead.",
]

if not SPACE_ID:
    print("Enter Space ID in widget first.")
else:
    existing_resp = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/instructions",
        headers=HEADERS
    )
    existing_text = {}
    if existing_resp.status_code == 200:
        for instr in existing_resp.json().get("instructions", []):
            existing_text[instr.get("content", "")] = instr.get("id")

    added = deleted = errors = 0
    for content in TEXT_INSTRUCTIONS:
        if content in existing_text:
            del_resp = requests.delete(
                f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/instructions/{existing_text[content]}",
                headers=HEADERS
            )
            if del_resp.status_code in (200, 204):
                deleted += 1

        add_resp = requests.post(
            f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/instructions",
            headers=HEADERS,
            json={"content": content}
        )
        if add_resp.status_code in (200, 201):
            added += 1
        else:
            errors += 1
            print(f"  ❌ {content[:60]}: {add_resp.status_code} {add_resp.text[:80]}")

    print(f"✅ {added} instructions added, {deleted} replaced, {errors} errors")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 02 Checkpoint
# MAGIC - [ ] 10 benchmarks uploaded (automated) — **run them now and note baseline score**
# MAGIC - [ ] 5 golden queries uploaded (automated)
# MAGIC - [ ] 4 text instructions uploaded (automated)
# MAGIC
# MAGIC **→ Next: Lab 03 — Run Benchmarks, Monitor & Iterate**
