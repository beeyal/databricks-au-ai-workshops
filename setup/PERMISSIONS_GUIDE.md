# Workshop Permissions Guide

This guide covers the full permission model for the AU AI Workshops programme. It tells you exactly who needs what, what must be done manually, and how to verify that access was granted correctly.

---

## Contents

1. [Who needs access to what](#1-who-needs-access-to-what)
2. [What cannot be scripted](#2-what-cannot-be-scripted-must-be-done-manually)
3. [How to run the grant script](#3-how-to-run-the-grant-script)
4. [How to verify access was granted](#4-how-to-verify-access-was-granted)
5. [How to revoke access after the session](#5-how-to-revoke-access-after-the-session)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Who needs access to what

| Role | Session | UC permissions needed | Workspace permissions | Must be done manually |
|---|---|---|---|---|
| Business user | Session 3 | `USE CATALOG` on `workshop_au`; `USE SCHEMA`, `SELECT` on `workshop_au.aemo` | `CAN_VIEW` on Genie Space; `CAN_USE` on SQL warehouse | Invite to workspace; add to Genie Space |
| Data Engineer / Data Scientist | Session 2 (core) | `USE CATALOG` on `workshop_au`; `USE SCHEMA`, `SELECT`, `EXECUTE` on `workshop_au.energy`, `workshop_au.aemo`, `workshop_au.ai_governance` | `CAN_USE` on SQL warehouse; `CAN_QUERY` on PT endpoint | Invite to workspace |
| Genie Code Developer | Session 5 (Genie Code) | Same as Data Engineer above | Same as Data Engineer; plus `CAN_VIEW` on Genie Space | Invite to workspace; add to Genie Space |
| MCP Agent Builder | Session 4 (Agents/MCP) | `USE CATALOG` on `workshop_au`; `USE SCHEMA`, `SELECT`, `EXECUTE` on `workshop_au.energy` and `workshop_au.aemo` | `CAN_QUERY` on PT endpoint | Invite to workspace |
| Admin (W1 Admin) | Session 1 | Full catalog admin on `workshop_au`; metastore admin rights to run `GRANT` statements | Workspace admin | Account Console → Workspaces → [workspace] → Admins |

**How permissions are delivered:** The grant script (`setup/grant_workshop_access.py`) creates a UC group for each session type and applies the above grants to the group. Adding a user to the group gives them all the permissions automatically. This means permissions can be adjusted for a cohort simply by adding or removing users from the group — no individual `GRANT` statements needed.

**Catalog and schema defaults:** Unless you changed the widgets in `00_workspace_setup.py`, the catalog is `workshop_au` and schemas are `energy`, `aemo`, `ai_governance`, and `audit`.

---

## 2. What cannot be scripted (must be done manually)

The following steps require the Account Console or Databricks UI and cannot be performed by a notebook running as a regular workspace user.

### Inviting users to the workspace

Users who are not already members of the workspace must be invited before they can be added to a group.

1. Go to **Account Console** → **User management** → **Users**.
2. Click **Add user**.
3. Enter the user's email address and click **Send invitation**.
4. The user receives an email and must accept before they appear in the workspace user list.

Allow **at least 24 hours** before the workshop for invitation emails to be accepted. Follow up with participants who have not accepted.

### Granting workspace admin

Only account admins can promote a user to workspace admin.

1. Go to **Account Console** → **Workspaces** → select the workspace.
2. Click **Permissions**.
3. Find the user and set their role to **Admin**.

This is needed for the **Workshop 1 / Session 2 Admin** role only.

### Geography enforcement setting

Data residency controls must be enabled by a workspace admin before the workshop. This is a one-time setting, not per-user.

1. Go to **Account Console** → **Workspaces** → select the workspace.
2. Click **Security and compliance**.
3. Enable **Enforce data processing within the workspace's geography**.

Confirm this is on before running the preflight check. The preflight notebook (`setup/preflight_check.py`) validates this setting.

### System table access

System tables (`system.billing.usage`, `system.access.audit`) must be enabled at the metastore level. This is required for Session 1 Lab 04.

1. Go to **Account Console** → **Data** → **Metastores**.
2. Select the metastore assigned to the workshop workspace.
3. Click **System schemas** and enable `billing` and `access`.

This must be done by a metastore admin. It can take up to 30 minutes to propagate.

### Genie Space permissions

The Genie Space created in Session 2 Lab 04 must have `CAN_VIEW` granted to participant groups via the UI. The Databricks SDK does not currently expose a method to set Genie Space-level permissions programmatically.

1. Open the Genie Space in the Databricks UI.
2. Click the **Share** button (top right).
3. Search for the group name (e.g., `workshop_session3_participants`).
4. Set permission to **Can view**.

Do this after running the grant script but before Session 3 participants log in.

---

## 3. How to run the grant script

The grant script is `setup/grant_workshop_access.py`. Run it as a Databricks notebook with a serverless or shared cluster.

### Step 1 — Confirm prerequisites

- You are running as a workspace admin (or have `MANAGE` on the workshop catalog).
- All participants have accepted their workspace invitation. See Section 2 above.
- `setup/00_workspace_setup.py` has already run successfully (catalog and tables exist).

### Step 2 — Open the notebook in Databricks

Upload or import `setup/grant_workshop_access.py` into your workspace via **Workspace** → **Import** or **Repos**.

### Step 3 — Set the widgets

At the top of the notebook, set:

| Widget | What to enter |
|---|---|
| `user_emails` | Comma-separated list of participant email addresses. Example: `alice@example.com, bob@example.com` |
| `session_type` | Choose from the dropdown — must match the session the participants are attending |
| `dry_run` | Set to `true` first to preview what will happen. Then set to `false` to apply. |

### Step 4 — Run with dry_run=true

Run all cells with `dry_run=true`. Review the output to confirm:
- All emails resolved to valid workspace users.
- The correct group name is shown.
- The UC `GRANT` statements look right for the session type.

If any users show as "not found", they have not accepted their workspace invitation yet. Do not proceed until all participants are in the workspace.

### Step 5 — Run with dry_run=false

Set `dry_run=false` and run all cells again. The script will:
1. Create the UC group if it does not exist.
2. Add all participants to the group.
3. Run the `GRANT` SQL statements for the session type.
4. Print a summary report.

### Step 6 — Verify (see Section 4)

Run the verification SQL queries to confirm grants are in place before the session starts.

---

## 4. How to verify access was granted

Run the following SQL in a notebook or the SQL editor. Replace `workshop_au` and `aemo` with the actual catalog and schema names if you changed the defaults.

### Check schema-level grants

```sql
SHOW GRANTS ON SCHEMA workshop_au.aemo;
```

Expected output for Session 3 (business users):

| principal | action_type | object_type | object_key |
|---|---|---|---|
| `workshop_session3_participants` | SELECT | SCHEMA | `workshop_au.aemo` |
| `workshop_session3_participants` | USE SCHEMA | SCHEMA | `workshop_au.aemo` |

### Check catalog-level grants

```sql
SHOW GRANTS ON CATALOG workshop_au;
```

Expected output:

| principal | action_type | object_type | object_key |
|---|---|---|---|
| `workshop_session3_participants` | USE CATALOG | CATALOG | `workshop_au` |

### Check grants for Session 2 schemas

```sql
SHOW GRANTS ON SCHEMA workshop_au.energy;
SHOW GRANTS ON SCHEMA workshop_au.ai_governance;
```

### Confirm a specific user is in the group

In a Python notebook cell:

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

group_name = "workshop_session3_participants"  # change to match session type
groups = list(w.groups.list(filter=f'displayName eq "{group_name}"'))
if groups:
    grp = groups[0]
    members = grp.members or []
    print(f"Group '{group_name}' has {len(members)} member(s):")
    for m in members:
        print(f"  - {m.display}")
else:
    print(f"Group '{group_name}' not found.")
```

### Spot-check from a participant account

If possible, log in as a participant (or ask a participant to confirm) that they can:

1. Navigate to **Data** → **workshop_au** in the Catalog Explorer.
2. See the `aemo` schema and its tables.
3. Open the SQL editor, select the workshop warehouse, and run:
   ```sql
   SELECT COUNT(*) FROM workshop_au.aemo.dispatch_intervals;
   ```

---

## 5. How to revoke access after the session

Run `setup/revoke_workshop_access.py` after the session is complete.

**Recommended default:** Use `revoke_mode = "Delete group entirely"`. Deleting the group immediately removes all UC grants associated with it. This is the cleanest post-session cleanup and leaves no residual permissions.

**When to use "Remove users from group" instead:** If you have another cohort for the same session within the next few days, keep the group and its grants in place. Just remove the previous cohort's users. Add the new cohort's users with the grant script before the next session.

See `revoke_workshop_access.py` for full instructions and the dry-run mode.

---

## 6. Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| `User not found` in grant script | Participant has not accepted the workspace invitation | Follow up with the participant; re-run the grant script once they have accepted |
| `PERMISSION_DENIED` on `spark.sql("GRANT ...")` | Running user is not a workspace admin or does not have `MANAGE` on the catalog | Re-run the notebook as a workspace admin, or ask the customer's admin to run it |
| `Warehouse not found` or warehouse selector shows nothing | No serverless SQL warehouse exists, or the running user cannot see it | Confirm a serverless warehouse exists (Workspace Settings → SQL Warehouses); ensure the running user has `CAN_USE` |
| `GROUP_ALREADY_EXISTS` | A group with the same name already exists from a previous run | This is not an error — the grant script handles this gracefully. The group is reused. |
| `INSUFFICIENT_PRIVILEGES` on `SHOW GRANTS` | Running user is not the catalog owner or a metastore admin | Use a workspace admin account to run verification queries |
| User can see the catalog in the explorer but gets `TABLE_OR_VIEW_NOT_FOUND` on query | `SELECT` was granted on the schema but `USE SCHEMA` was not, or vice versa | Re-run the grant script; the script grants both `USE SCHEMA` and `SELECT` together |
| Genie Space is not visible to participants | Group has UC access but the Space itself was not shared | Grant `CAN_VIEW` on the Genie Space to the participant group via the Share button — this cannot be scripted (see Section 2) |
| Participant gets `CROSS_REGION` or data residency error | Geography enforcement is on and a cross-geo model was used | This is working as intended. Route the request to an in-region PT endpoint. See `SESSION_MAP.md` for the list of in-region models. |
| `User has already been added` error during group membership patch | The SDK returned an error instead of silently ignoring a duplicate | This is safe to ignore. The user is already in the group. |
| Revocation fails with `GROUP_NOT_FOUND` | The group was already deleted in a previous run of `revoke_workshop_access.py` | No action needed — access is already revoked. |
