# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 04: AI Functions — In-Region Pattern for Australia East — SOLUTION
# MAGIC
# MAGIC **Workshop:** Genie Spaces & AI Features — Australian Regulated Industries
# MAGIC **Duration:** 40–45 minutes
# MAGIC **Role:** Data Engineer / ML Engineer
# MAGIC **Prerequisite:** Labs 01–02 complete — `workshop.energy_nem` tables exist
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC 1. Understand **why** default AI Functions are cross-geo and why that matters
# MAGIC 2. Deploy a **Provisioned Throughput (PT) endpoint** in AU East as the in-region AI router
# MAGIC 3. Create a **UC wrapper function** that routes all AI calls through the PT endpoint
# MAGIC 4. Implement classification, summarisation, and extraction using the in-region pattern
# MAGIC 5. Build Australian-specific **PII masking** (TFN, Medicare, ABN, ACN detection)
# MAGIC 6. Apply to realistic energy domain scenarios: outage classification and work order extraction
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The Core Problem: AI Functions Are Cross-Geo by Default
# MAGIC
# MAGIC ```
# MAGIC DEFAULT (cross-geo) — DO NOT USE for regulated AU data:
# MAGIC ─────────────────────────────────────────────────────────
# MAGIC  AU East workspace
# MAGIC       │  ai_classify(text, ...)
# MAGIC       │
# MAGIC       └──► FMAPI endpoint (US East / multi-region)
# MAGIC                       ── text crosses geo boundary ──►
# MAGIC
# MAGIC IN-REGION (correct pattern):
# MAGIC ─────────────────────────────────────────────────────────
# MAGIC  AU East workspace
# MAGIC       │  ai_query('au_east_llm_inregion', prompt)
# MAGIC       │
# MAGIC       └──► Provisioned Throughput endpoint (Australia East)
# MAGIC                       ── text stays in region ──►
# MAGIC ```
# MAGIC
# MAGIC **Regulatory context:** Under the Australian Privacy Act, AEMO's ISP, and the AER's
# MAGIC Cyber Security Guidelines, operational technology data and personal information
# MAGIC (customer NMIs, consumption data) must not be processed outside Australia without
# MAGIC explicit consent or a cross-border data agreement.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0 mlflow>=2.14
dbutils.library.restartPython()

# COMMAND ----------

import requests, time, json
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServedEntityInput, EndpointCoreConfigInput, TrafficConfig, Route
)

w    = WorkspaceClient()
HOST = spark.conf.get("spark.databricks.workspaceUrl")
CATALOG = "workshop"
SCHEMA  = "energy_nem"

