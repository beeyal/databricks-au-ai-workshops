# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A5C 0%, #FF3621 100%); padding: 24px 32px; border-radius: 10px; margin-bottom: 8px">
# MAGIC   <h1 style="color: white; margin: 0; font-size: 28px; font-family: 'DM Sans', sans-serif">
# MAGIC     Lab 05 -- Batch AI Processing Pipeline
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
# MAGIC     <td style="padding: 8px 16px">Data Engineer</td>
# MAGIC   </tr>
# MAGIC   <tr>
# MAGIC     <td style="padding: 8px 16px; background: #F4F4F4; border-radius: 4px"><strong>Prerequisite</strong></td>
# MAGIC     <td style="padding: 8px 16px">Lab 04 complete -- PT endpoint deployed and UC wrapper functions created</td>
# MAGIC   </tr>
# MAGIC </table>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Objectives
# MAGIC
# MAGIC | # | Objective |
# MAGIC |---|-----------|
# MAGIC | 1 | Process large volumes of unstructured regulatory documents with AI at scale |
# MAGIC | 2 | Use Spark + `ai_query` for distributed, parallelised inference |
# MAGIC | 3 | Implement the **incremental processing pattern** (only process new/changed records) |
# MAGIC | 4 | Handle errors gracefully with `failOnError => false` |
# MAGIC | 5 | Write AI-enriched results to Delta with `OPTIMIZE` and `ZORDER` |
# MAGIC | 6 | Schedule the pipeline as a Databricks Job with monitoring |
# MAGIC | 7 | Estimate and optimise cost before running a production batch |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Pipeline Architecture
# MAGIC
# MAGIC ```
# MAGIC regulatory_reports (Bronze Delta -- raw document text)
# MAGIC         |
# MAGIC         v  ai_query (in-region PT endpoint -- AU East)
# MAGIC         |  +-- classify document type
# MAGIC         |  +-- extract key dates and entities
# MAGIC         |  +-- summarise for dashboard display
# MAGIC         |
# MAGIC         v
# MAGIC processed_reports (Silver Delta -- AI-enriched metadata)
# MAGIC         |
# MAGIC         v
# MAGIC Genie Space + AI/BI Dashboard
# MAGIC ```
# MAGIC
# MAGIC <div style="background: #E8F8E8; padding: 12px 16px; border-radius: 6px; border-left: 4px solid #28A745; margin: 8px 0">
# MAGIC <strong>Data residency:</strong> Every <code>ai_query()</code> call in this pipeline uses the PT endpoint
# MAGIC deployed in Lab 04. No document text leaves Australia East.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 0 -- Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests, time, json
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DateType, BooleanType
from databricks.sdk import WorkspaceClient

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Workshop Configuration
# MAGIC > **Running in a customer environment?** Change the catalog name in the widget above to match
# MAGIC > what was set in `setup/00_workspace_setup.py` (default: `workshop_au`)

# COMMAND ----------
# Widget-based configuration — works in any customer Databricks environment
# These default values match what 00_workspace_setup.py creates
dbutils.widgets.text("catalog",     "workshop_au",          "Catalog name")
dbutils.widgets.text("schema",      "energy",               "Schema name")
dbutils.widgets.text("pt_endpoint", "au_east_llm_inregion", "PT endpoint name")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
PT_ENDPOINT  = dbutils.widgets.get("pt_endpoint")

print(f"Using catalog: {CATALOG}.{SCHEMA}")
print(f"PT endpoint:   {PT_ENDPOINT}")

# COMMAND ----------

w       = WorkspaceClient()
HOST    = spark.conf.get("spark.databricks.workspaceUrl")
# Configurable — change via widget above if running in customer environment
# CATALOG, SCHEMA, and PT_ENDPOINT are set by widgets above

# Configurable — change via widget above if running in customer environment
ENDPOINT_NAME = PT_ENDPOINT  # from widget, default "au_east_llm_inregion"

# Verify endpoint is ready before proceeding
try:
    ep = w.serving_endpoints.get(ENDPOINT_NAME)
    print(f"PT endpoint '{ENDPOINT_NAME}': {ep.state.ready}")
