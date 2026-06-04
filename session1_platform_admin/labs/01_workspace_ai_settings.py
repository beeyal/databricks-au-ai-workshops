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
# MAGIC ---
# MAGIC
# MAGIC ## The Problem
# MAGIC
# MAGIC > **Scenario:** You have just been granted Workspace Admin access to a new Azure Databricks workspace
# MAGIC > that will host AI workloads for a regulated entity. Before any user can query data with Genie or
# MAGIC > call a foundation model, you need to answer four questions:
# MAGIC >
# MAGIC > 1. Is data processing confined to AU East — or could a model call leak data offshore?
# MAGIC > 2. Is Partner-Powered AI enabled? What does it actually do to your data?
# MAGIC > 3. Who is allowed to see which AI assets — and how is that enforced?
# MAGIC > 4. Can you prove what happened? Is audit logging capturing AI events?
# MAGIC >
# MAGIC > Getting any of these wrong in a regulated context means a potential breach notification obligation
# MAGIC > to your regulator, and an inability to demonstrate control to auditors.
# MAGIC > This lab walks you through verifying and locking down all four controls.
# MAGIC
# MAGIC **The 4 controls you will verify and configure:**
# MAGIC
# MAGIC | # | Control | Why it matters | Where |
# MAGIC |---|---|---|---|
# MAGIC | 1 | Geography enforcement ON | Prevents AU data being processed in US/EU Databricks regions | Account Console |
# MAGIC | 2 | Partner-Powered AI setting understood | Controls whether AI features can call external partner models | Workspace settings API |
# MAGIC | 3 | UC permissions for AI assets | Governs which users/groups can query models, endpoints, and Genie Spaces | Unity Catalog |
# MAGIC | 4 | Audit logging active | Captures who queried what AI asset and when — required for regulatory evidence | system.access.audit |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC > **AU East residency quick ref** — Genie Spaces ✅ in-region | AI Gateway ✅ in-region | FMAPI Provisioned Throughput ✅ in-region | FMAPI Pay-Per-Token ⚠️ cross-geo by default (requires cross-geo processing enabled) | Knowledge Assistant ❌ not available in AU East | Foundation Model Fine-tuning ❌ not available AU East
# MAGIC >
# MAGIC > **Important:** ALL FMAPI Pay-Per-Token endpoints (including `databricks-claude-haiku-4-5`) require the "Allow cross-geography model serving" toggle to be enabled, because even AU-region models are currently backed by cross-geo infrastructure for Pay-Per-Token traffic. Only FMAPI Provisioned Throughput endpoints are fully in-region. See Lab 02 for the in-region setup using AI Gateway with a provisioned endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 0: Setup
# MAGIC
# MAGIC Run this section first. It auto-populates your workspace URL and token from the notebook context.
# MAGIC
# MAGIC **You do not need to fill in any widgets** unless you are running this lab against a different workspace.
# MAGIC - Leave the `workspace_url` widget at its default placeholder — the URL is read automatically from notebook context.
# MAGIC - Set `account_id` only if you want to use account-level API calls (Section 1 guidance text). It is not required for Controls 2–4.
# MAGIC - If the widget default has been overwritten, run: `dbutils.widgets.remove("workspace_url")` and re-run this cell.

# COMMAND ----------

import os
import json
import requests

# COMMAND ----------

# Widget-based configuration — account ID must be set manually (not available from notebook context)
dbutils.widgets.text("workspace_url", "https://<your-workspace>.azuredatabricks.net", "Workspace URL (auto-populated if blank)")
dbutils.widgets.text("account_id",    "<your-account-id>",                            "Account ID (from Account Console URL)")

WORKSPACE_URL_W  = dbutils.widgets.get("workspace_url")
ACCOUNT_ID_W     = dbutils.widgets.get("account_id")

print(f"Widget — Workspace URL : {WORKSPACE_URL_W}")
print(f"Widget — Account ID    : {ACCOUNT_ID_W}")
print()
print("NOTE: You do NOT need to fill in the workspace_url widget.")
print("      It will be auto-populated from the notebook context in the next cell.")
print("      Only fill it in if you are running this lab against a DIFFERENT workspace.")

# COMMAND ----------

# Auto-populate the workspace URL and token from the notebook context.
# This avoids token paste mistakes and works in any Databricks environment.
_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_auto_url   = _ctx.apiUrl().getOrElse(None)
_auto_token = _ctx.apiToken().getOrElse(None)

# Workspace URL resolution — two sources, clear priority:
#   PRIORITY 1: Notebook context auto-population (used in 99% of cases — no input needed)
#   PRIORITY 2: widget value (only if you typed a non-default URL into the widget)
#
# The widget default "https://<your-workspace>.azuredatabricks.net" is a placeholder.
# If the widget still shows that placeholder string, it has NOT been filled in,
# and the auto-detected URL is used. Only override if targeting a different workspace.
if WORKSPACE_URL_W != "https://<your-workspace>.azuredatabricks.net":
    WORKSPACE_URL = WORKSPACE_URL_W
    print(f"INFO: WORKSPACE_URL taken from widget (manual override): {WORKSPACE_URL}")
elif _auto_url:
    WORKSPACE_URL = _auto_url
    print(f"INFO: WORKSPACE_URL auto-populated from notebook context: {WORKSPACE_URL}")
else:
    raise ValueError(
        "WORKSPACE_URL could not be determined. "
        "Fill in the 'workspace_url' widget at the top of this notebook."
    )

# Token: prefer notebook context token (no clipboard paste required).
# For production, use a secret scope instead:
#   DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")
DATABRICKS_TOKEN = _auto_token

if not DATABRICKS_TOKEN:
    raise ValueError(
        "DATABRICKS_TOKEN could not be auto-populated. "
        "Use dbutils.secrets.get() with a secret scope, or ensure the cluster has a valid token context."
    )

# Derived — do not edit below this line
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

# Account ID: must be set via widget (not available from notebook context)
ACCOUNT_ID = ACCOUNT_ID_W if ACCOUNT_ID_W != "<your-account-id>" else "<your-account-id>"

print(f"Workspace URL : {WORKSPACE_URL}")
print(f"Account ID    : {ACCOUNT_ID} {'(set via widget)' if ACCOUNT_ID != '<your-account-id>' else '(NOT SET — needed for Section 1)'}")
print("Token         : [loaded from notebook context]")

