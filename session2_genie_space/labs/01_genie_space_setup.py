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
# MAGIC | **Prerequisites** | AEMO tables loaded — run `session2_genie_space/setup/setup.py` first if not done by facilitator |
# MAGIC | **Covers** | Slides 9, 23–27 — Setup, UC Metadata, Knowledge Store |
# MAGIC
# MAGIC > **Before running any code cell:** confirm `workshop_au.aemo` tables exist — run the verify cell below. If tables are missing, ask your facilitator to run `session2_genie_space/setup/setup.py`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The mental model
# MAGIC
# MAGIC > *"Think of Genie as a brand new analyst. Brilliant at SQL, but knows nothing about your business. Everything they know comes from what you put in the space."*
# MAGIC
# MAGIC > ⚠️ **Prerequisite:** Both workspace settings must be ON before Genie works:
# MAGIC > Geography enforcement (Account Console → Security and compliance) + Partner-Powered AI Features (workspace settings). Never disable Partner-Powered — it kills Genie entirely.
# MAGIC
# MAGIC ## Priority stack
# MAGIC
# MAGIC | Priority | Method | Why |
# MAGIC |---|---|---|
# MAGIC | **1st** | UC Metadata | First and best — column descriptions, PK/FK |
# MAGIC | **2nd** | Knowledge Store | Synonyms, joins, entity matching |
# MAGIC | **3rd** | Example SQL | Complex parameterised patterns |
# MAGIC | **Last** | Text Instructions | Universal rules only |

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Genie Space ID (from URL after creating)")
SPACE_ID = dbutils.widgets.get("genie_space_id")

CATALOG = "workshop_au"
SCHEMA  = "aemo"
HOST    = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print(f"Catalog: {CATALOG}.{SCHEMA}")
print(f"Space:   {SPACE_ID or '(create the space first, then paste ID here)'}")

# COMMAND ----------

# Verify AEMO tables exist before proceeding — STOP if any table is missing
REQUIRED_TABLES = [
    f"{CATALOG}.{SCHEMA}.spot_prices",
    f"{CATALOG}.{SCHEMA}.dispatch_intervals",
    f"{CATALOG}.{SCHEMA}.market_notices",
    f"{CATALOG}.{SCHEMA}.generator_registration",
    f"{CATALOG}.{SCHEMA}.settlement_amounts",
]

missing = []
for t in REQUIRED_TABLES:
    try:
        spark.sql(f"SELECT 1 FROM {t} LIMIT 1")
        print(f"  [OK] {t.split('.')[-1]}")
    except Exception:
        missing.append(t)
        print(f"  [MISSING] {t}")

if missing:
    raise RuntimeError(
        f"\n{len(missing)} table(s) missing in {CATALOG}.{SCHEMA}. "
        "Ask your facilitator to run session2_genie_space/setup/setup.py before continuing."
    )
