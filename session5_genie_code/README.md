# Session 5: Extending Genie Code

**Duration:** 60 minutes  
**Format:** 3 hands-on labs, in-order  
**Based on:** Sourabh Ghosh's [genie_for_energy](https://github.com/sourabhghose/genie_for_energy) Module 5 (05-extending.md sections 5A + 5B), adapted for AEMO  
**Target audience:** AEMO data engineers, analysts, and platform owners

---

## Session Overview

Genie Code out of the box has no awareness of NEM terminology, AEMO regulatory obligations, or your specific workshop tables. This session covers the three ways to extend Genie Code so it behaves like a domain expert from the first message.

| Lab | Topic | Duration | What you install |
|-----|-------|----------|-----------------|
| Lab 01 | Custom Instructions | 20 min | Personal instructions file at `/Users/{email}/.assistant_instructions.md` |
| Lab 02 | Skills Walkthrough | 30 min | Three SKILL.md files: `energy-analytics`, `regulatory-compliance`, `genie-space-creator` |
| Lab 03 | MCP Introduction | 10 min | Conceptual intro + `DatabricksMCPClient` tool discovery demo |

---

## Lab 01 — Custom Instructions (20 min)

**File:** `labs/01_custom_instructions.py`

Custom instructions are plain text loaded into every Genie Code conversation as the system prompt. They apply before you type anything.

This lab creates AEMO-specific personal instructions covering:
- NEM region codes (`NSW1`, `VIC1`, `QLD1`, `SA1`, `TAS1`)
- NMI format, DUID, RRP, LOR, SAIDI, SAIFI definitions
- Number formatting: `$/MWh` to 2dp, energy in `MWh`
- Date convention: `DD/MM/YYYY` for AER-formatted output
- Default catalog: `workshop_au`
- Regulatory context: SOCI Act 2018, Privacy Act 1988, NER, AER

You also see the workspace-level pattern (`Workspace/.assistant_workspace_instructions.md`) that a workspace admin would set once for all users.

**Test:** Genie Code correctly uses `VIC1`, `workshop_au.aemo.spot_prices`, and `DD/MM/YYYY` without being told — from the first message of a new conversation.

---

## Lab 02 — Skills Walkthrough (30 min)

**File:** `labs/02_skills_walkthrough.py`

Skills are `SKILL.md` files with YAML front-matter that Genie Code loads on demand — either when a query matches the `description:` field, or when you type `@skill-name` explicitly.

Three skills are created in `/Users/{email}/.assistant/skills/`:

### `energy-analytics`
SAIDI/SAIFI/CAIDI formulas, NEM spot price reference table (cap $15,300/MWh, floor -$1,000/MWh), 5-minute dispatch vs 30-minute settlement explained, and three ready-to-run SQL patterns for `workshop_au.aemo`.

Auto-loads on: SAIDI, SAIFI, spot price, RRP, dispatch, LOR, NEM analysis.

### `regulatory-compliance`
SOCI Act 2018 incident reporting obligations (12h critical / 72h significant), Privacy Act APP 6 and APP 11 for NMI data, NER Chapter 7 retention (7 years), STPIS performance benchmarks by network zone, and Major Event Day exclusion rules.

Auto-loads on: SOCI Act, compliance, AER, Privacy Act, STPIS, NER obligations.

### `genie-space-creator`
Full REST API walkthrough to create a Genie Space (create → add tables → add golden queries → set permissions). Includes five ready-to-use golden query templates for NEM data and the MCP endpoint URL pattern for connecting agents to the space.

Auto-loads on: create Genie Space, golden queries, NL-to-SQL, Genie API.

---

## Lab 03 — MCP Introduction (10 min)

**File:** `labs/03_mcp_intro.py`

Conceptual introduction to the Model Context Protocol and a single tool-discovery demo.

**Concept:** MCP is the open standard that connects AI agents to data sources using one consistent interface — the USB-C of AI tooling. Any MCP-compatible agent can reach your AEMO data without custom integration code per framework.

**Three in-region Databricks MCP servers:**

| Server | URL pattern | What it exposes |
|--------|-------------|-----------------|
| UC Functions | `/api/2.0/mcp/functions/{catalog}/{schema}` | All UC functions in a schema as callable tools |
| Genie Space | `/api/2.0/mcp/genie/{space_id}` | NL-to-SQL over a specific Genie Space |
| Vector Search | `/api/2.0/mcp/vector-search/{catalog}/{schema}/{index}` | Semantic search over a VS index |

All three endpoints run on Azure Australia East — no data leaves the region.

**Demo:** `DatabricksMCPClient.list_tools()` lists the same tools an agent sees during its planning phase. This makes the link between UC function `COMMENT` fields and agent tool selection concrete.

**Pointer:** For full hands-on agent building with all three MCP servers, see Session 4.

---

## Prerequisites

- Access to the workshop Databricks workspace (Azure Australia East)
- Unity Catalog enabled, access to `workshop_au` catalog
- Genie Code is on by default — no additional enablement needed
- Session 2 complete (Genie Spaces familiarity helpful but not required for Labs 01–02)
- Python packages: `databricks-sdk`, `databricks-mcp` (installed in Lab 03 setup cell)

---

## Skills Installed After This Session

```
/Users/{email}/.assistant_instructions.md           ← loads every session
/Users/{email}/.assistant/skills/
  energy-analytics/SKILL.md                         ← SAIDI/SAIFI, spot price, SQL patterns
  regulatory-compliance/SKILL.md                    ← SOCI Act, Privacy Act, STPIS
  genie-space-creator/SKILL.md                      ← REST API, golden queries, MCP endpoint
```

---

## Facilitator Notes

- Total runtime: 60 minutes with no buffer — run setup cells in Lab 03 before participants arrive
- Lab 01 has no pip installs; Labs 02 and 03 are also lightweight (dbutils + databricks-mcp)
- The `dbutils.fs.put` calls in Labs 01 and 02 write to workspace DBFS — they run in under 1 second
- If `DatabricksMCPClient.list_tools()` returns an empty list in Lab 03, this is expected when the `workshop_au.aemo` schema has no UC functions; direct participants to use `workshop_au.workshop_lab` instead
- Session 4 (MCP Agents) is the natural follow-on for anyone who wants to build a full agent with these tools
