# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%); padding: 20px; border-radius: 8px">
# MAGIC   <h1 style="color: #FFB3B3; margin: 0">🗑️ Workshop Teardown</h1>
# MAGIC   <p style="color: #FFD0D0; margin: 4px 0 0 0">Removes all workshop resources from the customer environment</p>
# MAGIC </div>
# MAGIC
# MAGIC ## ⚠️ Run this AFTER the workshop to clean up the customer environment
# MAGIC
# MAGIC This notebook removes:
# MAGIC - Workshop catalog and all schemas/tables
# MAGIC - Model Serving endpoints created during the workshop
# MAGIC - Vector Search endpoint and indexes
# MAGIC - Genie Spaces created during the workshop
# MAGIC - AI Gateway endpoints
# MAGIC
# MAGIC **Does NOT remove:** Participant user accounts, workspace settings, or any pre-existing resources.

# COMMAND ----------
# MAGIC %md
# MAGIC ### ⚙️ Configuration
# MAGIC Set these to match what was used during setup. The defaults match the standard workshop values.
# MAGIC
# MAGIC **To do a dry run (see what WOULD be deleted without deleting anything):**
# MAGIC Set `dry_run` to `true` and `confirm_delete` to `false`, then run all cells.
# MAGIC
# MAGIC **To actually delete everything:**
# MAGIC Set `dry_run` to `false` AND `confirm_delete` to `true`, then run all cells.

# COMMAND ----------
dbutils.widgets.removeAll()
dbutils.widgets.text("catalog",           "workshop_au",          "1. Catalog name")
dbutils.widgets.text("schema_energy",     "energy",               "2. Energy data schema")
dbutils.widgets.text("schema_governance", "ai_governance",        "3. Governance schema")
dbutils.widgets.text("vs_endpoint",       "workshop_vs",          "4. Vector Search endpoint name")
dbutils.widgets.text("pt_endpoint",       "au_east_llm_inregion", "5. PT endpoint name")
dbutils.widgets.dropdown("dry_run",       "true",  ["true", "false"], "6. Dry run (true = no deletes)")
dbutils.widgets.dropdown("confirm_delete","false", ["true", "false"], "7. Confirm delete (must be true to delete)")

# COMMAND ----------
CATALOG           = dbutils.widgets.get("catalog")
SCHEMA_ENERGY     = dbutils.widgets.get("schema_energy")
SCHEMA_GOVERNANCE = dbutils.widgets.get("schema_governance")
VS_ENDPOINT       = dbutils.widgets.get("vs_endpoint")
PT_ENDPOINT       = dbutils.widgets.get("pt_endpoint")
DRY_RUN           = dbutils.widgets.get("dry_run").lower() == "true"
CONFIRM_DELETE    = dbutils.widgets.get("confirm_delete").lower() == "true"

print("=" * 65)
print("  WORKSHOP TEARDOWN — CONFIGURATION")
print("=" * 65)
print(f"  Catalog:              {CATALOG}")
print(f"  Energy schema:        {SCHEMA_ENERGY}")
print(f"  Governance schema:    {SCHEMA_GOVERNANCE}")
print(f"  VS endpoint:          {VS_ENDPOINT}")
print(f"  PT endpoint:          {PT_ENDPOINT}")
print()
print(f"  DRY_RUN:              {DRY_RUN}")
print(f"  CONFIRM_DELETE:       {CONFIRM_DELETE}")
print("=" * 65)

if DRY_RUN:
    print()
    print("  *** DRY RUN MODE — nothing will be deleted ***")
    print("  Set dry_run=false and confirm_delete=true to actually delete resources.")
elif not CONFIRM_DELETE:
    print()
    print("  *** DRY RUN MODE (confirm_delete not set) — nothing will be deleted ***")
    print("  Set confirm_delete=true (and dry_run=false) to actually delete resources.")
else:
    print()
    print("  *** LIVE DELETE MODE — resources will be permanently removed ***")
    print("  This cannot be undone. Ensure you have a backup of any data you need.")

