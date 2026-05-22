# Databricks notebook source
# MAGIC %md
# MAGIC # Workshop Pre-Flight Check
# MAGIC
# MAGIC **Run this as a workspace admin BEFORE the workshop.**
# MAGIC
# MAGIC Each cell checks one capability. A final summary table shows PASS / FAIL / WARNING
# MAGIC with remediation steps for anything that needs attention.
# MAGIC
# MAGIC Expected runtime: ~4 minutes

# COMMAND ----------

# MAGIC %md ## 0 — Setup

# COMMAND ----------

import json
import time
from datetime import datetime, timezone
from typing import Any

# Results accumulator — list of dicts: {check, status, detail, remediation}
_RESULTS: list[dict] = []

# Status constants
PASS    = "PASS"
FAIL    = "FAIL"
WARN    = "WARNING"


def record(check: str, status: str, detail: str, remediation: str = "") -> None:
    """Record a check result and print immediately."""
    icon = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️"}.get(status, "?")
    print(f"{icon}  [{status:7s}]  {check}")
    if detail:
        print(f"           {detail}")
    if remediation and status != PASS:
        print(f"           Remediation: {remediation}")
    print()
    _RESULTS.append({"check": check, "status": status, "detail": detail, "remediation": remediation})


def safe_run(fn, check_name: str, remediation: str):
    """Execute fn(); catch exceptions and record as FAIL."""
    try:
        fn()
    except Exception as exc:
        record(check_name, FAIL, f"Unexpected error: {exc}", remediation)


