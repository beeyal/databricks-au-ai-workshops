# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 44px; border-radius: 12px; margin-bottom: 0;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', Arial, sans-serif; font-size: 2.4em; margin: 0 0 10px 0; font-weight: 700;">
# MAGIC     Lab 01: Designing and Setting Up Your Genie Space
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.90); font-size: 1.15em; margin: 0 0 6px 0; font-family: 'DM Sans', Arial, sans-serif;">
# MAGIC     Session 2: Building the Best Genie Space
# MAGIC   </p>
# MAGIC </div>
# MAGIC <div style="background: #f7f8fa; border-left: 4px solid #FF3621; padding: 18px 24px; border-radius: 0 8px 8px 0; margin-top: 0; font-family: 'DM Sans', Arial, sans-serif;">
# MAGIC   <table style="width:100%; border-collapse: collapse; font-size: 1em;">
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 16px 4px 0; font-weight: 600; color: #1B3A6B; white-space: nowrap;">Duration</td>
# MAGIC       <td style="padding: 4px 0;">40 minutes</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 16px 4px 0; font-weight: 600; color: #1B3A6B; white-space: nowrap;">Role</td>
# MAGIC       <td style="padding: 4px 0;">Data Engineer</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 16px 4px 0; font-weight: 600; color: #1B3A6B; white-space: nowrap;">Prerequisite</td>
# MAGIC       <td style="padding: 4px 0;">AEMO tables loaded in <code>workshop_au.aemo</code></td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 4px 16px 4px 0; font-weight: 600; color: #1B3A6B; white-space: nowrap;">Approach</td>
# MAGIC       <td style="padding: 4px 0;">UI-first with validation code cells — do everything in the browser, use code only to verify</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #fff8e1; border-left: 4px solid #FFA500; padding: 16px 22px; border-radius: 0 8px 8px 0; font-family: 'DM Sans', Arial, sans-serif; margin: 4px 0 12px 0;">
# MAGIC   <h3 style="margin: 0 0 8px 0; color: #7a4f00; font-size: 1.05em;">🔑  The Critical Architecture Insight — Read This First</h3>
# MAGIC   <p style="margin: 0 0 10px 0;">
# MAGIC     <strong>Genie does not always generate SQL from scratch.</strong>
# MAGIC     When a user asks a question, Genie's decision process is:
# MAGIC   </p>
# MAGIC   <ol style="margin: 0 0 10px 24px; padding: 0;">
# MAGIC     <li style="margin-bottom: 6px;"><strong>Does the question match a Golden Query exactly?</strong>
# MAGIC       If yes → the pre-written SQL runs directly. Answer is labelled <em>Trusted</em>. Deterministic.</li>
# MAGIC     <li style="margin-bottom: 6px;"><strong>No match found?</strong>
# MAGIC       Genie generates SQL from scratch using your instructions, UC metadata, and SQL Expressions as context.</li>
# MAGIC   </ol>
# MAGIC   <p style="margin: 0; font-weight: 600; color: #7a4f00;">
# MAGIC     This means golden queries are not just examples — they are routing rules.
# MAGIC     A golden query for "average spot price yesterday" guarantees that exact question always returns the same, audited SQL.
# MAGIC   </p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #e8f0fe; border-left: 4px solid #1B3A6B; padding: 16px 22px; border-radius: 0 8px 8px 0; font-family: 'DM Sans', Arial, sans-serif; margin: 4px 0 12px 0;">
# MAGIC   <h3 style="margin: 0 0 10px 0; color: #1B3A6B; font-size: 1.05em;">The Instruction Hierarchy (Slides 79–82)</h3>
# MAGIC   <p style="margin: 0 0 10px 0;">Genie uses four types of guidance. Apply them in this order — each layer handles what the previous one cannot:</p>
# MAGIC   <table style="width: 100%; border-collapse: collapse; font-size: 0.97em;">
# MAGIC     <thead>
# MAGIC       <tr style="background: #1B3A6B; color: white;">
# MAGIC         <th style="padding: 8px 12px; text-align: left;">Priority</th>
# MAGIC         <th style="padding: 8px 12px; text-align: left;">Layer</th>
# MAGIC         <th style="padding: 8px 12px; text-align: left;">Best for</th>
# MAGIC         <th style="padding: 8px 12px; text-align: left;">Where to set</th>
# MAGIC       </tr>
# MAGIC     </thead>
# MAGIC     <tbody>
# MAGIC       <tr style="background: #f0f4ff;">
# MAGIC         <td style="padding: 8px 12px; font-weight: 700; color: #1B3A6B;">1 — Foundation</td>
# MAGIC         <td style="padding: 8px 12px;"><strong>UC Metadata</strong></td>
# MAGIC         <td style="padding: 8px 12px;">Table/column descriptions, units, valid values, PK/FK relationships</td>
# MAGIC         <td style="padding: 8px 12px;">Catalog Explorer → Edit column description</td>
# MAGIC       </tr>
# MAGIC       <tr>
# MAGIC         <td style="padding: 8px 12px; font-weight: 700; color: #1B3A6B;">2 — Metrics</td>
# MAGIC         <td style="padding: 8px 12px;"><strong>SQL Expressions</strong></td>
# MAGIC         <td style="padding: 8px 12px;">Reusable KPIs, calculated fields, filter shortcuts, named measures</td>
# MAGIC         <td style="padding: 8px 12px;">Genie Space → Configure → SQL Expressions tab</td>
# MAGIC       </tr>
# MAGIC       <tr style="background: #f0f4ff;">
# MAGIC         <td style="padding: 8px 12px; font-weight: 700; color: #1B3A6B;">3 — Patterns</td>
# MAGIC         <td style="padding: 8px 12px;"><strong>Golden Queries</strong></td>
# MAGIC         <td style="padding: 8px 12px;">Complex multi-table joins, standard reports, auditable business queries</td>
# MAGIC         <td style="padding: 8px 12px;">Genie Space → Configure → Example SQL tab</td>
# MAGIC       </tr>
# MAGIC       <tr>
# MAGIC         <td style="padding: 8px 12px; font-weight: 700; color: #1B3A6B;">4 — Rules</td>
# MAGIC         <td style="padding: 8px 12px;"><strong>Text Instructions</strong></td>
# MAGIC         <td style="padding: 8px 12px;">Domain acronyms, business rules that cannot be expressed in SQL, tone/format preferences</td>
# MAGIC         <td style="padding: 8px 12px;">Genie Space → Configure → Instructions tab</td>
# MAGIC       </tr>
# MAGIC     </tbody>
# MAGIC   </table>
# MAGIC   <p style="margin: 10px 0 0 0; font-size: 0.93em; color: #444;">
# MAGIC     <strong>Rule of thumb:</strong> If it can be expressed in SQL, express it in SQL — not in text. Text instructions are for what SQL cannot capture.
# MAGIC   </p>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0: Before You Build — Design Principles  *(10 min, all UI)*

