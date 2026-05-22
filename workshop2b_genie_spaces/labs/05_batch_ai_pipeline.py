# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 05: Batch AI Processing Pipeline
# MAGIC
# MAGIC **Workshop:** Genie Spaces & AI Features — Australian Regulated Industries
# MAGIC **Duration:** 40–45 minutes
# MAGIC **Role:** Data Engineer
# MAGIC **Prerequisite:** Lab 04 complete — PT endpoint deployed and UC wrapper functions created
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC 1. Process large volumes of unstructured regulatory documents with AI at scale
# MAGIC 2. Use Spark + `ai_query` for distributed, parallelised inference
# MAGIC 3. Implement the **incremental processing pattern** (only process new/changed records)
# MAGIC 4. Handle errors gracefully with `failOnError = false`
# MAGIC 5. Write AI-enriched results to Delta with `OPTIMIZE` and `ZORDER`
# MAGIC 6. Schedule the pipeline as a Databricks Job with monitoring
# MAGIC 7. Estimate and optimise cost for production workloads
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Pipeline Architecture
# MAGIC
# MAGIC ```
# MAGIC regulatory_reports (Bronze Delta — raw PDF text)
# MAGIC         │
# MAGIC         ▼  ai_query (in-region PT endpoint)
# MAGIC         │  ├─ classify document type
# MAGIC         │  ├─ extract key dates and entities
# MAGIC         │  └─ summarise for dashboard display
# MAGIC         │
# MAGIC         ▼
# MAGIC processed_reports (Silver Delta — AI-enriched metadata)
# MAGIC         │
# MAGIC         ▼
# MAGIC Genie Space + AI/BI Dashboard
# MAGIC ```
# MAGIC
# MAGIC ## All AI Calls Route Through AU East PT Endpoint
# MAGIC
# MAGIC Every `ai_query()` call in this pipeline uses the PT endpoint deployed in Lab 04.
# MAGIC No document text leaves Australia East.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

%pip install -q databricks-sdk>=0.28.0
dbutils.library.restartPython()

# COMMAND ----------

import requests, time, json
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DateType, BooleanType
from databricks.sdk import WorkspaceClient

w       = WorkspaceClient()
HOST    = spark.conf.get("spark.databricks.workspaceUrl")
CATALOG = "workshop"
SCHEMA  = "energy_nem"

# TODO: confirm this matches your PT endpoint name from Lab 04
ENDPOINT_NAME = "au_east_llm_inregion"

# Verify endpoint is ready
try:
    ep = w.serving_endpoints.get(ENDPOINT_NAME)
    print(f"PT endpoint '{ENDPOINT_NAME}': {ep.state.ready}")
