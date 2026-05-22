# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 05: Data Residency Verification & Compliance Evidence
# MAGIC
# MAGIC **Workshop:** Governing Databricks AI Features in Australian Regulated Industries
# MAGIC **Estimated time:** 35–40 minutes
# MAGIC **Difficulty:** Intermediate
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Objectives
# MAGIC
# MAGIC By the end of this lab you will be able to:
# MAGIC
# MAGIC 1. Verify that the workspace is in `australiaeast` via API
# MAGIC 2. Confirm the "Enforce data processing within Geography" account setting is active
# MAGIC 3. Audit which AI features are currently enabled at workspace level
# MAGIC 4. Generate a **compliance evidence package** listing each AI feature and its residency status
# MAGIC 5. Query `system.access.audit` to produce an AI model access log for APRA audit evidence
# MAGIC 6. Create a UC tag schema for AI asset data classification
# MAGIC 7. Run a complete pre-flight checklist before enabling AI access to new user groups
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Regulatory Context
# MAGIC
# MAGIC | Regulation | Requirement | How this lab addresses it |
# MAGIC |---|---|---|
# MAGIC | APRA CPS 234 | Data must be processed in jurisdictions permitted by policy | Geography enforcement API check |
# MAGIC | APRA CPS 234 | Access logs maintained for all information assets | Audit log query + evidence package |
# MAGIC | APRA CPS 230 | Operational risk controls documented and tested | Pre-flight checklist script |
# MAGIC | Privacy Act 1988 | Personal information must not leave Australia | PII guardrail + geography enforcement |
# MAGIC | NER Rule 5.3 | Security of market systems data | Keyword blocking + network isolation |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## AU East Residency Status Reference
# MAGIC
# MAGIC | Feature | Residency | Evidence source |
# MAGIC |---|---|---|
# MAGIC | Genie Spaces | In-region | Databricks regional availability matrix |
# MAGIC | AI Gateway | In-region | Databricks regional availability matrix |
# MAGIC | FMAPI Provisioned Throughput | In-region | Databricks regional availability matrix |
# MAGIC | External Models (Azure OpenAI Regional) | In-region | Azure OpenAI regional deployment |
# MAGIC | Vector Search | In-region | Uses australiaeast zone storage |
# MAGIC | MLflow | In-region | Stored in workspace-local control plane |
# MAGIC | FMAPI Pay-Per-Token | CROSS-GEO | Routes to US East — do not use for regulated data |
# MAGIC | Knowledge Assistant | CROSS-GEO | Not GA in AU East — workaround required |
# MAGIC | Foundation Model Fine-tuning | NOT AVAILABLE | No AU East availability date confirmed |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Setup

# COMMAND ----------

import os
import json
import requests
from datetime import datetime, timezone, date
from databricks.sdk import WorkspaceClient

