# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 01: Workspace AI Settings & Access Control
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
# MAGIC 1. Inspect current workspace AI feature status via the Databricks REST API
# MAGIC 2. Enable and disable specific AI features at workspace level
# MAGIC 3. Verify the **"Enforce data processing within Geography"** account-level setting
# MAGIC 4. Grant Unity Catalog permissions on models, serving endpoints, and AI functions
# MAGIC 5. Create service principals for automated AI workloads
# MAGIC 6. Configure groups and Genie Space access for different business units
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## AU East Residency Reminder
# MAGIC
# MAGIC | Feature | Status |
# MAGIC |---|---|
# MAGIC | Genie Spaces | In-region (safe) |
# MAGIC | AI Gateway | In-region (safe) |
# MAGIC | FMAPI Provisioned Throughput | In-region (safe) |
# MAGIC | FMAPI Pay-Per-Token | Cross-geo — do NOT use for regulated data |
# MAGIC | Knowledge Assistant | Cross-geo — workaround required |
# MAGIC | Foundation Model Fine-tuning | Not available in AU East |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC - Workspace admin or account admin role
# MAGIC - A running cluster (DBR 14.3 LTS or later)
# MAGIC - `databricks-sdk` installed (pre-installed on DBR 13+)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Setup — Fill in your workspace details

# COMMAND ----------

import os

# TODO: Replace with your workspace URL (no trailing slash)
# Example: "https://adb-1234567890123456.7.azuredatabricks.net"
WORKSPACE_URL = "https://<your-workspace>.azuredatabricks.net"

# TODO: Paste a personal access token (Settings > Developer > Access tokens)
# In production, use a service principal OAuth token instead.
DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")

# Derived — do not edit
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

print(f"Workspace URL : {WORKSPACE_URL}")
print("Token         : [loaded from secret scope]")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Inspect Current Workspace AI Feature Status
# MAGIC
# MAGIC The Databricks workspace settings API exposes a `settings` namespace that
# MAGIC includes AI-related feature flags. We will query them now to understand the
# MAGIC current state before making any changes.

# COMMAND ----------

import requests
import json

def get_workspace_settings(workspace_url: str, headers: dict) -> dict:
    """
    Retrieve workspace-level feature settings via the Settings API.
    Returns the full settings payload as a dict.
    """
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def get_default_namespace_setting(workspace_url: str, headers: dict) -> dict:
    """Return the default catalog/schema namespace setting."""
    url = f"{workspace_url}/api/2.0/settings/types/default_namespace_ws_setting/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


# Query Genie Space feature flag
try:
    genie_setting = get_workspace_settings(WORKSPACE_URL, HEADERS)
    print("=== Genie Space Workspace Setting ===")
    print(json.dumps(genie_setting, indent=2))
