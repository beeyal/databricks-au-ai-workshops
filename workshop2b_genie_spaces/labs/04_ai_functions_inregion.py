# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A5C 0%, #FF3621 100%); padding: 24px 32px; border-radius: 10px; margin-bottom: 8px">
# MAGIC   <h1 style="color: white; margin: 0; font-size: 28px; font-family: 'DM Sans', sans-serif">
# MAGIC     Lab 04 -- AI Functions: In-Region Pattern for Australia East
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0 0; font-size: 15px">
# MAGIC     Workshop 2B: Genie Spaces and AI Features -- Australian Regulated Industries
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <table style="border-collapse: collapse; width: 100%; margin-top: 8px; font-family: 'DM Sans', sans-serif">
# MAGIC   <tr>
# MAGIC     <td style="padding: 8px 16px; background: #F4F4F4; border-radius: 4px; width: 25%"><strong>Duration</strong></td>
# MAGIC     <td style="padding: 8px 16px">40-45 minutes</td>
# MAGIC   </tr>
# MAGIC   <tr>
# MAGIC     <td style="padding: 8px 16px; background: #F4F4F4; border-radius: 4px"><strong>Role</strong></td>
# MAGIC     <td style="padding: 8px 16px">Data Engineer / ML Engineer</td>
# MAGIC   </tr>
# MAGIC   <tr>
# MAGIC     <td style="padding: 8px 16px; background: #F4F4F4; border-radius: 4px"><strong>Prerequisite</strong></td>
# MAGIC     <td style="padding: 8px 16px">Labs 01-02 complete -- <code>workshop_au.energy</code> tables exist</td>
# MAGIC   </tr>
# MAGIC </table>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Objectives
# MAGIC
# MAGIC | # | Objective |
# MAGIC |---|-----------|
# MAGIC | 1 | Understand why default AI Functions are cross-geo and why that matters for SOCI Act / critical infrastructure regulated workloads |
# MAGIC | 2 | Deploy a **Provisioned Throughput (PT) endpoint** in AU East as the in-region AI router |
# MAGIC | 3 | Create **Unity Catalog wrapper functions** that route all AI calls through the PT endpoint |
# MAGIC | 4 | Implement classification, summarisation, and extraction using the in-region pattern |
# MAGIC | 5 | Build Australian-specific **PII masking** -- TFN, Medicare, ABN, ACN, NMI detection |
# MAGIC | 6 | Apply to realistic energy domain scenarios: outage classification and work order extraction |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Why This Lab Exists: The Data Residency Problem
# MAGIC
# MAGIC The built-in AI Functions (`ai_classify`, `ai_summarize`, `ai_extract`, `ai_generate`) call Databricks' shared Foundation Model API. For AU East workspaces, model inference **may route outside Australia** (typically US East 1), which is incompatible with SOCI Act / critical infrastructure data handling requirements.
# MAGIC
# MAGIC ```
# MAGIC CROSS-GEO (avoid for regulated AU data)        IN-REGION (use this)
# MAGIC ─────────────────────────────────               ─────────────────────────────
# MAGIC  ai_classify(text, labels)                       ai_query('au_pt_endpoint', prompt)
# MAGIC  → FMAPI shared infra → may leave AU             → YOUR PT endpoint → stays in AU East
# MAGIC ```
# MAGIC
# MAGIC **Fix:** Deploy a Provisioned Throughput (PT) endpoint pinned to your workspace region, then route all AI calls through `ai_query('endpoint_name', prompt)`. The PT endpoint name (a plain string) is the routing key -- not a URL or catalog path.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 0 -- Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0 mlflow>=2.14
dbutils.library.restartPython()

# COMMAND ----------

import requests, time, json
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServedEntityInput, EndpointCoreConfigInput, TrafficConfig, Route
)

# COMMAND ----------

# Widget-based configuration — works in any customer Databricks environment
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

