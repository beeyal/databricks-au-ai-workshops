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
# MAGIC | **Covers** | Benchmarks → SQL Expressions → Golden Queries → Text Instructions → Inspect |
# MAGIC
# MAGIC > *"Create benchmarks before you iterate on instructions. Run them as a regression test with every change."*
# MAGIC
# MAGIC **Lab overview — what each tool does and when to reach for it:**
# MAGIC
# MAGIC | Tool | Purpose | When to use |
# MAGIC |---|---|---|
# MAGIC | **Benchmarks** | Measure answer quality — evaluation only, does not teach Genie anything | Always set first; re-run after every change |
# MAGIC | **SQL Expressions** | Lock in a KPI formula so Genie always computes it the same way | When a metric has one correct definition (e.g. renewable %) |
# MAGIC | **Golden Queries** | Show Genie a canonical SQL pattern for a whole question type | When users ask the same style of question repeatedly |
# MAGIC | **Text Instructions** | Universal formatting or behavioural rules that apply to every query | Last resort — only for things SQL cannot express |
# MAGIC | **Inspect** | See the SQL Genie generated to produce its answer — the primary query, shown for transparency | After any response — builds trust and helps debug |

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

# Shared helpers — used by every automated step in this lab.
# Run this cell once; all subsequent cells depend on these functions.

import requests, json, uuid

def _hex_uuid():
    """Return a 32-char lowercase hex UUID (no hyphens) as required by the Genie API."""
    return uuid.uuid4().hex

def _get_serialized_space(host, space_id, headers):
    """Fetch the current space and return (space_dict, config_dict).
    serialized_space is a JSON string nested inside the space response."""
    resp = requests.get(
        f"https://{host}/api/2.0/genie/spaces/{space_id}",
        params={"include_serialized_space": "true"},
        headers=headers
    )
    resp.raise_for_status()
    space = resp.json()
    if not space.get("serialized_space"):
        print("WARNING: no existing serialized_space — existing config will be replaced. "
              "Ensure Lab 01 Step 4 ran successfully before proceeding.")
    raw = space.get("serialized_space") or "{}"
    config = json.loads(raw)
    return space, config

def _patch_space(host, space_id, headers, config, etag=None):
    """Write the updated config back. Returns the response object.
    All space config lives in one serialized_space JSON blob — GET, mutate, PATCH.
    Pass etag=None to skip conflict detection (safe for initial setup)."""
    body = {"serialized_space": json.dumps(config)}
    if etag:
        body["etag"] = etag
    return requests.patch(
        f"https://{host}/api/2.0/genie/spaces/{space_id}",
        headers=headers,
        json=body
    )

