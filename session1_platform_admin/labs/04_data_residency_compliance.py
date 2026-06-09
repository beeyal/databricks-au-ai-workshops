# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">Lab 04: Data Residency &amp; Compliance Evidence</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries · Databricks</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | ~25 minutes |
# MAGIC | **Prerequisites** | Labs 01–03 complete |
# MAGIC | **By the end** | Compliance evidence package generated, pre-flight checklist run, regulatory audit log exported |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC | Regulation | Requirement | How this lab addresses it |
# MAGIC |---|---|---|
# MAGIC | Industry data governance | Data processed within permitted Australian jurisdictions | Geography enforcement workspace conf check |
# MAGIC | Data governance obligations | Access logs maintained for all AI assets | Audit log query + evidence package |
# MAGIC | Privacy Act 1988 | Reasonable steps under APP 11 | Pre-flight checklist script |
# MAGIC | Privacy Act 1988 | Cross-border disclosure accountability APP 8 | PII guardrail + geography enforcement |

# COMMAND ----------

# MAGIC %md
# MAGIC ## UI navigation — do this before running any code
# MAGIC
# MAGIC **Confirm workspace region:**
# MAGIC ```
# MAGIC Navigate: accounts.azuredatabricks.net → Workspaces → [your workspace name] → look at the Region field
# MAGIC You should see: australiaeast
# MAGIC ```
# MAGIC
# MAGIC **Geography enforcement toggle:**
# MAGIC ```
# MAGIC Navigate: accounts.azuredatabricks.net → Workspaces → [workspace] → Security and compliance tab
# MAGIC You should see: "Enforce data processing within workspace Geography for Designated Services" — default OFF
# MAGIC ```
# MAGIC
# MAGIC **UC tags in Catalog Explorer:**
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog → [catalog] → [table] → Overview tab → Tags section → [+ Add tag]
# MAGIC ```
# MAGIC
# MAGIC # Geography enforcement verified in Lab 01 preflight.
# MAGIC
# MAGIC > **Two workspace settings must both be correct for AI to work:**
# MAGIC > - **Geography enforcement** → Account Console → Security and compliance → **ON**
# MAGIC > - **Partner-Powered AI Features** → workspace settings → must remain **ON** (NEVER turn this off — it disables Genie, Genie Code, and AI/BI entirely)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 0: Setup</h2>
# MAGIC </div>

# COMMAND ----------

# NOTE: Run this — imports only, no side effects. Fails fast if the SDK isn't installed.
import os
import json
import requests
from datetime import datetime, timezone, date, timedelta
from databricks.sdk import WorkspaceClient

# COMMAND ----------

# NOTE: Set workspace URL, account ID, catalog, schema, and endpoint name here before running.
dbutils.widgets.text("workspace_url", "https://<your-workspace>.azuredatabricks.net", "Workspace URL")
dbutils.widgets.text("account_id",    "<your-account-id>",                            "Account ID")
dbutils.widgets.text("catalog",       "workshop_au",                                  "Catalog name")
dbutils.widgets.text("schema",        "ai_governance",                                "Schema name")
dbutils.widgets.text("gw_endpoint",   "au_east_llm_inregion",                         "AI Gateway endpoint name")

WORKSPACE_URL_W = dbutils.widgets.get("workspace_url")
ACCOUNT_ID_W    = dbutils.widgets.get("account_id")
CATALOG_W       = dbutils.widgets.get("catalog")
SCHEMA_W        = dbutils.widgets.get("schema")
GW_ENDPOINT     = dbutils.widgets.get("gw_endpoint")

print(f"Workspace URL   : {WORKSPACE_URL_W}")
print(f"Account ID      : {ACCOUNT_ID_W}")
print(f"Catalog.Schema  : {CATALOG_W}.{SCHEMA_W}")
print(f"GW endpoint     : {GW_ENDPOINT}")

# COMMAND ----------

# NOTE: Loads your PAT and initialises the WorkspaceClient — run before any section below.
WORKSPACE_URL = WORKSPACE_URL_W
ACCOUNT_ID    = ACCOUNT_ID_W

try:
    DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")
except Exception:
    DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "<paste-token-here>")

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

w = WorkspaceClient(host=WORKSPACE_URL, token=DATABRICKS_TOKEN)
print(f"WorkspaceClient initialized — host: {w.config.host}")