except Exception as e:
    print(f"WARNING: Could not verify endpoint: {e}")
    print("Ensure Lab 04 is complete and the endpoint is READY before continuing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1 -- Cost Estimation Before Running the Batch
# MAGIC
# MAGIC Run this cell before any AI processing. It calculates how many records are unprocessed
# MAGIC and estimates the inference cost so you can make an informed decision before committing
# MAGIC compute.
# MAGIC
# MAGIC <div style="background: #E8F4FD; padding: 12px 16px; border-radius: 6px; border-left: 4px solid #1B3A5C; margin: 8px 0">
# MAGIC <strong>Best practice:</strong> Always run cost estimation before a batch job in production.
# MAGIC For a daily pipeline processing 500 documents/day, a surprise 10x doc volume increase
# MAGIC will be caught here before it hits your PT endpoint budget.
# MAGIC </div>

# COMMAND ----------

def estimate_batch_cost(
    pending_count: int,
    avg_doc_chars: int = 3000,
    model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
) -> dict:
    """
    Estimates AI inference cost for a pending batch.
    Assumes 4 AI passes per document (classify + extract + 2x summarise).

    Cost model (approximate, check current Databricks pricing):
      PT Llama 3.1 8B: ~$0.004 per 1k input tokens, ~$0.006 per 1k output tokens
    """
    if pending_count == 0:
        return {"pending_count": 0, "estimated_cost_usd": 0.0, "estimated_cost_aud": 0.0}

    # Token estimation
    chars_per_doc    = avg_doc_chars
    prompt_overhead  = 300   # prompt template tokens per pass (instructions, schema)
    passes_per_doc   = 4     # classify + extract + executive summary + technical summary

    input_tokens_per_doc  = (chars_per_doc // 4) + prompt_overhead
    output_tokens_per_doc = 200  # avg output per pass

    total_input_tokens  = pending_count * passes_per_doc * input_tokens_per_doc
    total_output_tokens = pending_count * passes_per_doc * output_tokens_per_doc

    PRICE_INPUT_PER_1K  = 0.004  # USD per 1k input tokens (PT Llama 3.1 8B, approx)
    PRICE_OUTPUT_PER_1K = 0.006  # USD per 1k output tokens

    cost_usd = (
        (total_input_tokens  / 1000) * PRICE_INPUT_PER_1K +
        (total_output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    )

    AUD_USD_RATE = 0.65  # approximate -- update with current rate for accurate budgeting

    return {
        "model":                     model_name,
        "pending_count":             pending_count,
        "passes_per_doc":            passes_per_doc,
        "total_input_tokens":        total_input_tokens,
        "total_output_tokens":       total_output_tokens,
        "estimated_cost_usd":        round(cost_usd, 4),
        "estimated_cost_aud":        round(cost_usd / AUD_USD_RATE, 4),
        "cost_per_doc_usd":          round(cost_usd / pending_count, 6),
    }


def print_cost_estimate(estimate: dict) -> None:
    """Prints a cost estimate in a readable table format."""
    print("=" * 55)
    print("  PRE-RUN COST ESTIMATE")
    print("=" * 55)
    print(f"  Model              : {estimate['model']}")
    print(f"  Documents pending  : {estimate['pending_count']:,}")
    print(f"  AI passes / doc    : {estimate['passes_per_doc']}")
    print(f"  Input tokens total : {estimate['total_input_tokens']:,}")
    print(f"  Output tokens total: {estimate['total_output_tokens']:,}")
    print(f"  Estimated cost     : USD ${estimate['estimated_cost_usd']:.4f}")
    print(f"                       AUD ${estimate['estimated_cost_aud']:.4f}")
    print(f"  Cost per document  : USD ${estimate['cost_per_doc_usd']:.6f}")
    print("=" * 55)
    if estimate["pending_count"] == 0:
        print("  No pending records -- nothing to process.")
    elif estimate["estimated_cost_usd"] > 5.0:
        print("  WARNING: Estimated cost > USD $5. Consider reducing batch_size.")
    else:
        print("  Cost within normal range. Safe to proceed.")
    print("=" * 55)


# Count pending records now (before seeding, so may show 0 until Step 2)
try:
    pending_now = spark.sql(f"""
        SELECT COUNT(*) AS n
        FROM {CATALOG}.{SCHEMA}.regulatory_reports r
        LEFT ANTI JOIN {CATALOG}.{SCHEMA}.processed_reports p
            ON r.report_id = p.report_id
           AND p.processing_status = 'PROCESSED'
        WHERE r.document_text IS NOT NULL
          AND LENGTH(r.document_text) > 100
    """).collect()[0][0]
except Exception:
    pending_now = 0  # table may not exist yet -- will be created in Step 2

estimate = estimate_batch_cost(pending_count=pending_now)
print_cost_estimate(estimate)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (after seeding in Step 2, re-run this cell):**
# MAGIC ```
# MAGIC =======================================================
# MAGIC   PRE-RUN COST ESTIMATE
# MAGIC =======================================================
# MAGIC   Model              : meta-llama/Meta-Llama-3.1-8B-Instruct
# MAGIC   Documents pending  : 5
# MAGIC   AI passes / doc    : 4
# MAGIC   Input tokens total : 7,000
# MAGIC   Output tokens total: 4,000
# MAGIC   Estimated cost     : USD $0.0520
# MAGIC                        AUD $0.0800
# MAGIC   Cost per document  : USD $0.010400
# MAGIC =======================================================
# MAGIC   Cost within normal range. Safe to proceed.
# MAGIC =======================================================
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2 -- Seed Regulatory Reports with Realistic Document Text
# MAGIC
# MAGIC The `regulatory_reports` table from Lab 01 has placeholder text.
# MAGIC Replace it with longer, realistic regulatory document extracts that give the model
# MAGIC something meaningful to classify, extract, and summarise.

# COMMAND ----------

REGULATORY_DOCS = [
    {
        "report_type": "ANNUAL_PLANNING",
        "title":       "NEM Annual Planning Report FY2024 -- VIC1 Distribution Zone",
        "text": """
EXECUTIVE SUMMARY
This Annual Planning Report identifies network augmentation requirements for the Victorian
distribution network for the five-year period FY2025 to FY2029. The report is prepared in
accordance with the National Electricity Rules (NER) Chapter 5 and submitted to AEMO by
30 September 2024.

KEY FINDINGS
Three distribution feeders in the inner-north Melbourne network are forecast to exceed
summer peak rating by FY2026. The Essendon 66kV zone substation has reached 94% of rated
capacity during the February 2024 heatwave event, exceeding the N-1 security standard.
Load growth is driven by electric vehicle uptake (forecast 340,000 EVs by FY2027 in VIC1)
and rooftop solar export pressures.

CAPITAL EXPENDITURE REQUIREMENTS
Essendon Zone Substation Stage 2 augmentation: $47.2M (FY2025 construction start)
Ringwood 110kV feeder reinforcement: $23.8M (FY2026 construction start)
Footscray underground cable replacement: $12.1M (FY2025 construction start)
Total 5-year capital program: $143.6M

REGULATORY COMPLIANCE
All projects assessed under the Regulatory Investment Test for Distribution (RIT-D).
Essendon project passed RIT-D with Net Market Benefits of $12.4M NPV. Submissions to
AER under NER 5.17 to be lodged by 31 March 2025.

DATES
Submission date: 30 September 2024
AER review period: October 2024 to March 2025
Construction commencement: July 2025 (Essendon), January 2026 (Ringwood)
""",
    },
    {
        "report_type": "RELIABILITY_REPORT",
        "title":       "AER Annual Reliability Report FY2024 -- AUSNET Distribution",
        "text": """
RELIABILITY PERFORMANCE SUMMARY
AusNet Distribution's FY2024 System Average Interruption Duration Index (SAIDI) for
unplanned outages was 89.3 minutes per customer, compared with the AER Target of 95 minutes.
SAIFI was 0.87 interruptions per customer (Target: 0.95). Both metrics demonstrate
improvement from FY2023 (SAIDI: 102.1 min, SAIFI: 1.01).

MAJOR EVENT DAYS
Three Major Event Days (MEDs) occurred in FY2024:
1. 13 February 2024 -- Eastern bushfire risk day, total ENS: 4,200 MWh
2. 21 March 2024 -- Severe storm, Melbourne eastern suburbs, ENS: 2,800 MWh
3. 8 June 2024 -- Unexpected asset failure, Ringwood feeder complex, ENS: 310 MWh

CAUSE ANALYSIS
Vegetation contact: 34% of unplanned outages (up from 28% in FY2023)
Equipment failure: 28% (improvement from 35% in FY2023 following maintenance program)
Weather: 22% (storm-related)
Third party: 9% (excavation damage, 3 major events)
Unknown: 7%

STPIS IMPLICATIONS
FY2024 SAIDI result of 89.3 minutes (vs 95-minute target) generates STPIS bonus of
$1.23M under AER's Service Target Performance Incentive Scheme. Total STPIS accrual
position: +$3.1M for FY2024-FY2026 regulatory period.
""",
    },
    {
        "report_type": "CPEC_SUBMISSION",
        "title":       "Consumer Price Effects Cap Submission -- Jemena FY2025",
        "text": """
CPEC SUBMISSION OVERVIEW
Jemena Gas Networks submits this Consumer Price Effects Cap (CPEC) application to the
Australian Energy Regulator (AER) for the FY2025 regulatory period under the National
Gas Rules (NGR) Rule 91. This submission addresses the proposed capital program
for replacing ageing cast iron and asbestos cement mains in the northern Sydney network.

PROPOSED CAPITAL EXPENDITURE
Mains replacement program (FY2025-FY2029): $312M total
  - Cast iron mains more than 80 years old: $187M
  - Asbestos cement mains: $94M
  - Pressure regulation stations: $31M

CONSUMER IMPACT ASSESSMENT
The proposed program would increase average annual gas bills by $23 (3.2%) for residential
customers. Absent replacement, unplanned failure risk increases to 1 failure per 2.3km of
mains per year by FY2028 (current: 1 per 4.1km).

KEY DATES
AER submission deadline: 1 October 2024
AER draft decision: April 2025
Final decision and implementation: July 2025
""",
    },
    {
        "report_type": "STPIS",
        "title":       "STPIS Annual Performance Report FY2024 -- Ausgrid",
        "text": """
SERVICE TARGET PERFORMANCE INCENTIVE SCHEME
Annual Report -- Ausgrid Distribution -- FY2024

PERFORMANCE AGAINST TARGETS
SAIDI Unplanned: 68.2 min (Target: 72.0 min) -- OUTPERFORMANCE
SAIFI Unplanned: 0.73 (Target: 0.78) -- OUTPERFORMANCE
Momentary average interruption frequency index: 0.91 (Target: 1.05) -- OUTPERFORMANCE
Customer telephone response time (90th percentile): 88 seconds (Target: 120 seconds) -- OUTPERFORMANCE

INCENTIVE PAYMENTS
SAIDI outperformance of 3.8 minutes generates incentive of $4.2M
SAIFI outperformance of 0.05 generates incentive of $1.8M
Total STPIS incentive accrual FY2024: $6.0M
Cumulative FY2022-FY2024 period position: +$11.4M

PERFORMANCE DRIVERS
1. Network Automation Program Stage 3 completion (412 automated switches deployed)
2. Predictive maintenance algorithm (AI-based) identifying 127 pre-failure conditions
3. Accelerated underground cable replacement in inner Sydney (45km completed FY2024)
""",
    },
    {
        "report_type": "RIT_T",
        "title":       "RIT-T Assessment Report -- Murray-Darling Interconnector Upgrade",
        "text": """
REGULATORY INVESTMENT TEST FOR TRANSMISSION (RIT-T)
Project Proponent: TransGrid NSW
Project: Murray-Darling 330kV Interconnector Uprating

PROJECT DESCRIPTION
TransGrid proposes uprating the existing 330kV transmission line between Wagga Wagga and
Buronga from 680 MVA to 1,200 MVA thermal capacity. The project addresses network congestion
limiting renewable generation export from the Riverina Renewable Energy Zone under NSW LTESA.

MARKET BENEFITS ASSESSMENT
Constraint relief value (NPV, 10-year): $312M
Renewable integration value: $89M (based on 2.4 GW confirmed LTESA projects)
Avoided carbon costs (TLCC basis): $44M
Total market benefits: $445M

COSTS
Direct capital costs: $167M
Total costs (PV): $210M

NET MARKET BENEFIT
Net Market Benefit: $235M (positive -- project passes RIT-T)
Benefit-cost ratio: 2.12

AEMO SIGN-OFF
Submission date: 30 June 2024. AEMO non-contestability determination expected: 30 November 2024.
""",
    },
]

from datetime import datetime, date
from pyspark.sql import Row
import uuid

doc_rows = []
for i, doc in enumerate(REGULATORY_DOCS):
    doc_rows.append(Row(
        report_id        = str(uuid.uuid4()),
        report_type      = doc["report_type"],
        title            = doc["title"],
        period_start     = date(2023, 7, 1),
        period_end       = date(2024, 6, 30),
        submission_date  = date(2024, 9, 30 - i),
        submitting_entity= ["AUSNET", "AEMO", "JEMENA", "AUSGRID", "TRANSGRID"][i],
        document_url     = f"https://www.aer.gov.au/documents/rpt-{10 + i:04d}",
        document_text    = doc["text"].strip(),
        status           = "PUBLISHED",
        created_at       = datetime.now()
    ))

spark.createDataFrame(doc_rows).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_reports")
print(f"Regulatory reports: {spark.table(f'{CATALOG}.{SCHEMA}.regulatory_reports').count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3 -- Create the Output (Silver) Table

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.processed_reports (
    report_id              STRING    COMMENT 'FK to regulatory_reports.report_id',
    title                  STRING    COMMENT 'Report title',
    submitting_entity      STRING    COMMENT 'Entity that submitted the report',
    report_type_recorded   STRING    COMMENT 'Original report_type field value',
    ai_document_category   STRING    COMMENT 'AI-classified document category',
    ai_summary_executive   STRING    COMMENT 'AI-generated executive summary (60 words)',
    ai_summary_technical   STRING    COMMENT 'AI-generated technical summary (100 words)',
    ai_extracted_json      STRING    COMMENT 'AI-extracted structured metadata as JSON string',
    ai_key_dates           STRING    COMMENT 'Extracted key dates and deadlines as JSON array',
    ai_capital_value_m     DOUBLE    COMMENT 'Extracted capital expenditure value in AUD millions (null if not found)',
    ai_compliance_urgency  STRING    COMMENT 'AI-assessed urgency: IMMEDIATE, HIGH, MEDIUM, LOW',
    processing_status      STRING    COMMENT 'PROCESSED, FAILED, SKIPPED',
    processing_error       STRING    COMMENT 'Error message if processing_status = FAILED',
    processed_at           TIMESTAMP COMMENT 'Timestamp when AI processing completed',
    source_text_length     INT       COMMENT 'Length of source document_text in characters'
)
USING DELTA
COMMENT 'AI-enriched regulatory report metadata. All AI inference uses AU East endpoint -- no document text leaves Australia.'
TBLPROPERTIES (
    'delta.autoOptimize.autoCompact'   = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true'
)
""")
print(f"Created: {CATALOG}.{SCHEMA}.processed_reports")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4 -- The Incremental Processing Pattern
# MAGIC
# MAGIC Processing all documents on every run is wasteful and expensive.
# MAGIC The incremental pattern processes only records that do not yet have a corresponding
# MAGIC row in the output table.
# MAGIC
# MAGIC ```
# MAGIC regulatory_reports  LEFT ANTI JOIN  processed_reports  -->  only new records
# MAGIC ```
# MAGIC
# MAGIC | Pattern | Behaviour |
# MAGIC |---------|-----------|
# MAGIC | New document | No matching row in processed_reports -- included in batch |
# MAGIC | Already processed | `processing_status = 'PROCESSED'` exists -- excluded |
# MAGIC | Previously failed | No PROCESSED row -- included for retry |
# MAGIC | Empty document | `LENGTH(document_text) <= 100` -- excluded (no useful content) |

# COMMAND ----------

def get_unprocessed_reports(batch_size: int = 50):
    """
    Returns regulatory reports that have not yet been successfully processed.
    Uses LEFT ANTI JOIN to identify new or re-processable records.
    Failed records from previous runs are automatically included for retry.
    """
    return spark.sql(f"""
        SELECT r.*
        FROM {CATALOG}.{SCHEMA}.regulatory_reports r
        LEFT ANTI JOIN {CATALOG}.{SCHEMA}.processed_reports p
            ON r.report_id = p.report_id
           AND p.processing_status = 'PROCESSED'
        WHERE r.document_text IS NOT NULL
          AND LENGTH(r.document_text) > 100
        ORDER BY r.created_at
        LIMIT {batch_size}
    """)


pending = get_unprocessed_reports()
pending_count = pending.count()
print(f"Pending records to process: {pending_count}")
pending.select("report_id", "report_type", "title", F.length("document_text").alias("text_len")).show()

# Re-run cost estimate now that we have actual pending count
estimate = estimate_batch_cost(pending_count=pending_count)
print_cost_estimate(estimate)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5 -- Build the AI Enrichment Pipeline
# MAGIC
# MAGIC Three AI passes per document run in a single Spark query plan.
# MAGIC Spark optimises the physical plan and distributes inference across workers.
# MAGIC
# MAGIC | Pass | What it does | Output column |
# MAGIC |------|--------------|---------------|
# MAGIC | Classification | Document category + compliance urgency | `ai_document_category`, `ai_compliance_urgency` |
# MAGIC | Extraction | Key dates, capital values, regulatory body | `ai_extracted_json` |
# MAGIC | Summarisation | 60-word executive + 100-word technical summary | `ai_summary_executive`, `ai_summary_technical` |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5a -- Classification pass

# COMMAND ----------

def run_classification_pass(df) -> "DataFrame":
    """
    Adds AI classification columns.
    Uses failOnError => false -- a row-level error returns null instead of failing the job.
    """
    return df.withColumn(
        "ai_document_category",
        F.expr(f"""
            ai_query(
                '{ENDPOINT_NAME}',
                CONCAT(
                    'Classify this regulatory document into EXACTLY ONE category: ',
                    'PLANNING_REPORT, RELIABILITY_REPORT, COST_BENEFIT_ASSESSMENT, ',
                    'COMPLIANCE_SUBMISSION, INCENTIVE_SCHEME_REPORT, OTHER. ',
                    'Respond with ONLY the category name.\\n\\nTitle: ', title, '\\n\\nText excerpt:\\n',
                    LEFT(document_text, 500)
                ),
                failOnError => false
            )
        """)
    ).withColumn(
        "ai_compliance_urgency",
        F.expr(f"""
            ai_query(
                '{ENDPOINT_NAME}',
                CONCAT(
                    'Based on this regulatory document, classify the compliance urgency as one of: ',
                    'IMMEDIATE (action required within 30 days), ',
                    'HIGH (action required within 90 days), ',
                    'MEDIUM (action required within 12 months), ',
                    'LOW (informational, no immediate action). ',
                    'Respond with ONLY the urgency level word.\\n\\n',
                    'Title: ', title, '\\n\\n',
                    'Document excerpt:\\n', LEFT(document_text, 800)
                ),
                failOnError => false
            )
        """)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b -- Extraction pass

# COMMAND ----------

REPORT_EXTRACT_SCHEMA = """{
  "key_dates": [{"event": "string", "date": "YYYY-MM-DD or null"}],
  "capital_value_m": "number in AUD millions or null",
  "regulatory_body": "one of: AEMO, AER, ESB, AEMC, NONE",
  "key_regulation": "string - main rule or standard referenced",
  "geographic_scope": "string - regions or states affected"
}"""

def run_extraction_pass(df) -> "DataFrame":
    """Adds structured extraction JSON column."""
    return df.withColumn(
        "ai_extracted_json",
        F.expr(f"""
            ai_query(
                '{ENDPOINT_NAME}',
                CONCAT(
                    'Extract the following information from this regulatory document as JSON. ',
                    'If a field cannot be found, use null. Return ONLY valid JSON.\\n\\n',
                    'Schema: {REPORT_EXTRACT_SCHEMA.replace(chr(10), " ").replace("'", "''")}\\n\\n',
                    'Document text:\\n', LEFT(document_text, 2000)
                ),
                failOnError => false
            )
        """)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5c -- Summarisation pass

# COMMAND ----------

def run_summarisation_pass(df) -> "DataFrame":
    """Adds executive and technical summary columns."""
    df_exec = df.withColumn(
        "ai_summary_executive",
        F.expr(f"""
            ai_query(
                '{ENDPOINT_NAME}',
                CONCAT(
                    'Write a 60-word executive summary of this Australian energy regulatory document. ',
                    'Focus on business impact, financial figures, and key decisions required. ',
                    'Write in plain Australian English. No bullet points.\\n\\nDocument:\\n',
                    LEFT(document_text, 1500)
                ),
                failOnError => false
            )
        """)
    )

    return df_exec.withColumn(
        "ai_summary_technical",
        F.expr(f"""
            ai_query(
                '{ENDPOINT_NAME}',
                CONCAT(
                    'Write a 100-word technical summary of this Australian energy regulatory document ',
                    'for a network engineer audience. Include technical metrics (SAIDI/SAIFI, voltage levels, ',
                    'MW/MVA ratings), regulatory references (NER clauses, AER rules), and specific asset names. ',
                    'Plain text, no bullet points.\\n\\nDocument:\\n',
                    LEFT(document_text, 2000)
                ),
                failOnError => false
            )
        """)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5d -- Post-processing: materialise typed columns and add metadata

# COMMAND ----------

from pyspark.sql.functions import get_json_object

def run_post_processing(df) -> "DataFrame":
    """
    Parses the extracted JSON to materialise commonly-queried fields as typed columns.
    Also derives processing_status and adds audit metadata.
    """
    return (
        df
        .withColumn("ai_capital_value_m",
                    get_json_object("ai_extracted_json", "$.capital_value_m").cast("double"))
        .withColumn("ai_key_dates",
                    get_json_object("ai_extracted_json", "$.key_dates"))
        .withColumn("processing_status",
                    F.when(
                        F.col("ai_summary_executive").isNull() | F.col("ai_document_category").isNull(),
                        F.lit("FAILED")
                    ).otherwise(F.lit("PROCESSED")))
        .withColumn("processing_error",
                    F.when(F.col("processing_status") == "FAILED",
                           F.lit("One or more AI passes returned null -- check endpoint availability"))
                    .otherwise(F.lit(None).cast(StringType())))
        .withColumn("processed_at",       F.current_timestamp())
        .withColumn("source_text_length", F.length("document_text"))
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6 -- Run the Full Pipeline

# COMMAND ----------

def run_batch_pipeline(batch_size: int = 50, dry_run: bool = False) -> dict:
    """
    Full incremental pipeline:
      1. Get unprocessed records
      2. Run cost estimate
      3. Run classification, extraction, summarisation passes
      4. Post-process
      5. Merge into output table (MERGE INTO handles upserts)
    Returns a summary dict with counts and elapsed time.
    """
    import time
    start = time.time()

    # Step 1: Get pending records
    pending_df = get_unprocessed_reports(batch_size)
    count = pending_df.count()

    if count == 0:
        print("No new records to process.")
        return {"processed": 0, "failed": 0, "elapsed_s": 0}

    # Step 2: Show cost estimate for this batch
    est = estimate_batch_cost(pending_count=count)
    print_cost_estimate(est)
    print(f"Starting pipeline for {count} records...")

    # Step 3: Run AI passes (lazy -- Spark builds one query plan for all passes)
    df = pending_df
    df = run_classification_pass(df)
    df = run_extraction_pass(df)
    df = run_summarisation_pass(df)
    df = run_post_processing(df)

    # Select final output columns
    output_df = df.select(
        "report_id",
        "title",
        "submitting_entity",
        F.col("report_type").alias("report_type_recorded"),
        "ai_document_category",
        "ai_summary_executive",
        "ai_summary_technical",
        "ai_extracted_json",
        "ai_key_dates",
        "ai_capital_value_m",
        "ai_compliance_urgency",
        "processing_status",
        "processing_error",
        "processed_at",
        "source_text_length",
    )

    if dry_run:
        print("DRY RUN -- showing schema and first row preview:")
        output_df.printSchema()
        output_df.show(1, truncate=60, vertical=True)
        return {"dry_run": True, "pending_count": count}

    # Step 4: Merge into processed_reports (upsert by report_id)
    output_df.createOrReplaceTempView("_batch_results")
    spark.sql(f"""
        MERGE INTO {CATALOG}.{SCHEMA}.processed_reports AS target
        USING _batch_results AS source
        ON target.report_id = source.report_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

    elapsed = time.time() - start
    result_counts = spark.sql(f"""
        SELECT processing_status, COUNT(*) AS n
        FROM {CATALOG}.{SCHEMA}.processed_reports
        WHERE processed_at >= CURRENT_TIMESTAMP - INTERVAL 5 MINUTES
        GROUP BY processing_status
    """).collect()

    summary = {"elapsed_s": round(elapsed, 1)}
    for row in result_counts:
        summary[row.processing_status.lower()] = row.n

    print(f"\nPipeline complete in {elapsed:.1f}s")
    print(f"Results: {summary}")
    return summary


# Dry run first -- validates schema without writing any data
print("DRY RUN")
print("=" * 50)
run_batch_pipeline(batch_size=2, dry_run=True)

# COMMAND ----------

# Run the real pipeline
print("FULL PIPELINE RUN")
print("=" * 50)
pipeline_summary = run_batch_pipeline(batch_size=50)
print(pipeline_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (dry run):**
# MAGIC ```
# MAGIC DRY RUN
# MAGIC ==================================================
# MAGIC =======================================================
# MAGIC   PRE-RUN COST ESTIMATE
# MAGIC =======================================================
# MAGIC   Documents pending  : 2
# MAGIC   Estimated cost     : USD $0.0208
# MAGIC =======================================================
# MAGIC DRY RUN -- showing schema and first row preview:
# MAGIC root
# MAGIC  |-- report_id: string (nullable = true)
# MAGIC  |-- title: string (nullable = true)
# MAGIC  ...
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 7 -- Inspect and Validate Results

# COMMAND ----------

# Show all processed results
display(spark.table(f"{CATALOG}.{SCHEMA}.processed_reports"))

# COMMAND ----------

# Validate: check for failures and null AI outputs
spark.sql(f"""
SELECT
    COUNT(*)                                           AS total_processed,
    SUM(CASE WHEN processing_status='PROCESSED' THEN 1 ELSE 0 END) AS successful,
    SUM(CASE WHEN processing_status='FAILED'    THEN 1 ELSE 0 END) AS failed,
    ROUND(AVG(source_text_length), 0)                  AS avg_doc_chars,
    MIN(ai_capital_value_m)                            AS min_capital_m,
    MAX(ai_capital_value_m)                            AS max_capital_m
FROM {CATALOG}.{SCHEMA}.processed_reports
""").show()

# COMMAND ----------

# Review AI summaries for quality spot-check
spark.sql(f"""
SELECT
    title,
    report_type_recorded,
    ai_document_category,
    ai_compliance_urgency,
    ai_capital_value_m,
    LEFT(ai_summary_executive, 200) AS exec_summary_preview
FROM {CATALOG}.{SCHEMA}.processed_reports
WHERE processing_status = 'PROCESSED'
ORDER BY ai_compliance_urgency, ai_capital_value_m DESC NULLS LAST
""").show(truncate=60)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC +---------------+------+------------+----------+-----------+
# MAGIC | total_processed | successful | failed | avg_doc_chars | max_capital_m |
# MAGIC +---------------+------+------------+----------+-----------+
# MAGIC |             5 |          5 |      0 |          2420 |         445.0 |
# MAGIC +---------------+------+------------+----------+-----------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 8 -- Optimise the Output Table
# MAGIC
# MAGIC Run `OPTIMIZE` with `ZORDER` after each batch load. This improves query performance
# MAGIC for downstream Genie and dashboard queries.
# MAGIC
# MAGIC <div style="background: #E8F4FD; padding: 12px 16px; border-radius: 6px; border-left: 4px solid #1B3A5C; margin: 8px 0">
# MAGIC <strong>Why ZORDER on these columns?</strong> Genie and dashboard queries most commonly
# MAGIC filter on compliance urgency, report type, and entity. ZORDER co-locates data for these
# MAGIC common filter patterns, reducing data scanned per query.
# MAGIC </div>

# COMMAND ----------

print("Running OPTIMIZE with ZORDER on processed_reports...")
spark.sql(f"""
OPTIMIZE {CATALOG}.{SCHEMA}.processed_reports
ZORDER BY (ai_compliance_urgency, report_type_recorded, submitting_entity)
""")
print("OPTIMIZE complete.")

# Check table health
spark.sql(f"""
DESCRIBE DETAIL {CATALOG}.{SCHEMA}.processed_reports
""").select(
    "format", "numFiles", "sizeInBytes", "numOutputRows"
).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 9 -- Schedule as a Databricks Job
# MAGIC
# MAGIC ### Option A -- Create the job via the UI (recommended)
# MAGIC
# MAGIC **Navigate:** Workflows (left sidebar) -> [+ Create job]
# MAGIC
# MAGIC **Step 9.1 -- Name the job and add first task**
# MAGIC ```
# MAGIC +--- Create job -------------------------------------------------------+
# MAGIC |                                                                      |
# MAGIC |  Job name: [ ai_regulatory_processing_pipeline               ]      |
# MAGIC |                                                                      |
# MAGIC |  Task 1:                                                             |
# MAGIC |  +-- Task name: [ process_new_reports                        ]      |
# MAGIC |  +-- Type:  (*) Notebook  ( ) Python script  ( ) SQL  ( ) JAR       |
# MAGIC |  +-- Source: [ Workspace v ]                                        |
# MAGIC |  +-- Path: [ /Workspace/workshops/.../05_batch_ai_pipeline  ]       |
# MAGIC |  +-- Cluster: [ Use existing cluster v ] (select your cluster)      |
# MAGIC |                                                                      |
# MAGIC +----------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC **Step 9.2 -- Set the schedule**
# MAGIC
# MAGIC Click **[+ Add schedule / trigger]** then fill in:
# MAGIC ```
# MAGIC +--- Trigger ----------------------------------------------------------+
# MAGIC |                                                                      |
# MAGIC |  (*) Scheduled                                                       |
# MAGIC |  Cron expression: [ 0 30 2 * * ?  ]  (2:30 AM daily)               |
# MAGIC |  Timezone:        [ Australia/Melbourne v ]                          |
# MAGIC |                                                                      |
# MAGIC |  Preview: "Runs daily at 2:30 AM AEST"                              |
# MAGIC |                                                                      |
# MAGIC |  Status: ( ) Active  (*) Paused  <- leave paused until ready         |
# MAGIC |                                                                      |
# MAGIC +----------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC **Step 9.3 -- Configure notifications (recommended for production)**
# MAGIC ```
# MAGIC +--- Notifications ----------------------------------------------------+
# MAGIC |  On failure: [ your.email@company.com.au             ]              |
# MAGIC |  On success: (leave blank -- only alert on failure for daily jobs)   |
# MAGIC +----------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Option B -- Create the job via SDK (run the cell below)

# COMMAND ----------

from databricks.sdk.service.jobs import JobSettings, Task, NotebookTask

# TODO: replace with your actual notebook path
NOTEBOOK_PATH = f"/Workspace/workshops/workshop2b_genie_spaces/labs/05_batch_ai_pipeline"


def create_or_update_pipeline_job() -> int:
    """
    Creates (or updates) a scheduled job for the regulatory reports AI pipeline.
    Returns the job_id.
    """
    JOB_NAME = "Regulatory Reports AI Pipeline -- Daily"

    # Check if job already exists
    existing_jobs = list(w.jobs.list(name=JOB_NAME))
    if existing_jobs:
        job_id = existing_jobs[0].job_id
        print(f"Job already exists (id={job_id}). Updating...")
    else:
        job_id = None

    job_settings = {
        "name": JOB_NAME,
        "tasks": [
            {
                "task_key": "run_ai_pipeline",
                "notebook_task": {
                    "notebook_path": NOTEBOOK_PATH,
                    "base_parameters": {
                        "batch_size": "200",
                        "dry_run":    "false"
                    }
                },
                "existing_cluster_id": spark.conf.get("spark.databricks.clusterUsageTags.clusterId", ""),
                # For production, use a new dedicated cluster instead:
                # "new_cluster": {
                #     "spark_version": "15.4.x-scala2.12",
                #     "node_type_id": "Standard_D4s_v3",
                #     "num_workers": 2,
                # }
            }
        ],
        "schedule": {
            "quartz_cron_expression": "0 30 2 * * ?",  # 2:30 AM daily AEST (UTC+10 = 16:30 UTC prev day)
            "timezone_id": "Australia/Melbourne",
            "pause_status": "PAUSED"  # unpause when ready for production
        },
        "email_notifications": {
            # TODO: replace with your email
            # "on_failure": ["your.email@company.com.au"],
        },
        "tags": {
            "team":        "data-platform",
            "environment": "workshop",
            "data-class":  "regulatory"
        }
    }

    if job_id:
        w.jobs.reset(job_id=job_id, new_settings=job_settings)
        print(f"Job updated: {job_id}")
    else:
        created = w.jobs.create(**job_settings)
        job_id  = created.job_id
        print(f"Job created: {job_id}")

    print(f"\nJob URL: https://{HOST}/jobs/{job_id}")
    return job_id


try:
    JOB_ID = create_or_update_pipeline_job()
except Exception as e:
    print(f"Job creation skipped (workshop environment): {e}")
    JOB_ID = None
    print("In production: configure the job via the Jobs UI or Databricks Asset Bundles.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 10 -- Monitor Pipeline Runs
# MAGIC
# MAGIC ### Monitoring from the UI
# MAGIC
# MAGIC **Navigate:** Workflows -> [job name] -> **Runs** tab
# MAGIC
# MAGIC ```
# MAGIC +--- Job Runs ---------------------------------------------------------+
# MAGIC |                                                                      |
# MAGIC |  Run 1 | 2026-05-22 02:30 | Duration: 4m 32s | Success              |
# MAGIC |  Run 2 | 2026-05-21 02:30 | Duration: 3m 58s | Success              |
# MAGIC |  Run 3 | 2026-05-20 02:30 | Duration: 12m 3s | Failed               |
# MAGIC |        |  ^ click to see logs and error details                     |
# MAGIC |                                                                      |
# MAGIC +----------------------------------------------------------------------+
# MAGIC ```
# MAGIC
# MAGIC Click any run row to see:
# MAGIC - Full cluster logs
# MAGIC - Notebook output cell-by-cell
# MAGIC - Spark UI for query plans and stage timings
# MAGIC - Error stack trace for failed runs

# COMMAND ----------

# MAGIC %md
# MAGIC ### 10a -- Daily processing metrics

# COMMAND ----------

spark.sql(f"""
SELECT
    DATE(processed_at)                                 AS processing_date,
    COUNT(*)                                           AS records_processed,
    SUM(CASE WHEN processing_status='PROCESSED' THEN 1 ELSE 0 END) AS successful,
    SUM(CASE WHEN processing_status='FAILED'    THEN 1 ELSE 0 END) AS failed,
    ROUND(
        SUM(CASE WHEN processing_status='PROCESSED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    )                                                   AS success_pct,
    ROUND(AVG(source_text_length), 0)                  AS avg_doc_chars,
    SUM(source_text_length)                            AS total_chars_processed
FROM {CATALOG}.{SCHEMA}.processed_reports
GROUP BY DATE(processed_at)
ORDER BY processing_date DESC
""").show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 10b -- Failed records for investigation

# COMMAND ----------

spark.sql(f"""
SELECT
    report_id,
    title,
    processing_status,
    processing_error,
    processed_at
FROM {CATALOG}.{SCHEMA}.processed_reports
WHERE processing_status = 'FAILED'
ORDER BY processed_at DESC
LIMIT 20
""").show(truncate=80)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 10c -- Compliance urgency dashboard

# COMMAND ----------

spark.sql(f"""
SELECT
    ai_compliance_urgency,
    COUNT(*)                                           AS document_count,
    COLLECT_LIST(submitting_entity)                    AS entities,
    ROUND(SUM(COALESCE(ai_capital_value_m, 0)), 1)     AS total_capex_m,
    COLLECT_LIST(title)[0]                             AS sample_title
FROM {CATALOG}.{SCHEMA}.processed_reports
WHERE processing_status = 'PROCESSED'
GROUP BY ai_compliance_urgency
ORDER BY
    CASE ai_compliance_urgency
        WHEN 'IMMEDIATE' THEN 1
        WHEN 'HIGH'      THEN 2
        WHEN 'MEDIUM'    THEN 3
        WHEN 'LOW'       THEN 4
        ELSE 5
    END
""").show(truncate=60)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC +---------------------+---------------+-------+------------+
# MAGIC | ai_compliance_urgency | document_count | total_capex_m | sample_title |
# MAGIC +---------------------+---------------+-------+------------+
# MAGIC | HIGH                |             2 |        312.0 | NEM Annual Planning Report... |
# MAGIC | MEDIUM              |             2 |        235.0 | RIT-T Assessment Report...   |
# MAGIC | LOW                 |             1 |          6.0 | STPIS Annual Performance...  |
# MAGIC +---------------------+---------------+-------+------------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 11 -- Cost Optimisation Strategies

# COMMAND ----------

print("""
BATCH AI PIPELINE -- COST OPTIMISATION STRATEGIES
===================================================

1. USE SMALLER MODELS FOR SIMPLE TASKS
   - Classification (pick from list): 8B model -- accuracy comparable to 70B
   - Extraction (structured JSON): 8B is usually sufficient
   - Summarisation (quality matters): consider 70B for executive summaries
   Savings: up to 60% if you select model per task type

2. TRUNCATE INPUT TEXT INTELLIGENTLY
   - Regulatory documents: first 2,000 chars usually contains all key info
   - Work orders: typically < 1,000 chars total
   - Do NOT truncate when extracting dates/references from end of document
   Current implementation truncates to 2,000 chars -- review for your documents

3. CACHE RESULTS AGGRESSIVELY
   - Incremental pattern (LEFT ANTI JOIN) avoids reprocessing
   - Add a content_hash column to detect changed documents
   - Only reprocess if content_hash changes

4. SCHEDULE DURING OFF-PEAK HOURS
   - PT endpoints charged per provisioned throughput-second
   - Run batch jobs at 2 AM AEST when cluster is otherwise idle
   - Use scale-to-zero PT endpoint (min_provisioned_throughput=0)

5. RIGHT-SIZE THE PT ENDPOINT
   - For 200 docs/day batch (2 AM run): 100 tokens/s PT is sufficient
   - Over-provisioning wastes DBU allocation even when idle
   - Monitor utilisation in: Serving -> endpoint -> Metrics tab

6. SELECTIVE RE-PROCESSING
   - Only re-run failed records, not all records
   - Failed records automatically retried via LEFT ANTI JOIN pattern
   - Failed records usually have a correctable cause (prompt fix, not model failure)

MONTHLY COST SCENARIOS (Llama 3.1 8B, 4 passes, 3,000 char avg doc):
   100 docs/month:    USD ~$0.52  (AUD ~$0.80)
   1,000 docs/month:  USD ~$5.20  (AUD ~$8.00)
   10,000 docs/month: USD ~$52.00 (AUD ~$80.00)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 05 -- Final Summary

# COMMAND ----------

print("=" * 65)
print("WORKSHOP 2B -- COMPLETE LAB SUMMARY")
print("=" * 65)
print()
print("WHAT WAS BUILT:")
print()
print("  workshop.energy_nem schema:")
spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").select("tableName").show(20, truncate=False)

print("  UC AI Functions:")
try:
    spark.sql(f"SHOW FUNCTIONS IN {CATALOG}.ai_functions").select("function").show(10, truncate=False)
except Exception:
    print("    (run Lab 04 to create AI functions)")

print()
print("KEY ARCHITECTURE DECISIONS:")
print("  1. All AI inference routes through AU East PT endpoint")
print("  2. ai_query(endpoint_name, ...) replaces all ai_*() built-in functions")
print("  3. UC wrapper functions centralise prompt logic -- one place to update")
print("  4. Incremental processing with LEFT ANTI JOIN prevents reprocessing")
print("  5. OPTIMIZE + ZORDER after each batch improves downstream query performance")
print("  6. Genie Space uses databricks-qwen3-embedding-0-6b (in-region) for RAG")
print()
print("IN-REGION MODEL REFERENCE:")
print("  LLM inference:  meta-llama/Meta-Llama-3.1-8B-Instruct (AU East PT)")
print("  Embeddings:     databricks-qwen3-embedding-0-6b (AU East)")
print("  Do NOT use:     databricks-gte-large-en (cross-geo)")
print("  Do NOT use:     ai_classify/ai_summarize built-ins (cross-geo)")
print()
print("NEXT STEPS:")
print("  - Add processed_reports to your Genie Space as a trusted asset")
print("  - Create AI/BI dashboard tiles from v_dashboard_outage_summary")
print("  - Enable Genie Agent mode for cross-table questions")
print("  - Schedule the batch pipeline job for daily incremental processing")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab 05 -- Review Questions
# MAGIC
# MAGIC <div style="background: #F4F4F4; padding: 16px 20px; border-radius: 8px; margin: 8px 0">
# MAGIC
# MAGIC **Q1.** The incremental pipeline uses `LEFT ANTI JOIN` to find unprocessed records.
# MAGIC A document was processed but the result had `processing_status = 'FAILED'`.
# MAGIC Will it be reprocessed on the next run? Why or why not?
# MAGIC
# MAGIC **Q2.** A colleague suggests using `ai_summarize()` instead of `ai_query(endpoint, ...)`
# MAGIC to save the PT endpoint deployment effort. What are the two objections you raise?
# MAGIC
# MAGIC **Q3.** The pipeline processes 500 regulatory documents per month.
# MAGIC Using the cost model above, estimate the monthly cost in AUD
# MAGIC (use an AUD/USD rate of 0.65) for Llama 3.1 8B with 4 passes per doc.
# MAGIC
# MAGIC **Q4.** Why do we run `OPTIMIZE ZORDER BY (ai_compliance_urgency, report_type_recorded)`
# MAGIC rather than `OPTIMIZE ZORDER BY (report_id)`?
# MAGIC
# MAGIC **Q5.** A document extraction returns `ai_capital_value_m = null` even though the document
# MAGIC says "$143.6M". The extract schema specifies `"capital_value_m": "number in AUD millions"`.
# MAGIC List two prompt changes you would try to fix this.
# MAGIC
# MAGIC </div>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## End of Workshop 2B -- Genie Spaces and AI Features
# MAGIC
# MAGIC | Lab | Key Skill |
# MAGIC |-----|-----------|
# MAGIC | 01 | Create Genie Space via API; seed schema and golden queries |
# MAGIC | 02 | Admin deep-dive: comments, agent mode, troubleshooting |
# MAGIC | 03 | End-user question quality; Conversation API; Teams integration |
# MAGIC | 04 | In-region AI Functions via PT endpoint; Australian PII masking |
# MAGIC | 05 | Batch AI pipeline; incremental processing; scheduling; cost optimisation |
