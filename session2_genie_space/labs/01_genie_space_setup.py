# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 01: Create Your Genie Space</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 40 minutes |
# MAGIC | 👤 **Role** | Data Engineer / Genie Space Author |
# MAGIC | **Covers** | Slides 9, 23–27 — Setup, UC Metadata, Knowledge Store |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The mental model (Slide 23)
# MAGIC
# MAGIC > *"Think of Genie as a brand new analyst joining your organisation as their first job post university. This analyst is pretty good at writing SQL but has no pre-existing knowledge about your business — not high-level concepts, not low-level jargon. The only knowledge they will have is the context provided in that particular space."*
# MAGIC
# MAGIC **This changes how you build.** Everything you put in the space is onboarding material for that new analyst.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Priority stack (Slides 26–29)
# MAGIC
# MAGIC | Priority | Method | Why |
# MAGIC |---|---|---|
# MAGIC | **1st** | UC Metadata | First and best — column descriptions, PK/FK, value dictionaries |
# MAGIC | **2nd** | Knowledge Store | Synonyms, join hints, show/hide — without touching UC metadata |
# MAGIC | **3rd** | Example SQL | Parameterised golden queries for complex patterns |
# MAGIC | **Last** | Text Instructions | Only for universal rules that can't be expressed as SQL |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Before you build: Topic selection (Slide 24)
# MAGIC
# MAGIC > *"Just like there's no single dashboard for the organisation, there's no single Genie space."*
# MAGIC
# MAGIC **For this workshop** — we're building: **AEMO NEM Market Operations**
# MAGIC - Audience: Market operations team
# MAGIC - Tables: spot_prices, dispatch_intervals, market_notices
# MAGIC - 15 starter questions (Slide 34): average prices by region, price spikes, generator dispatch, fuel mix, LOR events
# MAGIC
# MAGIC **🖱️ Step 0 — UI: Navigate to Genie**
# MAGIC ```
# MAGIC Left sidebar → Genie (sparkle icon) → + New Space (top right)
# MAGIC ```

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID (from URL after creating)")
SPACE_ID = dbutils.widgets.get("genie_space_id")