else:
    print(f"\nAll {len(REQUIRED_TABLES)} tables present — ready to proceed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: UC Column Comments
# MAGIC
# MAGIC **🖱️ UI:** Catalog → workshop_au → aemo → [table] → Columns tab → pencil icon on each column
# MAGIC
# MAGIC **⚡ Or run the cell below to automate all columns at once.**
# MAGIC The script uses `ALTER TABLE … ALTER COLUMN … COMMENT` — which replaces any existing comment.

# COMMAND ----------

# Automated: set all column comments in one run
# Replaces existing comments. Safe to re-run.

COLUMN_COMMENTS = {
    f"{CATALOG}.{SCHEMA}.spot_prices": {
        "settlement_date": "Trading interval end time. 30-minute intervals. AEST/AEDT timezone. Use DATE(settlement_date) to filter by day.",
        "region_id":       "NEM region. Must be NSW1, VIC1, QLD1, SA1, or TAS1 — always with the '1' suffix.",
        "rrp":             "Regional Reference Price in $/MWh. Normal range $50–$200. Market cap $15,300/MWh. Floor -$1,000/MWh. Negative = oversupply.",
        "raise_6sec":      "6-second raise FCAS price. Hide unless FCAS analysis required.",
        "lower_6sec":      "6-second lower FCAS price. Hide unless FCAS analysis required.",
        "total_demand_mw": "Total scheduled demand for the region in MW.",
        "net_interchange": "Net MW flow between regions. Positive = exporting.",
        "scheduled_generation": "Total scheduled generation in the region in MW.",
    },
    f"{CATALOG}.{SCHEMA}.dispatch_intervals": {
        "settlement_date": "5-minute dispatch interval end time. Sum dispatch_mw and divide by 12 to convert to MWh.",
        "region_id":       "NEM region where the unit dispatched. Must be NSW1, VIC1, QLD1, SA1, or TAS1.",
        "duid":            "Dispatchable Unit Identifier. Unique per generating unit. Join to generator_registration on duid for station_name and fuel_type.",
        "dispatch_mw":     "Actual MW dispatched in this 5-minute interval. Divide SUM(dispatch_mw)/12 to get MWh.",
        "initial_mw":      "Initial MW target at interval start.",
        "available_mw":    "MW available for dispatch.",
        "ramp_rate":       "Maximum ramp rate in MW per minute.",
        "fuel_type":       "Generation technology: solar, wind, coal, gas, hydro, battery. Group with CASE into Renewable (solar, wind) vs Fossil Fuel (coal, gas).",
        "station_name":    "Human-readable station name e.g. Bayswater, Loy Yang A.",
        "state":           "Australian state the unit is located in.",
    },
    f"{CATALOG}.{SCHEMA}.market_notices": {
        "notice_id":     "Unique identifier for the market notice.",
        "notice_type":   "LOR1 = reserve watch. LOR2 = shortfall threatened. LOR3 = imminent critical shortage. Use LIKE 'LOR%' to match all LOR types.",
        "issue_time":    "When AEMO published the notice. Use to filter recent events.",
        "reason":        "Free-text description of the notice. Use SUBSTRING(reason, 1, 200) for summaries.",
        "effective_date":"When the notice takes effect.",
        "region_id":     "NEM region. NULL means the notice applies NEM-wide.",
        "intervention":  "True if this is an AEMO intervention notice.",
    },
    f"{CATALOG}.{SCHEMA}.generator_registration": {
        "duid":                   "Dispatchable Unit Identifier. Primary key. Join to dispatch_intervals.duid.",
        "station_name":           "Human-readable station name.",
        "participant_id":         "Market participant code (company identifier).",
        "region_id":              "NEM region where registered.",
        "fuel_type":              "Generation technology: solar, wind, coal, gas, hydro, battery.",
        "registered_capacity_mw": "Maximum registered capacity in MW.",
        "dispatch_type":          "GENERATOR, LOAD, or BIDIRECTIONAL.",
        "max_ramp_rate":          "Maximum ramp rate in MW per minute.",
        "min_load":               "Minimum stable load in MW.",
    },
    f"{CATALOG}.{SCHEMA}.settlement_amounts": {
        "settlement_date":              "Settlement week end date.",
        "participant_id":               "Market participant code.",
        "run_type":                     "FINAL, REVISED, or PRELIMINARY.",
        "energy_amount_aud":            "Energy component of settlement in AUD.",
        "fcas_amount_aud":              "FCAS (ancillary services) component in AUD.",
        "interconnector_residue_aud":   "Interconnector residue component in AUD.",
        "total_aud":                    "Net settlement amount in AUD.",
        "settlement_status":            "FINAL, PENDING, or DISPUTED.",
    },
}

results = []
for table_fqn, columns in COLUMN_COMMENTS.items():
    for col, comment in columns.items():
        safe_comment = comment.replace("'", "\\'")
        sql = f"ALTER TABLE {table_fqn} ALTER COLUMN `{col}` COMMENT '{safe_comment}'"
        try:
            spark.sql(sql)
            results.append(("✅", table_fqn.split(".")[-1], col))
        except Exception as e:
            results.append(("❌", table_fqn.split(".")[-1], f"{col}: {e}"))

print(f"Set {sum(1 for r in results if r[0]=='✅')} column comments")
for icon, tbl, col in results:
    print(f"  {icon} {tbl}.{col}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Table-level descriptions
# MAGIC
# MAGIC **🖱️ UI:** Catalog → [table] → Overview tab → Edit description
# MAGIC
# MAGIC **⚡ Automated:**

# COMMAND ----------

TABLE_DESCRIPTIONS = {
    f"{CATALOG}.{SCHEMA}.spot_prices": (
        "NEM 30-minute trading interval spot prices. "
        "Key column: rrp = Regional Reference Price in $/MWh. "
        "Regions: NSW1, VIC1, QLD1, SA1, TAS1."
    ),
    f"{CATALOG}.{SCHEMA}.dispatch_intervals": (
        "NEM 5-minute generator dispatch data. "
        "Key columns: duid (join to generator_registration), dispatch_mw (divide by 12 for MWh), fuel_type. "
        "12 intervals = 1 hour."
    ),
    f"{CATALOG}.{SCHEMA}.market_notices": (
        "AEMO market and system notices including LOR events. "
        "Key column: notice_type (LOR1/LOR2/LOR3 = escalating lack-of-reserve severity). "
        "Filter: WHERE notice_type LIKE 'LOR%' for LOR events."
    ),
    f"{CATALOG}.{SCHEMA}.generator_registration": (
        "NEM registered generator details. "
        "Join to dispatch_intervals on duid to get station_name and fuel_type."
    ),
    f"{CATALOG}.{SCHEMA}.settlement_amounts": (
        "Weekly NEM settlement amounts by participant. "
        "run_type: FINAL = confirmed, PRELIMINARY = estimate. "
        "total_aud = net settlement amount in AUD."
    ),
}

for table_fqn, desc in TABLE_DESCRIPTIONS.items():
    safe_desc = desc.replace("'", "\\'")
    try:
        spark.sql(f"COMMENT ON TABLE {table_fqn} IS '{safe_desc}'")
        print(f"✅ {table_fqn.split('.')[-1]}")
    except Exception as e:
        print(f"❌ {table_fqn.split('.')[-1]}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Create the Space
# MAGIC
# MAGIC **🖱️ UI (do this first):** Left sidebar → Genie → + New Space
# MAGIC ```
# MAGIC Title:       AEMO NEM Operations
# MAGIC Description: Natural language access to NEM spot prices, dispatch data,
# MAGIC              and market notices for the Market Operations team.
# MAGIC Warehouse:   select your serverless warehouse
# MAGIC → Create → Add tables: spot_prices, dispatch_intervals, market_notices, generator_registration
# MAGIC   (generator_registration is required for the duid join configured in Step 4)
# MAGIC → Copy the Space ID from the browser URL bar
# MAGIC → Paste into the widget at the top of this notebook
# MAGIC ```
# MAGIC
# MAGIC **⚡ Verify the space is live:**

# COMMAND ----------

import requests, json

if SPACE_ID:
    resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=HEADERS)
    if resp.status_code == 200:
        s = resp.json()
        print(f"✅ Space: {s.get('title')}")
        print(f"   URL: https://{HOST}/genie/spaces/{SPACE_ID}")
    else:
        print(f"❌ {resp.status_code}: {resp.text[:200]}")
else:
    print("Enter Space ID in the widget above first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Knowledge Store — synonyms, entity matching, joins
# MAGIC
# MAGIC **🖱️ UI for synonyms:** Configure → Data → [table] → column → Synonyms tab
# MAGIC **🖱️ UI for entity matching:** Configure → Data → [table] → column → Format assistance → enable
# MAGIC **🖱️ UI for joins:** Configure → Instructions → Joins → + Add
# MAGIC
# MAGIC Synonyms and entity matching are set in the space UI — do these manually in the Configure tab.
# MAGIC The join relationship can also be set via the space settings API:

# COMMAND ----------

# Automated: add the join relationship via API
# (Synonyms and entity matching must be done in the UI — Configure → Data tab)

if not SPACE_ID:
    print("Enter Space ID in widget first.")
else:
    join_payload = {
        "joins": [{
            "left_table":   f"{CATALOG}.{SCHEMA}.dispatch_intervals",
            "right_table":  f"{CATALOG}.{SCHEMA}.generator_registration",
            "join_condition": "dispatch_intervals.duid = generator_registration.duid",
            "relationship_type": "MANY_TO_ONE"
        }]
    }
    resp = requests.patch(
        f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
        headers=HEADERS,
        json=join_payload
    )
    if resp.status_code in (200, 204):
        print("✅ Join configured: dispatch_intervals ↔ generator_registration on duid")
    else:
        # Falls back to showing the manual UI steps
        print(f"API returned {resp.status_code} — add the join manually in the UI:")
        print("  Configure → Instructions → Joins → + Add")
        print("  Left: dispatch_intervals  |  Right: generator_registration")
        print("  Condition: dispatch_intervals.duid = generator_registration.duid")
        print("  Relationship: Many-to-one")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Synonyms to add manually (Configure → Data → [table] → column → Synonyms)
# MAGIC
# MAGIC | Table | Column | Synonyms |
# MAGIC |---|---|---|
# MAGIC | spot_prices | `region_id` | region, state, NEM region, zone |
# MAGIC | spot_prices | `rrp` | price, spot price, market price |
# MAGIC | spot_prices | `settlement_date` | date, trading interval |
# MAGIC | dispatch_intervals | `dispatch_mw` | dispatch, output, generation, MW |
# MAGIC | dispatch_intervals | `fuel_type` | fuel, energy type, generation type |
# MAGIC | market_notices | `notice_type` | notice category, type |
# MAGIC
# MAGIC ### Entity matching to enable (Configure → Data → [table] → column → Format assistance → toggle on)
# MAGIC
# MAGIC | Column | Maps |
# MAGIC |---|---|
# MAGIC | `region_id` | NSW → NSW1, Victoria → VIC1, QLD → QLD1, SA → SA1, TAS → TAS1 |
# MAGIC | `notice_type` | lack of reserve → LOR%, reserve warning → LOR1, critical shortage → LOR3 |
# MAGIC | `fuel_type` | renewables → solar/wind, coal → coal, gas peakers → gas |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 01 Checkpoint
# MAGIC - [ ] Column comments set (automated ✅)
# MAGIC - [ ] Table descriptions set (automated ✅)
# MAGIC - [ ] Space created with 3 tables, Space ID in widget
# MAGIC - [ ] Synonyms added for region_id and rrp (UI)
# MAGIC - [ ] Entity matching enabled for region_id and notice_type (UI)
# MAGIC - [ ] Join configured (API or UI)
# MAGIC
# MAGIC **→ Next: Lab 02 — Benchmarks, Golden Queries & Instructions**
