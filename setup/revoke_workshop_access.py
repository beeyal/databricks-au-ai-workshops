# Databricks notebook source
# MAGIC %md
# MAGIC # Workshop Access Revocation
# MAGIC
# MAGIC **Run after a workshop session is complete to remove participant access.**
# MAGIC
# MAGIC This notebook removes workshop participants from their UC group, which revokes all
# MAGIC group-based permissions in Unity Catalog without touching individual user accounts or
# MAGIC production resources.
# MAGIC
# MAGIC **Two revoke modes:**
# MAGIC - **Remove users from group** — users are ejected from the group but the group and its UC grants remain. Use when running another cohort soon and the group should be preserved.
# MAGIC - **Delete group entirely** — the group is deleted, which immediately drops all UC grants to that group name. This is the cleanest revoke and the recommended default for post-engagement cleanup.
# MAGIC
# MAGIC **Expected runtime:** < 2 minutes for up to 50 users.
# MAGIC
# MAGIC **Re-runnable:** safe to re-run. Users already removed from the group are skipped without error.

# COMMAND ----------
# MAGIC %md
# MAGIC ### Configuration — fill these in before running

# COMMAND ----------

dbutils.widgets.removeAll()

dbutils.widgets.text(
    "user_emails",
    "",
    "1. User emails (comma-separated)",
)
dbutils.widgets.dropdown(
    "session_type",
    "Session 3 — Business User",
    [
        "Session 2 — Data Engineer / Data Scientist",
        "Session 2a — Genie Code Developer",
        "Session 2c — MCP Agent Builder",
        "Session 3 — Business User",
        "Workshop 1 — Admin",
    ],
    "2. Session type",
)
dbutils.widgets.dropdown(
    "dry_run",
    "true",
    ["true", "false"],
    "3. Dry run (true = no changes made)",
)
dbutils.widgets.dropdown(
    "revoke_mode",
    "Remove users from group",
    ["Remove users from group", "Delete group entirely"],
    "4. Revoke mode",
)

# COMMAND ----------

USER_EMAILS_RAW = dbutils.widgets.get("user_emails")
SESSION_TYPE    = dbutils.widgets.get("session_type")
DRY_RUN         = dbutils.widgets.get("dry_run").lower() == "true"
REVOKE_MODE     = dbutils.widgets.get("revoke_mode")

print("=" * 65)
print("  WORKSHOP ACCESS REVOCATION — CONFIGURATION")
print("=" * 65)
print(f"  Session type:   {SESSION_TYPE}")
print(f"  Revoke mode:    {REVOKE_MODE}")
print(f"  Dry run:        {DRY_RUN}")
print()
if DRY_RUN:
    print("  *** DRY RUN MODE — no changes will be made ***")
    print("  Set dry_run=false to apply revocations.")
else:
    print("  *** LIVE MODE — access will be revoked ***")
print("=" * 65)

# COMMAND ----------

# MAGIC %md ## Section 1 — Parse User List

# COMMAND ----------

# Parse and validate the email list. Accepts comma or newline-separated values.
# Empty entries and whitespace are stripped. Invalid-looking emails are flagged.

raw_entries = USER_EMAILS_RAW.replace("\n", ",").split(",")

user_emails  = []
invalid      = []

for entry in raw_entries:
    email = entry.strip().lower()
    if not email:
        continue
    # Basic format check: must contain exactly one @ with something on both sides
    if email.count("@") == 1 and len(email.split("@")[0]) > 0 and len(email.split("@")[1]) > 1:
        user_emails.append(email)
    else:
        invalid.append(entry.strip())

print(f"Parsed {len(user_emails)} valid email(s).")

if invalid:
    print(f"\nSkipping {len(invalid)} invalid entry/entries:")
    for e in invalid:
        print(f"  ! {e}")

if not user_emails:
    raise ValueError(
        "No valid user emails provided. "
        "Enter at least one email in the 'user_emails' widget (comma-separated)."
    )

print("\nUsers to process:")
for email in user_emails:
    print(f"  - {email}")

# COMMAND ----------

# MAGIC %md ## Section 2 — Identify the Workshop Group

# COMMAND ----------

# Group names must match what was used in grant_workshop_access.py.
# These names are stable across cohorts — they are the UC principal whose grants get revoked.

SESSION_TO_GROUP = {
    "Session 2 — Data Engineer / Data Scientist": "workshop_session2_participants",
    "Session 2a — Genie Code Developer":          "workshop_session2a_participants",
    "Session 2c — MCP Agent Builder":             "workshop_session2c_participants",
    "Session 3 — Business User":                  "workshop_session3_participants",
    "Workshop 1 — Admin":                         "workshop_session1_admins",
}

GROUP_NAME = SESSION_TO_GROUP[SESSION_TYPE]

print(f"Target group: '{GROUP_NAME}' (for session: {SESSION_TYPE})")

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import Patch, PatchOp, PatchSchema

w = WorkspaceClient()