CATALOG = "workshop_au"
SCHEMA  = "aemo"
HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print(f"Catalog: {CATALOG}.{SCHEMA}")
print(f"Space ID: {SPACE_ID or '(not yet set — create space in UI first)'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: UC Metadata — the highest-leverage improvement (Slide 26)
# MAGIC
# MAGIC > *"UC metadata is the first and best option for providing Genie with the context it needs."*
# MAGIC
# MAGIC **🖱️ Navigate: Catalog → workshop_au → aemo → [table] → Columns tab → pencil icon**
# MAGIC
# MAGIC ### Column descriptions to add now
# MAGIC
# MAGIC **spot_prices table:**
# MAGIC
# MAGIC | Column | Description to add |
# MAGIC |---|---|
# MAGIC | `rrp` | Regional Reference Price in $/MWh. Normal range $50–$200. Market price cap $15,300/MWh. Price floor -$1,000/MWh. Negative prices indicate oversupply. |
# MAGIC | `region_id` | NEM region identifier. Must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix. |
# MAGIC | `settlement_date` | Trading interval end time. 30-minute intervals. Use DATE(settlement_date) to filter by day. |
# MAGIC
# MAGIC **dispatch_intervals table:**
# MAGIC
# MAGIC | Column | Description to add |
# MAGIC |---|---|
# MAGIC | `duid` | Dispatchable Unit Identifier. Unique per generating unit. Join to generator_registration on duid to get station name and fuel type. |
# MAGIC | `dispatch_mw` | Actual MW dispatched in the 5-minute interval. Sum and divide by 12 to convert to MWh. |
# MAGIC | `fuel_type` | Generation fuel: solar, wind, coal, gas, hydro, battery. Use CASE to group into Renewable / Fossil Fuel / Other. |
# MAGIC
# MAGIC **market_notices table:**
# MAGIC
# MAGIC | Column | Description to add |
# MAGIC |---|---|
# MAGIC | `notice_type` | Category: LOR1 (watch), LOR2 (threatened shortage), LOR3 (imminent shortage), MARKET NOTICE, SYSTEM NOTICE. |
# MAGIC | `issue_time` | When AEMO published the notice. Use to filter recent events. |
# MAGIC | `reason` | Free-text explanation of the notice. Contains the human-readable description. |

# COMMAND ----------

# Verify column comments are set
import pyspark.sql.functions as F

check = spark.sql(f"""
    SELECT table_name, column_name, comment
    FROM system.information_schema.columns
    WHERE table_catalog = '{CATALOG}'
      AND table_schema  = '{SCHEMA}'
      AND table_name    IN ('spot_prices', 'dispatch_intervals', 'market_notices')
      AND column_name   IN ('rrp', 'region_id', 'settlement_date', 'duid', 'dispatch_mw', 'fuel_type', 'notice_type', 'issue_time')
    ORDER BY table_name, column_name
""")

rows = check.collect()
for r in rows:
    icon = "✅" if r['comment'] else "❌ Add description in Catalog Explorer"
    print(f"{icon} {r['table_name']}.{r['column_name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Create the Space — UI walkthrough (Slide 9)
# MAGIC
# MAGIC **🖱️ Navigate: Left sidebar → Genie → + New Space**
# MAGIC
# MAGIC ```
# MAGIC Title:       AEMO NEM Operations
# MAGIC Description: Natural language access to NEM spot prices, dispatch data,
# MAGIC              and market notices for the Market Operations team.
# MAGIC Warehouse:   select your serverless warehouse
# MAGIC → Click Create
# MAGIC ```
# MAGIC
# MAGIC **🖱️ Add tables: Configure tab → Data → + Add**
# MAGIC ```
# MAGIC ✓ workshop_au.aemo.spot_prices
# MAGIC ✓ workshop_au.aemo.dispatch_intervals
# MAGIC ✓ workshop_au.aemo.market_notices
# MAGIC → Click Confirm
# MAGIC ```
# MAGIC
# MAGIC **🖱️ Review Suggested Queries** (appears automatically)
# MAGIC - Genie searches your workspace for queries related to these tables
# MAGIC - Accept useful ones, reject irrelevant ones
# MAGIC - Click Done
# MAGIC
# MAGIC **📋 Find your Space ID:**
# MAGIC ```
# MAGIC Browser URL bar after opening the space:
# MAGIC ...azuredatabricks.com/genie/spaces/01xxxxxxxxxxxxxxxxx
# MAGIC                                     ↑ copy this
# MAGIC ```
# MAGIC Paste it into the widget at the top of this notebook.

# COMMAND ----------

# Smoke test — verify the space is live
import requests

if SPACE_ID:
    resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=HEADERS)
    if resp.status_code == 200:
        s = resp.json()
        print(f"✅ Space: {s.get('title')}")
        print(f"   Datasets: {len(s.get('datasets', []))} tables")
        print(f"   URL: https://{HOST}/genie/spaces/{SPACE_ID}")
    else:
        print(f"❌ Error {resp.status_code}: {resp.text[:200]}")
else:
    print("Enter your Space ID in the widget above first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Knowledge Store — second-priority context (Slide 27)
# MAGIC
# MAGIC > *"Knowledge Store provides Genie local semantics for when you can't or don't want to update UC metadata."*
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Data → click table name → Synonyms / Format assistance tabs**
# MAGIC
# MAGIC ### Add synonyms (map business language to column names)
# MAGIC
# MAGIC | Table | Column | Synonyms to add |
# MAGIC |---|---|---|
# MAGIC | spot_prices | `region_id` | region, state, NEM region, zone |
# MAGIC | spot_prices | `rrp` | price, spot price, market price, $/MWh |
# MAGIC | spot_prices | `settlement_date` | date, time, interval, trading interval |
# MAGIC | dispatch_intervals | `dispatch_mw` | dispatch, output, generation, MW |
# MAGIC | dispatch_intervals | `fuel_type` | fuel, energy type, generation type |
# MAGIC | market_notices | `notice_type` | notice category, type |
# MAGIC
# MAGIC ### Entity matching — AEMO region codes (Slide 35)
# MAGIC
# MAGIC **🖱️ For `region_id` in spot_prices: Configure → Data → spot_prices → region_id → Format assistance → enable**
# MAGIC
# MAGIC This lets Genie map plain English to NEM codes:
# MAGIC ```
# MAGIC "NSW"        → NSW1    "New South Wales" → NSW1
# MAGIC "VIC" or "Victoria" → VIC1
# MAGIC "Queensland" → QLD1    "SA"              → SA1
# MAGIC "Tasmania"   → TAS1
# MAGIC ```
# MAGIC
# MAGIC **🖱️ For `notice_type` in market_notices: enable entity matching**
# MAGIC ```
# MAGIC "lack of reserve"    → LOR1, LOR2, LOR3
# MAGIC "reserve warning"    → LOR1
# MAGIC "reserve shortfall"  → LOR2
# MAGIC "critical shortage"  → LOR3
# MAGIC ```
# MAGIC
# MAGIC **🖱️ For `fuel_type` in dispatch_intervals: enable entity matching**
# MAGIC ```
# MAGIC "renewables"  → solar, wind
# MAGIC "coal"        → coal
# MAGIC "gas peakers" → gas
# MAGIC "hydro"       → hydro
# MAGIC ```
# MAGIC
# MAGIC ### Hide confusing columns
# MAGIC **🖱️ Configure → Data → spot_prices → eye icon to hide:**
# MAGIC - `raise_6sec`, `lower_6sec` (FCAS prices — hide unless FCAS questions expected)
# MAGIC
# MAGIC **🖱️ Configure → Data → dispatch_intervals → hide:**
# MAGIC - `initial_mw`, `available_mw`, `ramp_rate` (operational fields rarely needed for business Q&A)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Join configuration (Knowledge Store)
# MAGIC
# MAGIC **🖱️ Navigate: Configure → Instructions → Joins → + Add**
# MAGIC
# MAGIC ```
# MAGIC Left table:     dispatch_intervals
# MAGIC Right table:    generator_registration
# MAGIC Join condition: dispatch_intervals.duid = generator_registration.duid
# MAGIC Relationship:   Many-to-one
# MAGIC → Save
# MAGIC ```
# MAGIC
# MAGIC This tells Genie exactly how to join dispatch data with station names and fuel types.
# MAGIC Without this, Genie may guess wrong or refuse to join the tables.

# COMMAND ----------

# Validation: test that the join works
join_test = spark.sql(f"""
    SELECT 
        d.duid,
        g.station_name,
        g.fuel_type,
        ROUND(SUM(d.dispatch_mw) / 12, 1) AS mwh_last_7d
    FROM {CATALOG}.{SCHEMA}.dispatch_intervals d
    LEFT JOIN {CATALOG}.{SCHEMA}.generator_registration g ON d.duid = g.duid
    WHERE d.settlement_date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY d.duid, g.station_name, g.fuel_type
    ORDER BY mwh_last_7d DESC
    LIMIT 5
""")
display(join_test)
print("✅ Join works. Add this relationship in Configure → Instructions → Joins.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 01 Checkpoint
# MAGIC
# MAGIC Before moving to Lab 02, confirm:
# MAGIC - [ ] Column descriptions added for rrp, region_id, settlement_date, duid, dispatch_mw, notice_type
# MAGIC - [ ] Space created with 3 AEMO tables
# MAGIC - [ ] Synonyms added for region_id and rrp  
# MAGIC - [ ] Entity matching enabled for region_id (NSW→NSW1 etc.)
# MAGIC - [ ] Entity matching enabled for notice_type (lack of reserve→LOR%)
# MAGIC - [ ] Join configured: dispatch_intervals ↔ generator_registration
# MAGIC - [ ] Space ID entered in widget above
# MAGIC
# MAGIC **→ Next: Lab 02 — Benchmarks, Golden Queries & Instructions**

