# Workshop 1: Governing Databricks AI Features in Australian Regulated Industries

**Track:** Platform Admin / Security  
**Duration:** 4 hours  
**Audience:** Workspace admins, security architects, platform engineers, cloud infrastructure leads

---

## Overview

This workshop equips platform and security teams with the knowledge and hands-on experience to safely enable, govern, and audit Databricks AI features in environments subject to Australian regulatory obligations including SOCI Act 2018 (critical infrastructure), Privacy Act 1988 + APPs, AESCSF (energy sector cybersecurity), and AER regulatory obligations.

The workshop takes a controls-first approach: every AI feature introduced is accompanied by the corresponding governance control, Unity Catalog permission, and audit mechanism. By the end of the day, participants will have a documented controls framework they can adapt for their organisation.

### Why this matters for regulated industries

Australian regulators — Australian regulators expect organisations to maintain active oversight of AI systems that access or process regulated data. That means:

- Knowing exactly which AI features are enabled in each workspace
- Being able to prove that regulated data does not leave the Australian jurisdiction
- Maintaining an audit log of all AI interactions involving regulated data
- Having defined access controls that limit AI capabilities to authorised users

Databricks provides controls for all of these. This workshop shows you where they are and how to configure them.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Role | Workspace Admin on the workshop workspace, or Account Admin |
| Workspace | UC-enabled, in Australia East, sample data loaded (see main README) |
| DBR | 14.3 LTS or later (DBR 13+ has `databricks-sdk` pre-installed) |
| Prior knowledge | Familiarity with REST APIs and Python; basic Unity Catalog concepts helpful but not required |

---

## What You Will Learn

By the end of this workshop, you will be able to:

1. Inspect and configure AI feature flags at workspace and account level using the Databricks Settings API
2. Verify that "Enforce data processing within workspace Geography" is enabled — the primary data residency control
3. Configure AI Gateway endpoints with rate limiting and guardrails that block cross-region model calls
4. Query `system.access.audit` to produce an audit trail of all AI-related actions in your workspace
5. Apply Unity Catalog grants to AI assets: registered models, serving endpoints, AI Gateway routes, and Genie Spaces
6. Create and configure service principals for automated AI workloads following least-privilege principles
7. Design a group structure appropriate for a regulated energy utility or financial services environment

---

## Labs

### Lab 01 — Workspace AI Settings & Access Control

**File:** `labs/01_workspace_ai_settings.py`  
**Duration:** 35–40 minutes  
**Difficulty:** Intermediate

Configure and verify AI feature flags at workspace and account level. Understand the hierarchy of controls (account admin vs workspace admin), verify the geography enforcement setting, and set up Unity Catalog grants for AI assets including models, serving endpoints, and Genie Spaces. Create service principals for automated workloads and design a group structure for an energy utility.

Key topics: Settings API, geography enforcement (`shield_csp_enforcement_account_setting`), UC GRANT for AI assets, service principal creation, group structure.

---

### Lab 02 — AI Gateway Setup

**File:** `labs/02_ai_gateway_setup.py`  
**Duration:** 40–45 minutes  
**Difficulty:** Intermediate

AI Gateway is the control plane for all LLM calls originating from your workspace. Configure an AI Gateway endpoint that routes to your Provisioned Throughput model (in-region), sets per-user rate limits, and blocks access to external Pay-Per-Token models that process data outside Australia East. Configure guardrails to filter harmful content and PII patterns.

Key topics: AI Gateway endpoint creation, routing rules, rate limits, guardrail configuration, blocking unapproved models.

---

### Lab 03 — Audit Logging for AI Actions

**File:** `labs/03_audit_logging.py`  
**Duration:** 35–40 minutes  
**Difficulty:** Intermediate

Every AI action in Databricks — a Genie query, a model serving call, a Playground session, a Notebook Assistant generation — is recorded in `system.access.audit`. Query this table to build an audit view of AI activity in your workspace. Understand what each action type means, how to filter for AI-specific events, and how to export audit data for SIEM or compliance reporting systems.

Key topics: `system.access.audit` schema, AI event types (`genieQuery`, `serveModelQuery`, `aiGatewayRequest`), filtering, export patterns.

---

### Lab 04 — Unity Catalog Governance for AI Assets

**File:** `labs/04_uc_governance_ai.py`  
**Duration:** 30–35 minutes  
**Difficulty:** Intermediate

Apply the Unity Catalog governance model to AI assets end-to-end. Map out the full permission chain from raw data through to a Genie Space query: table SELECT → model EXECUTE → endpoint CAN_QUERY → Genie Space CAN_USE. Implement data tagging for regulated data assets and explore how tags propagate through the AI pipeline.

Key topics: Full permission chain, certified table badge, governed tags on AI assets, data classification for regulated data, lineage through AI pipelines.

---

## What You Will Have Built by the End

At the end of this workshop, your workshop workspace will have:

- A documented inventory of all AI features and their enabled/disabled state (output of Lab 1)
- An AI Gateway endpoint routing all LLM traffic through the in-region PT endpoint with rate limits applied (Lab 2)
- A live audit query dashboard showing AI activity in the workspace (Lab 3)
- A complete Unity Catalog permission structure for AI assets, following least-privilege for a regulated utility (Lab 4)
- A checklist of controls you can take back to your organisation's AI governance framework

---

## AU East Residency Reference

The table below is your quick reference for labs and discussions. It reflects the status as of May 2026.

| Feature | Residency | Safe for Regulated Data |
|---------|-----------|------------------------|
| Genie Spaces | In-region (AU East) | Yes |
| AI Gateway | In-region (AU East) | Yes |
| Notebook Assistant (Genie Code) | In-region (AU East) | Yes |
| FMAPI Provisioned Throughput | In-region (AU East) | Yes |
| Model Serving (custom models) | In-region (AU East) | Yes |
| FMAPI Pay-Per-Token | **Cross-geo** | **No** |
| Knowledge Assistant | **Cross-geo** | **No** — workaround: use Genie Spaces instead |
| Foundation Model Fine-tuning | Not available in AU East | N/A |

---

## Next Steps After This Workshop

- Run the same preflight and settings checks on your production workspace
- Review your organisation's AI feature request process against the controls covered today
- Schedule a follow-up session with your Databricks SA to review your specific SOCI Act and Privacy Act obligations and the Databricks shared responsibility model
- Consider whether Workshop 2a (Genie Code) or Workshop 2b (Genie Spaces) is the right next step for your technical teams