# Look up the group
print(f"\nSearching for group '{GROUP_NAME}'...")

target_group = None
for grp in w.groups.list(filter=f"displayName eq \"{GROUP_NAME}\""):
    if grp.display_name == GROUP_NAME:
        target_group = grp
        break

if target_group is None:
    print(f"  ⚠️  Group '{GROUP_NAME}' not found in this workspace.")
    print("      Nothing to revoke. The group may have already been deleted,")
    print("      or the session_type widget may not match what was used during grant.")
    dbutils.notebook.exit("Group not found — nothing to revoke.")

print(f"  Found group '{GROUP_NAME}' (ID: {target_group.id})")

# Build a lookup of current group members: email -> member_id
existing_members = {}   # email -> member value (user id)
if target_group.members:
    for member in target_group.members:
        # member.display is the email/username; member.value is the user id
        if member.display:
            existing_members[member.display.lower()] = member.value

print(f"  Current member count: {len(existing_members)}")
if existing_members:
    for email in sorted(existing_members):
        print(f"    - {email}")

# COMMAND ----------

# MAGIC %md ## Section 3 — Remove Users from Group (or Delete Group)

# COMMAND ----------

# Resolve user emails to user objects (needed for the remove-from-group path)

print("=" * 65)
if REVOKE_MODE == "Delete group entirely":
    print("SECTION 3 — DELETE GROUP")
    print("=" * 65)
    print(f"\nRevoke mode: DELETE GROUP ENTIRELY")
    print(f"This will delete the group '{GROUP_NAME}' and immediately drop")
    print(f"all UC grants that reference this group name.")
    print()
    if DRY_RUN:
        print(f"  [DRY RUN] Would delete group '{GROUP_NAME}' (ID: {target_group.id})")
        print(f"  [DRY RUN] This would remove all {len(existing_members)} member(s) and all UC grants.")
    else:
        print(f"  Deleting group '{GROUP_NAME}' (ID: {target_group.id})...")
        w.groups.delete(id=target_group.id)
        print(f"  ✅ Group '{GROUP_NAME}' deleted.")
        print(f"     All UC grants to this group name are now revoked.")

