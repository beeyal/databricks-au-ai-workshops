# Databricks notebook source
# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 24px; border-radius: 8px; margin-bottom: 8px">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 26px">Lab 05: The Operating Model</h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 13px">Session 2: Building the Best Genie Space · AEMO Enablement</p>
# MAGIC </div>
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | ⏱️ **Duration** | 20 minutes |
# MAGIC | **Covers** | Exploratory vs Certified spaces, certification checklist, space registry |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## The two-speed model
# MAGIC
# MAGIC Not all Genie Spaces are equal — and they shouldn't be. Running two tiers in parallel keeps quality high without slowing down exploration.
# MAGIC
# MAGIC | | **Exploratory** | **Certified** |
# MAGIC |---|---|---|
# MAGIC | **Purpose** | Discovery, ideation, prototyping | Production answers for business users |
# MAGIC | **Who builds** | Data analysts | Data engineers |
# MAGIC | **Tables** | Broad, sometimes untidy | Focused (≤5), well-documented |
# MAGIC | **Column comments** | Optional | Required — all key columns |
# MAGIC | **Golden queries** | Few or none | 10+ validated, parameterised |
# MAGIC | **Benchmark score** | Not measured | >80% Good required |
# MAGIC | **Audience** | Small team, data people | Business unit, non-technical users |
# MAGIC | **UC permissions** | Loose | Carefully scoped per role |
# MAGIC | **Monitoring** | Light | Feedback alert + weekly Monitor review |
# MAGIC | **Owner** | Anyone | Named person, accountable for quality |
# MAGIC
# MAGIC **The key rule:** business users should only ever access Certified spaces.
# MAGIC Exploratory spaces are for the data team to iterate in private.

# COMMAND ----------

dbutils.widgets.text("genie_space_id", "", "Space ID to certify")
dbutils.widgets.text("space_name",     "", "Space name (for registry)")
dbutils.widgets.text("space_owner",    "", "Owner email")

SPACE_ID   = dbutils.widgets.get("genie_space_id")
SPACE_NAME = dbutils.widgets.get("space_name") or "AEMO NEM Operations"
OWNER      = dbutils.widgets.get("space_owner")
CATALOG    = "workshop_au"
SCHEMA_GOV = "ai_governance"
HOST       = spark.conf.get("spark.databricks.workspaceUrl")
TOKEN      = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
HEADERS    = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print(f"Space: {SPACE_NAME} ({SPACE_ID or 'ID not set'})")
print(f"Owner: {OWNER or '(not set)'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Run the certification checklist
# MAGIC
# MAGIC **⚡ Automated** — checks every certification requirement and prints PASS / FAIL / WARN

# COMMAND ----------

import requests, json

checks = []

def check(label, passed, detail="", fix=""):
    icon = "✅ PASS" if passed else "❌ FAIL"
    checks.append({"label": label, "passed": passed, "detail": detail, "fix": fix})
    print(f"{icon}  {label}")
    if detail:
        print(f"         {detail}")
    if not passed and fix:
        print(f"         Fix: {fix}")

# ── 1. Column comments ──────────────────────────────────────────────────────
key_cols = {
    "spot_prices":          ["rrp", "region_id", "settlement_date"],
    "dispatch_intervals":   ["duid", "dispatch_mw", "fuel_type"],
    "market_notices":       ["notice_type", "issue_time"],
}
missing_comments = []
for tbl, cols in key_cols.items():
    rows = spark.sql(f"""
        SELECT column_name, comment
        FROM system.information_schema.columns
        WHERE table_catalog='{CATALOG}' AND table_schema='aemo'
          AND table_name='{tbl}' AND column_name IN ({','.join("'" + c + "'" for c in cols)})
    """).collect()
    for r in rows:
        if not r["comment"]:
            missing_comments.append(f"{tbl}.{r['column_name']}")

check(
    "Column comments set on key columns",
    len(missing_comments) == 0,
    detail=f"{len(missing_comments)} missing: {', '.join(missing_comments[:3])}" if missing_comments else "All key columns have comments",
    fix="Run Lab 01 Step 1 automated script"
)

# ── 2. Space exists and has tables ──────────────────────────────────────────
if SPACE_ID:
    resp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}", headers=HEADERS)
    if resp.status_code == 200:
        s      = resp.json()
        tables = len(s.get("datasets", []))
        check("Space accessible with tables added", tables >= 3,
              detail=f"{tables} tables", fix="Add tables in Configure → Data")
    else:
        check("Space accessible", False, detail=f"HTTP {resp.status_code}",
              fix="Verify SPACE_ID in widget")