except requests.HTTPError as e:
    print(f"HTTP error: {e.response.status_code} — {e.response.text}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b. List All AI-Relevant Workspace Settings
# MAGIC
# MAGIC The Settings API uses a typed namespace pattern. The table below lists the
# MAGIC setting types most relevant to AI governance in regulated environments.
# MAGIC
# MAGIC | Setting / API | What it controls |
# MAGIC |---|---|
# MAGIC | `aibi_genie_space_enabled_ws_setting` (typed API) | Genie Spaces on/off |
# MAGIC | `restrict_workspace_admins` (typed API) | Limits what non-admin users can do |
# MAGIC | `enableExportNotebook` (workspace-conf API) | Whether users can download notebooks |
# MAGIC | `enableResultsDownloading` (workspace-conf API) | Whether query results can be exported |
# MAGIC
# MAGIC **API paths:**
# MAGIC - Typed settings: `GET /api/2.0/settings/types/{type}/names/default`
# MAGIC - Legacy workspace conf: `GET /api/2.0/workspace-conf?keys=key1,key2`

# COMMAND ----------

# NOTE: The typed Settings API (/api/2.0/settings/types/…/names/default) only covers
# a subset of workspace controls. The following setting types are valid for this API:
#   - aibi_genie_space_enabled_ws_setting   → Genie Spaces on/off
#   - restrict_workspace_admins             → Restricts admin capabilities
#
# Older controls (notebook export, results download) live in the legacy
# workspace config API (/api/2.0/workspace-conf) and are NOT reachable via
# the typed settings path. Attempting to use the typed API for them returns 404.
AI_SETTING_TYPES = [
    "aibi_genie_space_enabled_ws_setting",
    "restrict_workspace_admins",
]

# These are fetched from the legacy workspace-conf endpoint instead
WORKSPACE_CONF_KEYS = [
    "enableNotebookTableClipboard",    # whether users can export notebook output
    "enableResultsDownloading",        # whether query results can be downloaded
    "enableExportNotebook",            # whether notebooks can be downloaded
]


def fetch_setting(workspace_url: str, headers: dict, setting_type: str) -> dict:
    url = f"{workspace_url}/api/2.0/settings/types/{setting_type}/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 404:
        return {"status": "not_found", "setting_type": setting_type}
    response.raise_for_status()
    return response.json()


def fetch_workspace_conf(workspace_url: str, headers: dict, keys: list) -> dict:
    """Fetch legacy workspace configuration keys."""
    url = f"{workspace_url}/api/2.0/workspace-conf"
    params = {"keys": ",".join(keys)}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        return {"error": f"HTTP {response.status_code}"}
    return response.json()


print(f"{'Setting Type':<50} {'Value / Status'}")
print("-" * 80)
for setting_type in AI_SETTING_TYPES:
    result = fetch_setting(WORKSPACE_URL, HEADERS, setting_type)
    value = result.get(setting_type, {})
    if not value:
        value = result.get("status", result)
    print(f"{setting_type:<50} {value}")

print()
print(f"{'Workspace conf key':<50} {'Value / Status'}")
print("-" * 80)
workspace_conf = fetch_workspace_conf(WORKSPACE_URL, HEADERS, WORKSPACE_CONF_KEYS)
for key in WORKSPACE_CONF_KEYS:
    value = workspace_conf.get(key, "not_set")
    print(f"{key:<50} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Enable / Disable Genie Spaces at Workspace Level
# MAGIC
# MAGIC **Why this matters for regulated industries:**
# MAGIC
# MAGIC Genie Spaces execute queries in-region (AU East). However, you may need to
# MAGIC restrict access to specific business units while an APRA CPS 234 or CPS 230
# MAGIC review is underway. The workspace-level toggle is the coarsest control.
# MAGIC Finer-grained control is handled via Unity Catalog grants (see section 4).

# COMMAND ----------

def set_genie_space_enabled(workspace_url: str, headers: dict, enabled: bool) -> dict:
    """
    Enable or disable Genie Spaces at the workspace level.

    Parameters
    ----------
    enabled : bool
        True to enable, False to disable.
    """
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"

    payload = {
        "setting_name": "default",
        "aibi_genie_space_enabled_ws_setting": {
            "enabled": enabled
        }
    }

    # GET the current etag first — required for conditional updates
    get_response = requests.get(url, headers=headers, timeout=30)
    if get_response.status_code == 200:
        etag = get_response.json().get("etag", "")
        payload["etag"] = etag

    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# TODO: Uncomment ONE of the lines below and run this cell
# set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=True)   # Turn Genie on
# set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=False)  # Turn Genie off

print("Genie Space toggle: commented out for safety.")
print("Uncomment the appropriate line above to change the setting.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Verify "Enforce Data Processing Within Geography"
# MAGIC
# MAGIC This account-level control is the **most important compliance setting** for
# MAGIC APRA-regulated entities. When enabled, it prevents Databricks features from
# MAGIC routing data to regions outside the workspace's primary geography.
# MAGIC
# MAGIC **Who can change it:** Account admins only (not workspace admins).
# MAGIC
# MAGIC The API endpoint lives under the Account API, not the Workspace API.

# COMMAND ----------

# TODO: Replace with your Databricks Account ID
# Found in: Account Console > Settings > Account information
ACCOUNT_ID = "<your-account-id>"

# Account-level API uses the same token if the user is an account admin
ACCOUNT_API_BASE = f"https://accounts.azuredatabricks.net/api/2.0/accounts/{ACCOUNT_ID}"

def get_enforce_geography_setting(account_id: str, headers: dict) -> dict:
    """
    Check whether 'Enforce data processing within workspace Geography' is enabled.
    Requires account admin permissions.
    """
    url = f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}/settings/types/shield_csp_enforcement_account_setting/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 403:
        return {
            "error": "403 Forbidden — you need Account Admin role to read this setting.",
            "recommendation": "Ask your Account Admin to verify this is enabled.",
        }
    response.raise_for_status()
    return response.json()


geography_setting = get_enforce_geography_setting(ACCOUNT_ID, HEADERS)
print("=== Enforce Geography Setting ===")
print(json.dumps(geography_setting, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Interpreting the Response
# MAGIC
# MAGIC A compliant response looks like:
# MAGIC
# MAGIC ```json
# MAGIC {
# MAGIC   "setting_name": "default",
# MAGIC   "shield_csp_enforcement_account_setting": {
# MAGIC     "csp": "COMPLIANCE_SECURITY_PROFILE"
# MAGIC   },
# MAGIC   "etag": "..."
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC If the setting is missing or `csp` is absent, escalate to your Databricks
# MAGIC account team immediately — cross-geo data processing may be occurring.

# COMMAND ----------

def compliance_check_geography(setting_response: dict) -> None:
    """Print a pass/fail compliance check for the geography enforcement setting."""
    if "error" in setting_response:
        print(f"[WARN] Could not verify: {setting_response['error']}")
        return

    csp_block = setting_response.get("shield_csp_enforcement_account_setting", {})
    csp_value = csp_block.get("csp", "")

    if csp_value == "COMPLIANCE_SECURITY_PROFILE":
        print("[PASS] Enforce data processing within Geography: ENABLED")
        print("       Regulated workloads are protected from cross-geo routing.")
    else:
        print("[FAIL] Enforce data processing within Geography: NOT ENABLED")
        print("       Action required: enable via Account Console > Settings.")
        print(f"       Current value: '{csp_value}'")


compliance_check_geography(geography_setting)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Unity Catalog Permissions for AI Assets
# MAGIC
# MAGIC AI features in Databricks are governed through Unity Catalog just like any
# MAGIC other data asset. The table below maps asset types to the permissions you
# MAGIC should configure for a typical energy utility:
# MAGIC
# MAGIC | Asset type | Typical GRANT | Typical REVOKE |
# MAGIC |---|---|---|
# MAGIC | Registered model | `EXECUTE` for inference, `APPLY TAG` for governance | `ALL PRIVILEGES` from `account users` |
# MAGIC | Model serving endpoint | `CAN_QUERY` for consumers | `CAN_MANAGE` from non-admins |
# MAGIC | AI Gateway endpoint | `CAN_QUERY` | — |
# MAGIC | Genie Space | `CAN_USE` | `CAN_MANAGE` from non-admins |
# MAGIC | Vector Search index | `SELECT` | — |
# MAGIC | External model | `EXECUTE` | — |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a. Grant permissions on a registered model

# COMMAND ----------

# SOLUTION: Run these SQL statements in a %sql cell or via spark.sql()

# TODO: Replace placeholders with your catalog, schema, model name, and principal
CATALOG_NAME    = "energy_ai"           # TODO: your catalog
SCHEMA_NAME     = "models"              # TODO: your schema
MODEL_NAME      = "meter_anomaly_v1"    # TODO: your model name
CONSUMER_GROUP  = "grp_analysts"        # TODO: group that runs inference
ADMIN_GROUP     = "grp_ai_admins"       # TODO: group that manages models

grant_model_sql = f"""
-- Allow the analyst group to run inference against the model
GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{CONSUMER_GROUP}`;

-- Allow the AI admins group to manage (register new versions, etc.)
GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{ADMIN_GROUP}`;

-- Verify
SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME};
"""

print("SQL to run (copy into a %sql cell or use spark.sql):\n")
print(grant_model_sql)

# COMMAND ----------

# Execute the GRANT statements via spark.sql
# Uncomment the lines below after filling in the TODO variables above.

# spark.sql(f"""
#   GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
#   TO `{CONSUMER_GROUP}`
# """)

# spark.sql(f"""
#   GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
#   TO `{ADMIN_GROUP}`
# """)

# display(spark.sql(f"SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"))

print("Uncomment the spark.sql calls above after updating the TODO variables.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Grant permissions on a model serving endpoint

# COMMAND ----------

# TODO: Fill in your endpoint name
ENDPOINT_NAME = "meter-anomaly-endpoint"  # TODO

grant_endpoint_sql = f"""
-- Allow analysts to query the serving endpoint
GRANT CAN_QUERY ON SERVING ENDPOINT `{ENDPOINT_NAME}`
  TO `{CONSUMER_GROUP}`;

-- Allow AI admins to manage the endpoint (scale, update config)
GRANT CAN_MANAGE ON SERVING ENDPOINT `{ENDPOINT_NAME}`
  TO `{ADMIN_GROUP}`;

-- Verify
SHOW GRANTS ON SERVING ENDPOINT `{ENDPOINT_NAME}`;
"""

print(grant_endpoint_sql)

# COMMAND ----------

# Use the Databricks SDK to set endpoint permissions programmatically
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServingEndpointAccessControlRequest,
    ServingEndpointPermissionLevel,
)

w = WorkspaceClient()  # Reads DATABRICKS_HOST and DATABRICKS_TOKEN from environment

# TODO: Uncomment and run after setting ENDPOINT_NAME above
# w.serving_endpoints.set_permissions(
#     serving_endpoint_id=ENDPOINT_NAME,
#     access_control_list=[
#         ServingEndpointAccessControlRequest(
#             group_name=CONSUMER_GROUP,
#             permission_level=ServingEndpointPermissionLevel.CAN_QUERY,
#         ),
#         ServingEndpointAccessControlRequest(
#             group_name=ADMIN_GROUP,
#             permission_level=ServingEndpointPermissionLevel.CAN_MANAGE,
#         ),
#     ],
# )
# print(f"Permissions set on endpoint: {ENDPOINT_NAME}")

print("SDK permission call is commented out — uncomment after setting variable values.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4c. Grant permissions on a Genie Space
# MAGIC
# MAGIC Genie Spaces are governed through the Databricks Dashboards permission model.
# MAGIC The SDK exposes this via `w.genie`.

# COMMAND ----------

# TODO: Replace with your Genie Space ID
# Found in the Genie Space URL: /genie/spaces/<space-id>
GENIE_SPACE_ID = "<your-genie-space-id>"  # TODO

# Note: Genie Space permissions are managed via the REST permissions API, not a
# dedicated SDK class. Use the endpoint below:
#   GET /api/2.0/permissions/dashboards/{dashboard_id}
# The Genie Space ID in the URL maps to the underlying dashboard ID.
# The SDK currently does not expose a typed GeniePermissionsRequest class.

# TODO: Uncomment after setting GENIE_SPACE_ID
# import requests
# perms_resp = requests.get(
#     f"{WORKSPACE_URL}/api/2.0/permissions/dashboards/{GENIE_SPACE_ID}",
#     headers=HEADERS,
#     timeout=15,
# )
# print(json.dumps(perms_resp.json(), indent=2))

print("Genie permissions call is commented out — uncomment after setting GENIE_SPACE_ID.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Create a Service Principal for AI Workloads
# MAGIC
# MAGIC Automated AI workloads (scheduled inference jobs, embedding pipelines,
# MAGIC regulatory report generation) should run as **service principals** rather
# MAGIC than individual user accounts. This:
# MAGIC
# MAGIC - Prevents breakage when a staff member leaves
# MAGIC - Provides a clean audit trail in `system.access.audit`
# MAGIC - Allows the principle of least privilege

# COMMAND ----------

from databricks.sdk.service.iam import ServicePrincipal

def create_ai_service_principal(w: WorkspaceClient, display_name: str) -> ServicePrincipal:
    """
    Create a service principal for an AI workload.

    Parameters
    ----------
    display_name : str
        Human-readable name, e.g. "svc-meter-inference"
    """
    sp = w.service_principals.create(
        display_name=display_name,
        active=True,
    )
    print(f"Created service principal: {sp.display_name} (ID: {sp.id})")
    return sp


# TODO: Uncomment and customise the service principal name
# sp = create_ai_service_principal(w, "svc-meter-anomaly-inference")

# --- After creating the SP, generate an OAuth secret for it ---
# OAuth secrets live on a separate API — w.service_principal_secrets (not w.service_principals)
# secret = w.service_principal_secrets.create(service_principal_id=sp.id)
# print(f"Client ID    : {sp.application_id}")
# print(f"Client Secret: {secret.secret}  <-- store in Key Vault immediately")

print("Service principal creation is commented out — safe to run in a non-prod workspace.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b. Assign the service principal to groups

# COMMAND ----------

from databricks.sdk.service.iam import Group

def assign_sp_to_group(w: WorkspaceClient, sp_id: int, group_display_name: str) -> None:
    """
    Add a service principal to an existing workspace group.
    """
    # Find the group
    groups = list(w.groups.list(filter=f"displayName eq \"{group_display_name}\""))
    if not groups:
        print(f"Group '{group_display_name}' not found.")
        return

    group = groups[0]
    group_id = group.id

    # Add the SP as a member
    w.groups.patch(
        id=group_id,
        operations=[{
            "op": "add",
            "path": "members",
            "value": [{"value": str(sp_id)}]
        }]
    )
    print(f"Added SP {sp_id} to group '{group_display_name}' (ID: {group_id})")


# TODO: After creating the SP, assign it to the relevant AI admin group
# assign_sp_to_group(w, sp.id, ADMIN_GROUP)

print("SP group assignment is commented out — run after creating the service principal.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Configure Groups for Genie Space Access
# MAGIC
# MAGIC In a regulated utility (e.g. electricity network operator), you will typically
# MAGIC have several distinct business units that need different levels of AI access:
# MAGIC
# MAGIC | Group | Genie access | Model serving | Notes |
# MAGIC |---|---|---|---|
# MAGIC | `grp_network_ops` | Read (meters, asset data) | CAN_QUERY | Day-to-day operations |
# MAGIC | `grp_regulatory` | Read (reports) | None | Regulatory reporting team |
# MAGIC | `grp_ai_admins` | Full | CAN_MANAGE | Data + AI platform team |
# MAGIC | `grp_data_science` | Full (dev workspaces) | CAN_MANAGE | Model builders |

# COMMAND ----------

def list_workspace_groups(w: WorkspaceClient) -> list:
    """Return all groups in the workspace."""
    return list(w.groups.list())


def create_group_if_missing(w: WorkspaceClient, display_name: str) -> Group:
    """Idempotently create a group."""
    existing = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if existing:
        print(f"Group already exists: {display_name} (ID: {existing[0].id})")
        return existing[0]

    group = w.groups.create(display_name=display_name)
    print(f"Created group: {display_name} (ID: {group.id})")
    return group


# Define the groups needed for an energy utility AI rollout
AI_GOVERNANCE_GROUPS = [
    "grp_network_ops",
    "grp_regulatory",
    "grp_ai_admins",
    "grp_data_science",
]

# TODO: Uncomment to create all groups in one pass
# print("Creating AI governance groups...")
# created_groups = {}
# for group_name in AI_GOVERNANCE_GROUPS:
#     g = create_group_if_missing(w, group_name)
#     created_groups[group_name] = g

# print("\nAll groups ready:")
# for name, g in created_groups.items():
#     print(f"  {name}: ID={g.id}")

print("Group creation loop is commented out — safe to run in any workspace.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6b. List current group memberships

# COMMAND ----------

def show_group_members(w: WorkspaceClient, group_display_name: str) -> None:
    """Print members of a group including service principals."""
    groups = list(w.groups.list(filter=f"displayName eq \"{group_display_name}\""))
    if not groups:
        print(f"Group '{group_display_name}' not found.")
        return

    group = w.groups.get(id=groups[0].id)
    members = group.members or []

    print(f"\nGroup: {group_display_name} ({len(members)} members)")
    print("-" * 50)
    for m in members:
        print(f"  {m.display} (ref: {m.ref})")


# TODO: Replace with a group that exists in your workspace
# show_group_members(w, "grp_ai_admins")

# --- Alternatively, list ALL groups ---
# all_groups = list_workspace_groups(w)
# print(f"Total workspace groups: {len(all_groups)}")
# for g in all_groups[:20]:  # first 20
#     print(f"  {g.display_name} (ID: {g.id})")

print("Group listing is commented out — safe to uncomment and run.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Lab Summary & Checkpoint
# MAGIC
# MAGIC Run the cell below to print a summary of what was verified in this lab.

# COMMAND ----------

print("=" * 60)
print("Lab 01 — Checkpoint Summary")
print("=" * 60)

checks = [
    ("Workspace AI settings queried via REST API", True),
    ("Genie Space toggle reviewed", True),
    ("Geography enforcement setting checked", True),
    ("UC GRANT SQL statements reviewed for models", True),
    ("UC GRANT SQL statements reviewed for endpoints", True),
    ("Service principal creation pattern reviewed", True),
    ("Group structure for energy utility documented", True),
]

for description, done in checks:
    status = "[DONE]" if done else "[TODO]"
    print(f"  {status}  {description}")

print()
print("Next lab: 02_ai_gateway_setup.py")
print("Topic   : Creating AI Gateway endpoints with rate limits and guardrails")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC ## Reference: Full REST API Cheat Sheet
# MAGIC
# MAGIC | Operation | Method | Endpoint |
# MAGIC |---|---|---|
# MAGIC | Get typed workspace setting | GET | `/api/2.0/settings/types/{type}/names/default` |
# MAGIC | Update typed workspace setting | PATCH | `/api/2.0/settings/types/{type}/names/default` |
# MAGIC | Get legacy workspace conf keys | GET | `/api/2.0/workspace-conf?keys=key1,key2` |
# MAGIC | Update legacy workspace conf keys | PATCH | `/api/2.0/workspace-conf` (JSON body) |
# MAGIC | Get account geography setting | GET | `accounts.azuredatabricks.net/api/2.0/accounts/{id}/settings/types/shield_csp_enforcement_account_setting/names/default` |
# MAGIC | List serving endpoints | GET | `/api/2.0/serving-endpoints` |
# MAGIC | Get endpoint permissions | GET | `/api/2.0/permissions/serving-endpoints/{name}` |
# MAGIC | List groups | GET | `/api/2.0/preview/scim/v2/Groups` |
# MAGIC | Create service principal | POST | `/api/2.0/preview/scim/v2/ServicePrincipals` |
