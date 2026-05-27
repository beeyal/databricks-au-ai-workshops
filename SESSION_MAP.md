# AEMO AI Enablement — Session Map

This document is the master reference for planning and delivering the AEMO AI enablement programme. It shows how the three sessions relate to one another, which workshop tracks map to each session, and the recommended week-by-week rollout sequence.

---

## Programme Structure at a Glance

The programme is designed as a three-session arc: governance first, technical configuration second, business use third. Sessions must be delivered in order — each session's output is a prerequisite for the next.

```
Session 1                Session 2                  Session 3
─────────────────        ────────────────────────   ──────────────────────
AI in Australia          Technical Enablement       Business Enablement
(2 hrs, mixed)           (half-day, DE + DS)        (2 hrs, business users)
                         │
                         ├── Core track (4 hrs)
                         │   session2_technical/
                         │
                         ├── Optional: Developer track (3 hrs)
                         │   workshop2a_genie_code/
                         │
                         └── Optional: Agent Builder track (3 hrs)
                             workshop2c_mcp_agents/
```

---

## Session 1: AI and Genie in Australia

**Duration:** 2 hours
**Audience:** Mixed — executives, architects, data leads, operations managers
**Format:** Presentation and discussion. No workshop labs.

### Purpose

Establishes shared understanding across technical and non-technical stakeholders of what is available in-region today, what is cross-geo (and therefore restricted for regulated data), and what is on the roadmap. The goal is to move the group from "we have questions about this" to "we have a clear plan and a timeline."

### Deliverable

The AU East AI availability deck covers all Databricks AI features and their AU East status as of the delivery date.

**Slide deck:** [https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit](https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit)

### Content Areas

| Section | What it covers |
|---------|---------------|
| What's in-region today | Genie Spaces, AI Gateway, FMAPI PT, Genie Code, Model Serving — all safe for regulated data |
| What's cross-geo | FMAPI Pay-Per-Token, Knowledge Assistant — not suitable for critical infrastructure regulated data without mitigations |
| What's not available | Foundation Model Fine-tuning not available in AU East as of May 2026 |
| Roadmap | Known planned availability dates; framed as direction, not commitment |
| Recommended path | Sessions 2 and 3 as the enablement vehicle |

### No labs or prerequisites

Session 1 has no hands-on component. Participants need only a browser and the slide deck link.

---

## Session 2: Technical Enablement

**Duration:** Half-day (~4 hours core track, optional tracks 3 hours each)
**Audience:** Data engineers, data scientists, platform engineers
**Format:** Hands-on labs in Databricks notebooks

### Purpose

Configures the workspace controls, AI Gateway, and Genie Space that Session 3 depends on. Session 2 cannot be skipped — Session 3 literally cannot run without its outputs.

---

### Core Track (4 hours) — `session2_technical/`

The core track is mandatory for all Session 2 participants. It follows the `session2_technical/labs/` sequence, drawing primarily from `workshop1_admin/labs/` and adding one new lab (Lab 04 — Genie Space Admin Setup).