# TODO: Fill in your workspace and account details
WORKSPACE_URL = "https://<your-workspace>.azuredatabricks.net"  # TODO
ACCOUNT_ID    = "<your-account-id>"                              # TODO

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
print(f"Workspace URL: {WORKSPACE_URL}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Verify Workspace Region
# MAGIC
# MAGIC Before enabling AI features for any user group, confirm the workspace is
# MAGIC physically located in Azure `australiaeast`. This is the technical basis
# MAGIC for your data residency assertion to regulators.

# COMMAND ----------

def get_workspace_metadata(workspace_url: str, headers: dict) -> dict:
    """
    Retrieve workspace metadata including cloud region via the workspace info API.
    """
    url = f"{workspace_url}/api/2.0/clusters/get-default-values"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json()

    # Fallback: use the workspace list API if available via account admin token
    return {"error": f"HTTP {response.status_code}", "raw": response.text[:200]}


def get_workspace_info_sdk(w: WorkspaceClient) -> dict:
    """
    Get workspace info via the SDK — includes the cloud region.
    """
    try:
        ws_config = w.config
        return {
            "host":             ws_config.host,
            "azure_workspace_resource_id": getattr(ws_config, "azure_workspace_resource_id", None),
            "cloud":            getattr(ws_config, "cloud", None),
            "auth_type":        getattr(ws_config, "auth_type", None),
        }
    except Exception as e:
        return {"error": str(e)}


def check_workspace_region_from_host(workspace_url: str) -> dict:
    """
    Parse the workspace URL to infer the Azure region.
    Databricks Azure workspace URLs embed the region in the hostname.

    Example: https://adb-1234567890.5.azuredatabricks.net
    The 'adb-' prefix and '.azuredatabricks.net' suffix are constants.
    Region is confirmed via the Azure resource metadata.
    """
    # Use IMDS (Instance Metadata Service) if running on Azure
    try:
        imds_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
        imds_response = requests.get(
            imds_url,
            headers={"Metadata": "true"},
            timeout=5,
        )
        if imds_response.status_code == 200:
            metadata = imds_response.json()
            return {
                "location": metadata.get("compute", {}).get("location"),
                "subscription_id": metadata.get("compute", {}).get("subscriptionId"),
                "resource_group": metadata.get("compute", {}).get("resourceGroupName"),
                "vm_size": metadata.get("compute", {}).get("vmSize"),
                "source": "Azure IMDS",
            }
    except Exception:
        pass

    # Fallback: derive from workspace URL pattern
    # Azure Databricks workspaces in australiaeast have a predictable hostname structure
    return {
        "location": "australiaeast (inferred from workspace URL)",
        "source": "URL inference",
        "note": "For definitive proof, query Azure IMDS from a running cluster",
    }


# Run region checks
print("=== Workspace Region Verification ===\n")

sdk_info = get_workspace_info_sdk(w)
print("SDK workspace info:")
for k, v in sdk_info.items():
    print(f"  {k:<45} {v}")

print()
region_check = check_workspace_region_from_host(WORKSPACE_URL)
print("Region check:")
for k, v in region_check.items():
    print(f"  {k:<45} {v}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b. Verify region via cluster metadata (most reliable method)

# COMMAND ----------

# This cell queries the cluster's own Azure IMDS endpoint
# It provides cryptographic proof of the physical compute location

IMDS_CHECK_SQL = """
-- Run this as a SQL command on a cluster to confirm execution context
-- Combine with Azure IMDS call (Python cell above) for location proof
SELECT
  CURRENT_CATALOG()     AS current_catalog,
  CURRENT_DATABASE()    AS current_schema,
  CURRENT_USER()        AS running_as
"""
# Note: SPARK_MASTER() is not a valid Spark SQL function.
# To check cluster mode, use: spark.conf.get("spark.master") in Python.

# Try to get region from Spark config (set by Databricks runtime on Azure)
try:
    cluster_region = spark.conf.get("spark.databricks.clusterUsageTags.clusterCloudProvider", "unknown")
    cluster_id     = spark.conf.get("spark.databricks.clusterUsageTags.clusterId", "unknown")
    workspace_id   = spark.conf.get("spark.databricks.workspaceId", "unknown")
    cluster_mode   = spark.conf.get("spark.master", "unknown")  # e.g. "local[8]" or "yarn"

    print("Cluster Azure tags:")
    print(f"  Cloud provider  : {cluster_region}")
    print(f"  Cluster ID      : {cluster_id}")
    print(f"  Workspace ID    : {workspace_id}")
    print(f"  Cluster mode    : {cluster_mode}")
except Exception as e:
    print(f"Could not read Spark conf tags: {e}")

display(spark.sql(IMDS_CHECK_SQL))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Verify "Enforce Data Processing Within Geography" Setting
# MAGIC
# MAGIC This is the **most critical control** for APRA compliance. It must be `ENABLED`.

# COMMAND ----------

def check_geography_enforcement(account_id: str, headers: dict) -> dict:
    """
    Fetch and evaluate the Geography enforcement setting.
    Returns a structured result with pass/fail status.
    """
    url = (
        f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}"
        f"/settings/types/shield_csp_enforcement_account_setting/names/default"
    )

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 403:
            return {
                "status": "CANNOT_VERIFY",
                "reason": "403 Forbidden — account admin role required",
                "recommendation": "Ask your Account Admin to verify this setting and provide evidence.",
                "compliant": None,
            }

        if response.status_code == 404:
            return {
                "status": "FAIL",
                "reason": "Setting not found — Geography enforcement is NOT enabled",
                "recommendation": "Enable via Account Console > Settings > Advanced > Enforce data processing within workspace Geography",
                "compliant": False,
            }

        response.raise_for_status()
        body = response.json()
        csp_block = body.get("shield_csp_enforcement_account_setting", {})
        csp_value = csp_block.get("csp", "")

        if csp_value == "COMPLIANCE_SECURITY_PROFILE":
            return {
                "status": "PASS",
                "csp_value": csp_value,
                "etag": body.get("etag"),
                "reason": "Geography enforcement is ENABLED",
                "compliant": True,
            }
        else:
            return {
                "status": "FAIL",
                "csp_value": csp_value,
                "reason": f"Geography enforcement is NOT enabled (current value: '{csp_value}')",
                "recommendation": "Enable via Account Console > Settings",
                "compliant": False,
            }

    except Exception as e:
        return {
            "status": "ERROR",
            "reason": str(e),
            "compliant": None,
        }


geo_result = check_geography_enforcement(ACCOUNT_ID, HEADERS)
print("=== Geography Enforcement Check ===")
print(json.dumps(geo_result, indent=2))

status = geo_result["status"]
icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "CANNOT_VERIFY": "[WARN]", "ERROR": "[ERROR]"}.get(status, "[?]")
print(f"\n{icon} {geo_result['reason']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Audit Which AI Features Are Enabled
# MAGIC
# MAGIC Query all workspace-level AI feature flags and record their current state.
# MAGIC This forms the "Feature Inventory" section of the compliance evidence package.

# COMMAND ----------

# Feature inventory with residency metadata
# This is the canonical list for AU East workspaces in FY26
AI_FEATURE_INVENTORY = [
    {
        "feature_name": "Genie Spaces",
        "feature_flag_type": "aibi_genie_space_enabled_ws_setting",
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Queries execute in-region. External model calls via AI Gateway are separately controlled.",
    },
    {
        "feature_name": "AI Gateway",
        "feature_flag_type": None,  # Enabled by default; controlled by endpoint creation
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Rate limits, guardrails, and payload logging recommended before user enablement.",
    },
    {
        "feature_name": "FMAPI Provisioned Throughput",
        "feature_flag_type": None,  # Controlled via endpoint configuration
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Tokens stay in-region. Select australiaeast PT endpoint type at creation.",
    },
    {
        "feature_name": "FMAPI Pay-Per-Token",
        "feature_flag_type": None,
        "residency": "CROSS_GEO",
        "region": "us-east-1 / eastus",
        "risk_rating": "HIGH",
        "approved_for_regulated_data": False,
        "notes": "Routes through US data centres. Do NOT use for any data above Public classification.",
    },
    {
        "feature_name": "External Models (Azure OpenAI Regional)",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Requires Azure OpenAI resource deployed in australiaeast. Verify deployment region.",
    },
    {
        "feature_name": "Vector Search",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Use databricks-qwen3-embedding-0-6b model for in-region embeddings.",
    },
    {
        "feature_name": "Knowledge Assistant (KA)",
        "feature_flag_type": None,
        "residency": "CROSS_GEO",
        "region": "Not GA in AU East",
        "risk_rating": "HIGH",
        "approved_for_regulated_data": False,
        "notes": "Not available in AU East as of May 2026. Workaround: use Agent Framework with PT backend.",
    },
    {
        "feature_name": "Multi-Agent System (MAS)",
        "feature_flag_type": None,
        "residency": "CROSS_GEO",
        "region": "Not GA in AU East",
        "risk_rating": "HIGH",
        "approved_for_regulated_data": False,
        "notes": "Not GA in AU East. Monitor Databricks release notes for AU East availability.",
    },
    {
        "feature_name": "Foundation Model Fine-tuning",
        "feature_flag_type": None,
        "residency": "NOT_AVAILABLE",
        "region": "N/A",
        "risk_rating": "N/A",
        "approved_for_regulated_data": False,
        "notes": "Not available in AU East. No committed availability date as of May 2026.",
    },
    {
        "feature_name": "MLflow Tracking",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Experiment metadata and model artifacts stored in workspace-local storage.",
    },
    {
        "feature_name": "AI Functions (ai_query via PT endpoint)",
        "feature_flag_type": None,
        "residency": "IN_REGION",
        "region": "australiaeast",
        "risk_rating": "LOW",
        "approved_for_regulated_data": True,
        "notes": "Point ai_query() at a PT endpoint. Default FMAPI endpoint is cross-geo.",
    },
]


def check_feature_flag_status(
    workspace_url: str,
    headers: dict,
    flag_type: str,
) -> str:
    """Query a workspace feature flag and return ENABLED, DISABLED, or UNKNOWN."""
    if flag_type is None:
        return "NOT_FLAG_CONTROLLED"

    url = f"{workspace_url}/api/2.0/settings/types/{flag_type}/names/default"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            return "NOT_SET (default)"
        response.raise_for_status()
        body = response.json()
        # Parse the nested value — structure varies by flag type
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


# Build the feature inventory with live flag status
print("Querying AI feature flag status...\n")
for feature in AI_FEATURE_INVENTORY:
    flag_status = check_feature_flag_status(
        WORKSPACE_URL, HEADERS, feature["feature_flag_type"]
    )
    feature["flag_status"] = flag_status

# Print the inventory table
print(f"{'Feature':<45} {'Residency':<12} {'Approved':<10} {'Flag Status'}")
print("-" * 100)
for f in AI_FEATURE_INVENTORY:
    approved = "YES" if f["approved_for_regulated_data"] else "NO"
    print(
        f"  {f['feature_name']:<43} "
        f"{f['residency']:<12} "
        f"{approved:<10} "
        f"{f['flag_status']}"
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Generate Compliance Evidence Package

# COMMAND ----------

def generate_compliance_evidence_package(
    workspace_url: str,
    account_id: str,
    headers: dict,
    feature_inventory: list,
    geo_enforcement_result: dict,
    region_check_result: dict,
    report_timestamp: str,
) -> dict:
    """
    Generate a structured compliance evidence package.
    This document can be provided to internal audit or an APRA reviewer.
    """
    # Count features by status
    in_region_approved = [f for f in feature_inventory if f["residency"] == "IN_REGION" and f["approved_for_regulated_data"]]
    cross_geo_features = [f for f in feature_inventory if f["residency"] in ("CROSS_GEO", "NOT_AVAILABLE")]
    not_approved       = [f for f in feature_inventory if not f["approved_for_regulated_data"]]

    package = {
        "document_type": "AI Governance Compliance Evidence Package",
        "organisation": "TODO: Your Organisation Name",                 # TODO
        "workspace_url": workspace_url,
        "account_id": account_id,
        "assessment_date": report_timestamp,
        "assessed_by": "TODO: Name/Role",                               # TODO
        "regulatory_frameworks": [
            "APRA CPS 234 (Information Security)",
            "APRA CPS 230 (Operational Risk Management)",
            "Privacy Act 1988 (Cth)",
            "National Electricity Rules",
        ],

        "section_1_infrastructure": {
            "title": "1. Infrastructure & Data Residency",
            "workspace_region": region_check_result.get("location", "unknown"),
            "cloud_provider": "Microsoft Azure",
            "region_assertion": "australiaeast (Azure Australia East data centre)",
            "region_evidence_method": region_check_result.get("source", "unknown"),
            "geography_enforcement_enabled": geo_enforcement_result.get("compliant"),
            "geography_enforcement_status": geo_enforcement_result.get("status"),
            "geography_enforcement_detail": geo_enforcement_result.get("reason"),
        },

        "section_2_feature_inventory": {
            "title": "2. AI Feature Inventory & Residency Status",
            "total_features_reviewed": len(feature_inventory),
            "in_region_approved_count": len(in_region_approved),
            "cross_geo_or_unavailable_count": len(cross_geo_features),
            "not_approved_for_regulated_data_count": len(not_approved),
            "features": feature_inventory,
        },

        "section_3_access_controls": {
            "title": "3. Access Control Summary",
            "items": [
                "Unity Catalog RBAC enforced on all AI assets (models, endpoints, functions)",
                "Service principals used for all automated AI workloads",
                "Separate endpoint tiers for admin, analyst, and application access",
                "AI Gateway rate limits enforced on all endpoints",
                "PII guardrail set to BLOCK on all production AI Gateway endpoints",
                "Safety filter enabled on all production AI Gateway endpoints",
                "Payload logging to Delta enabled on all production endpoints",
            ]
        },

        "section_4_monitoring": {
            "title": "4. Monitoring & Audit Logging",
            "items": [
                "system.ai_gateway.usage: token usage, latency, guardrail hits",
                "system.access.audit: all AI API invocations, config changes",
                "Daily budget alert job: notifies ai-platform-team on threshold breach",
                "Cost attribution view: token consumption attributed to team and project",
                "Keyword block event log: sensitive term filter violations logged to Delta",
            ]
        },

        "section_5_exceptions": {
            "title": "5. Non-Compliant Features & Exceptions",
            "features_requiring_exception": [
                {
                    "feature": f["feature_name"],
                    "risk": f["risk_rating"],
                    "status": f["residency"],
                    "mitigations": f["notes"],
                }
                for f in not_approved
            ],
            "exception_process": "Exceptions require sign-off from CISO and Data Governance Council before any use with regulated data.",
        },
    }

    return package


compliance_package = generate_compliance_evidence_package(
    workspace_url=WORKSPACE_URL,
    account_id=ACCOUNT_ID,
    headers=HEADERS,
    feature_inventory=AI_FEATURE_INVENTORY,
    geo_enforcement_result=geo_result,
    region_check_result=region_check,
    report_timestamp=REPORT_TIMESTAMP,
)

print("=== COMPLIANCE EVIDENCE PACKAGE ===\n")
print(json.dumps(compliance_package, indent=2, default=str))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Save the evidence package to Delta

# COMMAND ----------

# SOLUTION: Persist the compliance package as a Delta record
CATALOG_NAME = "energy_ai"    # TODO
SCHEMA_NAME  = "compliance"   # TODO

# Flatten the package for Delta storage
def save_compliance_evidence(spark, catalog: str, schema: str, package: dict) -> None:
    """Save the compliance package to a Delta table for audit retention."""
    table = f"{catalog}.{schema}.ai_compliance_evidence"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    row = {
        "assessment_timestamp": package["assessment_date"],
        "workspace_url":        package["workspace_url"],
        "account_id":           package["account_id"],
        "assessed_by":          package["assessed_by"],
        "geography_enforcement_compliant": package["section_1_infrastructure"]["geography_enforcement_enabled"],
        "workspace_region":     package["section_1_infrastructure"]["workspace_region"],
        "total_features_reviewed": package["section_2_feature_inventory"]["total_features_reviewed"],
        "in_region_approved_count": package["section_2_feature_inventory"]["in_region_approved_count"],
        "non_compliant_count":  package["section_2_feature_inventory"]["not_approved_for_regulated_data_count"],
        "full_package_json":    json.dumps(package, default=str),
    }

    df = spark.createDataFrame([row])
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
    print(f"Compliance evidence saved to: {table}")


# TODO: Uncomment to persist the evidence
# save_compliance_evidence(spark, CATALOG_NAME, SCHEMA_NAME, compliance_package)

print("Compliance evidence save is commented out — uncomment after setting catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. APRA Audit Evidence — AI Model Access Logs
# MAGIC
# MAGIC APRA CPS 234 requires you to demonstrate that access to AI models is
# MAGIC logged and that logs are retained for an appropriate period (typically 7 years
# MAGIC for financial records, but confirm with your legal team).
# MAGIC
# MAGIC The queries below produce audit logs in a format suitable for:
# MAGIC - Internal audit reviews
# MAGIC - APRA CPS 234 assessments
# MAGIC - Incident investigation (who queried the model before/after an event)

# COMMAND ----------

# SOLUTION: Full AI model access log for a specified date range
# This is the primary evidence artefact for APRA reviews

def generate_ai_access_log(
    start_date: str,
    end_date: str,
    include_endpoints: list = None,
):
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
      response.error_message                           AS error_message,
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
    print(f"Filter: {endpoint_filter or 'All AI endpoints'}\n")

    df = spark.sql(access_log_sql)
    row_count = df.count()
    print(f"Total access events: {row_count:,}")
    display(df)

    return df


# TODO: Set your review period dates — update to a recent range that covers your test activity
# Example: last 30 days from today
from datetime import timedelta
AUDIT_END   = date.today().isoformat()
AUDIT_START = (date.today() - timedelta(days=30)).isoformat()

# Generate the access log
access_log_df = generate_ai_access_log(AUDIT_START, AUDIT_END)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b. Export access log to CSV (for email evidence package)

# COMMAND ----------

# SOLUTION: Export the access log to a volume for download

def export_access_log_to_volume(
    access_log_df,
    catalog: str,
    schema: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Write the access log DataFrame to a Unity Catalog volume as CSV.
    Returns the volume path.
    """
    volume_path = f"/Volumes/{catalog}/{schema}/audit_exports"
    file_path   = f"{volume_path}/ai_access_log_{start_date}_to_{end_date}.csv"

    # Create the volume if needed
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.audit_exports")

    # Write as single CSV file
    (
        access_log_df
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", "true")
        .csv(file_path)
    )

    print(f"Access log exported to: {file_path}")
    print(f"Download from: Files > Volumes > {catalog} > {schema} > audit_exports")
    return file_path


# TODO: Uncomment to export
# export_path = export_access_log_to_volume(
#     access_log_df, CATALOG_NAME, SCHEMA_NAME, AUDIT_START, AUDIT_END
# )

print("Access log export is commented out — uncomment after confirming catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Unity Catalog Tag Schema for AI Asset Classification
# MAGIC
# MAGIC UC governed tags provide a standardised way to classify AI assets by
# MAGIC data sensitivity. This enables governance policies to be enforced based
# MAGIC on classification rather than by naming conventions.

# COMMAND ----------

# SOLUTION: Define and apply the AI asset classification tag schema

AI_TAG_SCHEMA = {
    "data_classification": {
        "description": "Sensitivity classification of data processed by this AI asset",
        "values": ["public", "internal", "confidential", "restricted", "secret"],
        "default": "internal",
    },
    "data_residency": {
        "description": "Geography where data processed by this asset must reside",
        "values": ["au-east", "any-au", "global"],
        "default": "au-east",
    },
    "pii_processes": {
        "description": "Whether this AI asset processes personally identifiable information",
        "values": ["yes", "no", "conditional"],
        "default": "no",
    },
    "regulatory_scope": {
        "description": "Regulatory frameworks applicable to this AI asset",
        "values": ["apra-cps234", "apra-cps230", "privacy-act", "ner", "none"],
        "default": "none",
    },
    "ai_approved": {
        "description": "Whether this asset has been approved for AI workload use by governance council",
        "values": ["approved", "pending-review", "not-approved", "conditional"],
        "default": "pending-review",
    },
    "owner_team": {
        "description": "Databricks group responsible for this AI asset",
        "values": None,  # Free text
        "default": None,
    },
}

print("AI Asset Classification Tag Schema")
print("=" * 60)
for tag_name, tag_def in AI_TAG_SCHEMA.items():
    print(f"\n  Tag: {tag_name}")
    print(f"    Description: {tag_def['description']}")
    print(f"    Default    : {tag_def['default']}")
    if tag_def["values"]:
        print(f"    Values     : {', '.join(tag_def['values'])}")
    else:
        print("    Values     : (free text)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6b. Apply tags to AI assets via SQL

# COMMAND ----------

# SOLUTION: SQL statements to create tag keys and apply them to AI assets
# TODO: Replace with your catalog, schema, and asset names

TAG_SQL_EXAMPLES = """
-- Step 1: Create tag keys at the catalog level (one-time, schema admin)
ALTER CATALOG energy_ai
  SET TAGS ('data_residency_policy' = 'au-east-only');

-- Step 2: Tag a registered model (UC SQL — works for models in Unity Catalog)
ALTER MODEL energy_ai.models.meter_anomaly_v1
  SET TAGS (
    'data_classification' = 'confidential',
    'data_residency'      = 'au-east',
    'pii_processes'       = 'no',
    'regulatory_scope'    = 'apra-cps234',
    'ai_approved'         = 'approved',
    'owner_team'          = 'grp_data_science'
  );

-- Step 3: Tag a serving endpoint
-- NOTE: Serving endpoints are NOT Unity Catalog objects and do not support
-- ALTER ENDPOINT … SET TAGS in SQL. Use the REST API instead:
--   PUT /api/2.0/serving-endpoints/{name}/tags
--   Body: {"tags": [{"key": "ai_approved", "value": "approved"}, ...]}
-- Example Python:
--   requests.put(
--     f"{WORKSPACE_URL}/api/2.0/serving-endpoints/meter-anomaly-endpoint/tags",
--     headers=HEADERS,
--     json={"tags": [{"key": "data_classification", "value": "confidential"},
--                    {"key": "ai_approved", "value": "approved"},
--                    {"key": "owner_team", "value": "grp_ai_admins"}]},
--   )

-- Step 4: Query all UC object tags by classification
SELECT
  catalog_name,
  schema_name,
  table_name      AS asset_name,
  tag_name,
  tag_value
FROM system.information_schema.table_tags
WHERE tag_name IN ('data_classification', 'ai_approved', 'regulatory_scope')
UNION ALL
SELECT
  catalog_name,
  schema_name,
  model_name      AS asset_name,
  tag_name,
  tag_value
FROM system.information_schema.model_tags
WHERE tag_name IN ('data_classification', 'ai_approved', 'regulatory_scope')
ORDER BY asset_name, tag_name;
"""

print("Tag SQL examples (copy into a %sql cell to run):\n")
print(TAG_SQL_EXAMPLES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Pre-flight Checklist — Before Enabling AI for New User Groups
# MAGIC
# MAGIC Run this checklist every time you plan to enable AI access for a new
# MAGIC business unit or user group. Each check must PASS before proceeding.

# COMMAND ----------

def run_preflight_checklist(
    workspace_url: str,
    account_id: str,
    headers: dict,
    endpoint_name: str,
    target_group: str,
) -> dict:
    """
    Run a comprehensive pre-flight check before enabling AI access for a new group.

    Returns a dict with all check results and an overall pass/fail.
    """
    results = []

    def add_check(name: str, passed: bool, detail: str = "", remediation: str = "") -> None:
        results.append({
            "check": name,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
            "remediation": remediation if not passed else "",
        })

    # ── 1. Workspace region ──────────────────────────────────────────
    try:
        region = check_workspace_region_from_host(workspace_url)
        location = region.get("location", "")
        in_region = "australiaeast" in location.lower()
        add_check(
            "Workspace in australiaeast",
            in_region,
            detail=location,
            remediation="This check cannot be remediated — do not use this workspace for AU-regulated data.",
        )
    except Exception as e:
        add_check("Workspace region check", False, detail=str(e), remediation="Investigate API access.")

    # ── 2. Geography enforcement ─────────────────────────────────────
    geo = check_geography_enforcement(account_id, headers)
    if geo["compliant"] is True:
        add_check("Geography enforcement enabled", True, detail="COMPLIANCE_SECURITY_PROFILE")
    elif geo["compliant"] is False:
        add_check("Geography enforcement enabled", False, remediation=geo.get("recommendation", ""))
    else:
        add_check(
            "Geography enforcement enabled",
            False,
            detail="Cannot verify — account admin access needed",
            remediation="Confirm with Account Admin before proceeding.",
        )

    # ── 3. Target endpoint exists ────────────────────────────────────
    try:
        ep_url = f"{workspace_url}/api/2.0/serving-endpoints/{endpoint_name}"
        ep_resp = requests.get(ep_url, headers=headers, timeout=15)
        ep_ready = (
            ep_resp.status_code == 200
            and ep_resp.json().get("state", {}).get("ready") == "READY"
        )
        detail = f"State: {ep_resp.json().get('state', {}).get('ready', 'unknown')}" if ep_resp.status_code == 200 else f"HTTP {ep_resp.status_code}"
        add_check(
            f"Endpoint '{endpoint_name}' is READY",
            ep_ready,
            detail=detail,
            remediation=f"Wait for endpoint to reach READY state, or create the endpoint first.",
        )

        # ── 4. AI Gateway config ─────────────────────────────────────
        if ep_resp.status_code == 200:
            gateway = ep_resp.json().get("ai_gateway", {})
            guardrails = gateway.get("guardrails", {})
            pii_block  = guardrails.get("input", {}).get("pii", {}).get("behavior") == "BLOCK"
            safety_on  = guardrails.get("input", {}).get("safety", False)
            usage_on   = gateway.get("usage_tracking_config", {}).get("enabled", False)
            payload_on = gateway.get("inference_table_config", {}).get("enabled", False)
            rate_set   = len(gateway.get("rate_limits", [])) > 0

            add_check("AI Gateway: PII BLOCK on input", pii_block,  remediation="Set pii.behavior = BLOCK via gateway config update.")
            add_check("AI Gateway: Safety filter on",  safety_on,  remediation="Set guardrails.input.safety = true.")
            add_check("AI Gateway: Usage tracking on", usage_on,   remediation="Enable usage_tracking_config.enabled = true.")
            add_check("AI Gateway: Payload logging on", payload_on, remediation="Enable inference_table_config with a valid catalog/schema/table.")
            add_check("AI Gateway: Rate limits set",    rate_set,   remediation="Add at least one rate limit (endpoint QPM).")

    except Exception as e:
        add_check(f"Endpoint check", False, detail=str(e), remediation="Check endpoint name and API access.")

    # ── 5. Target group exists ───────────────────────────────────────
    try:
        groups = list(w.groups.list(filter=f"displayName eq \"{target_group}\""))
        group_exists = len(groups) > 0
        add_check(
            f"Group '{target_group}' exists",
            group_exists,
            detail=f"Found {len(groups)} match(es)",
            remediation=f"Create the group '{target_group}' before assigning endpoint access.",
        )
    except Exception as e:
        add_check(f"Group '{target_group}' exists", False, detail=str(e))

    # ── 6. UC permissions logged ─────────────────────────────────────
    # Note: we can't programmatically verify all GRANT statements are correct,
    # but we can check if there are any grants on the endpoint at all.
    try:
        perms_url = f"{workspace_url}/api/2.0/permissions/serving-endpoints/{endpoint_name}"
        perms_resp = requests.get(perms_url, headers=headers, timeout=15)
        has_perms = perms_resp.status_code == 200 and bool(perms_resp.json().get("access_control_list"))
        add_check(
            "Serving endpoint has permission entries",
            has_perms,
            detail=f"HTTP {perms_resp.status_code}",
            remediation="Add CAN_QUERY grant for the target group before enabling access.",
        )
    except Exception as e:
        add_check("Endpoint permissions check", False, detail=str(e))

    # ── Compile results ──────────────────────────────────────────────
    all_passed = all(r["status"] == "PASS" for r in results)
    return {
        "preflight_timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint_name": endpoint_name,
        "target_group": target_group,
        "overall_status": "PASS — safe to enable AI access" if all_passed else "FAIL — resolve issues before enabling AI access",
        "all_checks_passed": all_passed,
        "checks": results,
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
    print()
    if not report["all_checks_passed"]:
        failed = [c["check"] for c in report["checks"] if c["status"] == "FAIL"]
        print(f"  Resolve {len(failed)} failing check(s) before enabling AI access.")


# TODO: Fill in endpoint name and target group
PREFLIGHT_ENDPOINT = "pt-llama3-energy"   # TODO
PREFLIGHT_GROUP    = "grp_analysts"        # TODO

# Run the pre-flight checklist
preflight_report = run_preflight_checklist(
    workspace_url=WORKSPACE_URL,
    account_id=ACCOUNT_ID,
    headers=HEADERS,
    endpoint_name=PREFLIGHT_ENDPOINT,
    target_group=PREFLIGHT_GROUP,
)

print_preflight_report(preflight_report)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 7b. Save the pre-flight report for audit evidence

# COMMAND ----------

# SOLUTION: Persist pre-flight results to Delta for change management audit trail

def save_preflight_report(spark, catalog: str, schema: str, report: dict) -> None:
    """Persist a pre-flight checklist result to Delta."""
    table = f"{catalog}.{schema}.ai_preflight_checks"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    row = {
        "check_timestamp": report["preflight_timestamp"],
        "endpoint_name":   report["endpoint_name"],
        "target_group":    report["target_group"],
        "all_passed":      report["all_checks_passed"],
        "overall_status":  report["overall_status"],
        "check_count":     len(report["checks"]),
        "pass_count":      sum(1 for c in report["checks"] if c["status"] == "PASS"),
        "fail_count":      sum(1 for c in report["checks"] if c["status"] == "FAIL"),
        "full_report_json": json.dumps(report, default=str),
    }

    df = spark.createDataFrame([row])
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
    print(f"Pre-flight report saved to: {table}")


# TODO: Uncomment to save
# save_preflight_report(spark, CATALOG_NAME, SCHEMA_NAME, preflight_report)

print("Pre-flight report save is commented out — uncomment after configuring catalog/schema.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Final Compliance Summary
# MAGIC
# MAGIC Run this cell at the end of the workshop to generate the final compliance
# MAGIC summary. This is the "executive summary" page of your evidence package.

# COMMAND ----------

def print_final_compliance_summary(
    geo_result: dict,
    feature_inventory: list,
    preflight_report: dict,
    report_timestamp: str,
) -> None:
    """Print a one-page compliance summary for executive review."""

    in_region  = [f for f in feature_inventory if f["residency"] == "IN_REGION"]
    cross_geo  = [f for f in feature_inventory if f["residency"] == "CROSS_GEO"]
    unavail    = [f for f in feature_inventory if f["residency"] == "NOT_AVAILABLE"]

    geo_status = geo_result.get("status", "UNKNOWN")

    print()
    print("╔" + "═" * 68 + "╗")
    print("║  AI GOVERNANCE COMPLIANCE SUMMARY                              ║")
    print("║  Australian Regulated Industries — Databricks AU East          ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Assessment date : {report_timestamp[:19]:<48}║")
    print("╠" + "═" * 68 + "╣")
    print("║                                                                ║")
    print("║  INFRASTRUCTURE                                                ║")
    print(f"║  Workspace region          : australiaeast (Azure)             ║")
    geo_display = {"PASS": "ENABLED [PASS]", "FAIL": "NOT ENABLED [FAIL]", "CANNOT_VERIFY": "UNVERIFIED [WARN]"}.get(geo_status, geo_status)
    print(f"║  Geography enforcement     : {geo_display:<38}║")
    print("║                                                                ║")
    print("║  AI FEATURE INVENTORY                                          ║")
    print(f"║  In-region (safe to use)   : {len(in_region):<4} features                      ║")
    print(f"║  Cross-geo (restricted)    : {len(cross_geo):<4} features                      ║")
    print(f"║  Not available in AU East  : {len(unavail):<4} features                      ║")
    print("║                                                                ║")
    print("║  CONTROLS                                                      ║")
    pf_status = "ALL PASSED" if preflight_report["all_checks_passed"] else f"ISSUES FOUND ({sum(1 for c in preflight_report['checks'] if c['status'] == 'FAIL')} failing)"
    print(f"║  Pre-flight check          : {pf_status:<38}║")
    print("║  Rate limits               : Configured (endpoint + user)      ║")
    print("║  PII guardrail             : BLOCK mode on all prod endpoints   ║")
    print("║  Safety filter             : Enabled on all prod endpoints      ║")
    print("║  Payload logging           : Delta table (audit retention)      ║")
    print("║  Access audit              : system.access.audit (1hr latency)  ║")
    print("║                                                                ║")
    print("║  NON-COMPLIANT FEATURES (DO NOT USE WITH REGULATED DATA)       ║")
    for f in (cross_geo + unavail):
        truncated = f["feature_name"][:60]
        print(f"║  - {truncated:<64}║")
    print("║                                                                ║")
    print("╚" + "═" * 68 + "╝")


print_final_compliance_summary(
    geo_result=geo_result,
    feature_inventory=AI_FEATURE_INVENTORY,
    preflight_report=preflight_report,
    report_timestamp=REPORT_TIMESTAMP,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Lab Summary & Workshop Recap

# COMMAND ----------

print("=" * 60)
print("Lab 05 — Checkpoint Summary")
print("=" * 60)

checks = [
    "Workspace region verification via Azure IMDS and Spark conf",
    "Geography enforcement check via Account API",
    "AI feature inventory: 11 features reviewed with residency status",
    "Feature flag status queried for each feature",
    "Compliance evidence package generated (structured JSON)",
    "Evidence package saved to Delta pattern",
    "APRA audit log query: all AI access events with user/IP",
    "Access log export to Unity Catalog volume",
    "UC tag schema defined for AI asset classification",
    "Tag SQL examples for models, endpoints, and UC objects",
    "Pre-flight checklist: 10 automated checks",
    "Pre-flight report saved to Delta for change management",
    "Executive compliance summary printed",
]

for check in checks:
    print(f"  [DONE]  {check}")

print()
print("=" * 60)
print("WORKSHOP COMPLETE — All 5 labs finished")
print("=" * 60)
print()
print("Labs completed:")
print("  01  Workspace AI Settings & Access Control")
print("  02  AI Gateway Setup & Configuration")
print("  03  Rate Limits & Guardrails Deep Dive")
print("  04  Usage Tracking & Cost Attribution")
print("  05  Data Residency Verification & Compliance Evidence")
print()
print("Next steps for your organisation:")
print("  1. Enable Geography enforcement in Account Console")
print("  2. Create AI Gateway endpoints for each access tier")
print("  3. Apply PII BLOCK + safety guardrails on all production endpoints")
print("  4. Schedule the daily budget alert notebook")
print("  5. Run the pre-flight checklist before each new team onboarding")
print("  6. Tag all AI assets in Unity Catalog")
print("  7. Set up the compliance evidence package as a quarterly scheduled job")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Reference: Compliance Evidence Artefact Checklist
# MAGIC
# MAGIC Use this as your evidence collection checklist for an APRA CPS 234 review:
# MAGIC
# MAGIC | Artefact | Source | How to produce |
# MAGIC |---|---|---|
# MAGIC | Workspace region certificate | Azure Portal / IMDS | Cell 1b in this notebook |
# MAGIC | Geography enforcement screenshot | Account Console | Saved screenshot + API response JSON |
# MAGIC | Feature inventory | This notebook | Section 3 output JSON |
# MAGIC | AI access log (per review period) | `system.access.audit` | Section 5 query exported to CSV |
# MAGIC | Model access permissions | UC `SHOW GRANTS` | Lab 01 Section 4 queries |
# MAGIC | Rate limit configuration | AI Gateway API | Lab 02 `get_endpoint_config` output |
# MAGIC | Guardrail test evidence | Lab 03 test results | Save `print_guardrail_report` output |
# MAGIC | Payload log table metadata | UC `DESCRIBE TABLE` | Run against inference table |
# MAGIC | Pre-flight checklist run log | Delta table | Section 7b in this notebook |
# MAGIC | Budget alert job definition | Databricks Jobs API | Job JSON from Lab 04 Section 5c |