def hdrs():
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print(f"Connected: {HOST}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1 -- Deploy a Provisioned Throughput Endpoint (AU East)
# MAGIC
# MAGIC > **START THIS STEP FIRST — deployment takes 5–15 minutes.**
# MAGIC > Run the SDK cell below (Option B) immediately, then proceed with reading the UI orientation
# MAGIC > and Step 2 while the endpoint provisions in the background.
# MAGIC > Do not skip ahead to Step 3 until the endpoint reaches **Ready** state.
# MAGIC
# MAGIC ### Option A -- Deploy via the UI
# MAGIC
# MAGIC **Navigate:** Left sidebar → Serving → **[+ Create serving endpoint]** (top right)
# MAGIC
# MAGIC ```
# MAGIC  Name:              au_east_llm_inregion   (must not start with "databricks-")
# MAGIC  Entity type:       Foundation model
# MAGIC  Model:             databricks-claude-haiku-4-5  ✅ in-region PT for AU East
# MAGIC  Throughput type:   Provisioned throughput        ← NOT Pay per token (that is cross-geo)
# MAGIC  Min throughput:    0                             (scale to zero — saves workshop cost)
# MAGIC  Click [Create] → status: Pending → Ready (5-15 minutes)
# MAGIC ```
# MAGIC
# MAGIC **Test from the UI once Ready:** Left sidebar → Serving → [endpoint name] → **"Query endpoint"** button (top right)
# MAGIC ```json
# MAGIC {"messages": [{"role": "user", "content": "Classify: transformer overheated during heatwave. WEATHER or EQUIPMENT?"}]}
# MAGIC ```
# MAGIC
# MAGIC ### Option B -- Deploy via SDK (cell below — run this NOW, then continue reading)

# COMMAND ----------

PT_ENDPOINT_NAME = PT_ENDPOINT          # from widget, default "au_east_llm_inregion"
PT_MODEL_NAME    = "databricks-claude-haiku-4-5"   # ✅ in-region PT model for AU East


def create_pt_endpoint(endpoint_name: str, model_name: str) -> str:
    """Creates a Provisioned Throughput serving endpoint. Skips if already exists."""
    print(f"Endpoint : {endpoint_name}")
    print(f"Model    : {model_name}")
    print("Estimated: 5-10 minutes to reach READY state...")
    try:
        existing = w.serving_endpoints.get(endpoint_name)
        print(f"Already exists — state: {existing.state.ready}. Reusing.")
        return endpoint_name
    except Exception:
        pass

    w.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    name=f"{endpoint_name}_entity",
                    entity_name=model_name,
                    entity_version="1",
                    min_provisioned_throughput=0,
                    max_provisioned_throughput=1000,
                )
            ],
            traffic_config=TrafficConfig(
                routes=[Route(served_model_name=f"{endpoint_name}_entity", traffic_percentage=100)]
            )
        ),
        timeout=600
    )
    print(f"Endpoint '{endpoint_name}' is READY.")
    return endpoint_name


ENDPOINT_NAME = create_pt_endpoint(PT_ENDPOINT_NAME, PT_MODEL_NAME)
print(f"\nEndpoint name for all subsequent cells: {ENDPOINT_NAME}")

# COMMAND ----------

# Verify endpoint is ready and confirm its configuration
def verify_endpoint_region(endpoint_name: str) -> None:
    ep = w.serving_endpoints.get(endpoint_name)
    print(f"Endpoint : {ep.name}")
    print(f"State    : {ep.state.ready if ep.state else 'unknown'}")
    if ep.config and ep.config.served_entities:
        for entity in ep.config.served_entities:
            print(f"Model    : {entity.entity_name}")
            print(f"Min TPU  : {entity.min_provisioned_throughput} tokens/s")
            print(f"Max TPU  : {entity.max_provisioned_throughput} tokens/s")
    print(f"\nInference URL: https://{HOST}/serving-endpoints/{endpoint_name}/invocations")
    print("This URL routes to AU East compute -- no cross-geo data transfer.")


try:
    verify_endpoint_region(ENDPOINT_NAME)