**Slide deck:** [https://docs.google.com/presentation/d/1PhUNgxUdViVYQi4gpWHFtj4WR8z44MJXo1BVdFcLX5Q/edit](https://docs.google.com/presentation/d/1PhUNgxUdViVYQi4gpWHFtj4WR8z44MJXo1BVdFcLX5Q/edit)

| # | Lab | Source File | Duration | Key Output |
|---|-----|------------|----------|------------|
| 01 | Workspace AI Settings & Access Control | `workshop1_admin/labs/01_workspace_ai_settings.py` | 35 min | Geography enforcement verified; UC groups configured |
| 02 | AI Gateway Setup & Configuration | `workshop1_admin/labs/02_ai_gateway_setup.py` | 40 min | AI Gateway endpoint live; PT routing confirmed |
| 03 | Rate Limits & Guardrails | `workshop1_admin/labs/03_rate_limits_guardrails.py` | 40 min | Per-user rate limits; AU PII guardrail active |
| 04 | Genie Space — Admin Setup | `session2_technical/labs/04_genie_space_admin_setup.py` | 45 min | Production Genie Space created; golden queries loaded |
| 05 | Usage Tracking & Cost Attribution | `workshop1_admin/labs/04_usage_tracking.py` | 35 min | Cost attribution view built; budget alert configured |
| 06 | Data Residency & Compliance Evidence | `workshop1_admin/labs/05_data_residency_compliance.py` | 35 min | SOCI Act + Privacy Act compliance evidence package exported |

**Go/no-go gate for Session 3:** The checklist at the end of Lab 04 must pass before Session 3 can be run. See `session2_technical/README.md` for the full checklist.

---

### Optional: Developer Track (3 hours) — `workshop2a_genie_code/`

Runs in parallel with or after the core track. Targets data engineers and ML engineers who want to use Genie Code (the notebook AI assistant) and build UC Functions.

**Slide deck:** [https://docs.google.com/presentation/d/1H6DiaIF8hPxj5ZtA5c6MK47uytoy30UKqNuHmwoS8C4/edit](https://docs.google.com/presentation/d/1H6DiaIF8hPxj5ZtA5c6MK47uytoy30UKqNuHmwoS8C4/edit)

| Lab | Title | Duration |
|-----|-------|----------|
| 01 | Genie Code Fundamentals | 45 min |
| 02 | Notebook Assistant & Chat Panel | 45 min |
| 03 | Autocomplete Patterns & Productivity Tips | 30 min |

Labs 01–03 from Workshop 2a are the prerequisite for the Agent Builder track.

---

### Optional: Agent Builder Track (3 hours) — `workshop2c_mcp_agents/`

For developers who want to go beyond Genie Code and build production AI agents using MCP. Requires Workshop 2a Labs 01–03 (or equivalent Genie Code experience) and a running PT endpoint.

**Slide deck:** *(add link when deck is created)*

| Lab | Title | Duration |
|-----|-------|----------|
| 00 | MCP & Skills Reference | Reference only |
| 01 | Agent Architecture & MCP Ecosystem | 30 min |
| 02 | Connecting to Databricks MCP Servers | 40 min |
| 03 | Building a Multi-Tool ReAct Agent | 45 min |
| 04 | Deploying as a Databricks App | 45 min |
| 05 | Monitoring & Governing MCP Agents | 30 min |

---

## Session 3: Business User Enablement

**Duration:** 2 hours
**Audience:** Business users, operations staff, analysts (30 people per cohort)
**Format:** Facilitated workshop, entirely through the Genie UI. No coding.

**Slide deck:** *(add link when deck is created)*

### Purpose

Gives business users hands-on experience with the Genie Space configured in Session 2. Six guided tasks cover the core AEMO operational use cases (spot prices, dispatch, notices, settlement, outages, dashboards), followed by open exploration with facilitator support.

Session 3 can be run as many times as needed after the initial Session 2 admin setup — the infrastructure does not need to be rebuilt for each cohort.

### Hard prerequisite

Session 2 core track must be complete and the Session 2 go/no-go checklist must pass before Session 3 can run.

| Required from Session 2 | Where it is created |
|------------------------|---------------------|
| AEMO Genie Space with 10+ golden queries | Session 2, Lab 04 |
| PT endpoint in `READY` state | Session 2, Lab 02 |
| AI Gateway on the Space's warehouse | Session 2, Lab 02 |
| `workshop_au.aemo.*` tables loaded | `setup/00_workspace_setup.py` |
| Participant access granted | `session3_business/genie_config/grant_participant_access.py` |

See `session3_business/README.md` for the full facilitator setup checklist.

---

## Timing Diagram — Recommended Week-by-Week Rollout

The diagram below shows the recommended delivery sequence for a standard 3-week enablement engagement. Adjust based on participant availability and infrastructure lead time.

```
Week 1: Preparation
──────────────────────────────────────────────────────────────
Mon   Provision workshop workspace (submit to go/workshops-studio)
Tue   Confirm UC enabled, geography enforcement on, serverless on
Wed   Deploy PT endpoint (15–30 min; confirm READY before Thu)
Thu   Run setup/00_workspace_setup.py — load AEMO sample data
Thu   Run setup/preflight_check.py — all checks must PASS
Fri   BUFFER — resolve any preflight failures
      (PT endpoint cold, UC not enabled, data not loading are the
       three most common blockers — allow at least 1 day to fix)

Week 2: Sessions 1 and 2
──────────────────────────────────────────────────────────────
Mon   SESSION 1 — AI and Genie in Australia (2 hrs, all stakeholders)
      Outcome: aligned on AI roadmap; Sessions 2 and 3 confirmed
Tue   PREP — confirm participant list for Session 2
Wed   SESSION 2 — Technical Enablement (half-day)
       ├── Core track (mandatory, all engineers, 4 hrs)
       ├── Developer track (optional, data engineers, 3 hrs)
       └── Agent Builder track (optional, developers, 3 hrs)
      End of day: run Session 2 go/no-go checklist
      Outcome: Genie Space live, AI Gateway configured, controls verified
Thu   REMEDIATION — fix any go/no-go failures
      (Golden queries most common — block 2 hrs to tune if needed)
Thu   Grant Session 3 participant access
      (run session3_business/genie_config/grant_participant_access.py)
Fri   Facilitator dry-run of Session 3
      (ask all 5 test questions; verify all pass)

Week 3: Session 3 and Follow-up
──────────────────────────────────────────────────────────────
Mon   SESSION 3 — Cohort 1 (30 business users, 2 hrs)
Wed   SESSION 3 — Cohort 2 if needed (30 business users, 2 hrs)
Thu   Post-session review:
       ├── Collect Genie questions that returned poor answers
       ├── Add or update golden queries for the production Space
       └── Share transition-to-production plan with customer
Fri   Debrief with customer platform team
      (review compliance evidence package; discuss production path)
```

**Notes on timing:**

- Week 1 infrastructure provisioning is the most variable step. Australian region workspace provisioning via the Credit Program can take 2–3 business days. Do not schedule Session 2 less than 5 business days after submitting the workspace request.

- The PT endpoint must be deployed and in `READY` state before Session 2. Endpoint deployment takes 15–30 minutes but can fail on first attempt due to capacity. Deploy it on Wednesday of Week 1 (not day-of) to leave time to retry.

- Session 3 can be run multiple times in Week 3 and beyond for additional cohorts. The infrastructure only needs to be set up once.

- The Agent Builder track (Workshop 2c) can be run independently of Session 3. It does not produce any prerequisite for Session 3, so it can be scheduled for a separate day if the primary cohort is not developer-focused.

---

## Repository Directory Structure

```
databricks-au-ai-workshops/
│
├── SESSION_MAP.md                    ← You are here
├── README.md                         ← Overall workshop overview + data residency reference
├── FACILITATOR_GUIDE.md              ← Pre-workshop setup + common issues
│
├── setup/
│   ├── 00_workspace_setup.py         ← Creates catalog, loads AEMO + NEM12 data
│   └── preflight_check.py            ← Validates workspace readiness
│
├── session2_technical/               ← SESSION 2: Core technical track
│   ├── README.md                     ← Session 2 overview, lab sequence, go/no-go checklist
│   └── labs/
│       └── 04_genie_space_admin_setup.py
│
├── session3_business/                ← SESSION 3: Business user enablement
│   ├── README.md                     ← Session 3 overview, facilitator setup, run sheet
│   ├── activities/
│   │   ├── question_card_library.md  ← 30 questions for guided tasks and open exploration
│   │   └── dashboard_building_guide.md
│   └── genie_config/
│       └── aemo_genie_space_setup.py ← Creates/validates the AEMO Genie Space
│
├── workshop1_admin/                  ← Governance and controls labs (reused in Session 2)
│   ├── README.md
│   └── labs/
│       ├── 01_workspace_ai_settings.py
│       ├── 02_ai_gateway_setup.py
│       ├── 03_audit_logging.py
│       └── 04_uc_governance_ai.py
│
├── workshop2a_genie_code/            ← Optional: Developer track (Session 2)
│   ├── README.md
│   └── labs/
│       ├── 01_genie_code_intro.py
│       ├── 02_notebook_assistant.py
│       └── 03_autocomplete_patterns.py
│
├── workshop2b_genie_spaces/          ← Standalone: Genie Spaces for business analysts
│   ├── README.md
│   └── labs/
│       └── ...
│
└── workshop2c_mcp_agents/            ← Optional: Agent Builder track (Session 2)
    ├── README.md                     ← Workshop 2c overview, lab guide, prerequisites
    └── labs/
        ├── 00_mcp_skills_reference.py
        ├── 01_agent_architecture_mcp.py
        ├── 02_mcp_connections.py
        ├── 03_react_agent_langgraph.py
        ├── 04_databricks_app_deployment.py
        └── 05_monitoring_governance.py
```

---

## Slide Decks Summary

| Session / Track | Slide Deck Link | Status |
|----------------|----------------|--------|
| Session 1 — AI and Genie in Australia | [Google Slides](https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit) | Ready |
| Session 2 — Core technical track | [Google Slides](https://docs.google.com/presentation/d/1PhUNgxUdViVYQi4gpWHFtj4WR8z44MJXo1BVdFcLX5Q/edit) | Ready |
| Session 2 — Developer track (Workshop 2a) | [Google Slides](https://docs.google.com/presentation/d/1H6DiaIF8hPxj5ZtA5c6MK47uytoy30UKqNuHmwoS8C4/edit) | Ready |
| Session 2 — Agent Builder track (Workshop 2c) | *(add link when created)* | To be created |
| Session 3 — Business user enablement | *(add link when created)* | To be created |

---

## Questions and Support

For questions about delivering this programme, contact the Databricks Australia SA team. For technical issues with specific labs, open a GitHub issue on this repository with the lab file name, error message, and your Databricks Runtime version.
