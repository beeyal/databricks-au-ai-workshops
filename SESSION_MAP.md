# AEMO AI Enablement — Session Map

Each session is self-contained. Run setup → labs → cleanup.

---

## Session 1: Platform Admins

**Folder:** `session1_platform_admin/`
**Audience:** Workspace admins
**Duration:** 2 hours

**Slide decks:**
- Part 1 — AU East AI Feature Overview: https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit
- Part 2 — Governance & Controls: https://docs.google.com/presentation/d/18FVU2dVZYdS0ijOMk325LV3m-ktn-_lNb3Zsn2McEhk/edit

**Setup:** `setup/setup.py`
Creates the `workshop_au` catalog and `energy` + `ai_governance` schemas, loads the energy grid sample data, grants participant access, verifies the PT endpoint is reachable.

**Labs:**

| Lab | File | Description |
|-----|------|-------------|
| 01 | `labs/01_workspace_ai_settings.py` | Inspect and configure AI feature flags; verify geography enforcement |
| 02 | `labs/02_ai_gateway_setup.py` | Configure an AI Gateway endpoint with routing rules and rate limits |
| 03 | `labs/03_rate_limits_guardrails.py` | Add guardrails to block cross-geo models and filter PII patterns |
| 04 | `labs/04_usage_tracking.py` | Query `system.access.audit` to build an AI activity audit view |
| 05 | `labs/05_data_residency_compliance.py` | Data residency deep-dive (optional, time-permitting) |

**Cleanup:** `setup/cleanup.py`
Drops the `energy` schema and tables, revokes participant grants, removes the AI Gateway test endpoint.

---

## Session 2: Building Genie Space

**Folder:** `session2_genie_space/`
**Audience:** Data engineers, analysts
**Duration:** 2.5 hours

**Slide deck:** TBD

**Setup:** `setup/setup.py`
Creates `workshop_au.aemo`, loads the 5 AEMO NEM tables from DBFS CSVs, adds column comments and table descriptions, grants participant access. Expected runtime: ~5 minutes.

**Labs:**

| Lab | File | Description |
|-----|------|-------------|
| 01 | `labs/01_genie_space_setup.py` | Create the AEMO Genie Space via UI; add trusted tables |
| 02 | `labs/02_user_workflows.py` | Upload golden queries and text instructions via API |
| 03 | `labs/03_governance_access.py` | Apply UC grants and Genie Space permissions |
| 04 | `labs/04_monitoring_cost.py` | Monitor Genie usage via system tables and AI Gateway metrics |
| 05 | `labs/05_operating_model.py` | Space certification, handoff checklist, and production readiness |

**Genie config:** `genie_config/aemo_space_config.py`
Pre-creates the AEMO Genie Space skeleton with golden queries and instructions. Run before participants arrive if you want the space ready at the start of Lab 01.

**Cleanup:** `setup/cleanup.py`
Drops `workshop_au.aemo` tables and schema, deletes Genie Spaces by ID (enter IDs in widget), revokes UC grants.

---

## Session 3: Line-of-Business

**Folder:** `session3_lob/`
**Audience:** ~100 business users
**Duration:** Half day
**Delivery:** Databricks LDT team — not in this repository

Virtual session: 24 June 09:00–12:00 AEST. Contact your Databricks account team.

---

## Session 4: MCP Agents (optional)

**Folder:** `session4_mcp_agents/`
**Audience:** Data engineers, analysts, ML engineers
**Level:** 200 (guided) · **Duration:** ~2.5–3 hours

**Slide deck:** https://docs.google.com/presentation/d/1LPaJmqGy1BW1J7phIsq-AoHbdbtn7EELAM8iowLCjWw/edit
Rebuilt (13 slides) on the Build→Evaluate→Govern→Deploy→Improve spine, pulled from official Databricks decks (Agent Bricks & AI, Lakebase Fieldkit, Workshop 2c) plus the AEMO-specific slides; SOCI-free. (The old MCP-fundamentals deck `1vwV4xr3xFJ6ypqL0hKe-up7hH0rsGEvCraEfwGbQQ4M` is superseded.)

Reframed around the agent lifecycle **Build → Evaluate → Govern → Deploy → Improve** — one lab per phase, Lab 05 loops back to Lab 02.

**Setup:** `setup/setup.py`
Creates the `workshop_au.aemo` catalog and loads the six AEMO tables, confirms the PT endpoint is `READY`, creates the Vector Search endpoint and `aemo_market_notices_index` (allow 5–10 minutes), registers the NEM UC functions, and grants participant access (`SELECT` + `EXECUTE`).

**Labs:**

