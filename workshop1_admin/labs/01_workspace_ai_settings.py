# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 28px">🔐 Lab 01: Workspace AI Settings & Access Control</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 14px">Workshop 1: Admin Track · Australian Regulated Industries · Databricks</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 35–40 minutes |
# MAGIC | 👤 **Role** | Workspace Admin / Account Admin |
# MAGIC | ⚠️ **Data residency** | All API calls stay in AU East |
# MAGIC | 🔧 **Cluster** | DBR 14.3 LTS or later (single node is fine) |
# MAGIC
# MAGIC **By the end of this lab you will have:**
# MAGIC - [ ] Verified current AI feature flags via the REST API
# MAGIC - [ ] Confirmed the geography enforcement setting is ON (or escalated if it isn't)
# MAGIC - [ ] Reviewed Genie Space toggle behaviour at workspace level
# MAGIC - [ ] Granted UC permissions for AI assets (models, serving endpoints, Genie Spaces)
# MAGIC - [ ] Created a service principal for automated AI workloads
# MAGIC - [ ] Configured groups for business-unit-level access control
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC <div style="background: #FFF3CD; padding: 12px 16px; border-radius: 6px; border-left: 4px solid #FF6B35; margin-top: 8px">
# MAGIC <strong>🇦🇺 AU East Residency Reference — Know before you click anything</strong>
# MAGIC
# MAGIC | Feature | Status | Notes |
# MAGIC |---|---|---|
# MAGIC | Genie Spaces | ✅ In-region | Safe for regulated data |
# MAGIC | AI Gateway | ✅ In-region | Required egress point for all LLM calls |
# MAGIC | FMAPI Provisioned Throughput | ✅ In-region | Recommended for regulated inference |
# MAGIC | FMAPI Pay-Per-Token | ❌ Cross-geo | Do NOT use for APRA-classified data |
# MAGIC | Knowledge Assistant | ⚠️ Cross-geo | Workaround available — see Lab 04 |
# MAGIC | Foundation Model Fine-tuning | ❌ Not available in AU East | No ETA as of May 2026 |
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Before We Code: 8-Minute UI Tour (do this first!)
# MAGIC
# MAGIC Before running any code, spend 8 minutes clicking through the UI.
# MAGIC The goal: understand what each setting looks like so the API responses
# MAGIC you'll see later make immediate sense.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 1 — Check the account-level Geography Enforcement toggle
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC accounts.azuredatabricks.net
# MAGIC   → Settings (left sidebar)
# MAGIC     → Security & compliance
# MAGIC       → Look for "Enforce data processing within workspace Geography"
# MAGIC ```
# MAGIC
# MAGIC **What you should see:**
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────────┐
# MAGIC │  Security & Compliance                                      │
# MAGIC │                                                             │
# MAGIC │  Enforce data processing within workspace Geography         │
# MAGIC │  ● ON  ○ OFF                              [Toggle]          │
# MAGIC │                                                             │
# MAGIC │  When ON: AI features cannot route data outside the        │
# MAGIC │  workspace region (e.g. Australia East)                     │
# MAGIC └─────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **What to note:** Is the toggle ON or OFF? It must be ON for APRA-regulated workloads.
# MAGIC Section 3 of this lab will verify this via API — the UI is the ground truth.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 2 — Inspect workspace-level AI feature flags
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Your workspace (adb-XXXXX.azuredatabricks.net)
# MAGIC   → Settings (gear icon, bottom of left sidebar)
# MAGIC     → Workspace settings
# MAGIC       → Scroll to "Advanced" section
# MAGIC         → Look for the Genie Spaces toggle
# MAGIC ```
# MAGIC
# MAGIC **What to note:** Is Genie Spaces enabled or disabled?
# MAGIC The API call in Section 1 reads the same value programmatically.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 3 — Browse the Unity Catalog permission model
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC Left sidebar → Catalog (stack-of-books icon)
# MAGIC   → Browse to any catalog you own
# MAGIC     → Click a table → Permissions tab
# MAGIC ```
# MAGIC
# MAGIC **What to look for:**
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────┐
# MAGIC │  Permissions for: energy_ai.models.meter_v1     │
# MAGIC │                                                  │
# MAGIC │  Principal               Privilege               │
# MAGIC │  grp_analysts            EXECUTE                 │
# MAGIC │  grp_ai_admins           ALL PRIVILEGES          │
# MAGIC │  account users           (none)                  │
# MAGIC └─────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC This is what the GRANT SQL in Section 4 produces.
# MAGIC Section 4 automates what you would otherwise do here manually.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Task 4 — Check the Groups list
# MAGIC
# MAGIC **Where to go:**
# MAGIC ```
# MAGIC accounts.azuredatabricks.net
# MAGIC   → User management (left sidebar)
# MAGIC     → Groups tab
# MAGIC ```
# MAGIC
# MAGIC **What to note:** Do groups like `grp_network_ops` or `grp_regulatory` exist?
# MAGIC If not, Section 6 of this lab creates them via the SDK.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Time check:** This tour should take about 8 minutes.
# MAGIC Return to this notebook before continuing.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 0: Setup — Fill in your workspace details</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~3 minutes · Run this cell before anything else</p>
# MAGIC </div>
# MAGIC
# MAGIC **Two things to fill in:**
# MAGIC 1. `WORKSPACE_URL` — your workspace hostname, no trailing slash
# MAGIC 2. `DATABRICKS_TOKEN` — a personal access token (PAT). Steps below if you don't have one yet.
# MAGIC
# MAGIC ---
# MAGIC ### 🖱️ How to get a Personal Access Token (PAT)
# MAGIC
# MAGIC **Navigation:** Workspace → top-right avatar → Settings → Developer → Access tokens
# MAGIC
# MAGIC ```
# MAGIC ┌─── Databricks Workspace ─────────────────────────────────────────┐
# MAGIC │  Top-right corner:                                                │
# MAGIC │  ┌──────────────────────┐                                         │
# MAGIC │  │  👤 Your name    ▾   │  ← click your avatar / initials        │
# MAGIC │  └──────────────────────┘                                         │
# MAGIC │       │                                                            │
# MAGIC │       ├── ⚙️  Settings                ← click here               │
# MAGIC │       │        │                                                   │
# MAGIC │       │        └── 🔧 Developer                                    │
# MAGIC │       │                 └── Access tokens   ← manage here         │
# MAGIC │       └── (other menu items)                                       │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC On the Access tokens page:
# MAGIC 1. Click **Generate new token**
# MAGIC 2. Add a comment like `workshop-lab-01`
# MAGIC 3. Set lifetime to **1 day** (enough for the workshop)
# MAGIC 4. Click **Generate** — copy the token value immediately (shown once only)
# MAGIC
# MAGIC > 💡 **Better practice:** Store the token in a secret scope so it never appears
# MAGIC > in notebook source. The cell below tries `dbutils.secrets.get` first and falls
# MAGIC > back to a direct paste — use the secret approach in any shared workspace.

