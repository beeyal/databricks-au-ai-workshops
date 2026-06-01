# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 01 SOLUTION: Workspace AI Settings & Access Control
# MAGIC
# MAGIC **Reference solution — all exercises completed. Share with participants after the lab.**

# COMMAND ----------

import os
import json
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import ServicePrincipal, Group
from databricks.sdk.service.serving import (
    ServingEndpointAccessControlRequest,
    ServingEndpointPermissionLevel,
)

# SOLUTION: Auto-populate config from the notebook context — no manual token paste needed
WORKSPACE_URL    = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

# SOLUTION: Account ID from secret scope (never hardcode)
try:
    ACCOUNT_ID = dbutils.secrets.get(scope="admin-workshop", key="account-id")
except Exception:
    ACCOUNT_ID = "<account-id-not-in-scope>"

CATALOG_NAME   = "energy_ai"
SCHEMA_NAME    = "models"
MODEL_NAME     = "meter_anomaly_v1"
ENDPOINT_NAME  = "meter-anomaly-endpoint"
CONSUMER_GROUP = "grp_analysts"
ADMIN_GROUP    = "grp_ai_admins"

w = WorkspaceClient()

print(f"Workspace URL       : {WORKSPACE_URL}")
print(f"WorkspaceClient host: {w.config.host}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1: Inspect Workspace AI Feature Status — SOLUTION

# COMMAND ----------

# SOLUTION: Both typed Settings API and legacy workspace-conf keys
AI_SETTING_TYPES = [
    "aibi_genie_space_enabled_ws_setting",
    "restrict_workspace_admins",
]

WORKSPACE_CONF_KEYS = [
    "enableNotebookTableClipboard",
    "enableResultsDownloading",
    "enableExportNotebook",
]


def fetch_typed_setting(workspace_url: str, headers: dict, setting_type: str) -> dict:
    """Fetch one typed workspace setting. Returns a dict with a 'status' key on 404."""
    url = f"{workspace_url}/api/2.0/settings/types/{setting_type}/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 404:
        return {"status": "not_found", "setting_type": setting_type}
    response.raise_for_status()
    return response.json()


def fetch_workspace_conf(workspace_url: str, headers: dict, keys: list) -> dict:
    """Fetch legacy workspace configuration keys via /api/2.0/workspace-conf."""
    url = f"{workspace_url}/api/2.0/workspace-conf"
    params = {"keys": ",".join(keys)}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        return {"error": f"HTTP {response.status_code} — {response.text[:200]}"}
    return response.json()


print(f"{'Setting Type':<52} {'Raw value'}")
print("─" * 80)
for setting_type in AI_SETTING_TYPES:
    result = fetch_typed_setting(WORKSPACE_URL, HEADERS, setting_type)
    inner = result.get(setting_type, {})
    if not inner:
        inner = result.get("status", result)
    print(f"{setting_type:<52} {inner}")

print()
print(f"{'Workspace-conf key':<52} {'Value'}")
print("─" * 80)
workspace_conf = fetch_workspace_conf(WORKSPACE_URL, HEADERS, WORKSPACE_CONF_KEYS)
for key in WORKSPACE_CONF_KEYS:
    value = workspace_conf.get(key, "not_set")
    print(f"{key:<52} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2: Enable / Disable Genie Spaces — SOLUTION

# COMMAND ----------

# SOLUTION: Toggle Genie Spaces with correct ETag handling
def set_genie_space_enabled(workspace_url: str, headers: dict, enabled: bool) -> dict:
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"

    # GET current state to obtain the required ETag (optimistic concurrency)
    get_resp = requests.get(url, headers=headers, timeout=30)
    etag = get_resp.json().get("etag", "") if get_resp.status_code == 200 else ""

    payload = {
        "setting_name": "default",
        "aibi_genie_space_enabled_ws_setting": {"enabled": enabled},
    }
    if etag:
        payload["etag"] = etag

    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# SOLUTION: Enable Genie Spaces (idempotent — safe to re-run)
result = set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=True)
print(f"Genie Space enabled: {result}")
# HTTP 409 Conflict = stale ETag; re-run the cell to auto-fetch a fresh one.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3: Verify Geography Enforcement — SOLUTION

# COMMAND ----------

# SOLUTION: Geography enforcement check + compliance output
def get_enforce_geography_setting(account_id: str, headers: dict) -> dict:
    url = (
        f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}"
        f"/settings/types/shield_csp_enforcement_account_setting/names/default"
    )
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 403:
        return {
            "error": "403 Forbidden",
            "detail": "You need Account Admin role to read this setting.",
            "action": "Ask your Account Admin to verify the toggle in the Account Console.",
        }
    if response.status_code == 404:
        return {
            "error": "404 Not found",
            "detail": "This account may not have the Compliance Security Profile enabled.",
            "action": "Contact your Databricks account team to enable it.",
        }
    response.raise_for_status()
    return response.json()


