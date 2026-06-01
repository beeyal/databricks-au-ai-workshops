# Facilitator Guide — AEMO AI Enablement Programme

This guide is for the person running the enablement sessions. Participants do not need to read this document — direct them to [.github/WORKSHOP_INSTRUCTIONS.md](.github/WORKSHOP_INSTRUCTIONS.md) and the individual session READMEs.

---

## Contents

1. [Pre-Workshop Setup (All Sessions)](#1-pre-workshop-setup-all-sessions)
2. [Session 1: Platform Administrators (2 hours)](#2-session-1--platform-administrators-2-hours)
3. [Session 2: Building Your Genie Space (2.5 hours)](#3-session-2--building-your-genie-space-25-hours)
4. [Session 3: LDT Line-of-Business Training](#4-session-3--ldt-line-of-business-training)
5. [Session 4: Building Agents, MCPs and Apps (Half day, optional)](#5-session-4--building-agents-mcps-and-apps-half-day-optional)
6. [Session 5: Extending Genie Code (1 hour, optional)](#6-session-5--extending-genie-code-1-hour-optional)
7. [Session 6: AI Ideation and Building (Half day, optional)](#7-session-6--ai-ideation-and-building-half-day-optional)
8. [Common Issues and Fixes](#8-common-issues-and-fixes)
9. [Environment Requirements](#9-environment-requirements)

---

## 1. Pre-Workshop Setup (All Sessions)

Run through this checklist before **every session**. Steps marked (First time only) are required only before the first session in the programme; all other steps should be re-confirmed before each subsequent session.

### 1 week before

- [ ] **Confirm workspace region.** The workspace must be in Australia East (`australiaeast`). Log into `accounts.cloud.databricks.com`, navigate to Workspaces, and confirm the Azure region shown is `Australia East`.
- [ ] **Enable data processing geography enforcement.** In Account Console → Workspaces → [workspace] → Security and Compliance, confirm **"Enforce data processing within workspace Geography"** is toggled ON. If it is not enabled, enable it now — it can take up to 30 minutes to propagate. This is the single most important compliance control for AEMO as a SOCI Act-regulated entity.
- [ ] **Deploy the Provisioned Throughput endpoint.** Go to Serving → Create serving endpoint. Select `databricks-claude-haiku-4-5` (AU East in-region; do not use Llama models — they route cross-geo for AU East). Name it `databricks-claude-haiku-4-5`. Allow 15 minutes for the endpoint to reach Ready status. Verify it is green before the session day.
- [ ] **Import the workshop repo.** Import `https://github.com/beeyal/databricks-au-ai-workshops` into Databricks Repos in the workshop workspace. If you have already done this for a previous session, do a Git pull to ensure you have the latest version.
- [ ] **Run setup/preflight_check.py.** Open the notebook in the workspace and run all cells. All 10 checks must show `[PASS]`. Do not proceed with any other setup steps until all checks pass. Fix any `[FAIL]` items before the session day — do not leave them for the morning.
- [ ] **Run setup/00_workspace_setup.py.** (First time only) This loads all sample data including NEM12 interval reads, NMI registry, compliance events, and reference documents. The notebook takes approximately 15 minutes on a fresh workspace. Confirm the following tables exist on completion:
  - `workshop_au.meters.nem12_interval_reads`
  - `workshop_au.meters.nmi_registry`
  - `workshop_au.regulatory.compliance_events`
  - `workshop_au.regulatory.reference_docs`
- [ ] **Run setup/grant_workshop_access.py.** This provisions participant access to all workshop catalogs, tables, and endpoints. Re-run this before each session if the participant list has changed.
- [ ] **Send participant login instructions.** Provide the workspace URL and login details to all participants at least 24 hours before the session. Include a prompt to log in and confirm they can access the workspace before the session day.

### Day-of (1 hour before)

- [ ] Log into the workshop workspace and confirm your own session is active
- [ ] Re-run `setup/preflight_check.py` — all checks should still be `[PASS]`
- [ ] Go to Serving and confirm the `databricks-claude-haiku-4-5` endpoint status is **Ready** (green). If it shows "Updating", wait — do not restart it unless it has been in that state for more than 20 minutes.
- [ ] Confirm the three key sample tables are queryable:
  ```sql
  SELECT COUNT(*) FROM workshop_au.meters.nem12_interval_reads;
  -- Expected: ~6,700 rows
  SELECT COUNT(*) FROM workshop_au.meters.nmi_registry;
  SELECT COUNT(*) FROM workshop_au.regulatory.compliance_events;
  ```
- [ ] Have the session slide deck open in a separate tab and confirm screen sharing is working
- [ ] Ask 2–3 participants to log in early as a smoke test — the most common issue (user not added to workspace) surfaces immediately this way
- [ ] If any participant cannot log in: go to Account Console → User Management, confirm the user exists, and add them to the workspace with at least Workspace User entitlement

---

## 2. Session 1 — Platform Administrators (2 hours)

**Audience:** Workspace admins, security architects, platform engineers, CISO team  
**Goal:** Participants leave knowing how to configure, govern, and audit AI features in Databricks for a SOCI Act-regulated environment  
**Labs:** 4 labs (one condensed)

### Timing guide

| Time | Activity |
|------|----------|
| 0:00–0:45 | Part 1 — AI Feature Overview (AU East deck). Walk the availability matrix, FMAPI tier breakdown, geography enforcement setting. |
| 0:45–1:05 | Lab 01 — Workspace AI settings (20 min) |
| 1:05–1:30 | Lab 02 — AI Gateway setup (25 min) |
| 1:30–1:50 | Lab 03 — Rate limits and guardrails (20 min) |
| 1:50–2:00 | Lab 04 — Usage tracking (10 min, key cells only — see note below) |

**Note on Lab 04:** The full Lab 04 is designed for 20 minutes but this session runs to 2 hours. Have participants run the audit query cells only (cells marked REQUIRED). Skip the export and dashboard cells. Offer Lab 04 as a standalone follow-up for participants who want to complete it in their own time.

**Note on Lab 05 (data residency):** Lab 05 is NOT part of this 2-hour session. It is available as optional self-directed follow-up. Point participants to it in the repo README.

### Key facilitation notes for Session 1

**The geography enforcement toggle is the most important moment in this session.** Pause the presentation when you reach it, ask everyone to open their Account Console in a browser tab, and find the setting together before you continue. Even if participants cannot toggle it themselves (because most will not be Account Admins on the workshop workspace), they need to know exactly where to find it so they can have the right conversation with their Account Admin.

**AI Gateway V1 vs V2:** V2 (Beta) launched LLM Guardrails on May 19 2026. Acknowledge that V2 exists and is in beta. Use V1 (GA) for all labs — V1 is what AEMO should use in production today. If someone asks about V2 guardrails specifically, note that the content-filtering capability is available but the APIs may change before GA.

**Query-router deprecation:** If any participant is using External Models with `databricks-query-router`, flag the June 1 2026 deprecation deadline. They need to migrate to a named endpoint.

**IRAP question:** This will come up. The correct answer is: Provisioned Throughput endpoints are IRAP-eligible (data stays in-region, no external routing). Pay-per-token endpoints are not IRAP-eligible. AI Gateway with a PT endpoint as the target backend is IRAP-eligible. When in doubt, direct to the Databricks Trust Centre.

**Common questions in Session 1:**

- *"What is the difference between a Workspace Admin and an Account Admin?"* — Account Admin governs the entire Databricks account: all workspaces, billing, UC metastores, and account-level compliance settings including geography enforcement. Workspace Admin governs one workspace. Geography enforcement lives at Account level.
- *"Can we use OAuth tokens instead of PATs?"* — Yes, and for production you should. Lab 01 section 5 shows service principals with OAuth secrets. PATs are used in the labs as a workshop convenience only.
- *"Does SCIM sync replace the need to manage GRANT statements?"* — SCIM handles identity (syncing users and groups from Azure Entra ID). Unity Catalog handles authorisation (GRANT statements). They work together — SCIM does not replace UC grants.
- *"How long is audit data retained in system tables?"* — 365 days by default. Export to external storage via Delta Sharing for longer retention periods.

### Lab 01 facilitation notes

Walk through the AU East residency table in the lab header before participants start. The green/red availability matrix is the anchor for every governance decision in this session. Participants from SOCI Act-regulated teams will have questions about Pay-per-Token — acknowledge the concern and tell them Lab 02 covers how to block it at the AI Gateway level.

The GRANT SQL cells in Section 4 are deliberately commented out. Do not uncomment them in a shared lab workspace. In regulated environments, reviewing a pattern without executing it in production is standard practice — reinforce that habit.

### Lab 02 facilitation notes

AI Gateway is the control plane for routing, rate limiting, and guardrailing LLM calls. The key message for AEMO: AI Gateway lets you enforce that only the in-region Provisioned Throughput endpoint is reachable for a given group or workload, making Pay-per-Token effectively unavailable to that group.

Watch for participants who do not have CAN_MANAGE on the serving endpoint. This is expected if their workspace entitlement was set to Workspace User only — remind them this is a lab simulation and their production role would include this permission.

### Lab 03 facilitation notes

Rate limits and guardrails in AI Gateway map directly to the kinds of controls AEMO's information security team will require before approving production use. Frame this lab as "here is how you answer the IS team's questions." The specific controls to highlight:

- Tokens per minute cap — prevents runaway costs and protects endpoint capacity for critical workloads
- User-level rate limits — important for a shared endpoint serving multiple teams
- Input/output guardrails (V2 beta) — content policy enforcement; acknowledge this is new and being evaluated for GA

### Lab 04 facilitation notes (condensed)

`system.access.audit` is where every AI action — Genie query, model serving call, AI Gateway request — is recorded. Run the live audit query that shows Genie Space queries in the log. If the Genie Space was tested during pre-session setup, those queries will already appear — this is a powerful moment, participants see their own actions in the log in real time.

Focus on the two REQUIRED cells only:
1. Query showing AI Playground interactions in the audit log
2. Query showing model serving endpoint calls by user

Save the dashboard build and export cells for participants who want to self-complete Lab 04 after the session.

---

## 3. Session 2 — Building Your Genie Space (2.5 hours)

**Audience:** Data analysts, reporting leads, business intelligence teams  
**Goal:** Participants leave with a working Genie Space connected to energy data and a production readiness checklist they can take back to their team  
**Labs:** 3 labs

### Pre-session setup (facilitator only)

- [ ] Run `session2_genie_space/genie_config/aemo_space_config.py` before the session. This creates the base Genie Space and loads the golden queries.
- [ ] Test the Genie Space by asking these three questions and confirming all return correct results:
  1. "What is the total energy consumption in kWh for each NMI last week?"
  2. "Which NMI had the highest consumption on a single day this month?"
  3. "How many intervals had an Estimated quality flag in the last 30 days?"
- [ ] Record the Space ID — participants will need it for Lab 01. The Space ID appears in the URL when you have the space open: `https://<workspace>.azuredatabricks.net/genie/spaces/<SPACE_ID>`.
- [ ] Confirm participants have `CAN_USE` on the Genie Space. This is granted by `grant_workshop_access.py` but verify it before the session.

### Timing guide

| Time | Activity |
|------|----------|
| 0:00–0:05 | Intro — what participants will build and why |
| 0:05–0:50 | Lab 01 — Genie Space setup (40 min) |
| 0:50–1:25 | Lab 02 — User workflows (35 min) |
| 1:25–2:00 | Lab 03 — Controls and governance (30 min) |
| 2:00–2:30 | Wrap-up and production readiness checklist (30 min) |

### Key facilitation notes for Session 2

**"Show SQL" is the most important feature in Genie Spaces.** Every participant must click it at least once during Lab 01. Do not move on until you have seen every participant click "View SQL" on a Genie response. This is the feature that answers the governance question: "How do we know the AI is giving us the right answer?" — you look at the SQL it generated.

**When Genie gives a wrong answer — use it as a teaching moment.** If Genie returns incorrect results for a question in Lab 01, do not hide it. Walk through the process of diagnosing why: look at the SQL it generated, identify where the logic went wrong (wrong column, wrong filter, ambiguous phrasing), then add a golden query for that question type and show that the corrected response is now reliable. This is the single most useful practical skill participants can take home from this session.

**Golden queries are the reliability mechanism.** Participants often expect Genie to be perfectly accurate out of the box. Correct that expectation early: Genie accuracy improves linearly with the quality and coverage of golden queries you provide. A mature production Genie Space for AEMO should have 20–50 golden queries covering the most common question types for their domain.

**Common questions in Session 2:**

- *"Can I use this for our real settlement data?"* — Yes. The path is: (1) connect your production settlement tables to Unity Catalog, (2) add comprehensive column descriptions and table-level descriptions to those tables, (3) build a Certified Space pointing at those tables, (4) add golden queries for the most common question types. This session gives you the pattern — the production data connection is a separate step with your data engineering team.
- *"What happens if a participant asks a question that touches regulated or sensitive data?"* — Genie only accesses tables you have explicitly added to the space. It cannot access tables outside the space, and UC row and column-level security applies. The data access controls you have configured in Unity Catalog are fully enforced.
- *"Can we embed Genie in our internal portal?"* — Yes, via the Genie Conversation API. That is covered as an optional extension in Session 5.
- *"Who can see the questions users are asking?"* — All Genie Space queries are logged in `system.access.audit`. The Space owner and Account Admins can see usage analytics in the Space settings panel.

### Lab 01 facilitation notes

Lab 01 is the "wow" lab. The goal is to have participants asking natural language questions against real (simulated) energy data and seeing correct SQL returned within the first 10 minutes.

Suggest these starter questions to participants who are unsure what to ask:
- "Show total daily energy consumption per NMI for last week"
- "Which NMI had the highest consumption on a single day?"
- "How many intervals had an Estimated quality flag this month?"
- "Show me the top 10 NMIs by total consumption in the last quarter"

If participants ask questions the space cannot answer (e.g., pricing data, customer names, generation data), use the moment to explain that Genie Spaces are intentionally scoped to their data. In a regulated environment, you want Genie to only access the data you have explicitly added — this is a security feature, not a limitation.

### Lab 02 facilitation notes

Lab 02 covers user workflows: sharing a space, managing access, and using conversation history. The key facilitation point is the access model: Genie Space access is controlled via UC permissions, not ad-hoc sharing links. This connects the space directly to the governance framework established in Session 1.

Reinforce the metadata-quality connection: Genie uses Unity Catalog column descriptions, table descriptions, and certified tags as context for SQL generation. The investment AEMO makes in UC metadata improves Genie accuracy. These are not separate concerns.

### Lab 03 facilitation notes

Lab 03 covers production controls: usage monitoring, golden query management, and the production readiness checklist. Walk through the checklist at the end of the lab as a group rather than having participants complete it individually — this surfaces good discussion about which items are already satisfied in AEMO's environment and which require additional work.

The production readiness checklist includes:
- Tables have descriptive column comments in UC
- Tables have table-level descriptions in UC
- At least 10 golden queries covering the most common question types
- Space has a meaningful description and is named for its audience
- Access is granted to a group (not individuals) via UC
- All queries are being logged in system.access.audit
- A data steward is named as the Space owner

---

## 4. Session 3 — LDT Line-of-Business Training

**This session is NOT covered by this facilitator guide.**

Session 3 is delivered by the LDT (Learning and Development Training) team using their own materials and facilitation resources. The LDT team's session covers Genie Spaces and AI Playground for non-technical business users, using AEMO-specific scenario content developed in collaboration with AEMO's L&D team.

**Facilitator handoff actions before Session 3:**
- Ensure the Genie Space built in Session 2 is live and accessible to LDT participants
- Confirm the PT endpoint is still Ready
- Share the Space ID and workspace URL with the LDT facilitator
- Re-run `setup/preflight_check.py` and share results with the LDT facilitator before their session

If you are the LDT facilitator and are reading this guide, contact the Databricks SA team for the LDT-specific session materials.

---

## 5. Session 4 — Building Agents, MCPs and Apps (Half day, optional)

**Audience:** Data engineers, ML engineers, application developers  
**Goal:** Participants build and deploy a working AI agent, integrate an MCP tool, and understand the deployment patterns for Databricks Apps  
**Duration:** Half day (approximately 3.5 hours of labs + facilitation)  
**Status:** Optional — run this session only if there is clear demand from AEMO's engineering team

### Pre-session setup (facilitator only)

- [ ] Confirm participants have CAN_USE on the `databricks-claude-haiku-4-5` endpoint
- [ ] Run `session4_mcp_agents/setup/setup.py` — this creates the agent catalog and scaffolding notebooks
- [ ] Test the sample agent by running the first cell of `session4_mcp_agents/labs/01_agent_architecture_mcp.py` and confirming a response is returned
- [ ] If using the MCP integration labs: confirm the MCP servers listed in `session4_mcp_agents/labs/02_connecting_mcp_servers.py` are reachable from the workspace
- [ ] Confirm Databricks Apps is enabled on the workspace (Workspace Settings → Apps → Enabled)

### Timing guide

| Time | Activity |
|------|----------|
| 0:00–0:20 | Introduction — agents, MCPs, and the Databricks Apps deployment model |
| 0:20–1:10 | Lab 01 — Building a Mosaic AI Agent with MLflow tracing (50 min) |
| 1:10–1:20 | Break |
| 1:20–2:10 | Lab 02 — Integrating an MCP tool (50 min) |
| 2:10–2:20 | Break |
| 2:20–3:10 | Lab 03 — Deploying as a Databricks App (50 min) |
| 3:10–3:30 | Wrap-up, deployment patterns review, Q&A |

### Key facilitation notes for Session 4

**MCPs (Model Context Protocol) are new.** Most participants will not have heard of the term. Spend 5 minutes at the start of the MCP lab explaining the concept: an MCP is a standardised way for an AI agent to call an external tool or data source. In the AEMO context, this could be a real-time meter data API, a regulatory document store, or an internal scheduling system. The agent you built in Lab 01 becomes significantly more useful when it can access live data through an MCP rather than relying on static tables.

**Databricks Apps deployment is the production path.** Labs 01 and 02 run agents in notebooks — that is for development and testing. Lab 03 shows the production deployment model: package the agent as a Databricks App, deploy it to a URL, and govern access via Unity Catalog. This is the architecture AEMO should use if they want to expose an AI agent to a broader set of users beyond the engineering team.

**MLflow tracing in Lab 01 is not optional.** Some participants will want to skip the tracing setup and go straight to running the agent. Do not allow this. MLflow traces are the audit trail for agent behaviour — in a regulated environment, they are equivalent to the `system.access.audit` log for Genie Spaces. Participants who skip tracing will not have the observability they need in production.

**Common questions in Session 4:**

- *"How does this compare to Azure OpenAI Service?"* — Azure OpenAI gives you models. Databricks gives you models plus data governance, Unity Catalog integration, MLflow observability, and a deployment platform. The Databricks-native path keeps data in your UC governance boundary; Azure OpenAI requires you to manage data movement and access control separately.
- *"Can the agent access our production settlement data?"* — Yes, using the same UC permissions model as Genie Spaces. Add the production tables to the agent's Unity Catalog access grants, and all row/column-level security is enforced automatically.
- *"What model should we use in production?"* — Start with `databricks-claude-haiku-4-5` (in-region, lower cost, fast). Move to `databricks-claude-sonnet-4-6` for tasks requiring stronger reasoning. Both are available in AU East.

---

## 6. Session 5 — Extending Genie Code (1 hour, optional)

**Audience:** Data engineers, analytics engineers  
**Goal:** Participants understand how to extend Genie Code with custom instructions and skills for AEMO-specific workflows  
**Status:** Optional — run this session only if there is clear demand from AEMO's engineering or analytics teams

### Pre-session setup (facilitator only)

This session is based on Sourabh's `genie_for_energy` repository: `https://github.com/sourabhghose/genie_for_energy` (Module 5).

- [ ] Import `https://github.com/sourabhghose/genie_for_energy` into Databricks Repos alongside the main workshop repo
- [ ] Confirm participants can access the `genie_for_energy/module5` directory in their workspace
- [ ] Review Module 5 notebooks before the session — they reference specific energy analytics functions; confirm these align with AEMO's data schema or adapt as needed
- [ ] Confirm the `databricks-claude-haiku-4-5` endpoint is Ready (this session's Lab 03 uses it)

### Timing guide

| Time | Activity |
|------|----------|
| 0:00–0:20 | Lab 01 — Custom instructions for Genie Code (20 min) |
| 0:20–0:50 | Lab 02 — Skills walkthrough: energy-analytics, regulatory-compliance, genie-space-creator (30 min) |
| 0:50–1:00 | Lab 03 — MCP introduction (10 min) |

### Key facilitation notes for Session 5

**Custom instructions are underused.** Most Genie Code users operate with no custom instructions, which means Genie has no context about their domain, coding standards, or conventions. Lab 01 shows the transformative difference between a generic prompt and one that is prefixed with domain context: "You are working with Australian NEM12 interval meter data. The main table is `workshop_au.meters.nem12_interval_reads`. Columns are: nmi, interval_date, interval_number, read_kwh, quality_flag, meter_serial, region. All timestamps are in AEST."

**Skills are composable.** Lab 02 walks through three pre-built skills from `genie_for_energy`:
1. `energy-analytics` — functions for NEM12 pattern analysis, consumption aggregation, and anomaly detection
2. `regulatory-compliance` — helper functions for compliance event classification and reporting period calculations
3. `genie-space-creator` — scaffolding to programmatically create a Genie Space from a table list and generate starter golden queries

The teaching point is that skills in Genie Code are reusable Python modules — AEMO can build their own skill library to standardise common analytics patterns across their notebook estate.

**Lab 03 MCP introduction is intentionally brief.** It is a 10-minute conceptual preview connecting to the deeper content in Session 4 (if that session is also running). If Session 4 is not on the programme, expand Lab 03 to 20 minutes and run through the MCP connection exercise in more detail.

**Common questions in Session 5:**

- *"How do we share custom instructions across the team?"* — Custom instructions can be stored in a shared notebook or as a workspace-level configuration. The `genie_for_energy` repo includes a pattern for loading instructions from a UC table, which allows centralised management and versioning.
- *"Are the skills in genie_for_energy production-ready?"* — They are reference implementations for common energy analytics patterns. Treat them as starting points — review the code, adapt the schemas to match your actual tables, and add appropriate error handling before deploying to production.
- *"Can Genie Code connect to our external data sources?"* — Via MCP (covered in Lab 03 and in depth in Session 4). Genie Code itself runs in the notebook compute context, so it can also use any library or connection available in the notebook environment.

---

## 7. Session 6 — AI Ideation and Building (Half day, optional)

**Audience:** Mixed — business analysts, data engineers, domain SMEs, management  
**Goal:** Teams identify, prioritise, and begin prototyping 2–3 high-value AI use cases for AEMO  
**Status:** Optional — most effective when run 2–4 weeks after Sessions 1–3, once participants have had time to work with Genie Spaces independently

### Pre-session setup (facilitator only)

- [ ] Confirm the Genie Space built in Session 2 is live, tested, and accessible to all participants in this session (including management/SMEs who may not have attended Sessions 1–2)
- [ ] Print or share digitally: `materials/question_card_library.md` — a set of prompt cards with example questions organised by AEMO domain (settlements, network operations, regulatory compliance, market data)
- [ ] Print or share digitally: `materials/use_case_canvas.md` — a structured worksheet for capturing a use case hypothesis, data requirements, success criteria, and implementation path
- [ ] Prepare the room for group working: tables of 4–6 people, whiteboard or equivalent per group
- [ ] For virtual delivery: set up breakout rooms in advance, one per team, with the use case canvas shared as a Google Doc in each room

### Timing guide

| Time | Activity |
|------|----------|
| 0:00–0:30 | Context setting — what AI can do for AEMO (30 min). Cover the 3 approved use case archetypes, demonstrate the live Genie Space, and show 2–3 reference examples from peer energy utilities. |
| 0:30–1:15 | Use case discovery (45 min). Teams fill in the use case canvas for 2–3 use case ideas. Facilitator and participants rotate through groups. |
| 1:15–2:15 | Hands-on Genie exploration (60 min). Teams use the live Genie Space to explore their use case ideas. Goal: at least one "this actually works" moment per team. |
| 2:15–2:45 | Prioritisation and roadmap (30 min). All-group shareout. Score use cases on a 2x2 (business value vs implementation effort). Identify the 1–2 highest-priority use cases for a subsequent sprint. |
| 2:45–3:00 | Wrap-up and next steps (15 min). Assign owners, set a follow-up date. |

### Key facilitation notes for Session 6

**The most common failure mode in ideation sessions is scope creep.** Participants will generate use cases that require data that does not yet exist in Unity Catalog, integrations that are months away, or models that are not in-region. Your role as facilitator is to redirect these toward what is achievable with the data and tools they have right now. A good redirect: "That is a great idea for Phase 2. For today, let's explore what we can do with the NEM12 data that is already in the Genie Space."

**The use case canvas is the deliverable.** Each team should leave Session 6 with at least one completed canvas that is specific enough to hand to a data engineer and say "build this." Vague use cases ("use AI to improve our operations") are a signal to go back to the canvas and fill in the data requirements, success criteria, and implementation path sections more specifically.

**Reference examples for context setting.** Use these energy utility AI adoption examples in the opening 30 minutes:
- Settlements data analytics: natural language queries replacing ad-hoc SQL requests (reduces analyst wait time from hours to minutes)
- Regulatory compliance event classification: automated categorisation of compliance events using AI functions, with human review for edge cases
- Network operations reporting: Genie Space for non-technical operations staff to query outage and performance data without needing SQL skills

These archetypes are directly relevant to AEMO and give participants a concrete frame for their own ideation.

**For the Genie exploration phase.** Circulate through teams and listen for two things:
1. Teams who are stuck on data that is not in the Genie Space — redirect them to questions the space can answer, or note the missing data as a future UC ingestion task
2. Teams who have a "this works" moment — ask them to capture the exact question that worked as a golden query candidate for the Space

**Prioritisation framework for the 2x2.** Use these axes:
- Business value: How many people benefit? How frequently? What is the cost of the current manual process?
- Implementation effort: Is the data already in UC? Does it require a new integration? Is the use case within existing AI Gateway guardrails?

Target the top-right quadrant: high value, low effort. These are your quick wins and the ones that build confidence for more complex use cases.

**Common questions in Session 6:**

- *"When can we move from the workshop data to our real data?"* — The path is: (1) confirm the production tables are in Unity Catalog, (2) set up column descriptions and table descriptions, (3) create a new Genie Space pointing at the production tables, (4) add golden queries. The Databricks SA team can assist with steps 1–2. Steps 3–4 can be done by AEMO's own team using the Session 2 labs as a guide.
- *"How do we get management approval to proceed?"* — The use case canvas completed in this session is designed to be the input to an approval process. It captures the business case, data requirements, and implementation path in a format that is consumable by a non-technical stakeholder. Suggest sharing the canvas with the relevant team lead as the first step.
- *"What does a production rollout look like?"* — For a Genie Space: create a Certified Space in UC (see Session 2 Lab 03 production checklist), run a 2-week internal pilot with 5–10 users, gather feedback on answer quality, refine golden queries, then open to the broader team. For an agent or app (Sessions 4–5): the Databricks Apps deployment model provides a URL, access control via UC, and usage monitoring via MLflow — the same deployment pattern as any internal web application.

---

## 8. Common Issues and Fixes

The following table covers the 15 most common issues encountered across all sessions. For issues not listed here, check `setup/preflight_check.py` output — it diagnoses the most common configuration problems and provides fix instructions inline.

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| Genie Space not visible in left sidebar | Feature not enabled at workspace level, or participant lacks entitlement | Go to Workspace Settings → AI Features → Genie Spaces: On. Also confirm the participant's workspace user entitlement includes AI features. |
| PT endpoint not Ready (stuck in "Updating") | Cold start, resource contention, or endpoint was recently deleted and recreated | Wait up to 30 minutes. If not Ready after 30 minutes, delete the endpoint and recreate it. Always provision at least 15 minutes before session start. |
| Geography enforcement OFF in preflight check | "Enforce data processing within Geography" not enabled at Account level | Enable in Account Console → Workspaces → [workspace] → Security and Compliance. Takes up to 30 minutes to propagate. |
| System tables empty or `workshop_au` catalog not found | `setup/00_workspace_setup.py` not run, or ran with errors | Re-run the setup notebook. Check for red error cells and fix the underlying issue (usually a permissions problem on the UC metastore). |
| Participant cannot access workspace | User not added as a workspace user | Go to Account Console → User Management, confirm the user exists at account level, and add them to the workspace with Workspace User entitlement. |
| Genie returns wrong answer or SQL error | Column or table name in the question does not match the actual schema | Add a column comment in Unity Catalog describing the column's meaning and name. Add a golden query for the question type that returned incorrect results. |
| `ai_query()` routes data outside AU East | Function called without specifying the PT endpoint explicitly | Change the call to `ai_query('databricks-claude-haiku-4-5', ...)`. Configure AI Gateway to block unapproved endpoints for the participant group. |
| `ai_query()` returns a permissions error | User lacks CAN_QUERY on the serving endpoint | Run: `GRANT CAN_QUERY ON SERVING ENDPOINT \`databricks-claude-haiku-4-5\` TO \`account users\`;` |
| Import repo fails in Databricks Repos | GitHub URL requires authentication | Use HTTPS with a GitHub Personal Access Token. Confirm the repository is public. |
| Serverless SQL warehouse not available | Serverless not enabled on the workspace | Enable via Account Console → Workspaces → [workspace] → Compute → Serverless. |
| `G` key does not trigger Generate in notebook | User is in Edit mode (cursor inside a cell) | Press Escape to enter Command mode, then press G. |
| Cluster attach fails with "cluster not found" | Shared cluster was terminated between sessions | Restart the shared cluster, or switch participants to a serverless environment. |
| `403 Forbidden` on Account API calls in Lab 01 | Participant is not an Account Admin (expected for most participants) | This is expected behaviour. Show the correct API response from the facilitator machine. The teaching point is knowing where to check, not executing the change. |
| SCIM group sync not reflected in workspace | SCIM provisioning delay (up to 15 minutes) | Wait 15 minutes and refresh. If the user is still not present, add them directly in the workspace UI as a temporary measure. |
| `databricks-sdk` import error in notebook | Older DBR version pre-dating SDK pre-install | Use DBR 13.3 LTS or later. `databricks-sdk` is pre-installed from DBR 13+. If on an older runtime, run `%pip install databricks-sdk` in the notebook. |

---

## 9. Environment Requirements

### Participants

Participants need a modern web browser only. No local software installation is required for any session.

| Requirement | Detail |
|-------------|--------|
| Browser | Google Chrome 110+ or Microsoft Edge 110+ (recommended). Firefox is supported but some notebook keyboard shortcuts differ. Safari is not recommended — WebSocket behaviour varies. |
| Network | HTTPS (port 443) outbound access to `*.azuredatabricks.net` and `*.blob.core.windows.net` |
| Screen resolution | 1280×800 minimum; 1920×1080 recommended for notebooks with the chat panel open alongside |
| Local tools | None required — all compute, storage, and AI processing runs in the Databricks workspace |

### Workspace (facilitator-provisioned)

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Cloud region | Azure Australia East | Azure Australia East |
| Databricks Runtime | DBR 14.3 LTS | DBR 15.4 LTS |
| Cluster type | Standard (single-user or shared) | Serverless |
| Unity Catalog | Enabled | Enabled |
| Serverless compute | Enabled | Enabled |
| AI features | Genie Spaces, AI Playground, Notebook Assistant all On | All AI features On |
| Provisioned Throughput | 1 endpoint (`databricks-claude-haiku-4-5`), 1 token unit | 2 token units for sessions with > 20 participants |
| Data residency enforcement | "Enforce data processing within Geography" ON | ON |
| Storage | Azure Data Lake Storage Gen2 (auto-provisioned with workspace) | — |

### Network (corporate/office delivery)

If running any session in a corporate office environment, confirm the following firewall rules with AEMO's network team at least 3 business days before:

| Traffic | Destination | Port | Notes |
|---------|-------------|------|-------|
| Databricks workspace UI | `*.azuredatabricks.net` | 443 | Required for all sessions |
| Azure Blob / ADLS Gen2 | `*.blob.core.windows.net`, `*.dfs.core.windows.net` | 443 | Required for data access |
| GitHub (repo import) | `github.com`, `raw.githubusercontent.com` | 443 | Required for setup steps; can be done by facilitator in advance to avoid dependency |
| Unity Catalog metastore | Embedded in workspace, no additional rule needed | — | — |

**Corporate network blocker to watch for:** Organisations using Zscaler or Cisco Umbrella for HTTPS inspection can break WebSocket connections used by the Databricks notebook editor. If participants see a persistent loading spinner when opening a notebook, ask AEMO's network team to whitelist `*.azuredatabricks.net` for WebSocket (`Upgrade: websocket`) traffic on port 443.

### Virtual delivery

For virtual sessions, all requirements above apply. Additionally:

- Use Zoom or Teams screen sharing with participants following along in their own browser windows simultaneously
- Recommend participants use two screens — one for the video call and one for the Databricks workspace — or two browser windows side by side
- Add 10–15% to all lab time estimates — virtual participants navigate more slowly without in-person guidance
- Use the video call chat window for participants to post error messages — faster than verbal descriptions and creates a written log for post-session follow-up
- For Session 6 (ideation), pre-configure breakout rooms with shared Google Docs containing the use case canvas template before the session starts
