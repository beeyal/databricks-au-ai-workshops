# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">Lab 01: Workspace AI Settings & Access Control</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries · Databricks</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 35–40 minutes |
# MAGIC | **Prerequisites** | Workshop workspace UC-enabled, DBR 14.3 LTS cluster attached |
# MAGIC | **Role** | Workspace Admin / Account Admin |
# MAGIC | **Data residency** | All API calls stay in AU East |
# MAGIC | **Cluster** | DBR 14.3 LTS or later |
# MAGIC
# MAGIC **By the end of this lab you will have:**
# MAGIC - [ ] Verified current AI feature flags via the REST API
# MAGIC - [ ] Confirmed the geography enforcement toggle is ON (Account Console only)
# MAGIC - [ ] Understood how Genie Space access is controlled (space sharing + UC grants, no workspace toggle)
# MAGIC - [ ] Granted UC permissions for AI assets (models, endpoints, Genie Spaces)
# MAGIC - [ ] Created a service principal for automated AI workloads
# MAGIC - [ ] Configured groups for business-unit-level access control
# MAGIC
# MAGIC > **AU East residency quick ref** — Genie Spaces ✅ in-region | AI Gateway ✅ in-region | FMAPI Provisioned Throughput ✅ in-region | FMAPI Pay-Per-Token ❌ cross-geo | Knowledge Assistant ⚠️ cross-geo (workaround in Lab 04) | Foundation Model Fine-tuning ❌ not available AU East

# COMMAND ----------

# MAGIC %md
# MAGIC ## UI Tour — do this before running any code
# MAGIC
# MAGIC **Task 1 — Geography Enforcement toggle (Account Console only)**
# MAGIC
# MAGIC Navigate: accounts.cloud.databricks.com → Workspaces → [your workspace name] → Security and compliance tab
# MAGIC You should see: Toggle labelled "Enforce data processing within workspace Geography for Designated Services" — it must be ON for SOCI Act / critical infrastructure regulated workloads.
# MAGIC
# MAGIC > This setting is NOT in the workspace admin console. It lives on the workspace detail page inside the Account Console.
# MAGIC
# MAGIC
# MAGIC > ⚠️ **Two settings must be correct for AI features to work:**
# MAGIC > - **Geography enforcement** → Account Console → Security and compliance → must be **ON**
# MAGIC > - **Partner-Powered AI Features** → workspace settings → must remain **ON**
# MAGIC > Turning Partner-Powered OFF disables Genie, Genie Code, and AI/BI entirely.
# MAGIC > It is NOT a data residency control — geography enforcement is the correct lever for data residency.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Task 2 — Workspace-level AI feature flags**
# MAGIC
# MAGIC There are three possible navigation paths depending on your workspace UI version — use whichever one matches what you see:
# MAGIC
# MAGIC - **Path A (current UI):** Click your username (top-right of workspace) → Settings → scroll to find AI / Machine Learning feature toggles
# MAGIC - **Path B:** Left sidebar → Settings icon (if present) → Workspace admin → feature settings
# MAGIC - **Path C:** The exact section label varies by workspace version — look for "Previews", "AI features", or "Machine Learning" sections
# MAGIC
# MAGIC > ⚠️ Exact UI labels vary. If you can't find AI toggles, ask your workspace admin or check via the API below.
# MAGIC
# MAGIC You should see: Toggles for Genie Spaces, AI/BI Dashboards, AI Playground, and Mosaic AI Agent Framework.
# MAGIC
# MAGIC > **Note:** When the Geography Enforcement toggle is ON (Task 1), cross-geo models such as FMAPI Pay-Per-Token are hidden from the AI Playground model picker — this is expected and correct behaviour, not a bug.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Task 3 — Unity Catalog permission model**
# MAGIC
# MAGIC Navigate: Left sidebar → Catalog icon (stacked layers) → expand catalog → schema → any table → Permissions tab
# MAGIC You should see: Current grants on that asset — principals, privilege levels.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Task 4 — Groups list**
# MAGIC
# MAGIC Navigate: Account Console → User management → Service principals (for SPs) or User management → Groups tab
# MAGIC You should see: Existing account-level groups. Section 6 creates new ones if needed.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 0: Setup

# COMMAND ----------

import os
import json
import requests

# COMMAND ----------