# Effective delete flag — both conditions must be satisfied
WILL_DELETE = (not DRY_RUN) and CONFIRM_DELETE

# COMMAND ----------

import time
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Track what was actually removed for the final summary
removed  = []
skipped  = []
errors   = []


def _action(resource_type: str, name: str, fn, reason: str = "") -> None:
    """
    Execute a delete action, respecting DRY_RUN / CONFIRM_DELETE flags.
    Records the outcome in removed / skipped / errors.
    """
    label = f"{resource_type}: {name}"
    if not WILL_DELETE:
        print(f"  [DRY RUN] Would remove {label}{(' — ' + reason) if reason else ''}")
        skipped.append(label)
        return
    try:
        fn()
        msg = f"Removed {label}{(' — ' + reason) if reason else ''}"
        print(f"  ✅ {msg}")
        removed.append(label)
    except Exception as exc:
        msg = f"{label}: {exc}"
        print(f"  ❌ Error removing {label}: {exc}")
        errors.append(msg)

# COMMAND ----------

# MAGIC %md ## 1 — Drop Workshop Catalog (CASCADE)

# COMMAND ----------

print("=" * 65)
print("STEP 1 — DROP WORKSHOP CATALOG")
print("=" * 65)

# Safety check: only drop the catalog if it matches the configured name
# and (in live mode) confirm it's not a critical production catalog name
PROTECTED_CATALOGS = {"main", "hive_metastore", "system", "__databricks_internal"}

if CATALOG.lower() in PROTECTED_CATALOGS:
    msg = (
        f"Refusing to drop catalog '{CATALOG}' — it is a protected system catalog. "
        "Update the 'catalog' widget to the workshop-specific catalog name."
    )
    print(f"  ❌ {msg}")
    errors.append(f"DROP CATALOG aborted: {msg}")
else:
    try:
        existing_catalogs = {c.name for c in w.catalogs.list()}
    except Exception as exc:
        existing_catalogs = set()
        print(f"  ⚠️  Could not list catalogs: {exc}")

    if CATALOG not in existing_catalogs:
        print(f"  ℹ️  Catalog '{CATALOG}' does not exist — nothing to drop.")
        skipped.append(f"Catalog: {CATALOG} (not found)")
    else:
        # Show what will be dropped before dropping
        try:
            schemas = [s.name for s in w.schemas.list(catalog_name=CATALOG)]
            print(f"\n  Catalog '{CATALOG}' contains schemas: {', '.join(schemas) or '(none)'}")
            for schema in schemas:
                try:
                    tables = [t.name for t in w.tables.list(catalog_name=CATALOG, schema_name=schema)]
                    if tables:
                        print(f"    Schema '{schema}': {', '.join(tables)}")
                except Exception:
                    pass
        except Exception as exc:
            print(f"  ⚠️  Could not enumerate catalog contents: {exc}")

        print()
        _action(
            "Catalog (CASCADE)",
            CATALOG,
            lambda: spark.sql(f"DROP CATALOG IF EXISTS {CATALOG} CASCADE"),
            reason="drops all schemas, tables, views, and volumes inside",
        )

# COMMAND ----------

# MAGIC %md ## 2 — Delete Model Serving Endpoints

# COMMAND ----------

print("=" * 65)
print("STEP 2 — DELETE MODEL SERVING ENDPOINTS")
print("=" * 65)

# Endpoint names that are safe to delete:
# 1. Exactly matches the configured PT_ENDPOINT name
# 2. Contains "workshop" in the name (catch-all for workshop-created endpoints)
# 3. Starts with the configured catalog name (naming convention: <catalog>_*)
# We never touch FMAPI pay-per-token endpoints (names start with "databricks-")

WORKSHOP_ENDPOINT_NAMES = {PT_ENDPOINT}

print(f"\nLooking for endpoints to delete...")
print(f"  Will delete: '{PT_ENDPOINT}' (configured PT endpoint)")
print(f"  Will also delete any endpoint whose name contains 'workshop'")
print(f"  Will NOT delete pay-per-token FMAPI endpoints (databricks-* prefix)")
print()

