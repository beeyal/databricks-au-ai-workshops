# Databricks AI Workshops — AEMO Enablement Programme

Six-session hands-on AI enablement for AEMO on Azure Australia East. All content scoped to in-region features only. Governed under SOCI Act 2018 + Privacy Act 1988 (not APRA — AEMO is an energy market operator, not an APRA-regulated entity).

---

## Quick Start

### Import into Databricks Repos

1. In your Databricks workspace, go to **Repos** (left sidebar)
2. Click **Add Repo**
3. Enter: `https://github.com/beeyal/databricks-au-ai-workshops`
4. Click **Create repo**

### Run workspace setup

Navigate to `setup/00_workspace_setup.py` and run it top to bottom. This creates the `workshop_au` Unity Catalog, loads the NEM12 synthetic dataset, and verifies that required AI features are enabled. Allow approximately 15 minutes.

### Run the preflight check

Navigate to `setup/preflight_check.py` and run all 10 checks. Every check must return `[PASS]` before any session starts. If any check returns `[FAIL]` or `[WARN]`, refer to [FACILITATOR_GUIDE.md](FACILITATOR_GUIDE.md) for remediation steps.

---

## Session Overview

Session 3 is run by the Databricks LDT team and is not in this repository.

| Session | Title | Audience | Duration | Status |
|---------|-------|----------|----------|--------|
| 1 | Platform Administrators | Workspace admins | 2 hours | Ready |
| 2 | Building Your Genie Space | Data engineers, analysts | 1.5 hours | Ready |
| 3 | Line-of-Business Training | 100 business users | Half day | LDT team |
| 4 | Building Agents, MCPs & Apps | Data engineers, scientists | Half day | Ready |
| 5 | Extending Genie Code | Data scientists, developers | 1 hour | Ready |
| 6 | AI Ideation and Building | 20-30 business participants | Half day | Ready |

---

## Repository Structure

```
databricks-au-ai-workshops/
├── setup/                         ← Run these before any session
│   ├── preflight_check.py         ← 10 checks, run first
│   ├── 00_workspace_setup.py      ← Load sample data (~15 min)
│   ├── grant_workshop_access.py   ← Provision participant access
│   └── 99_teardown.py             ← Post-workshop cleanup
├── workshop1_admin/               ← Session 1 Part 2 labs
├── session2_genie_space/          ← Session 2 labs
├── workshop2c_mcp_agents/         ← Session 4 labs
├── session5_genie_code/           ← Session 5 labs
├── session6_ideation/             ← Session 6 activities
├── data/                          ← Sample datasets (AEMO NEM synthetic)
└── [docs]                         ← README, FACILITATOR_GUIDE, etc.
```

---

## Data Residency

All content uses only AU East in-region features. The single most important setting:

**Account Console → Workspaces → [workspace] → Security and compliance → "Enforce data processing within workspace Geography" must be ON.**

| Feature | Residency | Safe for regulated data |
|---------|-----------|------------------------|
| Genie Spaces | In-region | Yes |
| AI Gateway | In-region | Yes |
| FMAPI Provisioned Throughput | In-region | Yes — requires endpoint deployment |
| Genie Code (Notebook Assistant) | In-region | Yes |
| FMAPI Pay-Per-Token | Cross-geo | No — do not use for regulated data |
| Knowledge Assistant | Cross-geo | No — workaround required |
| Foundation Model Fine-tuning | Not available | N/A — not available in AU East |

---

## Regulatory Framework

AEMO, APA, and AusNet are governed by:

- **SOCI Act 2018** — critical infrastructure obligations
- **Privacy Act 1988 + APPs** — personal information handling
- **AESCSF** — Australian Energy Sector Cyber Security Framework
- **AER** — Australian Energy Regulator obligations
- **NER** — National Electricity Rules

These organisations are **not** governed by APRA (which applies to banks, insurers, and superannuation funds).

---

## Sample Dataset

The workshops use a synthetic National Electricity Market (NEM) dataset. No actual customer or network data is used.

| Table | Description |
|-------|-------------|
| `workshop_au.meters.nem12_interval_reads` | Half-hourly interval meter reads (NMI, kWh, quality flag) |
| `workshop_au.meters.nmi_registry` | NMI master data — region, connection class, tariff type |
| `workshop_au.regulatory.compliance_events` | Simulated AEMO compliance and outage events |
| `workshop_au.regulatory.reference_docs` | Sample regulatory reference documents for Genie Spaces |

---

## Support

| Contact | For |
|---------|-----|
| Workshop facilitator (see invite) | Day-of logistics, access issues |
| Databricks Australia SA team | Technical questions, follow-up POC support |
| GitHub Issues on this repo | Bug reports, lab errors, content feedback |