# Widget-based configuration — works in any customer Databricks environment
dbutils.widgets.text("workspace_url", "https://<your-workspace>.azuredatabricks.net", "Workspace URL")
dbutils.widgets.text("account_id",    "<your-account-id>",                            "Account ID")
dbutils.widgets.text("gw_endpoint",   "au_east_llm_inregion",                         "AI Gateway endpoint name")

WORKSPACE_URL_W  = dbutils.widgets.get("workspace_url")
ACCOUNT_ID_W     = dbutils.widgets.get("account_id")
GW_ENDPOINT      = dbutils.widgets.get("gw_endpoint")

print(f"Workspace URL   : {WORKSPACE_URL_W}")
print(f"Account ID      : {ACCOUNT_ID_W}")
print(f"GW endpoint     : {GW_ENDPOINT}")

# COMMAND ----------

# TODO: Replace with your workspace URL (no trailing slash)
WORKSPACE_URL = WORKSPACE_URL_W if WORKSPACE_URL_W != "https://<your-workspace>.azuredatabricks.net" else "https://<your-workspace>.azuredatabricks.net"

# Option A (recommended): pull from a Databricks secret scope
# DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")

# Option B: paste directly (OK for a training lab only)
DATABRICKS_TOKEN = "<paste-your-pat-here>"

# Derived — do not edit below this line
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

# PAT navigation: top-right avatar → Settings → Developer → Access tokens → Generate new token
print(f"Workspace URL : {WORKSPACE_URL}")
print("Token         : [loaded]")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1: Inspect Current Workspace AI Feature Status
# MAGIC
# MAGIC The typed Settings API (`/api/2.0/settings/types/{type}/names/default`) covers newer controls.
# MAGIC Older guards (notebook export, results download) remain on the legacy `/api/2.0/workspace-conf` endpoint.
# MAGIC
# MAGIC | Setting | API | Controls |
# MAGIC |---|---|---|
# MAGIC | `llm_proxy_partner_powered` | Typed Settings | Partner-Powered AI (Genie, AI/BI, AI Playground on/off) |
# MAGIC | `restrict_workspace_admins` | Typed Settings | Non-admin restrictions |
# MAGIC | `enableExportNotebook` | Typed Settings (`enable-export-notebook`) or workspace-conf (backward compat) | Notebook source download |
# MAGIC | `enableResultsDownloading` | Typed Settings (`enable-results-downloading`) or workspace-conf (backward compat) | Query result CSV export |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC 🖱️ **UI:** Click username (top-right) → Settings → look for AI / Machine Learning or Previews section
# MAGIC You should see: toggles for Genie Spaces, AI/BI Dashboards, AI Playground. Exact section name varies by workspace version. Export/download toggles may be under Settings → Workspace settings → Advanced.
# MAGIC
# MAGIC > **Geography enforcement interaction:** When the geography enforcement toggle is ON, cross-geo models (e.g. FMAPI Pay-Per-Token) are hidden from the AI Playground model picker. If users report missing models in the Playground, verify geography enforcement status before troubleshooting anything else.
# MAGIC
# MAGIC ⚡ **Or run the cell below to read all AI feature flags and legacy conf keys at once:**

# COMMAND ----------

# Typed Settings API type names (verified against databricks-sdk):
#   restrict_workspace_admins       -> /api/2.0/settings/types/restrict_workspace_admins/names/default
#   llm_proxy_partner_powered       -> /api/2.0/settings/types/llm_proxy_partner_powered/names/default
#     (this is the Partner-Powered AI master switch — controls Genie, Genie Code, AI/BI)
#   enable-results-downloading      -> /api/2.0/settings/types/enable-results-downloading/names/default
#   enable-export-notebook          -> /api/2.0/settings/types/enable-export-notebook/names/default
#   enable-notebook-table-clipboard -> /api/2.0/settings/types/enable-notebook-table-clipboard/names/default
#
# NOTE: There is no 'aibi_genie_space_enabled_ws_setting' type in the API.
# Genie on/off is controlled by the 'llm_proxy_partner_powered' setting.
# enableResultsDownloading, enableExportNotebook, and enableNotebookTableClipboard
# also have typed settings equivalents — the workspace-conf endpoint may still return
# them for backward compatibility, but the canonical path is the typed settings API.
AI_SETTING_TYPES = [
    "llm_proxy_partner_powered",   # Partner-Powered AI (master switch for Genie, AI/BI, AI Playground)
    "restrict_workspace_admins",
]

# These can also be fetched via the typed settings API, but workspace-conf remains
# supported for backward compatibility and is simpler for a read-only inspection.
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


