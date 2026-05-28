# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 32px 40px; border-radius: 12px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', Arial, sans-serif; font-size: 2.2em; margin: 0 0 8px 0;">Lab 03: Controls, Governance &amp; Access</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0;">Session 2 · AEMO NEM Operations · 25 minutes</p>
# MAGIC </div>
# MAGIC <div style="background: #f7f8fa; border-left: 4px solid #FF3621; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 0;">
# MAGIC   <b>What you will learn:</b> How to monitor Genie Space usage, understand the audit trail, interpret billing, manage access programmatically, explain the data privacy model to stakeholders, and complete a production readiness checklist before rolling out to business users.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widget Configuration

# COMMAND ----------

dbutils.widgets.text("catalog",     "workshop_au",        "Catalog")
dbutils.widgets.text("schema_aemo", "aemo",               "Schema")
dbutils.widgets.text("space_id",    "",                   "Genie Space ID (from Lab 01)")
dbutils.widgets.text("lookback_days", "7",                "Lookback days for monitoring")

# COMMAND ----------

CATALOG       = dbutils.widgets.get("catalog")
SCHEMA        = dbutils.widgets.get("schema_aemo")
SPACE_ID      = dbutils.widgets.get("space_id")
LOOKBACK_DAYS = int(dbutils.widgets.get("lookback_days"))

if not SPACE_ID:
    try:
        SPACE_ID = spark.conf.get("workshop.genie.space_id")
        print(f"Retrieved Space ID from session config: {SPACE_ID}")
    except Exception:
        print("WARNING: Enter your Space ID in the 'space_id' widget above.")

from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