except Exception as e:
    print(f"WARNING: Could not verify endpoint: {e}")
    print("Ensure Lab 04 is complete and the endpoint is READY before continuing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Seed Regulatory Reports with Realistic Document Text
# MAGIC
# MAGIC The `regulatory_reports` table from Lab 01 has placeholder text.
# MAGIC We'll replace it with longer, more realistic regulatory document extracts
# MAGIC that give the AI model something meaningful to process.

# COMMAND ----------

# Seed realistic document text for each report type
REGULATORY_DOCS = [
    {
        "report_type": "ANNUAL_PLANNING",
        "title":       "NEM Annual Planning Report FY2024 — VIC1 Distribution Zone",
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
AER review period: October 2024 – March 2025
Construction commencement: July 2025 (Essendon), January 2026 (Ringwood)
""",
    },
    {
        "report_type": "RELIABILITY_REPORT",
        "title":       "AER Annual Reliability Report FY2024 — AUSNET Distribution",
        "text": """
RELIABILITY PERFORMANCE SUMMARY
AusNet Distribution's FY2024 System Average Interruption Duration Index (SAIDI) for
unplanned outages was 89.3 minutes per customer, compared with the AER Target of 95 minutes.
SAIFI was 0.87 interruptions per customer (Target: 0.95). Both metrics demonstrate
improvement from FY2023 (SAIDI: 102.1 min, SAIFI: 1.01).

MAJOR EVENT DAYS
Three Major Event Days (MEDs) occurred in FY2024:
1. 13 February 2024 — Eastern bushfire risk day, total ENS: 4,200 MWh
2. 21 March 2024 — Severe storm, Melbourne eastern suburbs, ENS: 2,800 MWh
3. 8 June 2024 — Unexpected asset failure, Ringwood feeder complex, ENS: 310 MWh

CAUSE ANALYSIS
Vegetation contact: 34% of unplanned outages (up from 28% in FY2023)
Equipment failure: 28% (improvement from 35% in FY2023 following maintenance program)
Weather: 22% (storm-related)
Third party: 9% (excavation damage, 3 major events)
Unknown: 7%

VEGETATION MANAGEMENT
Increase in vegetation contact attributed to deferred pruning cycles during COVID period
(FY2021-FY2022). Accelerated vegetation management program commenced FY2023 with
$18.4M investment. Full cycle catch-up expected FY2026.

STPIS IMPLICATIONS
FY2024 SAIDI result of 89.3 minutes (vs 95-minute target) generates STPIS bonus of
$1.23M under AER's Service Target Performance Incentive Scheme. Total STPIS accrual
position: +$3.1M for FY2024-FY2026 regulatory period.
""",
    },
    {
        "report_type": "CPEC_SUBMISSION",
        "title":       "Consumer Price Effects Cap Submission — Jemena FY2025",
        "text": """
CPEC SUBMISSION OVERVIEW
Jemena Gas Networks submits this Consumer Price Effects Cap (CPEC) application to the
Australian Energy Regulator (AER) for the FY2025 regulatory period under the National
Gas Rules (NGR) Rule 91. This submission addresses the proposed capital program
for replacing ageing cast iron and asbestos cement mains in the northern Sydney network.

PROPOSED CAPITAL EXPENDITURE
Mains replacement program (FY2025-FY2029): $312M total
  - Cast iron mains >80 years old: $187M
  - Asbestos cement mains: $94M
  - Pressure regulation stations: $31M

CONSUMER IMPACT ASSESSMENT
The proposed program would increase average annual gas bills by $23 (3.2%) for residential
customers. Absent replacement, unplanned failure risk increases to 1 failure per 2.3km of
mains per year by FY2028 (current: 1 per 4.1km). Each unplanned failure results in average
service interruption of 8.2 hours for 340 customers.

SAFETY COMPLIANCE
The program addresses compliance with AS/NZS 4645.1 and the Work Health and Safety
(General) Regulation 2017. Asbestos cement mains removal required under state Safe Work NSW
directive by 31 December 2027.

KEY DATES
AER submission deadline: 1 October 2024
AER draft decision: April 2025
Final decision and implementation: July 2025
""",
    },
    {
        "report_type": "STPIS",
        "title":       "STPIS Annual Performance Report FY2024 — Ausgrid",
        "text": """
SERVICE TARGET PERFORMANCE INCENTIVE SCHEME
Annual Report — Ausgrid Distribution — FY2024

PERFORMANCE AGAINST TARGETS
SAIDI Unplanned: 68.2 min (Target: 72.0 min) — OUTPERFORMANCE
SAIFI Unplanned: 0.73 (Target: 0.78) — OUTPERFORMANCE
Momentary average interruption frequency index: 0.91 (Target: 1.05) — OUTPERFORMANCE
Customer telephone response time (90th percentile): 88 seconds (Target: 120 seconds) — OUTPERFORMANCE

INCENTIVE PAYMENTS
SAIDI outperformance of 3.8 minutes generates incentive of $4.2M
SAIFI outperformance of 0.05 generates incentive of $1.8M
Total STPIS incentive accrual FY2024: $6.0M
Cumulative FY2022-FY2024 period position: +$11.4M

PERFORMANCE DRIVERS
Ausgrid's FY2024 performance improvement attributed to:
1. Network Automation Program Stage 3 completion (412 automated switches deployed)
2. Predictive maintenance algorithm (AI-based) identifying 127 pre-failure conditions
3. Accelerated underground cable replacement in inner Sydney (45km completed FY2024)

MAJOR EVENT DAY EXCLUSIONS
4 Major Event Days excluded per NER clause 7.7.2:
Total excluded SAIDI: 31.2 minutes
Without MED exclusions, reported SAIDI would be 99.4 minutes.
""",
    },
    {
        "report_type": "RIT_T",
        "title":       "RIT-T Assessment Report — Murray-Darling Interconnector Upgrade",
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
Connection agreement costs: $12M
Present value of operating costs (40-year): $31M
Total costs (PV): $210M

NET MARKET BENEFIT
Net Market Benefit: $235M (positive — project passes RIT-T)
Benefit-cost ratio: 2.12

PREFERRED OPTION
Option 2 (reconductoring with HTLS conductor) preferred over Option 1 (new parallel circuit)
on cost-benefit grounds. Environmental impact assessment complete — no critical habitat impacts.

AEMO SIGN-OFF
This RIT-T assessment has been reviewed by AEMO and found compliant with NER clause 5.16.
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
# MAGIC ## Step 2 — Create the Output (Silver) Table

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.processed_reports (
    report_id              STRING    COMMENT 'FK → regulatory_reports.report_id',
    title                  STRING    COMMENT 'Report title',
    submitting_entity      STRING    COMMENT 'Entity that submitted the report',
    report_type_recorded   STRING    COMMENT 'Original report_type field value',
    ai_document_category   STRING    COMMENT 'AI-classified document category',
    ai_summary_executive   STRING    COMMENT 'AI-generated executive summary (60 words)',
    ai_summary_technical   STRING    COMMENT 'AI-generated technical summary (100 words)',
    ai_extracted_json      STRING    COMMENT 'AI-extracted structured metadata as JSON string',
    ai_key_dates           STRING    COMMENT 'Extracted key dates and deadlines as JSON array',
    ai_capital_value_m     DOUBLE    COMMENT 'Extracted capital expenditure value in $M (null if not found)',
    ai_compliance_urgency  STRING    COMMENT 'AI-assessed urgency: IMMEDIATE, HIGH, MEDIUM, LOW',
    processing_status      STRING    COMMENT 'PROCESSED, FAILED, SKIPPED',
    processing_error       STRING    COMMENT 'Error message if processing_status = FAILED',
    processed_at           TIMESTAMP COMMENT 'Timestamp when AI processing completed',
    source_text_length     INT       COMMENT 'Length of source document_text in characters'
)
USING DELTA
COMMENT 'AI-enriched regulatory report metadata. Processed from regulatory_reports using in-region PT endpoint.
All AI inference uses AU East endpoint — no document text leaves Australia.'
TBLPROPERTIES (
    'delta.autoOptimize.autoCompact'   = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true'
)
""")
print(f"Created: {CATALOG}.{SCHEMA}.processed_reports")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — The Incremental Processing Pattern
# MAGIC
# MAGIC Processing all documents on every run is wasteful and expensive.
# MAGIC The incremental pattern: process only records that don't yet have a corresponding
# MAGIC row in the output table.
# MAGIC
# MAGIC ```
# MAGIC regulatory_reports  LEFT ANTI JOIN  processed_reports  →  only new records
# MAGIC ```

# COMMAND ----------

def get_unprocessed_reports(batch_size: int = 50) -> "DataFrame":
    """
    Returns regulatory reports that have not yet been successfully processed.
    Uses LEFT ANTI JOIN to identify new or re-processable records.
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
print(f"Pending records to process: {pending.count()}")
pending.select("report_id", "report_type", "title", F.length("document_text").alias("text_len")).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Build the AI Enrichment Pipeline
# MAGIC
# MAGIC We run three AI passes per document:
# MAGIC 1. **Classification** — document category and compliance urgency
# MAGIC 2. **Extraction** — key dates, capital values, entities
# MAGIC 3. **Summarisation** — executive and technical summaries
# MAGIC
# MAGIC All use `ai_query` with the in-region PT endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a — Classification pass

# COMMAND ----------

def run_classification_pass(df: "DataFrame") -> "DataFrame":
    """
    Adds AI classification columns to the dataframe.
    Uses ai_query with failOnError=false to handle individual row errors gracefully.
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
# MAGIC ### 4b — Extraction pass

# COMMAND ----------

REPORT_EXTRACT_SCHEMA = """{
  "key_dates": [{"event": "string", "date": "YYYY-MM-DD or null"}],
  "capital_value_m": "number in AUD millions or null",
  "regulatory_body": "one of: AEMO, AER, ESB, AEMC, NONE",
  "key_regulation": "string - main rule or standard referenced",
  "geographic_scope": "string - regions or states affected"
}"""

def run_extraction_pass(df: "DataFrame") -> "DataFrame":
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
# MAGIC ### 4c — Summarisation pass

# COMMAND ----------

def run_summarisation_pass(df: "DataFrame") -> "DataFrame":
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

    df_tech = df_exec.withColumn(
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

    return df_tech

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4d — Post-processing: extract capital value from JSON

# COMMAND ----------

from pyspark.sql.functions import get_json_object, regexp_extract

def run_post_processing(df: "DataFrame") -> "DataFrame":
    """
    Parses the extracted JSON to materialise commonly-queried fields as typed columns.
    Also adds processing metadata columns.
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
                    ).otherwise(F.lit("PROCESSED"))
                    )
        .withColumn("processing_error",
                    F.when(F.col("processing_status") == "FAILED",
                           F.lit("One or more AI passes returned null — check endpoint availability"))
                    .otherwise(F.lit(None).cast(StringType())))
        .withColumn("processed_at",     F.current_timestamp())
        .withColumn("source_text_length", F.length("document_text"))
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Run the Full Pipeline

# COMMAND ----------

def run_batch_pipeline(batch_size: int = 50, dry_run: bool = False) -> dict:
    """
    Full incremental pipeline:
    1. Get unprocessed records
    2. Run classification, extraction, summarisation
    3. Post-process
    4. Merge into output table
    Returns a summary dict with counts.
    """
    import time
    start = time.time()

    # Step 1: Get pending records
    pending_df = get_unprocessed_reports(batch_size)
    count = pending_df.count()

    if count == 0:
        print("No new records to process.")
        return {"processed": 0, "failed": 0, "skipped": 0, "elapsed_s": 0}

    print(f"Processing {count} records...")

    # Step 2: Run AI passes (lazy — Spark builds the plan)
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
        print("DRY RUN — showing schema and first row preview:")
        output_df.printSchema()
        output_df.show(1, truncate=60, vertical=True)
        return {"dry_run": True, "pending_count": count}

    # Step 3: Merge into processed_reports (upsert by report_id)
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


# Run a dry run first to validate the schema
print("DRY RUN")
print("=" * 50)
run_batch_pipeline(batch_size=2, dry_run=True)

# COMMAND ----------

# Run the real pipeline
print("\nFULL PIPELINE RUN")
print("=" * 50)
pipeline_summary = run_batch_pipeline(batch_size=50)
print(pipeline_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 — Inspect and Validate Results

# COMMAND ----------

# Show processed results
display(spark.table(f"{CATALOG}.{SCHEMA}.processed_reports"))

# COMMAND ----------

# Validate: check for failures and null AI outputs
spark.sql(f"""
SELECT
    COUNT(*)                                           AS total_processed,
    SUM(CASE WHEN processing_status='PROCESSED' THEN 1 ELSE 0 END) AS successful,
    SUM(CASE WHEN processing_status='FAILED'    THEN 1 ELSE 0 END) AS failed,
    AVG(source_text_length)                            AS avg_text_length,
    MIN(ai_capital_value_m)                            AS min_capital_m,
    MAX(ai_capital_value_m)                            AS max_capital_m
FROM {CATALOG}.{SCHEMA}.processed_reports
""").show()

# COMMAND ----------

# Review AI summaries for quality
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
# MAGIC ## Step 7 — Optimise the Output Table
# MAGIC
# MAGIC After writing a batch, run `OPTIMIZE` and `ZORDER` on the output table.
# MAGIC This improves query performance for downstream Genie and dashboard queries.

# COMMAND ----------

# OPTIMIZE and ZORDER — run after each batch load
# ZORDER by columns most commonly used in WHERE clauses

print("Running OPTIMIZE with ZORDER on processed_reports...")
spark.sql(f"""
OPTIMIZE {CATALOG}.{SCHEMA}.processed_reports
ZORDER BY (ai_compliance_urgency, report_type_recorded, submitting_entity)
""")
print("OPTIMIZE complete.")

# Check table health after optimization
spark.sql(f"""
DESCRIBE DETAIL {CATALOG}.{SCHEMA}.processed_reports
""").select(
    "format", "numFiles", "sizeInBytes", "numOutputRows"
).show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 8 — Schedule as a Databricks Job
# MAGIC
# MAGIC Create a job that runs the incremental pipeline on a daily schedule.

# COMMAND ----------

from databricks.sdk.service.jobs import (
    JobSettings, Task, NotebookTask, CronSchedule, JobEmailNotifications
)

# TODO: replace with your actual notebook path
NOTEBOOK_PATH = f"/Workspace/workshops/workshop2b_genie_spaces/labs/05_batch_ai_pipeline"

# The job runs only the pipeline function — define the pipeline-only notebook path
PIPELINE_NOTEBOOK_PATH = NOTEBOOK_PATH  # or a dedicated pipeline-only notebook

def create_or_update_pipeline_job() -> int:
    """
    Creates (or updates) a scheduled job for the regulatory reports AI pipeline.
    Returns the job_id.
    """
    JOB_NAME = "Regulatory Reports AI Pipeline — Daily"

    # Check if job already exists
    existing_jobs = list(w.jobs.list(name=JOB_NAME))
    if existing_jobs:
        job_id = existing_jobs[0].job_id
        print(f"Job already exists (id={job_id}). Updating schedule...")
        update_target = existing_jobs[0]
    else:
        job_id = None

    job_settings = {
        "name": JOB_NAME,
        "tasks": [
            {
                "task_key": "run_ai_pipeline",
                "notebook_task": {
                    "notebook_path": PIPELINE_NOTEBOOK_PATH,
                    "base_parameters": {
                        "batch_size": "200",
                        "dry_run":    "false"
                    }
                },
                "existing_cluster_id": spark.conf.get("spark.databricks.clusterUsageTags.clusterId", ""),
                # For production use a new cluster:
                # "new_cluster": {
                #     "spark_version": "15.4.x-scala2.12",
                #     "node_type_id": "Standard_D4s_v3",
                #     "num_workers": 2,
                #     "azure_attributes": {"availability": "SPOT_AZURE"}
                # }
            }
        ],
        "schedule": {
            "quartz_cron_expression": "0 30 2 * * ?",  # 2:30 AM daily AEST (UTC+10 = 16:30 UTC)
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

    workspace_url = HOST
    print(f"\nJob URL: https://{workspace_url}/jobs/{job_id}")
    return job_id


try:
    JOB_ID = create_or_update_pipeline_job()
except Exception as e:
    print(f"Job creation skipped (workshop environment): {e}")
    JOB_ID = None
    print("In production: configure the job via the Jobs UI or Databricks Asset Bundles.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 9 — Monitor Pipeline Runs
# MAGIC
# MAGIC After scheduling, monitor pipeline health with these queries.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9a — Daily processing metrics

# COMMAND ----------

spark.sql(f"""
SELECT
    DATE(processed_at)                                 AS processing_date,
    COUNT(*)                                           AS records_processed,
    SUM(CASE WHEN processing_status='PROCESSED' THEN 1 ELSE 0 END) AS successful,
    SUM(CASE WHEN processing_status='FAILED'    THEN 1 ELSE 0 END) AS failed,
    ROUND(SUM(CASE WHEN processing_status='PROCESSED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
                                                       AS success_pct,
    ROUND(AVG(source_text_length), 0)                  AS avg_doc_chars,
    SUM(source_text_length)                            AS total_chars_processed
FROM {CATALOG}.{SCHEMA}.processed_reports
GROUP BY DATE(processed_at)
ORDER BY processing_date DESC
""").show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9b — Failed records for investigation

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
# MAGIC ### 9c — Compliance urgency dashboard

# COMMAND ----------

spark.sql(f"""
SELECT
    ai_compliance_urgency,
    COUNT(*)                                           AS document_count,
    COLLECT_LIST(submitting_entity)                    AS entities,
    SUM(COALESCE(ai_capital_value_m, 0))               AS total_capex_m,
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
# MAGIC ## Step 10 — Cost Estimation and Optimisation
# MAGIC
# MAGIC For a production regulated-industry workload, cost control is important.

# COMMAND ----------

# Cost estimation model for this pipeline
def estimate_pipeline_cost(
    monthly_new_docs: int,
    avg_doc_chars: int = 3000,
    model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
) -> dict:
    """
    Estimates monthly AI inference cost for the batch pipeline.
    Assumes 3 AI passes per document (classification + extraction + 2x summarisation).
    """
    # Approximate tokens: 1 token ≈ 4 characters
    chars_per_doc    = avg_doc_chars
    prompt_overhead  = 300   # prompt template tokens per pass
    passes_per_doc   = 4     # classify + extract + 2x summarise

    input_tokens_per_doc  = (chars_per_doc // 4) + prompt_overhead
    output_tokens_per_doc = 200  # avg output per pass

    total_input_tokens  = monthly_new_docs * passes_per_doc * input_tokens_per_doc
    total_output_tokens = monthly_new_docs * passes_per_doc * output_tokens_per_doc

    # PT endpoint pricing for Llama 3.1 8B (approximate, check current pricing)
    # PT endpoints are billed per DBU for provisioned throughput
    # Estimate: 1000 tokens/s PT at 0.07 DBU/s ≈ $0.0042 per 1000 tokens at $0.07/DBU
    # For budgeting use $0.004 per 1000 input tokens, $0.006 per 1000 output tokens
    PRICE_INPUT_PER_1K  = 0.004  # USD per 1000 input tokens (PT Llama 3.1 8B)
    PRICE_OUTPUT_PER_1K = 0.006  # USD per 1000 output tokens

    cost_usd = (
        (total_input_tokens  / 1000) * PRICE_INPUT_PER_1K +
        (total_output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    )

    return {
        "monthly_docs":              monthly_new_docs,
        "ai_passes_per_doc":         passes_per_doc,
        "total_input_tokens_M":      round(total_input_tokens  / 1_000_000, 2),
        "total_output_tokens_M":     round(total_output_tokens / 1_000_000, 2),
        "estimated_cost_usd":        round(cost_usd, 2),
        "cost_per_doc_usd":          round(cost_usd / monthly_new_docs, 4) if monthly_new_docs else 0,
        "model":                     model_name,
    }


print("PIPELINE COST ESTIMATES (per month)")
print("=" * 60)
for scenario in [
    {"docs": 100,   "label": "Small (100 reports/month)"},
    {"docs": 1000,  "label": "Medium (1,000 reports/month)"},
    {"docs": 10000, "label": "Large (10,000 reports/month)"},
]:
    est = estimate_pipeline_cost(scenario["docs"])
    print(f"\n{scenario['label']}:")
    print(f"  Total input tokens:  {est['total_input_tokens_M']}M")
    print(f"  Total output tokens: {est['total_output_tokens_M']}M")
    print(f"  Estimated cost:      USD ${est['estimated_cost_usd']:.2f} (~AUD ${est['estimated_cost_usd']*1.55:.2f})")
    print(f"  Cost per document:   USD ${est['cost_per_doc_usd']:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Cost Optimisation Strategies

# COMMAND ----------

COST_OPTIMISATION_GUIDE = """
BATCH AI PIPELINE — COST OPTIMISATION STRATEGIES
=================================================

1. USE SMALLER MODELS FOR SIMPLE TASKS
   - Classification (pick from list): use 8B model — accuracy comparable to 70B
   - Extraction (structured JSON): 8B is usually sufficient
   - Summarisation (quality matters): consider 70B for executive summaries
   Savings: up to 60% if you select model per task type

2. TRUNCATE INPUT TEXT INTELLIGENTLY
   - Regulatory documents: first 2,000 chars usually contains all key info
   - Work orders: typically < 1,000 chars total
   - Do NOT truncate when extracting dates/references from end of document
   Current implementation truncates to 2,000 chars — review for your documents

3. BATCH DOCUMENTS TOGETHER (FEW-SHOT IN ONE CALL)
   - Instead of 1 call per document, send 3-5 short documents per call
   - Reduces prompt overhead (repeated instructions)
   - Savings: ~20-30% on prompt token count
   Trade-off: more complex prompts, need response parsing

4. CACHE RESULTS AGGRESSIVELY
   - Incremental pattern (LEFT ANTI JOIN) avoids reprocessing
   - Add a content_hash column to detect changed documents
   - Only reprocess if content_hash changes

5. SCHEDULE DURING OFF-PEAK HOURS
   - PT endpoints charged per provisioned throughput
   - Run batch jobs at 2am AEST when cluster is otherwise idle
   - Use scale-to-zero PT endpoint (min_provisioned_throughput=0)

6. RIGHT-SIZE THE PT ENDPOINT
   - For 200 docs/day batch (2am run): 100 tokens/s PT is sufficient
   - Over-provisioning wastes DBU allocation even when idle
   - Monitor utilization in serving endpoint metrics

7. SELECTIVE RE-PROCESSING
   - Only re-run failed records, not all records
   - WHERE processing_status = 'FAILED' in the ANTI JOIN
   - Failed records usually have a correctable cause (prompt fix, not model failure)
"""

print(COST_OPTIMISATION_GUIDE)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab 05 — Final Summary

# COMMAND ----------

print("=" * 65)
print("WORKSHOP 2B — COMPLETE LAB SUMMARY")
print("=" * 65)
print()
print("WHAT WAS BUILT:")
print()
print("  workshop.energy_nem schema:")
spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").select("tableName").show(20, truncate=False)

print("  UC AI Functions:")
try:
    spark.sql(f"SHOW FUNCTIONS IN {CATALOG}.ai_functions").select("function").show(10, truncate=False)
except:
    print("    (run Lab 04 to create AI functions)")

print()
print("KEY ARCHITECTURE DECISIONS:")
print("  1. All AI inference routes through AU East PT endpoint")
print("  2. ai_query(endpoint_name, ...) replaces all ai_*() built-in functions")
print("  3. UC wrapper functions centralise prompt logic — one place to update")
print("  4. Incremental processing with LEFT ANTI JOIN prevents reprocessing")
print("  5. OPTIMIZE + ZORDER after each batch improves downstream query performance")
print("  6. Genie Space uses databricks-qwen3-embedding-0-6b (in-region) for RAG")
print()
print("IN-REGION MODEL REFERENCE:")
print("  LLM inference:   meta-llama/Meta-Llama-3.1-8B-Instruct (AU East PT)")
print("  Embeddings:      databricks-qwen3-embedding-0-6b (AU East)")
print("  Do NOT use:      databricks-gte-large-en (cross-geo)")
print("  Do NOT use:      ai_classify/ai_summarize built-ins (cross-geo)")
print()
print("NEXT STEPS:")
print("  - Add processed_reports to your Genie Space as a trusted asset")
print("  - Create AI/BI dashboard tiles from v_dashboard_outage_summary")
print("  - Enable Genie Agent mode for cross-table questions")
print("  - Schedule the batch pipeline job for daily incremental processing")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab 05 — Review Questions
# MAGIC
# MAGIC 1. The incremental pipeline uses `LEFT ANTI JOIN` to find unprocessed records.
# MAGIC    A document was processed but the result had `processing_status = 'FAILED'`.
# MAGIC    Will it be reprocessed on the next run? Why or why not?
# MAGIC
# MAGIC 2. A colleague suggests using `ai_summarize()` instead of `ai_query(endpoint, ...)`
# MAGIC    to save the PT endpoint deployment effort. What are the two objections you raise?
# MAGIC
# MAGIC 3. The pipeline processes 500 regulatory documents per month.
# MAGIC    Using the cost model above, estimate the monthly cost in AUD
# MAGIC    (use an AUD/USD rate of 0.65) for using Llama 3.1 8B with 4 passes per doc.
# MAGIC
# MAGIC 4. Why do we run `OPTIMIZE ZORDER BY (ai_compliance_urgency, report_type_recorded)`
# MAGIC    rather than `OPTIMIZE ZORDER BY (report_id)`?
# MAGIC
# MAGIC 5. A document extraction returns `ai_capital_value_m = null` even though the document
# MAGIC    says "$143.6M". The extract schema specifies `"capital_value_m": "number in AUD millions"`.
# MAGIC    List two prompt changes you would try to fix this.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## End of Workshop 2B — Genie Spaces & AI Features
# MAGIC
# MAGIC **Workshop Summary:**
# MAGIC
# MAGIC | Lab | Key Skill |
# MAGIC |-----|-----------|
# MAGIC | 01 | Create Genie Space via API; seed schema and golden queries |
# MAGIC | 02 | Admin deep-dive: comments, agent mode, troubleshooting |
# MAGIC | 03 | End-user question quality; Conversation API; Teams integration |
# MAGIC | 04 | In-region AI Functions via PT endpoint; Australian PII masking |
# MAGIC | 05 | Batch AI pipeline; incremental processing; scheduling; cost optimisation |
