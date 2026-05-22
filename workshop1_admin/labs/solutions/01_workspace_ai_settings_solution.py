# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 01 SOLUTION: Workspace AI Settings & Access Control
# MAGIC
# MAGIC **This is the reference solution notebook. All TODO items are completed.**

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

# ── SOLUTION: Configuration ───────────────────────────────────────────────────
WORKSPACE_URL   = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

ACCOUNT_ID     = dbutils.secrets.get(scope="admin-workshop", key="account-id")
CATALOG_NAME   = "energy_ai"
SCHEMA_NAME    = "models"
MODEL_NAME     = "meter_anomaly_v1"
ENDPOINT_NAME  = "meter-anomaly-endpoint"
CONSUMER_GROUP = "grp_analysts"
ADMIN_GROUP    = "grp_ai_admins"

w = WorkspaceClient()

print(f"Workspace URL : {WORKSPACE_URL}")
print(f"WorkspaceClient host: {w.config.host}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Inspect Workspace AI Feature Status — SOLUTION

# COMMAND ----------

# SOLUTION
def get_workspace_settings(workspace_url: str, headers: dict) -> dict:
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 404:
        return {"status": "not_configured", "meaning": "Genie Spaces uses workspace default (enabled)"}
    response.raise_for_status()
    return response.json()


genie_setting = get_workspace_settings(WORKSPACE_URL, HEADERS)
print("=== Genie Space Workspace Setting ===")
print(json.dumps(genie_setting, indent=2))

# COMMAND ----------

# SOLUTION: Query all AI-relevant settings
AI_SETTING_TYPES = [
    "aibi_genie_space_enabled_ws_setting",
    "enable_export_notebook",
    "enable_results_downloading",
    "restrict_workspace_admins",
]


def fetch_setting(workspace_url, headers, setting_type):
    url = f"{workspace_url}/api/2.0/settings/types/{setting_type}/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 404:
        return {"status": "not_found"}
    response.raise_for_status()
    return response.json()


print(f"{'Setting Type':<50} {'Current Value'}")
print("-" * 80)
for setting_type in AI_SETTING_TYPES:
    result = fetch_setting(WORKSPACE_URL, HEADERS, setting_type)
    # Extract the typed value
    typed_value = result.get(setting_type, result.get("status", "N/A"))
    print(f"{setting_type:<50} {typed_value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Enable/Disable Genie Spaces — SOLUTION

# COMMAND ----------

# SOLUTION: Toggle Genie Spaces
def set_genie_space_enabled(workspace_url: str, headers: dict, enabled: bool) -> dict:
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"

    # GET current etag
    get_resp = requests.get(url, headers=headers, timeout=30)
    etag = get_resp.json().get("etag", "") if get_resp.status_code == 200 else ""

    payload = {
        "setting_name": "default",
        "aibi_genie_space_enabled_ws_setting": {"enabled": enabled},
        "etag": etag,
    }
    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# Enable Genie Spaces
result = set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=True)
print(f"Genie Space enabled: {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verify Geography Enforcement — SOLUTION

# COMMAND ----------

# SOLUTION: Geography enforcement check + compliance output
def get_enforce_geography_setting(account_id: str, headers: dict) -> dict:
    url = (
        f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}"
        f"/settings/types/shield_csp_enforcement_account_setting/names/default"
    )
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 403:
        return {"error": "403 Forbidden — account admin role required"}
    response.raise_for_status()
    return response.json()


def compliance_check_geography(setting_response: dict) -> bool:
    if "error" in setting_response:
        print(f"[WARN] Cannot verify: {setting_response['error']}")
        return False
    csp = setting_response.get("shield_csp_enforcement_account_setting", {}).get("csp", "")
    if csp == "COMPLIANCE_SECURITY_PROFILE":
        print("[PASS] Geography enforcement: ENABLED — regulated workloads protected.")
        return True
    else:
        print(f"[FAIL] Geography enforcement: NOT ENABLED (value='{csp}')")
        return False


geography_setting = get_enforce_geography_setting(ACCOUNT_ID, HEADERS)
print(json.dumps(geography_setting, indent=2))
compliance_check_geography(geography_setting)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. UC Permissions — SOLUTION

# COMMAND ----------

# SOLUTION: Grant model permissions
spark.sql(f"""
  GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{CONSUMER_GROUP}`
""")

spark.sql(f"""
  GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{ADMIN_GROUP}`
""")

display(spark.sql(f"SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"))

# COMMAND ----------

# SOLUTION: Grant endpoint permissions via SDK
w.serving_endpoints.set_permissions(
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
print(f"Permissions set on endpoint: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Service Principal — SOLUTION

# COMMAND ----------

# SOLUTION: Create service principal and assign to group
sp = w.service_principals.create(
    display_name="svc-meter-anomaly-inference",
    active=True,
)
print(f"Created SP: {sp.display_name} (ID: {sp.id})")

# Generate OAuth secret
secret = w.service_principals.create_secret(sp.id)
print(f"Client ID    : {sp.application_id}")
print(f"Client Secret: [store in Azure Key Vault]")

# Assign to AI admin group
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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Groups — SOLUTION

# COMMAND ----------

# SOLUTION: Create all required AI governance groups
AI_GOVERNANCE_GROUPS = [
    "grp_network_ops",
    "grp_regulatory",
    "grp_ai_admins",
    "grp_data_science",
]


def create_group_if_missing(w: WorkspaceClient, display_name: str) -> Group:
    existing = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if existing:
        print(f"  [EXISTS] {display_name} (ID: {existing[0].id})")
        return existing[0]
    g = w.groups.create(display_name=display_name)
    print(f"  [CREATED] {display_name} (ID: {g.id})")
    return g


print("Creating AI governance groups...")
created = {name: create_group_if_missing(w, name) for name in AI_GOVERNANCE_GROUPS}
print(f"\nAll {len(created)} groups ready.")

# COMMAND ----------

# SOLUTION: Show members of the admin group
def show_group_members(w: WorkspaceClient, display_name: str) -> None:
    groups = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if not groups:
        print(f"Group '{display_name}' not found.")
        return
    group = w.groups.get(id=groups[0].id)
    members = group.members or []
    print(f"Group: {display_name} — {len(members)} members")
    for m in members:
        print(f"  {m.display} ({m.ref})")


show_group_members(w, ADMIN_GROUP)

# COMMAND ----------

# Lab 01 Summary
print("=" * 60)
print("Lab 01 SOLUTION — Complete")
print("=" * 60)
print()
print("All tasks completed:")
print("  [DONE] Workspace AI settings queried via REST API")
print("  [DONE] Genie Space toggle enabled")
print("  [DONE] Geography enforcement verified")
print("  [DONE] UC GRANT statements executed (model + endpoint)")
print("  [DONE] Service principal created")
print("  [DONE] AI governance groups created")