# Expected output:
# Workspace URL : https://adb-1234567890.12.azuredatabricks.net
# Account ID    : (NOT SET — needed for Section 1)
# Token         : [loaded from notebook context]

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Control 1: Geography Enforcement
# MAGIC
# MAGIC **WHY:** The geography enforcement toggle prevents Databricks features from routing your data outside the workspace region (AU East). Without it, features like AI Playground may send prompts and data to US-region infrastructure. For regulated entities and licensed operators, this is a mandatory control — not a best practice.
# MAGIC
# MAGIC When this toggle is OFF, cross-geo model calls are permitted. When it is ON:
# MAGIC - Cross-geo FMAPI Pay-Per-Token models are hidden from the AI Playground model picker
# MAGIC - Features that require cross-geo processing are blocked at the platform level
# MAGIC - Your data stays within the Azure Australia East region boundary
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### 🖱️ UI Steps — the only supported verification method
# MAGIC
# MAGIC The geography enforcement toggle is managed exclusively through the Account Console UI.
# MAGIC There is no confirmed public REST API path to read or set this toggle programmatically.
# MAGIC It is controlled by an internal Databricks configuration flag
# MAGIC (`ASSISTANT_WORKSPACE_ENFORCE_DATA_RESIDENCY`) that is applied through the
# MAGIC Account Console — not through the typed settings API.
# MAGIC
# MAGIC 1. Navigate to: **accounts.azuredatabricks.net** → Workspaces → [your workspace name]
# MAGIC 2. Click the **Security and compliance** tab
# MAGIC 3. Find: "Enforce data processing within workspace Geography for Designated Services"
# MAGIC 4. Confirm the toggle is **ON** (blue/enabled)
# MAGIC
# MAGIC > This setting is NOT in the workspace admin console. It lives on the workspace detail page inside the Account Console. For Azure workspaces use `accounts.azuredatabricks.net`.
# MAGIC
# MAGIC > If you do not have Account Admin role, ask your Account Admin to verify and screenshot the toggle before you proceed.
# MAGIC
# MAGIC ### ⚡ API — read-only: check audit log for recent geography setting changes
# MAGIC
# MAGIC While there is no public API to read the current geography enforcement state, every toggle
# MAGIC change fires a `updateWorkspaceConfiguration` event in `system.access.audit`. You can use
# MAGIC this to confirm when the setting was last changed and by whom — useful for compliance evidence.

# COMMAND ----------

def check_geography_change_audit(workspace_url: str, headers: dict, account_id: str) -> dict:
    """
    Check system.access.audit for recent geography enforcement changes.

    The geography enforcement toggle fires action_name = 'updateWorkspaceConfiguration'
    in system.access.audit when changed. This is NOT a real-time API read of the toggle
    state — it is an audit trail of changes.

    To read the current toggle state: use the Account Console UI (steps above).
    The toggle state is NOT readable via any confirmed public REST API path.

    Returns a status dict explaining how to verify via UI and via the audit log.
    """
    status = {
        "verification_method": "UI only — Account Console → Workspaces → Security and compliance",
        "audit_trail": "system.access.audit WHERE action_name = 'updateWorkspaceConfiguration'",
        "no_public_api": (
            "There is no confirmed public REST API path to read or set the geography enforcement "
            "toggle. It is managed by an internal Databricks flag applied via the Account Console."
        ),
    }
    if account_id == "<your-account-id>":
        status["account_id_status"] = "Not set — cannot look up workspace list."
    else:
        status["account_id_status"] = f"Account ID: {account_id}"
    return status


geography_status = check_geography_change_audit(WORKSPACE_URL, HEADERS, ACCOUNT_ID)
print("=" * 60)
print("  Control 1: Geography Enforcement")
print("=" * 60)
print()
print("Verification method: Account Console UI (no public API available)")
print()
print("Steps:")
print("  1. accounts.azuredatabricks.net → Workspaces → [your workspace]")
print("  2. Security and compliance tab")
print("  3. 'Enforce data processing within workspace Geography for Designated Services'")
print("  4. Confirm toggle is ON (blue/enabled)")
print()
print("Audit trail — run this SQL to see geography setting changes:")
print("""
  SELECT event_time, user_identity.email, action_name, request_params
  FROM system.access.audit
  WHERE action_name = 'updateWorkspaceConfiguration'
    AND event_date >= current_date() - INTERVAL 90 DAYS
  ORDER BY event_time DESC
  LIMIT 10
""")
print("─" * 60)
print("geography_enforced = None  (must be verified via Account Console UI)")
geography_enforced = None  # Set to True manually after confirming the UI toggle is ON

# Expected output:
# ============================================================
#   Control 1: Geography Enforcement
# ============================================================
#
# Verification method: Account Console UI (no public API available)
# Steps:
#   1. accounts.azuredatabricks.net → Workspaces → [your workspace]
#   2. Security and compliance tab
#   3. 'Enforce data processing within workspace Geography for Designated Services'
#   4. Confirm toggle is ON (blue/enabled)
# ...
# geography_enforced = None  (must be verified via Account Console UI)

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Verify Control 1
# MAGIC
# MAGIC After completing the UI steps above:
# MAGIC - If the toggle is **ON**: set `geography_enforced = True` in the cell above (for the checkpoint cell)
# MAGIC - If the toggle is **OFF**: your Account Admin must enable it before deploying AI workloads to regulated users
# MAGIC - If you see the audit SQL returns a recent `updateWorkspaceConfiguration` event, note the user and timestamp as compliance evidence

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Control 2: Partner-Powered AI Feature Flags
# MAGIC
# MAGIC **WHY:** Several Databricks AI features can call external partner services. Understanding which features are enabled — and what data they handle — is required before onboarding regulated users.
# MAGIC
# MAGIC **Partner-Powered AI (llm_proxy_partner_powered)** controls whether AI features can route prompts through Databricks' internal LLM proxy to partner model providers. When enabled, prompts from AI Playground, Genie suggestions, and similar features may be processed by external partner infrastructure.
# MAGIC
# MAGIC | Setting type | Scope | What it controls |
# MAGIC |---|---|---|
# MAGIC | `llm_proxy_partner_powered` | Workspace | Enables or disables partner-powered AI features for this workspace |
# MAGIC | `llm_proxy_partner_powered` | Account | Default for all new workspaces |
# MAGIC | `llm_proxy_partner_powered_enforce` | Account | Forces all workspaces to inherit account setting; workspace admins cannot override |
# MAGIC
# MAGIC > **Security implications:** When `llm_proxy_partner_powered` is `true`, prompts from features like AI Playground suggestions may be sent to external partner model providers. For data classified above Public, this setting should be `false` unless your DLP controls confirm partner data handling meets your regulatory requirements.
# MAGIC
# MAGIC > **Geography enforcement interaction:** If geography enforcement is ON, cross-geo partner calls are blocked at the platform level regardless of this setting. However, do not rely solely on geography enforcement — setting `llm_proxy_partner_powered=false` explicitly provides defence in depth.
# MAGIC
# MAGIC | Setting key | What it controls | Security relevance |
# MAGIC |---|---|---|
# MAGIC | `aibi_genie_space_enabled_ws_setting` | Master on/off for ALL Genie Spaces | Turning this OFF disables Genie across the entire workspace — not a per-space control |
# MAGIC | `restrict_workspace_admins` | Non-admin user restrictions | Useful for tightening default access |
# MAGIC | `enableResultsDownloading` | Whether users can download query results as CSV | Prevent data exfiltration from the notebook UI |
# MAGIC | `enableExportNotebook` | Whether users can download notebook source files | Prevent IP and code exfiltration |
# MAGIC
# MAGIC ### 🖱️ UI Steps
# MAGIC
# MAGIC There is no single "AI features" settings page — the toggles are spread across two locations:
# MAGIC
# MAGIC 1. **Feature flags (newer controls):** Click your username top-right → Settings → scroll to find "AI / Machine Learning" or "Previews" section. Exact label varies by workspace version.
# MAGIC 2. **Security settings (export/download):** Settings → Workspace settings → Advanced. Look for "Allow users to download results" and "Allow users to export notebooks".
# MAGIC
# MAGIC > If you cannot find these via the UI, the API check below is the authoritative source.
# MAGIC
# MAGIC ### ⚡ API Check — read all AI feature flags at once