else:
    check("Space ID provided", False, fix="Enter Space ID in widget above")

# ── 3. Golden queries ────────────────────────────────────────────────────────
if SPACE_ID:
    qresp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
                         headers=HEADERS)
    if qresp.status_code == 200:
        n_queries = len(qresp.json().get("sql_queries", []))
        check("10+ golden queries", n_queries >= 5,
              detail=f"{n_queries} queries (target 10+, workshop minimum 5)",
              fix="Run Lab 02 Step 2 automated script")
    else:
        check("Golden queries readable", False)

# ── 4. Benchmarks ────────────────────────────────────────────────────────────
if SPACE_ID:
    bresp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-runs",
                         headers=HEADERS)
    if bresp.status_code == 200:
        runs = bresp.json().get("benchmark_runs", [])
        if runs:
            latest  = runs[0]
            results = latest.get("benchmark_results", [])
            good    = sum(1 for r in results if r.get("rating") == "GOOD")
            total   = len(results)
            score   = round(good * 100 / total) if total else 0
            check("Benchmark score ≥80%", score >= 80,
                  detail=f"{score}% ({good}/{total} Good)",
                  fix="Run Lab 03 — identify failures, add golden queries, re-run")
        else:
            check("Benchmarks run at least once", False, fix="Run Lab 03 Step 1")
    else:
        check("Benchmarks accessible", False)

# ── 5. Instructions ──────────────────────────────────────────────────────────
if SPACE_ID:
    iresp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/instructions",
                         headers=HEADERS)
    if iresp.status_code == 200:
        n_instr = len(iresp.json().get("instructions", []))
        check("Text instructions present", n_instr >= 1,
              detail=f"{n_instr} instructions",
              fix="Run Lab 02 Step 3 automated script")

# ── 6. Owner set ─────────────────────────────────────────────────────────────
check("Named space owner provided", bool(OWNER),
      detail=OWNER or "(not set)",
      fix="Enter owner email in widget above")

# ── 7. Feedback alert ────────────────────────────────────────────────────────
# We can't check if an alert exists via API easily — ask the user
print("\n  ⚠️  MANUAL: Feedback alert configured?")
print("         Check: Alerts → search 'Genie Negative Feedback'")
print("         If missing: run Lab 04 Step 4")

# ── Summary ──────────────────────────────────────────────────────────────────
passed  = sum(1 for c in checks if c["passed"])
total_c = len(checks)
print(f"\n{'='*50}")
print(f"Certification score: {passed}/{total_c} checks passed")
if passed == total_c:
    print("🎉 Ready to certify!")
else:
    print(f"⚠️  Fix {total_c - passed} issue(s) before certifying.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Create the Space Registry
# MAGIC
# MAGIC Track all Genie Spaces across the organisation — their status, owner, and certification history.
# MAGIC
# MAGIC **⚡ Automated** — creates the registry table if it doesn't exist, then upserts this space.

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA_GOV}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA_GOV}.genie_space_registry (
        space_id         STRING  COMMENT 'Genie Space ID from URL',
        space_name       STRING  COMMENT 'Human-readable name',
        owner_email      STRING  COMMENT 'Named owner responsible for quality',
        status           STRING  COMMENT 'EXPLORATORY or CERTIFIED',
        tables           STRING  COMMENT 'Comma-separated table list',
        benchmark_score  INT     COMMENT 'Latest benchmark % score',
        golden_queries   INT     COMMENT 'Number of golden queries',
        certified_at     TIMESTAMP,
        last_reviewed    TIMESTAMP,
        notes            STRING
    )
    USING DELTA
    COMMENT 'Registry of all Genie Spaces — tracks exploratory vs certified status'
