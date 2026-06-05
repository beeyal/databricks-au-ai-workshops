# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Ataccama → Unity Catalog Metadata Sync</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Extracts table and column descriptions from Ataccama ONE and applies them to Unity Catalog</p>
# MAGIC </div>
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Connects to Ataccama ONE REST API and extracts all catalog entities (tables/views) with their descriptions
# MAGIC 2. Extracts column-level descriptions for each entity
# MAGIC 3. Maps Ataccama entities to UC `catalog.schema.table` paths
# MAGIC 4. Applies descriptions to Unity Catalog via `COMMENT ON TABLE` and `ALTER TABLE ALTER COLUMN COMMENT`
# MAGIC
# MAGIC **Dry run mode (default ON):** prints what would change without writing anything.
# MAGIC Set `DRY_RUN = False` to apply changes.
# MAGIC
# MAGIC **Prerequisites:** Ataccama ONE URL + API credentials (username/password or API token).

# COMMAND ----------

# ── Configuration ─────────────────────────────────────────────────────────────
dbutils.widgets.text("ataccama_url",      "",             "Ataccama ONE URL (e.g. https://ataccama.yourorg.com)")
dbutils.widgets.text("ataccama_username", "",             "Ataccama username")
dbutils.widgets.text("ataccama_password", "",             "Ataccama password")
dbutils.widgets.text("ataccama_api_token","",             "Ataccama API token (alternative to user/pass)")
dbutils.widgets.text("uc_catalog",        "",             "UC catalog to update (leave blank to process all)")
dbutils.widgets.text("uc_schema",         "",             "UC schema to update (leave blank for all schemas)")
dbutils.widgets.text("source_filter",     "",             "Filter by Ataccama source name (leave blank for all)")
dbutils.widgets.dropdown("dry_run",       "true", ["true","false"], "Dry run — preview only, no changes written")
dbutils.widgets.dropdown("overwrite",     "false",["true","false"], "Overwrite existing descriptions")

ATACCAMA_URL      = dbutils.widgets.get("ataccama_url").rstrip("/")
ATACCAMA_USERNAME = dbutils.widgets.get("ataccama_username")
ATACCAMA_PASSWORD = dbutils.widgets.get("ataccama_password")
ATACCAMA_TOKEN    = dbutils.widgets.get("ataccama_api_token")
UC_CATALOG        = dbutils.widgets.get("uc_catalog") or None
UC_SCHEMA         = dbutils.widgets.get("uc_schema") or None
SOURCE_FILTER     = dbutils.widgets.get("source_filter") or None
DRY_RUN           = dbutils.widgets.get("dry_run") == "true"
OVERWRITE         = dbutils.widgets.get("overwrite") == "true"

if not ATACCAMA_URL:
    raise ValueError("Ataccama URL is required. Enter it in the 'ataccama_url' widget.")