# COMMAND ----------

# MAGIC %md
# MAGIC ### The 5-Table Rule
# MAGIC
# MAGIC ```
# MAGIC Navigate: Left sidebar → Genie icon → click "+ New Space" (top-right corner)
# MAGIC           (Do NOT fill anything in yet — just explore the interface)
# MAGIC
# MAGIC ┌─────────────────────────────────────────────────────────────────────────┐
# MAGIC │  ⚡ Design rule: A Genie Space should answer questions for              │
# MAGIC │     ONE topic for ONE audience.  Not everything for everyone.           │
# MAGIC │                                                                         │
# MAGIC │  ✅ Good: "AEMO Market Operations Analytics"                            │
# MAGIC │      Tables:   spot_prices, dispatch_intervals, market_notices          │
# MAGIC │      Audience: Market operations team                                   │
# MAGIC │      Scope:    NEM prices and dispatch events                           │
# MAGIC │                                                                         │
# MAGIC │  ✅ Good: "NEM Settlements & Finance"                                   │
# MAGIC │      Tables:   settlement_amounts, generator_registration               │
# MAGIC │      Audience: Finance team                                             │
# MAGIC │      Scope:    Participant settlement amounts                           │
# MAGIC │                                                                         │
# MAGIC │  ❌ Anti-pattern: One "super-Genie" with all 6 AEMO tables              │
# MAGIC │      Result:  Ambiguous queries, conflicting instructions,              │
# MAGIC │               poor accuracy, confused users                             │
# MAGIC └─────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Why does too many tables hurt accuracy?
# MAGIC  → More tables = more ambiguity when the user says "dispatch data"
# MAGIC  → Instructions written for finance users conflict with operations users
# MAGIC  → Golden queries that join settlement tables pollute NEM price answers
# MAGIC  → Genie cannot specialise — it hedges every answer
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Topic Selection Exercise *(UI only — no code)*
# MAGIC
# MAGIC **For this workshop you will build:** `"AEMO NEM Operations"`
# MAGIC - **Tables:** spot_prices, dispatch_intervals, market_notices
# MAGIC - **Audience:** Market operations team
# MAGIC - **Scope:** NEM spot prices, dispatch events, and operational alerts
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Before you create any space, gather 10–15 representative questions your users actually ask.**
# MAGIC Getting these questions right drives everything else: your golden queries, your SQL Expressions, and your benchmark tests.
# MAGIC
# MAGIC Here are the 10 questions we will design around in this workshop:
# MAGIC
# MAGIC | # | Question | Why it matters |
# MAGIC |---|----------|----------------|
# MAGIC | 1 | What was the average spot price in VIC1 yesterday? | Daily price review — most common ask |
# MAGIC | 2 | Which generator had the highest dispatch in QLD last week? | Generator performance tracking |
# MAGIC | 3 | Were there any LOR events in the last 14 days? | Operational risk monitoring |
# MAGIC | 4 | Compare spot prices across all regions for last month | Regional benchmarking |
# MAGIC | 5 | Which fuel types dispatched most during the afternoon peak? | Generation mix analysis |
# MAGIC | 6 | Show me price spikes above $500/MWh this month | Extreme event detection |
# MAGIC | 7 | What was the total MWh dispatched by solar in SA last week? | Renewable penetration |
# MAGIC | 8 | How many market notices were issued this week? | Operations summary |
# MAGIC | 9 | What is the average dispatch for ERARING in the last 30 days? | Station-level tracking |
# MAGIC | 10 | Which regions had prices above $300/MWh yesterday? | Spike region identification |
# MAGIC
# MAGIC > **Write these down** — we will turn questions 1, 2, 3, 4, and 6 into golden queries in Lab 02.
# MAGIC > The rest drive SQL Expressions and benchmark tests.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1: UC Metadata — Your Foundation  *(10 min)*
# MAGIC
# MAGIC UC metadata is the highest-leverage improvement you can make to a Genie Space.
# MAGIC It costs zero runtime tokens — Genie reads it once during configuration, not on every question.
# MAGIC Every other layer (SQL Expressions, golden queries, text instructions) inherits its accuracy from the quality of your column descriptions.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1.1 — Add a table-level description
# MAGIC
# MAGIC ```
# MAGIC Navigate:
# MAGIC   Left sidebar → Catalog icon
# MAGIC   → workshop_au (expand)
# MAGIC   → aemo (expand)
# MAGIC   → spot_prices
# MAGIC   → click the "Overview" tab (top of the right panel)
# MAGIC   → click the pencil icon next to "Description"
# MAGIC
# MAGIC Type this description and click Save:
# MAGIC ┌─────────────────────────────────────────────────────────────────────────┐
# MAGIC │  NEM 30-minute trading interval spot prices for all five regions.       │
# MAGIC │  Key column: rrp = Regional Reference Price in $/MWh.                  │
# MAGIC │  Regions: NSW1, VIC1, QLD1, SA1, TAS1 (always include the '1' suffix). │
# MAGIC │  One row per region per 30-minute trading interval.                     │
# MAGIC │  settlement_date is the interval end time in AEST/AEDT.                │
# MAGIC └─────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Why: Genie uses this to understand what the table is before choosing columns.
# MAGIC      Without it, Genie may confuse spot_prices with settlement_amounts.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1.2 — Add column-level descriptions for spot_prices
# MAGIC
# MAGIC ```
# MAGIC Navigate:
# MAGIC   Catalog → workshop_au → aemo → spot_prices
# MAGIC   → click the "Columns" tab
# MAGIC   → click the pencil icon next to each column listed below
# MAGIC
# MAGIC ┌──────────────────┬──────────────────────────────────────────────────────────────────┐
# MAGIC │ Column           │ Description to enter                                             │
# MAGIC ├──────────────────┼──────────────────────────────────────────────────────────────────┤
# MAGIC │ rrp              │ Regional Reference Price in $/MWh. Normal range $50–200.         │
# MAGIC │                  │ Market price cap = $15,300. Price floor = -$1,000.               │
# MAGIC │                  │ Negative prices indicate renewable oversupply (curtailment risk).│
# MAGIC │                  │ A price > $300/MWh is a spike; > $5,000/MWh is extreme.         │
# MAGIC ├──────────────────┼──────────────────────────────────────────────────────────────────┤
# MAGIC │ region_id        │ NEM region identifier. Must be NSW1, VIC1, QLD1, SA1, or TAS1   │
# MAGIC │                  │ — always with the '1' suffix. Never use NSW, VIC, QLD etc.       │
# MAGIC │                  │ NSW1=New South Wales, VIC1=Victoria, QLD1=Queensland,            │
# MAGIC │                  │ SA1=South Australia, TAS1=Tasmania.                              │
# MAGIC ├──────────────────┼──────────────────────────────────────────────────────────────────┤
# MAGIC │ settlement_date  │ Trading interval end time. 30-minute intervals.                  │
# MAGIC │                  │ AEST/AEDT timezone. Use DATE(settlement_date) to filter by day.  │
# MAGIC │                  │ Do not convert to UTC — all reporting is in local Australian time.│
# MAGIC └──────────────────┴──────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Tip: Save each column before moving to the next.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1.3 — Add column descriptions for market_notices
# MAGIC
# MAGIC ```
# MAGIC Navigate:
# MAGIC   Catalog → workshop_au → aemo → market_notices → Columns tab
# MAGIC
# MAGIC ┌──────────────────┬──────────────────────────────────────────────────────────────────┐
# MAGIC │ Column           │ Description to enter                                             │
# MAGIC ├──────────────────┼──────────────────────────────────────────────────────────────────┤
# MAGIC │ notice_type      │ Category of AEMO market notice.                                  │
# MAGIC │                  │ LOR1 = Lack of Reserve Level 1 (watch).                         │
# MAGIC │                  │ LOR2 = Lack of Reserve Level 2 (manual shedding possible).      │
# MAGIC │                  │ LOR3 = Lack of Reserve Level 3 (shedding imminent/occurring).   │
# MAGIC │                  │ MT_PASA = Medium-term reserve assessment.                        │
# MAGIC │                  │ RECLASSIFY = Network constraint reclassification.                │
# MAGIC ├──────────────────┼──────────────────────────────────────────────────────────────────┤
# MAGIC │ issue_time       │ Timestamp when AEMO issued the notice. AEST/AEDT.               │
# MAGIC │                  │ Filter this column for "recent notices" queries.                 │
# MAGIC ├──────────────────┼──────────────────────────────────────────────────────────────────┤
# MAGIC │ reason           │ Full text of the AEMO notice. May be long. Use LEFT(reason, 250) │
# MAGIC │                  │ in queries to keep results readable.                             │
# MAGIC └──────────────────┴──────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Validation: Confirm column comments are set before proceeding