# COMMAND ----------

# Typed Settings API: newer controls (post-2023 settings surface)
# These use the /api/2.0/settings/types/{type}/names/default path.
#
# CONFIRMED setting types:
#   llm_proxy_partner_powered         — Partner-Powered AI workspace toggle
#   aibi_genie_space_enabled_ws_setting — Genie Spaces workspace-wide on/off
#   restrict_workspace_admins         — Non-admin restrictions
#
# GET response format for llm_proxy_partner_powered:
#   {"etag": "...", "setting_name": "default", "boolean_val": {"value": true}}
#
# PATCH body to disable Partner-Powered AI:
#   {"setting": {"boolean_val": {"value": false}}, "allow_missing": true, "field_mask": "boolean_val"}
#
# NOTE: Changes to llm_proxy_partner_powered take up to 3 minutes to propagate.

AI_SETTING_TYPES = [
    "llm_proxy_partner_powered",            # Partner-Powered AI workspace toggle (confirmed GA)
    "aibi_genie_space_enabled_ws_setting",  # Genie Spaces workspace-wide on/off
    "restrict_workspace_admins",            # Non-admin restrictions
]

# These security settings can be read via both the typed API (hyphen form) and the legacy
# workspace-conf endpoint. We use workspace-conf here for simplicity.
WORKSPACE_CONF_KEYS = [
    "enableNotebookTableClipboard",
    "enableResultsDownloading",
    "enableExportNotebook",
]


def fetch_typed_setting(workspace_url: str, headers: dict, setting_type: str) -> dict:
    """
    Fetch one typed workspace setting via the Settings API.
    Returns a dict with status='not_available' on 404 — treated as a graceful skip,
    not an error, because some settings are workspace-tier-dependent.
    """
    url = f"{workspace_url}/api/2.0/settings/types/{setting_type}/names/default"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 404:
        return {"status": "not_available", "setting_type": setting_type,
                "note": "Setting not found on this workspace tier — may require a different tier or region"}
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
print(f"{'Setting Type':<52} {'Value / Status'}")
print("─" * 80)
for setting_type in AI_SETTING_TYPES:
    result = fetch_typed_setting(WORKSPACE_URL, HEADERS, setting_type)
    if result.get("status") == "not_available":
        display = "not available on this workspace tier"
    elif setting_type == "llm_proxy_partner_powered":
        # llm_proxy_partner_powered returns {"etag": "...", "setting_name": "default", "boolean_val": {"value": true/false}}
        boolean_val = result.get("boolean_val", {})
        val = boolean_val.get("value", "(unknown)")
        security_note = " ← REVIEW: external partner calls enabled" if val is True else " ← GOOD: partner calls disabled"
        display = f"boolean_val.value = {val}{security_note}"
    else:
        inner = result.get(setting_type, {})
        display = str(inner) if inner else str(result)
    print(f"{setting_type:<52} {display}")

# --- Query legacy workspace conf keys ---
print()
print(f"{'Workspace-conf key':<52} {'Effective value'}")
print("─" * 80)
workspace_conf = fetch_workspace_conf(WORKSPACE_URL, HEADERS, WORKSPACE_CONF_KEYS)
for key in WORKSPACE_CONF_KEYS:
    raw_value = workspace_conf.get(key)
    if raw_value is None:
        # null from workspace-conf means the setting has never been explicitly set.
        # The platform default applies. Confirmed defaults:
        #   enableResultsDownloading    = true (platform default)
        #   enableExportNotebook        = true (platform default)
        #   enableNotebookTableClipboard = true (platform default)
        display = "null → platform default applies (currently: true)"
    else:
        display = raw_value
    print(f"{key:<52} {display}")

# Expected output:
# Setting Type                                         Value / Status
# ────────────────────────────────────────────────────────────────────────────────
# llm_proxy_partner_powered                            boolean_val.value = True ← REVIEW: external partner calls enabled
# aibi_genie_space_enabled_ws_setting                  {'enabled': True}
# restrict_workspace_admins                            {'restrict_workspace_admins': 'ALLOW_ALL'}
#
# Workspace-conf key                                   Effective value
# ────────────────────────────────────────────────────────────────────────────────
# enableNotebookTableClipboard                         null → platform default applies (currently: true)
# enableResultsDownloading                             null → platform default applies (currently: true)
# enableExportNotebook                                 null → platform default applies (currently: true)
#
# NOTE: null means the setting has never been explicitly set. The platform default is true
# for all three security keys. If your policy requires these to be false, explicitly set them:
#   PATCH /api/2.0/workspace-conf  {"enableResultsDownloading": "false", "enableExportNotebook": "false"}

# COMMAND ----------