try:
    all_endpoints = list(w.serving_endpoints.list())
except Exception as exc:
    print(f"  ❌ Could not list serving endpoints: {exc}")
    errors.append(f"List serving endpoints: {exc}")
    all_endpoints = []

for ep in all_endpoints:
    ep_name = ep.name or ""

    # Skip system / FMAPI endpoints
    if ep_name.startswith("databricks-"):
        print(f"  Skipping FMAPI endpoint: {ep_name}")
        continue

    # Delete if it's a configured workshop endpoint or has "workshop" in the name
    should_delete = (
        ep_name in WORKSHOP_ENDPOINT_NAMES
        or "workshop" in ep_name.lower()
    )

    if should_delete:
        _action(
            "Serving endpoint",
            ep_name,
            lambda n=ep_name: w.serving_endpoints.delete(name=n),
        )
    else:
        print(f"  Leaving untouched: {ep_name}")

if not all_endpoints:
    print("  No serving endpoints found.")

# COMMAND ----------

# MAGIC %md ## 3 — Delete Vector Search Endpoint and Indexes

# COMMAND ----------

print("=" * 65)
print("STEP 3 — DELETE VECTOR SEARCH ENDPOINT AND INDEXES")
print("=" * 65)

# Safety: only delete VS endpoints that match the configured name or contain "workshop"
WORKSHOP_VS_NAMES = {VS_ENDPOINT}

print(f"\nTarget VS endpoint: '{VS_ENDPOINT}'")
print()

try:
    vs_endpoints = list(w.vector_search_endpoints.list_endpoints())
except Exception as exc:
    print(f"  ❌ Could not list Vector Search endpoints: {exc}")
    errors.append(f"List VS endpoints: {exc}")
    vs_endpoints = []

for vs_ep in vs_endpoints:
    ep_name = vs_ep.name or ""

    should_delete = (
        ep_name in WORKSHOP_VS_NAMES
        or "workshop" in ep_name.lower()
    )

    if not should_delete:
        print(f"  Leaving untouched: {ep_name}")
        continue

    # First delete all indexes on this endpoint
    print(f"\n  Endpoint '{ep_name}' — deleting indexes first...")
    try:
        indexes = list(w.vector_search_indexes.list_indexes(endpoint_name=ep_name))
    except Exception as exc:
        indexes = []
        print(f"    ⚠️  Could not list indexes: {exc}")

    for idx in indexes:
        idx_name = idx.name or ""
        _action(
            "VS index",
            idx_name,
            lambda n=idx_name: w.vector_search_indexes.delete_index(index_name=n),
        )

    if WILL_DELETE and indexes:
        # Give the platform a moment to process index deletions before removing the endpoint
        print(f"    Waiting 15 seconds for index deletion to propagate...")
        time.sleep(15)

    _action(
        "VS endpoint",
        ep_name,
        lambda n=ep_name: w.vector_search_endpoints.delete_endpoint(endpoint_name=n),
    )

if not vs_endpoints:
    print("  No Vector Search endpoints found.")

# COMMAND ----------

# MAGIC %md ## 4 — Delete Genie Spaces

# COMMAND ----------

print("=" * 65)
print("STEP 4 — DELETE GENIE SPACES")
print("=" * 65)

# Genie Space names created by the setup notebook
WORKSHOP_GENIE_NAMES = {
    "AU Energy Workshop — Regulated Data Assistant",
}

# Also delete any Genie space whose title contains "workshop" (case-insensitive)
print(f"\nLooking for Genie spaces to delete...")
print(f"  Configured names: {', '.join(WORKSHOP_GENIE_NAMES)}")
print(f"  Will also delete any space whose title contains 'workshop'")
print()

try:
    all_spaces = list(w.genie.list_spaces())
except Exception as exc:
    print(f"  ⚠️  Could not list Genie spaces: {exc}")
    print("      (This may mean Genie is not enabled on this workspace — that is OK.)")
    all_spaces = []

