# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 24px 32px; border-radius: 12px; color: white; font-family: 'DM Sans', sans-serif; margin-bottom: 8px;">
# MAGIC   <h1 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 700;">Workshop Access Provisioning</h1>
# MAGIC   <p style="margin: 0; font-size: 15px; opacity: 0.9;">Databricks AU AI Workshops — Run this notebook before each session to grant participants access to the correct resources.</p>
# MAGIC   <hr style="border-color: rgba(255,255,255,0.3); margin: 16px 0 12px 0;">
# MAGIC   <p style="margin: 0; font-size: 13px; opacity: 0.75;">
# MAGIC     ✅ <strong>Idempotent</strong> — safe to run twice &nbsp;|&nbsp;
# MAGIC     🔒 <strong>PATCH-based</strong> — additive permissions, never removes existing access &nbsp;|&nbsp;
# MAGIC     🧪 <strong>Dry-run mode</strong> — set <code>dry_run=true</code> to preview without making changes
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC > **Before running:** All participants must already be invited to this Databricks workspace via **Account Console → User management → Invite user**. This script cannot create workspace users — it can only grant permissions to existing ones.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prerequisites
# MAGIC
# MAGIC | Step | Who | Where |
# MAGIC |------|-----|-------|
# MAGIC | Invite users to workspace | Workspace admin | Account Console → User management → Invite user |
# MAGIC | Copy user emails | Facilitator | Attendee registration list |
# MAGIC | Find Genie Space ID | Facilitator | URL: `.../genie/rooms/{id}` — copy the `{id}` part |
# MAGIC | Find SQL Warehouse ID | Facilitator | SQL → Warehouses → click warehouse → copy ID from URL |
# MAGIC | Note PT endpoint name | Facilitator | Machine Learning → Serving → endpoint name |
# MAGIC
# MAGIC > **Session 2 Admin track only:** Workspace admin access cannot be granted via API. Add participants as workspace admins manually in **Account Console → Workspaces → [workspace] → Admins** after running this script.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widgets — Fill in before running

# COMMAND ----------

dbutils.widgets.removeAll()