print("Helpers loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Add Benchmarks
# MAGIC
# MAGIC Benchmarks are an **evaluation tool only** — they do not teach Genie anything.
# MAGIC They measure whether Genie produces the SQL you expect.
# MAGIC Set them now, before you add any instructions, so you have a baseline score to compare against.
# MAGIC
# MAGIC **🖱️ UI — Configure tab navigation:**
# MAGIC 1. Open your Genie Space and click the **Benchmark** tab in the top navigation bar (alongside Chat | Monitor | Configure | Share)
# MAGIC 2. Click **+ Add benchmark**
# MAGIC 3. Type the question in the **Question** field
# MAGIC 4. Paste the expected SQL into the **Expected SQL** field
# MAGIC 5. Click **Save**
# MAGIC 6. Repeat for each benchmark, then click **Run benchmarks** to see your baseline score
# MAGIC
# MAGIC **⚡ Automated:** the cell below uploads all 4 benchmarks in one PATCH call.

# COMMAND ----------

BENCHMARKS = [
    {
        "title": "What was the average spot price in NSW1 yesterday?",
        "sql":   f"SELECT region_id, ROUND(AVG(rrp), 2) AS avg_price_mwh FROM {CATALOG}.{SCHEMA}.spot_prices WHERE region_id = 'NSW1' AND DATE(settlement_date) = CURRENT_DATE - 1 GROUP BY region_id"
    },
    {
        "title": "What was the fuel mix for dispatch in SA today?",
        "sql":   f"SELECT fuel_type, ROUND(SUM(dispatch_mw)/12, 0) AS total_mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals WHERE region_id = 'SA1' AND DATE(settlement_date) = CURRENT_DATE GROUP BY fuel_type ORDER BY total_mwh DESC"
    },
    {
        "title": "Were there any LOR events in the last fortnight?",
        "sql":   f"SELECT notice_type, issue_time, region_id, SUBSTRING(reason, 1, 200) AS summary FROM {CATALOG}.{SCHEMA}.market_notices WHERE notice_type LIKE 'LOR%' AND issue_time >= CURRENT_TIMESTAMP - INTERVAL 14 DAYS ORDER BY issue_time DESC"
    },
    {
        "title": "Which generators dispatched the most MW in QLD last week?",
        "sql":   f"SELECT d.duid, g.station_name, g.fuel_type, ROUND(SUM(d.dispatch_mw)/12, 1) AS total_mwh FROM {CATALOG}.{SCHEMA}.dispatch_intervals d LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid WHERE d.region_id = 'QLD1' AND d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS GROUP BY d.duid, g.station_name, g.fuel_type ORDER BY total_mwh DESC LIMIT 10"
    },
]

# API field path (verified 2026-06-03):
#   config["benchmarks"]["questions"] = [
#       {"id": <32-hex-uuid>, "question": [<str>], "answer": [{"format": "SQL", "content": [<sql>]}]}
#   ]
# Sort by id after generation — the API requires alphabetical order.
space, config = _get_serialized_space(HOST, SPACE_ID, HEADERS)

if "benchmarks" not in config:
    config["benchmarks"] = {}

questions = [
    {
        "id": _hex_uuid(),
        "question": [bm["title"]],
        "answer": [{"format": "SQL", "content": [bm["sql"]]}]
    }
    for bm in BENCHMARKS
]
questions.sort(key=lambda q: q["id"])
config["benchmarks"]["questions"] = questions

patch_resp = _patch_space(HOST, SPACE_ID, HEADERS, config)
if patch_resp.status_code in (200, 204):
    print(f"✅ {len(BENCHMARKS)} benchmarks written")
    print("\nNow go to the Benchmark tab → Run benchmarks and note your baseline score.")
else:
    print(f"❌ PATCH failed: {patch_resp.status_code}")
    print(patch_resp.text[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Add SQL Expressions
# MAGIC
# MAGIC A SQL Expression locks in a **single correct formula for a KPI**.
# MAGIC When Genie sees a question that matches the expression name or description,
# MAGIC it uses your formula exactly — no improvisation.
# MAGIC Use this for metrics where there is one right definition and variation is a bug.
# MAGIC
# MAGIC > **Example:** "renewable percentage" could be calculated as wind+solar divided by total,
# MAGIC > or as wind+solar+hydro divided by total, depending on who you ask.
# MAGIC > A SQL Expression ends that ambiguity for your space.
# MAGIC
# MAGIC **🖱️ UI — Configure → Instructions → SQL Expressions:**
# MAGIC 1. In your Genie Space click **Configure** (top navigation)
# MAGIC 2. In the left sidebar click **Instructions**
# MAGIC 3. Click the **SQL Expressions** sub-tab
# MAGIC 4. Click **+ Add**
# MAGIC 5. Fill in:
# MAGIC    - **Name** — short identifier (no spaces; used as the column alias in generated SQL)
# MAGIC    - **Description** — when should Genie use this expression? Be specific.
# MAGIC    - **Expression** — the SQL fragment (no SELECT keyword, no FROM — just the expression)
# MAGIC 6. Click **Save**
# MAGIC 7. Repeat for each expression below
# MAGIC
# MAGIC **⚡ Automated:** the cell below uploads both expressions in one PATCH call.

# COMMAND ----------

# API note (2026-06): SQL Expressions cannot be set via the serialized_space PATCH API
# — the key is not exposed. Enter these manually in the UI.
# Configure → Instructions → SQL Expressions → + Add

SQL_EXPRESSIONS = [
    {
        "name":        "avg_spot_price_mwh",
        "description": "Use this expression when the question asks for average spot price or average electricity price. Returns the average Regional Reference Price in $/MWh rounded to 2 decimal places.",
        "expression":  "ROUND(AVG(rrp), 2)"
    },
    {
        "name":        "renewable_pct",
        "description": "Use this expression when the question asks about renewable percentage, renewable share, or the proportion of clean energy in dispatch. Renewables are solar and wind only.",
        "expression":  "ROUND(SUM(CASE WHEN fuel_type IN ('solar', 'wind') THEN dispatch_mw ELSE 0 END) * 100.0 / NULLIF(SUM(dispatch_mw), 0), 1)"
    },
]

print("⚠️  SQL Expressions must be entered via the Genie UI — API not available.")
print("   Configure → Instructions → SQL Expressions → + Add")
print()
for e in SQL_EXPRESSIONS:
    print(f"{'='*55}")
    print(f"Name:        {e['name']}")
    print(f"Description: {e['description']}")
    print(f"Expression:  {e['expression']}")
    print()
print(f"ℹ️  {len(SQL_EXPRESSIONS)} expressions listed above — paste each into the UI.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Add Golden Queries
# MAGIC
# MAGIC A Golden Query shows Genie a **canonical SQL pattern for a whole question type**.
# MAGIC Unlike a benchmark (which only measures), a golden query actively teaches Genie
# MAGIC which JOINs, filters, and column names to use for that class of question.
# MAGIC The Description field is critical — it tells Genie when to apply the query.
# MAGIC
# MAGIC > **API note (2026-06):** The `serialized_space` PATCH endpoint does not expose
# MAGIC > a `sql_queries` field — it is silently rejected as "Unknown field".
# MAGIC > Golden queries must be entered manually in the UI.
# MAGIC > The cell below prints each query ready to copy-paste.
# MAGIC
# MAGIC **🖱️ UI — Configure → Instructions → SQL Queries:**
# MAGIC 1. In your Genie Space click **Configure** (top navigation)
# MAGIC 2. In the left sidebar click **Instructions**
# MAGIC 3. Click the **SQL Queries** sub-tab
# MAGIC 4. Click **+ Add**
# MAGIC 5. Fill in:
# MAGIC    - **Name** — short descriptive label
# MAGIC    - **Description** — triggers that tell Genie when to use this query (include synonyms)
# MAGIC    - **SQL** — paste the query from the cell output below
# MAGIC 6. Click **Save**
# MAGIC 7. Repeat for the second query

# COMMAND ----------

GOLDEN_QUERIES = [
    {
        "name": "Average spot price by region for a date",
        "description": "Use when asking about price levels, price averages, or electricity prices for a specific day or date range. The :date_period parameter accepts a date value.",
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
        "name": "Top generators by dispatch in a region",
        "description": "Use when asking which generators dispatched the most, top generators, generation output, or MW dispatched by station. :region is the NEM region code (e.g. QLD1, SA1, VIC1).",
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
]

print("Golden queries must be entered manually via Configure → Instructions → SQL Queries → + Add")
print()
for i, gq in enumerate(GOLDEN_QUERIES, 1):
    print(f"{'='*65}")
    print(f"Query {i} of {len(GOLDEN_QUERIES)}")
    print(f"Name:        {gq['name']}")
    print(f"Description: {gq['description']}")
    print(f"SQL:\n{gq['query']}")
    print()
print(f"Paste each block into the UI — {len(GOLDEN_QUERIES)} queries total.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Text Instructions — last resort only
# MAGIC
# MAGIC Text Instructions are **universal rules that apply to every query** in the space.
# MAGIC Use them only for things that SQL cannot express — formatting preferences,
# MAGIC behavioural rules, or domain terminology that must hold regardless of question type.
# MAGIC
# MAGIC **Decision rule — reach for text instructions only when:**
# MAGIC - A SQL Expression cannot encode it (not a formula)
# MAGIC - A Golden Query description cannot encode it (not question-type-specific)
# MAGIC - It genuinely applies to every query, not just some
# MAGIC
# MAGIC **🖱️ UI — Configure → Instructions → Text:**
# MAGIC 1. In your Genie Space click **Configure** (top navigation)
# MAGIC 2. In the left sidebar click **Instructions**
# MAGIC 3. Click the **Text** sub-tab
# MAGIC 4. Type or paste your instructions into the text field (no + Add button — it is a single text area)
# MAGIC 5. Click **Save**
# MAGIC
# MAGIC **⚡ Automated:** the cell below uploads all 4 instructions in one PATCH call.

# COMMAND ----------

TEXT_INSTRUCTIONS = [
    "Always express prices in $/MWh with 2 decimal places.",
    "Region codes must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix. Never use NSW, VIC, QLD, SA, or TAS without the suffix.",
    "LOR1 = first reserve watch warning. LOR2 = reserve shortfall threatened. LOR3 = imminent critical shortage. Always use LIKE 'LOR%' to match all LOR types.",
    "When asked about 'today' with no data available, say so and suggest yesterday instead.",
]

# API field path (verified 2026-06-03):
#   config["instructions"]["text_instructions"] = [{"content": ["line1\n", "line2\n", "last line"]}]
# Rules:
#   - Nested inside config["instructions"], not at root
#   - At most ONE item in the list (proto constraint)
#   - Each item is {"content": [list of strings]}
#   - Trailing "\n" on all lines except the last so they display as separate bullets in the UI
space, config = _get_serialized_space(HOST, SPACE_ID, HEADERS)

if "instructions" not in config:
    config["instructions"] = {}

content_lines = [f"{instr}\n" for instr in TEXT_INSTRUCTIONS[:-1]] + [TEXT_INSTRUCTIONS[-1]]
config["instructions"]["text_instructions"] = [{"content": content_lines}]

patch_resp = _patch_space(HOST, SPACE_ID, HEADERS, config)
if patch_resp.status_code in (200, 204):
    print(f"✅ {len(TEXT_INSTRUCTIONS)} text instructions written")
else:
    print(f"❌ PATCH failed: {patch_resp.status_code}")
    print(patch_resp.text[:400])

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Inspect — See What SQL Genie Actually Ran
# MAGIC
# MAGIC Inspect is a **transparency feature**, not a self-auditing loop.
# MAGIC When you click the magnifying glass icon on a response, you see the SQL Genie generated
# MAGIC and executed to produce that answer — the primary query, shown verbatim.
# MAGIC This is how you verify that your instructions are having the intended effect.
# MAGIC
# MAGIC Genie does not automatically run a second "verification" query to cross-check its own answer.
# MAGIC You are the verifier — Inspect gives you the raw SQL so you can read it yourself.
# MAGIC
# MAGIC **🖱️ UI — how to open Inspect:**
# MAGIC 1. Go to the **Chat** tab in your Genie Space
# MAGIC 2. Ask any question — for example: *"What was the average spot price in NSW1 yesterday?"*
# MAGIC 3. Wait for the response to appear
# MAGIC 4. Look for the **magnifying glass icon** (🔍) in the bottom-right corner of the response card
# MAGIC 5. Click it — a panel opens showing:
# MAGIC    - The **SQL Genie ran** to produce this answer
# MAGIC    - The result set returned by that SQL
# MAGIC
# MAGIC **How to use Inspect for debugging:**
# MAGIC
# MAGIC | What you see in the SQL | What it tells you |
# MAGIC |---|---|
# MAGIC | SQL matches your golden query pattern | Genie is applying your golden query correctly |
# MAGIC | SQL uses your SQL Expression formula verbatim | The expression fired — description matched the question |
# MAGIC | SQL ignores your SQL Expression (improvised a different formula) | The expression description may not match how users phrase the question — refine it |
# MAGIC | SQL has the wrong filter (wrong region, wrong date) | Genie misread the question — try rephrasing or adding a text instruction |
# MAGIC | No SQL appears / Inspect unavailable | The response was a clarification, not a data query — ask a data question |
# MAGIC
# MAGIC > **Try it:** ask *"What is the renewable percentage in SA today?"* — then Inspect the result.
# MAGIC > Read the SQL and check whether your `renewable_pct` expression appears in it.
# MAGIC > If it does not, the description on the expression needs to be more specific or use different trigger words.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 02 Checkpoint
# MAGIC
# MAGIC | Step | Tool | Method | Status |
# MAGIC |---|---|---|---|
# MAGIC | 1 | 4 benchmarks | Automated | Run via Benchmark tab → Run benchmarks |
# MAGIC | 2 | 2 SQL Expressions | Automated | Verify in Configure → Instructions → SQL Expressions |
# MAGIC | 3 | 2 golden queries | UI only (API does not expose `sql_queries`) | Pasted from Step 3 output |
# MAGIC | 4 | 4 text instructions | Automated | Verify in Configure → Instructions → Text |
# MAGIC | 5 | Inspect | UI | Opened Inspect on at least one response; read the generated SQL |
# MAGIC
# MAGIC **Now re-run your benchmarks:** Benchmark tab → Run benchmarks.
# MAGIC Compare your new score to the baseline from Step 1.
# MAGIC Each addition should move the score — if it does not, the description or instruction needs refinement.
# MAGIC
# MAGIC **API field reference:**
# MAGIC | Config section | Correct field path |
# MAGIC |---|---|
# MAGIC | Benchmarks | `config["benchmarks"]["questions"]` — each item: `{"id":<hex-uuid>, "question":[...], "answer":[{"format":"SQL","content":[...]}]}` |
# MAGIC | SQL Expressions | `config["instructions"]["sql_expressions"]` — each item: `{"name":..., "description":..., "expression":...}` |
# MAGIC | Golden Queries | Not available via API — UI only (Configure → Instructions → SQL Queries) |
# MAGIC | Text Instructions | `config["instructions"]["text_instructions"]` — exactly one item: `{"content":["line1\n","line2"]}` |
# MAGIC
# MAGIC **→ Next: Lab 03 — Monitor, Iterate & Annotate**