# COMMAND ----------

import os
import json
import requests

# TODO: Replace with your workspace URL (no trailing slash)
# Example: "https://adb-1234567890123456.7.azuredatabricks.net"
WORKSPACE_URL = "https://<your-workspace>.azuredatabricks.net"

# TODO: Choose ONE of the following token approaches and comment out the other.

# Option A (recommended): pull from a Databricks secret scope
# DATABRICKS_TOKEN = dbutils.secrets.get(scope="admin-workshop", key="workspace-token")

# Option B: paste directly (OK for a training lab — never do this in production)
DATABRICKS_TOKEN = "<paste-your-pat-here>"

# Derived — do not edit below this line
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json",
}

print(f"Workspace URL : {WORKSPACE_URL}")
print("Token         : [loaded]")

# COMMAND ----------

# MAGIC %md
# MAGIC #### ✅ Expected output after the setup cell:
# MAGIC ```
# MAGIC Workspace URL : https://adb-xxxxxxxxxxxx.7.azuredatabricks.net
# MAGIC Token         : [loaded]
# MAGIC ```
# MAGIC
# MAGIC > ⚠️ **If you still see `<your-workspace>` in the URL**: you haven't edited
# MAGIC > `WORKSPACE_URL` yet. Go back and replace the placeholder before running
# MAGIC > any of the cells below.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 1: Inspect Current Workspace AI Feature Status</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~8 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC The Databricks Settings API uses a **typed namespace** pattern. Each feature flag
# MAGIC has its own endpoint path under `/api/2.0/settings/types/{type}/names/default`.
# MAGIC
# MAGIC **What we are checking:**
# MAGIC
# MAGIC | Setting type | API family | Controls |
# MAGIC |---|---|---|
# MAGIC | `aibi_genie_space_enabled_ws_setting` | Typed Settings API | Genie Spaces on/off for this workspace |
# MAGIC | `restrict_workspace_admins` | Typed Settings API | Limits what non-admin users can do |
# MAGIC | `enableExportNotebook` | Legacy workspace-conf API | Whether users can download notebook source |
# MAGIC | `enableResultsDownloading` | Legacy workspace-conf API | Whether query results can be exported to CSV |
# MAGIC
# MAGIC **Why two different APIs?** The newer typed Settings API only covers a subset of
# MAGIC controls. Older guards (notebook export, results download) remain on the legacy
# MAGIC `/api/2.0/workspace-conf` endpoint. Trying them via the typed path returns a 404.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find workspace settings in the UI first
# MAGIC
# MAGIC Before running the API, spend 2 minutes locating these toggles in the console
# MAGIC so you understand exactly what the API is querying.
# MAGIC
# MAGIC **Navigation:** Workspace sidebar → ⚙️ Settings (gear icon, very bottom of sidebar)
# MAGIC
# MAGIC ```
# MAGIC ┌─── Databricks Workspace ─────────────────────────────────────────┐
# MAGIC │  Left sidebar (scroll to the bottom):                             │
# MAGIC │  ├── 🏠 Home                                                       │
# MAGIC │  ├── 📊 Catalog                                                    │
# MAGIC │  ├── 💻 Compute                                                    │
# MAGIC │  ├── ...                                                           │
# MAGIC │  └── ⚙️  Settings          ← click here (gear icon)              │
# MAGIC │            │                                                        │
# MAGIC │            ├── Workspace settings     ← export/download toggles    │
# MAGIC │            ├── AI & Machine Learning  ← AI feature toggles         │
# MAGIC │            └── Advanced                                             │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Under "Workspace settings"** you will see toggle switches including:
# MAGIC - "Allow users to download notebook results" → maps to `enableResultsDownloading`
# MAGIC - "Allow users to export notebooks" → maps to `enableExportNotebook`
# MAGIC
# MAGIC **Under "AI & Machine Learning"** you will see:
# MAGIC - Genie toggle → maps to `aibi_genie_space_enabled_ws_setting`
# MAGIC - AI Playground toggle
# MAGIC - Mosaic AI Agent Framework toggle
# MAGIC
# MAGIC > 💡 **Can't find Settings?** Make sure you are in the **workspace** console
# MAGIC > (e.g. `adb-xxxx.7.azuredatabricks.net`), not the Account Console
# MAGIC > (`accounts.azuredatabricks.net`). They are separate UIs with different sidebars.