""")
print(f"✅ Registry table ready: {CATALOG}.{SCHEMA_GOV}.genie_space_registry")

# COMMAND ----------

# Upsert this space into the registry
if SPACE_ID:
    # Get latest benchmark score
    score = None
    n_queries = 0
    tables_list = ""

    try:
        bresp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/benchmark-runs",
                             headers=HEADERS)
        if bresp.status_code == 200:
            runs = bresp.json().get("benchmark_runs", [])
            if runs:
                results = runs[0].get("benchmark_results", [])
                good = sum(1 for r in results if r.get("rating") == "GOOD")
                total_r = len(results)
                score = round(good * 100 / total_r) if total_r else 0

        qresp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
                             headers=HEADERS)
        if qresp.status_code == 200:
            n_queries = len(qresp.json().get("sql_queries", []))

        sresp = requests.get(f"https://{HOST}/api/2.0/genie/spaces/{SPACE_ID}",
                             headers=HEADERS)
        if sresp.status_code == 200:
            datasets = sresp.json().get("datasets", [])
            tables_list = ", ".join(d.get("table_name", "") for d in datasets)
    except:
        pass

    # Determine status
    status = "CERTIFIED" if (score and score >= 80 and n_queries >= 5 and OWNER) else "EXPLORATORY"

    spark.sql(f"""
        MERGE INTO {CATALOG}.{SCHEMA_GOV}.genie_space_registry AS t
        USING (SELECT
            '{SPACE_ID}'       AS space_id,
            '{SPACE_NAME}'     AS space_name,
            '{OWNER}'          AS owner_email,
            '{status}'         AS status,
            '{tables_list}'    AS tables,
            {score or 'NULL'}  AS benchmark_score,
            {n_queries}        AS golden_queries,
            {'CURRENT_TIMESTAMP()' if status == 'CERTIFIED' else 'NULL'} AS certified_at,
            CURRENT_TIMESTAMP() AS last_reviewed,
            'Added from Lab 05 certification check' AS notes
        ) AS s ON t.space_id = s.space_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"✅ Space '{SPACE_NAME}' registered as: {status}")
    if status == "EXPLORATORY":
        print("   → Fix remaining checklist items to qualify for CERTIFIED status")
else:
    print("Enter Space ID in widget to register this space.")

display(spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA_GOV}.genie_space_registry ORDER BY last_reviewed DESC"))

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Governance — who can create spaces and when?
# MAGIC
# MAGIC **🖱️ Recommended permission model for AEMO:**
# MAGIC
# MAGIC | Role | Can create spaces? | Access Certified spaces | Access Exploratory spaces |
# MAGIC |---|---|---|---|
# MAGIC | Data Engineer | Yes (Exploratory + Certified) | CAN MANAGE | CAN MANAGE |
# MAGIC | Data Analyst | Yes (Exploratory only) | CAN RUN | CAN MANAGE |
# MAGIC | Business User | No | CAN RUN | No access |
# MAGIC | Line Manager | No | CAN RUN | No access |
# MAGIC
# MAGIC **What this means in practice:**
# MAGIC - Business users never see an Exploratory space — they only access spaces the data team has certified
# MAGIC - Data analysts can experiment freely in Exploratory spaces; they must involve a data engineer to promote to Certified
# MAGIC - The registry table (`genie_space_registry`) is the source of truth for what's Certified

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Certification promotion workflow
# MAGIC
# MAGIC When a space is ready to move from Exploratory → Certified:

# COMMAND ----------

def promote_to_certified(space_id, space_name, owner_email, notes=""):
    """
    Promote a space to CERTIFIED in the registry.
    Run this after all checklist items pass.
    """
    spark.sql(f"""
        UPDATE {CATALOG}.{SCHEMA_GOV}.genie_space_registry
        SET
            status       = 'CERTIFIED',
            certified_at = CURRENT_TIMESTAMP(),
            last_reviewed = CURRENT_TIMESTAMP(),
            notes        = '{notes}'
        WHERE space_id = '{space_id}'
    """)
    print(f"✅ '{space_name}' promoted to CERTIFIED")
    print(f"   Owner: {owner_email}")
    print(f"   Next: share with business users (CAN RUN)")
    print(f"   Next: configure feedback alert if not done")
    print(f"   Next: add to DB1 / Databricks One entry point for business users")

# Uncomment to promote:
# promote_to_certified(SPACE_ID, SPACE_NAME, OWNER, notes="All checklist items passed - Lab 05")