dbutils.widgets.text(
    "user_emails",
    "",
    "User emails (comma or newline separated)"
)
dbutils.widgets.dropdown(
    "session_type",
    "Session 3 — Business Users",
    [
        "Session 3 — Business Users",
        "Session 2 — Data Engineers",
        "Session 2a — Genie Code Developers",
        "Session 2c — MCP Agent Builders",
        "Session 2 Admin — Workshop 1 Admin Track",
    ],
    "Session type"
)
dbutils.widgets.text("catalog",          "workshop_au",         "Unity Catalog name")
dbutils.widgets.text("schema_energy",    "energy",              "Energy schema name")
dbutils.widgets.text("schema_aemo",      "aemo",                "AEMO schema name")
dbutils.widgets.text("schema_governance","ai_governance",        "Governance schema name")
dbutils.widgets.text("genie_space_id",   "",                    "Genie Space ID (from URL: .../genie/rooms/{id})")
dbutils.widgets.text("warehouse_id",     "",                    "SQL Warehouse ID")
dbutils.widgets.text("pt_endpoint",      "au_east_llm_inregion","PT / Serving endpoint name")
dbutils.widgets.dropdown(
    "dry_run",
    "true",
    ["true", "false"],
    "Dry run (preview only — no changes made)"
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 0 — Parse inputs and summarise

# COMMAND ----------

import re

# ---------- Read widgets ----------
raw_emails   = dbutils.widgets.get("user_emails")
session_type = dbutils.widgets.get("session_type")
catalog      = dbutils.widgets.get("catalog").strip()
schema_energy     = dbutils.widgets.get("schema_energy").strip()
schema_aemo       = dbutils.widgets.get("schema_aemo").strip()
schema_governance = dbutils.widgets.get("schema_governance").strip()
genie_space_id    = dbutils.widgets.get("genie_space_id").strip()
warehouse_id      = dbutils.widgets.get("warehouse_id").strip()
pt_endpoint       = dbutils.widgets.get("pt_endpoint").strip()
dry_run           = dbutils.widgets.get("dry_run").strip().lower() == "true"

# ---------- Parse email list ----------
# Split on comma, semicolon, or newline; strip whitespace; deduplicate; lower-case
emails_raw = re.split(r"[,;\n]+", raw_emails)
emails = sorted({e.strip().lower() for e in emails_raw if e.strip()})

if not emails:
    raise ValueError(
        "No emails provided. Fill in the 'user_emails' widget before running."
    )

# ---------- Summary ----------
mode_label = "🧪 DRY RUN (no changes will be made)" if dry_run else "🚀 LIVE RUN (changes will be applied)"

print("=" * 65)
print(f"  Workshop Access Provisioning")
print("=" * 65)
print(f"  Mode         : {mode_label}")
print(f"  Session type : {session_type}")
print(f"  Catalog      : {catalog}")
print(f"  Emails ({len(emails):>2})  : {', '.join(emails)}")
print(f"  Genie Space  : {genie_space_id or '(not set — will skip)'}")
print(f"  Warehouse ID : {warehouse_id  or '(not set — will skip)'}")
print(f"  PT endpoint  : {pt_endpoint   or '(not set — will skip)'}")
print("=" * 65)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 1 — Validate users exist in workspace

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

valid_users = {}   # email -> User object
failed      = {}   # email -> reason string

print(f"Checking {len(emails)} email(s) against workspace user directory...\n")

for email in emails:
    try:
        results = list(w.users.list(filter=f"userName eq '{email}'"))
    except Exception as exc:
        failed[email] = f"API error during lookup: {exc}"
        print(f"  ❌  {email} — API error: {exc}")
        continue

    if not results:
        failed[email] = (
            "User not found in workspace — "
            "invite via Account Console → User management → Invite user first"
        )
        print(f"  ❌  {email} — not found in workspace")
    else:
        user = results[0]
        valid_users[email] = user
        print(f"  ✅  {email} — found (id={user.id})")

print(f"\nValid: {len(valid_users)}   Failed: {len(failed)}")

if not valid_users and not dry_run:
    raise RuntimeError(
        "No valid users found. Invite participants to the workspace first, "
        "then re-run this notebook."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 2 — Determine permissions for session type

# COMMAND ----------

# Permission matrix per session type.
# Keys:
#   schemas    — list of (catalog, schema) tuples to grant UC access on
#   grants     — UC privilege names to apply on each schema
#   warehouse  — bool: grant CAN_USE on the SQL warehouse
#   pt_endpoint— bool: grant CAN_QUERY on the PT serving endpoint
#   genie_space— bool: grant CAN_VIEW on the Genie Space
#   group_name — str or None: group to create/use (None = Admin track, skip group)
#   note       — str or None: print this warning at the top of the run

SESSION_PERMS = {
    "Session 3 — Business Users": {
        "schemas":     [(catalog, schema_aemo)],
        "grants":      ["USE CATALOG", "USE SCHEMA", "SELECT"],
        "warehouse":   True,
        "pt_endpoint": False,
        "genie_space": True,
        "group_name":  "workshop_s3_participants",
        "note":        None,
    },
    "Session 2 — Data Engineers": {
        "schemas":     [(catalog, schema_energy), (catalog, schema_governance)],
        "grants":      ["USE CATALOG", "USE SCHEMA", "SELECT", "EXECUTE"],
        "warehouse":   True,
        "pt_endpoint": True,
        "genie_space": True,
        "group_name":  "workshop_s2_data_engineers",
        "note":        None,
    },
    "Session 2a — Genie Code Developers": {
        "schemas":     [(catalog, schema_energy)],
        "grants":      ["USE CATALOG", "USE SCHEMA", "SELECT", "EXECUTE"],
        "warehouse":   True,
        "pt_endpoint": True,
        "genie_space": True,
        "group_name":  "workshop_s2a_developers",
        "note":        None,
    },
    "Session 2c — MCP Agent Builders": {
        "schemas":     [(catalog, schema_energy), (catalog, schema_aemo)],
        "grants":      ["USE CATALOG", "USE SCHEMA", "SELECT", "EXECUTE"],
        "warehouse":   True,
        "pt_endpoint": True,
        "genie_space": True,
        "group_name":  "workshop_s2c_agent_builders",
        "note":        None,
    },
    "Session 2 Admin — Workshop 1 Admin Track": {
        "schemas":     [],
        "grants":      [],
        "warehouse":   True,
        "pt_endpoint": True,
        "genie_space": False,
        "group_name":  None,
        "note": (
            "⚠️  Workspace admin CANNOT be scripted. "
            "Add participants as workspace admins manually in "
            "Account Console → Workspaces → [workspace] → Admins. "
            "This script will grant SQL warehouse + PT endpoint access only."
        ),
    },
}

perms = SESSION_PERMS[session_type]

# Print special notes first so the facilitator sees them before anything runs
if perms["note"]:
    print(perms["note"])
    print()

print(f"Permission profile for '{session_type}':")
print(f"  Group name  : {perms['group_name'] or '(none — Admin track)'}")
print(f"  Schemas     : {perms['schemas'] or '(none)'}")
print(f"  Grants      : {perms['grants']  or '(none)'}")
print(f"  Warehouse   : {'yes' if perms['warehouse']   else 'no'}")
print(f"  PT endpoint : {'yes' if perms['pt_endpoint'] else 'no'}")
print(f"  Genie Space : {'yes' if perms['genie_space'] else 'no'}")

# Derived convenience variables used in subsequent sections
group_name    = perms["group_name"]
schemas       = perms["schemas"]
grants        = perms["grants"]
need_warehouse   = perms["warehouse"]
need_pt_endpoint = perms["pt_endpoint"]
need_genie_space = perms["genie_space"]

# Track per-user outcome for the final report
report = {}  # email -> {"status": "granted"|"failed"|"skipped", "detail": str}

# Pre-populate failures from Section 1
for email, reason in failed.items():
    report[email] = {"status": "failed", "detail": reason}

# Pre-populate dry_run skips for valid users (will be overwritten if live run)
if dry_run:
    for email in valid_users:
        report[email] = {"status": "skipped", "detail": "dry_run=true — no changes made"}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 3 — Create or retrieve group, add users
# MAGIC
# MAGIC > Group membership additions are idempotent: adding a user who is already a member is a no-op (the SCIM PATCH ADD operation does not create duplicates).

# COMMAND ----------

from databricks.sdk.service.iam import ComplexValue, Patch, PatchOp, PatchSchema

group = None  # populated below if group_name is set

if group_name is None:
    print("Admin track — no group to create. Skipping this section.")
else:
    if dry_run:
        print(f"[DRY RUN] Would create or retrieve group '{group_name}'")
        for email in valid_users:
            print(f"[DRY RUN] Would add {email} to group '{group_name}'")
    else:
        # --- Create or retrieve group ---
        try:
            existing = list(w.groups.list(filter=f"displayName eq '{group_name}'"))
        except Exception as exc:
            raise RuntimeError(f"Failed to query groups: {exc}") from exc

        if existing:
            group = existing[0]
            print(f"✅  Group '{group_name}' already exists (id={group.id})")
        else:
            group = w.groups.create(display_name=group_name)
            print(f"✅  Created group '{group_name}' (id={group.id})")

        # --- Add each valid user to the group ---
        for email, user in valid_users.items():
            try:
                w.groups.patch(
                    id=group.id,
                    schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
                    operations=[
                        Patch(
                            op=PatchOp.ADD,
                            path="members",
                            value=[{"value": user.id}],
                        )
                    ],
                )
                print(f"  ✅  Added {email} to group '{group_name}'")
                # Initialise report entry; may be enriched by later sections
                report[email] = {
                    "status": "granted",
                    "detail": f"Group: {group_name}",
                }
            except Exception as exc:
                err = f"Failed to add to group '{group_name}': {exc}"
                report[email] = {"status": "failed", "detail": err}
                print(f"  ❌  {email} — {err}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4 — Grant Unity Catalog permissions to group
# MAGIC
# MAGIC `GRANT ... ON SCHEMA` applies to **all current and future tables and views** in that schema, so individual table grants are not needed.
# MAGIC
# MAGIC > Running this twice is safe — Databricks UC GRANT is idempotent (re-granting an existing privilege is a no-op).

# COMMAND ----------

# Build the full list of SQL statements to execute
def build_grant_statements(catalog_name, schema_name, grant_list, principal):
    """Return a list of GRANT SQL strings for the given schema and privileges."""
    statements = []
    for grant in grant_list:
        if grant == "USE CATALOG":
            statements.append(
                f"GRANT USE CATALOG ON CATALOG `{catalog_name}` TO `{principal}`"
            )
        elif grant == "USE SCHEMA":
            statements.append(
                f"GRANT USE SCHEMA ON SCHEMA `{catalog_name}`.`{schema_name}` TO `{principal}`"
            )
        elif grant == "SELECT":
            statements.append(
                f"GRANT SELECT ON SCHEMA `{catalog_name}`.`{schema_name}` TO `{principal}`"
            )
        elif grant == "EXECUTE":
            statements.append(
                f"GRANT EXECUTE ON SCHEMA `{catalog_name}`.`{schema_name}` TO `{principal}`"
            )
        else:
            statements.append(
                f"GRANT {grant} ON SCHEMA `{catalog_name}`.`{schema_name}` TO `{principal}`"
            )
    return statements


if group_name is None or not schemas or not grants:
    print("No UC grants required for this session type. Skipping.")
else:
    # Deduplicate USE CATALOG statements — only one needed per catalog regardless
    # of how many schemas are granted.
    all_statements = []
    use_catalog_seen = set()

    for (cat, sch) in schemas:
        for stmt in build_grant_statements(cat, sch, grants, group_name):
            if stmt.startswith("GRANT USE CATALOG"):
                if cat not in use_catalog_seen:
                    use_catalog_seen.add(cat)
                    all_statements.append(stmt)
            else:
                all_statements.append(stmt)

    if dry_run:
        print("[DRY RUN] Would execute the following GRANT statements:\n")
        for stmt in all_statements:
            print(f"  {stmt}")
    else:
        print(f"Executing {len(all_statements)} GRANT statement(s)...\n")
        uc_errors = []
        for stmt in all_statements:
            try:
                spark.sql(stmt)
                print(f"  ✅  {stmt}")
            except Exception as exc:
                err_msg = f"UC GRANT error — {stmt}: {exc}"
                uc_errors.append(err_msg)
                print(f"  ❌  {err_msg}")

        if uc_errors:
            print(f"\n⚠️  {len(uc_errors)} GRANT statement(s) failed (see above). "
                  f"Check that the catalog '{catalog}' and schemas exist, "
                  f"and that this notebook's service principal has MANAGE privilege on them.")
        else:
            print(f"\n✅  All GRANT statements applied successfully.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 5 — Grant SQL warehouse access (CAN_USE)
# MAGIC
# MAGIC Uses `permissions.update()` (HTTP PATCH) — additive, does not replace existing ACLs.

# COMMAND ----------

from databricks.sdk.service.iam import AccessControlRequest, PermissionLevel

if not need_warehouse:
    print("Warehouse access not required for this session type. Skipping.")
elif not warehouse_id:
    print("⚠️  warehouse_id widget is empty. Skipping warehouse grants.")
    print("    Set the 'warehouse_id' widget and re-run if warehouse access is needed.")
elif dry_run:
    for email in valid_users:
        print(f"[DRY RUN] Would grant CAN_USE on warehouse '{warehouse_id}' to {email}")
else:
    print(f"Granting CAN_USE on SQL warehouse '{warehouse_id}'...\n")
    for email, user in valid_users.items():
        if report.get(email, {}).get("status") == "failed":
            print(f"  ⏭️   Skipping {email} (failed earlier)")
            continue
        try:
            w.permissions.update(
                request_object_type="sql/warehouses",
                request_object_id=warehouse_id,
                access_control_list=[
                    AccessControlRequest(
                        user_name=email,
                        permission_level=PermissionLevel.CAN_USE,
                    )
                ],
            )
            print(f"  ✅  {email} — CAN_USE granted on warehouse")
            # Append warehouse detail to existing report entry
            if email in report and report[email]["status"] == "granted":
                report[email]["detail"] += " | Warehouse: CAN_USE"
        except Exception as exc:
            err = f"Warehouse permission error: {exc}"
            print(f"  ❌  {email} — {err}")
            # Don't overwrite a harder failure, but note the warehouse error
            if report.get(email, {}).get("status") != "failed":
                report[email] = {"status": "failed", "detail": err}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 6 — Grant PT (Serving) endpoint access (CAN_QUERY)
# MAGIC
# MAGIC Uses `permissions.update()` (HTTP PATCH) — additive.

# COMMAND ----------

if not need_pt_endpoint:
    print("PT endpoint access not required for this session type. Skipping.")
elif not pt_endpoint:
    print("⚠️  pt_endpoint widget is empty. Skipping serving endpoint grants.")
    print("    Set the 'pt_endpoint' widget and re-run if endpoint access is needed.")
elif dry_run:
    for email in valid_users:
        print(f"[DRY RUN] Would grant CAN_QUERY on endpoint '{pt_endpoint}' to {email}")
else:
    print(f"Granting CAN_QUERY on serving endpoint '{pt_endpoint}'...\n")
    for email, user in valid_users.items():
        if report.get(email, {}).get("status") == "failed":
            print(f"  ⏭️   Skipping {email} (failed earlier)")
            continue
        try:
            w.permissions.update(
                request_object_type="serving-endpoints",
                request_object_id=pt_endpoint,
                access_control_list=[
                    AccessControlRequest(
                        user_name=email,
                        permission_level=PermissionLevel.CAN_QUERY,
                    )
                ],
            )
            print(f"  ✅  {email} — CAN_QUERY granted on endpoint '{pt_endpoint}'")
            if email in report and report[email]["status"] == "granted":
                report[email]["detail"] += f" | Endpoint: CAN_QUERY"
        except Exception as exc:
            err = f"Endpoint permission error: {exc}"
            print(f"  ❌  {email} — {err}")
            if report.get(email, {}).get("status") != "failed":
                report[email] = {"status": "failed", "detail": err}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 7 — Grant Genie Space access (CAN_VIEW, via REST API)
# MAGIC
# MAGIC The Databricks Python SDK does not have a typed method for Genie Space permissions. We use the underlying REST endpoint directly. The resource type for Genie Spaces in the permissions API is `"dashboards"`.
# MAGIC
# MAGIC > Permissions are granted to the **group**, not individual users, so the group from Section 3 must exist before this section runs.

# COMMAND ----------

import requests

if not need_genie_space:
    print("Genie Space access not required for this session type. Skipping.")
elif not genie_space_id:
    print("⚠️  genie_space_id widget is empty. Skipping Genie Space grants.")
    print("    Find the Genie Space ID in the URL: .../genie/rooms/{id}")
    print("    Set the 'genie_space_id' widget and re-run.")
elif group_name is None:
    # Defensive: Admin track does not need Genie Space access
    print("Admin track — no group to grant Genie Space access to. Skipping.")
elif dry_run:
    print(
        f"[DRY RUN] Would grant CAN_VIEW on Genie Space '{genie_space_id}' "
        f"to group '{group_name}'"
    )
else:
    # Retrieve credentials at runtime (PAT is scoped to this notebook session)
    TOKEN = (
        dbutils.notebook.entry_point
        .getDbutils()
        .notebook()
        .getContext()
        .apiToken()
        .get()
    )
    HOST = spark.conf.get("spark.databricks.workspaceUrl")

    url = f"https://{HOST}/api/2.0/permissions/dashboards/{genie_space_id}"
    payload = {
        "access_control_list": [
            {
                "group_name": group_name,
                "permission_level": "CAN_VIEW",
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    print(f"PATCH {url}")
    print(f"  Granting CAN_VIEW to group '{group_name}' on Genie Space '{genie_space_id}'...\n")

    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=30)
        if resp.ok:
            print(f"  ✅  CAN_VIEW granted on Genie Space '{genie_space_id}' to group '{group_name}'")
        else:
            print(
                f"  ❌  API returned {resp.status_code}: {resp.text}\n"
                f"      Verify the genie_space_id is correct and this service principal "
                f"has CAN_MANAGE on the Genie Space."
            )
    except requests.exceptions.RequestException as exc:
        print(f"  ❌  Request failed: {exc}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 8 — Final report

# COMMAND ----------

# Ensure every input email has a report entry (belt-and-suspenders)
for email in emails:
    if email not in report:
        if email in valid_users:
            report[email] = {"status": "granted", "detail": "Permissions applied"}
        else:
            report[email] = {
                "status": "failed",
                "detail": (
                    "User not found in workspace — "
                    "invite via Account Console → User management → Invite user first"
                ),
            }

STATUS_ICON = {
    "granted": "✅ Granted",
    "failed":  "❌ Failed",
    "skipped": "⚠️  Skipped",
}

# Determine column widths for pretty-printing
col_email  = max(len("User"),   max(len(e) for e in report))
col_status = max(len("Status"), max(len(STATUS_ICON[v["status"]]) for v in report.values()))
col_detail = max(len("Details"), max(len(v["detail"]) for v in report.values()))

sep = f"+{'-'*(col_email+2)}+{'-'*(col_status+2)}+{'-'*(col_detail+2)}+"
hdr = f"| {'User':<{col_email}} | {'Status':<{col_status}} | {'Details':<{col_detail}} |"

print("\n" + sep)
print(hdr)
print(sep)

counts = {"granted": 0, "failed": 0, "skipped": 0}
for email in sorted(report):
    entry   = report[email]
    status  = entry["status"]
    icon    = STATUS_ICON[status]
    detail  = entry["detail"]
    counts[status] += 1
    print(f"| {email:<{col_email}} | {icon:<{col_status}} | {detail:<{col_detail}} |")

print(sep)
print(f"\nSummary:  ✅ {counts['granted']} granted  |  ❌ {counts['failed']} failed  |  ⚠️  {counts['skipped']} skipped (dry run)\n")

if dry_run:
    print("ℹ️  This was a DRY RUN. No changes were made.")
    print("   Set dry_run = false and re-run to apply permissions.")
elif counts["failed"] > 0:
    print(
        "⚠️  Some users could not be provisioned. Review the 'Failed' rows above.\n"
        "   Most common cause: user not yet invited to this workspace.\n"
        "   Fix: Account Console → User management → Invite user, then re-run this notebook."
    )
else:
    print("🎉  All participants have been provisioned successfully.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick reference — what was granted
# MAGIC
# MAGIC | Resource | What was granted | To |
# MAGIC |----------|------------------|----|
# MAGIC | Unity Catalog schemas | USE CATALOG, USE SCHEMA, SELECT (+ EXECUTE for dev sessions) | Group |
# MAGIC | SQL Warehouse | CAN_USE | Individual users |
# MAGIC | PT Serving Endpoint | CAN_QUERY | Individual users |
# MAGIC | Genie Space | CAN_VIEW | Group |
# MAGIC
# MAGIC **Notes:**
# MAGIC - `GRANT ... ON SCHEMA` covers all current and future tables/views/functions in that schema — no per-table grants needed.
# MAGIC - Warehouse and endpoint permissions are granted directly to users (not the group) to ensure they appear in each user's UI immediately.
# MAGIC - Running this notebook a second time is safe — UC GRANTs and SCIM PATCH ADD are idempotent.
# MAGIC - To revoke access after a session, use `REVOKE` SQL statements and the corresponding `permissions.set()` SDK calls, or delete the group.