else:
    print("SECTION 3 — REMOVE USERS FROM GROUP")
    print("=" * 65)
    print()

    # Resolve each email to a Databricks user ID
    resolved_users  = {}   # email -> user_id
    not_found_users = []   # emails that could not be resolved

    print("Resolving user emails to workspace user IDs...")
    for email in user_emails:
        try:
            results = list(w.users.list(filter=f"userName eq \"{email}\""))
            if results:
                resolved_users[email] = results[0].id
                print(f"  ✅ {email} → ID {results[0].id}")
            else:
                not_found_users.append(email)
                print(f"  ⚠️  {email} — not found in this workspace (may not have been invited yet)")
        except Exception as exc:
            not_found_users.append(email)
            print(f"  ⚠️  {email} — lookup failed: {exc}")

    print()
    if not_found_users:
        print(f"  {len(not_found_users)} user(s) could not be resolved and will be skipped:")
        for e in not_found_users:
            print(f"    - {e}")

    # Remove each resolved user from the group
    removed   = []
    skipped   = []
    failed    = []

    print(f"\nRemoving {len(resolved_users)} user(s) from group '{GROUP_NAME}'...")
    for email, user_id in resolved_users.items():
        if email not in existing_members:
            skipped.append(email)
            print(f"  [SKIP] {email} — not a current member of '{GROUP_NAME}'")
            continue

        if DRY_RUN:
            removed.append(email)
            print(f"  [DRY RUN] Would remove {email} from '{GROUP_NAME}'")
        else:
            try:
                w.groups.patch(
                    id=target_group.id,
                    schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
                    operations=[
                        Patch(
                            op=PatchOp.REMOVE,
                            path=f"members[value eq \"{user_id}\"]",
                        )
                    ],
                )
                removed.append(email)
                print(f"  ✅ Removed: {email}")
            except Exception as exc:
                failed.append(email)
                print(f"  ❌ Failed to remove {email}: {exc}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Section 4 — Optionally Revoke Individual UC Grants (Remove-from-group mode only)
# MAGIC
# MAGIC **This section is OPTIONAL and not required in most cases.**
# MAGIC
# MAGIC When using "Remove users from group", the UC grants remain on the group — but the user
# MAGIC is no longer in the group, so they lose access automatically. You only need to run the
# MAGIC REVOKE statements below if you want to completely remove the group's UC privileges
# MAGIC (e.g., to repurpose the group for a different audience before the next cohort).
# MAGIC
# MAGIC If you used "Delete group entirely" in Section 3, all grants were already removed.
# MAGIC Skip this section entirely.

# COMMAND ----------

# OPTIONAL — only uncomment and run if you need to drop the group's UC grants
# without deleting the group itself (unusual scenario).
#
# Replace CATALOG and SCHEMA with the values used during setup (default: workshop_au, aemo).

# CATALOG = "workshop_au"
#
# # Revoke grants per session type
# session_revokes = {
#     "Session 3 — Business User": [
#         f"REVOKE USE CATALOG ON CATALOG {CATALOG} FROM `{GROUP_NAME}`",
#         f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.aemo FROM `{GROUP_NAME}`",
#         f"REVOKE SELECT ON SCHEMA {CATALOG}.aemo FROM `{GROUP_NAME}`",
#     ],
#     "Session 2 — Data Engineer / Data Scientist": [
#         f"REVOKE USE CATALOG ON CATALOG {CATALOG} FROM `{GROUP_NAME}`",
#         f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.energy FROM `{GROUP_NAME}`",
#         f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.aemo FROM `{GROUP_NAME}`",
#         f"REVOKE USE SCHEMA ON SCHEMA {CATALOG}.ai_governance FROM `{GROUP_NAME}`",
#         f"REVOKE SELECT ON SCHEMA {CATALOG}.energy FROM `{GROUP_NAME}`",
#         f"REVOKE EXECUTE ON SCHEMA {CATALOG}.energy FROM `{GROUP_NAME}`",
#         f"REVOKE SELECT ON SCHEMA {CATALOG}.aemo FROM `{GROUP_NAME}`",
#         f"REVOKE EXECUTE ON SCHEMA {CATALOG}.aemo FROM `{GROUP_NAME}`",
#         f"REVOKE SELECT ON SCHEMA {CATALOG}.ai_governance FROM `{GROUP_NAME}`",
#         f"REVOKE EXECUTE ON SCHEMA {CATALOG}.ai_governance FROM `{GROUP_NAME}`",
#     ],
#     # Add other session types as needed — mirror the GRANT statements from grant_workshop_access.py
# }
#
# revokes = session_revokes.get(SESSION_TYPE, [])
# if not revokes:
#     print(f"No REVOKE statements defined for session type '{SESSION_TYPE}'.")
# else:
#     for stmt in revokes:
#         print(f"  {'[DRY RUN] ' if DRY_RUN else ''}Executing: {stmt}")
#         if not DRY_RUN:
#             try:
#                 spark.sql(stmt)
#                 print(f"    ✅ Done.")
#             except Exception as exc:
#                 print(f"    ❌ Failed: {exc}")

print("Section 4 is commented out by default.")
print("Uncomment the block above only if you need to revoke the group's UC grants")
print("without deleting the group (rare scenario).")
print()
print("If you ran 'Delete group entirely' in Section 3, all grants are already revoked.")

# COMMAND ----------

# MAGIC %md ## Section 5 — Summary Report

# COMMAND ----------

print()
print("=" * 65)
print("  REVOCATION SUMMARY")
print("=" * 65)
print(f"  Session:      {SESSION_TYPE}")
print(f"  Group:        {GROUP_NAME}")
print(f"  Revoke mode:  {REVOKE_MODE}")
print(f"  Dry run:      {DRY_RUN}")
print()

if REVOKE_MODE == "Delete group entirely":
    if DRY_RUN:
        print(f"  [DRY RUN] Would delete group '{GROUP_NAME}'")
        print(f"  [DRY RUN] Would revoke all UC grants associated with this group")
        print(f"  [DRY RUN] {len(existing_members)} member(s) would lose access")
    else:
        print(f"  ✅ Group '{GROUP_NAME}' deleted")
        print(f"     All UC grants to this group have been revoked")
        print(f"     {len(existing_members)} member(s) have lost access")
else:
    if DRY_RUN:
        print(f"  [DRY RUN] Would remove {len(removed)} user(s) from '{GROUP_NAME}'")
    else:
        print(f"  Removed:  {len(removed)} user(s)")
        print(f"  Skipped:  {len(skipped)} user(s) (were not in the group)")
        print(f"  Failed:   {len(failed)} user(s)")
        print(f"  Not found:{len(not_found_users)} user(s) (not in workspace)")

    if removed:
        print()
        print("  Users removed:")
        for e in sorted(removed):
            prefix = "[DRY RUN] " if DRY_RUN else ""
            print(f"    {prefix}✅ {e}")

    if skipped:
        print()
        print("  Users skipped (not in group):")
        for e in sorted(skipped):
            print(f"    ⚠️  {e}")

    if failed:
        print()
        print("  Users that failed:")
        for e in sorted(failed):
            print(f"    ❌ {e}")

    if not_found_users:
        print()
        print("  Users not found in workspace:")
        for e in sorted(not_found_users):
            print(f"    ?  {e}")

print()
if DRY_RUN:
    print("  Re-run with dry_run=false to apply these changes.")
else:
    print("  Revocation complete.")
    if REVOKE_MODE == "Remove users from group":
        print()
        print("  Note: the group and its UC grants remain. Users removed from")
        print(f"  '{GROUP_NAME}' no longer inherit those grants.")
        print("  If this is the final session, consider re-running with")
        print("  revoke_mode='Delete group entirely' for complete cleanup.")
print("=" * 65)