mode = "DRY RUN — nothing will be written" if DRY_RUN else "LIVE — descriptions will be applied to Unity Catalog"
print(f"Mode          : {mode}")
print(f"Ataccama URL  : {ATACCAMA_URL}")
print(f"UC target     : {UC_CATALOG or 'all catalogs'}.{UC_SCHEMA or 'all schemas'}")
print(f"Source filter : {SOURCE_FILTER or 'all sources'}")
print(f"Overwrite     : {OVERWRITE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Authenticate with Ataccama ONE

# COMMAND ----------

import requests
import json
from typing import Optional

session = requests.Session()
session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

def _auth_headers() -> dict:
    """Return auth headers — token takes priority over username/password."""
    if ATACCAMA_TOKEN:
        return {"Authorization": f"Bearer {ATACCAMA_TOKEN}"}
    if ATACCAMA_USERNAME and ATACCAMA_PASSWORD:
        import base64
        creds = base64.b64encode(f"{ATACCAMA_USERNAME}:{ATACCAMA_PASSWORD}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}
    raise ValueError("Provide either ataccama_api_token or ataccama_username + ataccama_password.")

AUTH_HEADERS = _auth_headers()
session.headers.update(AUTH_HEADERS)

# Verify connectivity
try:
    resp = session.get(f"{ATACCAMA_URL}/api/v1/catalog/entities", params={"limit": 1})
    if resp.status_code == 401:
        raise ValueError(f"Authentication failed (401). Check your credentials.")
    elif resp.status_code == 404:
        # Try alternative API path (Ataccama ONE agentic/cloud uses /one/api)
        resp = session.get(f"{ATACCAMA_URL}/one/api/v1/catalog/entities", params={"limit": 1})
        if resp.ok:
            API_BASE = f"{ATACCAMA_URL}/one/api/v1"
        else:
            raise ValueError(f"Cannot reach Ataccama API. Got {resp.status_code}. Check the URL.")
    elif resp.ok:
        API_BASE = f"{ATACCAMA_URL}/api/v1"
    else:
        raise ValueError(f"Ataccama API returned {resp.status_code}: {resp.text[:200]}")
    print(f"✅ Connected to Ataccama ONE ({resp.status_code})")
    print(f"   API base: {API_BASE}")
except requests.exceptions.ConnectionError as e:
    raise ConnectionError(f"Cannot connect to {ATACCAMA_URL}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Extract all catalog entities (tables/views) with descriptions

# COMMAND ----------

def get_all_entities(source_filter: Optional[str] = None) -> list[dict]:
    """
    Fetch all catalog entities from Ataccama ONE.
    Returns a flat list of entity dicts, each with:
      - id, name, description, type
      - sourceId, sourceName, schemaName, tableName (parsed from entity path)
    """
    entities = []
    limit = 100
    offset = 0

    params = {"limit": limit, "orderBy": "name"}
    if source_filter:
        params["filter"] = f"sourceName='{source_filter}'"

    while True:
        params["offset"] = offset
        resp = session.get(f"{API_BASE}/catalog/entities", params=params)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", data.get("data", data.get("content", [])))
        if not items:
            break

        for item in items:
            entities.append(item)

        total = data.get("total", data.get("totalElements", len(items)))
        offset += limit
        if offset >= total or len(items) < limit:
            break

    return entities

print("Fetching entities from Ataccama catalog...")
all_entities = get_all_entities(SOURCE_FILTER)
print(f"  Found {len(all_entities)} entities total")

# Show a sample to understand the structure
if all_entities:
    sample = all_entities[0]
    print(f"\n  Sample entity keys: {list(sample.keys())}")
    print(f"  Sample entity: {json.dumps(sample, indent=2)[:600]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Parse entity paths → UC `catalog.schema.table` mapping
# MAGIC
# MAGIC Ataccama stores entities with a source path like `oracle://schema/table` or `databricks://catalog/schema/table`.
# MAGIC This step extracts the UC-compatible names.
# MAGIC
# MAGIC **Adjust the `_parse_uc_path` function** if your Ataccama entity naming convention differs.

# COMMAND ----------

def _parse_uc_path(entity: dict) -> Optional[tuple[str, str, str]]:
    """
    Parse an Ataccama entity into a (catalog, schema, table) tuple.
    Returns None if the entity cannot be mapped to UC.

    Ataccama entity fields vary by connector type. Common patterns:
    - entity["sourcePath"] = "catalog.schema.table"
    - entity["path"] = "/catalog/schema/table"
    - entity["location"] / entity["connectionPath"]
    - entity["parentPath"] + entity["name"]
    """
    name = entity.get("name", "")

    # Pattern A: entity has explicit catalog/schema/table fields
    if all(k in entity for k in ["catalogName", "schemaName", "tableName"]):
        return entity["catalogName"], entity["schemaName"], entity["tableName"]

    # Pattern B: entity has a dot-separated full path
    for path_field in ["fullName", "sourcePath", "qualifiedName", "fullPath"]:
        path = entity.get(path_field, "")
        if path and path.count(".") >= 2:
            parts = path.split(".")
            return parts[-3], parts[-2], parts[-1]

    # Pattern C: entity has parentPath + name
    parent = entity.get("parentPath", entity.get("schemaPath", ""))
    if parent and name:
        parent_parts = parent.strip("/").split("/")
        if len(parent_parts) >= 2:
            return parent_parts[-2], parent_parts[-1], name
        elif len(parent_parts) == 1:
            # Only schema known, no catalog
            return None, parent_parts[0], name

    # Pattern D: entity["location"] = "databricks://catalog/schema/table"
    location = entity.get("location", entity.get("connectionPath", ""))
    if location:
        import re
        m = re.search(r'(?:databricks://|/)([^/]+)/([^/]+)/([^/]+)$', location)
        if m:
            return m.group(1), m.group(2), m.group(3)

    # Pattern E: just a name with dots
    if "." in name:
        parts = name.split(".")
        if len(parts) == 3:
            return tuple(parts)
        if len(parts) == 2:
            return None, parts[0], parts[1]

    return None  # Cannot map this entity

# Test the parser on sample entities
print("Testing entity path parser on first 5 entities:")
for e in all_entities[:5]:
    result = _parse_uc_path(e)
    print(f"  {e.get('name','?')[:50]} → {result}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Get column descriptions for each entity

# COMMAND ----------

def get_columns(entity_id: str) -> list[dict]:
    """
    Fetch attributes (columns) for a catalog entity.
    Returns list of dicts with: name, description, dataType, position.
    """
    # Try different endpoint patterns
    for endpoint in [
        f"{API_BASE}/catalog/entities/{entity_id}/attributes",
        f"{API_BASE}/catalog/entities/{entity_id}/columns",
        f"{API_BASE}/catalog/attributes",
    ]:
        params = {"entityId": entity_id} if "attributes" in endpoint and entity_id not in endpoint else {}
        resp = session.get(endpoint, params=params)
        if resp.ok:
            data = resp.json()
            items = data.get("items", data.get("data", data.get("content", [])))
            return items
    return []

# Test on first entity
if all_entities:
    test_entity = all_entities[0]
    test_cols = get_columns(test_entity.get("id", test_entity.get("entityId", "")))
    print(f"Sample columns for '{test_entity.get('name','?')}':")
    if test_cols:
        print(f"  Column keys: {list(test_cols[0].keys())}")
        for c in test_cols[:3]:
            print(f"  {c.get('name','?')}: {c.get('description','(no description)')[:80]}")
    else:
        print("  No columns returned — adjust endpoint in get_columns()")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Build the full metadata map

# COMMAND ----------

from dataclasses import dataclass, field

@dataclass
class TableMeta:
    catalog: Optional[str]
    schema: str
    table: str
    table_description: str
    columns: list[dict] = field(default_factory=list)  # [{name, description}]

    @property
    def fqn(self) -> str:
        if self.catalog:
            return f"{self.catalog}.{self.schema}.{self.table}"
        return f"{self.schema}.{self.table}"

print("Building metadata map...")
metadata: list[TableMeta] = []
skipped = 0

for entity in all_entities:
    # Skip entities with no description
    desc = (entity.get("description") or entity.get("businessDescription") or "").strip()

    path = _parse_uc_path(entity)
    if not path:
        skipped += 1
        continue

    cat, schema, table = path

    # Apply UC catalog/schema filters
    if UC_CATALOG and cat and cat != UC_CATALOG:
        skipped += 1
        continue
    if UC_SCHEMA and schema != UC_SCHEMA:
        skipped += 1
        continue

    # Use widget catalog if entity has no catalog
    if not cat and UC_CATALOG:
        cat = UC_CATALOG

    entity_id = entity.get("id", entity.get("entityId", ""))
    raw_cols = get_columns(entity_id) if entity_id else []

    columns = []
    for col in raw_cols:
        col_desc = (col.get("description") or col.get("businessDescription") or "").strip()
        col_name = col.get("name", col.get("attributeName", ""))
        if col_name:
            columns.append({"name": col_name, "description": col_desc})

    metadata.append(TableMeta(
        catalog=cat,
        schema=schema,
        table=table,
        table_description=desc,
        columns=columns,
    ))

print(f"  ✅ {len(metadata)} entities mapped to UC paths")
print(f"  ⚠️  {skipped} entities skipped (unmappable path or filtered out)")
print()
print(f"  With table descriptions: {sum(1 for m in metadata if m.table_description)}")
print(f"  With column descriptions: {sum(1 for m in metadata if any(c['description'] for c in m.columns))}")

# Show preview
print("\nPreview (first 5):")
for m in metadata[:5]:
    col_count = sum(1 for c in m.columns if c["description"])
    print(f"  {m.fqn}")
    print(f"    Table: {m.table_description[:70] or '(none)'}")
    print(f"    Columns with descriptions: {col_count}/{len(m.columns)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Apply descriptions to Unity Catalog

# COMMAND ----------

results = {"table_ok": 0, "table_skip": 0, "table_err": 0,
           "col_ok": 0, "col_skip": 0, "col_err": 0}

def _escape(s: str) -> str:
    return s.replace("'", "\\'").replace("\n", " ").strip()

def _table_has_description(fqn: str) -> bool:
    """Check if UC table already has a description."""
    try:
        parts = fqn.split(".")
        if len(parts) == 3:
            df = spark.sql(f"SELECT comment FROM {parts[0]}.information_schema.tables "
                          f"WHERE table_schema='{parts[1]}' AND table_name='{parts[2]}'")
        else:
            df = spark.sql(f"SELECT comment FROM information_schema.tables "
                          f"WHERE table_schema='{parts[0]}' AND table_name='{parts[1]}'")
        rows = df.collect()
        return bool(rows and rows[0]["comment"])
    except Exception:
        return False

def _col_has_description(fqn: str, col_name: str) -> bool:
    """Check if a UC column already has a description."""
    try:
        parts = fqn.split(".")
        if len(parts) == 3:
            df = spark.sql(f"SELECT comment FROM {parts[0]}.information_schema.columns "
                          f"WHERE table_schema='{parts[1]}' AND table_name='{parts[2]}' "
                          f"AND column_name='{col_name}'")
        else:
            df = spark.sql(f"SELECT comment FROM information_schema.columns "
                          f"WHERE table_schema='{parts[0]}' AND table_name='{parts[1]}' "
                          f"AND column_name='{col_name}'")
        rows = df.collect()
        return bool(rows and rows[0]["comment"])
    except Exception:
        return False

print(f"Applying descriptions {'(DRY RUN)' if DRY_RUN else '(LIVE)'}...\n")

for m in metadata:
    fqn = m.fqn

    # ── Table description ───────────────────────────────────────────────────
    if m.table_description:
        already_has = not OVERWRITE and _table_has_description(fqn)
        if already_has:
            results["table_skip"] += 1
        else:
            sql = f"COMMENT ON TABLE {fqn} IS '{_escape(m.table_description)}'"
            if DRY_RUN:
                print(f"  [DRY RUN] {sql[:120]}")
                results["table_ok"] += 1
            else:
                try:
                    spark.sql(sql)
                    results["table_ok"] += 1
                except Exception as e:
                    print(f"  ❌ Table {fqn}: {e}")
                    results["table_err"] += 1
    else:
        results["table_skip"] += 1

    # ── Column descriptions ─────────────────────────────────────────────────
    for col in m.columns:
        if not col["description"]:
            results["col_skip"] += 1
            continue

        col_name = col["name"]
        already_has = not OVERWRITE and _col_has_description(fqn, col_name)
        if already_has:
            results["col_skip"] += 1
            continue

        sql = f"ALTER TABLE {fqn} ALTER COLUMN `{col_name}` COMMENT '{_escape(col['description'])}'"
        if DRY_RUN:
            print(f"  [DRY RUN] {sql[:120]}")
            results["col_ok"] += 1
        else:
            try:
                spark.sql(sql)
                results["col_ok"] += 1
            except Exception as e:
                print(f"  ❌ Column {fqn}.{col_name}: {e}")
                results["col_err"] += 1

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("=" * 55)
print(f"  {'Dry run preview' if DRY_RUN else 'Sync complete'}")
print("=" * 55)
print()
print(f"  Tables updated  : {results['table_ok']}")
print(f"  Tables skipped  : {results['table_skip']}  (already had description or no description in Ataccama)")
print(f"  Tables errored  : {results['table_err']}")
print()
print(f"  Columns updated : {results['col_ok']}")
print(f"  Columns skipped : {results['col_skip']}")
print(f"  Columns errored : {results['col_err']}")
print()
if DRY_RUN:
    print("⚠️  DRY RUN — set dry_run widget to 'false' to apply changes.")
else:
    print("✅ Done. Verify in Catalog Explorer → select a table → Overview tab.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Troubleshooting
# MAGIC
# MAGIC ### Entity path parser returned None for all entities
# MAGIC Ataccama entity naming varies by connector. Run the cell below to inspect raw entity structure
# MAGIC and adjust `_parse_uc_path()` accordingly.

# COMMAND ----------

# Diagnostic: print raw structure of first 3 entities to help adjust the path parser
if all_entities:
    print("Raw entity structure (first 3) — use this to adjust _parse_uc_path():\n")
    for e in all_entities[:3]:
        print(json.dumps(e, indent=2)[:800])
        print("---")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Entity has columns but no descriptions were found
# MAGIC Check the raw column structure below and adjust `get_columns()` if needed.

# COMMAND ----------

# Diagnostic: print raw column structure for the first entity
if all_entities:
    entity_id = all_entities[0].get("id", all_entities[0].get("entityId", ""))
    raw = get_columns(entity_id)
    if raw:
        print(f"Raw column structure for '{all_entities[0].get('name','?')}':\n")
        print(json.dumps(raw[:2], indent=2)[:800])
    else:
        print("No columns returned. The entity may use a different attributes endpoint.")
        print("Try: GET /api/v1/catalog/entities/{id}/attributes or /api/v1/catalog/attributes?entityId={id}")
