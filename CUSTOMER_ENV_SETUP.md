# Running the Workshop in a Customer Databricks Environment

This guide is for Databricks SAs who need to run the AU AI Workshops **inside a customer's own Databricks workspace** rather than a Databricks Credit Program workspace. Read the [FACILITATOR_GUIDE.md](FACILITATOR_GUIDE.md) first — this document only covers the delta for customer environments.

---

## Contents

1. [Why customer environments need extra preparation](#1-why-customer-environments-need-extra-preparation)
2. [Prerequisites — what must be true before you arrive](#2-prerequisites--what-must-be-true-before-you-arrive)
3. [Permission matrix — what each participant needs](#3-permission-matrix--what-each-participant-needs)
4. [Catalog isolation strategy](#4-catalog-isolation-strategy)
5. [Configuring the catalog name via widgets](#5-configuring-the-catalog-name-via-widgets)
6. [Cost estimation for the customer](#6-cost-estimation-for-the-customer)
7. [Network requirements](#7-network-requirements)
8. [Running setup in a customer workspace](#8-running-setup-in-a-customer-workspace)
9. [Cleaning up after the workshop](#9-cleaning-up-after-the-workshop)
10. [Known customer environments](#10-known-customer-environments)
11. [Troubleshooting customer-specific issues](#11-troubleshooting-customer-specific-issues)

---

## 1. Why customer environments need extra preparation

A Databricks Credit Program workspace is purpose-built for workshops: there are no production workloads, no data governance restrictions on sample data, no IAM constraints from an enterprise IT team, and no cost alerts to worry about.

A customer's production (or pre-production) workspace is the opposite. You must:

- Create an isolated catalog so workshop tables cannot collide with production data
- Request permissions in advance — the customer's IT team may need days to approve
- Estimate and agree on the cost so there are no surprises on the customer's cloud bill
- Confirm AI features are enabled — some customers have AI features disabled by policy
- Verify data residency settings are in place before handling any mock regulated data

Running the pre-flight check notebook (`setup/preflight_check.py`) against the customer workspace at least **three business days before the workshop** is mandatory.

---

## 2. Prerequisites — what must be true before you arrive

Work through the following checklist with the customer's workspace admin at least one week in advance.

### Workspace-level

| Requirement | How to verify | Who can action it |
|---|---|---|
| Unity Catalog enabled and a metastore assigned to the workspace | `SHOW CATALOGS` returns `system` | Account Admin |
| Serverless compute enabled | Workspace Settings → Compute → Serverless | Workspace Admin |
| AI features enabled (Genie, Playground, Notebook AI Assistant) | Account Console → Feature Enablement | Account Admin |
| Foundation Model API accessible | `Serving → Foundation Models` shows endpoints | Enabled automatically with AI features |
| Vector Search enabled | `Compute → Vector Search` tab visible | Account Admin |
| Data processing within geography enforced | Account Console → Workspaces → Compliance & Security | Account Admin |
| `system.access.audit` and `system.billing.usage` accessible | Pre-flight check Section 8 and 9 | Metastore Admin |
| At least one serverless SQL warehouse running | SQL Warehouses page | Workspace Admin |

### Infrastructure

| Requirement | Note |
|---|---|
| Repo cloned into the workspace | Via Repos or Files. Tell the SA Git credentials they use. |
| Sample CSV files uploaded to DBFS | Run: `databricks fs cp -r ./data/sample_data/ dbfs:/tmp/au_workshop/sample_data/` — requires Databricks CLI installed |
| A workshop-dedicated catalog pre-approved | IT governance may require a catalog creation request |

### Timing

- **1 week before:** Confirm prerequisites above. Run pre-flight check.
- **3 days before:** Confirm permissions are in place for all participants.
- **Day of, 1 hour before:** Run `00_workspace_setup.py` fully. Smoke tests must pass.

---

## 3. Permission matrix — what each participant needs

The workshop uses three distinct personas. Confirm that participants' accounts have been added to the right groups or have had individual grants applied.

### Workshop 1 (Admin Track)

Participants need to query system tables, browse audit logs, and understand Unity Catalog governance. They do not write to any tables.

| Object | Permission required | Grant statement |
|---|---|---|
| Workshop catalog | `USE CATALOG` | `GRANT USE CATALOG ON CATALOG <catalog> TO <group>` |
| All workshop schemas | `USE SCHEMA` | `GRANT USE SCHEMA ON SCHEMA <catalog>.* TO <group>` |
| All workshop tables | `SELECT` | `GRANT SELECT ON ALL TABLES IN SCHEMA <catalog>.energy TO <group>` — repeat for audit, ai_governance |
| `system.access.audit` | `SELECT` | `GRANT SELECT ON system.access.audit TO <group>` |
| `system.billing.usage` | `SELECT` | `GRANT SELECT ON system.billing.usage TO <group>` |
| Vector Search endpoint | `CAN_QUERY` | Via UI: Vector Search → Endpoint → Permissions |
| Genie Space | `CAN_USE` | Via UI: Genie → Space Settings → Permissions |

### Session 5 (Genie Code Track)

Participants query tables using Genie + AI/BI Dashboards. Same as Session 1 but also need dashboard creation rights.

| Object | Permission required | Grant statement |
|---|---|---|
| All of Session 1 permissions | — | As above |
| AI/BI Dashboards | `CAN_EDIT` on the workspace folder | Workspace Admin → Permissions |
| Genie Space | `CAN_MANAGE` (to create their own questions/threads) | Via UI: Genie → Space Settings → Permissions |

### Session 2 (Genie Spaces Track)

Participants create their own Genie Spaces. They need catalog-level and Genie management permissions.

| Object | Permission required | Grant statement |
|---|---|---|
| All of Workshop 1 permissions | — | As above |
| Workshop catalog | `CREATE SCHEMA` | `GRANT CREATE SCHEMA ON CATALOG <catalog> TO <group>` |
| Genie feature | `CAN_CREATE` | Workspace Settings → Feature Enablement → Genie → Allow all users |
| Model Serving (FMAPI) | `CAN_QUERY` on the LLaMA endpoint | Via UI: Serving → [endpoint] → Permissions |

### Suggested group structure

Rather than granting individual permissions, create a Unity Catalog group and a workspace group before the workshop:

```sql
-- Run as metastore admin
CREATE GROUP workshop_participants;

GRANT USE CATALOG   ON CATALOG <catalog>             TO workshop_participants;
GRANT USE SCHEMA    ON SCHEMA  <catalog>.energy      TO workshop_participants;
GRANT USE SCHEMA    ON SCHEMA  <catalog>.audit        TO workshop_participants;
GRANT USE SCHEMA    ON SCHEMA  <catalog>.ai_governance TO workshop_participants;
GRANT SELECT        ON ALL TABLES IN SCHEMA <catalog>.energy       TO workshop_participants;
GRANT SELECT        ON ALL TABLES IN SCHEMA <catalog>.audit         TO workshop_participants;
GRANT SELECT        ON ALL TABLES IN SCHEMA <catalog>.ai_governance TO workshop_participants;
GRANT SELECT        ON system.access.audit   TO workshop_participants;
GRANT SELECT        ON system.billing.usage  TO workshop_participants;
```

Then add participants to `workshop_participants` via Account Console → Groups before the workshop.

---

## 4. Catalog isolation strategy

**Never use the customer's `main` or any existing production catalog.** Create a dedicated catalog for the workshop. This gives you:

- A clean DROP CASCADE path after the workshop (no accidental production table deletions)
- A clear cost attribution boundary (billing shows `workshop_<name>` compute and storage)
- Zero risk of naming collisions with real tables
- Easy permission scoping — participants only need access to the one catalog

### Recommended naming convention

| Customer | Suggested catalog name |
|---|---|
| AEMO | `workshop_aemo` |
| APA Group | `workshop_apa` |
| AusNet | `workshop_ausnet` |
| Other / generic | `workshop_au` |

### Creating the catalog

The setup notebook creates the catalog automatically. If the customer's governance process requires the catalog to exist before the setup notebook runs (for example, if catalog creation goes through an approval workflow), the customer's workspace admin can create it in advance:

```sql
CREATE CATALOG IF NOT EXISTS workshop_aemo
  COMMENT 'Databricks AI Workshop — temporary, will be dropped after the session';
```

You can also create it via the Databricks CLI:

```bash
databricks catalogs create workshop_aemo \
  --comment "Databricks AI Workshop — temporary, will be dropped after the session"
```

---

## 5. Configuring the catalog name via widgets

Both `setup/preflight_check.py` and `setup/00_workspace_setup.py` expose **Databricks widgets** at the top of the notebook so you can change the catalog name (and schema names) without editing any code.

When you open the notebook in the customer's workspace, you will see a toolbar of widgets at the top of the output area:

| Widget | Default | What it controls |
|---|---|---|
| `catalog` | `workshop_au` | The Unity Catalog catalog for all workshop data |
| `schema_energy` | `energy` | Schema for network/meter/outage/maintenance tables |
| `schema_governance` | `ai_governance` | Schema for policy documents and VS index |
| `vs_endpoint` | `workshop_vs` | Name of the Vector Search endpoint to create |
| `pt_endpoint` | `au_east_llm_inregion` | Name of a custom pay-per-token endpoint (if any) |

**To run against a customer environment:**

1. Open `setup/preflight_check.py` in the customer's workspace.
2. Change the `catalog` widget to the agreed catalog name (e.g. `workshop_aemo`).
3. Run the notebook. All checks will target the configured catalog.
4. Fix any FAILs and review WARNs before the workshop day.
5. Open `setup/00_workspace_setup.py` and set the same `catalog` widget value.
6. Run `00_workspace_setup.py`. All resources will be created under `workshop_aemo`.

The schema defaults (`energy`, `ai_governance`) are safe to leave as-is for most customers — they are inside the isolated catalog, so they cannot collide with production schemas in `main` or any other catalog.

---

## 6. Cost estimation for the customer

The following estimates are for a 4-hour workshop with approximately 20 participants, running on an Azure australiaeast workspace. All costs are in AUD at list price (no negotiated discounts applied).

### One-off setup costs (run by facilitator, ~15–30 minutes)

| Resource | DBU type | Estimated DBUs | Estimated AUD |
|---|---|---|---|
| Setup notebook (serverless all-purpose) | Serverless Jobs | 2–4 DBUs | $4–8 |
| Vector Search index initial sync | Vector Search | ~2 DBUs | $6 |
| **Setup subtotal** | | | **~$10–15** |

### Per-participant workshop costs (4 hours × 20 participants)

| Resource | DBU type | Estimated DBUs per participant | Estimated AUD (×20) |
|---|---|---|---|
| Serverless SQL warehouse (shared) | Serverless SQL | 2–4 DBUs total | $10–20 |
| Foundation Model API (pay-per-token) | FMAPI PPT | ~500K tokens total across all participants | $8–12 |
| Notebook compute (if not serverless) | All-Purpose | 4–8 DBUs per participant | $160–320 |

### Ongoing costs if resources are left running

| Resource | Daily cost if not torn down |
|---|---|
| Vector Search endpoint (STANDARD) | ~$25/day |
| Custom PT serving endpoint (if deployed) | ~$30–60/day (depends on node type) |
| Storage for Delta tables (6 tables × ~50 MB) | < $0.10/day |

**Key message for the customer:** The workshop itself costs approximately **$30–50 AUD** at list price for a standard run. The teardown notebook removes all resources that have ongoing costs. If you forget to run teardown, the Vector Search endpoint is the most expensive ongoing resource.

### How to communicate this

When briefing the customer's finance or IT team, frame it as:

> "We will create a temporary isolated catalog (`workshop_aemo`) containing sample data only. The catalog and all associated compute resources will be deleted within 24 hours of the workshop using a teardown notebook. Total cost is estimated at AUD $50–80 for a 4-hour session with 20 participants. There are no long-running compute instances left behind."

---

## 7. Network requirements

### Azure workspaces (australiaeast)

No special firewall changes are required for the workshop. The workshop notebooks use:

- Databricks REST APIs (internal, no egress)
- Foundation Model API (internal to the Databricks platform)
- Vector Search (internal to the Databricks platform)

If the customer's workspace is on a **private networking** configuration (no public IP / Private Link), confirm the following:

| Traffic type | Required allowance |
|---|---|
| Notebook → Foundation Model API | Allowed by default on Private Link (uses internal VNet routing) |
| Notebook → Vector Search | Allowed by default on Private Link |
| Databricks CLI (for data upload) | Requires workspace Public Endpoint or VPN access to the private endpoint |

If the Databricks CLI cannot reach the workspace for the data upload step, ask the customer's network team to allow outbound access from a jump host to the workspace private endpoint, or upload the CSVs manually via the Databricks Files UI.

### Serverless networking (Azure June 2026 NSP deadline)

If the customer's workspace has `NSP (Network Security Perimeter)` policies enforced, ensure the NSP allows the service tag `AzureDatabricksServerless.AustraliaEast`. This is required for serverless SQL warehouses and serverless job compute to function. See the [Databricks NSP documentation](https://docs.databricks.com/administration-guide/cloud-configurations/azure/serverless-networking.html) for the full service tag list.

### AWS workspaces

No special networking changes are required. If the workspace is in a VPC without internet access, the same FMAPI / Vector Search caveats as Azure Private Link apply.

---

## 8. Running setup in a customer workspace

### Step-by-step

1. **Upload sample data** (from your laptop, before the workshop day):

   ```bash
   # Requires Databricks CLI >= 0.18 authenticated against the customer workspace
   databricks fs cp -r ./data/sample_data/ dbfs:/tmp/au_workshop/sample_data/ --overwrite
   ```

   Verify the upload:

   ```bash
   databricks fs ls dbfs:/tmp/au_workshop/sample_data/
   ```

   Expected output: 6 CSV files (`energy_assets.csv`, `meter_readings.csv`, `outage_events.csv`, `maintenance_work_orders.csv`, `regulatory_reports.csv`, `policy_documents.csv`).

2. **Clone the repo into the customer workspace:**

   - Workspace → Repos → Add Repo → paste the GitHub URL
   - Or use the Databricks CLI: `databricks repos create --url <github_url> --provider github`

3. **Run the pre-flight check** (`setup/preflight_check.py`):

   - Change `catalog` widget to `workshop_<customer_name>`
   - Run all cells
   - All checks should be PASS or WARNING — no FAILs
   - Fix any FAILs before proceeding

4. **Run setup** (`setup/00_workspace_setup.py`):

   - Change `catalog` widget to match the pre-flight check value
   - Run all cells
   - Expected runtime: 12–20 minutes (most time is Vector Search index sync)
   - All smoke tests must pass before the workshop begins

5. **Grant participant permissions** (after catalog is created by setup):

   ```sql
   -- Run as metastore admin or catalog owner
   GRANT USE CATALOG    ON CATALOG workshop_aemo       TO workshop_participants;
   GRANT USE SCHEMA     ON SCHEMA  workshop_aemo.energy      TO workshop_participants;
   GRANT USE SCHEMA     ON SCHEMA  workshop_aemo.audit        TO workshop_participants;
   GRANT USE SCHEMA     ON SCHEMA  workshop_aemo.ai_governance TO workshop_participants;
   GRANT SELECT ON ALL TABLES IN SCHEMA workshop_aemo.energy       TO workshop_participants;
   GRANT SELECT ON ALL TABLES IN SCHEMA workshop_aemo.audit         TO workshop_participants;
   GRANT SELECT ON ALL TABLES IN SCHEMA workshop_aemo.ai_governance TO workshop_participants;
   ```

6. **Test end-to-end as a participant:**

   - Log out and log back in as a test participant account (or use a second browser in incognito)
   - Open Genie and confirm the workshop Genie Space is visible
   - Run one sample query to confirm data access works

---

## 9. Cleaning up after the workshop

Run `setup/99_teardown.py` **within 24 hours of the workshop ending** to avoid ongoing Vector Search and Model Serving costs.

### Teardown procedure

1. Open `setup/99_teardown.py` in the workspace.
2. Set widget values to match what was used during setup:
   - `catalog` → e.g. `workshop_aemo`
   - `vs_endpoint` → e.g. `workshop_vs`
   - `pt_endpoint` → whatever was used (default: `au_east_llm_inregion`)
3. **First, do a dry run:**
   - Set `dry_run` → `true`
   - Set `confirm_delete` → `false`
   - Run all cells
   - Review the "Would remove" output — confirm it lists only workshop resources
4. **Then, do the actual delete:**
   - Set `dry_run` → `false`
   - Set `confirm_delete` → `true`
   - Run all cells
5. Verify the final summary shows no errors.

### What the teardown removes

| Resource | How removed |
|---|---|
| Workshop catalog + all tables | `DROP CATALOG CASCADE` |
| Custom PT serving endpoints | SDK delete — only endpoints matching the configured name or containing "workshop" |
| Vector Search indexes | SDK delete — all indexes on the configured VS endpoint |
| Vector Search endpoint | SDK delete — only endpoints matching the configured name or containing "workshop" |
| Genie Spaces | SDK delete — only spaces with "AU Energy Workshop" title or "workshop" in the title |

### What the teardown does NOT remove

- FMAPI pay-per-token endpoints (names start with `databricks-`) — these are platform-managed
- Participant user accounts
- The cloned repo
- Workspace settings that were configured before the workshop
- Any pre-existing resources that do not match the workshop naming patterns

### Manual cleanup (if teardown fails)

If the SDK calls fail (e.g. due to a permissions issue on the customer workspace), perform the cleanup manually:

| Resource | Manual steps |
|---|---|
| Catalog | Catalog Explorer → right-click `workshop_<customer>` → Delete → CASCADE |
| VS endpoint | Compute → Vector Search → `workshop_vs` → Delete endpoint |
| Serving endpoints | Serving → `au_east_llm_inregion` (or the configured name) → Delete |
| Genie Spaces | Data Intelligence → Genie → Space settings → Delete space |

---

## 10. Known customer environments

The following table captures known workspace IDs and special notes for Australian energy sector customers. Update this table as you work with each customer.

| Customer | Workspace URL | Workspace ID | Cloud / Region | Special notes |
|---|---|---|---|---|
| AEMO | `adb-XXXX.azuredatabricks.net` | TBC | Azure / australiaeast | 83+ workspaces — confirm which workspace with Steffen/Sourabh. AI features auto-enabled May 2026. NSP cutover June 9 2026. |
| APA Group | `adb-XXXX.azuredatabricks.net` | TBC | Azure / australiaeast | APA uses Copilot/CBIC alongside Databricks. Confirm AI features are enabled (separate from Copilot). Check with Jay Coleman. |
| AusNet | `adb-XXXX.azuredatabricks.net` | TBC | Azure / australiaeast | Bingi is primary contact. Workshop catalog should be `workshop_ausnet`. Confirm serverless is enabled — AusNet had historical classic-only compute. |
| Generic / DCP | Standard DCP workspace | — | Azure / australiaeast | Default setup — no special configuration needed. Use `workshop_au` catalog. |

_Replace `XXXX` with the actual workspace ID when confirmed. Do not store PATs or credentials in this file._

### AEMO-specific notes

- AEMO has AI Playground, Agents, and AI Gateway auto-enabled as of May 2026.
- The AI governance workshop (Module 3 of Workshop 1) is directly relevant to AEMO's AI Playground cost-control and governance concerns raised by Christopher Tao.
- AEMO uses Azure NSP. Ensure the `AzureDatabricksServerless.AustraliaEast` service tag is allowed before running the setup notebook on a serverless cluster.
- Confirm which specific workspace to use with Steffen Crouwel (AE) and Sourabh (cloud) before the engagement.

### APA Group-specific notes

- APA uses Entra ID (formerly Azure AD) for SSO. Confirm that the workshop participant accounts exist in Entra and are synced to the Databricks workspace before the day.
- APA is evaluating Copilot as an alternative to some Databricks AI features. Workshop 1 Lab on FMAPI governance can directly address the "Copilot vs Databricks AI" comparison — use the talking points in the APA agent brief.
- Jay Coleman is the primary technical contact. Pre-brief him on the workshop structure at least one week before.

### AusNet-specific notes

- Dan (AusNet) prefers L100-level content for non-technical stakeholders. If running Session 2 (Genie Spaces) with AusNet, tailor the Genie Space demo to AusNet's meter data and asset management vocabulary.
- Lisa Byrne (Data Governance Manager) is interested in Unity Catalog certification and lineage. Workshop 1 Labs 1–3 are highly relevant.
- Use catalog name `workshop_ausnet` and confirm with Bingi that catalog creation has been pre-approved through AusNet's data governance process.

---

## 11. Troubleshooting customer-specific issues

### "CREATE CATALOG fails — permission denied"

The user running the setup notebook does not have `CREATE CATALOG` on the metastore.

**Fix:** Ask the customer's metastore admin to either:
- Grant `CREATE CATALOG` to the facilitator's account: `GRANT CREATE CATALOG ON METASTORE TO facilitator@customer.com`
- Pre-create the catalog themselves and grant `OWNER` to the facilitator

### "Vector Search endpoint creation fails — quota exceeded"

Azure australiaeast may have Vector Search endpoint quotas per workspace.

**Fix:** Check the existing VS endpoints (`w.vector_search_endpoints.list_endpoints()`). If there are already 2+ endpoints, ask the customer's workspace admin to delete unused ones, or use an existing endpoint by setting the `vs_endpoint` widget to its name.

### "Foundation Model API returns 403 — model not accessible"

The specific FMAPI model (e.g. `databricks-qwen3-embedding-0-6b`) is not available in the customer's workspace region or their FMAPI entitlements are restricted.

**Fix:**
1. Check which FMAPI models are available: `list(w.serving_endpoints.list())` filtered to names starting with `databricks-`.
2. If the embedding model is missing, check [go/mosaic-au-roadmap](https://go/mosaic-au-roadmap) for regional availability.
3. Substitute an available embedding model — edit the `EMBEDDING_MODEL` variable in `00_workspace_setup.py`.
4. If no FMAPI models are available at all, escalate to the Databricks account team to confirm FMAPI is enabled on the workspace subscription.

### "Genie Space creation fails"

Genie may not be enabled on the customer workspace, or the SDK version does not include the Genie API.

**Fix:** The setup notebook handles this gracefully — Genie Space creation failure is a warning, not a blocking error. Participants can still use the Genie Space if it is created manually:
1. Go to Data Intelligence → Genie → New Genie Space
2. Use the title and table list printed in the setup notebook output

### "system.access.audit returns no results for the last 7 days"

Audit log streaming may have a delay, or the customer has not enabled system table streaming.

**Fix:** Go to Account Console → Metastore → System Tables → Enable audit streaming. Note that new rows can take 1–4 hours to appear after enabling. For Workshop 1 Lab 2 (audit log exploration), this check is important — if there are no rows, the lab exercise will not work meaningfully. Consider running the workshop against a DCP workspace for the audit-heavy labs if this cannot be resolved.

### "Databricks CLI cannot authenticate to the customer workspace"

OAuth or PAT authentication issues prevent the CSV upload step from running.

**Fix options:**
1. Use OAuth: `databricks auth login --host https://<workspace>.azuredatabricks.net`
2. Use a short-lived PAT: Account Console → User Settings → Access Tokens → Generate Token (set expiry to workshop day + 1)
3. Upload CSVs via the Databricks Files UI: Workspace → [repo path] → data → upload files
4. If using the Files UI, update `SAMPLE_DATA_PATH` in the setup notebook to point to the Volumes or Files path instead of `dbfs:/tmp/...`

---

_Last updated: 2026-05-22. Maintained by the Databricks AU SA team._
_For questions, contact Beyza Yalavac (beyza.yalavac@databricks.com)._