# MAGIC %md
# MAGIC ### ⚡ 2b. Disable Partner-Powered AI (if required by policy)
# MAGIC
# MAGIC If the check above shows `llm_proxy_partner_powered = True` and your DLP policy does not permit
# MAGIC external partner model calls for this workspace, use the PATCH below to disable it.
# MAGIC
# MAGIC **Changes take up to 3 minutes to propagate across the workspace.**
# MAGIC
# MAGIC To enforce the setting across all workspaces from the account level (so workspace admins cannot
# MAGIC re-enable it), use the `llm_proxy_partner_powered_enforce` account-level setting via the
# MAGIC Account API: `PATCH /api/2.0/accounts/{account_id}/settings/types/llm_proxy_partner_powered_enforce/names/default`

# COMMAND ----------

def set_partner_powered_ai(workspace_url: str, headers: dict, enabled: bool) -> dict:
    """
    Enable or disable Partner-Powered AI for this workspace.

    Setting type: llm_proxy_partner_powered
    Path: PATCH /api/2.0/settings/types/llm_proxy_partner_powered/names/default

    GET response format:
      {"etag": "<etag>", "setting_name": "default", "boolean_val": {"value": true}}

    PATCH body format (ETag from GET is required for optimistic concurrency):
      {"setting": {"boolean_val": {"value": false}}, "allow_missing": true, "field_mask": "boolean_val"}

    Changes take up to 3 minutes to propagate.

    Account-level enforce (prevents workspace override):
      PATCH /api/2.0/accounts/{account_id}/settings/types/llm_proxy_partner_powered_enforce/names/default
      Same body format as above.
    """
    url = f"{workspace_url}/api/2.0/settings/types/llm_proxy_partner_powered/names/default"

    # GET current state to obtain the ETag (required for optimistic concurrency)
    get_resp = requests.get(url, headers=headers, timeout=30)
    if get_resp.status_code == 404:
        return {
            "status": "not_available",
            "note": "llm_proxy_partner_powered not found on this workspace tier"
        }
    get_resp.raise_for_status()
    etag = get_resp.json().get("etag", "")

    payload = {
        "setting": {"boolean_val": {"value": enabled}},
        "allow_missing": True,
        "field_mask": "boolean_val",
    }
    if etag:
        payload["etag"] = etag

    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# Read-only: show current state
print("Reading current Partner-Powered AI setting...")
ppa_current = fetch_typed_setting(WORKSPACE_URL, HEADERS, "llm_proxy_partner_powered")
if ppa_current.get("status") == "not_available":
    print("llm_proxy_partner_powered: not available on this workspace tier")
else:
    val = ppa_current.get("boolean_val", {}).get("value", "(unknown)")
    print(f"llm_proxy_partner_powered.boolean_val.value = {val}")
    if val is True:
        print("  -> Partner-Powered AI is ENABLED. If policy requires it disabled, uncomment the PATCH call below.")
    else:
        print("  -> Partner-Powered AI is DISABLED. Meets policy requirement for external partner call restriction.")

print()
print("To disable Partner-Powered AI (uncomment and run — workspace-wide effect):")
print("  result = set_partner_powered_ai(WORKSPACE_URL, HEADERS, enabled=False)")
print()
print("To enforce at account level (workspace admins cannot re-enable):")
print(f"  PATCH https://accounts.azuredatabricks.net/api/2.0/accounts/{ACCOUNT_ID}/settings/types/llm_proxy_partner_powered_enforce/names/default")
print('  Body: {"setting": {"boolean_val": {"value": true}}, "allow_missing": true, "field_mask": "boolean_val"}')

# ONLY uncomment if you intentionally want to disable Partner-Powered AI
# result = set_partner_powered_ai(WORKSPACE_URL, HEADERS, enabled=False)
# print(f"Updated setting: {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Verify Control 2
# MAGIC
# MAGIC Review the output above:
# MAGIC - **`llm_proxy_partner_powered`** — if `True` and your policy prohibits external partner model calls, disable it using the PATCH call shown above.
# MAGIC - **`aibi_genie_space_enabled_ws_setting`** — should show `{'enabled': True}` (Genie is on). If you see `not available`, this is a workspace tier limitation — not a security gap.
# MAGIC - **`enableResultsDownloading` / `enableExportNotebook`** — `null` means platform default (true = allowed). If your CISO policy requires these disabled, run: `PATCH /api/2.0/workspace-conf {"enableResultsDownloading": "false", "enableExportNotebook": "false"}`
# MAGIC - A `null` value here is NOT a misconfiguration — it means the setting has not been explicitly overridden from the default.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Control 3: Unity Catalog Permissions for AI Assets
# MAGIC
# MAGIC **WHY:** AI assets in Databricks (registered models, serving endpoints, Genie Spaces) are access-controlled through Unity Catalog and workspace ACLs. Without explicit grants, only workspace admins can use them. Without explicit revokes, `account users` may inherit broad access. Getting this wrong means regulated data is accessible to the wrong users — or no users at all (if permissions are too restrictive for production workflows).
# MAGIC
# MAGIC UC grants travel with the asset across workspaces sharing the same metastore — one consistent policy regardless of which workspace a user comes from.
# MAGIC
# MAGIC | Asset type | Permission mechanism | Typical grant for consumers | Typical grant for admins |
# MAGIC |---|---|---|---|
# MAGIC | Registered model | UC SQL GRANT | `EXECUTE` (run inference) | `ALL PRIVILEGES` |
# MAGIC | Model serving endpoint | Workspace ACL (SDK/UI) | `CAN_QUERY` | `CAN_MANAGE` |
# MAGIC | Genie Space | Workspace permissions API | `CAN_USE` | `CAN_MANAGE` |
# MAGIC
# MAGIC ### 🖱️ UI Steps
# MAGIC
# MAGIC **Registered models:**
# MAGIC 1. Left sidebar → Catalog icon (stacked layers)
# MAGIC 2. Expand: catalog → schema → Models folder → [model name]
# MAGIC 3. Click **Permissions** tab
# MAGIC 4. You should see: current grants. Click **Grant** to add a principal.
# MAGIC
# MAGIC **Serving endpoints:**
# MAGIC 1. Left sidebar → Serving
# MAGIC 2. Click an endpoint name → **Permissions** tab
# MAGIC 3. You should see: CAN_QUERY / CAN_MANAGE assignments. Click **Grant**.
# MAGIC
# MAGIC **Genie Spaces:**
# MAGIC 1. Left sidebar → Genie → [Space name]
# MAGIC 2. Kebab menu (top-right) → **Share** or **Permissions**
# MAGIC 3. Add groups with CAN_USE / CAN_EDIT / CAN_MANAGE
# MAGIC
# MAGIC > The Genie Space URL contains the space ID: `.../genie/spaces/<SPACE-ID>` — copy that ID for the API call below.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ⚡ 3a. Grant permissions on a registered model