print("Review the checklist above, then uncomment promote_to_certified() to certify.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 05 Checkpoint
# MAGIC - [ ] Certification checklist run — score noted
# MAGIC - [ ] Space registry table created
# MAGIC - [ ] This space registered (EXPLORATORY or CERTIFIED)
# MAGIC - [ ] Governance model understood — business users only access Certified spaces
# MAGIC - [ ] Promotion workflow understood
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🎯 Session 2 — All 5 Labs Complete
# MAGIC
# MAGIC | Lab | Topic | Time |
# MAGIC |---|---|---|
# MAGIC | 01 | Create space + UC metadata + Knowledge Store | 40 min |
# MAGIC | 02 | Benchmarks + golden queries + text instructions | 35 min |
# MAGIC | 03 | Run benchmarks + Monitor tab + rollout | 30 min |
# MAGIC | 04 | Monitoring + cost + feedback alert + dashboard | 25 min |
# MAGIC | 05 | Operating model — Exploratory vs Certified | 20 min |
# MAGIC | | **Total** | **~2.5 hours** |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Permissions — bulk grant access
# MAGIC
# MAGIC **🖱️ UI:** Share button (top right of Genie Space)
# MAGIC
# MAGIC **⚡ Automated** — grant CAN_RUN to a list of users or a group at once.
# MAGIC Replaces nothing — uses PATCH (additive).

# COMMAND ----------

import requests

# Edit these lists before running
USERS_CAN_RUN  = [
    # "analyst1@aemo.com.au",
    # "analyst2@aemo.com.au",
]
GROUPS_CAN_RUN = [
    # "market-operations-team",  # UC group name
]
EDITORS = [
    # "dataengineer@aemo.com.au",
]

def grant_space_permissions(space_id, users_run, groups_run, editors):
    if not space_id:
        print("Enter Space ID in widget first."); return

    acl = []
    for u in users_run:
        acl.append({"user_name": u, "permission_level": "CAN_RUN"})
    for g in groups_run:
        acl.append({"group_name": g, "permission_level": "CAN_RUN"})
    for e in editors:
        acl.append({"user_name": e, "permission_level": "CAN_EDIT"})

    if not acl:
        print("Add users/groups to the lists above, then re-run."); return

    resp = requests.patch(
        f"https://{HOST}/api/2.0/permissions/dashboards/{space_id}",
        headers=HEADERS,
        json={"access_control_list": acl}
    )
    if resp.status_code in (200, 204):
        print(f"✅ Granted access to {len(acl)} principals")
        for entry in acl:
            p = entry.get("user_name") or entry.get("group_name")
            print(f"   {entry['permission_level']}: {p}")
    else:
        print(f"❌ {resp.status_code}: {resp.text[:200]}")

grant_space_permissions(SPACE_ID, USERS_CAN_RUN, GROUPS_CAN_RUN, EDITORS)

# COMMAND ----------

# Verify current permissions
if SPACE_ID:
    resp = requests.get(
        f"https://{HOST}/api/2.0/permissions/dashboards/{SPACE_ID}",
        headers=HEADERS
    )
    if resp.status_code == 200:
        acl = resp.json().get("access_control_list", [])
        print(f"Current permissions ({len(acl)} entries):")
        for entry in acl:
            p = entry.get("user_name") or entry.get("group_name") or "unknown"
            print(f"  {entry.get('permission_level'):12s} {p}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6: UC permissions — what the space inherits
# MAGIC
# MAGIC > *"Every Genie query runs in the exact permission and security context as if the user manually ran SQL."*
# MAGIC > *(Slide 18 — End-to-End Security Model)*
# MAGIC
# MAGIC Genie Space permissions control who can **open the space**.
# MAGIC UC permissions control what **data they can see inside it**.
# MAGIC Both must be configured.

# COMMAND ----------

# Check what UC permissions are set on the AEMO schema
uc_grants = spark.sql(f"SHOW GRANTS ON SCHEMA {CATALOG}.aemo")
print(f"Current grants on {CATALOG}.aemo:")
display(uc_grants)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Grant UC access to groups
# MAGIC
# MAGIC **⚡ Automated** — edit the group name, then run.

# COMMAND ----------

# Grant read access on AEMO schema to a UC group
# Edit GROUP_NAME before running

GROUP_NAME = "workshop_participants"  # change to your UC group

grants_to_apply = [
    f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{GROUP_NAME}`",
    f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.aemo TO `{GROUP_NAME}`",
    f"GRANT SELECT ON SCHEMA {CATALOG}.aemo TO `{GROUP_NAME}`",
]

print(f"Grants to apply for group '{GROUP_NAME}':\n")
for stmt in grants_to_apply:
    print(f"  {stmt}")

print("\nUncomment and run to apply:")
# for stmt in grants_to_apply:
#     spark.sql(stmt)
#     print(f"✅ {stmt[:80]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 7: Workspace AI feature settings — admin checklist
# MAGIC
# MAGIC **🖱️ UI:** Workspace Settings → AI features
# MAGIC
# MAGIC These must be ON for Genie to work:

# COMMAND ----------

import requests

WORKSPACE_URL = f"https://{HOST}"

settings_to_check = [
    ("aibi_genie_space_enabled_ws_setting",  "Genie Spaces"),
    ("notebook_ml_assistant_enabled_setting", "Notebook AI Assistant"),
]

print("Checking workspace AI feature settings:\n")
for setting_type, label in settings_to_check:
    try:
        resp = requests.get(
            f"{WORKSPACE_URL}/api/2.0/settings/types/{setting_type}/names/default",
            headers=HEADERS
        )
        if resp.status_code == 200:
            data = resp.json()
            # Navigate nested structure
            enabled = None
            for key, val in data.items():
                if isinstance(val, dict) and "enabled" in val:
                    enabled = val["enabled"]
                    break
            if enabled is True:
                print(f"  ✅ {label}: ENABLED")
            elif enabled is False:
                print(f"  ❌ {label}: DISABLED — enable in Workspace Settings → AI features")
            else:
                print(f"  ⚠️  {label}: status unknown (check UI)")
        else:
            print(f"  ⚠️  {label}: could not verify ({resp.status_code})")
    except Exception as e:
        print(f"  ⚠️  {label}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 8: Geography enforcement — data residency check
# MAGIC
# MAGIC The single most important compliance setting for AEMO.
# MAGIC
# MAGIC **🖱️ UI:** accounts.cloud.databricks.com → Workspaces → [workspace] → Security and compliance
# MAGIC → "Enforce data processing within workspace Geography for Designated Services" must be **ON**

# COMMAND ----------

# Check geography enforcement via API
try:
    resp = requests.get(
        f"{WORKSPACE_URL}/api/2.0/settings/types/enforce_workspace_feature_on_network_setting/names/default",
        headers=HEADERS
    )
    if resp.status_code == 200:
        data = resp.json()
        print("Geography enforcement setting:")
        print(json.dumps(data, indent=2)[:400])
    else:
        print(f"Could not read setting via API (status {resp.status_code})")
        print("→ Verify manually: Account Console → Workspaces → [workspace] → Security and compliance")
        print("→ Toggle: 'Enforce data processing within workspace Geography' must be ON")
except Exception as e:
    print(f"Note: {e}")
    print("→ Check manually in Account Console → Workspaces → Security and compliance tab")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## ✅ Lab 05 Full Checklist
# MAGIC
# MAGIC **Space quality:**
# MAGIC - [ ] Certification checklist run — all items passing
# MAGIC - [ ] Space registered in genie_space_registry table
# MAGIC - [ ] Status set to CERTIFIED (or action items noted for Exploratory)
# MAGIC
# MAGIC **Permissions:**
# MAGIC - [ ] Space-level permissions set (CAN RUN for business users)
# MAGIC - [ ] UC permissions set (USE SCHEMA + SELECT on aemo schema)
# MAGIC - [ ] Named owner has CAN MANAGE
# MAGIC
# MAGIC **Admin:**
# MAGIC - [ ] Genie Spaces feature enabled in Workspace Settings
# MAGIC - [ ] Geography enforcement ON in Account Console
# MAGIC - [ ] Feedback alert configured (Lab 04)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🎯 Session 2 — All 5 Labs Complete
# MAGIC
# MAGIC | Lab | Topic | Time |
# MAGIC |---|---|---|
# MAGIC | 01 | Create space + UC metadata + Knowledge Store | 40 min |
# MAGIC | 02 | Benchmarks + golden queries + text instructions | 35 min |
# MAGIC | 03 | Run benchmarks + Monitor tab + rollout | 30 min |
# MAGIC | 04 | Monitoring + cost + feedback alert + dashboard | 25 min |
# MAGIC | 05 | Operating model + permissions + admin settings | 20 min |
# MAGIC | | **Total** | **~2.5 hours** |