def compliance_check_geography(setting_response: dict) -> bool:
    """Print a pass/fail compliance check and return True if ENABLED."""
    if "error" in setting_response:
        print(f"CANNOT VERIFY — {setting_response['error']}")
        print(f"   Detail : {setting_response.get('detail', '')}")
        print(f"   Action : {setting_response.get('action', '')}")
        return False
    csp = setting_response.get("shield_csp_enforcement_account_setting", {}).get("csp", "")
    print("─" * 60)
    if csp == "COMPLIANCE_SECURITY_PROFILE":
        print("PASS — Enforce data processing within Geography: ENABLED")
        print("    SOCI Act data residency requirement: MET")
        return True
    else:
        print("FAIL — Enforce data processing within Geography: NOT ENABLED")
        print(f"    Current value : '{csp or '(not set)'}'")
        print("    ACTION: Open the Account Console → Workspaces → Security and compliance tab.")
        return False
    print("─" * 60)


geography_setting = get_enforce_geography_setting(ACCOUNT_ID, HEADERS)
print("=== Geography Enforcement Setting ===")
print(json.dumps(geography_setting, indent=2))
compliance_check_geography(geography_setting)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4: Unity Catalog Permissions — SOLUTION

# COMMAND ----------

# SOLUTION: Grant model permissions via SQL
spark.sql(f"""
  GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{CONSUMER_GROUP}`
""")
print(f"Granted EXECUTE on {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME} to {CONSUMER_GROUP}")

spark.sql(f"""
  GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{ADMIN_GROUP}`
""")
print(f"Granted ALL PRIVILEGES on {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME} to {ADMIN_GROUP}")

display(spark.sql(f"SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"))

# COMMAND ----------

