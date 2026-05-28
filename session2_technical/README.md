# Session 2: Technical Enablement for Governance, Controls, Access & Cost

**Track:** Technical Enablement  
**Duration:** Half-day (4 hours)  
**Audience:** Data Engineers, Data Scientists, Platform Engineers  
**Format:** Working session with live examples and discussion

---

## Overview

Session 2 is the technical layer of the AEMO AI enablement programme. Where Session 1 was a governance and strategy discussion, this session puts hands on keyboards — configuring the actual controls that make AI safe to open up to business users in Session 3.

The session takes a left-to-right controls flow: access before gateway, gateway before guardrails, Genie Space before usage tracking, compliance evidence last. Every step builds on the one before. By the end, participants have a technically complete, documented environment that is ready for business user enablement.

### Who attends Session 2

| Role | What they do here |
|------|--------------------|
| Data Engineers | Genie Space setup, golden queries, UC permissions, usage views |
| Data Scientists | AI Gateway endpoint config, guardrail tuning, PT endpoint validation |
| Platform Engineers | Workspace settings verification, geography enforcement, compliance evidence package |

---

## Lab Sequence

| # | Lab | Source | Duration | Outcome |
|---|-----|--------|----------|---------|
| 01 | Workspace AI Settings & Access Control | `workshop1_admin/labs/01_workspace_ai_settings.py` | 35 min | Geography enforcement verified; UC groups and grants configured |
| 02 | AI Gateway Setup & Configuration | `workshop1_admin/labs/02_ai_gateway_setup.py` | 40 min | AI Gateway endpoint live; PT routing confirmed; cross-geo models blocked |
| 03 | Rate Limits & Guardrails | `workshop1_admin/labs/03_rate_limits_guardrails.py` | 40 min | Per-user rate limits set; AU PII guardrail active; guardrail evidence generated |
| 04 | Genie Space — Admin Setup & Operating Model | `session2_technical/labs/04_genie_space_admin_setup.py` | 45 min | Production Genie Space live; operating model understood; certification checklist run |
| 05 | Usage Tracking & Cost Attribution | `workshop1_admin/labs/04_usage_tracking.py` | 35 min | Cost attribution view built; AI Gateway usage queried; budget alert configured |
| 06 | Data Residency & Compliance Evidence | `workshop1_admin/labs/05_data_residency_compliance.py` | 35 min | Compliance evidence package generated; SOCI Act + Privacy Act compliance artefact exported |

**Total: ~230 minutes of lab time.** Allow ~30 minutes for discussion, troubleshooting, and break.

---

## What You Will Have Built by the End of Session 2

By the end of this session, the workshop workspace will have:

1. **Geography enforcement confirmed** — `shield_csp_enforcement_account_setting` verified enabled at account level; documentation evidence captured.

2. **AI Gateway endpoint live** — All LLM traffic from the workspace routes through a single AI Gateway endpoint pointing at the in-region Provisioned Throughput model (`au_east_llm_inregion`). Cross-geo Pay-Per-Token models are explicitly blocked.

3. **Rate limits configured** — Per-user QPM cap set on the AI Gateway endpoint so no single user can exhaust capacity. Rate limit events appear in `system.ai_gateway.usage`.

4. **AU PII guardrail active** — Input guardrail blocking TFN patterns, Medicare numbers, and common AU PII patterns. Guardrail configuration saved as SOCI Act compliance artefact.

5. **Production Genie Space** — `Workshop — Energy Operations` Genie Space created with:
   - `workshop_au.energy` tables as trusted assets (principle of least privilege)
   - 10+ validated golden queries for AEMO/AER question patterns
   - Comprehensive instructions including SAIDI/SAIFI formulas, AU financial year, and data quality rules
   - AI Gateway enabled on the Space's SQL warehouse
   - Operating model status set to `exploratory` (ready to promote to `certified` after benchmark)

6. **Usage dashboard** — `v_ai_cost_attribution` view built over `system.ai_gateway.usage` and `system.billing.usage`. Budget alert SQL ready to deploy.

7. **Compliance evidence package** — JSON artefact covering geography enforcement, AI Gateway config, guardrail config, and AI asset UC grants. Ready for SOCI Act 2018 + Privacy Act review.

---

## Prerequisites Before Session 3 Can Run

Session 3 opens Genie to business users. The following must be true before that session begins. This checklist is also the final output of Lab 04, run as a live verification.

### Technical Prerequisites

- [ ] **Geography enforcement enabled** — `shield_csp_enforcement_account_setting` must be `ENABLED` at account level. Verify with: `GET /api/2.0/accounts/{account_id}/settings/types/shield_csp_enforcement_account_setting/etag/default`.

- [ ] **PT endpoint deployed and running** — The Provisioned Throughput endpoint (`au_east_llm_inregion` or equivalent) must be in `READY` state. Verify with the Serving Endpoints API or in the UI under Machine Learning > Serving.

- [ ] **AI Gateway enabled on the PT endpoint** — The endpoint must have AI Gateway configured (not just model serving). Verify: navigate to the endpoint, confirm an AI Gateway config exists with usage tracking on.

- [ ] **Workshop Genie Space created** — The `Workshop — Energy Operations` Genie Space must exist with `workshop_au.energy` tables as trusted assets. Space ID must be recorded for facilitator use.

- [ ] **At least 10 golden queries added** — The Genie Space knowledge store must have 10 or more verified SQL queries. Verify with `GET /api/2.0/genie/spaces/{SPACE_ID}/sql-queries`.

- [ ] **Rate limits set for business user group** — The AI Gateway endpoint must have per-user QPM limits applied. Business user group (`aemo-genie-users` or equivalent) must have `CAN_USE` only — not `CAN_MANAGE`.

- [ ] **Participant access granted** — Workshop participants (business user group) must have `CAN_USE` on the Genie Space and `SELECT` on the trusted UC tables. Verify with `GET /api/2.0/permissions/genie/spaces/{SPACE_ID}`.

- [ ] **Genie Space certification status tagged** — The space should have `space_certification_status` UC tag set. For Session 3 readiness, `exploratory` is acceptable; `certified` is the production target.

### Facilitator Preparation

- [ ] Participant list confirmed — all business users have Databricks workspace access at Viewer level or above.
- [ ] Genie Space URL copied and ready to share — format: `https://{workspace}/genie/spaces/{SPACE_ID}`.
- [ ] Sample questions list prepared — 10–15 business questions participants can ask in Session 3 (provided in Lab 04 output).
- [ ] Compliance evidence package from Lab 06 saved and accessible — needed if regulatory compliance review arises.

### What Happens if Prerequisites Are Not Met

| Unmet prerequisite | Impact on Session 3 | Resolution time |
|--------------------|--------------------|-----------------| 
| PT endpoint not running | Genie has no model to call; all questions fail | 15–30 min to deploy |
| No golden queries | Genie gives poor answers for first session; trust erodes quickly | 30–60 min to add 10 queries |
| Participant access not granted | Participants cannot open the space | 5 min per group grant |
| Geography enforcement off | Regulatory risk; facilitator must flag before proceeding | Immediate — account admin required |

---

## Navigation Guide

Labs 01, 02, 03, 05, and 06 are sourced from `workshop1_admin/labs/`. They do not need to be duplicated — open them from that location in Databricks Repos. Only Lab 04 is new and lives in this folder.

See `session2_technical/labs/README.md` for the full path reference and lab sequencing notes.