# COMMAND ----------

# NOTE: The typed Settings API only covers a subset of workspace controls.
# Attempting typed API for legacy keys (enableExportNotebook etc.) returns 404.
AI_SETTING_TYPES = [
    "aibi_genie_space_enabled_ws_setting",
    "restrict_workspace_admins",
]

# These must come from the legacy workspace-conf endpoint
WORKSPACE_CONF_KEYS = [
    "enableNotebookTableClipboard",   # whether users can export notebook output cells
    "enableResultsDownloading",       # whether query results can be downloaded to CSV
    "enableExportNotebook",           # whether notebooks can be downloaded as .ipynb/.py
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
# MAGIC #### ✅ Expected output — Section 1:
# MAGIC ```
# MAGIC Setting Type                                         Raw value
# MAGIC ────────────────────────────────────────────────────────────────────────────────
# MAGIC aibi_genie_space_enabled_ws_setting                  {'enabled': True}
# MAGIC restrict_workspace_admins                            {'allowed_bag': ...}
# MAGIC
# MAGIC Workspace-conf key                                   Value
# MAGIC ────────────────────────────────────────────────────────────────────────────────
# MAGIC enableNotebookTableClipboard                         true
# MAGIC enableResultsDownloading                             true
# MAGIC enableExportNotebook                                 true
# MAGIC ```
# MAGIC
# MAGIC **For an APRA-regulated workspace, the recommended hardened values are:**
# MAGIC
# MAGIC | Key | Recommended | Why |
# MAGIC |---|---|---|
# MAGIC | `enableResultsDownloading` | `false` | Prevents bulk data exfiltration via CSV download |
# MAGIC | `enableExportNotebook` | `false` | Prevents code + embedded credentials leaving the platform |
# MAGIC | `aibi_genie_space_enabled_ws_setting` | `true` (controlled via UC grants) | AI/BI is in-region; restrict per-user via UC, not by disabling globally |
# MAGIC
# MAGIC > ⚠️ **If `enableResultsDownloading` or `enableExportNotebook` is `true` in a regulated
# MAGIC > workspace**: flag this to your CISO. You can fix it in the UI under
# MAGIC > ⚙️ Settings → Workspace settings without any API call.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 2: Enable / Disable Genie Spaces at Workspace Level</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~5 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC **Why this matters for regulated industries:**
# MAGIC
# MAGIC Genie Spaces execute queries in-region (AU East) — they are **safe for regulated data**.
# MAGIC However, you may still need to temporarily disable the feature workspace-wide while
# MAGIC an APRA CPS 234 or CPS 230 review is underway, or while you set up the correct UC
# MAGIC access controls. The workspace-level toggle is the **coarsest** control available.
# MAGIC Finer-grained per-user and per-table access is handled via Unity Catalog grants
# MAGIC (see Section 4).

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find the Genie Space toggle in the UI
# MAGIC
# MAGIC **Navigation:** ⚙️ Settings → AI & Machine Learning
# MAGIC
# MAGIC ```
# MAGIC ┌─── Workspace Settings ───────────────────────────────────────────┐
# MAGIC │  ⚙️  Settings                                                     │
# MAGIC │      ├── Workspace settings                                       │
# MAGIC │      ├── AI & Machine Learning   ← click here                    │
# MAGIC │      └── Advanced                                                 │
# MAGIC │                                                                   │
# MAGIC │  Under "AI & Machine Learning":                                   │
# MAGIC │  ┌─────────────────────────────────────────────────────────┐      │
# MAGIC │  │  Genie                                          [●  ON]  │      │
# MAGIC │  │  AI/BI Dashboards                               [●  ON]  │      │
# MAGIC │  │  AI Playground                                  [●  ON]  │      │
# MAGIC │  │  Mosaic AI Agent Framework                      [●  ON]  │      │
# MAGIC │  └─────────────────────────────────────────────────────────┘      │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC The "Genie" toggle corresponds directly to `aibi_genie_space_enabled_ws_setting`.
# MAGIC Flipping it in the UI is equivalent to running the PATCH call below.
# MAGIC
# MAGIC > 💡 **Rule of thumb:** Only disable Genie globally if you have no UC access
# MAGIC > control in place yet. Once UC grants are configured (Section 4), leave the
# MAGIC > global toggle ON and restrict at the UC level for finer granularity.

# COMMAND ----------

def set_genie_space_enabled(workspace_url: str, headers: dict, enabled: bool) -> dict:
    """
    Enable or disable Genie Spaces at the workspace level via the Settings API.

    The API uses optimistic concurrency — you must GET the current ETag and include
    it in the PATCH body. This function handles that automatically.

    Parameters
    ----------
    enabled : bool
        True to enable Genie Spaces, False to disable.
    """
    url = f"{workspace_url}/api/2.0/settings/types/aibi_genie_space_enabled_ws_setting/names/default"

    payload = {
        "setting_name": "default",
        "aibi_genie_space_enabled_ws_setting": {
            "enabled": enabled
        }
    }

    # GET the current state first to obtain the required ETag
    get_response = requests.get(url, headers=headers, timeout=30)
    if get_response.status_code == 200:
        etag = get_response.json().get("etag", "")
        if etag:
            payload["etag"] = etag

    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# TODO: Uncomment ONE of the lines below and run this cell to change the setting.
# The cell is safe to run commented-out — it only prints instructions.

# set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=True)   # Turn Genie on
# set_genie_space_enabled(WORKSPACE_URL, HEADERS, enabled=False)  # Turn Genie off

print("Genie Space toggle: commented out for safety.")
print("Uncomment the appropriate line above to make a change.")
print()
print("Equivalent UI action: ⚙️ Settings → AI & Machine Learning → Genie toggle")

# COMMAND ----------

# MAGIC %md
# MAGIC #### ✅ Expected output if you uncomment the enable call:
# MAGIC ```json
# MAGIC {
# MAGIC   "setting_name": "default",
# MAGIC   "aibi_genie_space_enabled_ws_setting": {
# MAGIC     "enabled": true
# MAGIC   },
# MAGIC   "etag": "some-etag-string"
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC > ⚠️ **HTTP 409 Conflict?** The ETag is stale — someone else changed the setting
# MAGIC > between your GET and PATCH. Simply re-run the cell; `set_genie_space_enabled`
# MAGIC > fetches a fresh ETag on every call and will succeed on the second attempt.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 3: Verify "Enforce Data Processing Within Geography"</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~7 minutes · Requires Account Admin role</p>
# MAGIC </div>
# MAGIC
# MAGIC This is the **single most important compliance setting** for APRA-regulated entities.
# MAGIC When enabled, it prevents Databricks platform features from routing data to regions
# MAGIC outside the workspace's primary geography (AU East for Australian workspaces).
# MAGIC
# MAGIC **Who can change it:** Account Admins only. Workspace Admins who are not also
# MAGIC Account Admins will receive a 403 — this is expected and correct behaviour.
# MAGIC
# MAGIC **API note:** This setting lives under the **Account API** at
# MAGIC `accounts.azuredatabricks.net`, a different hostname from your workspace URL.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find this setting in the Account Console
# MAGIC
# MAGIC **Navigation:** Account Console (accounts.cloud.databricks.com) → Workspaces → [workspace name] → **Security and compliance** tab
# MAGIC
# MAGIC > ⚠️ This setting is NOT under "Settings → AI & Machine Learning". It lives on the
# MAGIC > workspace detail page in the Account Console under the **Security and compliance** tab.
# MAGIC
# MAGIC ```
# MAGIC ┌─── Account Console (accounts.azuredatabricks.net) ───────────────┐
# MAGIC │  Left sidebar:                                                    │
# MAGIC │  ├── 🏠 Home                                                       │
# MAGIC │  └── 🏢 Workspaces          ← click here                         │
# MAGIC │            │                                                        │
# MAGIC │            └── [your workspace name]  ← click the workspace       │
# MAGIC │                 │                                                   │
# MAGIC │                 ├── Overview tab                                    │
# MAGIC │                 ├── Security and compliance tab  ← CLICK THIS TAB │
# MAGIC │                 │       │                                           │
# MAGIC │                 │       └── "Enforce data processing within        │
# MAGIC │                 │            workspace geography"  [toggle]         │
# MAGIC │                 │                ← THIS ONE ← MUST BE ON           │
# MAGIC │                 └── ...other tabs                                   │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **For any APRA-regulated workspace, this toggle MUST be ON (blue).**
# MAGIC If it is OFF (grey), stop this lab and enable it before doing anything else —
# MAGIC cross-geo data processing may already be occurring.
# MAGIC
# MAGIC > 💡 **Your Account ID** is also on this page under "Account information",
# MAGIC > or visible in the URL:
# MAGIC > `accounts.azuredatabricks.net/account/<your-account-id>/...`

# COMMAND ----------

# TODO: Replace with your Databricks Account ID
# Found in: Account Console → Settings → Account information
# Or from the URL: accounts.azuredatabricks.net/account/<id>/...
ACCOUNT_ID = "<your-account-id>"


def get_enforce_geography_setting(account_id: str, headers: dict) -> dict:
    """
    Check whether 'Enforce data processing within workspace Geography' is enabled.
    Requires Account Admin permissions.
    Returns a dict with the setting payload, or an error key explaining the failure.
    """
    url = (
        f"https://accounts.azuredatabricks.net/api/2.0/accounts/{account_id}"
        f"/settings/types/shield_csp_enforcement_account_setting/names/default"
    )
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 403:
        return {
            "error": "403 Forbidden",
            "detail": "You need Account Admin role to read this setting.",
            "action": "Ask your Account Admin to run this cell, or verify the toggle manually in the Account Console.",
        }
    if response.status_code == 404:
        return {
            "error": "404 Not found",
            "detail": "This account may not have the Compliance Security Profile feature enabled.",
            "action": "Contact your Databricks account team to enable it.",
        }
    response.raise_for_status()
    return response.json()


geography_setting = get_enforce_geography_setting(ACCOUNT_ID, HEADERS)
print("=== Geography Enforcement Setting ===")
print(json.dumps(geography_setting, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC #### ✅ Expected output — compliant workspace:
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
# MAGIC **If `csp` is absent or anything other than `COMPLIANCE_SECURITY_PROFILE`:**
# MAGIC stop here — enable the setting in the Account Console before continuing.
# MAGIC
# MAGIC > ⚠️ **403 response?** Expected if you are a workspace-only admin. Ask your
# MAGIC > Account Admin to verify the toggle in the Account Console.

# COMMAND ----------

def compliance_check_geography(setting_response: dict) -> None:
    """
    Print a formatted pass/fail compliance check for the geography enforcement setting.
    Handles three outcomes: compliant, non-compliant, permission denied.
    """
    if "error" in setting_response:
        print(f"⚠️  CANNOT VERIFY — {setting_response['error']}")
        print(f"   Detail : {setting_response.get('detail', '')}")
        print(f"   Action : {setting_response.get('action', '')}")
        return

    csp_block = setting_response.get("shield_csp_enforcement_account_setting", {})
    csp_value = csp_block.get("csp", "")

    print("─" * 60)
    if csp_value == "COMPLIANCE_SECURITY_PROFILE":
        print("✅  PASS — Enforce data processing within Geography: ENABLED")
        print("    Regulated workloads are protected from cross-geo routing.")
        print("    APRA CPS 234 data residency requirement: MET")
    else:
        print("❌  FAIL — Enforce data processing within Geography: NOT ENABLED")
        print(f"    Current value : '{csp_value or '(not set)'}'")
        print()
        print("    IMMEDIATE ACTION REQUIRED:")
        print("    1. Open accounts.azuredatabricks.net in a new tab")
        print("    2. Go to Settings → Account information")
        print("    3. Enable 'Enforce data processing within workspace geography'")
        print("    4. Re-run this cell to confirm the change took effect")
    print("─" * 60)


compliance_check_geography(geography_setting)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 🔍 Checkpoint: Before You Continue
# MAGIC
# MAGIC Run the cell below to verify your Section 1–3 setup before moving on to
# MAGIC Unity Catalog permissions.

# COMMAND ----------

print("=" * 60)
print("  Checkpoint — Sections 1–3")
print("=" * 60)
print()

checks = []

# Check 1: workspace URL configured
if "<your-workspace>" in WORKSPACE_URL:
    checks.append(("Workspace URL configured", False, "Still contains placeholder — update WORKSPACE_URL"))
else:
    checks.append(("Workspace URL configured", True, WORKSPACE_URL))

# Check 2: token looks real
if "<paste" in DATABRICKS_TOKEN or len(DATABRICKS_TOKEN) < 20:
    checks.append(("Token set", False, "Token appears to be a placeholder — update DATABRICKS_TOKEN"))
else:
    checks.append(("Token set", True, "Token loaded (length OK)"))

# Check 3: account ID configured
if "<your-account-id>" in ACCOUNT_ID:
    checks.append(("Account ID set", False, "Still placeholder — set ACCOUNT_ID to verify geography setting"))
else:
    checks.append(("Account ID set", True, ACCOUNT_ID))

# Check 4: geography setting result
if isinstance(geography_setting, dict):
    if "error" in geography_setting:
        checks.append(("Geography enforcement verified", False, geography_setting["error"]))
    else:
        csp = geography_setting.get("shield_csp_enforcement_account_setting", {}).get("csp", "")
        if csp == "COMPLIANCE_SECURITY_PROFILE":
            checks.append(("Geography enforcement verified", True, "ENABLED — compliant"))
        else:
            checks.append(("Geography enforcement verified", False, f"NOT ENABLED — current: '{csp}'"))
else:
    checks.append(("Geography enforcement verified", False, "geography_setting not available"))

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
    print("⚠️  Fix the items marked ❌ above before proceeding.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 4: Unity Catalog Permissions for AI Assets</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~10 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC AI features in Databricks are governed through Unity Catalog just like any other
# MAGIC data asset. The table below maps asset types to permissions for a typical energy
# MAGIC utility or APRA-regulated organisation:
# MAGIC
# MAGIC | Asset type | Typical GRANT | Typical REVOKE |
# MAGIC |---|---|---|
# MAGIC | Registered model | `EXECUTE` for inference, `APPLY TAG` for governance | `ALL PRIVILEGES` from `account users` |
# MAGIC | Model serving endpoint | `CAN_QUERY` for consumers | `CAN_MANAGE` from non-admins |
# MAGIC | AI Gateway endpoint | `CAN_QUERY` | — |
# MAGIC | Genie Space | `CAN_USE` | `CAN_MANAGE` from non-admins |
# MAGIC | Vector Search index | `SELECT` | — |
# MAGIC | External model | `EXECUTE` | — |
# MAGIC
# MAGIC **Why not just use workspace-level access?** UC grants travel with the asset
# MAGIC across workspaces sharing the same metastore. If your organisation has separate
# MAGIC prod/dev/test workspaces, a UC GRANT gives one consistent policy regardless of
# MAGIC which workspace a user is in.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Explore Unity Catalog before running SQL
# MAGIC
# MAGIC **Navigation:** Workspace sidebar → 📊 Catalog
# MAGIC
# MAGIC ```
# MAGIC ┌─── Databricks Workspace ─────────────────────────────────────────┐
# MAGIC │  Left sidebar:                                                    │
# MAGIC │  ├── 🏠 Home                                                       │
# MAGIC │  ├── 📊 Catalog            ← click here                           │
# MAGIC │  │       │                                                          │
# MAGIC │  │       ├── [catalog name]     (e.g. energy_ai)                   │
# MAGIC │  │       │       ├── [schema]   (e.g. models)                      │
# MAGIC │  │       │       │       └── Tables / Views / Models / Functions   │
# MAGIC │  │       │       └── Permissions tab  ← view current grants here   │
# MAGIC │  │       └── + Create catalog                                       │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC Navigate to any model, click the **Permissions** tab to see the current grant
# MAGIC list. The SQL `GRANT` statements below produce entries visible there.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a. Grant permissions on a registered model

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

-- Allow the AI admins group to fully manage the model (register versions, delete, etc.)
GRANT ALL PRIVILEGES ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME}
  TO `{ADMIN_GROUP}`;

-- Verify the grants were applied
SHOW GRANTS ON MODEL {CATALOG_NAME}.{SCHEMA_NAME}.{MODEL_NAME};
"""

print("SQL to run — copy into a %sql cell or use spark.sql():\n")
print(grant_model_sql)
print("Or uncomment the spark.sql calls in the next cell to execute directly.")

# COMMAND ----------

# Execute the GRANT statements via spark.sql.
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
# MAGIC #### ✅ Expected output after GRANT + SHOW GRANTS:
# MAGIC ```
# MAGIC Principal        | Privilege       | Object type | Object name
# MAGIC grp_analysts     | EXECUTE         | FUNCTION    | energy_ai.models.meter_anomaly_v1
# MAGIC grp_ai_admins    | ALL PRIVILEGES  | FUNCTION    | energy_ai.models.meter_anomaly_v1
# MAGIC ```
# MAGIC
# MAGIC > 💡 **Confirm in the UI:** After running the GRANT, go to
# MAGIC > 📊 Catalog → energy_ai → models → meter_anomaly_v1 → **Permissions** tab.
# MAGIC > Both groups should appear in the list.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Grant permissions on a model serving endpoint

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find serving endpoints in the UI
# MAGIC
# MAGIC **Navigation:** Workspace sidebar → Machine Learning → Serving
# MAGIC
# MAGIC ```
# MAGIC ┌─── Databricks Workspace ─────────────────────────────────────────┐
# MAGIC │  Left sidebar:                                                    │
# MAGIC │  ├── 🏠 Home                                                       │
# MAGIC │  ├── 🤖 Machine Learning                                           │
# MAGIC │  │       ├── Experiments                                           │
# MAGIC │  │       ├── Models              (MLflow model registry)           │
# MAGIC │  │       └── Serving             ← click here                     │
# MAGIC │  │              │                                                   │
# MAGIC │  │              └── [list of endpoints]                            │
# MAGIC │  │                    └── [endpoint name]   ← click an endpoint   │
# MAGIC │  │                           └── Permissions tab  ← set here      │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC The **Permissions** tab on any endpoint shows current CAN_QUERY / CAN_MANAGE /
# MAGIC IS_OWNER assignments. The SDK call below produces the same result programmatically.

# COMMAND ----------

# TODO: Fill in your endpoint name
ENDPOINT_NAME = "meter-anomaly-endpoint"  # TODO: your model serving endpoint name

grant_endpoint_sql = f"""
-- Allow analysts to query the endpoint (run predictions)
GRANT CAN_QUERY ON SERVING ENDPOINT `{ENDPOINT_NAME}`
  TO `{CONSUMER_GROUP}`;

-- Allow AI admins to manage the endpoint (scale, update config, delete)
GRANT CAN_MANAGE ON SERVING ENDPOINT `{ENDPOINT_NAME}`
  TO `{ADMIN_GROUP}`;

-- Verify
SHOW GRANTS ON SERVING ENDPOINT `{ENDPOINT_NAME}`;
"""

print("SQL to run:\n")
print(grant_endpoint_sql)

# COMMAND ----------

# Use the Databricks SDK to set endpoint permissions programmatically.
# Equivalent to the SQL GRANT above but automatable in deployment pipelines.
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServingEndpointAccessControlRequest,
    ServingEndpointPermissionLevel,
)

w = WorkspaceClient()  # Reads DATABRICKS_HOST and DATABRICKS_TOKEN from environment

# TODO: Uncomment and run after setting ENDPOINT_NAME and group variables
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
# print(f"SDK permissions set on endpoint: {ENDPOINT_NAME}")

print("SDK permission call is commented out — uncomment after setting variable values.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4c. Grant permissions on a Genie Space

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find a Genie Space ID in the UI
# MAGIC
# MAGIC **Navigation:** Workspace sidebar → 🧞 Genie (or search "Genie" in the top search bar)
# MAGIC
# MAGIC ```
# MAGIC ┌─── Databricks Workspace ─────────────────────────────────────────┐
# MAGIC │  Left sidebar:                                                    │
# MAGIC │  ├── 🏠 Home                                                       │
# MAGIC │  ├── 🧞 Genie               ← click here                          │
# MAGIC │  │       └── [list of Genie Spaces]                               │
# MAGIC │  │              └── [Space name]    ← click a space               │
# MAGIC │  │                                                                  │
# MAGIC │  Look at the URL bar in your browser:                              │
# MAGIC │  https://adb-xxxx.7.azuredatabricks.net/genie/spaces/<SPACE-ID>   │
# MAGIC │                                                      ^^^^^^^^^^^^  │
# MAGIC │                                           copy this ID             │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Setting permissions on a Genie Space via the UI:**
# MAGIC 1. Open the Genie Space
# MAGIC 2. Click the **⋯ kebab menu** (top-right corner of the Space)
# MAGIC 3. Select **Share** or **Permissions**
# MAGIC 4. Add groups: CAN_USE for viewers, CAN_EDIT for editors, CAN_MANAGE for admins
# MAGIC
# MAGIC The REST API call below is useful for automated post-deployment configuration.

# COMMAND ----------

# TODO: Replace with your Genie Space ID (copy from the browser URL)
GENIE_SPACE_ID = "<your-genie-space-id>"  # TODO


def get_genie_space_permissions(workspace_url: str, headers: dict, genie_space_id: str) -> dict:
    """Fetch current permissions for a Genie Space via the dashboards permissions API."""
    url = f"{workspace_url}/api/2.0/permissions/dashboards/{genie_space_id}"
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
    permission_level: str,  # "CAN_USE", "CAN_EDIT", or "CAN_MANAGE"
) -> dict:
    """Grant a group access to a Genie Space. Safe to call multiple times (PATCH is additive)."""
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

print("Genie Space permission calls are commented out — uncomment after setting GENIE_SPACE_ID.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 5: Create a Service Principal for AI Workloads</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~7 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC Automated AI workloads (scheduled inference jobs, embedding pipelines, regulatory
# MAGIC report generation) should run as **service principals** rather than personal accounts.
# MAGIC This approach:
# MAGIC
# MAGIC - Prevents workload failure when a staff member leaves or changes teams
# MAGIC - Provides a clean audit trail in `system.access.audit` (SP identity, not human email)
# MAGIC - Enables least-privilege access — the SP only gets what the workload needs
# MAGIC - Allows credential rotation without disrupting multiple workloads

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find Service Principals in the Account Console
# MAGIC
# MAGIC **Navigation:** accounts.azuredatabricks.net → 🔐 Service principals (left sidebar)
# MAGIC
# MAGIC ```
# MAGIC ┌─── Account Console (accounts.azuredatabricks.net) ───────────────┐
# MAGIC │  Left sidebar:                                                    │
# MAGIC │  ├── 🏠 Home                                                       │
# MAGIC │  ├── 🏢 Workspaces                                                 │
# MAGIC │  ├── 👥 Users & groups                                             │
# MAGIC │  ├── 🔐 Service principals   ← click here                         │
# MAGIC │  │       │                                                          │
# MAGIC │  │       └── [list of existing SPs]                                │
# MAGIC │  │              └── [SP name]                                       │
# MAGIC │  │                     ├── Roles tab     (account-level roles)     │
# MAGIC │  │                     ├── Groups tab    (group memberships)       │
# MAGIC │  │                     └── Secrets tab   (OAuth client secrets)   │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **To create a Service Principal via the UI:**
# MAGIC 1. Click **Add service principal** (top-right button)
# MAGIC 2. Enter a name following the convention `svc-<workload>` (e.g. `svc-meter-anomaly-inference`)
# MAGIC 3. Click **Add** — the SP appears in the list immediately
# MAGIC 4. Click the SP → **Secrets** tab → **Generate secret** to create an OAuth credential
# MAGIC 5. Copy the Client Secret value immediately (it is shown only once)
# MAGIC
# MAGIC The SDK call below automates steps 1–3.

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
    print(f"✅  Created service principal: {sp.display_name}")
    print(f"    Application ID : {sp.application_id}")
    print(f"    Internal ID    : {sp.id}")
    print()
    print("Next steps:")
    print("  1. Generate an OAuth client secret:")
    print("     secret = w.service_principal_secrets.create(service_principal_id=sp.id)")
    print("  2. Store secret.secret in Azure Key Vault or a Databricks secret scope")
    print("  3. Assign the SP to the relevant group (see next cell)")
    return sp


# TODO: Uncomment and customise the name, then run
# sp = create_ai_service_principal(w, "svc-meter-anomaly-inference")

# After creating the SP, generate an OAuth secret:
# Note: w.service_principal_secrets is a separate API from w.service_principals
# secret = w.service_principal_secrets.create(service_principal_id=sp.id)
# print(f"Client ID     : {sp.application_id}")
# print(f"Client Secret : {secret.secret}  ← store in Key Vault, never in notebook source")

print("Service principal creation is commented out — safe to run in a non-prod workspace.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5b. Assign the service principal to groups

# COMMAND ----------

from databricks.sdk.service.iam import Group

def assign_sp_to_group(w: WorkspaceClient, sp_id: int, group_display_name: str) -> None:
    """
    Add a service principal to an existing workspace group using SCIM PATCH.
    Idempotent — safe to call multiple times; the group membership won't be duplicated.
    """
    groups = list(w.groups.list(filter=f"displayName eq \"{group_display_name}\""))
    if not groups:
        print(f"❌  Group '{group_display_name}' not found in this workspace.")
        print(f"    Create it first in Section 6, then retry.")
        return

    group = groups[0]
    w.groups.patch(
        id=group.id,
        operations=[{
            "op": "add",
            "path": "members",
            "value": [{"value": str(sp_id)}]
        }]
    )
    print(f"✅  Added SP {sp_id} to group '{group_display_name}' (group ID: {group.id})")


# TODO: After creating the SP above, assign it to the AI admin group
# assign_sp_to_group(w, sp.id, ADMIN_GROUP)

print("SP group assignment is commented out — run after creating the service principal.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 6: Configure Groups for Business Unit AI Access</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~5 minutes</p>
# MAGIC </div>
# MAGIC
# MAGIC In a regulated utility (electricity network operator, gas distributor, AEMO, etc.),
# MAGIC you typically need distinct groups with different AI access levels:
# MAGIC
# MAGIC | Group | Genie | Model serving | Playground | Notes |
# MAGIC |---|---|---|---|---|
# MAGIC | `grp_network_ops` | CAN_USE (meter + asset spaces) | CAN_QUERY | No | Day-to-day operations |
# MAGIC | `grp_regulatory` | CAN_USE (reporting spaces only) | None | No | Regulatory reporting team |
# MAGIC | `grp_ai_admins` | CAN_MANAGE | CAN_MANAGE | Yes | Data + AI platform team |
# MAGIC | `grp_data_science` | CAN_USE (dev workspaces) | CAN_MANAGE | Yes | Model builders |
# MAGIC
# MAGIC > 💡 **Production recommendation:** Sync these groups from Azure AD / Entra ID via
# MAGIC > SCIM provisioning rather than creating them manually. This keeps group membership
# MAGIC > in sync with your HR system automatically. Find the SCIM endpoint in the Account
# MAGIC > Console → Settings → Identity and Access → SCIM provisioning.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### 🖱️ Find Groups in the Account Console
# MAGIC
# MAGIC **Navigation:** accounts.azuredatabricks.net → 👥 Users & groups → Groups tab
# MAGIC
# MAGIC ```
# MAGIC ┌─── Account Console ──────────────────────────────────────────────┐
# MAGIC │  Left sidebar:                                                    │
# MAGIC │  ├── 👥 Users & groups      ← click here                         │
# MAGIC │  │       │                                                          │
# MAGIC │  │       ├── Users tab                                             │
# MAGIC │  │       └── Groups tab      ← then click Groups                  │
# MAGIC │  │               │                                                  │
# MAGIC │  │               ├── + Add group   (top-right button)              │
# MAGIC │  │               └── [list of existing groups]                     │
# MAGIC │  │                       └── [group name]                          │
# MAGIC │  │                              ├── Members tab                    │
# MAGIC │  │                              └── Entitlements tab               │
# MAGIC └──────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC > ⚠️ **Important:** Groups created in the Account Console are account-level groups
# MAGIC > available to all workspaces sharing that metastore. Groups created inside
# MAGIC > a workspace's Admin settings are workspace-local and cannot be shared.
# MAGIC > **Always create AI governance groups at the account level.**

# COMMAND ----------

def create_group_if_missing(w: WorkspaceClient, display_name: str) -> Group:
    """
    Idempotently create a workspace group.
    If the group already exists, returns it without raising an error.
    Safe to call in CI/CD deployment pipelines.
    """
    existing = list(w.groups.list(filter=f"displayName eq \"{display_name}\""))
    if existing:
        print(f"  ℹ️   Already exists: {display_name} (ID: {existing[0].id})")
        return existing[0]

    group = w.groups.create(display_name=display_name)
    print(f"  ✅  Created: {display_name} (ID: {group.id})")
    return group


# Standard governance groups for an energy utility AI rollout
AI_GOVERNANCE_GROUPS = [
    "grp_network_ops",    # operational users, day-to-day AI queries
    "grp_regulatory",     # regulatory reporting team, read-only AI access
    "grp_ai_admins",      # platform team, full AI/ML admin
    "grp_data_science",   # model builders, dev-only full access
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
# MAGIC <div style="border-left: 4px solid #FF3621; padding-left: 16px; margin: 24px 0">
# MAGIC <h2 style="color: #1B3139; margin: 0">Section 7: Lab Summary & Final Checkpoint</h2>
# MAGIC <p style="color: #666; margin: 4px 0 0 0">⏱️ ~2 minutes</p>
# MAGIC </div>

# COMMAND ----------

print("=" * 60)
print("  Lab 01 — Final Checkpoint Summary")
print("=" * 60)
print()

outcomes = [
    ("Section 1", "Workspace AI feature flags queried via REST API",       True),
    ("Section 1", "Legacy workspace-conf keys (export, results) reviewed", True),
    ("Section 2", "Genie Space toggle mechanism understood",               True),
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
print("  Duration  : 40–45 minutes")
print("─" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #E8F4F1; padding: 16px; border-radius: 8px; border-left: 4px solid #00A86B">
# MAGIC <h3 style="color: #006B45; margin: 0 0 8px 0">✅ Lab 01 Complete</h3>
# MAGIC <p>You have successfully:</p>
# MAGIC <ul>
# MAGIC <li>Queried workspace AI feature flags via the typed Settings API and the legacy workspace-conf API</li>
# MAGIC <li>Located the geography enforcement setting in both the API response and the Account Console UI</li>
# MAGIC <li>Reviewed how to toggle Genie Spaces at the workspace level (UI + API)</li>
# MAGIC <li>Written GRANT SQL and SDK calls for registered models, serving endpoints, and Genie Spaces</li>
# MAGIC <li>Reviewed how to create a service principal and generate OAuth credentials for automated workloads</li>
# MAGIC <li>Designed a group structure appropriate for an energy utility AI governance model</li>
# MAGIC </ul>
# MAGIC <p><strong>Next:</strong> &rarr; Lab 02: AI Gateway Setup</p>
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
# MAGIC | Get legacy workspace conf keys | GET | `/api/2.0/workspace-conf?keys=key1,key2` |
# MAGIC | Update legacy workspace conf keys | PATCH | `/api/2.0/workspace-conf` (JSON body) |
# MAGIC | Get account geography setting | GET | `accounts.azuredatabricks.net/api/2.0/accounts/{id}/settings/types/shield_csp_enforcement_account_setting/names/default` |
# MAGIC | List serving endpoints | GET | `/api/2.0/serving-endpoints` |
# MAGIC | Get endpoint permissions | GET | `/api/2.0/permissions/serving-endpoints/{name}` |
# MAGIC | Get Genie Space permissions | GET | `/api/2.0/permissions/dashboards/{space-id}` |
# MAGIC | Set Genie Space permissions | PATCH | `/api/2.0/permissions/dashboards/{space-id}` |
# MAGIC | List groups | GET | `/api/2.0/preview/scim/v2/Groups` |
# MAGIC | Create service principal | POST | `/api/2.0/preview/scim/v2/ServicePrincipals` |
# MAGIC | Create SP OAuth secret | POST | `/api/2.0/accounts/{id}/servicePrincipals/{sp-id}/credentials/secrets` |