def hdrs():
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print(f"Connected: {HOST}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Understand the Designated Services Classification
# MAGIC
# MAGIC Databricks AI Functions (`ai_classify`, `ai_summarize`, `ai_extract`, `ai_generate`) call
# MAGIC the **Foundation Model API (FMAPI)**. In AU East, FMAPI is a "Designated Service" under
# MAGIC the Databricks Cloud Agreement — meaning the underlying model inference may run
# MAGIC in a different region (typically US East 1).
# MAGIC
# MAGIC **This is distinct from compute:** Your Delta tables, jobs, and clusters always run in AU East.
# MAGIC But the model serving inference for FMAPI pay-per-token models currently routes globally.
# MAGIC
# MAGIC ### The Workaround
# MAGIC
# MAGIC Deploy a **Provisioned Throughput (PT)** endpoint on an explicitly AU East serving endpoint.
# MAGIC PT endpoints run on your workspace's compute region — guaranteed AU East inference.
# MAGIC Replace all `ai_*` function calls with `ai_query('your_pt_endpoint', prompt)`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Deploy a Provisioned Throughput Endpoint (AU East)

# COMMAND ----------

# SOLUTION: endpoint name — change if another group already claimed this name
PT_ENDPOINT_NAME = "au_east_llm_inregion"

# Available in-region models for AU East (confirmed May 2026):
# - meta-llama/Meta-Llama-3.1-8B-Instruct   (smallest, fastest, cheapest)
# - meta-llama/Meta-Llama-3.1-70B-Instruct  (balanced quality/cost)
# - meta-llama/Meta-Llama-3.3-70B-Instruct  (recommended for complex tasks)
# - mistralai/Mistral-7B-Instruct-v0.2       (fast, good for classification)
#
# NOT available in-region for AU East (cross-geo):
# - databricks-claude-sonnet-4 (cross-geo for AU as of May 2026)
# - databricks-meta-llama-3-1-405b (cross-geo for AU)
#
# Use Meta-Llama-3.1-8B for this workshop (most cost-effective, in-region)

PT_MODEL_NAME = "databricks-claude-haiku-4-5"

# Minimum scale (0 = scale to zero when idle, reduces cost for workshop)
PT_SCALE_TO_ZERO = True

def create_pt_endpoint(endpoint_name: str, model_name: str) -> str:
    """
    Creates a Provisioned Throughput serving endpoint.
    Returns the endpoint name once it is ready.
    """
    print(f"Creating PT endpoint: {endpoint_name}")
    print(f"Model: {model_name}")
    print("This typically takes 5–10 minutes...")

    try:
        # Check if already exists
        existing = w.serving_endpoints.get(endpoint_name)
        print(f"Endpoint already exists (state: {existing.state.ready}). Reusing.")
        return endpoint_name
    except Exception:
        pass  # Doesn't exist yet

    # Create the endpoint
    w.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    name=f"{endpoint_name}_entity",
                    entity_name=model_name,
                    entity_version="1",
                    min_provisioned_throughput=0,  # scale to zero when idle
                    max_provisioned_throughput=1000,  # tokens per second
                )
            ],
            traffic_config=TrafficConfig(
                routes=[Route(served_model_name=f"{endpoint_name}_entity", traffic_percentage=100)]
            )
        ),
        timeout=600  # 10 minutes
    )

    print(f"Endpoint '{endpoint_name}' is ready.")
    return endpoint_name