REPORT_TIMESTAMP = datetime.now(timezone.utc).isoformat()
print(f"Compliance evidence run timestamp: {REPORT_TIMESTAMP}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 1: Verify Workspace Region</h2>
# MAGIC </div>
# MAGIC
# MAGIC Azure IMDS is the most authoritative source. On serverless compute, IMDS returns a connection error — verify the region via Account Console and include a screenshot in your evidence package.

# COMMAND ----------

# NOTE: Attempts IMDS region check — returns "unknown" on serverless; take a screenshot as evidence instead.
def check_workspace_region_from_host(workspace_url: str) -> dict:
    """
    Attempt to confirm the Azure region via IMDS (only reachable from classic compute nodes).
    Returns 'unknown' on serverless or when network policy blocks 169.254.x.x.
    """
    try:
        imds_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
        resp = requests.get(imds_url, headers={"Metadata": "true"}, timeout=5)
        if resp.status_code == 200:
            m = resp.json().get("compute", {})
            return {"location": m.get("location"), "vm_size": m.get("vmSize"), "source": "Azure IMDS (authoritative)"}
    except Exception:
        pass
    return {
        "location": "unknown — verify via Account Console screenshot",
        "source":   "IMDS unreachable (serverless or network policy). Run from a classic cluster for IMDS confirmation.",
    }


print(f"SDK host : {w.config.host}")
region_check = check_workspace_region_from_host(WORKSPACE_URL)
for k, v in region_check.items():
    print(f"  {k:<15} {v}")

# COMMAND ----------

# NOTE: Reads Spark conf tags for cloud provider and cluster ID — faster than IMDS on classic compute.
# Spark conf tags — set by the Databricks runtime on Azure; fast and reliable cluster-level signal
try:
    cluster_cloud = spark.conf.get("spark.databricks.clusterUsageTags.clusterCloudProvider", "unknown")
    cluster_id    = spark.conf.get("spark.databricks.clusterUsageTags.clusterId", "unknown")
    workspace_id  = spark.conf.get("spark.databricks.workspaceId", "unknown")

    print("Cluster Spark conf tags:")
    print(f"  Cloud provider  : {cluster_cloud}")
    print(f"  Cluster ID      : {cluster_id}")
    print(f"  Workspace ID    : {workspace_id}")
except Exception as e:
    print(f"Could not read Spark conf tags: {e}")

display(spark.sql("""
  SELECT
    CURRENT_CATALOG()  AS current_catalog,
    CURRENT_DATABASE() AS current_schema,
    CURRENT_USER()     AS running_as
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 2: Generate Compliance Evidence Package</h2>
# MAGIC </div>
# MAGIC
# MAGIC Assembles the evidence into a structured JSON document. Fill in organisation name and assessor name before sharing with your security team.

# COMMAND ----------

# NOTE: Checks the geography enforcement toggle via API — WARN is expected if you don't have account admin.
def check_geography_enforcement(workspace_client: WorkspaceClient) -> dict:
    """
    Check whether geography enforcement is enabled via workspace-conf API.
    Returns CANNOT_VERIFY when the key is not recognised (most workspace tiers).
    Falls back gracefully — never raises — so the evidence package can proceed.
    Note: CSP (Compliance Security Profile) is a separate account-level setting.
    """
    try:
        conf = workspace_client.workspace_conf.get_status(keys="enableDataProcessingWithinGeography")
        value = conf.get("enableDataProcessingWithinGeography", "").lower() if conf else ""

        if value == "true":
            return {"status": "PASS", "raw_value": value,
                    "reason": "Geography enforcement is ENABLED", "compliant": True}
        elif value == "false":
            return {"status": "FAIL", "raw_value": value,
                    "reason": "Geography enforcement is NOT enabled",
                    "recommendation": "Enable via Account Console → Workspaces → Security and compliance tab",
                    "compliant": False}
        else:
            return {"status": "CANNOT_VERIFY", "raw_value": value or "(empty)",
                    "reason": "Key readable but value empty or unset. Verify via Account Console UI.",
                    "recommendation": "Attach Account Console screenshot as compliance evidence.",
                    "compliant": None}
    except Exception as e:
        err_str = str(e)
        reason_map = {
            "INVALIDKEYS": "Key 'enableDataProcessingWithinGeography' is not valid on this workspace tier.",
            "BAD_REQUEST": "Geography enforcement key is not valid on this workspace tier (BadRequest).",
            "403": "Insufficient permissions to read workspace configuration.",
            "PERMISSION_DENIED": "Insufficient permissions to read workspace configuration.",
        }
        reason_detail = next((v for k, v in reason_map.items() if k in err_str.upper()), err_str[:200])
        return {
            "status": "CANNOT_VERIFY",
            "reason": f"{reason_detail} Verify via Account Console UI and attach a screenshot.",
            "recommendation": "accounts.azuredatabricks.net → Workspaces → [workspace] → Security and compliance tab",
            "compliant": None,
        }


geo_result = check_geography_enforcement(w)
print("=== Geography Enforcement Check ===")
print(json.dumps(geo_result, indent=2))

icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "CANNOT_VERIFY": "[WARN]"}.get(geo_result["status"], "[?]")
print(f"\n{icon} {geo_result['reason']}")

# COMMAND ----------

# NOTE: Reference — prints the AI feature residency inventory showing which features are approved for regulated data.
# Feature inventory — used in the compliance evidence package and final summary.
# NOT_FLAG_CONTROLLED = feature is governed by endpoint config/AI Gateway rules, not a binary workspace toggle.
AI_FEATURE_INVENTORY = [
    {"feature_name": "Genie Spaces", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Queries execute in-region."},
    {"feature_name": "Genie Agent Mode (within Genie Spaces)", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "In-region for ANZ. Distinct from Supervisor Agent Bricks."},
    {"feature_name": "AI Gateway", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Rate limits, guardrails, payload logging recommended before user enablement."},
    {"feature_name": "FMAPI Provisioned Throughput", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Select australiaeast PT endpoint type at creation."},
    {"feature_name": "FMAPI Pay-Per-Token (in-geo: claude-haiku-4-5, claude-sonnet-4-5/4-6, claude-opus-4-6, gpt-oss-20b/120b, qwen3-embedding-0-6b)",
     "residency": "IN_REGION", "risk_rating": "LOW", "approved_for_regulated_data": True,
     "notes": "Natively in-region for AU East. No cross-geo routing required."},
    {"feature_name": "FMAPI Pay-Per-Token (cross-geo: Llama, Gemma, qwen35-122b-a10b, qwen3-next-80b-a3b-instruct, older Claude Sonnet 4)",
     "residency": "CROSS_GEO", "risk_rating": "HIGH", "approved_for_regulated_data": False,
     "notes": "Requires cross-geo routing enabled. Do NOT use for regulated data."},
    {"feature_name": "External Models (Azure OpenAI Regional)", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Verify Azure OpenAI resource deployed in australiaeast."},
    {"feature_name": "Vector Search", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Use databricks-qwen3-embedding-0-6b for in-region embeddings."},
    {"feature_name": "Knowledge Assistant (Agent Bricks)", "residency": "CROSS_GEO", "risk_rating": "HIGH",
     "approved_for_regulated_data": False, "notes": "No committed in-geo date as of June 2026."},
    {"feature_name": "Supervisor Agent / MAS (Agent Bricks)", "residency": "CROSS_GEO", "risk_rating": "HIGH",
     "approved_for_regulated_data": False, "notes": "No committed in-geo date as of June 2026."},
    {"feature_name": "Foundation Model Fine-tuning", "residency": "NOT_AVAILABLE", "risk_rating": "N/A",
     "approved_for_regulated_data": False, "notes": "Not available in AU East."},
    {"feature_name": "MLflow Tracking", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Experiment metadata and artifacts stored in workspace-local storage."},
    {"feature_name": "AI Functions (ai_query via PT endpoint)", "residency": "IN_REGION", "risk_rating": "LOW",
     "approved_for_regulated_data": True, "notes": "Point ai_query() at a PT endpoint. Default FMAPI endpoint is cross-geo."},
]

print(f"{'Feature':<50} {'Residency':<14} {'Approved'}")
print("-" * 78)
for f in AI_FEATURE_INVENTORY:
    approved = "YES" if f["approved_for_regulated_data"] else "NO"
    print(f"  {f['feature_name']:<48} {f['residency']:<14} {approved}")

# COMMAND ----------

# NOTE: Assembles and prints the full compliance evidence package — fill in TODO fields before sharing.
not_approved = [f for f in AI_FEATURE_INVENTORY if not f["approved_for_regulated_data"]]

compliance_package = {
    "document_type":   "AI Governance Compliance Evidence Package",
    "organisation":    "TODO: Your Organisation Name",
    "workspace_url":   WORKSPACE_URL,
    "account_id":      ACCOUNT_ID,
    "assessment_date": REPORT_TIMESTAMP,
    "assessed_by":     "TODO: Name/Role",
    "regulatory_frameworks": ["Privacy Act 1988"],
    "section_1_infrastructure": {
        "workspace_region":                     region_check.get("location", "unknown"),
        "region_verification_source":           region_check.get("source", "unknown"),
        "cloud_provider":                       "Microsoft Azure",
        # Geography enforcement = workspace conf key 'enableDataProcessingWithinGeography'
        # This is the toggle in Account Console. It is NOT the Compliance Security Profile (CSP).
        "geography_enforcement_enabled":        geo_result.get("compliant"),
        "geography_enforcement_status":         geo_result.get("status"),
        "geography_enforcement_detail":         geo_result.get("reason"),
    },
    "section_2_feature_inventory": {
        "total_features_reviewed": len(AI_FEATURE_INVENTORY),
        "in_region_approved":      sum(1 for f in AI_FEATURE_INVENTORY if f["residency"] == "IN_REGION"),
        "not_approved_count":      len(not_approved),
        "features":                AI_FEATURE_INVENTORY,
    },
    # Access controls below are DECLARED — not auto-verified by this script.
    # Attach supporting evidence from Labs 01-03 to validate each declared control.
    "section_3_access_controls_declared": [
        "Unity Catalog RBAC on all AI assets (verify: Lab 01 endpoint permissions output)",
        "Rate limits on all endpoints (verify: Lab 01 rate limit config output)",
        "PII BLOCK + safety filter on all production endpoints (verify: Lab 02 guardrail test results)",
        "Payload logging to Delta via inference_table_config on all production endpoints (verify: Lab 01)",
    ],
    "section_4_exceptions": {
        "features_requiring_exception": [
            {"feature": f["feature_name"], "risk": f["risk_rating"], "status": f["residency"]}
            for f in not_approved
        ],
        "exception_process": "Requires CISO + Data Governance Council sign-off before use with regulated data.",
    },
}

print("=== COMPLIANCE EVIDENCE PACKAGE ===\n")
print(json.dumps(compliance_package, indent=2, default=str))

# COMMAND ----------

# NOTE: Uncomment to persist the compliance evidence package to a Delta table for audit retention.
CATALOG_NAME = CATALOG_W
SCHEMA_NAME  = SCHEMA_W

# Uncomment to persist the evidence to Delta for audit retention
# spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")
# row = {
#     "assessment_timestamp":            compliance_package["assessment_date"],
#     "workspace_url":                   compliance_package["workspace_url"],
#     "geography_enforcement_compliant": compliance_package["section_1_infrastructure"]["geography_enforcement_enabled"],
#     "geography_enforcement_status":    compliance_package["section_1_infrastructure"]["geography_enforcement_status"],
#     "workspace_region":                compliance_package["section_1_infrastructure"]["workspace_region"],
#     "not_approved_count":              compliance_package["section_2_feature_inventory"]["not_approved_count"],
#     "full_package_json":               json.dumps(compliance_package, default=str),
# }
# spark.createDataFrame([row]).write.format("delta").mode("append").option("mergeSchema", "true") \
#     .saveAsTable(f"{CATALOG_NAME}.{SCHEMA_NAME}.ai_compliance_evidence")
# print(f"Evidence saved to {CATALOG_NAME}.{SCHEMA_NAME}.ai_compliance_evidence")

print("Evidence package Delta save: pattern provided above — uncomment to execute.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 3: Regulatory Compliance Audit Evidence — AI Model Access Logs</h2>
# MAGIC </div>
# MAGIC
# MAGIC `system.access.audit` captures admin-level actions: endpoint creation, AI Gateway config updates, permission changes. Retain per your organisation's policy — typically 7 years for regulatory obligations.
# MAGIC
# MAGIC **What is NOT in `system.access.audit`:** Per-request inference detail. For per-request audit, use `system.ai_gateway.usage` (Beta, AU East).
# MAGIC
# MAGIC **UI:** Left sidebar → Catalog → system → access → audit → Sample Data tab → filter `service_name` to `serverlessRealTimeInference`

# COMMAND ----------

# NOTE: Queries the last 30 days of AI admin events from system.access.audit for audit evidence.
def generate_ai_access_log(start_date: str, end_date: str, include_endpoints: list = None):
    """
    Generate an AI model admin action log for Privacy Act and governance audit purposes.
    Uses strict less-than against start of next day to avoid sub-second gaps at 23:59:59.
    """
    endpoint_filter = ""
    if include_endpoints:
        names = ", ".join(f"'{n}'" for n in include_endpoints)
        endpoint_filter = f"AND request_params['endpointName'] IN ({names})"

    access_log_sql = f"""
    SELECT
      event_time                                       AS access_time,
      user_identity.email                              AS user_email,
      user_identity.subject_name                       AS identity_type,
      source_ip_address                                AS source_ip,
      action_name                                      AS action,
      service_name                                     AS service,
      request_params['endpointName']                   AS endpoint_name,
      response.status_code                             AS response_code,
      request_id                                       AS audit_request_id
    FROM system.access.audit
    WHERE
      event_time >= TIMESTAMP '{start_date} 00:00:00'
      AND event_time < TIMESTAMP '{end_date} 00:00:00' + INTERVAL 1 DAY
      AND service_name IN ('serverlessRealTimeInference', 'databricksGenie', 'aiPlayground')
      {endpoint_filter}
    ORDER BY event_time DESC
    """

    print(f"AI Admin Action Log: {start_date} to {end_date} (inclusive)")
    print(f"Service filter: serverlessRealTimeInference, databricksGenie, aiPlayground")
    print(f"Endpoint filter: {endpoint_filter or 'All AI service endpoints'}\n")

    df        = spark.sql(access_log_sql)
    row_count = df.count()
    print(f"Total admin action events in period: {row_count:,}")
    display(df)
    return df


AUDIT_END   = date.today().isoformat()
AUDIT_START = (date.today() - timedelta(days=30)).isoformat()

access_log_df = generate_ai_access_log(AUDIT_START, AUDIT_END)

# COMMAND ----------

# NOTE: Uncomment to export the access log to a UC volume as CSV for offline audit submission.
# Uncomment to export access log to a Unity Catalog volume (CSV) for offline audit submission
# spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.audit_exports")
# (access_log_df.coalesce(1).write.mode("overwrite").option("header", "true")
#     .csv(f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/audit_exports/ai_access_log_{AUDIT_START}_to_{AUDIT_END}.csv"))
# print(f"Access log exported to /Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/audit_exports/")

print("Access log export pattern: uncomment to execute after confirming catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 4: Unity Catalog Tag Schema for AI Asset Classification</h2>
# MAGIC </div>
# MAGIC
# MAGIC UC governed tags classify AI assets by data sensitivity. Tags are immediately visible to all users with SELECT on the asset and queryable via `system.information_schema.table_tags`.
# MAGIC
# MAGIC **UI:** Left sidebar → Catalog → [catalog] → [table or model] → Overview tab → Tags section → [+ Add tag]

# COMMAND ----------

# NOTE: Reference — prints the UC tag schema for AI asset classification. No changes made here.
AI_TAG_SCHEMA = {
    "data_classification": (["public", "internal", "confidential", "restricted", "secret"], "internal"),
    "data_residency":      (["au-east", "any-au", "global"],                                "au-east"),
    "pii_processes":       (["yes", "no", "conditional"],                                   "no"),
    "regulatory_scope":    (["privacy-act-1988", "aer", "ner", "none"],                     "none"),
    "ai_approved":         (["approved", "pending-review", "not-approved", "conditional"],  "pending-review"),
    "owner_team":          (None,                                                            None),
}

print("AI Asset Classification Tag Schema")
print(f"{'Tag':<25} {'Default':<20} Allowed values")
print("-" * 80)
for tag_name, (values, default) in AI_TAG_SCHEMA.items():
    vals = ", ".join(values) if values else "(free text)"
    print(f"  {tag_name:<23} {str(default):<20} {vals}")

# COMMAND ----------

# NOTE: Reference only — copy the ALTER statements into a SQL cell to apply tags to your assets.
TAG_SQL_EXAMPLES = """
-- Apply a residency policy tag at the catalog level
ALTER CATALOG energy_ai
  SET TAGS ('data_residency_policy' = 'au-east-only');

-- Tag a registered model in Unity Catalog
ALTER MODEL energy_ai.models.meter_anomaly_v1
  SET TAGS (
    'data_classification' = 'confidential',
    'data_residency'      = 'au-east',
    'pii_processes'       = 'no',
    'regulatory_scope'    = 'aer',
    'ai_approved'         = 'approved',
    'owner_team'          = 'grp_data_science'
  );

-- Serving endpoints are NOT Unity Catalog objects — tag them via REST API:
--   PUT /api/2.0/serving-endpoints/{name}/tags
--   Body: {"tags": [{"key": "ai_approved", "value": "approved"}, ...]}

-- Query all UC table tags by classification
SELECT
  catalog_name, schema_name, table_name AS asset_name, tag_name, tag_value
FROM system.information_schema.table_tags
WHERE tag_name IN ('data_classification', 'ai_approved', 'regulatory_scope')
ORDER BY asset_name, tag_name;
"""

print("Tag SQL examples (copy into a %sql cell to run):\n")
print(TAG_SQL_EXAMPLES)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 5: Pre-flight Checklist — Before Enabling AI for New User Groups</h2>
# MAGIC </div>
# MAGIC
# MAGIC Run this checklist every time you enable AI access for a new business unit or user group. Resolve all FAIL items before proceeding. WARN items require out-of-band confirmation.
# MAGIC
# MAGIC **UI (manual pre-flight equivalent):**
# MAGIC 1. accounts.azuredatabricks.net → Workspaces → [workspace] → Security and compliance tab → verify Geography enforcement is ON
# MAGIC 2. Left sidebar → AI Gateway → [endpoint] → verify state is Ready
# MAGIC 3. Edit Unity AI Gateway → confirm PII BLOCK + safety filter are enabled on input and output
# MAGIC 4. User management → Groups → confirm target group exists

# COMMAND ----------

# NOTE: Runs the pre-flight checklist against your endpoint and group — resolve all FAIL items before onboarding.
def run_preflight_checklist(
    workspace_url: str, headers: dict, workspace_client: WorkspaceClient,
    endpoint_name: str, target_group: str,
) -> dict:
    """
    Run pre-flight checks before enabling AI access for a new group.
    CANNOT_VERIFY results are treated as WARN rather than FAIL.
    """
    results = []

    def add_check(name: str, status: str, detail: str = "", remediation: str = "") -> None:
        results.append({"check": name, "status": status, "detail": detail,
                        "remediation": remediation if status != "PASS" else ""})

    # 1. Workspace region
    try:
        region   = check_workspace_region_from_host(workspace_url)
        location = region.get("location", "")
        if "australiaeast" in location.lower():
            add_check("Workspace in australiaeast", "PASS", detail=location)
        elif "unknown" in location.lower():
            add_check("Workspace in australiaeast", "WARN",
                      detail="Region could not be confirmed via IMDS (serverless or network policy)",
                      remediation="Verify region via Account Console and attach a screenshot.")
        else:
            add_check("Workspace in australiaeast", "FAIL", detail=location,
                      remediation="Do not use this workspace for AU-regulated data.")
    except Exception as e:
        add_check("Workspace region check", "FAIL", detail=str(e))

    # 2. Geography enforcement — WARN if cannot verify (requires admin)
    geo = check_geography_enforcement(workspace_client)
    if geo["compliant"] is True:
        add_check("Geography enforcement enabled", "PASS", detail=geo.get("reason", ""))
    elif geo["compliant"] is False:
        add_check("Geography enforcement enabled", "FAIL",
                  detail=geo.get("reason", ""),
                  remediation=geo.get("recommendation", "Enable via Account Console → Security and compliance tab"))
    else:
        add_check("Geography enforcement enabled", "WARN",
                  detail=geo.get("reason", "Cannot verify"),
                  remediation="Obtain account/workspace admin confirmation before enabling AI access.")

    # 3. Target endpoint exists and is READY
    try:
        ep_url   = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}"
        ep_resp  = requests.get(ep_url, headers=headers, timeout=15)
        ep_json  = ep_resp.json() if ep_resp.status_code == 200 else {}
        ep_ready = (ep_resp.status_code == 200 and ep_json.get("state", {}).get("ready") == "READY")
        detail   = f"State: {ep_json.get('state', {}).get('ready', 'unknown')}" if ep_resp.status_code == 200 else f"HTTP {ep_resp.status_code}"
        add_check(f"Endpoint '{endpoint_name}' is READY", "PASS" if ep_ready else "FAIL",
                  detail=detail, remediation="Wait for endpoint to reach READY state.")

        if ep_resp.status_code == 200:
            gateway    = ep_json.get("ai_gateway", {})
            guardrails = gateway.get("guardrails", {})
            pii_block  = guardrails.get("input", {}).get("pii", {}).get("behavior") == "BLOCK"
            safety_on  = guardrails.get("input", {}).get("safety", False)
            usage_on   = gateway.get("usage_tracking_config",  {}).get("enabled", False)
            payload_on = gateway.get("inference_table_config", {}).get("enabled", False)
            rate_set   = len(gateway.get("rate_limits", [])) > 0

            add_check("AI Gateway: PII BLOCK on input",  "PASS" if pii_block  else "FAIL",
                      remediation="Set guardrails.input.pii.behavior = BLOCK via AI Gateway config update.")
            add_check("AI Gateway: Safety filter on",    "PASS" if safety_on  else "FAIL",
                      remediation="Set guardrails.input.safety = true in AI Gateway config.")
            add_check("AI Gateway: Usage tracking on",   "PASS" if usage_on   else "FAIL",
                      remediation="Enable usage_tracking_config.enabled = true in AI Gateway config.")
            add_check("AI Gateway: Payload logging on",  "PASS" if payload_on else "FAIL",
                      remediation="Enable inference_table_config with a valid catalog/schema/table_name_prefix.")
            add_check("AI Gateway: Rate limits set",     "PASS" if rate_set   else "FAIL",
                      remediation="Add at least one rate limit (e.g., endpoint-level QPM) in AI Gateway config.")

    except Exception as e:
        add_check("Endpoint check", "FAIL", detail=str(e))

    # 4. Target group exists in the workspace
    try:
        groups       = list(workspace_client.groups.list(filter=f"displayName eq \"{target_group}\""))
        group_exists = len(groups) > 0
        add_check(f"Group '{target_group}' exists",
                  "PASS" if group_exists else "FAIL",
                  detail=f"Found {len(groups)} match(es)",
                  remediation=f"Create the group '{target_group}' before assigning endpoint access.")
    except Exception as e:
        add_check(f"Group '{target_group}' exists", "FAIL", detail=str(e))

    # 5. Endpoint has permission entries
    try:
        perms_url  = f"{workspace_url}/api/2.0/permissions/serving-endpoints/{endpoint_name}"
        perms_resp = requests.get(perms_url, headers=headers, timeout=15)
        has_perms  = perms_resp.status_code == 200 and bool(perms_resp.json().get("access_control_list"))
        add_check("Serving endpoint has permission entries",
                  "PASS" if has_perms else "FAIL",
                  detail=f"HTTP {perms_resp.status_code}",
                  remediation="Add CAN_QUERY grant for the target group before enabling access.")
    except Exception as e:
        add_check("Endpoint permissions check", "FAIL", detail=str(e))

    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    all_passed = fail_count == 0

    return {
        "preflight_timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint_name":       endpoint_name,
        "target_group":        target_group,
        "overall_status":      "PASS — safe to enable AI access" if all_passed else "FAIL — resolve issues before enabling AI access",
        "all_checks_passed":   all_passed,
        "fail_count":          fail_count,
        "warn_count":          warn_count,
        "checks":              results,
    }


def print_preflight_report(report: dict) -> None:
    print("=" * 70)
    print("Pre-flight Checklist Report")
    print(f"Endpoint    : {report['endpoint_name']}")
    print(f"Target group: {report['target_group']}")
    print(f"Timestamp   : {report['preflight_timestamp']}")
    print("=" * 70)
    print()

    for check in report["checks"]:
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}.get(check["status"], "[?]")
        print(f"  {icon}  {check['check']}")
        if check.get("detail"):
            print(f"         {check['detail']}")
        if check.get("remediation"):
            label = "FIX" if check["status"] == "FAIL" else "ACT"
            print(f"  {label}  → {check['remediation']}")

    print()
    print(f"  Overall: {report['overall_status']}")
    if report["fail_count"] > 0:
        print(f"  Resolve {report['fail_count']} FAIL item(s) before enabling AI access.")
    if report["warn_count"] > 0:
        print(f"  {report['warn_count']} WARN item(s) require out-of-band confirmation — document separately.")


PREFLIGHT_ENDPOINT = GW_ENDPOINT
PREFLIGHT_GROUP    = "grp_analysts"        # Update to your target group

preflight_report = run_preflight_checklist(
    workspace_url=WORKSPACE_URL, headers=HEADERS, workspace_client=w,
    endpoint_name=PREFLIGHT_ENDPOINT, target_group=PREFLIGHT_GROUP,
)

print_preflight_report(preflight_report)

# COMMAND ----------

# NOTE: Uncomment to persist the pre-flight report to Delta as change management evidence.
# Uncomment to save the pre-flight report to Delta for change management evidence
# row = {
#     "check_timestamp":  preflight_report["preflight_timestamp"],
#     "endpoint_name":    preflight_report["endpoint_name"],
#     "target_group":     preflight_report["target_group"],
#     "all_passed":       preflight_report["all_checks_passed"],
#     "pass_count":       sum(1 for c in preflight_report["checks"] if c["status"] == "PASS"),
#     "fail_count":       preflight_report["fail_count"],
#     "warn_count":       preflight_report["warn_count"],
#     "full_report_json": json.dumps(preflight_report, default=str),
# }
# spark.createDataFrame([row]).write.format("delta").mode("append").option("mergeSchema", "true") \
#     .saveAsTable(f"{CATALOG_NAME}.{SCHEMA_NAME}.ai_preflight_checks")
# print(f"Pre-flight report saved to {CATALOG_NAME}.{SCHEMA_NAME}.ai_preflight_checks")

print("Pre-flight report Delta save: uncomment to execute after configuring catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 6: Final Compliance Summary</h2>
# MAGIC </div>

# COMMAND ----------

# NOTE: Prints the final compliance summary — read the output and resolve any FAIL or WARN items.
geo_status  = geo_result.get("status", "UNKNOWN")
geo_display = {
    "PASS":          "ENABLED [PASS]",
    "FAIL":          "NOT ENABLED [FAIL]",
    "CANNOT_VERIFY": "UNVERIFIED [WARN] — confirm with admin",
}.get(geo_status, geo_status)

workspace_region_display = region_check.get("location", "unknown")

in_region  = [f for f in AI_FEATURE_INVENTORY if f["residency"] == "IN_REGION"]
restricted = [f for f in AI_FEATURE_INVENTORY if f["residency"] in ("CROSS_GEO", "NOT_AVAILABLE")]
pf_status  = "ALL PASSED" if preflight_report["all_checks_passed"] else (
    f"ISSUES ({preflight_report['fail_count']} failing, {preflight_report['warn_count']} warn)"
)

print("=" * 60)
print(f"AI GOVERNANCE COMPLIANCE SUMMARY — {REPORT_TIMESTAMP[:10]}")
print("=" * 60)
print(f"  Workspace region       : {workspace_region_display}")
print(f"  Geography enforcement  : {geo_display}")
print(f"  In-region features     : {len(in_region)}")
print(f"  Restricted/unavailable : {len(restricted)}")
print(f"  Pre-flight checks      : {pf_status}")
print(f"  PII guardrail          : BLOCK on all prod endpoints (verify: pre-flight above)")
print(f"  Admin audit log        : system.access.audit (service: serverlessRealTimeInference)")
print(f"  Per-request audit      : system.ai_gateway.usage (Beta, in-region AU East)")
print()
print("  FEATURES NOT APPROVED FOR REGULATED DATA:")
for f in restricted:
    print(f"    - {f['feature_name']} ({f['residency']})")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Checkpoint &amp; Workshop Recap</h2>
# MAGIC </div>

# COMMAND ----------

# NOTE: Checkpoint — reference only, lists everything covered in this lab. No action needed.
print("=" * 60)
print("Lab 04 — Checkpoint Summary")
print("=" * 60)

checks = [
    "Workspace region verification via Azure IMDS and Spark conf",
    "Geography enforcement check via workspace conf API",
    "AI feature inventory: 13 features reviewed with residency and approval status",
    "Compliance evidence package generated (structured JSON with regulatory frameworks)",
    "Evidence package Delta save: pattern provided (uncomment to execute)",
    "Regulatory compliance audit log query: AI admin events with user/IP/action",
    "Access log export pattern: provided (uncomment to execute)",
    "UC tag schema defined for AI asset classification",
    "Pre-flight checklist: PASS/FAIL/WARN with geography enforcement as WARN for non-admins",
    "Pre-flight report Delta save: pattern provided (uncomment to execute)",
    "Final compliance summary with correct region from region_check",
]

for check in checks:
    print(f"  [DONE]  {check}")

print()
print("-" * 60)
print("  This is the final lab in the Workshop 1 Admin Track.")
print("-" * 60)
print()
print("=" * 60)
print("WORKSHOP COMPLETE — All 4 labs finished")
print("=" * 60)
print()
print("Recommended next steps:")
print("  1. Enable Geography enforcement in Account Console")
print("  2. Create AI Gateway endpoints for each access tier")
print("  3. Apply PII BLOCK + safety guardrails on all production endpoints")
print("  4. Schedule the daily budget alert notebook (Lab 03)")
print("  5. Run the pre-flight checklist before each new team onboarding")
print("  6. Tag all AI assets in Unity Catalog")
print("  7. Schedule the compliance evidence package as a quarterly job")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #F0F4F8; padding: 16px; border-radius: 6px; margin-top: 16px">
# MAGIC <h3 style="color: #1B3139; margin: 0 0 12px 0">Compliance Evidence Artefact Checklist</h3>
# MAGIC
# MAGIC | Artefact | Regulatory obligation | Source | How to produce |
# MAGIC |---|---|---|---|
# MAGIC | Workspace region confirmation | AER data sovereignty | Azure IMDS / Spark conf | Section 1 output |
# MAGIC | Geography enforcement evidence | Privacy Act APP 8 / AER guidelines | Account Console screenshot + Section 2 API output | Section 2 output |
# MAGIC | Feature inventory | Your organisation's compliance obligations | This notebook | Section 2 printed table |
# MAGIC | AI admin action log (per review period) | Access records retention obligation | `system.access.audit` | Section 3 export to CSV |
# MAGIC | Per-request inference log | Model access detail | `system.ai_gateway.usage` (Beta) | Query separately — Lab 03 |
# MAGIC | Rate limit configuration | Privacy Act APP 11 (reasonable security steps) | AI Gateway API | Lab 01 compliance check output |
# MAGIC | Guardrail test evidence | Privacy Act APP 11 / APP 8 | Lab 02 test results | `print_guardrail_report` output |
# MAGIC | Pre-flight checklist run log | Change management evidence | Delta table | Section 5 in this notebook |
# MAGIC | Budget alert job definition | Governance / cost control | Databricks Jobs API | Lab 03 Section 5 SDK snippet |
# MAGIC </div>