except Exception as e:
    print(f"Endpoint not yet ready: {e}")
    print("Wait a few more minutes and re-run this cell.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2 -- Create Unity Catalog Wrapper Functions
# MAGIC
# MAGIC Wrapping the PT endpoint in UC functions gives a single update point, SQL accessibility from Genie and dashboards, versioned prompt templates, and UC-governed permissions.

# COMMAND ----------

ENDPOINT_FQN = ENDPOINT_NAME  # plain string; ai_query resolves by workspace

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.ai_functions")
print(f"Schema ready: {CATALOG}.ai_functions")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2a -- Generic classifier

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.classify_text(
    text_input    STRING COMMENT 'Text to classify',
    categories    STRING COMMENT 'Comma-separated valid categories',
    domain_context STRING COMMENT 'Domain context to guide classification'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Classifies text using the AU East in-region PT endpoint. No data leaves the region.'
RETURN
    ai_query(
        '{ENDPOINT_FQN}',
        CONCAT(
            'You are a text classifier for ', domain_context, '. ',
            'Classify the following text into EXACTLY ONE of these categories: ', categories, '. ',
            'Respond with ONLY the category name -- no explanation, no punctuation.\\n\\n',
            'Text: ', text_input
        )
    )
""")
print(f"Created: {CATALOG}.ai_functions.classify_text")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2b -- Summarisation

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.summarise_text(
    text_input STRING COMMENT 'Text to summarise',
    max_words  INT    COMMENT 'Maximum word count (e.g. 50, 100, 200)',
    audience   STRING COMMENT 'Target audience: EXECUTIVE, TECHNICAL, OPERATIONAL'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Summarises text for a target audience using the AU East in-region endpoint.'
RETURN
    ai_query(
        '{ENDPOINT_FQN}',
        CONCAT(
            'Summarise the following text in at most ', CAST(max_words AS STRING), ' words ',
            'for a ', audience, ' audience in the Australian energy industry. ',
            'Focus on key findings, metrics, and regulatory implications. ',
            'Write in plain Australian English. Do not use bullet points.\\n\\n',
            'Text:\\n', text_input
        )
    )
""")
print(f"Created: {CATALOG}.ai_functions.summarise_text")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2c -- Structured extraction

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.extract_json(
    text_input  STRING COMMENT 'Text to extract from',
    json_schema STRING COMMENT 'JSON schema describing fields to extract'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Extracts structured fields from unstructured text as JSON. Uses AU East PT endpoint.'
RETURN
    ai_query(
        '{ENDPOINT_FQN}',
        CONCAT(
            'Extract the following information from the text below and return it as valid JSON. ',
            'If a field cannot be found, use null. Do not include any text outside the JSON object.\\n\\n',
            'Required JSON schema:\\n', json_schema, '\\n\\n',
            'Text:\\n', text_input
        )
    )
""")
print(f"Created: {CATALOG}.ai_functions.extract_json")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2d -- Australian PII detection

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.detect_au_pii(
    text_input STRING COMMENT 'Text to scan for Australian PII'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Detects AU PII (TFN, Medicare, ABN, ACN, NMI). Returns JSON. Uses AU East endpoint -- PII never leaves Australia.'
RETURN
    ai_query(
        '{ENDPOINT_FQN}',
        CONCAT(
            'Analyse the following text for Australian personally identifiable information (PII). ',
            'Check for: ',
            '(1) Tax File Number (TFN): 8-9 digit number, formatted XXX XXX XXX, ',
            '(2) Medicare Number: 10-digit number starting with 2-6, ',
            '(3) ABN: 11 digits, often formatted XX XXX XXX XXX, ',
            '(4) ACN: 9 digits, often formatted XXX XXX XXX, ',
            '(5) NMI (National Metering Identifier): 10-11 alphanumeric chars starting with a letter. ',
            'Return a JSON object: ',
            '{{"contains_pii": true/false, ',
            '"pii_types_found": ["TFN","MEDICARE","ABN","ACN","NMI"], ',
            '"masking_required": true/false, ',
            '"risk_level": "HIGH/MEDIUM/LOW/NONE"}}. ',
            'Return ONLY the JSON.\\n\\nText: ', text_input
        )
    )
""")
print(f"Created: {CATALOG}.ai_functions.detect_au_pii")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3 -- Test the Wrapper Functions
# MAGIC
# MAGIC The PT endpoint must be in **Ready** state before running these cells.
# MAGIC Check: Left sidebar → Serving → `au_east_llm_inregion`

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a -- Classification test: outage cause from field notes

# COMMAND ----------

test_outage_texts = [
    ("Storm knocked over a 66kV feeder pole near Dandenong Creek. Wire down, roads closed.",
     "WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN"),
    ("Excavator struck underground 11kV cable during council roadworks in Footscray.",
     "WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN"),
    ("Transformer bushings failed at Essendon zone substation. OEM bulletin related issue.",
     "WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN"),
]

print("CLASSIFICATION TEST -- Outage Cause from Field Notes")
print("=" * 60)
for text, categories in test_outage_texts:
    result = spark.sql(f"""
        SELECT {CATALOG}.ai_functions.classify_text(
            '{text.replace("'", "''")}',
            '{categories}',
            'Australian electricity distribution network operations'
        ) AS classification
    """).collect()[0][0]
    print(f"\nText:   {text[:80]}")
    print(f"Result: {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b -- Summarisation test: regulatory report extract

# COMMAND ----------

SAMPLE_REPORT_TEXT = """
The Distribution Annual Planning Report for FY2024 identifies three critical
augmentation projects requiring capital investment in the VIC1 distribution
zone. The Essendon 66kV substation has reached 97% of rated capacity during
summer peak conditions, exceeding the AER's N-1 security standard threshold
of 90%. The Ringwood 110kV feeder has experienced three voltage violation
events in the past 12 months, with load growth forecast to increase violations
to 8 events per year by 2026. Capital expenditure requirements are estimated
at $47.2M for Essendon augmentation, $23.8M for Ringwood feeder reinforcement,
and $12.1M for the Footscray cable replacement. The total program is
$83.1M over three years. AER regulatory approval is required under the
AEMC's Distribution Reliability Minimum Standards by June 2025.
"""

print("SUMMARISATION TEST -- Three audiences, 60 words each")
print("=" * 60)
for audience in ["EXECUTIVE", "TECHNICAL", "OPERATIONAL"]:
    result = spark.sql(f"""
        SELECT {CATALOG}.ai_functions.summarise_text(
            '{SAMPLE_REPORT_TEXT.strip().replace(chr(10), " ").replace("'", "''")}',
            60,
            '{audience}'
        ) AS summary
    """).collect()[0][0]
    print(f"\n[{audience}]")
    print(f"  {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3c -- Structured extraction test: maintenance work order

# COMMAND ----------

WORK_ORDER_TEXT = """
Work Order #WO-2024-08341
Date: 14 August 2024
Technician: J. Smith (ID: T-4821)
Asset: Dandenong Zone Substation - Transformer T3 (66kV/22kV, 40MVA)
Asset ID: ZS-DAND-T3

Fault Description:
On inspection found oil leak from bushing seal on 66kV HV winding. Estimated
oil loss approximately 15 litres. Partial discharge activity detected on
phase B bushing using UHF sensor (PD level: 450 pC at 66kV). Transformer
oil sample sent to Doble Engineering for DGA analysis (sample ref: OIL-2024-4521).

Actions Taken:
1. Temporary de-energisation approved by AEMO (AEMO Outage Reference: AEMO-OUT-240814-002)
2. Emergency oil top-up performed (15L Shell Diala S4 ZX-I added)
3. Bushing cleaned and temporary sealant applied
4. Partial discharge test repeated: PD level reduced to 85 pC (within acceptable limits)
5. Re-energised at 09:47 AEST

Next Actions:
- Full bushing replacement required within 90 days (by 12 November 2024)
- Spare bushing ordered from ABB Australia (order #ABB-AU-2024-7734)
- DGA results expected in 5 business days

Hours worked: 6.5h (2 technicians)
Parts used: Shell Diala S4 ZX-I oil (15L), temporary bushing sealant kit
"""

EXTRACT_SCHEMA = """{
  "work_order_id": "string",
  "work_date": "date (YYYY-MM-DD)",
  "asset_id": "string",
  "asset_name": "string",
  "fault_type": "string (one word or short phrase)",
  "aemo_outage_reference": "string or null",
  "hours_worked": "number",
  "next_action_deadline": "date (YYYY-MM-DD) or null",
  "oil_added_litres": "number or null"
}"""

print("EXTRACTION TEST -- Maintenance Work Order")
print("=" * 60)
result = spark.sql(f"""
    SELECT {CATALOG}.ai_functions.extract_json(
        '{WORK_ORDER_TEXT.strip().replace(chr(10), " ").replace("'", "''")}',
        '{EXTRACT_SCHEMA.replace(chr(10), " ").replace("'", "''")}'
    ) AS extracted
""").collect()[0][0]

print(result)
try:
    parsed = json.loads(result)
    print("\nParsed fields:")
    for k, v in parsed.items():
        print(f"  {k}: {v}")
except json.JSONDecodeError:
    print("\nNote: clean up JSON if model added extra text around the object.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3d -- Australian PII detection

# COMMAND ----------

PII_TEST_TEXTS = [
    "Customer TFN 123 456 782 has lodged a complaint about meter NMI Q1234567890 readings.",
    "Invoice from AusNet Services Ltd ABN 52 741 965 080 for network services.",
    "Customer Medicare card 2345 67891 0 -- please verify before processing rebate.",
    "The Essendon substation recorded peak demand of 38.4 MW on 15 January 2024.",
]

print("AUSTRALIAN PII DETECTION TEST")
print("=" * 60)
for text in PII_TEST_TEXTS:
    result = spark.sql(f"""
        SELECT {CATALOG}.ai_functions.detect_au_pii(
            '{text.replace("'", "''")}'
        ) AS pii_result
    """).collect()[0][0]

    print(f"\nText:   {text[:80]}")
    try:
        pii = json.loads(result)
        print(f"  Contains PII : {pii.get('contains_pii')}")
        print(f"  Types found  : {pii.get('pii_types_found', [])}")
        print(f"  Risk level   : {pii.get('risk_level')}")
    except Exception:
        print(f"  Raw result: {result[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4 -- Applied Example: Bulk Classification of Outage Field Notes

# COMMAND ----------

# Add unstructured field notes column if it does not exist
spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.outages
ADD COLUMN IF NOT EXISTS field_notes STRING
COMMENT 'Unstructured field technician notes describing the outage cause and restoration actions'
""")

# Seed sample field notes for each cause category
from pyspark.sql.functions import col, when, lit

field_notes_map = {
    "WEATHER":           "Storm damage to overhead lines. Strong winds caused conductor to sag into trees along the creek corridor. Supply restored after vegetation cleared and conductor re-tensioned.",
    "EQUIPMENT_FAILURE": "Transformer failure at zone substation. OC relay operated. Fault investigation found insulation breakdown on 22kV winding. Emergency transformer swap-out performed.",
    "VEGETATION":        "Tree branch contact with 11kV bare conductor. Branch fell during calm conditions, possibly due to disease. Tree removed and conductor inspected prior to re-energisation.",
    "THIRD_PARTY":       "Third-party cable strike during civil works. Excavator operator failed to dial before dig. Immediate isolation and cable repair. Regulatory notification sent to Energy Safe Victoria.",
    "UNKNOWN":           "Supply loss detected by SCADA at 03:22. No obvious fault found on patrol. Supply restored by switching operation. Root cause investigation ongoing.",
}

for cause, note in field_notes_map.items():
    spark.sql(f"""
        UPDATE {CATALOG}.{SCHEMA}.outages
        SET field_notes = '{note}'
        WHERE cause_category = '{cause}'
          AND field_notes IS NULL
    """)

print("Field notes seeded.")
spark.table(f"{CATALOG}.{SCHEMA}.outages").select(
    "outage_id", "cause_category", "field_notes"
).show(5, truncate=60)

# COMMAND ----------

# Classify outage field notes using the in-region function
outages_with_notes = spark.sql(f"""
    SELECT
        outage_id,
        cause_category                                    AS recorded_cause,
        field_notes,
        {CATALOG}.ai_functions.classify_text(
            field_notes,
            'WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN',
            'Australian electricity distribution network field operations'
        )                                                 AS ai_classified_cause
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE field_notes IS NOT NULL
    LIMIT 10
""")

outages_with_notes.show(truncate=50)

# COMMAND ----------

# Measure classification agreement rate
spark.sql(f"""
SELECT
    COUNT(*)                                                                AS total,
    SUM(CASE WHEN recorded_cause = ai_classified_cause THEN 1 ELSE 0 END) AS agreements,
    ROUND(
        SUM(CASE WHEN recorded_cause = ai_classified_cause THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    )                                                                       AS agreement_pct
FROM (
    SELECT
        cause_category AS recorded_cause,
        {CATALOG}.ai_functions.classify_text(
            field_notes,
            'WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN',
            'Australian electricity distribution network field operations'
        ) AS ai_classified_cause
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE field_notes IS NOT NULL
)
""").show()

# COMMAND ----------

# MAGIC %md
# MAGIC **Checkpoint:** Agreement rate of 70-100% is expected for seeded data with clear categories. Real-world field notes typically land at 65-85%; adding 2-3 few-shot examples to the prompt lifts this to 85-95%.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5 -- Extract Equipment Details from Work Orders

# COMMAND ----------

# Create work orders table
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.work_orders (
    work_order_id  STRING    COMMENT 'Work order identifier, e.g. WO-2024-08341',
    asset_id       STRING    COMMENT 'FK to assets.asset_id',
    created_date   DATE      COMMENT 'Date work order was raised',
    work_notes     STRING    COMMENT 'Unstructured technician notes from field',
    status         STRING    COMMENT 'OPEN, IN_PROGRESS, CLOSED',
    created_at     TIMESTAMP COMMENT 'Record creation timestamp'
)
USING DELTA
COMMENT 'Maintenance work orders. work_notes contains unstructured field technician text for AI extraction.'
""")

# Seed with realistic work orders
import uuid
from datetime import datetime, date
from pyspark.sql import Row

work_order_templates = [
    {
        "notes": "Transformer T3 bushing oil leak identified during routine thermography scan. "
                 "66kV/22kV, 40MVA unit. Partial discharge 450pC phase B. Oil sample WO-OIL-001 sent to Doble. "
                 "Temporary repair completed. Full bushing replacement required by 01 Nov 2024. "
                 "Estimate 16 hours work, 2 technicians required.",
    },
    {
        "notes": "Switch bay 4B circuit breaker SF6 gas pressure alarm. Asset: 110kV CB at Sunshine zone sub. "
                 "Gas pressure: 0.42 MPa (minimum 0.45 MPa for operation). Gas top-up performed to 0.60 MPa. "
                 "CB operated successfully post top-up. Schedule full SF6 service in 6 months.",
    },
    {
        "notes": "Routine inspection of 11kV feeder F23 recloser. Unit: Noja Power OSM-15. "
                 "Found insulation cracking on phase C arrestor. Arrestor replaced from stores. "
                 "SCADA comms fault identified - radio module requires replacement. "
                 "Radio module on order, ETA 3 weeks.",
    },
]

asset_ids_rows = spark.table(f"{CATALOG}.{SCHEMA}.assets").select("asset_id").limit(3).collect()
wo_rows = []
for i, template in enumerate(work_order_templates):
    wo_rows.append(Row(
        work_order_id = f"WO-2024-{8341 + i:05d}",
        asset_id      = asset_ids_rows[i].asset_id if i < len(asset_ids_rows) else None,
        created_date  = date(2024, 8, 14 + i),
        work_notes    = template["notes"],
        status        = "CLOSED" if i == 0 else "IN_PROGRESS",
        created_at    = datetime.now()
    ))

spark.createDataFrame(wo_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.work_orders")
print(f"Work orders in table: {spark.table(f'{CATALOG}.{SCHEMA}.work_orders').count()}")

# COMMAND ----------

# Extract structured fields from work order notes using in-region AI
WO_EXTRACT_SCHEMA = """{
  "asset_voltage_kv": "number or null",
  "fault_type": "string - short description",
  "action_taken": "string - main action taken",
  "parts_used": "array of strings - list of parts/materials used",
  "follow_up_required": "boolean",
  "estimated_hours": "number or null",
  "urgency": "one of: IMMEDIATE, WITHIN_30_DAYS, WITHIN_90_DAYS, ROUTINE or null"
}"""

result_df = spark.sql(f"""
SELECT
    work_order_id,
    status,
    LEFT(work_notes, 80)    AS notes_preview,
    {CATALOG}.ai_functions.extract_json(
        work_notes,
        '{WO_EXTRACT_SCHEMA.replace(chr(10), " ").replace("'", "''")}'
    )                       AS extracted_json
FROM {CATALOG}.{SCHEMA}.work_orders
""")

result_df.show(truncate=50)

# COMMAND ----------

# Parse the JSON and write to a structured table
from pyspark.sql.functions import from_json, col as c
from pyspark.sql.types import StructType, StructField, StringType, BooleanType, DoubleType, ArrayType

extraction_schema = StructType([
    StructField("asset_voltage_kv",   DoubleType(),            True),
    StructField("fault_type",         StringType(),            True),
    StructField("action_taken",       StringType(),            True),
    StructField("parts_used",         ArrayType(StringType()), True),
    StructField("follow_up_required", BooleanType(),           True),
    StructField("estimated_hours",    DoubleType(),            True),
    StructField("urgency",            StringType(),            True),
])

parsed_df = (
    result_df
    .withColumn("extracted", from_json(c("extracted_json"), extraction_schema))
    .select(
        "work_order_id",
        "status",
        c("extracted.fault_type"),
        c("extracted.urgency"),
        c("extracted.follow_up_required"),
        c("extracted.estimated_hours"),
        c("extracted.action_taken"),
    )
)

parsed_df.show(truncate=60)

# Save structured results to Delta
parsed_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.work_orders_extracted")
print(f"Saved to: {CATALOG}.{SCHEMA}.work_orders_extracted")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6 -- Pattern Reference Card

# COMMAND ----------

print("""
AU EAST AI FUNCTIONS -- IN-REGION PATTERN REFERENCE
=====================================================

SETUP (once per workspace):
  1. Deploy PT endpoint:
       model: databricks-claude-haiku-4-5   ✅ in-region PT for AU East

  2. UC wrapper functions in catalog.ai_functions:
       classify_text(text, categories, domain_context)
       summarise_text(text, max_words, audience)
       extract_json(text, json_schema)
       detect_au_pii(text)

IN SQL (all in-region):
  SELECT catalog.ai_functions.classify_text(col, 'A,B', 'domain') FROM tbl
  SELECT catalog.ai_functions.summarise_text(doc, 100, 'EXECUTIVE') FROM tbl
  SELECT catalog.ai_functions.extract_json(notes, '{"field": "type"}') FROM tbl
  SELECT catalog.ai_functions.detect_au_pii(customer_text) FROM tbl

DO NOT USE (cross-geo for AU):
  ai_classify(), ai_summarize(), ai_extract(), ai_generate()

IN-REGION EMBEDDING (for Vector Search / Genie RAG):
  USE:   databricks-qwen3-embedding-0-6b
  AVOID: databricks-gte-large-en  (cross-geo)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 04 -- Review Questions
# MAGIC
# MAGIC **Q1.** A colleague says "I'll just use `ai_classify()` -- it's faster." What are the two reasons this is a problem for your SOCI Act / critical infrastructure regulated energy company?
# MAGIC
# MAGIC **Q2.** The PT endpoint is deployed and working. The model vendor releases a newer model. How do you update all AI function calls without changing every notebook or query?
# MAGIC
# MAGIC **Q3.** A work order extraction returns `null` for `estimated_hours` even though the text says "16 hours work". What might cause this, and how would you fix the schema hint?
# MAGIC
# MAGIC **Q4.** Which five PII types does `detect_au_pii` detect? Which one is specific to the energy industry?
# MAGIC
# MAGIC **Q5.** The classification agreement rate is 70%. List three ways to improve it without switching to a larger model.
# MAGIC
# MAGIC **Proceed to Lab 05 when ready.**