# COMMAND ----------

# ---------------------------------------------------------------------------
# TODO: Replace ALL values below with your actual catalog, schema, model, and group names.
#       The names shown are EXAMPLES ONLY — they do not exist in your workspace.
#       Running the SQL or SDK calls with these placeholder values will fail.
# ---------------------------------------------------------------------------
CATALOG_NAME    = "<your-catalog>"          # TODO: e.g. "main" or "energy_prod"
SCHEMA_NAME     = "<your-schema>"           # TODO: e.g. "models"
MODEL_NAME      = "<your-model-name>"       # TODO: registered model name in UC
CONSUMER_GROUP  = "<consumer-group>"        # TODO: group that will run inference
ADMIN_GROUP     = "<admin-group>"           # TODO: group that will manage models
# ---------------------------------------------------------------------------

grant_model_sql = f"""
-- Allow the analyst group to run inference against the registered model
GRANT EXECUTE ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{CONSUMER_GROUP}`;

-- Allow the AI admins group to fully manage the model
GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{ADMIN_GROUP}`;

-- Verify — expected output: two rows, one per grant above
SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME};
"""

if "<your-catalog>" in CATALOG_NAME or "<your-schema>" in SCHEMA_NAME or "<your-model-name>" in MODEL_NAME:
    print("ACTION REQUIRED: Replace the TODO variables above (CATALOG_NAME, SCHEMA_NAME, MODEL_NAME,")
    print("                 CONSUMER_GROUP, ADMIN_GROUP) with your actual values before running SQL.")
    print()
print("SQL template (update variables above, then run in a %sql cell or spark.sql()):\n")
print(grant_model_sql)

# Expected output after SHOW GRANTS (your actual names will differ):
# principal              privilege_type   object_type   object_name
# <consumer-group>       EXECUTE          MODEL         <catalog>.<schema>.<model>
# <admin-group>          ALL PRIVILEGES   MODEL         <catalog>.<schema>.<model>

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
# MAGIC ### ⚡ 3b. Grant permissions on a model serving endpoint
# MAGIC
# MAGIC > **Important:** Model serving endpoint permissions are workspace-level ACLs — they are NOT governed through Unity Catalog SQL GRANT statements. You cannot use `GRANT CAN_QUERY ON SERVING ENDPOINT ...` in SQL; that syntax does not exist. Use the SDK method below (or the UI) to set endpoint permissions.

# COMMAND ----------

# TODO: Fill in your endpoint name
ENDPOINT_NAME = "<your-endpoint-name>"  # TODO: your model serving endpoint name (e.g. "my-model-endpoint")

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServingEndpointAccessControlRequest,
    ServingEndpointPermissionLevel,
)

# Initialize WorkspaceClient using the same host and token as the REST API calls above.
w = WorkspaceClient(host=WORKSPACE_URL, token=DATABRICKS_TOKEN)
print(f"WorkspaceClient initialized — host: {w.config.host}")

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
# print(f"Permissions updated on endpoint: {ENDPOINT_NAME}")

# Expected output after update_permissions:
# Permissions updated on endpoint: <your-endpoint-name>

if "<your-endpoint-name>" in ENDPOINT_NAME:
    print("ACTION REQUIRED: Set ENDPOINT_NAME to your actual model serving endpoint name above.")
else:
    print(f"Endpoint: {ENDPOINT_NAME}")
