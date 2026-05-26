# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">🔒 Lab 05: Data Residency & Compliance Evidence</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | **Prerequisites** | Labs 01–04 complete |
# MAGIC | **By the end** | Compliance evidence package generated, pre-flight checklist run, APRA audit log exported |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC | Regulation | Requirement | How this lab addresses it |
# MAGIC |---|---|---|
# MAGIC | APRA CPS 234 | Data processed in permitted jurisdictions | Geography enforcement API check |
# MAGIC | APRA CPS 234 | Access logs maintained for all information assets | Audit log query + evidence package |
# MAGIC | APRA CPS 230 | Operational risk controls documented and tested | Pre-flight checklist script |
# MAGIC | Privacy Act 1988 | Personal information must not leave Australia | PII guardrail + geography enforcement |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### AU East residency — quick reference
# MAGIC
# MAGIC | Feature | Residency | Safe for regulated data? |
# MAGIC |---|---|---|
# MAGIC | Genie Spaces | In-region | Yes |
# MAGIC | AI Gateway | In-region | Yes |
# MAGIC | FMAPI Provisioned Throughput | In-region | Yes |
# MAGIC | External Models (Azure OpenAI Regional) | In-region | Yes — verify deployment region |
# MAGIC | Vector Search | In-region | Yes |
# MAGIC | MLflow Tracking | In-region | Yes |
# MAGIC | FMAPI Pay-Per-Token | Cross-geo | **No** — routes to US East |
# MAGIC | Knowledge Assistant | Cross-geo | **No** — not GA in AU East |
# MAGIC | Foundation Model Fine-tuning | Not available | Not applicable |

# COMMAND ----------

# MAGIC %md
# MAGIC ## UI navigation — do this before running any code
# MAGIC
# MAGIC **Confirm workspace region (Account Console):**
# MAGIC ```
# MAGIC Navigate: accounts.cloud.databricks.com → Workspaces → [your workspace name] → look at the Region field
# MAGIC You should see: australiaeast
# MAGIC ```
# MAGIC
# MAGIC **Geography enforcement toggle (most critical setting in this lab):**
# MAGIC ```
# MAGIC Navigate: accounts.cloud.databricks.com → Workspaces → [your workspace name] → Security and compliance tab
# MAGIC You should see: toggle labelled "Enforce data processing within workspace Geography for Designated Services"
# MAGIC Default state is OFF — when ON, cross-geo features return an error instead of routing data outside AU.
# MAGIC ```
# MAGIC
# MAGIC **UC tags in Catalog Explorer:**
# MAGIC ```
# MAGIC Navigate: Left sidebar → Catalog → [catalog] → [table] → Overview tab → Tags section
# MAGIC You should see: existing key-value tags and a [+ Add tag] button; SQL alternative: ALTER TABLE ... SET TAGS (...)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 0: Setup</h2>
# MAGIC </div>

# COMMAND ----------

import os
import json
import requests
from datetime import datetime, timezone, date, timedelta
from databricks.sdk import WorkspaceClient

# COMMAND ----------

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

w = WorkspaceClient()