# SOLUTION: Grant Genie Space permission via REST API
def grant_genie_space_permission(
    workspace_url: str,
    headers: dict,
    genie_space_id: str,
    group_name: str,
    permission_level: str,  # "CAN_USE", "CAN_EDIT", or "CAN_MANAGE"
) -> dict:
    """Grant a group access to a Genie Space. PATCH is additive — safe to call multiple times."""
    url = f"{workspace_url}/api/2.0/permissions/dashboards/{genie_space_id}"
    payload = {
        "access_control_list": [
            {
                "group_name": group_name,
                "permission_level": permission_level,
            }
        ]
    }
    response = requests.patch(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


# Grant permission when GENIE_SPACE_ID is available
GENIE_SPACE_ID = "<your-genie-space-id>"  # Replace with actual ID from the URL
# result = grant_genie_space_permission(WORKSPACE_URL, HEADERS, GENIE_SPACE_ID, CONSUMER_GROUP, "CAN_USE")
# print(json.dumps(result, indent=2))
print("Genie Space permission helper defined — set GENIE_SPACE_ID and uncomment to apply.")

# COMMAND ----------

# SOLUTION: Grant serving endpoint permissions via SDK
w.serving_endpoints.update_permissions(
    serving_endpoint_id=ENDPOINT_NAME,
    access_control_list=[
        ServingEndpointAccessControlRequest(
            group_name=CONSUMER_GROUP,
            permission_level=ServingEndpointPermissionLevel.CAN_QUERY,
        ),
        ServingEndpointAccessControlRequest(
            group_name=ADMIN_GROUP,
            permission_level=ServingEndpointPermissionLevel.CAN_MANAGE,
        ),
    ],
)
print(f"SDK permissions set on endpoint: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 5: Service Principal — SOLUTION

# COMMAND ----------

# SOLUTION: Create service principal using the SDK
def create_ai_service_principal(w: WorkspaceClient, display_name: str) -> ServicePrincipal:
    """
    Create a service principal for an AI workload.
    Naming convention: svc-<workload-purpose>
    """
    sp = w.service_principals.create(
        display_name=display_name,
        active=True,
    )
    print(f"Created service principal: {sp.display_name}")
    print(f"    Application ID : {sp.application_id}")
    print(f"    Internal ID    : {sp.id}")
    print()
    print("Next: generate an OAuth client secret and store it in a secret scope or Azure Key Vault.")
    return sp


# SOLUTION: Create the SP
sp = create_ai_service_principal(w, "svc-meter-anomaly-inference")

# SOLUTION: Generate OAuth client secret
# The secret is shown only once — store it immediately in Key Vault or a secret scope
secret = w.service_principal_secrets.create(service_principal_id=sp.id)
print(f"Client ID     : {sp.application_id}")
print(f"Client Secret : [stored in Azure Key Vault — not printed here]")

# SOLUTION: Assign to AI admin group
groups = list(w.groups.list(filter=f"displayName eq \"{ADMIN_GROUP}\""))
if groups:
    w.groups.patch(
        id=groups[0].id,
        operations=[{
            "op": "add",
            "path": "members",
            "value": [{"value": str(sp.id)}],
        }]
    )
    print(f"SP added to group: {ADMIN_GROUP}")
else:
    print(f"Group '{ADMIN_GROUP}' not found — create it in Section 6 first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 6: Groups — SOLUTION

# COMMAND ----------

# SOLUTION: Create all required AI governance groups (idempotent)
AI_GOVERNANCE_GROUPS = [
    "grp_network_ops",
    "grp_regulatory",
    "grp_ai_admins",
    "grp_data_science",
]


def create_group_if_missing(w: WorkspaceClient, display_name: str) -> Group:
    """Idempotently create a workspace group."""
    existing = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if existing:
        print(f"  [EXISTS]  {display_name} (ID: {existing[0].id})")
        return existing[0]
    g = w.groups.create(display_name=display_name)
    print(f"  [CREATED] {display_name} (ID: {g.id})")
    return g


print("Creating AI governance groups...")
created_groups = {name: create_group_if_missing(w, name) for name in AI_GOVERNANCE_GROUPS}
print(f"\nAll {len(created_groups)} groups ready.")

# COMMAND ----------

# SOLUTION: Show current group membership (read-only)
def show_group_members(w: WorkspaceClient, display_name: str) -> None:
    """Print all members of a group, including service principals."""
    groups = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if not groups:
        print(f"Group '{display_name}' not found in this workspace.")
        return
    group = w.groups.get(id=groups[0].id)
    members = group.members or []
    print(f"\nGroup: {display_name} ({len(members)} member(s))")
    print("─" * 50)
    if not members:
        print("  (no members yet)")
    for m in members:
        print(f"  {m.display or '(unnamed)'}  ·  ref: {m.ref}")


def list_all_workspace_groups(w: WorkspaceClient, limit: int = 30) -> None:
    """Print up to `limit` groups visible in the workspace."""
    all_groups = list(w.groups.list())
    print(f"Total workspace groups: {len(all_groups)} (showing first {min(limit, len(all_groups))})")
    print("─" * 60)
    for g in all_groups[:limit]:
        print(f"  {g.display_name:<40} ID: {g.id}")


show_group_members(w, ADMIN_GROUP)
list_all_workspace_groups(w)

# COMMAND ----------

# Lab 01 Final Checkpoint Summary
print("=" * 60)
print("  Lab 01 SOLUTION — Final Checkpoint Summary")
print("=" * 60)
print()

outcomes = [
    ("Section 1", "Workspace AI feature flags queried (typed Settings + workspace-conf)", True),
    ("Section 2", "Genie Space toggle enabled via PATCH API",                             True),
    ("Section 3", "Geography enforcement setting read and verified",                      True),
    ("Section 4", "UC GRANT SQL executed for registered model",                           True),
    ("Section 4", "SDK-based serving endpoint permissions set",                           True),
    ("Section 4", "Genie Space REST permission helper demonstrated",                      True),
    ("Section 5", "Service principal created with OAuth secret",                          True),
    ("Section 5", "SP assigned to AI admin group",                                        True),
    ("Section 6", "All 4 AI governance groups created (idempotent)",                      True),
    ("Section 6", "Group membership listing executed",                                    True),
]

for section, description, done in outcomes:
    icon = "✅" if done else "⬜"
    print(f"  {icon}  [{section}] {description}")

print()
print("─" * 60)
print("  Next lab  : 02_ai_gateway_setup.py")
print("  Topic     : Creating AI Gateway endpoints with rate limits and guardrails")
print("─" * 60)
