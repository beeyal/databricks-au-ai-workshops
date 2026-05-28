# Session 2: Building Your Genie Space

**Audience:** AEMO data engineers and market analysts
**Duration:** 1.5 hours (three 25-minute labs + 15 minutes buffer for discussion)
**Level:** Intermediate — assumes familiarity with SQL and Databricks notebooks

---

## Session overview

Participants build a production-grade AI/BI Genie Space connected to AEMO NEM operational data. By the end of the session, the Space is live, configured with domain-specific instructions and golden queries, governance-reviewed, and ready for pilot rollout to business users.

The session covers the full lifecycle: create, configure, use, govern.

---

## Labs

| Lab | File | Duration | Focus |
|-----|------|----------|-------|
| 01 | `labs/01_genie_space_setup.py` | 25 min | Create the Space, add trusted tables, load golden queries, set permissions |
| 02 | `labs/02_user_workflows.py` | 25 min | Seven progressively complex NEM questions, follow-up conversations, add to dashboard |
| 03 | `labs/03_governance_access.py` | 25 min | Usage monitoring, audit trail, billing visibility, access management, production checklist |

### Lab 01 — Setting Up an Effective Genie Space

Creates the Genie Space via REST API, registers five AEMO tables as trusted assets, populates the Knowledge Store with ten golden queries covering NEM operations, writes domain-specific Space instructions (NEM terminology, region codes, aggregation preferences), and sets `CAN_VIEW` for analysts and `CAN_EDIT` for data engineers. Ends with a two-question API checkpoint.

**Key outcomes:** Reproducible Space creation via code; participants understand why instructions and golden queries matter for answer quality.

### Lab 02 — Core User Workflows

Participants work in the Genie Space UI asking seven questions in increasing complexity: single-region spot price lookup, five-region comparison, price spike investigation, LOR notice retrieval, multi-month coal vs renewable trend (with Agent mode), follow-up conversation to drill into spike events, and adding a result to an AI/BI dashboard. Each task includes a validation SQL cell to cross-check Genie's answer against raw data.

**Key outcomes:** Participants experience the analyst workflow end-to-end; they learn to verify Genie answers using Show SQL; they create their first dashboard from a Genie result.

### Lab 03 — Controls, Governance and Access

Covers the operational and compliance aspects required before rolling out Genie to business users. Queries `system.query.history` and `system.ai_gateway.usage` for usage monitoring, `system.access.audit` for the security audit trail, `system.billing.usage` for DBU attribution. Demonstrates programmatic access management via the SDK. Explains precisely what the language model receives (schema metadata) versus what stays in Australia East (row data). Closes with an eight-point automated production readiness checklist.

**Key outcomes:** Data governance staff can answer "what data does Genie send to the model?"; engineers can monitor and manage the Space programmatically; team has a production checklist before go-live.

---

## Prerequisites

1. **Session 1 complete** — participants have run the onboarding notebooks and are authenticated to the workshop workspace
2. **AEMO tables loaded** — the following Unity Catalog tables must exist before Lab 01:

   | Table | Description |
   |-------|-------------|
   | `workshop_au.aemo.spot_prices` | 5-minute regional reference prices (RRP) for all NEM regions |
   | `workshop_au.aemo.dispatch_intervals` | Generator dispatch targets and actual output per dispatch interval |
   | `workshop_au.aemo.market_notices` | LOR, reserve notices, and operational alerts |
   | `workshop_au.aemo.generator_registration` | Static generator metadata: DUID, station, fuel type, installed capacity |
   | `workshop_au.aemo.settlement_amounts` | Preliminary and final trading amounts per participant |

3. **Permissions** — participants need `CREATE` privilege on `workshop_au.aemo` (to create Genie Spaces that reference these tables) and `USE CATALOG` on `workshop_au`
4. **Serverless SQL warehouse** — at least one Pro or Serverless SQL warehouse must be running in the workspace; Genie uses this to execute queries

---

## Setup instructions

Run the setup notebook before starting Lab 01:

```
genie_config/aemo_space_config.py
```

This notebook:
- Verifies the five AEMO tables exist and are populated
- Adds descriptive Unity Catalog column comments (improves Genie SQL generation quality)
- Confirms a serverless warehouse is available
- Prints the workspace URL for the facilitator to share with participants

---

## Facilitator notes

- The Space ID from Lab 01 is needed in Labs 02 and 03. It is stored in `spark.conf` within the same session. If participants run labs in separate sessions, they must paste the Space ID into the widget.
- Golden queries in Lab 01 are written in Delta Lake SQL dialect. If workshop tables use a different dialect, update date functions (`DATE_SUB`, `DATE_FORMAT`, `ADD_MONTHS`) to match.
- Lab 02 Task 5 uses Agent mode — confirm it is enabled on the workspace before the session (`Feature: AI Agent Mode` in workspace settings).
- The audit log queries in Lab 03 require `system.access.audit` to be enabled. Contact your workspace admin if the table is not accessible.
- Settlement data in the workshop is synthetic — remind participants that the governance discussion applies to real settlement data in production workspaces.

Full facilitator guide: `facilitator_notes/`