| Lab | File | Lifecycle | Description |
|-----|------|-----------|-------------|
| 01 | `labs/01_build_agent.py` | **Build** | LangGraph ReAct agent on the PT endpoint + 3 MCP servers, then Lakebase short-term memory + a multi-turn follow-up |
| 02 | `labs/02_evaluate_agent.py` | **Evaluate** | `mlflow.genai.evaluate()` with LLM-judge scorers against `eval/golden_questions.jsonl` |
| 03 | `labs/03_govern_agent.py` | **Govern** | Residency/cross-geo block, AI Gateway, PII/safety guardrails, UC access, `system.access.audit` |
| 04 | `labs/04_deploy_react_app.py` | **Deploy** | Build + deploy the React app in `app/` as a Databricks App (SSO, service principal) |
| 05 | `labs/05_improve_feedback_loop.py` | **Improve** | Human feedback → new eval cases → re-run Lab 02; close the loop |

**App:** `app/` — a React + TypeScript SPA with a FastAPI backend (streaming chat, sources panel, Lakebase memory), deployed as a Databricks App. Build the frontend with `cd app/frontend && npm install && npm run build`.

**Eval set:** `eval/golden_questions.jsonl` — 10 AEMO NEM questions with `inputs` + `expectations`.

**Cleanup:** `setup/cleanup.py`
Deletes the Vector Search endpoint and index, drops the UC functions, revokes grants, and removes the Databricks App.

---

## Session 5: Genie Code (optional)

**Folder:** `session5_genie_code/`
**Audience:** Data scientists
**Duration:** 1 hour

**Slide deck:** TBD

**Based on:** https://github.com/sourabhghose/genie_for_energy (Module 5)

**Setup:** `setup/setup.py`
Confirms the `workshop_au` catalog is accessible and Genie Code is enabled in the workspace. No data loading required — Session 5 uses the tables loaded by Sessions 1 and 2.

**Labs:**

| Lab | File | Description |
|-----|------|-------------|
| 01 | `labs/01_custom_instructions.py` | Write AEMO-specific personal instructions for Genie Code |
| 02 | `labs/02_skills_walkthrough.py` | Create three SKILL.md files: `energy-analytics`, `regulatory-compliance`, `genie-space-creator` |
| 03 | `labs/03_mcp_intro.py` | MCP concepts and `DatabricksMCPClient.list_tools()` demo |

**Skills (installed during Lab 02):**

| Skill | Trigger keywords |
|-------|-----------------|
| `energy-analytics` | SAIDI, SAIFI, spot price, RRP, dispatch, LOR, NEM analysis |
| `regulatory-compliance` | Australian regulatory requirements, compliance, AER, Privacy Act, STPIS, NER obligations |
| `genie-space-creator` | create Genie Space, golden queries, NL-to-SQL, Genie API |

**Cleanup:** `setup/cleanup.py`
Removes the custom instructions file and skill files from the participant's workspace home directory.

---

## Session 6: AI Ideation (optional)

**Folder:** `session6_ideation/`
**Audience:** 20–30 business users
**Duration:** Half day

**Slide deck:** TBD

**Setup:** `setup/setup.py`
Grants participant access to the AEMO Genie Space and `workshop_au.aemo` tables. Requires Session 2 to have been run first — Session 6 uses the same Genie Space built in Session 2.

**Activities:**

| File | When used |
|------|-----------|
| `activities/01_use_case_canvas.md` | Use case discovery block + hands-on exploration |
| `activities/02_question_starter_library.md` | Hands-on Genie exploration block |

**Facilitator notes:** `facilitator_notes/session6_guide.md`

**Cleanup:** `setup/cleanup.py`
Revokes participant grants on the AEMO Genie Space and schema. Does not drop any data (shared with Session 2).

---

## Slide Decks Summary

| Session | Deck | Status |
|---------|------|--------|
| Session 1 — AU East AI Feature Overview | [Google Slides](https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit) | Ready |
| Session 1 — Governance & Controls | [Google Slides](https://docs.google.com/presentation/d/18FVU2dVZYdS0ijOMk325LV3m-ktn-_lNb3Zsn2McEhk/edit) | Ready |
| Session 2 — Building Your Genie Space | TBD | To be created |
| Session 3 — LDT Line-of-Business Training | Owned by LDT team | LDT team |
| Session 4 — Building Agents, MCPs & Apps | [Google Slides](https://docs.google.com/presentation/d/1LPaJmqGy1BW1J7phIsq-AoHbdbtn7EELAM8iowLCjWw/edit) | Ready (rebuilt to L200) |
| Session 5 — Extending Genie Code | TBD | To be created |
| Session 6 — AI Ideation and Building | TBD | To be created |