# Create the endpoint (runs synchronously — wait for READY state)
# NOTE: This takes 5–10 minutes. Proceed with reviewing the next cells while waiting.
ENDPOINT_NAME = create_pt_endpoint(PT_ENDPOINT_NAME, PT_MODEL_NAME)
print(f"\nEndpoint name for all subsequent cells: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### While the endpoint starts: verify the endpoint is AU East
# MAGIC
# MAGIC Once the endpoint is ready, run this cell to confirm it is serving in AU East.

# COMMAND ----------

def verify_endpoint_region(endpoint_name: str) -> None:
    """Confirm endpoint is ready and log its configuration."""
    ep = w.serving_endpoints.get(endpoint_name)
    print(f"Endpoint: {ep.name}")
    print(f"State:    {ep.state.ready if ep.state else 'unknown'}")

    config = ep.config
    if config and config.served_entities:
        for entity in config.served_entities:
            print(f"Model:    {entity.entity_name}")
            print(f"Min TPU:  {entity.min_provisioned_throughput}")
            print(f"Max TPU:  {entity.max_provisioned_throughput}")

    # The endpoint URL always points to your workspace region (AU East)
    print(f"\nInference URL: https://{HOST}/serving-endpoints/{endpoint_name}/invocations")
    print("This URL routes to AU East compute — no cross-geo data transfer.")


try:
    verify_endpoint_region(ENDPOINT_NAME)
except Exception as e:
    print(f"Endpoint not yet ready: {e}")
    print("Wait a few more minutes and re-run this cell.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Create a UC Wrapper Function
# MAGIC
# MAGIC Rather than calling `ai_query('endpoint_name', ...)` everywhere, create a
# MAGIC Unity Catalog function that wraps the PT endpoint. This gives you:
# MAGIC - A single place to swap the endpoint without updating every query
# MAGIC - SQL-accessible callable from Genie, notebooks, and jobs
# MAGIC - Consistent prompt templating

# COMMAND ----------

# TODO: replace endpoint name if you used a different name above
ENDPOINT_FQN = ENDPOINT_NAME  # just the endpoint name; ai_query resolves it

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.ai_functions")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a — Generic classifier function

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.classify_text(
    text_input STRING COMMENT 'The text to classify',
    categories STRING COMMENT 'Comma-separated list of valid categories',
    domain_context STRING COMMENT 'Domain context to guide the classifier'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Classifies text into one of the provided categories using the in-region AU East PT endpoint.
All inference runs in Australia East. No data leaves the region.'
RETURN
    ai_query(
        '{ENDPOINT_FQN}',
        CONCAT(
            'You are a text classifier for ', domain_context, '. ',
            'Classify the following text into EXACTLY ONE of these categories: ', categories, '. ',
            'Respond with ONLY the category name — no explanation, no punctuation, no other text.\\n\\n',
            'Text: ', text_input
        )
    )
""")
print(f"Created: {CATALOG}.ai_functions.classify_text")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b — Summarisation function

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.summarise_text(
    text_input   STRING COMMENT 'The text to summarise',
    max_words    INT    COMMENT 'Maximum word count for the summary (e.g. 50, 100, 200)',
    audience     STRING COMMENT 'Target audience: EXECUTIVE, TECHNICAL, OPERATIONAL'
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
# MAGIC ### 3c — Structured extraction function

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.extract_json(
    text_input STRING COMMENT 'The text to extract from',
    json_schema STRING COMMENT 'JSON schema describing fields to extract, as a string'
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
# MAGIC ### 3d — PII detection function (Australian-specific)

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.ai_functions.detect_au_pii(
    text_input STRING COMMENT 'Text to scan for Australian PII'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Detects Australian PII (TFN, Medicare, ABN, ACN, NMI) in text.
Returns JSON with detected PII types and whether masking is required.
Uses AU East in-region endpoint — PII data never leaves Australia.'
RETURN
    ai_query(
        '{ENDPOINT_FQN}',
        CONCAT(
            'Analyse the following text for Australian personally identifiable information (PII). ',
            'Check for: ',
            '(1) Tax File Number (TFN): 8-9 digit number, sometimes formatted as XXX XXX XXX, ',
            '(2) Medicare Number: 10-digit number starting with 2-6, sometimes formatted with spaces, ',
            '(3) ABN (Australian Business Number): 11 digits, often formatted XX XXX XXX XXX, ',
            '(4) ACN (Australian Company Number): 9 digits, often formatted XXX XXX XXX, ',
            '(5) NMI (National Metering Identifier): 10-11 alphanumeric characters starting with a letter. ',
            'Return a JSON object with these fields: ',
            '{"contains_pii": true/false, ',
            '"pii_types_found": ["TFN","MEDICARE","ABN","ACN","NMI"], ',
            '"masking_required": true/false, ',
            '"risk_level": "HIGH/MEDIUM/LOW/NONE"}. ',
            'Return ONLY the JSON — no explanation.\\n\\nText: ', text_input
        )
    )
""")
print(f"Created: {CATALOG}.ai_functions.detect_au_pii")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Test the Wrapper Functions

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a — Classification test

# COMMAND ----------

# Test: classify outage cause from unstructured field notes
test_outage_texts = [
    ("Storm knocked over a 66kV feeder pole near Dandenong Creek. Wire down, roads closed.",
     "WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN"),
    ("Excavator struck underground 11kV cable during council roadworks in Footscray.",
     "WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN"),
    ("Transformer bushings failed at Essendon zone substation. OEM bulletin related issue.",
     "WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN"),
]

print("CLASSIFICATION TEST — Outage Cause from Field Notes")
print("=" * 60)
for text, categories in test_outage_texts:
    result = spark.sql(f"""
        SELECT {CATALOG}.ai_functions.classify_text(
            '{text.replace("'", "''")}',
            '{categories}',
            'Australian electricity distribution network operations'
        ) AS classification
    """).collect()[0][0]
    print(f"\nText:   {text[:80]}...")
    print(f"Result: {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b — Summarisation test

# COMMAND ----------

# Test: summarise a regulatory report extract
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

print("SUMMARISATION TEST")
print("=" * 60)
for audience in ["EXECUTIVE", "TECHNICAL", "OPERATIONAL"]:
    result = spark.sql(f"""
        SELECT {CATALOG}.ai_functions.summarise_text(
            '{SAMPLE_REPORT_TEXT.strip().replace(chr(10), " ").replace("'", "''")}',
            60,
            '{audience}'
        ) AS summary
    """).collect()[0][0]
    print(f"\n[{audience} - 60 words]")
    print(f"  {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4c — Structured extraction test

# COMMAND ----------

# Test: extract structured data from a maintenance work order
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

print("EXTRACTION TEST — Work Order")
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
    print("Note: clean up the JSON if model added extra text")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4d — Australian PII Detection

# COMMAND ----------

PII_TEST_TEXTS = [
    # Contains TFN and NMI
    "Customer TFN 123 456 782 has lodged a complaint about meter NMI Q1234567890 readings.",
    # Contains ABN
    "Invoice from AusNet Services Ltd ABN 52 741 965 080 for network services.",
    # Contains Medicare
    "Customer Medicare card 2345 67891 0 — please verify before processing rebate.",
    # No PII
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
        print(f"  Contains PII: {pii.get('contains_pii')}")
        print(f"  Types found:  {pii.get('pii_types_found', [])}")
        print(f"  Risk level:   {pii.get('risk_level')}")
    except:
        print(f"  Raw result: {result[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Applied Example: Classify Outage Reports (Bulk)
# MAGIC
# MAGIC Apply the in-region classification pattern to the outages table.
# MAGIC This is the foundation for the batch pipeline in Lab 05.

# COMMAND ----------

# Add a sample unstructured description column to outages
spark.sql(f"""
ALTER TABLE {CATALOG}.{SCHEMA}.outages
ADD COLUMN IF NOT EXISTS field_notes STRING
COMMENT 'Unstructured field technician notes describing the outage cause and restoration actions'
""")

# Seed sample field notes for the 30 outage rows
from pyspark.sql.functions import col, when, lit

field_notes_map = {
    "WEATHER":            "Storm damage to overhead lines. Strong winds caused conductor to sag into trees along the creek corridor. Supply restored after vegetation cleared and conductor re-tensioned.",
    "EQUIPMENT_FAILURE":  "Transformer failure at zone substation. OC relay operated. Fault investigation found insulation breakdown on 22kV winding. Emergency transformer swap-out performed.",
    "VEGETATION":         "Tree branch contact with 11kV bare conductor. Branch fell during calm conditions, possibly due to disease. Tree removed and conductor inspected prior to re-energisation.",
    "THIRD_PARTY":        "Third-party cable strike during civil works. Excavator operator failed to dial before dig. Immediate isolation and cable repair. Regulatory notification sent to Energy Safe Victoria.",
    "UNKNOWN":            "Supply loss detected by SCADA at 03:22. No obvious fault found on patrol. Supply restored by switching operation. Root cause investigation ongoing.",
}

# Update each cause_category with corresponding field notes
for cause, note in field_notes_map.items():
    spark.sql(f"""
        UPDATE {CATALOG}.{SCHEMA}.outages
        SET field_notes = '{note}'
        WHERE cause_category = '{cause}'
          AND field_notes IS NULL
    """)

print("Field notes seeded.")
spark.table(f"{CATALOG}.{SCHEMA}.outages").select("outage_id", "cause_category", "field_notes").show(5, truncate=60)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Classify outage field notes using the in-region function

# COMMAND ----------

# Read outages with field notes and classify using in-region function
outages_with_notes = spark.sql(f"""
    SELECT
        outage_id,
        cause_category                           AS recorded_cause,
        field_notes,
        {CATALOG}.ai_functions.classify_text(
            field_notes,
            'WEATHER,EQUIPMENT_FAILURE,VEGETATION,THIRD_PARTY,UNKNOWN',
            'Australian electricity distribution network field operations'
        )                                        AS ai_classified_cause
    FROM {CATALOG}.{SCHEMA}.outages
    WHERE field_notes IS NOT NULL
    LIMIT 10
""")

outages_with_notes.show(truncate=50)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Measure classification agreement rate

# COMMAND ----------

spark.sql(f"""
SELECT
    COUNT(*)                                                   AS total,
    SUM(CASE WHEN recorded_cause = ai_classified_cause THEN 1 ELSE 0 END) AS agreements,
    ROUND(
        SUM(CASE WHEN recorded_cause = ai_classified_cause THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    )                                                         AS agreement_pct
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
# MAGIC ## Step 6 — Extract Equipment Details from Work Orders
# MAGIC
# MAGIC Demonstrate end-to-end extraction pipeline: unstructured text → structured Delta table.

# COMMAND ----------

# Create work orders table for this example
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.work_orders (
    work_order_id  STRING    COMMENT 'Work order identifier, e.g. WO-2024-08341',
    asset_id       STRING    COMMENT 'FK → assets.asset_id',
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
from datetime import datetime, date, timedelta
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
print(f"Work orders created: {spark.table(f'{CATALOG}.{SCHEMA}.work_orders').count()}")

# COMMAND ----------

# Extract structured data from work order notes using in-region AI
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
print(f"Structured work order data saved to {CATALOG}.{SCHEMA}.work_orders_extracted")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 — Pattern Reference Card
# MAGIC
# MAGIC All patterns from this lab in one summary for quick reference.

# COMMAND ----------

print("""
AU EAST AI FUNCTIONS — IN-REGION PATTERN REFERENCE
====================================================

SETUP (once per workspace):
  1. Deploy PT endpoint:
       endpoint_name = "au_east_llm_inregion"
       model_name    = "databricks-claude-haiku-4-5"

  2. Create UC wrapper functions in catalog.ai_functions:
       classify_text(text, categories, domain_context)
       summarise_text(text, max_words, audience)
       extract_json(text, json_schema)
       detect_au_pii(text)

USAGE IN SQL (all in-region):
  -- Classification
  SELECT catalog.ai_functions.classify_text(
      my_text_col,
      'TYPE_A,TYPE_B,TYPE_C',
      'domain description'
  ) FROM my_table

  -- Summarisation
  SELECT catalog.ai_functions.summarise_text(document_col, 100, 'EXECUTIVE')
  FROM regulatory_reports

  -- Extraction
  SELECT catalog.ai_functions.extract_json(notes_col, '{"field": "type"}')
  FROM work_orders

  -- PII Detection
  SELECT catalog.ai_functions.detect_au_pii(customer_text_col)
  FROM customer_messages

DO NOT USE (cross-geo for AU):
  ai_classify(text, labels)          -- routes to US East
  ai_summarize(text)                 -- routes to US East
  ai_extract(text, object_types)     -- routes to US East
  ai_generate(prompt)                -- routes to US East

EMBEDDING MODEL FOR VECTOR SEARCH / GENIE RAG:
  In-region:   databricks-qwen3-embedding-0-6b  ← USE THIS
  Cross-geo:   databricks-gte-large-en           ← AVOID for regulated AU data
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab 04 — Review Questions
# MAGIC
# MAGIC 1. A colleague says "I'll just use `ai_classify()` — it's faster and easier than
# MAGIC    deploying a PT endpoint." What are the two reasons this is a problem for your
# MAGIC    energy company customer?
# MAGIC
# MAGIC 2. The PT endpoint is deployed and working. A week later, the model vendor releases
# MAGIC    a newer model version. How do you update all AI function calls to use the new model
# MAGIC    without changing every notebook?
# MAGIC
# MAGIC 3. A work order extraction returns `null` for `estimated_hours` even though the text
# MAGIC    says "16 hours". What might be causing this, and how would you fix the prompt?
# MAGIC
# MAGIC 4. Which PII types are detected by the `detect_au_pii` function? Which type is specific
# MAGIC    to the energy industry (not just general Australian PII)?
# MAGIC
# MAGIC 5. The classification agreement rate between `recorded_cause` and `ai_classified_cause`
# MAGIC    is 70%. What are three ways you could improve it?
# MAGIC
# MAGIC **Proceed to Lab 05 when ready.**
