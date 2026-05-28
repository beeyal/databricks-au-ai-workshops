# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3139 0%, #243447 100%); padding: 28px 32px; border-radius: 10px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: #FF6B35; margin: 0 0 8px 0; font-size: 2em; font-family: 'DM Sans', sans-serif;">
# MAGIC     Lab 01: Custom Instructions for AEMO
# MAGIC   </h1>
# MAGIC   <p style="color: #AECBCC; margin: 0; font-size: 1em;">
# MAGIC     Session 5: Extending Genie Code — AEMO Workshop · Australia East
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Duration</strong><br>20 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Session 2 complete, Genie Code enabled
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All Genie Code inference: AU East
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC ### What you will do
# MAGIC
# MAGIC | Step | Action | Time |
# MAGIC |------|--------|------|
# MAGIC | 1 | Understand what custom instructions are and how they load | 5 min |
# MAGIC | 2 | Write AEMO-specific personal instructions | 8 min |
# MAGIC | 3 | See the workspace-level pattern (admin step, view only) | 3 min |
# MAGIC | 4 | Test: ask Genie Code about NMI format before and after | 4 min |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 1 — What Are Custom Instructions?
# MAGIC
# MAGIC Custom instructions are plain text that Genie Code loads into **every conversation as the system prompt**.
# MAGIC They apply before you type anything. There is no button to press — Genie reads them automatically each time you open the panel.
# MAGIC
# MAGIC Without them, Genie Code has no awareness that:
# MAGIC - `NMI` means National Metering Identifier, not "no message indicator"
# MAGIC - Region codes are `NSW1`, `VIC1`, `QLD1`, `SA1`, `TAS1` — not `NSW` or `Victoria`
# MAGIC - Prices should appear in `$/MWh` to 2 decimal places
# MAGIC - Dates should be `DD/MM/YYYY` for any AER-formatted output
# MAGIC
# MAGIC **Where do they live?**
# MAGIC
# MAGIC | Level | Path | Visible to | Who sets it |
# MAGIC |-------|------|-----------|-------------|
# MAGIC | Personal | `/Users/{your-email}/.assistant_instructions.md` | You only | You |
# MAGIC | Workspace | `Workspace/.assistant_workspace_instructions.md` | All users | Workspace admin only |
# MAGIC | Project | `AGENTS.md` in any directory | Notebooks in that directory tree | Any user |
# MAGIC
# MAGIC All three levels stack — Genie merges them in order: workspace → personal → AGENTS.md.
# MAGIC Total character budget: **20,000 characters** across all loaded files combined.
# MAGIC
# MAGIC **Rule of thumb for what to put in custom instructions:**
# MAGIC
# MAGIC | Put here | Because |
# MAGIC |----------|---------|
# MAGIC | Terminology unique to your domain (NMI, DUID, RRP) | Cheap to repeat every session — short |
# MAGIC | Date/number formatting rules | Universal across all your work |
# MAGIC | Default catalog + schema | Saves retyping the three-part name |
# MAGIC | Regulatory context summary (1–3 sentences) | Genie Code never guesses compliance context correctly without it |
# MAGIC
# MAGIC | Do NOT put here | Put it in a Skill instead |
# MAGIC |-----------------|--------------------------|
# MAGIC | Full table schemas with column names | Too large; schema changes burn tokens every session |
# MAGIC | Detailed formula walkthroughs (SAIDI, SAIFI) | Load on demand via a Skill document |
# MAGIC | Step-by-step processes | Skills load only when needed |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 2 — Create Your Personal AEMO Instructions
# MAGIC
# MAGIC Run the cell below. It writes a Markdown file to your personal user folder using `dbutils.fs.put`.
# MAGIC The path `/Users/{your-email}/.assistant_instructions.md` is where Genie Code looks automatically.
# MAGIC
# MAGIC You will see `True` printed when the write succeeds.

# COMMAND ----------

username = spark.sql("SELECT current_user()").collect()[0][0]
instructions_path = f"/Users/{username}/.assistant_instructions.md"