for space in all_spaces:
    space_title = space.title or ""
    space_id    = space.id or ""

    should_delete = (
        space_title in WORKSHOP_GENIE_NAMES
        or "workshop" in space_title.lower()
    )

    if should_delete:
        _action(
            "Genie Space",
            f"'{space_title}' (ID: {space_id})",
            lambda sid=space_id: w.genie.delete_space(space_id=sid),
        )
    else:
        print(f"  Leaving untouched: '{space_title}' (ID: {space_id})")

if not all_spaces:
    print("  No Genie spaces found (or Genie API not accessible).")

# COMMAND ----------

# MAGIC %md ## 5 — Delete Workshop Participant Groups

# COMMAND ----------

print("=" * 65)
print("STEP 5 — DELETE WORKSHOP PARTICIPANT GROUPS")
print("=" * 65)

# All group names created by grant_workshop_access.py
WORKSHOP_GROUP_NAMES = {
    "workshop_s3_participants",
    "workshop_s2_data_engineers",
    "workshop_s2a_developers",
    "workshop_s2c_agent_builders",
}

print(f"\nLooking for workshop groups to delete...")
print(f"  Target groups: {', '.join(sorted(WORKSHOP_GROUP_NAMES))}")
print()

try:
    # List groups that match any of our workshop group names
    groups_found = []
    for group_name in WORKSHOP_GROUP_NAMES:
        try:
            results = list(w.groups.list(filter=f"displayName eq '{group_name}'"))
            groups_found.extend(results)
        except Exception as exc:
            print(f"  ⚠️  Could not query group '{group_name}': {exc}")

    if not groups_found:
        print("  No workshop participant groups found — already cleaned up or never created.")
    else:
        for grp in groups_found:
            grp_name = grp.display_name or ""
            grp_id   = grp.id or ""
            _action(
                "Participant group",
                f"'{grp_name}' (ID: {grp_id})",
                lambda gid=grp_id: w.groups.delete(id=gid),
            )

except Exception as exc:
    print(f"  ❌ Could not list/delete groups: {exc}")
    errors.append(f"Group cleanup: {exc}")

# COMMAND ----------

# MAGIC %md ## 6 — Final Summary

# COMMAND ----------

print()
print("=" * 65)
print("  TEARDOWN SUMMARY")
print(f"  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 65)

if not WILL_DELETE:
    print()
    print("  *** THIS WAS A DRY RUN — nothing was deleted ***")
    print()
    print(f"  Resources that WOULD have been removed ({len(skipped)}):")
    for s in skipped:
        print(f"    - {s}")
    print()
    print("  To actually delete:")
    print("    1. Set widget 'dry_run'        → false")
    print("    2. Set widget 'confirm_delete' → true")
    print("    3. Re-run all cells")
else:
    print()
    if removed:
        print(f"  ✅ Removed ({len(removed)}):")
        for r in removed:
            print(f"    - {r}")
    else:
        print("  ℹ️  Nothing was removed (resources may have already been absent).")

    if skipped:
        print()
        print(f"  ⏭️  Skipped ({len(skipped)}) — resources already absent or protected:")
        for s in skipped:
            print(f"    - {s}")

    if errors:
        print()
        print(f"  ❌ Errors ({len(errors)}) — manual cleanup may be needed:")
        for e in errors:
            print(f"    - {e}")
        print()
        print("  For manual cleanup:")
        print("    - Catalog:  Catalog Explorer → right-click catalog → Delete")
        print("    - VS endpoint: Compute → Vector Search → Delete endpoint")
        print("    - Serving endpoints: Serving → [endpoint name] → Delete")
        print("    - Genie spaces:   Data Intelligence → Genie → Space settings → Delete")
    else:
        print()
        print("  ✅ Teardown completed with no errors.")

print()
print("  Participant user accounts and workspace settings were NOT modified.")
print("  Pre-existing resources (FMAPI endpoints, existing catalogs) were NOT touched.")
print("=" * 65)