# COMMAND ----------

# Verify column comments are set for spot_prices
# If any show "NO COMMENT" go back to the UI and add the description before continuing

result = spark.sql("""
    SELECT column_name, comment
    FROM system.information_schema.columns
    WHERE table_catalog = 'workshop_au'
      AND table_schema   = 'aemo'
      AND table_name     = 'spot_prices'
      AND column_name IN ('rrp', 'region_id', 'settlement_date')
    ORDER BY column_name
""").collect()

all_set = True
print("spot_prices column descriptions:")
print("─" * 70)
for row in result:
    has_comment = bool(row['comment'])
    status = "✅" if has_comment else "❌ MISSING"
    preview = row['comment'][:75] if has_comment else "NO COMMENT — go back to Catalog and add it"
    print(f"  {status}  {row['column_name']:<20} {preview}")
    if not has_comment:
        all_set = False

print("─" * 70)
if all_set:
    print("\n✅  All spot_prices column descriptions are set. Proceed to Section 2.")
else:
    print("\n⚠️   Some descriptions are missing. Return to Catalog Explorer and add them before continuing.")
    print("     The quality of your Genie Space depends on this foundation.")

# COMMAND ----------

# Verify market_notices column descriptions
result_mn = spark.sql("""
    SELECT column_name, comment
    FROM system.information_schema.columns
    WHERE table_catalog = 'workshop_au'
      AND table_schema   = 'aemo'
      AND table_name     = 'market_notices'
      AND column_name IN ('notice_type', 'issue_time', 'reason')
    ORDER BY column_name
""").collect()