instructions_content = """# AEMO Operations Context

## Who I am and what I work on
I work at AEMO (Australian Energy Market Operator) and analyse NEM operational data on Databricks.
All code targets Azure Australia East. All Delta tables use Unity Catalog three-part names.
Default catalog: workshop_au

## Regulatory environment
AEMO operates the National Electricity Market (NEM) and gas markets.
Governing legislation: SOCI Act 2018 (critical infrastructure), Privacy Act 1988, National Electricity Rules (NER), AER.
For any output that will go into an AER report, follow the formatting conventions in this document.

## Data conventions — learn these before responding

| Term | Meaning |
|------|---------|
| NMI | National Metering Identifier — 10 characters, e.g. 6123456789 |
| DUID | Dispatchable Unit Identifier — unique generator ID in AEMO systems |
| RRP | Regional Reference Price — the NEM spot price in $/MWh |
| LOR | Lack of Reserve — LOR1 (watch), LOR2 (threatened), LOR3 (imminent) |
| SAIDI | System Average Interruption Duration Index — minutes per customer per year (lower is better) |
| SAIFI | System Average Interruption Frequency Index — interruptions per customer per year |
| CAIDI | Customer Average Interruption Duration Index — SAIDI / SAIFI (average duration per interruption) |

## Region codes — always use these exact values
NSW1, VIC1, QLD1, SA1, TAS1
Do NOT use: NSW, VIC, QLD, SA, TAS, New South Wales, etc.

## Number and date formatting
- Energy: MWh or kWh (not MW unless specifically discussing dispatch capacity)
- Prices: $/MWh to 2 decimal places (e.g. $87.43/MWh)
- Market price cap: $15,300/MWh | Floor: -$1,000/MWh
- Dates: DD/MM/YYYY format for any AER-formatted output (e.g. 01/07/2024)
- Timestamps: AEST or AEDT — always state the timezone

## Available tables (catalog: workshop_au)
- workshop_au.aemo.spot_prices — 30-min trading interval prices; column rrp = RRP in $/MWh
- workshop_au.aemo.dispatch_intervals — 5-min generator dispatch by DUID
- workshop_au.aemo.market_notices — LOR1/LOR2/LOR3 events and market interventions
- workshop_au.aemo.generator_registration — NEM generator details: fuel_type, registered_capacity_mw

## Coding conventions
- Always use catalog.schema.table three-part format: workshop_au.aemo.spot_prices
- Prefer Spark SQL or Delta table operations over pandas for large datasets
- Default Azure region for any service references: australiaeast
- Store outputs in workshop_au — do not create tables in system schemas
"""