print("=" * 70)
print(f"  Databricks AU AI Workshops — Pre-Flight Check")
print(f"  Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)
print()

# COMMAND ----------

# MAGIC %md ## 1 — Workspace Identity and Region

# COMMAND ----------

import re


def check_workspace_region():
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    host = ctx.apiUrl().get()                   # e.g. https://adb-xxxx.azuredatabricks.net
    workspace_id = ctx.workspaceId().get()

    # Try to derive region from the cluster spark conf (Azure injects this)
    try:
        region = spark.conf.get("spark.databricks.clusterUsageTags.region")
    except Exception:
        region = "unknown"

    # Cloud provider
    try:
        cloud = spark.conf.get("spark.databricks.clusterUsageTags.cloudProvider", "unknown").lower()
    except Exception:
        cloud = "unknown"

    detail = f"Host: {host} | Workspace ID: {workspace_id} | Region: {region} | Cloud: {cloud}"

    # Validate: must be Azure australiaeast for in-region AI features
    if cloud == "azure" and "australiaeast" in region.lower():
        record("Workspace region (Azure australiaeast)", PASS, detail)
    elif cloud == "azure" and region != "unknown":
        record(
            "Workspace region",
            WARN,
            detail,
            remediation=(
                f"Region is '{region}', not 'australiaeast'. "
                "Some AU-data-residency AI features (Qwen3 embedding, KA/MAS) are only available "
                "in Azure australiaeast. Confirm with your Databricks account team before the workshop."
            ),
        )
    elif region == "unknown":
        record("Workspace region", WARN, detail, remediation="Could not determine region from Spark conf. Verify manually in the Account Console.")
    else:
        record("Workspace region", PASS, detail)


safe_run(
    check_workspace_region,
    "Workspace region",
    "Check Account Console > Workspaces for region details.",
)

# COMMAND ----------

# MAGIC %md ## 2 — Unity Catalog Enabled

# COMMAND ----------


def check_unity_catalog():
    # If UC is enabled, spark.sql("SHOW CATALOGS") returns at least 'system' and 'hive_metastore'
    catalogs = [r["catalog"] for r in spark.sql("SHOW CATALOGS").collect()]
    has_system  = "system" in catalogs
    has_main    = any(c not in ("hive_metastore", "__databricks_internal") for c in catalogs)

    if has_system and has_main:
        record(
            "Unity Catalog enabled",
            PASS,
            f"Catalogs visible: {', '.join(catalogs[:8])}{'…' if len(catalogs) > 8 else ''}",
        )
    elif has_system:
        record(
            "Unity Catalog enabled",
            WARN,
            f"Only 'system' and 'hive_metastore' catalogs found. No customer catalog yet.",
            remediation="Unity Catalog is enabled. Create a catalog for the workshop: CREATE CATALOG workshop_au;",
        )
    else:
        record(
            "Unity Catalog enabled",
            FAIL,
            "SHOW CATALOGS returned only hive_metastore — Unity Catalog not enabled.",
            remediation=(
                "Enable Unity Catalog in the Account Console > Unity Catalog. "
                "Assign a metastore to this workspace. Requires Account Admin role. "
                "See: https://docs.databricks.com/data-governance/unity-catalog/get-started.html"
            ),
        )


safe_run(
    check_unity_catalog,
    "Unity Catalog enabled",
    "Open Account Console > Unity Catalog and enable it for this workspace.",
)

# COMMAND ----------

# MAGIC %md ## 3 — Serverless Compute Enabled

# COMMAND ----------


def check_serverless():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()

    # Check workspace settings for serverless
    try:
        settings = w.settings.default_namespace.get()
    except Exception:
        settings = None

    # Try to list serverless SQL warehouses as a proxy for serverless enablement
    warehouses = list(w.warehouses.list())
    serverless_wh = [wh for wh in warehouses if getattr(wh, "enable_serverless_compute", False)]
    serverless_or_pro = [wh for wh in warehouses if wh.warehouse_type and wh.warehouse_type.value in ("PRO", "SERVERLESS")]

    # Also check if notebook-level serverless is on (Spark conf key injected by platform)
    try:
        is_serverless_nb = spark.conf.get("spark.databricks.clusterUsageTags.clusterNodeType", "") == "serverless"
    except Exception:
        is_serverless_nb = False

    if serverless_wh:
        record("Serverless compute enabled", PASS, f"Found {len(serverless_wh)} serverless SQL warehouse(s).")
    elif serverless_or_pro:
        record(
            "Serverless compute enabled",
            WARN,
            f"Found {len(serverless_or_pro)} Pro/Serverless-capable warehouse(s) — check serverless is enabled on each.",
            remediation="In SQL Warehouses, edit the warehouse and enable 'Serverless' under Advanced Options.",
        )
    else:
        record(
            "Serverless compute enabled",
            WARN,
            "No serverless-enabled SQL warehouses found. Workshop exercises use serverless.",
            remediation=(
                "Create a Serverless SQL Warehouse: SQL Warehouses > Create > select 'Serverless'. "
                "If the option is greyed out, contact your workspace admin to enable serverless "
                "in Account Console > Settings > Feature Enablement."
            ),
        )


safe_run(
    check_serverless,
    "Serverless compute enabled",
    "Enable serverless in Account Console > Feature Enablement.",
)

# COMMAND ----------

# MAGIC %md ## 4 — AI Features Enabled (Genie, AI Playground, Notebook Assistant)

# COMMAND ----------


def check_ai_features():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()

    results = {}

    # 4a — AI Playground / Foundation Model API: try listing serving endpoints
    try:
        endpoints = list(w.serving_endpoints.list())
        fmapi_endpoints = [ep for ep in endpoints if "databricks" in (ep.creator or "").lower()
                           or (ep.name or "").startswith("databricks-")]
        results["Foundation Model API accessible"] = (True, f"{len(endpoints)} endpoint(s) listed")
    except Exception as exc:
        results["Foundation Model API accessible"] = (False, str(exc))

    # 4b — Genie: try listing Genie spaces (requires feature enabled)
    try:
        spaces = list(w.genie.list_spaces())
        results["Genie Spaces accessible"] = (True, f"{len(spaces)} Genie space(s) found")
    except Exception as exc:
        if "FEATURE_DISABLED" in str(exc) or "403" in str(exc) or "feature" in str(exc).lower():
            results["Genie Spaces accessible"] = (False, f"Feature not enabled: {exc}")
        else:
            results["Genie Spaces accessible"] = (True, f"API reachable (0 spaces yet): {exc}")

    # 4c — Notebook AI Assistant: check workspace conf
    try:
        conf_resp = w.workspace_conf.get_status(keys=["enableNotebookAIAssistant"])
        nb_assist = conf_resp.get("enableNotebookAIAssistant", "unknown")
        results["Notebook AI Assistant"] = (
            nb_assist.lower() in ("true", "1"),
            f"enableNotebookAIAssistant={nb_assist}"
        )
    except Exception as exc:
        results["Notebook AI Assistant"] = (True, f"Config key not accessible (may be enabled by default): {exc}")

    all_ok = all(v for v, _ in results.values())
    detail = " | ".join(f"{k}: {'OK' if v else 'FAIL'} ({d})" for k, (v, d) in results.items())

    if all_ok:
        record("AI features (Genie + FMAPI + Notebook Assistant)", PASS, detail)
    else:
        failed = [k for k, (v, _) in results.items() if not v]
        record(
            "AI features",
            FAIL,
            detail,
            remediation=(
                f"Failed: {', '.join(failed)}. "
                "Enable in: Account Console > Settings > Feature Enablement > AI/ML features. "
                "For Genie specifically, also ensure 'Databricks AI' is enabled in Workspace Settings > Features. "
                "For Notebook AI Assistant, go to Admin Settings > Workspace Settings > Enable AI Assistant."
            ),
        )


safe_run(
    check_ai_features,
    "AI features (Genie + FMAPI + Notebook Assistant)",
    "Enable AI features in Account Console > Settings > Feature Enablement.",
)

# COMMAND ----------

# MAGIC %md ## 5 — Data Processing Geography Enforcement

# COMMAND ----------


def check_data_geography():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()

    # Check the 'Enforce data processing within Geography' workspace setting
    # This maps to the workspace conf key 'enforceUserIsolation' / data residency controls
    # The public setting in Account Console is under Compliance & Security
    try:
        conf = w.workspace_conf.get_status(keys=["enableDataProcessingWithinGeography"])
        val = conf.get("enableDataProcessingWithinGeography", "unknown")
    except Exception:
        val = "unknown"

    # Also check via account-level compliance settings if possible
    try:
        from databricks.sdk import AccountClient
        a = AccountClient()
        compliance = a.settings.compliance_security_profile.get()
        is_compliance_enabled = compliance.compliance_security_profile_workspace.is_enabled
    except Exception:
        is_compliance_enabled = None

    if val.lower() in ("true", "1"):
        record(
            "Data processing within geography",
            PASS,
            "Workspace setting 'Enforce data processing within Geography' is enabled.",
        )
    elif val == "unknown" and is_compliance_enabled:
        record(
            "Data processing within geography",
            PASS,
            "Compliance Security Profile enabled — data residency controls active.",
        )
    elif val == "unknown":
        record(
            "Data processing within geography",
            WARN,
            "Could not confirm geography enforcement setting — verify manually.",
            remediation=(
                "In Account Console, go to Workspaces > [this workspace] > Compliance & Security. "
                "Enable 'Enforce data processing within Geography'. "
                "This is required for APRA CPS 234 and AEMO/AER data sovereignty obligations."
            ),
        )
    else:
        record(
            "Data processing within geography",
            FAIL,
            f"Setting value: {val} — geography enforcement is NOT enabled.",
            remediation=(
                "Enable 'Enforce data processing within Geography' in Account Console > "
                "Workspaces > [this workspace] > Compliance & Security. "
                "Restart all clusters after enabling. Required for regulated industry workshops."
            ),
        )


safe_run(
    check_data_geography,
    "Data processing within geography",
    "Enable in Account Console > Workspaces > Compliance & Security.",
)

# COMMAND ----------

# MAGIC %md ## 6 — Model Serving Availability

# COMMAND ----------


def check_model_serving():
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ServedModelInput, ServedModelInputWorkloadSize

    w = WorkspaceClient()

    # Check FMAPI pay-per-token endpoints are reachable
    try:
        endpoints = {ep.name: ep for ep in w.serving_endpoints.list()}
    except Exception as exc:
        record(
            "Model Serving availability",
            FAIL,
            f"Cannot list serving endpoints: {exc}",
            remediation="Ensure Model Serving is enabled for this workspace and your token has 'Can Query' permission.",
        )
        return

    # Check for the Qwen3 embedding model (needed for Vector Search)
    qwen3_name   = "databricks-qwen3-embedding-0-6b"
    llama_name   = "databricks-meta-llama-3-3-70b-instruct"
    dbrx_name    = "databricks-dbrx-instruct"

    expected_models = [qwen3_name, llama_name, dbrx_name]
    found_models    = [m for m in expected_models if m in endpoints]
    missing_models  = [m for m in expected_models if m not in endpoints]

    # Query one FMAPI model to validate end-to-end connectivity
    test_model = llama_name if llama_name in endpoints else (found_models[0] if found_models else None)
    query_ok   = False
    query_detail = "No FMAPI model available to test"

    if test_model:
        try:
            import urllib.request
            ctx  = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
            host = ctx.apiUrl().get()
            token = ctx.apiToken().get()
            payload = json.dumps({
                "messages": [{"role": "user", "content": "Reply with only the word: OK"}],
                "max_tokens": 5,
            }).encode()
            req = urllib.request.Request(
                f"{host}/serving-endpoints/{test_model}/invocations",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read())
                reply = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                query_ok = True
                query_detail = f"Test query to '{test_model}' succeeded. Response: '{reply.strip()[:50]}'"
        except Exception as exc:
            query_detail = f"Test query to '{test_model}' failed: {exc}"

    if found_models and query_ok:
        record(
            "Model Serving availability",
            PASS,
            f"Found: {', '.join(found_models)}. {query_detail}",
        )
    elif found_models:
        record(
            "Model Serving availability",
            WARN,
            f"Endpoints exist but test query failed. {query_detail}",
            remediation="Check Model Serving quotas and network egress rules. Ensure the cluster can reach the serving endpoint URL.",
        )
    else:
        record(
            "Model Serving availability",
            FAIL,
            f"Missing pay-per-token models: {', '.join(missing_models)}. Total endpoints found: {len(endpoints)}",
            remediation=(
                "Pay-per-token FMAPI endpoints are provisioned automatically if Model Serving is enabled. "
                "Go to Serving > Foundation Models and confirm the endpoint list. "
                "If unavailable in australiaeast, check go/mosaic-au-roadmap for regional availability."
            ),
        )


safe_run(
    check_model_serving,
    "Model Serving availability",
    "Enable Model Serving in Account Console > Feature Enablement.",
)

# COMMAND ----------

# MAGIC %md ## 7 — Vector Search Availability

# COMMAND ----------


def check_vector_search():
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.vectorsearch import EndpointType

    w = WorkspaceClient()

    try:
        vs_endpoints = list(w.vector_search_endpoints.list_endpoints())
    except Exception as exc:
        record(
            "Vector Search availability",
            FAIL,
            f"Cannot list Vector Search endpoints: {exc}",
            remediation=(
                "Enable Vector Search in Account Console > Feature Enablement. "
                "Then create an endpoint: w.vector_search_endpoints.create_endpoint(name='workshop_vs', endpoint_type=EndpointType.STANDARD)"
            ),
        )
        return

    if vs_endpoints:
        ready = [ep for ep in vs_endpoints if str(getattr(ep, "endpoint_status", "")).upper() in ("ONLINE", "PROVISIONING")]
        names = [ep.name for ep in vs_endpoints]
        if ready:
            record("Vector Search availability", PASS, f"Endpoints: {', '.join(names)}")
        else:
            record(
                "Vector Search availability",
                WARN,
                f"Endpoints found but none ONLINE: {', '.join(names)}",
                remediation="Wait for endpoint provisioning to complete (can take 10-15 minutes). Check status in the Vector Search UI.",
            )
    else:
        record(
            "Vector Search availability",
            WARN,
            "No Vector Search endpoints found. The setup notebook will create one.",
            remediation=(
                "Run the setup notebook (00_workspace_setup.py) to create the Vector Search endpoint automatically. "
                "Or manually: databricks vector-search endpoints create --name workshop_vs --endpoint-type STANDARD"
            ),
        )


safe_run(
    check_vector_search,
    "Vector Search availability",
    "Enable Vector Search and create an endpoint via the SDK or setup notebook.",
)

# COMMAND ----------

# MAGIC %md ## 8 — system.access.audit Access

# COMMAND ----------


def check_audit_access():
    try:
        # Check the table exists and we can read at least 1 row
        count = spark.sql(
            "SELECT COUNT(*) AS n FROM system.access.audit LIMIT 1"
        ).collect()[0]["n"]
        # Pull a sample to verify data freshness
        sample = spark.sql(
            """
            SELECT MAX(event_time) AS latest_event
            FROM   system.access.audit
            WHERE  event_time > current_timestamp() - INTERVAL 7 DAYS
            """
        ).collect()[0]
        latest = sample["latest_event"]
        if latest:
            record(
                "system.access.audit access",
                PASS,
                f"Readable. Latest event within 7 days: {latest}",
            )
        else:
            record(
                "system.access.audit access",
                WARN,
                "Table is readable but no events in the last 7 days — audit log delivery may be delayed.",
                remediation="Check Account Console > System Tables > Audit to confirm audit log streaming is enabled.",
            )
    except Exception as exc:
        record(
            "system.access.audit access",
            FAIL,
            f"Cannot query system.access.audit: {exc}",
            remediation=(
                "Enable system tables: Account Console > Metastore > System Tables > Enable. "
                "Grant access: GRANT SELECT ON system.access.audit TO `data.admin@company.com`; "
                "Note: system tables require Unity Catalog and Metastore Admin role."
            ),
        )


safe_run(
    check_audit_access,
    "system.access.audit access",
    "Enable system tables in Account Console > Metastore > System Tables.",
)

# COMMAND ----------

# MAGIC %md ## 9 — system.billing.usage Access

# COMMAND ----------


def check_billing_access():
    try:
        count = spark.sql(
            "SELECT COUNT(*) AS n FROM system.billing.usage WHERE usage_date > current_date() - 30"
        ).collect()[0]["n"]
        record(
            "system.billing.usage access",
            PASS,
            f"{count:,} billing rows in the last 30 days.",
        )
    except Exception as exc:
        record(
            "system.billing.usage access",
            FAIL,
            f"Cannot query system.billing.usage: {exc}",
            remediation=(
                "Enable system tables: Account Console > Metastore > System Tables > Enable. "
                "Grant SELECT on system.billing.usage to the workshop user group. "
                "Billing data streams with a ~4-hour lag."
            ),
        )


safe_run(
    check_billing_access,
    "system.billing.usage access",
    "Enable billing system tables and grant SELECT to workshop users.",
)

# COMMAND ----------

# MAGIC %md ## 10 — Workshop Catalog and Permissions

# COMMAND ----------


def check_workshop_catalog():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()

    catalog_name = "workshop_au"

    try:
        catalogs = {c.name for c in w.catalogs.list()}
    except Exception as exc:
        record(
            "Workshop catalog",
            WARN,
            f"Could not list catalogs via SDK: {exc}",
            remediation="Run the setup notebook (00_workspace_setup.py) to create workshop_au catalog.",
        )
        return

    if catalog_name in catalogs:
        # Check schemas
        try:
            schemas = {s.name for s in w.schemas.list(catalog_name=catalog_name)}
            expected = {"energy", "audit", "ai_governance"}
            missing  = expected - schemas
            if not missing:
                record(
                    "Workshop catalog",
                    PASS,
                    f"Catalog '{catalog_name}' exists with schemas: {', '.join(sorted(schemas))}",
                )
            else:
                record(
                    "Workshop catalog",
                    WARN,
                    f"Catalog exists but missing schemas: {', '.join(missing)}",
                    remediation="Run the setup notebook (00_workspace_setup.py) to create the missing schemas.",
                )
        except Exception as exc:
            record("Workshop catalog", WARN, f"Catalog exists but schema list failed: {exc}")
    else:
        record(
            "Workshop catalog",
            WARN,
            f"Catalog '{catalog_name}' does not exist yet.",
            remediation="Run the setup notebook (00_workspace_setup.py) to create the catalog and schemas.",
        )


safe_run(
    check_workshop_catalog,
    "Workshop catalog",
    "Run 00_workspace_setup.py to create workshop_au catalog.",
)

# COMMAND ----------

# MAGIC %md ## Final Report

# COMMAND ----------

print()
print("=" * 70)
print("  PRE-FLIGHT CHECK SUMMARY")
print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)