print(f"Catalog      : {CATALOG}")
print(f"Schema       : {SCHEMA}")
print(f"Space ID     : {SPACE_ID}")
print(f"Lookback days: {LOOKBACK_DAYS}")
print(f"Workspace    : {w.config.host}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — Monitoring Genie Usage
# MAGIC
# MAGIC Genie Spaces are backed by Databricks SQL (serverless warehouses).
# MAGIC Every question a user asks becomes one or more SQL queries on your warehouse.
# MAGIC You can monitor usage through two lenses:
# MAGIC
# MAGIC | System table | What it tracks |
# MAGIC |-------------|---------------|
# MAGIC | `system.query.history` | Every SQL query executed — includes Genie-generated queries tagged with source |
# MAGIC | `system.ai_gateway.usage` | AI API calls routed through AI Gateway — tokens, model, latency |
# MAGIC | `system.billing.usage` | DBU consumption including serverless SQL used by Genie |
# MAGIC
# MAGIC > **Note for workshop participants:** System tables may not be populated in workshop environments with limited query history. The SQL below is production-ready — use it on your production workspace to see real data.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1a — Query history for this Genie Space

# COMMAND ----------

# MAGIC %sql
# MAGIC -- All SQL queries executed by Genie in this Space over the lookback window
# MAGIC -- Genie-generated queries are tagged with statement_type = 'GENIE' or via the client_application field
# MAGIC SELECT
# MAGIC     statement_id,
# MAGIC     executed_by,
# MAGIC     start_time,
# MAGIC     ROUND(total_duration_ms / 1000.0, 2)  AS duration_seconds,
# MAGIC     rows_produced,
# MAGIC     status,
# MAGIC     LEFT(statement_text, 300)              AS sql_preview
# MAGIC FROM system.query.history
# MAGIC WHERE
# MAGIC     start_time >= DATE_SUB(CURRENT_TIMESTAMP(), ${lookback_days})
# MAGIC     AND (
# MAGIC         client_application LIKE '%genie%'
# MAGIC         OR client_application LIKE '%Genie%'
# MAGIC     )
# MAGIC ORDER BY start_time DESC
# MAGIC LIMIT 100

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b — Usage summary: questions per user

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Summarise how many Genie queries each user has run
# MAGIC SELECT
# MAGIC     executed_by                             AS user,
# MAGIC     COUNT(*)                                AS query_count,
# MAGIC     ROUND(AVG(total_duration_ms / 1000.0), 2) AS avg_duration_seconds,
# MAGIC     SUM(rows_produced)                      AS total_rows_returned,
# MAGIC     MIN(start_time)                         AS first_query,
# MAGIC     MAX(start_time)                         AS most_recent_query
# MAGIC FROM system.query.history
# MAGIC WHERE
# MAGIC     start_time >= DATE_SUB(CURRENT_TIMESTAMP(), ${lookback_days})
# MAGIC     AND (
# MAGIC         client_application LIKE '%genie%'
# MAGIC         OR client_application LIKE '%Genie%'
# MAGIC     )
# MAGIC GROUP BY executed_by
# MAGIC ORDER BY query_count DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c — AI Gateway usage (token consumption)
# MAGIC
# MAGIC Genie calls the foundation model via AI Gateway to interpret natural language questions.
# MAGIC Token usage here is what AEMO would be charged for the language model component.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- AI Gateway usage for Genie (model calls, token counts)
# MAGIC -- Available when AI Gateway logging is enabled on the workspace
# MAGIC SELECT
# MAGIC     timestamp,
# MAGIC     endpoint_name,
# MAGIC     request_id,
# MAGIC     databricks_user_email                   AS user,
# MAGIC     usage_context.num_input_tokens          AS input_tokens,
# MAGIC     usage_context.num_output_tokens         AS output_tokens,
# MAGIC     ROUND(response_time_ms / 1000.0, 2)     AS response_seconds,
# MAGIC     status_code
# MAGIC FROM system.ai_gateway.usage
# MAGIC WHERE
# MAGIC     timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), ${lookback_days})
# MAGIC     AND endpoint_name LIKE '%genie%'
# MAGIC ORDER BY timestamp DESC
# MAGIC LIMIT 200

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Audit Trail: Who Accessed the Genie Space
# MAGIC
# MAGIC The Unity Catalog audit log (`system.access.audit`) records every access event:
# MAGIC who opened the Space, who asked a question, and who changed the configuration.
# MAGIC
# MAGIC This is the log you would query for:
# MAGIC - Security incident investigation ("who accessed NEM data on date X?")
# MAGIC - Compliance reporting ("who has viewed settlement amounts this month?")
# MAGIC - Adoption tracking ("is the team actually using the Space we built?")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Audit log for Genie Space access events
# MAGIC SELECT
# MAGIC     event_time,
# MAGIC     user_identity.email              AS user_email,
# MAGIC     action_name,
# MAGIC     request_params.space_id          AS space_id,
# MAGIC     request_params.conversation_id   AS conversation_id,
# MAGIC     response.statusCode              AS status
# MAGIC FROM system.access.audit
# MAGIC WHERE
# MAGIC     event_time >= DATE_SUB(CURRENT_TIMESTAMP(), ${lookback_days})
# MAGIC     AND service_name = 'genieService'
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 200

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Configuration changes to Genie Spaces (who updated instructions, added tables, etc.)
# MAGIC SELECT
# MAGIC     event_time,
# MAGIC     user_identity.email              AS changed_by,
# MAGIC     action_name,
# MAGIC     request_params.space_id          AS space_id,
# MAGIC     request_params                   AS change_details
# MAGIC FROM system.access.audit
# MAGIC WHERE
# MAGIC     event_time >= DATE_SUB(CURRENT_TIMESTAMP(), ${lookback_days})
# MAGIC     AND service_name = 'genieService'
# MAGIC     AND action_name IN (
# MAGIC         'updateGenieSpace', 'createGenieSpace', 'deleteGenieSpace',
# MAGIC         'addGenieDataset', 'removeGenieDataset',
# MAGIC         'createGenieQuery', 'updateGenieQuery', 'deleteGenieQuery',
# MAGIC         'updateGenieSpacePermissions'
# MAGIC     )
# MAGIC ORDER BY event_time DESC

# COMMAND ----------

# MAGIC %md
# MAGIC > **Key audit events to monitor:**
# MAGIC >
# MAGIC > | Action | What it means |
# MAGIC > |--------|--------------|
# MAGIC > | `startConversation` | User opened a new chat with Genie |
# MAGIC > | `createConversationMessage` | User asked a question |
# MAGIC > | `updateGenieSpace` | Instructions or settings were changed |
# MAGIC > | `addGenieDataset` | A new table was added as a trusted asset |
# MAGIC > | `updateGenieSpacePermissions` | Access was granted or revoked |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Billing Visibility: What Does Genie Cost?
# MAGIC
# MAGIC Genie Spaces consume two types of resources:
# MAGIC
# MAGIC | Resource | What drives it | How it appears in billing |
# MAGIC |----------|---------------|--------------------------|
# MAGIC | **Serverless SQL DBUs** | Running the SQL queries Genie generates | `system.billing.usage` — SKU contains "SQL Serverless" |
# MAGIC | **Foundation model tokens** | The language model call to interpret the question | Included in Databricks platform; counted in `system.ai_gateway.usage` |
# MAGIC
# MAGIC **Rule of thumb for AEMO:** A typical Genie question that runs a 5-second query on a small result set costs roughly 0.01–0.05 serverless SQL DBUs. At workshop scale (20 participants, 50 questions each) this is negligible.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Serverless SQL DBU consumption attributable to Genie
# MAGIC -- Genie uses serverless SQL warehouses; the usage_metadata.job_id is null for interactive
# MAGIC SELECT
# MAGIC     usage_date,
# MAGIC     sku_name,
# MAGIC     ROUND(SUM(usage_quantity), 4)  AS total_dbus,
# MAGIC     COUNT(*)                        AS billing_records
# MAGIC FROM system.billing.usage
# MAGIC WHERE
# MAGIC     usage_date >= DATE_SUB(CURRENT_DATE(), ${lookback_days})
# MAGIC     AND sku_name LIKE '%SQL Serverless%'
# MAGIC GROUP BY usage_date, sku_name
# MAGIC ORDER BY usage_date DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Breakdown of serverless SQL DBUs by workload type
# MAGIC -- usage_metadata.endpoint_id corresponds to the SQL warehouse Genie is using
# MAGIC SELECT
# MAGIC     usage_date,
# MAGIC     usage_metadata.endpoint_id              AS warehouse_id,
# MAGIC     billing_origin_product,
# MAGIC     ROUND(SUM(usage_quantity), 4)            AS total_dbus
# MAGIC FROM system.billing.usage
# MAGIC WHERE
# MAGIC     usage_date >= DATE_SUB(CURRENT_DATE(), ${lookback_days})
# MAGIC     AND sku_name LIKE '%SQL Serverless%'
# MAGIC     AND billing_origin_product = 'GENIE'
# MAGIC GROUP BY usage_date, usage_metadata.endpoint_id, billing_origin_product
# MAGIC ORDER BY usage_date DESC, total_dbus DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Access Management via SDK
# MAGIC
# MAGIC Lab 01 set permissions via REST API. Here we show how to:
# MAGIC - Read current permissions on the Space
# MAGIC - Add a new user or group
# MAGIC - Remove a user's access
# MAGIC - These are the same operations you would use in an automated onboarding workflow

# COMMAND ----------

# Read current permissions on the Space
print(f"Current permissions on Space {SPACE_ID}:\n")

try:
    perms = w.api_client.do(
        "GET",
        f"/api/2.0/permissions/dashboards/{SPACE_ID}",
    )

    # Display in a clean table
    acl = perms.get("access_control_list", [])
    if acl:
        print(f"{'Principal':<35} {'Type':<10} {'Permission'}")
        print("-" * 65)
        for entry in acl:
            if "group_name" in entry:
                principal = entry["group_name"]
                ptype = "group"
            elif "user_name" in entry:
                principal = entry["user_name"]
                ptype = "user"
            elif "service_principal_name" in entry:
                principal = entry["service_principal_name"]
                ptype = "sp"
            else:
                principal = str(entry)
                ptype = "unknown"

            for perm in entry.get("all_permissions", []):
                print(f"{principal:<35} {ptype:<10} {perm.get('permission_level', 'N/A')}")
    else:
        print("No access control entries found (you may be the owner by default).")

except Exception as e:
    print(f"Could not retrieve permissions: {e}")

# COMMAND ----------

# Add a specific user as CAN_VIEW (example — update with a real username in your workspace)
NEW_USER_EMAIL = "workshop.participant@aemo.com.au"  # Replace with a real email for production

print(f"Example: Adding {NEW_USER_EMAIL} as CAN_VIEW...\n")
print("(This cell is in DRY RUN mode — uncomment the API call to execute)\n")

ADD_PERMISSION_BODY = {
    "access_control_list": [
        {"user_name": NEW_USER_EMAIL, "permission_level": "CAN_VIEW"}
    ]
}

print("API call that would be made:")
print(f"  PATCH /api/2.0/permissions/dashboards/{SPACE_ID}")
print(f"  Body: {ADD_PERMISSION_BODY}")
print()
print("To execute, uncomment this block:")
print("""
# w.api_client.do(
#     "PATCH",
#     f"/api/2.0/permissions/dashboards/{SPACE_ID}",
#     body=ADD_PERMISSION_BODY,
# )
# print(f"Access granted to {NEW_USER_EMAIL}")
""")

# COMMAND ----------

# Remove a user's access (revoke by setting to empty permissions)
REMOVE_USER_EMAIL = "workshop.participant@aemo.com.au"  # Replace with real email

print(f"Example: Removing access for {REMOVE_USER_EMAIL}...\n")
print("(This cell is in DRY RUN mode — uncomment to execute)\n")

print("To revoke access, update the full ACL without that user, or use:")
print("""
# Revoke by setting the user's permissions to an empty list
# w.api_client.do(
#     "PATCH",
#     f"/api/2.0/permissions/dashboards/{SPACE_ID}",
#     body={
#         "access_control_list": [
#             {"user_name": REMOVE_USER_EMAIL, "permission_level": "NO_PERMISSIONS"}
#         ]
#     }
# )
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Bulk access management pattern (production)
# MAGIC
# MAGIC For AEMO's production rollout, you would integrate this with your HR/IdP system:
# MAGIC
# MAGIC ```python
# MAGIC # Pseudocode — sync Genie permissions from an approved-users list
# MAGIC approved_analysts = get_approved_users_from_hr_system()  # Your IdP API
# MAGIC
# MAGIC current_perms = get_space_permissions(space_id)
# MAGIC current_users = {u["user_name"] for u in current_perms if "user_name" in u}
# MAGIC
# MAGIC # Grant access to new approvals
# MAGIC for user in approved_analysts - current_users:
# MAGIC     grant_space_permission(space_id, user, "CAN_VIEW")
# MAGIC
# MAGIC # Revoke access for removed users
# MAGIC for user in current_users - approved_analysts:
# MAGIC     revoke_space_permission(space_id, user)
# MAGIC ```
# MAGIC
# MAGIC This pattern runs as a scheduled Databricks Job daily — ensuring Genie access always mirrors your HR-managed role list.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 5 — Responsible Usage: What Genie Sends to the Model
# MAGIC
# MAGIC This is the most important section for AEMO's data governance team.
# MAGIC Understanding the data flow is critical before sharing Genie with staff who handle market-sensitive or operationally critical data.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #e8f4fd; border: 2px solid #1B3A6B; border-radius: 8px; padding: 20px 24px; font-family: 'DM Sans', Arial, sans-serif;">
# MAGIC
# MAGIC <h3 style="color: #1B3A6B; margin-top: 0;">What Genie sends to the language model</h3>
# MAGIC
# MAGIC <table style="width: 100%; border-collapse: collapse;">
# MAGIC <thead>
# MAGIC <tr style="background: #1B3A6B; color: white;">
# MAGIC <th style="padding: 10px 14px; text-align: left;">What is sent</th>
# MAGIC <th style="padding: 10px 14px; text-align: left;">Example</th>
# MAGIC </tr>
# MAGIC </thead>
# MAGIC <tbody>
# MAGIC <tr style="background: #f0f7ff;">
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Your question text</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">"What was the average spot price in VIC1 yesterday?"</td>
# MAGIC </tr>
# MAGIC <tr>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Table names</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">workshop_au.aemo.spot_prices</td>
# MAGIC </tr>
# MAGIC <tr style="background: #f0f7ff;">
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Column names and data types</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">settlement_date TIMESTAMP, region_id STRING, rrp DOUBLE</td>
# MAGIC </tr>
# MAGIC <tr>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Column comments (from Unity Catalog)</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">"Regional Reference Price in $/MWh for this dispatch interval"</td>
# MAGIC </tr>
# MAGIC <tr style="background: #f0f7ff;">
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Space instructions you wrote</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">The NEM context text from Lab 01</td>
# MAGIC </tr>
# MAGIC <tr>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Golden queries from Knowledge Store</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">The 10 SQL examples we added in Lab 01</td>
# MAGIC </tr>
# MAGIC </tbody>
# MAGIC </table>
# MAGIC
# MAGIC <h3 style="color: #d32f2f; margin-top: 20px;">What Genie does NOT send to the model</h3>
# MAGIC
# MAGIC <table style="width: 100%; border-collapse: collapse;">
# MAGIC <thead>
# MAGIC <tr style="background: #d32f2f; color: white;">
# MAGIC <th style="padding: 10px 14px; text-align: left;">What is NOT sent</th>
# MAGIC <th style="padding: 10px 14px; text-align: left;">Why this matters for AEMO</th>
# MAGIC </tr>
# MAGIC </thead>
# MAGIC <tbody>
# MAGIC <tr style="background: #fff5f5;">
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;"><b>Actual row data from your tables</b></td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Settlement amounts, individual generator outputs, and NMI-level data stay in Australia East</td>
# MAGIC </tr>
# MAGIC <tr>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Query result data</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">The numbers Genie returns to the user are not sent back to the model for training</td>
# MAGIC </tr>
# MAGIC <tr style="background: #fff5f5;">
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Previous conversation history (in standard mode)</td>
# MAGIC <td style="padding: 10px 14px; border-bottom: 1px solid #ddd;">Each conversation turn is scoped; prior answers are not re-sent unless in Agent mode</td>
# MAGIC </tr>
# MAGIC </tbody>
# MAGIC </table>
# MAGIC
# MAGIC <p style="margin-top: 16px; color: #1B3A6B;"><b>The SQL runs on your Databricks serverless SQL warehouse in Australia East — only the final result set is shown to the user in the browser. No row-level data leaves your Databricks environment.</b></p>
# MAGIC
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Data flow diagram
# MAGIC
# MAGIC ```
# MAGIC USER (browser)
# MAGIC     │
# MAGIC     │  "What was the average spot price in VIC1 yesterday?"
# MAGIC     ▼
# MAGIC GENIE SERVICE (Databricks control plane, AU region)
# MAGIC     │
# MAGIC     │  Sends to LLM:
# MAGIC     │  - Question text
# MAGIC     │  - Table schema (column names + types + comments)
# MAGIC     │  - Space instructions
# MAGIC     │  - Relevant golden queries
# MAGIC     ▼
# MAGIC FOUNDATION MODEL (Databricks-hosted, AU region)
# MAGIC     │
# MAGIC     │  Returns: SQL query text
# MAGIC     │  SELECT ROUND(AVG(rrp), 2) AS avg_price ...
# MAGIC     ▼
# MAGIC GENIE SERVICE
# MAGIC     │
# MAGIC     │  Executes SQL on:
# MAGIC     ▼
# MAGIC SERVERLESS SQL WAREHOUSE (AU East data plane)
# MAGIC     │  ← workshop_au.aemo.spot_prices (actual row data stays here)
# MAGIC     │
# MAGIC     │  Returns: result set (1 row: VIC1, $87.42/MWh)
# MAGIC     ▼
# MAGIC USER (browser) ← sees result table and optional visualisation
# MAGIC ```

# COMMAND ----------

# Verify column comments are set on the tables
# Good column comments improve Genie's SQL generation quality
print("Checking Unity Catalog column comments on spot_prices...\n")

cols = spark.sql(f"DESCRIBE TABLE {CATALOG}.{SCHEMA}.spot_prices").collect()
print(f"{'Column':<25} {'Type':<15} {'Comment'}")
print("-" * 80)
for row in cols:
    col_name = row["col_name"]
    data_type = row["data_type"]
    comment   = row["comment"] if row["comment"] else "(no comment — consider adding one)"
    if not col_name.startswith("#"):
        print(f"{col_name:<25} {data_type:<15} {comment}")

# COMMAND ----------

# MAGIC %md
# MAGIC > **Tip for AEMO data engineers:** Adding descriptive comments to table columns in Unity Catalog directly improves Genie answer quality. The model uses comments to understand what each column means without needing to infer from the name alone.
# MAGIC >
# MAGIC > ```sql
# MAGIC > ALTER TABLE workshop_au.aemo.spot_prices
# MAGIC > ALTER COLUMN rrp COMMENT 'Regional Reference Price in $/MWh. The spot price for this 30-minute trading interval in this NEM region.';
# MAGIC >
# MAGIC > ALTER TABLE workshop_au.aemo.spot_prices
# MAGIC > ALTER COLUMN region_id COMMENT 'NEM region code: NSW1, VIC1, QLD1, SA1, or TAS1';
# MAGIC > ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 6 — Production Readiness Checklist
# MAGIC
# MAGIC Before opening the Genie Space to AEMO business users, work through this checklist.
# MAGIC Run the validation cells under each item.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #f7f8fa; border: 1px solid #ddd; border-radius: 8px; padding: 20px 24px;">
# MAGIC <h3 style="margin-top: 0;">Production Readiness: 8 Checks Before Going Live</h3>
# MAGIC
# MAGIC | # | Check | Why it matters |
# MAGIC |---|-------|---------------|
# MAGIC | 1 | All tables have column-level comments in Unity Catalog | Improves SQL generation accuracy |
# MAGIC | 2 | Space instructions include domain terminology and region codes | Prevents wrong column/table matches |
# MAGIC | 3 | At least 5 golden queries covering the top use cases | Anchors Genie to your preferred patterns |
# MAGIC | 4 | Permissions set — no "All workspace users" unless intentional | Prevents unintended access to settlement data |
# MAGIC | 5 | A serverless SQL warehouse is assigned and auto-stops after inactivity | Controls cost; no idle compute |
# MAGIC | 6 | Audit logging is enabled on the workspace | Required for compliance and incident investigation |
# MAGIC | 7 | Test questions return correct answers (verified against raw SQL) | Catch errors before users see them |
# MAGIC | 8 | Escalation path documented — what do users do when Genie gets it wrong? | Critical for data-sensitive users like market analysts |
# MAGIC
# MAGIC </div>

# COMMAND ----------

# Check 1: Verify column comments exist on critical tables
print("Check 1: Column comments on critical tables\n")

check_tables = ["spot_prices", "dispatch_intervals", "market_notices"]
issues = []

for table in check_tables:
    cols = spark.sql(f"DESCRIBE TABLE {CATALOG}.{SCHEMA}.{table}").collect()
    missing_comments = [
        row["col_name"] for row in cols
        if not row["comment"] and not row["col_name"].startswith("#")
    ]
    if missing_comments:
        issues.append(f"  {table}: columns without comments: {missing_comments}")
        print(f"  {table:<30} WARN — {len(missing_comments)} columns have no comment")
    else:
        print(f"  {table:<30} PASS ✓")

if issues:
    print("\nColumns needing comments:")
    for i in issues:
        print(i)

# COMMAND ----------

# Check 2: Verify Space instructions are non-empty
print("Check 2: Space instructions are configured\n")

try:
    space_details = w.api_client.do(
        "GET",
        f"/api/2.0/genie/spaces/{SPACE_ID}",
    )
    instructions = space_details.get("instructions", "")
    if len(instructions) > 100:
        print(f"  Instructions: PASS ✓ ({len(instructions)} characters)")
        # Check for key NEM terms
        nem_terms = ["NMI", "DUID", "LOR", "RRP", "NSW1", "VIC1", "QLD1", "SA1", "TAS1"]
        found = [t for t in nem_terms if t in instructions]
        missing = [t for t in nem_terms if t not in instructions]
        print(f"  NEM terms found   : {found}")
        if missing:
            print(f"  NEM terms missing : {missing}")
    else:
        print(f"  Instructions: WARN — too short ({len(instructions)} chars). Add domain context.")
except Exception as e:
    print(f"  Could not check instructions: {e}")

# COMMAND ----------

# Check 3: Verify golden queries exist
print("Check 3: Golden queries in Knowledge Store\n")

try:
    queries = w.api_client.do(
        "GET",
        f"/api/2.0/genie/spaces/{SPACE_ID}/sql-queries",
    )
    query_list = queries.get("sql_queries", [])
    count = len(query_list)
    if count >= 5:
        print(f"  Golden queries: PASS ✓ ({count} queries found)")
        for q in query_list:
            print(f"    - {q.get('name', 'Untitled')}")
    else:
        print(f"  Golden queries: WARN — only {count} found, recommend at least 5")
except Exception as e:
    print(f"  Could not check queries: {e}")

# COMMAND ----------

# Check 4: Verify permissions do not include unrestricted access
print("Check 4: Permission scope check\n")

try:
    perms = w.api_client.do(
        "GET",
        f"/api/2.0/permissions/dashboards/{SPACE_ID}",
    )
    acl = perms.get("access_control_list", [])
    broad_access = [
        e for e in acl
        if e.get("group_name") in ("account users", "All Users", "all users")
    ]
    if broad_access:
        print("  Permissions: WARN — Space is accessible to ALL workspace users.")
        print("  For settlement data, restrict to named groups only.")
    else:
        print(f"  Permissions: PASS ✓ — access is restricted to specific groups/users")
        for entry in acl:
            principal = entry.get("group_name") or entry.get("user_name") or "unknown"
            for perm in entry.get("all_permissions", []):
                print(f"    {principal}: {perm.get('permission_level')}")
except Exception as e:
    print(f"  Could not check permissions: {e}")

# COMMAND ----------

# Check 5: Verify a serverless warehouse is assigned
print("Check 5: Warehouse assignment\n")

try:
    space_details = w.api_client.do(
        "GET",
        f"/api/2.0/genie/spaces/{SPACE_ID}",
    )
    warehouse_id = space_details.get("warehouse_id", "")
    if warehouse_id:
        wh = w.api_client.do(
            "GET",
            f"/api/2.0/sql/warehouses/{warehouse_id}",
        )
        wh_name = wh.get("name", "unknown")
        wh_type = wh.get("warehouse_type", "unknown")
        auto_stop = wh.get("auto_stop_mins", "not set")
        print(f"  Warehouse: PASS ✓")
        print(f"    Name    : {wh_name}")
        print(f"    Type    : {wh_type}")
        print(f"    Auto-stop: {auto_stop} minutes")
        if wh_type != "PRO" and wh_type != "SERVERLESS":
            print("    WARN: Recommend using a Serverless or Pro warehouse for Genie")
    else:
        print("  Warehouse: WARN — no warehouse assigned. Genie will use default workspace warehouse.")
except Exception as e:
    print(f"  Could not check warehouse: {e}")

# COMMAND ----------

# Check 6: Audit logging (check that recent events appear in system.access.audit)
print("Check 6: Audit logging reachability\n")

try:
    result = spark.sql("""
        SELECT COUNT(*) AS recent_audit_events
        FROM system.access.audit
        WHERE event_time >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    """).collect()
    count = result[0]["recent_audit_events"]
    if count > 0:
        print(f"  Audit log: PASS ✓ ({count:,} events in the last 24 hours)")
    else:
        print("  Audit log: WARN — no events in the last 24 hours. Check audit log enablement.")
except Exception as e:
    print(f"  Audit log: WARN — system.access.audit not accessible: {e}")
    print("  Ensure the workspace admin has enabled audit log delivery.")

# COMMAND ----------

# Check 7: Run two quick test questions and verify responses
print("Check 7: End-to-end question verification\n")
import time

test_questions = [
    "How many dispatch intervals are in the spot prices table?",
    "What are the NEM region codes?",
]

for question in test_questions:
    try:
        conv = w.api_client.do(
            "POST",
            f"/api/2.0/genie/spaces/{SPACE_ID}/start-conversation",
            body={"content": question},
        )
        conv_id = conv["conversation_id"]
        msg_id  = conv["message_id"]

        for _ in range(20):
            time.sleep(3)
            msg = w.api_client.do(
                "GET",
                f"/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conv_id}/messages/{msg_id}",
            )
            if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
                break

        status = msg.get("status", "UNKNOWN")
        icon = "✓" if status == "COMPLETED" else "✗"
        print(f"  {icon} '{question}' → {status}")
    except Exception as e:
        print(f"  ✗ '{question}' → ERROR: {e}")

# COMMAND ----------

# Check 8: Summarise readiness
print("\n" + "="*60)
print("PRODUCTION READINESS SUMMARY")
print("="*60)
print("""
Checklist Item                              Status
─────────────────────────────────────────────────
1. Column comments                          Run Check 1 output above
2. Space instructions                       Run Check 2 output above
3. Golden queries (≥5)                      Run Check 3 output above
4. Permission scope                         Run Check 4 output above
5. Serverless warehouse assigned            Run Check 5 output above
6. Audit logging accessible                 Run Check 6 output above
7. Test questions pass                      Run Check 7 output above
8. Escalation path documented               MANUAL — add to your runbook

ESCALATION PATH TEMPLATE FOR AEMO:
  If Genie returns an incorrect answer:
  1. Click 'Show SQL' and verify the query
  2. Run the SQL directly in a notebook to confirm the raw result
  3. If the SQL is wrong, add a golden query that shows the correct pattern
  4. If the SQL is right but Genie's narrative is wrong, refine Space instructions
  5. Escalate to your Databricks SA if the issue persists across multiple questions

Contact: Workshop facilitator → Databricks Australia SA team
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Lab Summary
# MAGIC
# MAGIC | Section | What was covered |
# MAGIC |---------|-----------------|
# MAGIC | Monitoring | `system.query.history` for Genie SQL, `system.ai_gateway.usage` for token counts |
# MAGIC | Audit trail | `system.access.audit` for access events, configuration changes |
# MAGIC | Billing | Serverless SQL DBU attribution with `billing_origin_product = 'GENIE'` |
# MAGIC | Access management | Read, grant, and revoke permissions via SDK; bulk sync pattern |
# MAGIC | Data privacy | What goes to the model (schema) vs what stays in AU East (row data) |
# MAGIC | Production readiness | 8-point checklist with automated validation cells |
# MAGIC
# MAGIC ### Key governance principles for AEMO Genie deployment
# MAGIC
# MAGIC 1. **Schema is safe to share with the model** — column names and comments do not contain sensitive data
# MAGIC 2. **Row data never leaves your warehouse** — the model generates SQL; your warehouse executes it
# MAGIC 3. **All access is auditable** — every question, every permission change is in `system.access.audit`
# MAGIC 4. **Unity Catalog permissions apply** — if a user cannot query a table directly, Genie cannot query it for them either
# MAGIC 5. **Cost is proportional to usage** — Genie charges serverless SQL DBUs only when queries execute; idle Spaces cost nothing
# MAGIC
# MAGIC ### Session 2 complete
# MAGIC You have built, configured, tested, and governance-reviewed an AEMO NEM Operations Genie Space.
# MAGIC The Space is ready for pilot rollout to a small group of market analysts.

# COMMAND ----------

# Final cell — print Space URL for sharing
space_url = f"{w.config.host}#pages/genie/spaces/{SPACE_ID}"
print("Your AEMO NEM Operations Genie Space:")
print(f"  {space_url}")
print()
print("Share this URL with your pilot group of analysts.")
print("They need CAN_VIEW permission on the Space and access to the workshop_au catalog.")
displayHTML(
    f'<div style="background:#f7f8fa; border:1px solid #ddd; border-radius:8px; padding:16px 20px;">'
    f'<b>AEMO NEM Operations Genie Space</b><br>'
    f'<a href="{space_url}" target="_blank" style="color:#FF3621; font-size:1.1em;">{space_url}</a>'
    f'</div>'
)