print("market_notices column descriptions:")
print("─" * 70)
mn_all_set = True
for row in result_mn:
    has_comment = bool(row['comment'])
    status = "✅" if has_comment else "❌ MISSING"
    preview = row['comment'][:75] if has_comment else "NO COMMENT — go back to Catalog and add it"
    print(f"  {status}  {row['column_name']:<20} {preview}")
    if not has_comment:
        mn_all_set = False

print("─" * 70)
if mn_all_set:
    print("\n✅  market_notices column descriptions are set.")
else:
    print("\n⚠️   market_notices column descriptions are missing. Add them before continuing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2: Create the Space — UI Walkthrough  *(10 min)*

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2.1 — Open the New Space dialog
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────────────────────┐
# MAGIC │  Left sidebar → Genie icon (sparkle ✨)                                │
# MAGIC │  → click "+ New Space"  (top-right corner of the Genie home page)      │
# MAGIC │                                                                         │
# MAGIC │  You land on the "New Genie Space" form:                               │
# MAGIC │                                                                         │
# MAGIC │  ┌───────────────────────────────────────────────────────────────┐     │
# MAGIC │  │  Title         [ AEMO NEM Operations                        ] │     │
# MAGIC │  │                                                               │     │
# MAGIC │  │  Description   [ Natural language access to NEM spot prices, ] │     │
# MAGIC │  │                [ dispatch data, and market notices.           ] │     │
# MAGIC │  │                [ Ask questions in plain English — no SQL      ] │     │
# MAGIC │  │                [ needed.                                      ] │     │
# MAGIC │  │                [ Best for: Market Operations team             ] │     │
# MAGIC │  │                [ Data: Last 6 months                         ] │     │
# MAGIC │  │                                                               │     │
# MAGIC │  │  Warehouse     [ select your serverless warehouse         ▼ ] │     │
# MAGIC │  │                                                               │     │
# MAGIC │  │                              [ Create ]                       │     │
# MAGIC │  └───────────────────────────────────────────────────────────────┘     │
# MAGIC └─────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Fill in:
# MAGIC   Title:       AEMO NEM Operations
# MAGIC   Description: Natural language access to NEM spot prices, dispatch data,
# MAGIC                and market notices. Ask questions in plain English — no SQL
# MAGIC                needed. Best for: Market Operations team | Data: Last 6 months
# MAGIC   Warehouse:   select your serverless warehouse from the dropdown
# MAGIC
# MAGIC → Click "Create"
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2.2 — Add tables to the space
# MAGIC
# MAGIC ```
# MAGIC After clicking Create, you land on the Configure tab of your new space.
# MAGIC
# MAGIC ┌──────────────────────────────────────────────────────────────────────────┐
# MAGIC │  Configure tab layout:                                                   │
# MAGIC │                                                                          │
# MAGIC │  ┌─────────────────────┐  ┌──────────────────────────────────────────┐  │
# MAGIC │  │  DATA               │  │  Instructions  │  SQL Expressions  │ ...  │  │
# MAGIC │  │  ─────────────      │  └──────────────────────────────────────────┘  │
# MAGIC │  │  + Add tables  ←───┼── click this button                            │
# MAGIC │  │                     │                                                 │
# MAGIC │  │  Tables added:      │                                                 │
# MAGIC │  │  (none yet)         │                                                 │
# MAGIC │  └─────────────────────┘                                                 │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Click "+ Add tables" (or "Add" in the data section)
# MAGIC
# MAGIC In the table picker dialog, navigate to:
# MAGIC   workshop_au → aemo
# MAGIC
# MAGIC Check these three tables:
# MAGIC   ✓  spot_prices
# MAGIC   ✓  dispatch_intervals
# MAGIC   ✓  market_notices
# MAGIC
# MAGIC → Click "Confirm"
# MAGIC
# MAGIC Note: We are NOT adding generator_registration and settlement_amounts
# MAGIC       to this space — those belong in the "NEM Settlements & Finance" space.
# MAGIC       This is the 5-table rule in action.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2.3 — Review the Suggested Queries dialog
# MAGIC
# MAGIC ```
# MAGIC After adding tables, a "Suggested Queries" dialog appears automatically.
# MAGIC
# MAGIC ┌──────────────────────────────────────────────────────────────────────────┐
# MAGIC │  Suggested Queries                                                       │
# MAGIC │  ─────────────────────────────────────────────────────────────────────  │
# MAGIC │  Genie searched your workspace for existing queries that reference       │
# MAGIC │  your tables. These could become golden queries.                         │
# MAGIC │                                                                          │
# MAGIC │  [ ] Average spot price by region                    [Preview] [Accept]  │
# MAGIC │  [ ] Count of LOR notices by type                    [Preview] [Accept]  │
# MAGIC │  [ ] Generator dispatch by fuel type last 7 days     [Preview] [Accept]  │
# MAGIC │  ...                                                                     │
# MAGIC │                                                                          │
# MAGIC │                                              [ Done ]                    │
# MAGIC └──────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC How to evaluate each suggestion:
# MAGIC   ✅ Accept:  The query looks correct, uses your column names, joins sensibly
# MAGIC   ❌ Reject:  The query uses wrong column names, has incorrect filters,
# MAGIC               or is too specific to a one-off analysis
# MAGIC
# MAGIC → Click "Done" when finished
# MAGIC   (It is fine to accept none — we will add golden queries in Lab 02)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2.4 — Find and save your Space ID

# COMMAND ----------

# MAGIC %md
# MAGIC ```
# MAGIC After creating the space, look at your browser URL bar.
# MAGIC
# MAGIC URL pattern:
# MAGIC   https://<your-workspace>.azuredatabricks.net/genie/spaces/01f0abc123def456
# MAGIC                                                              ↑
# MAGIC                                              This is your SPACE_ID
# MAGIC                                              Copy it now.
# MAGIC
# MAGIC The Space ID is a hex string, typically 16-20 characters.
# MAGIC Example:  01f0abc123def456  (yours will be different)
# MAGIC ```

# COMMAND ----------

# Paste your Space ID below — this widget persists across the lab session
dbutils.widgets.text("genie_space_id", "", "Genie Space ID (from URL)")

SPACE_ID = dbutils.widgets.get("genie_space_id")

if not SPACE_ID:
    print("⚠️   Please enter your Genie Space ID in the widget above.")
    print("     Find it in the browser URL bar after creating the space:")
    print("     https://<workspace>.azuredatabricks.net/genie/spaces/<SPACE_ID>")
    print("\n     After entering it, re-run this cell.")
else:
    workspace_url = spark.conf.get("spark.databricks.workspaceUrl")
    print(f"✅  Space ID saved: {SPACE_ID}")
    print(f"    Direct URL:  https://{workspace_url}/genie/spaces/{SPACE_ID}")

# COMMAND ----------

# Quick smoke test — confirm the API can reach the space
import requests

if SPACE_ID:
    HOST    = spark.conf.get("spark.databricks.workspaceUrl")
    TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

    response = requests.get(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
        headers=HEADERS
    )

    if response.status_code == 200:
        space = response.json()
        print("✅  Space is reachable via API")
        print(f"    Title:    {space.get('title', 'Unknown')}")
        print(f"    Datasets: {len(space.get('datasets', []))} table(s) added")
        datasets = space.get('datasets', [])
        for ds in datasets:
            print(f"              • {ds.get('table_name', ds)}")
    else:
        print(f"❌  Error: HTTP {response.status_code}")
        print(f"    Response: {response.text[:300]}")
        print(f"\n    Check that SPACE_ID is correct and the warehouse is running.")
else:
    print("⚠️   SPACE_ID is not set. Enter it in the widget above and re-run both cells.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3: Curate Column Metadata in the Space  *(10 min)*
# MAGIC
# MAGIC UC column descriptions (Section 1) apply globally across all of Databricks.
# MAGIC The Genie Space Configure tab lets you add *space-specific* refinements that only
# MAGIC apply when this space answers questions — synonyms, entity matching, and visibility.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3.1 — Add column synonyms
# MAGIC
# MAGIC ```
# MAGIC Navigate:
# MAGIC   Your Genie Space → Configure tab
# MAGIC   → In the DATA section on the left, click "spot_prices"
# MAGIC   → The column list for spot_prices appears on the right
# MAGIC   → Click the "Synonyms" tab (below the column list)
# MAGIC
# MAGIC For each column below, click the column name and enter synonyms:
# MAGIC
# MAGIC ┌───────────────────┬──────────────────────────────────────────────────────┐
# MAGIC │ Column            │ Synonyms to add (comma-separated or one per field)   │
# MAGIC ├───────────────────┼──────────────────────────────────────────────────────┤
# MAGIC │ region_id         │ region, NEM region, state, zone, area                │
# MAGIC ├───────────────────┼──────────────────────────────────────────────────────┤
# MAGIC │ rrp               │ price, spot price, market price, $/MWh, energy price │
# MAGIC ├───────────────────┼──────────────────────────────────────────────────────┤
# MAGIC │ settlement_date   │ date, time, interval time, trading interval, period   │
# MAGIC └───────────────────┴──────────────────────────────────────────────────────┘
# MAGIC
# MAGIC Why synonyms matter:
# MAGIC   A user asks: "What was the price in NSW yesterday?"
# MAGIC   Without synonyms → Genie may not know "price" = rrp column
# MAGIC   With synonyms    → Genie maps "price" → rrp immediately, no guessing
# MAGIC
# MAGIC Repeat for market_notices table:
# MAGIC ┌───────────────────┬──────────────────────────────────────────────────────┐
# MAGIC │ Column            │ Synonyms to add                                      │
# MAGIC ├───────────────────┼──────────────────────────────────────────────────────┤
# MAGIC │ notice_type       │ type, notice category, event type, alert type        │
# MAGIC ├───────────────────┼──────────────────────────────────────────────────────┤
# MAGIC │ issue_time        │ issued, date, when, notice date, time issued         │
# MAGIC └───────────────────┴──────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3.2 — Enable Entity Matching for region_id
# MAGIC
# MAGIC ```
# MAGIC Entity matching lets Genie understand user shorthand and map it to exact values.
# MAGIC Without it, a user typing "NSW" or "New South Wales" may confuse Genie.
# MAGIC
# MAGIC Navigate:
# MAGIC   Genie Space → Configure → DATA → spot_prices
# MAGIC   → Click the "region_id" column
# MAGIC   → Scroll down to "Entity Matching"
# MAGIC   → Toggle it ON
# MAGIC   → Click "Refresh prompt matching"
# MAGIC
# MAGIC After enabling, Genie scans the actual values in region_id and learns:
# MAGIC   "NSW"           → NSW1
# MAGIC   "New South Wales" → NSW1
# MAGIC   "Victoria"      → VIC1
# MAGIC   "QLD"           → QLD1
# MAGIC   "South Australia" → SA1
# MAGIC   "Tasmania"      → TAS1
# MAGIC
# MAGIC Test it: In the space chat, type "What was the price in New South Wales yesterday?"
# MAGIC Expected: Genie writes  WHERE region_id = 'NSW1'  (not 'New South Wales')
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3.3 — Hide low-value columns
# MAGIC
# MAGIC ```
# MAGIC Some columns exist for internal processing or advanced FCAS analysis that
# MAGIC most market operations users never ask about. Hiding them reduces ambiguity
# MAGIC and speeds up Genie's column selection.
# MAGIC
# MAGIC Navigate:
# MAGIC   Genie Space → Configure → DATA → spot_prices
# MAGIC   → Find these columns in the list:
# MAGIC
# MAGIC ┌────────────────────────┬──────────────────────────────────────────────────┐
# MAGIC │ Column                 │ Action                                           │
# MAGIC ├────────────────────────┼──────────────────────────────────────────────────┤
# MAGIC │ raise_6sec             │ Click the eye icon → Hide                        │
# MAGIC │ raise_60sec            │ Click the eye icon → Hide                        │
# MAGIC │ raise_5min             │ Click the eye icon → Hide                        │
# MAGIC │ lower_6sec             │ Click the eye icon → Hide                        │
# MAGIC │ lower_60sec            │ Click the eye icon → Hide                        │
# MAGIC │ lower_5min             │ Click the eye icon → Hide                        │
# MAGIC └────────────────────────┴──────────────────────────────────────────────────┘
# MAGIC
# MAGIC When to NOT hide: If your operations team does ask about FCAS (frequency
# MAGIC control ancillary services), keep these columns visible. Only hide what
# MAGIC your audience will never query.
# MAGIC
# MAGIC → Click "Save changes" after hiding columns
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### Validation: Test the space basics with an API smoke test

# COMMAND ----------

# Full smoke test — send a real question and verify the space responds
import time

if not SPACE_ID:
    print("⚠️   SPACE_ID not set. Enter it in the widget in Section 2 and re-run.")
else:
    HOST    = spark.conf.get("spark.databricks.workspaceUrl")
    TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

    TEST_QUESTION = "What was the average spot price in VIC1 yesterday?"

    print(f"Sending test question: '{TEST_QUESTION}'")
    print("Waiting for response (this may take 15–30 seconds)...\n")

    # Start a conversation
    resp = requests.post(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/start-conversation",
        headers=HEADERS,
        json={"content": TEST_QUESTION}
    )

    if resp.status_code != 200:
        print(f"❌  Failed to start conversation: HTTP {resp.status_code}")
        print(f"    {resp.text[:300]}")
    else:
        data    = resp.json()
        conv_id = data.get("conversation_id")
        msg_id  = data.get("message_id")

        # Poll for completion
        status = "PENDING"
        for attempt in range(30):
            time.sleep(3)
            poll = requests.get(
                f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conv_id}/messages/{msg_id}",
                headers=HEADERS
            )
            if poll.status_code == 200:
                msg_data = poll.json()
                status   = msg_data.get("status", "PENDING")
                if status in ("COMPLETED", "FAILED", "CANCELLED"):
                    break
            if attempt % 5 == 4:
                print(f"  Still waiting... ({(attempt+1)*3}s elapsed)")

        print(f"\nStatus: {status}")

        if status == "COMPLETED":
            attachments = msg_data.get("attachments", [])
            sql_found   = False
            for att in attachments:
                if att.get("query"):
                    sql_text = att["query"].get("query", "")
                    print(f"\n✅  Genie responded with SQL:")
                    print("─" * 60)
                    print(sql_text)
                    print("─" * 60)
                    sql_found = True

            if not sql_found:
                print("✅  Genie responded (open the space in the UI to see the full answer)")

        elif status == "FAILED":
            print("❌  Genie returned FAILED status.")
            print("    Common causes:")
            print("    • Tables not added to the space yet")
            print("    • SQL warehouse is stopped — start it first")
            print("    • Column descriptions reference non-existent columns")
            print(f"\n    Full message: {msg_data}")
        else:
            print(f"⚠️   Unexpected status: {status}")
            print("    Try opening the space in the UI and asking the question directly.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 Checkpoint
# MAGIC
# MAGIC Run the cell below to verify the setup before moving to the wrap-up.

# COMMAND ----------

# Full checkpoint: verify tables, column comments, and space API access
print("=" * 65)
print("LAB 01 CHECKPOINT")
print("=" * 65)

checks = []

# Check 1: spot_prices column comments
try:
    rows = spark.sql("""
        SELECT column_name, comment
        FROM system.information_schema.columns
        WHERE table_catalog = 'workshop_au'
          AND table_schema   = 'aemo'
          AND table_name     = 'spot_prices'
          AND column_name IN ('rrp', 'region_id', 'settlement_date')
    """).collect()
    spot_ok = all(bool(r['comment']) for r in rows)
    checks.append(("UC column descriptions — spot_prices", spot_ok,
                   "Add descriptions in Catalog → spot_prices → Columns tab" if not spot_ok else ""))
except Exception as e:
    checks.append(("UC column descriptions — spot_prices", False, str(e)[:80]))

# Check 2: market_notices column comments
try:
    rows_mn = spark.sql("""
        SELECT column_name, comment
        FROM system.information_schema.columns
        WHERE table_catalog = 'workshop_au'
          AND table_schema   = 'aemo'
          AND table_name     = 'market_notices'
          AND column_name IN ('notice_type', 'issue_time')
    """).collect()
    mn_ok = all(bool(r['comment']) for r in rows_mn)
    checks.append(("UC column descriptions — market_notices", mn_ok,
                   "Add descriptions in Catalog → market_notices → Columns tab" if not mn_ok else ""))
except Exception as e:
    checks.append(("UC column descriptions — market_notices", False, str(e)[:80]))

# Check 3: Space ID is set
space_id_ok = bool(SPACE_ID)
checks.append(("Genie Space ID saved in widget", space_id_ok,
               "Create the space in the UI and paste the ID into the widget" if not space_id_ok else ""))

# Check 4: Space is reachable via API
if SPACE_ID:
    try:
        HOST    = spark.conf.get("spark.databricks.workspaceUrl")
        TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
        HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
        r = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=HEADERS)
        api_ok = r.status_code == 200
        if api_ok:
            sp = r.json()
            n_tables = len(sp.get("datasets", []))
        checks.append(("Genie Space reachable via API", api_ok,
                       f"HTTP {r.status_code} — check SPACE_ID" if not api_ok else ""))

        # Check 5: Tables added
        if api_ok:
            tables_added = n_tables >= 3
            checks.append((f"Tables added to space (need 3, found {n_tables})", tables_added,
                           "Go to Configure → Add tables → select spot_prices, dispatch_intervals, market_notices" if not tables_added else ""))
    except Exception as e:
        checks.append(("Genie Space reachable via API", False, str(e)[:80]))
else:
    checks.append(("Genie Space reachable via API", False, "SPACE_ID not set"))
    checks.append(("Tables added to space", False, "SPACE_ID not set"))

# Manual checks (UI steps we cannot verify via API)
manual_checks = [
    "Column synonyms added for region_id and rrp",
    "Entity matching enabled for region_id",
    "Low-value FCAS columns hidden (raise_6sec etc.)",
]

# Print results
print("\nAutomated checks:")
all_auto_ok = True
for label, ok, hint in checks:
    icon = "✅" if ok else "❌"
    print(f"  {icon}  {label}")
    if not ok and hint:
        print(f"       → {hint}")
    if not ok:
        all_auto_ok = False

print("\nManual checks (confirm you completed these in the UI):")
for item in manual_checks:
    print(f"  ☐  {item}")

print("\n" + "=" * 65)
if all_auto_ok:
    print("✅  All automated checks passed.")
    print("    Confirm the three manual checks above, then proceed to Lab 02.")
else:
    print("⚠️   One or more automated checks failed. Fix them before continuing.")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 01 Summary
# MAGIC
# MAGIC <div style="font-family: 'DM Sans', Arial, sans-serif;">
# MAGIC <table style="width: 100%; border-collapse: collapse; font-size: 0.97em; margin-top: 8px;">
# MAGIC   <thead>
# MAGIC     <tr style="background: #1B3A6B; color: white;">
# MAGIC       <th style="padding: 10px 14px; text-align: left;">Section</th>
# MAGIC       <th style="padding: 10px 14px; text-align: left;">What you did</th>
# MAGIC       <th style="padding: 10px 14px; text-align: left;">Why it matters</th>
# MAGIC     </tr>
# MAGIC   </thead>
# MAGIC   <tbody>
# MAGIC     <tr style="background: #f7f8fa;">
# MAGIC       <td style="padding: 9px 14px; font-weight: 600;">Section 0</td>
# MAGIC       <td style="padding: 9px 14px;">Applied the 5-Table Rule and collected 10 representative user questions</td>
# MAGIC       <td style="padding: 9px 14px;">Scoped the space for one audience; questions drive golden query design</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 9px 14px; font-weight: 600;">Section 1</td>
# MAGIC       <td style="padding: 9px 14px;">Added UC table and column descriptions for spot_prices and market_notices</td>
# MAGIC       <td style="padding: 9px 14px;">Foundation layer — every other instruction layer inherits this accuracy</td>
# MAGIC     </tr>
# MAGIC     <tr style="background: #f7f8fa;">
# MAGIC       <td style="padding: 9px 14px; font-weight: 600;">Section 2</td>
# MAGIC       <td style="padding: 9px 14px;">Created "AEMO NEM Operations" space via UI with 3 tables</td>
# MAGIC       <td style="padding: 9px 14px;">Scoped to market operations audience; avoided the super-Genie anti-pattern</td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 9px 14px; font-weight: 600;">Section 3</td>
# MAGIC       <td style="padding: 9px 14px;">Added synonyms, enabled entity matching, hid low-value columns</td>
# MAGIC       <td style="padding: 9px 14px;">User shorthand ("NSW", "price") now maps to exact column values reliably</td>
# MAGIC     </tr>
# MAGIC   </tbody>
# MAGIC </table>
# MAGIC </div>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC <div style="background: #e8f0fe; border-left: 4px solid #1B3A6B; padding: 14px 20px; border-radius: 0 8px 8px 0; font-family: 'DM Sans', Arial, sans-serif; margin-top: 12px;">
# MAGIC   <strong>Key insight from this lab:</strong><br>
# MAGIC   Golden queries are routing rules. When a user's question matches a golden query, Genie skips SQL generation entirely
# MAGIC   and runs the pre-written SQL directly. The answer is labelled <em>Trusted</em>. This is why the instruction hierarchy matters:
# MAGIC   UC metadata gives Genie accurate column knowledge, synonyms handle user shorthand, and golden queries guarantee
# MAGIC   deterministic answers for your most critical business questions.<br><br>
# MAGIC   <strong>Next → Lab 02: The Instruction Hierarchy</strong><br>
# MAGIC   You will add SQL Expressions for KPIs, write your first golden queries, and add text instructions for rules
# MAGIC   that cannot be expressed in SQL.
# MAGIC </div>

# COMMAND ----------

# Persist Space ID for Lab 02 and Lab 03
# (Widget values persist within a session; copy this if you run labs in separate sessions)
print("─" * 55)
print("Space ID for Lab 02 and Lab 03:")
print(f"  {SPACE_ID}")
print("─" * 55)
print("\nIf you run the next lab in a new notebook session,")
print("paste this value into the genie_space_id widget.")