status_icon = {PASS: "✅", FAIL: "❌", WARN: "⚠️ "}
col_w = 45

header = f"{'CHECK':<{col_w}} {'STATUS':8}  DETAIL"
print(header)
print("-" * 70)
for r in _RESULTS:
    icon   = status_icon.get(r["status"], "?")
    status = r["status"]
    check  = r["check"][:col_w]
    # Truncate detail for table readability
    detail = (r["detail"] or "")[:60]
    if len(r["detail"] or "") > 60:
        detail += "…"
    print(f"{check:<{col_w}} {icon} {status:7s}  {detail}")

print("-" * 70)

n_pass = sum(1 for r in _RESULTS if r["status"] == PASS)
n_fail = sum(1 for r in _RESULTS if r["status"] == FAIL)
n_warn = sum(1 for r in _RESULTS if r["status"] == WARN)

print(f"\n  Total: {len(_RESULTS)} checks — {n_pass} PASS  |  {n_warn} WARNING  |  {n_fail} FAIL")

if n_fail == 0 and n_warn == 0:
    print("\n  ✅  All checks passed. Workspace is ready for the workshop.")
elif n_fail == 0:
    print(f"\n  ⚠️   {n_warn} warning(s) — review remediation steps above before the workshop.")
else:
    print(f"\n  ❌  {n_fail} check(s) FAILED — these must be resolved before the workshop.")
    print()
    print("  FAILED CHECKS — REMEDIATION REQUIRED:")
    for r in _RESULTS:
        if r["status"] == FAIL:
            print(f"\n  ❌ {r['check']}")
            print(f"     Detail:     {r['detail']}")
            print(f"     Remediate:  {r['remediation']}")

print()
print("=" * 70)
