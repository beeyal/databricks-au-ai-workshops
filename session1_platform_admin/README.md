# Session 1: Governing Databricks AI Features in Australian Regulated Industries

**Track:** Platform Admin / Security  
**Duration:** ~2 hours (4 labs × 25–40 min each)  
**Audience:** Workspace admins, security architects, platform engineers, cloud infrastructure leads

---

## Overview

This workshop equips platform and security teams with the knowledge and hands-on experience to safely enable, govern, and audit Databricks AI features in environments subject to Australian regulatory obligations including Privacy Act 1988 + APPs, AESCSF (energy sector cybersecurity), and AER regulatory obligations.

The workshop takes a controls-first approach: every AI feature introduced is accompanied by the corresponding governance control, Unity Catalog permission, and audit mechanism. By the end of the day, participants will have a documented controls framework they can adapt for their organisation.

### Why this matters for regulated industries

Australian regulators expect organisations to maintain active oversight of AI systems that access or process regulated data. That means:

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

### Lab 01 — AI Gateway Setup

**File:** `labs/01_ai_gateway_setup.py`  
**Duration:** ~40 minutes  
**Difficulty:** Intermediate

Pre-flight checks (geography enforcement, Partner-Powered AI flags, UC grants on models/endpoints/Genie Spaces), then configure an AI Gateway route on the prerequisite serving endpoint. Covers rate limits, PII BLOCK guardrails, payload logging, and end-to-end testing.

Key topics: Settings API (`llm_proxy_partner_powered`), geography enforcement (UI-verified), UC GRANT for AI assets, AI Gateway config via REST and SDK, PII/safety testing, compliance check.

---

### Lab 02 — Rate Limits & Guardrails

**File:** `labs/02_rate_limits_guardrails.py`  
**Duration:** ~35 minutes  
**Difficulty:** Intermediate

Prove rate limits fire 429s with a live burst test. Test built-in AU PII detection (TFN, Medicare, ABN, phone, email). Handle the NMI edge case. Add application-layer keyword blocking and a custom LLM-as-judge UC function for energy-sector-specific identifiers. Generate a structured guardrail verification report.

Key topics: QPM/TPM limits, 429 handling, AU PII pattern testing, NMI edge case, keyword blocking, custom UC guardrail, verification report artefact.

---

### Lab 03 — Usage Tracking & Cost Attribution

**File:** `labs/03_usage_tracking.py`  
**Duration:** ~30 minutes  
**Difficulty:** Intermediate

Verify audit logging is active. Query `system.ai_gateway.usage` for token consumption, user trends, and guardrail hits. Build a cost attribution view by team/project tag. Set up a daily budget alert. Reference SQL query card included.

Key topics: `system.ai_gateway.usage`, `system.access.audit`, `system.billing.usage`, cost attribution by request tag, budget alerts, split billing via endpoint tags.

---

### Lab 04 — Data Residency & Compliance Evidence

**File:** `labs/04_data_residency_compliance.py`  
**Duration:** ~25 minutes  
**Difficulty:** Intermediate

Assemble a compliance evidence package: workspace region verification, geography enforcement check, AI feature inventory with residency status, regulatory audit log export, UC tag schema for asset classification, and a pre-flight checklist for new user group onboarding.

Key topics: Geography enforcement API check, pre-flight checklist script, `system.access.audit` AI event export, UC governed tags, compliance evidence package, Privacy Act PII controls documentation.

---

## What You Will Have Built by the End

At the end of this workshop, your workshop workspace will have:

- An AI Gateway endpoint routing all LLM traffic through the in-region PT endpoint, with PII BLOCK guardrails, payload logging, and rate limits configured (Lab 01)
- Proven rate limits and AU PII guardrails via live tests, with a guardrail verification report (Lab 02)
- A cost attribution view across AI usage system tables with a daily budget alert configured (Lab 03)
- A compliance evidence package with pre-flight checklist, feature inventory, and regulatory audit log export (Lab 04)
- A controls checklist you can take back to your organisation's AI governance framework

---

## AU East Residency Reference

The table below is your quick reference for labs and discussions. It reflects the status as of June 2026.

| Feature | Residency | Safe for Regulated Data |
|---------|-----------|------------------------|
| Genie Spaces | In-region (AU East) | Yes |
| Genie Agent Mode (within Genie Spaces) | In-region (AU East) | Yes |
| AI Gateway | In-region (AU East) | Yes |
| FMAPI Provisioned Throughput | In-region (AU East) | Yes |
| FMAPI Pay-Per-Token — claude-haiku-4-5, claude-sonnet-4-5/4-6, claude-opus-4-6, gpt-oss-20b/120b, qwen3-embedding-0-6b | In-region (AU East) | **Yes** |
| FMAPI Pay-Per-Token — Llama, Gemma, qwen35-122b-a10b, qwen3-next-80b-a3b-instruct, older Claude Sonnet 4 | **Cross-geo** | **No** |
| Model Serving (custom models) | In-region (AU East) | Yes |
| Knowledge Assistant (Agent Bricks) | **Cross-geo** | **No** — no committed AU East in-geo date |
| Supervisor Agent / MAS (Agent Bricks) | **Cross-geo** | **No** — no committed AU East in-geo date |
| Foundation Model Fine-tuning | Not available in AU East | N/A |

---

## Next Steps After This Workshop

- Run the same preflight and settings checks on your production workspace
- Review your organisation's AI feature request process against the controls covered today
- Schedule a follow-up session with your Databricks SA to review your specific Australian regulatory requirements and Privacy Act obligations and the Databricks shared responsibility model
- Consider whether Session 5 (Genie Code) or Session 2 (Building Your Genie Space) is the right next step for your technical teams
