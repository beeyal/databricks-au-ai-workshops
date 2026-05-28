# AEMO AI Enablement — Session Map

Master reference for the AEMO six-session AI enablement programme. Covers session content, lab files, decks, durations, and delivery notes.

---

## Session 1: Platform Administrators (2 hours)

**Audience:** Workspace admins
**Format:** Presentation + hands-on labs
**Total time:** 2 hours

### Part 1 — AI Feature Overview (~45 min)

**Deck:** https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit

Covers AU East feature availability, in-geo vs cross-geo posture, FMAPI tiers, AI Gateway, and MCP. Establishes the regulatory baseline (SOCI Act 2018, Privacy Act 1988, AESCSF) and confirms which features are safe for regulated workloads without additional controls.

### Part 2 — Governance & Controls (~75 min)

**Deck:** https://docs.google.com/presentation/d/18FVU2dVZYdS0ijOMk325LV3m-ktn-_lNb3Zsn2McEhk/edit

**Labs:**

| Lab | File | Duration |
|-----|------|----------|
| 01 | `workshop1_admin/labs/01_workspace_ai_settings.py` | 20 min |
| 02 | `workshop1_admin/labs/02_ai_gateway_setup.py` | 25 min |
| 03 | `workshop1_admin/labs/03_rate_limits_guardrails.py` | 20 min |
| 04 | `workshop1_admin/labs/04_usage_tracking.py` | 20 min |

Note: Lab 05 (data residency deep-dive) is optional and is not included in the 2-hour schedule. It can be run separately if the group has capacity.

---

## Session 2: Building Your Genie Space (1.5 hours)

**Audience:** Data engineers, analysts
**Format:** Hands-on labs
**Total time:** 1.5 hours

**Deck:** TBD

**Pre-session setup:** Run `session2_genie_space/genie_config/aemo_space_config.py` before participants arrive to pre-create the AEMO Genie Space skeleton.

**Labs:**

| Lab | File | Duration |
|-----|------|----------|
| 01 | `session2_genie_space/labs/01_genie_space_setup.py` | 25 min |
| 02 | `session2_genie_space/labs/02_user_workflows.py` | 25 min |
| 03 | `session2_genie_space/labs/03_governance_access.py` | 25 min |

---

## Session 3: LDT Line-of-Business Training

**Audience:** ~100 business users
**Format:** Facilitated training — run by Databricks LDT team
**Duration:** Half day

This session is not delivered from this repository. Content and facilitation are owned by the Databricks Learning & Development Team (LDT).

Virtual session: 24 June 09:00–12:00 AEST (or schedule custom cohort with LDT).

---

## Session 4 (Optional): Building Agents, MCPs & Apps (Half day)

**Audience:** Data engineers, data scientists
**Format:** Hands-on labs
**Total time:** Half day (~4 hours)

**Deck:** https://docs.google.com/presentation/d/1vwV4xr3xFJ6ypqL0hKe-up7hH0rsGEvCraEfwGbQQ4M/edit

**Labs:**

| Lab | File |
|-----|------|
| 01 | `workshop2c_mcp_agents/labs/01_agent_architecture_mcp.py` |
| 02 | `workshop2c_mcp_agents/labs/02_mcp_connections.py` |
| 03 | `workshop2c_mcp_agents/labs/03_react_agent_langgraph.py` |
| 04 | `workshop2c_mcp_agents/labs/04_databricks_app_deployment.py` |
| 05 | `workshop2c_mcp_agents/labs/05_monitoring_governance.py` |

**Prerequisites:** Session 1 complete; a Provisioned Throughput endpoint in `READY` state.

---

## Session 5 (Optional): Extending Genie Code (1 hour)

**Audience:** Data scientists, developers
**Format:** Hands-on labs
**Total time:** 1 hour

**Deck:** TBD

**Based on:** https://github.com/sourabhghose/genie_for_energy (Module 5)

**Labs:**

| Lab | File | Duration |
|-----|------|----------|
| 01 | `session5_genie_code/labs/01_custom_instructions.py` | 20 min |
| 02 | `session5_genie_code/labs/02_skills_walkthrough.py` | 30 min |
| 03 | `session5_genie_code/labs/03_mcp_intro.py` | 10 min |

**Reusable skills in `session5_genie_code/skills/`:**
- `energy-analytics` — NEM data query patterns
- `regulatory-compliance` — SOCI Act + AESCSF compliance checks
- `genie-space-creator` — Automated Genie Space scaffolding

---

## Session 6 (Optional): AI Ideation and Building (Half day)

**Audience:** 20–30 AEMO business participants
**Format:** In-person facilitated workshop
**Total time:** Half day

**Activities:** `session6_ideation/activities/`

Structured ideation session where business participants identify real AEMO use cases, prototype with Genie, and present back to the group. No coding required. Facilitated by the Databricks SA with optional technical support for participants who want to go further.

---

## Slide Decks Summary

| Session | Deck | Status |
|---------|------|--------|
| Session 1 Part 1 — AI Feature Overview | [Google Slides](https://docs.google.com/presentation/d/1a0Ji2kmWhJWgT78AeSFe37qN7ZfUOTrYFtXeHCRDTbg/edit) | Ready |
| Session 1 Part 2 — Governance & Controls | [Google Slides](https://docs.google.com/presentation/d/18FVU2dVZYdS0ijOMk325LV3m-ktn-_lNb3Zsn2McEhk/edit) | Ready |
| Session 2 — Building Your Genie Space | TBD | To be created |
| Session 3 — LDT Line-of-Business Training | Owned by LDT team | LDT team |
| Session 4 — Building Agents, MCPs & Apps | [Google Slides](https://docs.google.com/presentation/d/1vwV4xr3xFJ6ypqL0hKe-up7hH0rsGEvCraEfwGbQQ4M/edit) | Ready |
| Session 5 — Extending Genie Code | TBD | To be created |
| Session 6 — AI Ideation and Building | TBD | To be created |