print("SDK permission call is commented out — uncomment after setting ENDPOINT_NAME.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ⚡ 3c. Grant permissions on a Genie Space
# MAGIC
# MAGIC > **Permissions API:** Genie Spaces use the `dashboards` object type in the permissions API (`/api/2.0/permissions/dashboards/{space_id}`). This is the same endpoint used for AI/BI Lakeview dashboards.
# MAGIC >
# MAGIC > Valid permission levels: **`CAN_USE`** (query the space), `CAN_EDIT` (modify questions), `CAN_MANAGE` (admin).

# COMMAND ----------

# TODO: Replace with your Genie Space ID (copy from the browser URL: .../genie/spaces/<SPACE-ID>)
GENIE_SPACE_ID = "<your-genie-space-id>"  # TODO


def get_genie_space_permissions(workspace_url: str, headers: dict, genie_space_id: str) -> dict:
    """
    Fetch current permissions for a Genie Space via the permissions API.
    Genie Spaces use the 'dashboards' object type.
    """
    url = f"{workspace_url}/api/2.0/permissions/dashboards/{genie_space_id}"
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 404:
        return {"error": f"Space ID '{genie_space_id}' not found — verify the ID from the browser URL"}
    response.raise_for_status()
    return response.json()


def grant_genie_space_permission(
    workspace_url: str,
    headers: dict,
    genie_space_id: str,
    group_name: str,
    permission_level: str,  # "CAN_USE", "CAN_EDIT", or "CAN_MANAGE"
) -> dict:
    """
    Grant a group access to a Genie Space. PATCH is additive — existing grants are preserved.
    Safe to call multiple times (idempotent).
    """
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

# Expected output after PATCH:
# {
#   "object_id": "/dashboards/<SPACE-ID>",
#   "object_type": "dashboard",
#   "access_control_list": [
#     {"group_name": "<consumer-group>", "all_permissions": [{"permission_level": "CAN_USE", "inherited": false}]}
#   ]
# }

if "<your-genie-space-id>" in GENIE_SPACE_ID:
    print("ACTION REQUIRED: Set GENIE_SPACE_ID to your Genie Space ID.")
    print("  Find it in the browser URL: .../genie/spaces/<SPACE-ID>")
else:
    print(f"Genie Space ID: {GENIE_SPACE_ID}")
print("Genie Space permission calls are commented out — uncomment after setting GENIE_SPACE_ID.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Verify Control 3
# MAGIC
# MAGIC After running the cells above:
# MAGIC - SHOW GRANTS on your model should return at least two rows (EXECUTE for consumers, ALL PRIVILEGES for admins)
# MAGIC - Serving endpoint permissions updated without error
# MAGIC - Genie Space PATCH returned an `access_control_list` with your group and CAN_USE

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Control 4: Confirm Audit Logging is Active
# MAGIC
# MAGIC **WHY:** Audit logging captures every AI API call — who queried which Genie Space, which model was invoked, who changed a permission setting. For regulated entities, audit logs are a compliance requirement, not a nice-to-have. If audit logging is not active, you cannot demonstrate to a regulator what happened with your AI workloads.
# MAGIC
# MAGIC Databricks writes audit events to `system.access.audit` automatically when the system tables schema is enabled. AI-specific events to watch for:
# MAGIC
# MAGIC | Event service_name | Action name | What it captures |
# MAGIC |---|---|---|
# MAGIC | `aibi` | `genieConversation` | Genie Space query (user, space, question) |
# MAGIC | `mlflowAcledArtifact` | `getServingEndpoint` | Model serving endpoint access |
# MAGIC | `workspace` | `updatePermissions` | Permission changes on AI assets |
# MAGIC | `accounts` | `updateWorkspaceConfiguration` | Workspace-level setting changes (including geography enforcement toggle) |
# MAGIC | `serverlessRealTimeInference` | `putInferenceEndpointAiGateway` | AI Gateway config changes (create/update) |
# MAGIC
# MAGIC > **Note on AI Gateway runtime calls:** Individual inference requests through AI Gateway do NOT appear in `system.access.audit`. The audit log records config changes, not per-request traffic. Per-request data lives in `system.ai_gateway.usage` (Beta) and the payload log Delta table configured in Lab 02.
# MAGIC
# MAGIC ### 🖱️ UI Steps
# MAGIC
# MAGIC 1. Left sidebar → Catalog icon
# MAGIC 2. Navigate to: `system` → `access` → `audit`
# MAGIC 3. Click **Open in query editor** (or run the SQL below)
# MAGIC 4. You should see: rows with recent event timestamps. If the table is empty or not found, system tables are not yet enabled.
# MAGIC
# MAGIC > To enable system tables: Account Console → Settings → System tables → Enable. This is a one-time account-level action.
# MAGIC
# MAGIC ### ⚡ API/SQL Check — verify audit log has AI events

# COMMAND ----------

# Read-only audit log verification — safe to run at any time.
# This confirms (a) system tables are enabled and (b) AI events are being captured.

audit_check_sql = """
-- Check 1: confirm the audit table is reachable and has recent events
SELECT
  event_date,
  service_name,
  action_name,
  COUNT(*) AS event_count
FROM system.access.audit
WHERE event_date >= current_date() - INTERVAL 7 DAYS
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC
LIMIT 20
"""

ai_audit_check_sql = """
-- Check 2: confirm AI-specific events are present (Genie, serving endpoint, permission changes)
SELECT
  event_time,
  service_name,
  action_name,
  user_identity.email AS user_email,
  request_params
FROM system.access.audit
WHERE event_date >= current_date() - INTERVAL 7 DAYS
  AND service_name IN ('aibi', 'mlflowAcledArtifact', 'serverlessRealTimeInference')
ORDER BY event_time DESC
LIMIT 10
"""

geo_change_sql = """
-- Check 3: geography enforcement toggle changes (use as compliance evidence for Control 1)
SELECT
  event_time,
  user_identity.email AS changed_by,
  action_name,
  request_params
FROM system.access.audit
WHERE action_name = 'updateWorkspaceConfiguration'
  AND event_date >= current_date() - INTERVAL 90 DAYS
ORDER BY event_time DESC
LIMIT 5
"""

print("Run these SQL queries in a %sql cell or spark.sql() to verify audit logging:")
print()
print("-- QUERY 1: Recent event summary by service")
print(audit_check_sql)
print()
print("-- QUERY 2: AI-specific audit events (Genie, serving, AI Gateway config)")
print(ai_audit_check_sql)
print()
print("-- QUERY 3: Geography enforcement changes (compliance evidence for Control 1)")
print(geo_change_sql)

# COMMAND ----------

# Live audit check — uncomment to execute
# Requires system tables enabled on this workspace.

# try:
#     audit_summary = spark.sql("""
#         SELECT service_name, action_name, COUNT(*) as cnt
#         FROM system.access.audit
#         WHERE event_date >= current_date() - INTERVAL 7 DAYS
#         GROUP BY 1, 2
#         ORDER BY 3 DESC
#         LIMIT 10
#     """)
#     row_count = audit_summary.count()
#     if row_count > 0:
#         print(f"PASS — audit table reachable, {row_count} distinct event types in last 7 days")
#         display(audit_summary)
#     else:
#         print("WARNING — audit table exists but has no events in last 7 days. Verify system tables are being written.")
# except Exception as e:
#     print(f"CANNOT VERIFY — {e}")
#     print("ACTION: Enable system tables in Account Console → Settings → System tables")

# Expected output:
# PASS — audit table reachable, 8 distinct event types in last 7 days
# service_name                   action_name              cnt
# workspace                      getNotebook              1243
# aibi                           genieConversation        87
# mlflowAcledArtifact            getServingEndpoint       34
# serverlessRealTimeInference    putInferenceEndpointAiGateway   3
# ...

print("Audit log check is commented out — uncomment to execute against system.access.audit.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ✅ Verify Control 4
# MAGIC
# MAGIC After running the audit check:
# MAGIC - **PASS:** Table is reachable, rows are present, AI events (`aibi`, `mlflowAcledArtifact`, `serverlessRealTimeInference`) appear in results
# MAGIC - **Empty table:** System tables enabled but no AI activity yet — this is OK in a fresh workspace. Use AI Playground once, then re-run to confirm events are flowing.
# MAGIC - **Table not found:** System tables not enabled. Enable via Account Console → Settings → System tables.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Checkpoint: All 4 Controls

# COMMAND ----------

print("=" * 60)
print("  Lab 01 — 4 Controls Checkpoint")
print("=" * 60)
print()

checks = []

# Control 1: Geography enforcement — no public API; must be confirmed via UI
# geography_enforced is set in the Control 1 cell above.
# If you confirmed the toggle is ON in Account Console, set geography_enforced = True there.
if geography_enforced is True:
    checks.append(("Control 1 — Geography enforcement", True,
                   "Confirmed ON via Account Console UI"))
elif geography_enforced is False:
    checks.append(("Control 1 — Geography enforcement", False,
                   "Confirmed OFF — must enable in Account Console before deploying AI workloads"))
else:
    checks.append(("Control 1 — Geography enforcement", False,
                   "Not yet confirmed. Set geography_enforced = True in the Control 1 cell after verifying "
                   "the toggle is ON in Account Console → Workspaces → Security and compliance."))

# Control 2: Partner-Powered AI setting readable
if WORKSPACE_URL and "<your-workspace>" not in WORKSPACE_URL:
    ppa_check = fetch_typed_setting(WORKSPACE_URL, HEADERS, "llm_proxy_partner_powered")
    if ppa_check.get("status") == "not_available":
        checks.append(("Control 2 — AI feature flags readable", True,
                       "Settings API reachable (llm_proxy_partner_powered: not available on this tier)"))
    else:
        val = ppa_check.get("boolean_val", {}).get("value", "(unknown)")
        note = "REVIEW: partner calls enabled" if val is True else "OK: partner calls disabled"
        checks.append(("Control 2 — AI feature flags readable", True,
                       f"Settings API reachable. llm_proxy_partner_powered = {val} ({note})"))
else:
    checks.append(("Control 2 — AI feature flags readable", False, "Workspace URL not configured"))

# Control 3: WorkspaceClient initialised (prerequisite for SDK permission calls)
try:
    _ = w.config.host
    checks.append(("Control 3 — UC permissions SDK ready", True, f"WorkspaceClient host: {w.config.host}"))
except Exception as e:
    checks.append(("Control 3 — UC permissions SDK ready", False, str(e)))

# Control 4: system.access.audit reachable (informational — requires system tables)
try:
    count = spark.sql("SELECT COUNT(*) as n FROM system.access.audit").collect()[0]["n"]
    checks.append(("Control 4 — Audit logging active", True, f"system.access.audit has {count:,} rows"))
except Exception as e:
    checks.append(("Control 4 — Audit logging active", False,
                   f"system.access.audit not reachable: {str(e)[:80]} — enable system tables in Account Console"))

print()
for description, passed, detail in checks:
    icon = "✅" if passed else "❌"
    print(f"  {icon}  {description}")
    if not passed:
        print(f"       → {detail}")
    else:
        print(f"       {detail}")

print()
all_pass = all(p for _, p, _ in checks)
if all_pass:
    print("─" * 60)
    print("  ✅ Lab 01 complete. Your workspace is configured for regulated AI use.")
    print("─" * 60)
else:
    print("─" * 60)
    print("  Fix the items marked ❌ above before deploying AI workloads to regulated users.")
    print("─" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Supporting Material: Genie Space Workspace Toggle
# MAGIC
# MAGIC This section is reference material. You do not need to run it during the lab — it documents the Genie Space master toggle for completeness.
# MAGIC
# MAGIC **When would you turn this off?** Only in exceptional circumstances — for example, if the workspace is a pure pipeline workspace with no interactive users. For most regulated deployments the right approach is:
# MAGIC 1. Keep the workspace toggle ON
# MAGIC 2. Control who can access individual spaces via space sharing (Share button → add users/groups with CAN_USE)
# MAGIC 3. Apply UC row/column filters so each user only sees data they are permitted to see
# MAGIC 4. Keep geography enforcement ON so data stays in AU East
# MAGIC
# MAGIC | Layer | What it controls | Where to configure |
# MAGIC |---|---|---|
# MAGIC | `aibi_genie_space_enabled_ws_setting` | Master switch — turns off ALL Genie Spaces workspace-wide | Typed Settings API |
# MAGIC | Space sharing | Who can access a specific space | Space → Share → add users/groups with CAN_USE |
# MAGIC | UC grants | What data each user can see inside the space | GRANT SELECT ON TABLE/SCHEMA |

# COMMAND ----------

def set_genie_space_enabled(workspace_url: str, headers: dict, enabled: bool) -> dict:
    """
    Enable or disable Genie Spaces workspace-wide via the typed Settings API.

    Setting type: aibi_genie_space_enabled_ws_setting
    The API requires an ETag for optimistic concurrency — this function fetches it automatically.

    enabled=True  → Genie Spaces are available to all users with space-level access
    enabled=False → Genie Spaces are disabled across the entire workspace

    HTTP 404 means this setting is not available on this workspace tier.
    HTTP 409 Conflict means a stale ETag; re-run the cell to fetch a fresh one.
    """
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"

    # GET current state to obtain the required ETag (optimistic concurrency)
    get_resp = requests.get(url, headers=headers, timeout=30)
    if get_resp.status_code == 404:
        return {
            "status": "not_available",
            "note": "aibi_genie_space_enabled_ws_setting not found on this workspace tier"
        }
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


# Read the current Genie Space setting (read-only — safe to run)
print("Reading current Genie Space workspace setting...")
current_state = fetch_typed_setting(WORKSPACE_URL, HEADERS, "aibi_genie_space_enabled_ws_setting")
if current_state.get("status") == "not_available":
    print("aibi_genie_space_enabled_ws_setting: not available on this workspace tier")
    print("Note: Genie Spaces may still be functional — check the UI directly.")
else:
    genie_block = current_state.get("aibi_genie_space_enabled_ws_setting", {})
    is_enabled = genie_block.get("enabled", "(unknown)")
    print(f"aibi_genie_space_enabled_ws_setting.enabled = {is_enabled}")

print()
print("To toggle Genie Spaces off (uncomment and run — affects the ENTIRE workspace):")
print("  result = set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=False)")
print("To re-enable:")
print("  result = set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=True)")

# ONLY uncomment if you intentionally want to toggle the setting
# result = set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=False)
# result = set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=True)
# print(f"Updated setting: {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Supporting Material: Service Principal & Group Setup
# MAGIC
# MAGIC Automated AI workloads (scheduled inference jobs, embedding pipelines) should run as service principals — not personal accounts. This prevents workload failure when staff leave and provides a clean audit trail in `system.access.audit`.
# MAGIC
# MAGIC Groups created in the Account Console are account-level and available to all workspaces sharing that metastore. Always create AI governance groups at the account level.
# MAGIC
# MAGIC **Production recommendation — AIM (Automatic Identity Management):**
# MAGIC AIM is GA for Entra ID and is the preferred path over manual SCIM. With AIM:
# MAGIC - Users are provisioned just-in-time on first sign-in — no pre-staging required
# MAGIC - Groups sync automatically from Entra ID, including nested groups
# MAGIC - Service principals are also synced alongside human identities
# MAGIC
# MAGIC Configure at: Account Console → Security → User Provisioning → Automatic identity management
# MAGIC
# MAGIC | Group | Genie | Model serving | Playground |
# MAGIC |---|---|---|---|
# MAGIC | `grp_network_ops` | CAN_USE (meter + asset spaces) | CAN_QUERY | No |
# MAGIC | `grp_regulatory` | CAN_USE (reporting spaces only) | None | No |
# MAGIC | `grp_ai_admins` | CAN_MANAGE | CAN_MANAGE | Yes |
# MAGIC | `grp_data_science` | CAN_USE (dev) | CAN_MANAGE | Yes |
# MAGIC
# MAGIC 🖱️ **UI:** Account Console → User Management → Service Principals → Add service principal
# MAGIC After creation: SP detail page → Secrets tab → Generate secret (save immediately — shown once only).

# COMMAND ----------

from databricks.sdk.service.iam import ServicePrincipal, Group, Patch, PatchOp, PatchSchema


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
    print("Next: generate an OAuth client secret and store it in a Databricks secret scope.")
    return sp


def create_group_if_missing(w: WorkspaceClient, display_name: str) -> Group:
    """Idempotently create a workspace group. Returns existing group without error if found."""
    existing = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if existing:
        print(f"  Already exists: {display_name} (ID: {existing[0].id})")
        return existing[0]
    group = w.groups.create(display_name=display_name)
    print(f"  Created: {display_name} (ID: {group.id})")
    return group


def assign_sp_to_group(w: WorkspaceClient, sp_id: int, group_display_name: str) -> None:
    """
    Add a service principal to an existing group using SCIM PATCH.
    Use only when AIM is not yet configured — AIM syncs group membership automatically.
    """
    groups = list(w.groups.list(filter=f"displayName eq \"{group_display_name}\""))
    if not groups:
        print(f"Group '{group_display_name}' not found — create it first.")
        return
    group = groups[0]
    w.groups.patch(
        id=group.id,
        schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        operations=[Patch(op=PatchOp.ADD, path="members", value=[{"value": str(sp_id)}])]
    )
    print(f"Added SP {sp_id} to group '{group_display_name}' (group ID: {group.id})")


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


# Standard governance groups for an energy utility AI rollout
AI_GOVERNANCE_GROUPS = [
    "grp_network_ops",
    "grp_regulatory",
    "grp_ai_admins",
    "grp_data_science",
]

# --- Read-only: list current groups (safe to uncomment and run) ---
# list_all_workspace_groups(w)

# --- Create all governance groups (uncomment to execute) ---
# print("Creating AI governance groups...")
# created_groups = {}
# for group_name in AI_GOVERNANCE_GROUPS:
#     g = create_group_if_missing(w, group_name)
#     created_groups[group_name] = g
# print(f"\nAll {len(created_groups)} groups ready.")

# --- Create a service principal (uncomment to execute) ---
# sp = create_ai_service_principal(w, "svc-meter-anomaly-inference")
# secret = w.service_principal_secrets.create(service_principal_id=sp.id)
# print(f"Client ID     : {sp.application_id}")
# print(f"Client Secret : {secret.secret}  ← store in Key Vault, never in notebook source")

# --- Assign SP to group (uncomment after creating SP and groups) ---
# assign_sp_to_group(w, sp.id, "grp_ai_admins")

print("Service principal and group calls are commented out.")
print("Read-only call (list_all_workspace_groups) is safe to uncomment and run at any time.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #E8F4F1; padding: 16px; border-radius: 8px; border-left: 4px solid #00A86B">
# MAGIC <h3 style="color: #006B45; margin: 0 0 8px 0">✅ Lab 01 complete. Your workspace is configured for regulated AI use.</h3>
# MAGIC <ul>
# MAGIC <li><strong>Control 1:</strong> Geography enforcement — verified via Account Console UI (no public API available; managed via internal platform flag; changes auditable in system.access.audit as updateWorkspaceConfiguration)</li>
# MAGIC <li><strong>Control 2:</strong> Partner-Powered AI inspected via llm_proxy_partner_powered typed setting — disable if policy prohibits external partner model calls</li>
# MAGIC <li><strong>Control 3:</strong> UC permissions written for registered models, serving endpoints, and Genie Spaces</li>
# MAGIC <li><strong>Control 4:</strong> Audit logging confirmed active — AI events flowing into system.access.audit</li>
# MAGIC </ul>
# MAGIC <p><strong>Next:</strong> Lab 02: AI Gateway Setup — rate limits, guardrails, and in-region model routing</p>
# MAGIC </div>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Reference: Full REST API Cheat Sheet
# MAGIC
# MAGIC | Operation | Method | Endpoint |
# MAGIC |---|---|---|
# MAGIC | Get typed workspace setting | GET | `/api/2.0/settings/types/{type}/names/default` |
# MAGIC | Update typed workspace setting | PATCH | `/api/2.0/settings/types/{type}/names/default` |
# MAGIC | Get Genie Space workspace toggle | GET | `/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default` |
# MAGIC | Get Partner-Powered AI (workspace) | GET | `/api/2.0/settings/types/llm_proxy_partner_powered/names/default` |
# MAGIC | Disable Partner-Powered AI (workspace) | PATCH | `/api/2.0/settings/types/llm_proxy_partner_powered/names/default` body: `{"setting": {"boolean_val": {"value": false}}, "allow_missing": true, "field_mask": "boolean_val"}` |
# MAGIC | Enforce Partner-Powered AI across all workspaces (account) | PATCH | `https://accounts.azuredatabricks.net/api/2.0/accounts/{id}/settings/types/llm_proxy_partner_powered_enforce/names/default` |
# MAGIC | Get legacy workspace conf keys | GET | `/api/2.0/workspace-conf?keys=key1,key2` |
# MAGIC | Set legacy workspace conf keys | PATCH | `/api/2.0/workspace-conf` body: `{"enableResultsDownloading": "false"}` |
# MAGIC | Geography enforcement toggle | UI only | Account Console → Workspaces → Security and compliance (no public API path confirmed) |
# MAGIC | Audit geography enforcement changes | SQL | `SELECT * FROM system.access.audit WHERE action_name = 'updateWorkspaceConfiguration'` |
# MAGIC | Get Genie Space permissions | GET | `/api/2.0/permissions/dashboards/{space-id}` |
# MAGIC | Set Genie Space permissions | PATCH | `/api/2.0/permissions/dashboards/{space-id}` |
# MAGIC | Get endpoint permissions (SDK) | — | `w.serving_endpoints.get_permissions(serving_endpoint_id=...)` |
# MAGIC | Set endpoint permissions (SDK) | — | `w.serving_endpoints.update_permissions(serving_endpoint_id=..., access_control_list=[...])` |
# MAGIC | Query AI audit events | SQL | `SELECT * FROM system.access.audit WHERE service_name IN ('aibi','serverlessRealTimeInference')` |
# MAGIC | Create service principal | SDK | `w.service_principals.create(display_name=...)` |
# MAGIC | Create SP OAuth secret | SDK | `w.service_principal_secrets.create(service_principal_id=sp.id)` |