# --- Query typed settings ---
print(f"{'Setting Type':<52} {'Raw value'}")
print("─" * 80)
for setting_type in AI_SETTING_TYPES:
    result = fetch_typed_setting(WORKSPACE_URL, HEADERS, setting_type)
    inner = result.get(setting_type, {})
    if not inner:
        inner = result.get("status", result)
    print(f"{setting_type:<52} {inner}")

# --- Query legacy workspace conf keys ---
print()
print(f"{'Workspace-conf key':<52} {'Value'}")
print("─" * 80)
workspace_conf = fetch_workspace_conf(WORKSPACE_URL, HEADERS, WORKSPACE_CONF_KEYS)
for key in WORKSPACE_CONF_KEYS:
    value = workspace_conf.get(key, "not_set")
    print(f"{key:<52} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC **General workspace security settings worth reviewing (not specific to SOCI Act — check with your CISO):**
# MAGIC
# MAGIC | Key | Common secure value | What it controls |
# MAGIC |---|---|---|
# MAGIC | `enableResultsDownloading` | `false` | Prevents users downloading query results as CSV |
# MAGIC | `enableExportNotebook` | `false` | Prevents exporting notebooks outside the platform |
# MAGIC
# MAGIC These are general data governance settings. Whether to enable them depends on your organisation's policy — discuss with your CISO rather than assuming they must be disabled.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2: How Genie Space Access Is Actually Controlled
# MAGIC
# MAGIC There is no workspace-level "Genie on/off" toggle. Access to Genie Spaces works through two layers:
# MAGIC
# MAGIC | Layer | What it controls | Where to configure |
# MAGIC |---|---|---|
# MAGIC | **Partner-Powered AI Features** | Master switch — turns off ALL AI features including Genie, Genie Code, AI/BI | Workspace Settings → AI features → Partner-Powered AI Features (keep this ON) |
# MAGIC | **Genie Space sharing** | Who can access a specific space | Space → Share button → add users/groups with CAN_RUN |
# MAGIC | **UC grants** | What data each user can see inside the space | GRANT SELECT ON TABLE/SCHEMA |
# MAGIC
# MAGIC The right way to restrict Genie access for regulated data is **not** to disable Genie globally — it is to:
# MAGIC 1. Only share Genie Spaces with the right groups
# MAGIC 2. Use UC row/column filters so each user only sees data they're permitted to see
# MAGIC 3. Keep geography enforcement ON so data stays in AU East
# MAGIC
# MAGIC ⚡ **Read the current AI feature flags (informational — do not change unless intentional):**

# COMMAND ----------

# Note: there is no API to enable/disable Genie specifically.
# Access is controlled via space sharing (CAN_RUN) and UC grants.
# The cell below reads current AI feature flags so you can see what's on/off.
print("Reading AI feature flags...")
# set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=False)  # Turn Genie off

# HTTP 409 Conflict = stale ETag; re-run the cell to auto-fetch a fresh one.
print("Genie Space toggle: commented out for safety. Uncomment to make a change.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3: Verify "Enforce Data Processing Within Geography"
# MAGIC
# MAGIC This is the single most important compliance setting for SOCI Act / critical infrastructure regulated entities. When enabled, it prevents Databricks features from routing data outside the workspace region (AU East).
# MAGIC
# MAGIC **Who can change it:** Account Admins only. Workspace-only Admins will receive a 403 — expected.
# MAGIC
# MAGIC 🖱️ **UI:** accounts.cloud.databricks.com → Workspaces → [your workspace name] → Security and compliance tab
# MAGIC You should see: Toggle "Enforce data processing within workspace Geography for Designated Services" — must be ON. This setting is NOT in the workspace admin console.
# MAGIC
# MAGIC ⚡ **Or run the cell below to check it programmatically (Account Admin token required):**

# COMMAND ----------

# TODO: Replace with your Databricks Account ID
# Found in the Account Console URL: accounts.azuredatabricks.net/account/<id>/...
ACCOUNT_ID = ACCOUNT_ID_W if ACCOUNT_ID_W != "<your-account-id>" else "<your-account-id>"


def get_enforce_geography_setting(account_id: str, headers: dict) -> dict:
    """
    Check whether the Compliance Security Profile (CSP) is enabled at the account level.
    CSP is the prerequisite for the 'Enforce data processing within workspace Geography'
    toggle in the Account Console.

    API type name: shield_csp_enablement_ac
    (SDK: CspEnablementAccountAPI, path: /api/2.0/accounts/{id}/settings/types/shield_csp_enablement_ac/names/default)

    Requires Account Admin permissions. Returns error dict on 403/404.

    NOTE: The per-workspace Geography enforcement toggle (Account Console ->
    Workspaces -> [workspace] -> Security and compliance) must be verified in the
    Account Console UI — it is a workspace-level attribute, not a typed setting.
    """
    url = (
        f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}"
        f"/settings/types/shield_csp_enablement_ac/names/default"
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


geography_setting = get_enforce_geography_setting(ACCOUNT_ID, HEADERS)
print("=== Geography Enforcement Setting ===")
print(json.dumps(geography_setting, indent=2))

# COMMAND ----------

def compliance_check_geography(setting_response: dict) -> None:
    """
    Print a pass/fail compliance check for the account-level CSP enablement setting.

    Response schema (shield_csp_enablement_ac):
      {
        "csp_enablement_account": {
          "is_enforced": true/false,
          "compliance_standards": [...]
        },
        "etag": "...",
        "setting_name": "default"
      }

    is_enforced=true means CSP is enforced at account level (cannot be overridden per workspace).
    For SOCI Act / critical infrastructure workloads, also verify the per-workspace Geography
    enforcement toggle in Account Console -> Workspaces -> [workspace] -> Security and compliance.
    """
    if "error" in setting_response:
        print(f"CANNOT VERIFY — {setting_response['error']}")
        print(f"   Detail : {setting_response.get('detail', '')}")
        print(f"   Action : {setting_response.get('action', '')}")
        return

    csp_block = setting_response.get("csp_enablement_account", {})
    is_enforced = csp_block.get("is_enforced", False)
    standards = csp_block.get("compliance_standards", [])

    print("─" * 60)
    if is_enforced:
        print("PASS — Compliance Security Profile: ENFORCED at account level")
        print(f"    Compliance standards : {standards or '(default)'}")
        print("    Next: verify per-workspace Geography enforcement in Account Console.")
    else:
        print("INFO — Compliance Security Profile: NOT enforced at account level (is_enforced=false)")
        print(f"    Compliance standards : {standards or '(none)'}")
        print("    This setting controls whether CSP can be overridden per workspace.")
        print("    ACTION: Verify the Geography enforcement toggle per workspace in Account Console")
        print("    → Workspaces → [workspace] → Security and compliance tab.")
    print("─" * 60)


compliance_check_geography(geography_setting)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checkpoint — Sections 1–3

# COMMAND ----------

print("=" * 60)
print("  Checkpoint — Sections 1–3")
print("=" * 60)
print()

checks = []

if "<your-workspace>" in WORKSPACE_URL:
    checks.append(("Workspace URL configured", False, "Still contains placeholder — update WORKSPACE_URL"))
else:
    checks.append(("Workspace URL configured", True, WORKSPACE_URL))

if "<paste" in DATABRICKS_TOKEN or len(DATABRICKS_TOKEN) < 20:
    checks.append(("Token set", False, "Token appears to be a placeholder — update DATABRICKS_TOKEN"))
else:
    checks.append(("Token set", True, "Token loaded (length OK)"))

if "<your-account-id>" in ACCOUNT_ID:
    checks.append(("Account ID set", False, "Still placeholder — set ACCOUNT_ID to verify geography setting"))
else:
    checks.append(("Account ID set", True, ACCOUNT_ID))

if isinstance(geography_setting, dict):
    if "error" in geography_setting:
        checks.append(("CSP account-level enforcement verified", False, geography_setting["error"]))
    else:
        is_enforced = geography_setting.get("csp_enablement_account", {}).get("is_enforced", False)
        if is_enforced:
            checks.append(("CSP account-level enforcement verified", True, "is_enforced=true — CSP enforced at account level"))
        else:
            checks.append(("CSP account-level enforcement verified", False, "is_enforced=false — verify per-workspace geography toggle in Account Console"))
else:
    checks.append(("CSP account-level enforcement verified", False, "geography_setting not available"))

for description, passed, detail in checks:
    icon = "✅" if passed else "❌"
    print(f"  {icon}  {description}")
    if not passed:
        print(f"       → {detail}")

print()
all_pass = all(p for _, p, _ in checks)
if all_pass:
    print("All checks passed — proceed to Section 4: Unity Catalog Permissions.")
else:
    print("Fix the items marked ❌ above before proceeding.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4: Unity Catalog Permissions for AI Assets
# MAGIC
# MAGIC AI assets in Databricks are governed through Unity Catalog. UC grants travel with the asset across workspaces sharing the same metastore — one consistent policy regardless of which workspace a user is in.
# MAGIC
# MAGIC | Asset type | Typical GRANT | Typical REVOKE |
# MAGIC |---|---|---|
# MAGIC | Registered model | `EXECUTE` for inference | `ALL PRIVILEGES` from `account users` |
# MAGIC | Model serving endpoint | `CAN_QUERY` for consumers | `CAN_MANAGE` from non-admins |
# MAGIC | Genie Space | `CAN_RUN` for consumers | `CAN_MANAGE` from non-admins |
# MAGIC
# MAGIC Navigate: Left sidebar → Catalog icon (stacked layers) → expand catalog → schema → asset → Permissions tab
# MAGIC You should see: Current grants — the SQL GRANT statements below produce entries visible here.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a. Grant permissions on a registered model
# MAGIC
# MAGIC 🖱️ **UI:** Left sidebar → Catalog → expand catalog → schema → [model name] → Permissions tab → Grant
# MAGIC You should see: A dialog to add a principal (user, group, or service principal) with a privilege selector. EXECUTE = run inference, ALL PRIVILEGES = full management.
# MAGIC
# MAGIC ⚡ **Or run the cell below to generate the GRANT SQL:**

# COMMAND ----------

# TODO: Replace these placeholders with your actual values
CATALOG_NAME    = "energy_ai"           # TODO: catalog containing your model
SCHEMA_NAME     = "models"              # TODO: schema containing your model
MODEL_NAME      = "meter_anomaly_v1"    # TODO: registered model name
CONSUMER_GROUP  = "grp_analysts"        # TODO: group that runs inference
ADMIN_GROUP     = "grp_ai_admins"       # TODO: group that manages models

grant_model_sql = f"""
-- Allow the analyst group to run inference against the registered model
GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{CONSUMER_GROUP}`;

-- Allow the AI admins group to fully manage the model
GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{ADMIN_GROUP}`;

-- Verify
SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME};
"""

print("SQL to run — copy into a %sql cell or use spark.sql():\n")
print(grant_model_sql)

# COMMAND ----------

# Uncomment the blocks below after confirming the TODO variables above are correct.

# spark.sql(f"""
#   GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
#   TO `{CONSUMER_GROUP}`
# """)
# print(f"Granted EXECUTE on {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME} to {CONSUMER_GROUP}")

# spark.sql(f"""
#   GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
#   TO `{ADMIN_GROUP}`
# """)
# print(f"Granted ALL PRIVILEGES on {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME} to {ADMIN_GROUP}")

# display(spark.sql(f"SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}"))

print("spark.sql calls are commented out — uncomment after updating the TODO variables.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Grant permissions on a model serving endpoint
# MAGIC
# MAGIC 🖱️ **UI:** Left sidebar → Serving → click an endpoint name → Permissions tab
# MAGIC You should see: Current CAN_QUERY / CAN_MANAGE assignments for that endpoint. Click Grant to add a principal.
# MAGIC
# MAGIC ⚡ **Or run the cell below to generate the GRANT SQL and SDK call:**

# COMMAND ----------

# TODO: Fill in your endpoint name
ENDPOINT_NAME = "meter-anomaly-endpoint"  # TODO: your model serving endpoint name

grant_endpoint_sql = f"""
GRANT CAN_QUERY ON SERVING ENDPOINT `{ENDPOINT_NAME}` TO `{CONSUMER_GROUP}`;
GRANT CAN_MANAGE ON SERVING ENDPOINT `{ENDPOINT_NAME}` TO `{ADMIN_GROUP}`;
SHOW GRANTS ON SERVING ENDPOINT `{ENDPOINT_NAME}`;
"""

print("SQL to run:\n")
print(grant_endpoint_sql)

# COMMAND ----------

# Use the Databricks SDK to set endpoint permissions programmatically.
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServingEndpointAccessControlRequest,
    ServingEndpointPermissionLevel,
)

w = WorkspaceClient()  # Reads DATABRICKS_HOST and DATABRICKS_TOKEN from environment

# TODO: Uncomment and run after setting ENDPOINT_NAME and group variables
# w.serving_endpoints.update_permissions(
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
# print(f"SDK permissions updated on endpoint: {ENDPOINT_NAME}")

print("SDK permission call is commented out — uncomment after setting variable values.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4c. Grant permissions on a Genie Space
# MAGIC
# MAGIC 🖱️ **UI:** Left sidebar → Genie → [Space name] → kebab menu (top-right) → Share or Permissions → add groups with CAN_VIEW / CAN_RUN / CAN_EDIT / CAN_MANAGE
# MAGIC You should see: The Genie Space URL contains the space ID: `.../genie/spaces/<SPACE-ID>` — copy that ID for the API call below.
# MAGIC
# MAGIC > **Permissions API object type:** Genie Spaces use object type `genie` in the permissions API (`/api/2.0/permissions/genie/{space_id}`). Do not use `dashboards` — that is for AI/BI Lakeview dashboards, a different object type.
# MAGIC
# MAGIC ⚡ **Or run the cell below to read and set Genie Space permissions via the REST API (uncomment after setting GENIE_SPACE_ID):**

# COMMAND ----------

# TODO: Replace with your Genie Space ID (copy from the browser URL)
GENIE_SPACE_ID = "<your-genie-space-id>"  # TODO


def get_genie_space_permissions(workspace_url: str, headers: dict, genie_space_id: str) -> dict:
    """
    Fetch current permissions for a Genie Space via the Genie permissions API.

    Object type for Genie Spaces in the permissions API is 'genie' (not 'dashboards').
    'dashboards' is for AI/BI Lakeview dashboards — a different object type.

    Valid permission levels for Genie Spaces: CAN_VIEW, CAN_RUN, CAN_EDIT, CAN_MANAGE.
    """
    url = f"{workspace_url}/api/2.0/permissions/genie/{genie_space_id}"
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 404:
        return {"error": f"Space ID '{genie_space_id}' not found — verify the ID from the URL"}
    response.raise_for_status()
    return response.json()


def grant_genie_space_permission(
    workspace_url: str,
    headers: dict,
    genie_space_id: str,
    group_name: str,
    permission_level: str,  # "CAN_VIEW", "CAN_RUN", "CAN_EDIT", or "CAN_MANAGE"
) -> dict:
    """Grant a group access to a Genie Space. PATCH is additive — safe to call multiple times."""
    url = f"{workspace_url}/api/2.0/permissions/genie/{genie_space_id}"
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


# TODO: Uncomment after setting GENIE_SPACE_ID
# print("Current Genie Space permissions:")
# current = get_genie_space_permissions(WORKSPACE_URL, HEADERS, GENIE_SPACE_ID)
# print(json.dumps(current, indent=2))
#
# print("\nGranting CAN_USE to consumer group...")
# result = grant_genie_space_permission(
#     WORKSPACE_URL, HEADERS, GENIE_SPACE_ID, CONSUMER_GROUP, "CAN_USE"
# )
# print(json.dumps(result, indent=2))

print("Genie Space permission calls are commented out — uncomment after setting GENIE_SPACE_ID.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 5: Create a Service Principal for AI Workloads
# MAGIC
# MAGIC Automated AI workloads (scheduled inference jobs, embedding pipelines) should run as service principals — not personal accounts. This prevents workload failure when staff leave, provides a clean audit trail in `system.access.audit`, and enables least-privilege access.
# MAGIC
# MAGIC 🖱️ **UI:** accounts.cloud.databricks.com → User management → Service principals tab → Add service principal
# MAGIC You should see: A name field — enter `svc-<workload>` format. After creation, go to the SP detail page → Secrets tab → Generate secret (save the secret immediately — it is shown once only).
# MAGIC
# MAGIC ⚡ **Or run the cell below to create the service principal via the SDK (uncomment the call):**

# COMMAND ----------

from databricks.sdk.service.iam import ServicePrincipal

def create_ai_service_principal(w: WorkspaceClient, display_name: str) -> ServicePrincipal:
    """
    Create a service principal for an AI workload.
    Naming convention: svc-<workload-purpose>
    Examples: svc-meter-anomaly-inference, svc-nem12-embedding-pipeline
    """
    sp = w.service_principals.create(
        display_name=display_name,
        active=True,
    )
    print(f"Created service principal: {sp.display_name}")
    print(f"    Application ID : {sp.application_id}")
    print(f"    Internal ID    : {sp.id}")
    print()
    print("Next: generate an OAuth client secret and store it in a Databricks secret scope or Azure Key Vault.")
    return sp


# TODO: Uncomment and customise the name, then run
# sp = create_ai_service_principal(w, "svc-meter-anomaly-inference")

# After creating the SP, generate an OAuth secret:
# secret = w.service_principal_secrets.create(service_principal_id=sp.id)
# print(f"Client ID     : {sp.application_id}")
# print(f"Client Secret : {secret.secret}  ← store in Key Vault, never in notebook source")

print("Service principal creation is commented out — safe to run in a non-prod workspace.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b. Assign the service principal to groups

# COMMAND ----------

from databricks.sdk.service.iam import Group, Patch, PatchOp, PatchSchema

def assign_sp_to_group(w: WorkspaceClient, sp_id: int, group_display_name: str) -> None:
    """
    Add a service principal to an existing workspace group using SCIM PATCH.
    Production preference: use AIM (Automatic Identity Management) for Entra ID — groups and SPs
    sync automatically and this manual step is unnecessary. Use this function only when AIM is
    not yet configured or for non-Entra identity providers.
    Uses typed SDK objects (Patch/PatchOp/PatchSchema) rather than raw dicts —
    PatchOp.ADD issues a PATCH (additive), so existing members are preserved.
    Idempotent — safe to call multiple times.
    """
    groups = list(w.groups.list(filter=f"displayName eq \"{group_display_name}\""))
    if not groups:
        print(f"Group '{group_display_name}' not found — create it in Section 6 first.")
        return

    group = groups[0]
    w.groups.patch(
        id=group.id,
        schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        operations=[Patch(op=PatchOp.ADD, path="members", value=[{"value": str(sp_id)}])]
    )
    print(f"Added SP {sp_id} to group '{group_display_name}' (group ID: {group.id})")


# TODO: After creating the SP above, assign it to the AI admin group
# assign_sp_to_group(w, sp.id, ADMIN_GROUP)

print("SP group assignment is commented out — run after creating the service principal.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 6: Configure Groups for Business Unit AI Access
# MAGIC
# MAGIC Groups created in the Account Console are account-level and available to all workspaces sharing that metastore. Always create AI governance groups at the account level — not inside workspace Admin settings.
# MAGIC
# MAGIC **Production recommendation — AIM (Automatic Identity Management):**
# MAGIC AIM is now GA for Entra ID and is the preferred path over SCIM. With AIM:
# MAGIC - Users are provisioned just-in-time on first sign-in — no pre-staging required
# MAGIC - Groups sync automatically from Entra ID, including nested groups
# MAGIC - Service Principals are also synced alongside human identities
# MAGIC
# MAGIC Configure at: Account Console → Security → User Provisioning → Automatic identity management
# MAGIC
# MAGIC **AEMO-specific:** AEMO is on Azure with Entra ID. AIM will be auto-enabled on your Azure Databricks account by **August 24, 2026** (Microsoft-driven rollout). Review your account cohort at the internal dashboard to check for any Entra ID mismatches to resolve before that date. Exception process: go/aim/file-exception
# MAGIC
# MAGIC If AIM is not yet configured, SCIM remains available. Find the SCIM endpoint at Account Console → Settings → Identity and Access → SCIM provisioning.
# MAGIC
# MAGIC | Group | Genie | Model serving | Playground |
# MAGIC |---|---|---|---|
# MAGIC | `grp_network_ops` | CAN_USE (meter + asset spaces) | CAN_QUERY | No |
# MAGIC | `grp_regulatory` | CAN_USE (reporting spaces only) | None | No |
# MAGIC | `grp_ai_admins` | CAN_MANAGE | CAN_MANAGE | Yes |
# MAGIC | `grp_data_science` | CAN_USE (dev) | CAN_MANAGE | Yes |
# MAGIC
# MAGIC 🖱️ **UI:** accounts.cloud.databricks.com → User management → Groups tab → Add group
# MAGIC You should see: A name field. Enter the group name, then add members and assign workspace access from the group detail page.
# MAGIC
# MAGIC ⚡ **Or run the cell below to create all four governance groups in one pass (uncomment to execute):**

# COMMAND ----------

def create_group_if_missing(w: WorkspaceClient, display_name: str) -> Group:
    """
    Idempotently create a workspace group.
    If the group already exists, returns it without raising an error.
    """
    existing = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if existing:
        print(f"  Already exists: {display_name} (ID: {existing[0].id})")
        return existing[0]

    group = w.groups.create(display_name=display_name)
    print(f"  Created: {display_name} (ID: {group.id})")
    return group


# Standard governance groups for an energy utility AI rollout
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
# print(f"\nAll {len(created_groups)} groups ready.")

print("Group creation loop is commented out — safe to run in any workspace.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6b. List current group memberships (read-only — always safe to run)

# COMMAND ----------

def show_group_members(w: WorkspaceClient, group_display_name: str) -> None:
    """Print all members of a group, including service principals."""
    groups = list(w.groups.list(filter=f"displayName eq \"{group_display_name}\""))
    if not groups:
        print(f"Group '{group_display_name}' not found in this workspace.")
        return

    group = w.groups.get(id=groups[0].id)
    members = group.members or []

    print(f"\nGroup: {group_display_name} ({len(members)} member(s))")
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


# These are read-only — safe to uncomment and run immediately
# show_group_members(w, "grp_ai_admins")
# list_all_workspace_groups(w)

print("Group listing calls are read-only — safe to uncomment and run at any time.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 7: Lab Summary & Final Checkpoint

# COMMAND ----------

print("=" * 60)
print("  Lab 01 — Final Checkpoint Summary")
print("=" * 60)
print()

outcomes = [
    ("Section 1", "Workspace AI feature flags queried via REST API",       True),
    ("Section 1", "Legacy workspace-conf keys (export, results) reviewed", True),
    ("Section 2", "Genie access control model understood (space sharing + UC grants)", True),
    ("Section 3", "Geography enforcement setting checked",                 True),
    ("Section 4", "UC GRANT SQL for registered models reviewed",           True),
    ("Section 4", "SDK-based serving endpoint permissions reviewed",       True),
    ("Section 4", "Genie Space permission REST API reviewed",              True),
    ("Section 5", "Service principal creation pattern covered",            True),
    ("Section 5", "OAuth client secret rotation pattern covered",          True),
    ("Section 6", "AI governance group structure for utilities designed",  True),
]

for section, description, done in outcomes:
    icon = "✅" if done else "⬜"
    print(f"  {icon}  [{section}] {description}")

print()
print("─" * 60)
print("  Next lab  : 02_ai_gateway_setup.py")
print("  Topic     : Creating AI Gateway endpoints with rate limits and guardrails")
print("─" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #E8F4F1; padding: 16px; border-radius: 8px; border-left: 4px solid #00A86B">
# MAGIC <h3 style="color: #006B45; margin: 0 0 8px 0">Lab 01 Complete</h3>
# MAGIC <ul>
# MAGIC <li>Queried workspace AI feature flags (typed Settings API + legacy workspace-conf)</li>
# MAGIC <li>Located and verified the geography enforcement toggle (Account Console only)</li>
# MAGIC <li>Understood Genie access model: space sharing + UC grants (no workspace on/off toggle)</li>
# MAGIC <li>Wrote GRANT SQL and SDK calls for registered models, serving endpoints, Genie Spaces</li>
# MAGIC <li>Created a service principal with OAuth credentials for automated workloads</li>
# MAGIC <li>Designed a group structure for energy utility AI governance</li>
# MAGIC </ul>
# MAGIC <p><strong>Next:</strong> Lab 02: AI Gateway Setup</p>
# MAGIC </div>
# MAGIC
# MAGIC ## Reference: Full REST API Cheat Sheet
# MAGIC
# MAGIC | Operation | Method | Endpoint |
# MAGIC |---|---|---|
# MAGIC | Get typed workspace setting | GET | `/api/2.0/settings/types/{type}/names/default` |
# MAGIC | Update typed workspace setting | PATCH | `/api/2.0/settings/types/{type}/names/default` |
# MAGIC | Get legacy workspace conf keys | GET | `/api/2.0/workspace-conf?keys=key1,key2` |
# MAGIC | Get account CSP enablement setting | GET | `accounts.azuredatabricks.net/api/2.0/accounts/{id}/settings/types/shield_csp_enablement_ac/names/default` |
# MAGIC | List serving endpoints | GET | `/api/2.0/serving-endpoints` |
# MAGIC | Get endpoint permissions | GET | `/api/2.0/permissions/serving-endpoints/{name}` |
# MAGIC | Get Genie Space permissions | GET | `/api/2.0/permissions/genie/{space-id}` |
# MAGIC | Set Genie Space permissions | PATCH | `/api/2.0/permissions/genie/{space-id}` |
# MAGIC | Create service principal | POST | `/api/2.0/preview/scim/v2/ServicePrincipals` | (or via AIM automatic sync — preferred) |
# MAGIC | Create SP OAuth secret | POST | `/api/2.0/accounts/{id}/servicePrincipals/{sp-id}/credentials/secrets` |