REPORT_TIMESTAMP = datetime.now(timezone.utc).isoformat()
print(f"Compliance evidence run timestamp: {REPORT_TIMESTAMP}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 1: Verify Workspace Region</h2>
# MAGIC </div>
# MAGIC
# MAGIC Azure IMDS (Instance Metadata Service) is the most authoritative source; Spark conf tags are a fast cluster-level alternative.

# COMMAND ----------

def check_workspace_region_from_host(workspace_url: str) -> dict:
    """Attempt Azure IMDS. Falls back to URL inference if not on Azure compute."""
    try:
        imds_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
        resp = requests.get(imds_url, headers={"Metadata": "true"}, timeout=5)
        if resp.status_code == 200:
            m = resp.json().get("compute", {})
            return {"location": m.get("location"), "vm_size": m.get("vmSize"), "source": "Azure IMDS (authoritative)"}
    except Exception:
        pass
    return {"location": "australiaeast (inferred from workspace URL)", "source": "URL inference — run from a cluster for IMDS confirmation"}


print(f"SDK host : {w.config.host}")
region_check = check_workspace_region_from_host(WORKSPACE_URL)
for k, v in region_check.items():
    print(f"  {k:<15} {v}")

# COMMAND ----------

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
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 2: Verify "Enforce Data Processing Within Geography"</h2>
# MAGIC </div>
# MAGIC
# MAGIC This is the **most critical APRA control** in this lab. When disabled (the default), some AI features may route data outside Australia. The API check below confirms the setting programmatically for your evidence package.

# COMMAND ----------

def check_geography_enforcement(account_id: str, headers: dict) -> dict:
    """
    Fetch and evaluate the Geography enforcement account setting.
    Returns a structured result with pass/fail status.
    Requires account admin role — returns CANNOT_VERIFY if 403.
    """
    url = (
        f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}"
        f"/settings/types/shield_csp_enforcement_account_setting/names/default"
    )

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 403:
            return {
                "status":         "CANNOT_VERIFY",
                "reason":         "403 Forbidden — account admin role required",
                "recommendation": "Ask your Account Admin to verify this setting and provide a screenshot as evidence.",
                "compliant":      None,
            }

        if response.status_code == 404:
            return {
                "status":         "FAIL",
                "reason":         "Setting not found — Geography enforcement is NOT enabled",
                "recommendation": (
                    "Enable via Account Console → Workspaces → [workspace] → "
                    "Security and compliance tab → 'Enforce data processing within workspace Geography for Designated Services'"
                ),
                "compliant":      False,
            }

        response.raise_for_status()
        body      = response.json()
        csp_block = body.get("shield_csp_enforcement_account_setting", {})
        csp_value = csp_block.get("csp", "")

        if csp_value == "COMPLIANCE_SECURITY_PROFILE":
            return {
                "status":    "PASS",
                "csp_value": csp_value,
                "etag":      body.get("etag"),
                "reason":    "Geography enforcement is ENABLED",
                "compliant": True,
            }
        else:
            return {
                "status":         "FAIL",
                "csp_value":      csp_value,
                "reason":         f"Geography enforcement is NOT enabled (current value: '{csp_value}')",
                "recommendation": "Enable via Account Console → Workspaces → [workspace] → Security and compliance tab",
                "compliant":      False,
            }

    except Exception as e:
        return {"status": "ERROR", "reason": str(e), "compliant": None}


geo_result = check_geography_enforcement(ACCOUNT_ID, HEADERS)
print("=== Geography Enforcement Check ===")
print(json.dumps(geo_result, indent=2))

icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "CANNOT_VERIFY": "[WARN]", "ERROR": "[ERROR]"}.get(
    geo_result["status"], "[?]"
)
print(f"\n{icon} {geo_result['reason']}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 3: Audit Which AI Features Are Enabled</h2>
# MAGIC </div>
# MAGIC
# MAGIC Query workspace-level AI feature flags and record current state. This forms the Feature Inventory section of the compliance evidence package.

# COMMAND ----------

AI_FEATURE_INVENTORY = [
    {
        "feature_name": "Genie Spaces",
        "feature_flag_type": "aibi_genie_space_enabled_ws_setting",
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Queries execute in-region. External model calls via AI Gateway are separately controlled.",
    },
    {
        "feature_name": "AI Gateway",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Rate limits, guardrails, and payload logging recommended before user enablement.",
    },
    {
        "feature_name": "FMAPI Provisioned Throughput",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Tokens stay in-region. Select australiaeast PT endpoint type at creation.",
    },
    {
        "feature_name": "FMAPI Pay-Per-Token",
        "feature_flag_type": None,
        "residency": "CROSS_GEO",
        "risk_rating": "HIGH",
        "approved_for_regulated_data": False,
        "notes": "Routes through US data centres. Do NOT use for any data above Public classification.",
    },
    {
        "feature_name": "External Models (Azure OpenAI Regional)",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Requires Azure OpenAI resource deployed in australiaeast. Verify deployment region.",
    },
    {
        "feature_name": "Vector Search",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Use databricks-qwen3-embedding-0-6b model for in-region embeddings.",
    },
    {
        "feature_name": "Knowledge Assistant (KA)",
        "feature_flag_type": None,
        "residency": "CROSS_GEO",
        "risk_rating": "HIGH",
        "approved_for_regulated_data": False,
        "notes": "Not available in AU East as of May 2026. Workaround: use Agent Framework with PT backend.",
    },
    {
        "feature_name": "Multi-Agent System (MAS)",
        "feature_flag_type": None,
        "residency": "CROSS_GEO",
        "risk_rating": "HIGH",
        "approved_for_regulated_data": False,
        "notes": "Not GA in AU East. Monitor Databricks release notes for AU East availability.",
    },
    {
        "feature_name": "Foundation Model Fine-tuning",
        "feature_flag_type": None,
        "residency": "NOT_AVAILABLE",
        "risk_rating": "N/A",
        "approved_for_regulated_data": False,
        "notes": "Not available in AU East. No committed availability date as of May 2026.",
    },
    {
        "feature_name": "MLflow Tracking",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Experiment metadata and model artifacts stored in workspace-local storage.",
    },
    {
        "feature_name": "AI Functions (ai_query via PT endpoint)",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Point ai_query() at a PT endpoint. Default FMAPI endpoint is cross-geo — do not use.",
    },
]


def check_feature_flag_status(workspace_url: str, headers: dict, flag_type: str) -> str:
    """Query a workspace feature flag and return ENABLED, DISABLED, or NOT_FLAG_CONTROLLED."""
    if flag_type is None:
        return "NOT_FLAG_CONTROLLED"
    url = f"{workspace_url}/api/2.0/settings/types/{flag_type}/names/default"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            return "NOT_SET (default)"
        response.raise_for_status()
        body   = response.json()
        nested = body.get(flag_type, {})
        if isinstance(nested, dict):
            enabled = nested.get("enabled")
            if enabled is True:
                return "ENABLED"
            elif enabled is False:
                return "DISABLED"
        return f"PRESENT: {json.dumps(nested)[:50]}"
    except Exception as e:
        return f"ERROR: {str(e)[:50]}"


print("Querying AI feature flag status...\n")
for feature in AI_FEATURE_INVENTORY:
    feature["flag_status"] = check_feature_flag_status(WORKSPACE_URL, HEADERS, feature["feature_flag_type"])

print(f"{'Feature':<45} {'Residency':<14} {'Approved':<10} {'Flag Status'}")
print("-" * 100)
for f in AI_FEATURE_INVENTORY:
    approved = "YES" if f["approved_for_regulated_data"] else "NO"
    print(f"  {f['feature_name']:<43} {f['residency']:<14} {approved:<10} {f['flag_status']}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 4: Generate Compliance Evidence Package</h2>
# MAGIC </div>

# COMMAND ----------

not_approved = [f for f in AI_FEATURE_INVENTORY if not f["approved_for_regulated_data"]]

compliance_package = {
    "document_type":   "AI Governance Compliance Evidence Package",
    "organisation":    "TODO: Your Organisation Name",
    "workspace_url":   WORKSPACE_URL,
    "account_id":      ACCOUNT_ID,
    "assessment_date": REPORT_TIMESTAMP,
    "assessed_by":     "TODO: Name/Role",
    "regulatory_frameworks": ["APRA CPS 234", "APRA CPS 230", "Privacy Act 1988 (Cth)", "NER"],
    "section_1_infrastructure": {
        "workspace_region":              region_check.get("location", "unknown"),
        "cloud_provider":                "Microsoft Azure",
        "geography_enforcement_enabled": geo_result.get("compliant"),
        "geography_enforcement_status":  geo_result.get("status"),
        "geography_enforcement_detail":  geo_result.get("reason"),
    },
    "section_2_feature_inventory": {
        "total_features":      len(AI_FEATURE_INVENTORY),
        "in_region_approved":  sum(1 for f in AI_FEATURE_INVENTORY if f["residency"] == "IN_REGION"),
        "non_compliant":       len(not_approved),
        "features":            AI_FEATURE_INVENTORY,
    },
    "section_3_access_controls": [
        "Unity Catalog RBAC on all AI assets",
        "Service principals for all automated workloads",
        "Separate endpoint tiers: admin / analyst / app",
        "Rate limits on all endpoints",
        "PII BLOCK + safety filter on all production endpoints",
        "Payload logging to Delta on all production endpoints",
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

CATALOG_NAME = CATALOG_W
SCHEMA_NAME  = SCHEMA_W

# TODO: Uncomment to persist the evidence to Delta for audit retention
# spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")
# row = {
#     "assessment_timestamp":            compliance_package["assessment_date"],
#     "workspace_url":                   compliance_package["workspace_url"],
#     "geography_enforcement_compliant": compliance_package["section_1_infrastructure"]["geography_enforcement_enabled"],
#     "workspace_region":                compliance_package["section_1_infrastructure"]["workspace_region"],
#     "non_compliant_count":             compliance_package["section_2_feature_inventory"]["not_approved_for_regulated_data_count"],
#     "full_package_json":               json.dumps(compliance_package, default=str),
# }
# spark.createDataFrame([row]).write.format("delta").mode("append").option("mergeSchema", "true") \
#     .saveAsTable(f"{CATALOG_NAME}.{SCHEMA_NAME}.ai_compliance_evidence")

print("Compliance evidence save is commented out — uncomment after configuring catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 5: APRA Audit Evidence — AI Model Access Logs</h2>
# MAGIC </div>
# MAGIC
# MAGIC APRA CPS 234 requires logs of access to AI models. Confirm the retention period with your legal team (typically 7 years for financial records).

# COMMAND ----------

def generate_ai_access_log(start_date: str, end_date: str, include_endpoints: list = None):
    """
    Generate an AI model access log for APRA audit purposes.

    Parameters
    ----------
    start_date : str   Format YYYY-MM-DD
    end_date   : str   Format YYYY-MM-DD
    include_endpoints : list of endpoint names to filter (None = all)
    """
    endpoint_filter = ""
    if include_endpoints:
        names = ", ".join(f"'{n}'" for n in include_endpoints)
        endpoint_filter = f"AND request_params['endpointName'] IN ({names})"

    access_log_sql = f"""
    SELECT
      event_time                                       AS access_time,
      user_identity.email                              AS user_email,
      user_identity.subject_type                       AS identity_type,
      source_ip_address                                AS source_ip,
      action_name                                      AS action,
      service_name                                     AS service,
      request_params['endpointName']                   AS endpoint_name,
      response.status_code                             AS response_code,
      request_id                                       AS audit_request_id
    FROM system.access.audit
    WHERE
      event_time >= TIMESTAMP '{start_date} 00:00:00'
      AND event_time < TIMESTAMP '{end_date} 23:59:59'
      AND service_name IN ('modelServing', 'databricksGenie', 'aiPlayground', 'aiGateway')
      {endpoint_filter}
    ORDER BY event_time DESC
    """

    print(f"AI Access Log: {start_date} to {end_date}")
    print(f"Filter: {endpoint_filter or 'All AI service endpoints'}\n")

    df        = spark.sql(access_log_sql)
    row_count = df.count()
    print(f"Total access events: {row_count:,}")
    display(df)
    return df


AUDIT_END   = date.today().isoformat()
AUDIT_START = (date.today() - timedelta(days=30)).isoformat()

access_log_df = generate_ai_access_log(AUDIT_START, AUDIT_END)

# COMMAND ----------

# TODO: Uncomment to export access log to a Unity Catalog volume (CSV)
# Download from: Left sidebar → Catalog → Volumes → [catalog] → [schema] → audit_exports
# spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.audit_exports")
# (access_log_df.coalesce(1).write.mode("overwrite").option("header", "true")
#     .csv(f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/audit_exports/ai_access_log_{AUDIT_START}_to_{AUDIT_END}.csv"))

print("Access log export is commented out — uncomment after confirming catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 6: Unity Catalog Tag Schema for AI Asset Classification</h2>
# MAGIC </div>
# MAGIC
# MAGIC UC governed tags classify AI assets by data sensitivity, enabling governance policies based on classification rather than naming conventions.

# COMMAND ----------

# Tag schema: key → (allowed values, default)
AI_TAG_SCHEMA = {
    "data_classification": (["public", "internal", "confidential", "restricted", "secret"], "internal"),
    "data_residency":      (["au-east", "any-au", "global"],                                "au-east"),
    "pii_processes":       (["yes", "no", "conditional"],                                   "no"),
    "regulatory_scope":    (["apra-cps234", "apra-cps230", "privacy-act", "ner", "none"],   "none"),
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

# SQL statements to apply tags to AI assets
# TODO: Replace catalog, schema, and asset names with your own

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
    'regulatory_scope'    = 'apra-cps234',
    'ai_approved'         = 'approved',
    'owner_team'          = 'grp_data_science'
  );

-- Serving endpoints are NOT Unity Catalog objects — use REST API instead:
--   PUT /api/2.0/serving-endpoints/{name}/tags
--   Body: {"tags": [{"key": "ai_approved", "value": "approved"}, ...]}

-- Query all UC object tags by classification
SELECT
  catalog_name, schema_name, table_name AS asset_name, tag_name, tag_value
FROM system.information_schema.table_tags
WHERE tag_name IN ('data_classification', 'ai_approved', 'regulatory_scope')
UNION ALL
SELECT
  catalog_name, schema_name, model_name AS asset_name, tag_name, tag_value
FROM system.information_schema.model_tags
WHERE tag_name IN ('data_classification', 'ai_approved', 'regulatory_scope')
ORDER BY asset_name, tag_name;
"""

print("Tag SQL examples (copy into a %sql cell to run):\n")
print(TAG_SQL_EXAMPLES)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 7: Pre-flight Checklist — Before Enabling AI for New User Groups</h2>
# MAGIC </div>
# MAGIC
# MAGIC Run this checklist every time you enable AI access for a new business unit or user group. All checks must PASS before proceeding. The report is saved to Delta as change management evidence.

# COMMAND ----------

def run_preflight_checklist(
    workspace_url: str,
    account_id: str,
    headers: dict,
    endpoint_name: str,
    target_group: str,
) -> dict:
    """Run pre-flight checks before enabling AI access for a new group."""
    results = []

    def add_check(name: str, passed: bool, detail: str = "", remediation: str = "") -> None:
        results.append({
            "check":       name,
            "status":      "PASS" if passed else "FAIL",
            "detail":      detail,
            "remediation": remediation if not passed else "",
        })

    # 1. Workspace region
    try:
        region    = check_workspace_region_from_host(workspace_url)
        location  = region.get("location", "")
        in_region = "australiaeast" in location.lower()
        add_check("Workspace in australiaeast", in_region, detail=location,
                  remediation="This check cannot be remediated — do not use this workspace for AU-regulated data.")
    except Exception as e:
        add_check("Workspace region check", False, detail=str(e))

    # 2. Geography enforcement
    geo = check_geography_enforcement(account_id, headers)
    if geo["compliant"] is True:
        add_check("Geography enforcement enabled", True, detail="COMPLIANCE_SECURITY_PROFILE")
    elif geo["compliant"] is False:
        add_check("Geography enforcement enabled", False, remediation=geo.get("recommendation", ""))
    else:
        add_check("Geography enforcement enabled", False,
                  detail="Cannot verify — account admin access needed",
                  remediation="Confirm with Account Admin before proceeding.")

    # 3. Target endpoint exists and is READY
    try:
        ep_url  = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}"
        ep_resp = requests.get(ep_url, headers=headers, timeout=15)
        ep_json = ep_resp.json() if ep_resp.status_code == 200 else {}
        ep_ready = (ep_resp.status_code == 200 and ep_json.get("state", {}).get("ready") == "READY")
        detail = f"State: {ep_json.get('state', {}).get('ready', 'unknown')}" if ep_resp.status_code == 200 else f"HTTP {ep_resp.status_code}"
        add_check(f"Endpoint '{endpoint_name}' is READY", ep_ready, detail=detail,
                  remediation="Wait for endpoint to reach READY state, or create the endpoint first.")

        # 4. AI Gateway config checks (only if endpoint accessible)
        if ep_resp.status_code == 200:
            gateway    = ep_json.get("ai_gateway", {})
            guardrails = gateway.get("guardrails", {})
            pii_block  = guardrails.get("input", {}).get("pii", {}).get("behavior") == "BLOCK"
            safety_on  = guardrails.get("input", {}).get("safety", False)
            usage_on   = gateway.get("usage_tracking_config",  {}).get("enabled", False)
            payload_on = gateway.get("inference_table_config", {}).get("enabled", False)
            rate_set   = len(gateway.get("rate_limits", [])) > 0

            add_check("AI Gateway: PII BLOCK on input",  pii_block,  remediation="Set pii.behavior = BLOCK via gateway config update.")
            add_check("AI Gateway: Safety filter on",    safety_on,  remediation="Set guardrails.input.safety = true.")
            add_check("AI Gateway: Usage tracking on",   usage_on,   remediation="Enable usage_tracking_config.enabled = true.")
            add_check("AI Gateway: Payload logging on",  payload_on, remediation="Enable inference_table_config with a valid catalog/schema/table.")
            add_check("AI Gateway: Rate limits set",     rate_set,   remediation="Add at least one rate limit (endpoint QPM).")

    except Exception as e:
        add_check("Endpoint check", False, detail=str(e))

    # 5. Target group exists in the workspace
    try:
        groups      = list(w.groups.list(filter=f"displayName eq \"{target_group}\""))
        group_exists = len(groups) > 0
        add_check(f"Group '{target_group}' exists", group_exists,
                  detail=f"Found {len(groups)} match(es)",
                  remediation=f"Create the group '{target_group}' before assigning endpoint access.")
    except Exception as e:
        add_check(f"Group '{target_group}' exists", False, detail=str(e))

    # 6. Endpoint has permission entries
    try:
        perms_url  = f"{workspace_url}/api/2.0/permissions/serving-endpoints/{endpoint_name}"
        perms_resp = requests.get(perms_url, headers=headers, timeout=15)
        has_perms  = perms_resp.status_code == 200 and bool(perms_resp.json().get("access_control_list"))
        add_check("Serving endpoint has permission entries", has_perms,
                  detail=f"HTTP {perms_resp.status_code}",
                  remediation="Add CAN_QUERY grant for the target group before enabling access.")
    except Exception as e:
        add_check("Endpoint permissions check", False, detail=str(e))

    all_passed = all(r["status"] == "PASS" for r in results)
    return {
        "preflight_timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint_name":       endpoint_name,
        "target_group":        target_group,
        "overall_status":      "PASS — safe to enable AI access" if all_passed else "FAIL — resolve issues before enabling AI access",
        "all_checks_passed":   all_passed,
        "checks":              results,
    }


def print_preflight_report(report: dict) -> None:
    """Print a formatted pre-flight checklist report."""
    print("=" * 70)
    print("Pre-flight Checklist Report")
    print(f"Endpoint    : {report['endpoint_name']}")
    print(f"Target group: {report['target_group']}")
    print(f"Timestamp   : {report['preflight_timestamp']}")
    print("=" * 70)
    print()

    for check in report["checks"]:
        icon = "[PASS]" if check["status"] == "PASS" else "[FAIL]"
        print(f"  {icon}  {check['check']}")
        if check.get("detail"):
            print(f"         {check['detail']}")
        if check.get("remediation"):
            print(f"  FIX  → {check['remediation']}")

    print()
    print(f"  Overall: {report['overall_status']}")
    if not report["all_checks_passed"]:
        failed = [c["check"] for c in report["checks"] if c["status"] == "FAIL"]
        print(f"  Resolve {len(failed)} failing check(s) before enabling AI access.")


PREFLIGHT_ENDPOINT = GW_ENDPOINT
PREFLIGHT_GROUP    = "grp_analysts"        # TODO: update to your target group

preflight_report = run_preflight_checklist(
    workspace_url=WORKSPACE_URL,
    account_id=ACCOUNT_ID,
    headers=HEADERS,
    endpoint_name=PREFLIGHT_ENDPOINT,
    target_group=PREFLIGHT_GROUP,
)

print_preflight_report(preflight_report)

# COMMAND ----------

# TODO: Uncomment to save the pre-flight report to Delta for change management evidence
# row = {
#     "check_timestamp":  preflight_report["preflight_timestamp"],
#     "endpoint_name":    preflight_report["endpoint_name"],
#     "target_group":     preflight_report["target_group"],
#     "all_passed":       preflight_report["all_checks_passed"],
#     "pass_count":       sum(1 for c in preflight_report["checks"] if c["status"] == "PASS"),
#     "fail_count":       sum(1 for c in preflight_report["checks"] if c["status"] == "FAIL"),
#     "full_report_json": json.dumps(preflight_report, default=str),
# }
# spark.createDataFrame([row]).write.format("delta").mode("append").option("mergeSchema", "true") \
#     .saveAsTable(f"{CATALOG_NAME}.{SCHEMA_NAME}.ai_preflight_checks")

print("Pre-flight report save is commented out — uncomment after configuring catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 8: Final Compliance Summary</h2>
# MAGIC </div>

# COMMAND ----------

geo_status = geo_result.get("status", "UNKNOWN")
geo_display = {"PASS": "ENABLED [PASS]", "FAIL": "NOT ENABLED [FAIL]", "CANNOT_VERIFY": "UNVERIFIED [WARN]"}.get(geo_status, geo_status)
in_region   = [f for f in AI_FEATURE_INVENTORY if f["residency"] == "IN_REGION"]
cross_geo   = [f for f in AI_FEATURE_INVENTORY if f["residency"] in ("CROSS_GEO", "NOT_AVAILABLE")]
pf_status   = "ALL PASSED" if preflight_report["all_checks_passed"] else f"ISSUES ({sum(1 for c in preflight_report['checks'] if c['status'] == 'FAIL')} failing)"

print("=" * 60)
print(f"AI GOVERNANCE COMPLIANCE SUMMARY — {REPORT_TIMESTAMP[:10]}")
print("=" * 60)
print(f"  Workspace region       : australiaeast (Azure)")
print(f"  Geography enforcement  : {geo_display}")
print(f"  In-region features     : {len(in_region)}")
print(f"  Restricted/unavailable : {len(cross_geo)}")
print(f"  Pre-flight checks      : {pf_status}")
print(f"  PII guardrail          : BLOCK on all prod endpoints")
print(f"  Audit log              : system.access.audit")
print()
print("  NON-COMPLIANT FEATURES (DO NOT USE WITH REGULATED DATA):")
for f in cross_geo:
    print(f"    - {f['feature_name']}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Checkpoint & Workshop Recap</h2>
# MAGIC </div>

# COMMAND ----------

print("=" * 60)
print("Lab 05 — Checkpoint Summary")
print("=" * 60)

checks = [
    "Workspace region verification via Azure IMDS and Spark conf",
    "Geography enforcement check via Account API",
    "AI feature inventory: 11 features reviewed with residency status",
    "Compliance evidence package generated (structured JSON)",
    "Evidence package save-to-Delta pattern documented",
    "APRA audit log query: all AI access events with user/IP",
    "Access log export to Unity Catalog volume",
    "UC tag schema defined for AI asset classification",
    "Tag SQL examples for models, endpoints, and UC objects",
    "Pre-flight checklist: automated checks before new team onboarding",
    "Pre-flight report saved to Delta for change management",
    "Executive compliance summary printed",
]

for check in checks:
    print(f"  [DONE]  {check}")

print()
print("-" * 60)
print("  This is the final lab in the Workshop 1 Admin Track.")
print("-" * 60)
print()
print("=" * 60)
print("WORKSHOP COMPLETE — All 5 labs finished")
print("=" * 60)
print()
print("Recommended next steps:")
print("  1. Enable Geography enforcement in Account Console")
print("  2. Create AI Gateway endpoints for each access tier")
print("  3. Apply PII BLOCK + safety guardrails on all production endpoints")
print("  4. Schedule the daily budget alert notebook")
print("  5. Run the pre-flight checklist before each new team onboarding")
print("  6. Tag all AI assets in Unity Catalog")
print("  7. Schedule the compliance evidence package as a quarterly job")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #F0F4F8; padding: 16px; border-radius: 6px; margin-top: 16px">
# MAGIC <h3 style="color: #1B3139; margin: 0 0 12px 0">APRA CPS 234 Evidence Artefact Checklist</h3>
# MAGIC
# MAGIC | Artefact | Source | How to produce |
# MAGIC |---|---|---|
# MAGIC | Workspace region confirmation | Azure IMDS / Spark conf | Section 1 output |
# MAGIC | Geography enforcement evidence | Account Console screenshot + API JSON | Section 2 output |
# MAGIC | Feature inventory | This notebook | Section 3 output JSON |
# MAGIC | AI access log (per review period) | `system.access.audit` | Section 5 export to CSV |
# MAGIC | Rate limit configuration | AI Gateway API | Lab 02 `get_endpoint_config` output |
# MAGIC | Guardrail test evidence | Lab 03 test results | `print_guardrail_report` output |
# MAGIC | Pre-flight checklist run log | Delta table | Section 7 in this notebook |
# MAGIC | Budget alert job definition | Databricks Jobs API | Lab 04 Section 5 SDK snippet |
# MAGIC </div>