result = dbutils.fs.put(instructions_path, instructions_content, overwrite=True)
print(f"Written to: {instructions_path}")
print(f"Result    : {result}")
print(f"\nLength    : {len(instructions_content):,} characters (budget: 20,000 total)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Verify the file was written

# COMMAND ----------

content = dbutils.fs.head(instructions_path)
print(content[:500])
print(f"\n--- full file: {len(content):,} characters ---")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — List your personal assistant folder
# MAGIC
# MAGIC This shows everything Genie Code can find in your personal folder:

# COMMAND ----------

user_folder = f"/Users/{username}"
files = dbutils.fs.ls(user_folder)
assistant_files = [f for f in files if ".assistant" in f.name or "instructions" in f.name]

if assistant_files:
    print("Assistant-related files in your user folder:")
    for f in assistant_files:
        print(f"  {f.path}  ({f.size:,} bytes)")
else:
    print("No assistant files yet — the instructions file you just created is the first one.")
    print(f"\nAll files in {user_folder}:")
    for f in files[:10]:
        print(f"  {f.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 3 — Workspace-Level Instructions (Admin Step — View Only)
# MAGIC
# MAGIC Workspace instructions apply to **every user** in the workspace. Only a workspace admin can write them.
# MAGIC This section shows you what the path looks like and what AEMO would put there — you do not need to run it.
# MAGIC
# MAGIC **Path:** `Workspace/.assistant_workspace_instructions.md`
# MAGIC (Note: `Workspace/` is the root of the workspace file tree, not a DBFS path — use the Files API or the UI to write it.)
# MAGIC
# MAGIC The snippet below shows the AEMO workspace-level content that a workspace admin would create once.
# MAGIC It establishes the base layer that all personal and project instructions build on top of.

# COMMAND ----------

# This cell is informational — do not run it unless you are a workspace admin.
# Workspace instructions path: Workspace/.assistant_workspace_instructions.md
# Written via: workspace Files API, or Repos/Files UI at the workspace root level.

workspace_instructions_preview = """# AEMO Databricks Workspace — Shared Context

## Workspace
This workspace belongs to AEMO (Australian Energy Market Operator).
All workloads run on Azure Australia East. Unity Catalog is enabled.
Primary catalog: workshop_au

## Data classification
Data in this workspace may include Critical Infrastructure data under the SOCI Act 2018.
Do not generate code that writes data outside this workspace without explicit approval.
Do not suggest using external APIs that would transmit market data.

## Table naming convention
Always qualify table names: catalog.schema.table (three-part format).
Do not use unqualified table names — they resolve to the session default schema only.

## Output format defaults
Dates: DD/MM/YYYY | Times: HH:MM AEST/AEDT | Energy: MWh | Prices: $/MWh (2 dp)
"""

print("--- Workspace instructions preview (admin sets this once) ---")
print(workspace_instructions_preview)
print("\nTo write this as admin:")
print("  1. Workspace UI → Files → navigate to root")
print("  2. Create file: .assistant_workspace_instructions.md")
print("  3. Paste the content above")
print("  4. Save — all users in the workspace will have this context automatically.")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Section 4 — Test: Before and After
# MAGIC
# MAGIC ### 4.1 — The test
# MAGIC
# MAGIC Open the Genie Code panel (sparkle icon, top-right) and start a **new conversation** (click the + or New Chat button).
# MAGIC Starting a new conversation forces Genie Code to reload your instructions file.
# MAGIC
# MAGIC Paste each prompt below — one at a time — and observe the difference.
# MAGIC
# MAGIC **Prompt A — terminology test:**
# MAGIC ```
# MAGIC Write a SQL query that returns the top 5 NMIs by total consumption last month
# MAGIC from the spot prices table.
# MAGIC ```
# MAGIC Expected with instructions loaded: Genie Code uses `workshop_au.aemo.spot_prices`,
# MAGIC expresses energy in MWh, formats the date filter in DD/MM/YYYY style, and does not ask
# MAGIC "what is NMI?".
# MAGIC
# MAGIC **Prompt B — region code test:**
# MAGIC ```
# MAGIC Show me the average spot price for Victoria over the last 7 days.
# MAGIC ```
# MAGIC Expected with instructions loaded: Genie Code filters on `region_id = 'VIC1'` (not `'VIC'` or `'Victoria'`).
# MAGIC
# MAGIC **Prompt C — regulatory context test:**
# MAGIC ```
# MAGIC I need to prepare a price report for the AER. What format should the date column use?
# MAGIC ```
# MAGIC Expected with instructions loaded: Genie Code answers `DD/MM/YYYY` immediately, citing
# MAGIC Australian convention, without you having to specify it.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 — What to observe
# MAGIC
# MAGIC | Behaviour | Without instructions | With instructions |
# MAGIC |-----------|---------------------|-------------------|
# MAGIC | Table reference | May use `spot_prices` or ask for the table name | Uses `workshop_au.aemo.spot_prices` |
# MAGIC | Victoria region filter | May write `WHERE region = 'VIC'` | Writes `WHERE region_id = 'VIC1'` |
# MAGIC | Date format in output | ISO 8601 default (`2024-07-01`) | DD/MM/YYYY (`01/07/2024`) for AER context |
# MAGIC | NMI explanation | May explain what NMI is | Treats it as known domain term |
# MAGIC
# MAGIC If you see the wrong behaviour, check that you started a **new conversation** after writing the file.
# MAGIC Genie Code reads the instructions file at conversation start — existing sessions are not updated.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 — Updating your instructions
# MAGIC
# MAGIC Instructions are just a Markdown file. Edit them any time:

# COMMAND ----------

# Add a new section to your existing instructions
additional_content = "\n\n## Team conventions\n- Prefer window functions over self-joins for time-series rolling calculations\n- Add a COMMENT block to every SQL query explaining the business intent\n- UC function COMMENT fields should include 'Use this when asked about...' for LLM discoverability\n"

existing = dbutils.fs.head(instructions_path)
updated  = existing + additional_content

dbutils.fs.put(instructions_path, updated, overwrite=True)
print(f"Instructions updated: {len(updated):,} characters total")
print(f"New section added: ## Team conventions")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #00843D 0%, #1B3A6B 100%); color: white; padding: 20px 24px; border-radius: 10px; margin-top: 24px;">
# MAGIC   <h2 style="color: white; margin: 0 0 10px 0; font-family: 'DM Sans', sans-serif;">Lab 01 Complete — 20 minutes</h2>
# MAGIC   <table style="color: white; width: 100%; border-collapse: collapse; font-size: 0.95em;">
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold; width: 40%;">Personal instructions</td>
# MAGIC       <td style="padding: 6px 10px;">Written to <code style="color:#FF6B35;">/Users/{username}/.assistant_instructions.md</code></td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">AEMO context loaded</td>
# MAGIC       <td style="padding: 6px 10px;">NMI format, region codes, $/MWh pricing, DD/MM/YYYY dates, table paths</td>
# MAGIC     </tr>
# MAGIC     <tr style="border-bottom: 1px solid rgba(255,255,255,0.2);">
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Workspace pattern seen</td>
# MAGIC       <td style="padding: 6px 10px;">Admin sets once at <code style="color:#FF6B35;">Workspace/.assistant_workspace_instructions.md</code></td>
# MAGIC     </tr>
# MAGIC     <tr>
# MAGIC       <td style="padding: 6px 10px; font-weight: bold;">Tested</td>
# MAGIC       <td style="padding: 6px 10px;">Genie Code uses VIC1, workshop_au.aemo.spot_prices, DD/MM/YYYY without prompting</td>
# MAGIC     </tr>
# MAGIC   </table>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 14px 0 0 0; font-weight: bold;">
# MAGIC     Next: Lab 02 — Skills Walkthrough (30 min)
# MAGIC   </p>
# MAGIC </div>
