# Databricks AI Workshops — Australian Regulated Industries

Hands-on workshop series for enabling AI features on Databricks in critical infrastructure and privacy-regulated environments — designed and tested for the **Australia East** region.

---

## Overview

This repository contains three complementary workshops covering the full spectrum of Databricks AI adoption, from platform governance to daily developer and analyst productivity. All content is designed for organisations operating under Australian regulatory frameworks including SOCI Act 2018 (critical infrastructure), Privacy Act 1988, AESCSF, and AER regulatory obligations.

| # | Workshop | Track | Duration |
|---|----------|-------|----------|
| 1 | **Governing Databricks AI Features** | Platform Admin / Security | 3.5–4 hours |
| 2a | **Genie Code for Developers** | Data Engineer / ML Engineer | 3.5–4 hours |
| 2b | **Genie Spaces for Business Users** | Analyst / Business Stakeholder | 3 hours |

Workshop 2a and 2b are independent and can be run on the same day or on separate days. Workshop 1 should be completed (or at least facilitated) before either Workshop 2.

---

## Prerequisites

The following must be in place **before** participants arrive on the day. See the [Facilitator Guide](FACILITATOR_GUIDE.md) for setup instructions.

| Requirement | Detail |
|-------------|--------|
| Databricks workspace | UC-enabled, hosted in **Australia East** (`australiaeast`) |
| Unity Catalog | Enabled on the workspace (not optional — required for all labs) |
| Serverless compute | Enabled on the workspace |
| Data residency setting | "Enforce data processing within workspace Geography" enabled at Account level |
| Role — Workshop 1 | Workspace Admin or Account Admin |
| Role — Workshop 2a/2b | Data Engineer or above (SELECT on `workshop_au` catalog) |
| Participant device | Modern browser (Chrome or Edge recommended); no local install required |
| Network | HTTPS outbound to `*.azuredatabricks.net` and `*.blob.core.windows.net` |

---

## Quick Start

### Step 1 — Import the repository into your Databricks workspace

1. In your Databricks workspace, go to **Repos** (left sidebar)
2. Click **Add repo**
3. Enter the GitHub URL for this repository
4. Click **Create repo**

Detailed instructions with common error fixes are in [.github/WORKSHOP_INSTRUCTIONS.md](.github/WORKSHOP_INSTRUCTIONS.md).

### Step 2 — Run the workspace setup notebook

Navigate to `setup/00_workspace_setup.py` in your Repos and run it top to bottom. This notebook:
- Creates the `workshop_au` Unity Catalog and sample schemas
- Loads the NEM12 interval meter sample dataset
- Loads the regulatory reference documents
- Verifies that required AI features are enabled

Allow approximately 15 minutes for setup to complete.

### Step 3 — Run the preflight check

Navigate to `setup/preflight_check.py` and run it. All checks should return `[PASS]` before the workshop starts. If any check returns `[FAIL]` or `[WARN]`, refer to the [Facilitator Guide](FACILITATOR_GUIDE.md) for remediation steps.

---

## Workshop Overview

| Workshop | Audience | Duration | Labs | Prerequisites | Slide Deck |
|----------|----------|----------|------|---------------|------------|
| [Workshop 1: Governing Databricks AI Features](workshop1_admin/) | Workspace admins, security architects, platform engineers | 3.5–4 hours | Lab 01 Workspace AI Settings (45 min) · Lab 02 AI Gateway Setup (50 min) · Lab 03 Rate Limits & Guardrails (30 min) · Lab 04 Usage Tracking (25 min) · Lab 05 Data Residency & Compliance (40 min) | Workspace Admin or Account Admin role | *(link to be added by facilitator)* |
| [Workshop 2a: Genie Code for Developers](workshop2a_genie_code/) | Data engineers, ML engineers, analytics engineers | 3.5–4 hours | Lab 01 Genie Code Intro (30 min) · Lab 02 Notebook AI Features (30 min) · Lab 03 Custom Instructions, Skills & Tools (60 min) · Lab 04 MCP Integration (45 min) | Workshop 1 complete, or Databricks workspace access with Data Engineer role | *(link to be added by facilitator)* |
| [Workshop 2b: Genie Spaces for Business Users](workshop2b_genie_spaces/) | Business analysts, data analysts, reporting leads | 3 hours | Lab 01 Genie Space Setup (30 min) · Lab 02 Genie Space Admin (35 min) · Lab 03 Genie End User (35 min) · Lab 04 AI Functions In-Region (30 min) · Lab 05 Batch AI Pipeline (30 min) | Workshop 1 complete, or Databricks workspace access with at least Viewer role on Genie Spaces | *(link to be added by facilitator)* |

---

## Repository Structure

```
databricks-au-ai-workshops/
│
├── README.md                        ← You are here
├── FACILITATOR_GUIDE.md             ← Pre-workshop setup + facilitation notes
│
├── setup/
│   ├── 00_workspace_setup.py        ← Loads sample data, creates catalog/schemas
│   └── preflight_check.py           ← Validates workspace is ready for workshops
│
├── data/
│   ├── sample_data/                 ← NEM12 interval meter sample records
│   └── regulatory_docs/             ← Sample regulatory reference documents for Genie Spaces
│
├── workshop1_admin/
│   ├── README.md                    ← Workshop 1 overview and lab guide
│   ├── labs/
│   │   ├── 01_workspace_ai_settings.py     ← AI feature flags, geography enforcement
│   │   ├── 02_ai_gateway_setup.py          ← AI Gateway endpoints, rate limits
│   │   ├── 03_audit_logging.py             ← system.access.audit for AI actions
│   │   ├── 04_uc_governance_ai.py          ← UC grants on models, endpoints, Genie
│   │   └── solutions/                      ← Completed versions of all labs
│   └── facilitator_notes/                  ← Facilitator-only timing and Q&A notes
│
├── workshop2a_genie_code/
│   ├── README.md                    ← Workshop 2a overview and lab guide
│   ├── labs/
│   │   ├── 01_genie_code_intro.py          ← Generate, explain, fix, document
│   │   ├── 02_notebook_assistant.py        ← Chat panel, context, multi-turn prompts
│   │   ├── 03_autocomplete_patterns.py     ← Inline autocomplete best practices
│   │   └── solutions/
│   └── facilitator_notes/
│
├── workshop2b_genie_spaces/
│   ├── README.md                    ← Workshop 2b overview and lab guide
│   ├── labs/
│   │   ├── 01_genie_spaces_intro.sql       ← Natural language to SQL fundamentals
│   │   ├── 02_curating_data_for_genie.py   ← Semantic layer, certified tables, comments
│   │   ├── 03_genie_quality.py             ← Tuning, trust & verification patterns
│   │   ├── 04_ai_functions_regulated.sql   ← ai_query, residency gotchas
│   │   └── solutions/
│   └── facilitator_notes/
│
└── .github/
    └── WORKSHOP_INSTRUCTIONS.md     ← Step-by-step repo import instructions for participants
```

---

## Data Residency Compliance

All workshop content is designed for the **Australia East** (`australiaeast`) Azure region. Every lab explicitly documents its data residency posture.

The AI features used across these workshops have the following residency status as of May 2026:

| Feature | Residency | Notes |
|---------|-----------|-------|
| Genie Spaces | In-region | Safe for regulated data |
| AI Gateway | In-region | Safe for regulated data |
| FMAPI Provisioned Throughput | In-region | Safe for regulated data; requires endpoint deployment |
| Genie Code (Notebook Assistant) | In-region | Processed via Azure AI Services hosted in AU East |
| FMAPI Pay-Per-Token | **Cross-geo** | Do **not** use for regulated or personally identifiable data |
| Knowledge Assistant | **Cross-geo** | Workaround required; documented in Workshop 1 |
| Foundation Model Fine-tuning | Not available | Not available in AU East as of May 2026 |

> **Important:** The "Enforce data processing within workspace Geography" setting must be enabled at the **Account Console** level before any regulated workload runs. Workshop 1, Lab 1 covers how to verify and enforce this setting programmatically. This single setting is the most important compliance control in the entire workshop series.

---

## Sample Dataset

The workshops use a synthetic National Electricity Market (NEM) dataset that simulates real-world Australian energy data without containing actual customer information.

| Table | Description | Rows (sample) |
|-------|-------------|---------------|
| `workshop_au.meters.nem12_interval_reads` | Half-hourly interval meter reads for NEM-connected premises (NMI, kWh, quality flag) | ~6,700 |
| `workshop_au.meters.nmi_registry` | NMI master data including region (NSW1, VIC1, SA1, QLD1), connection class, and tariff type | ~50 |
| `workshop_au.regulatory.compliance_events` | Simulated AEMO compliance and outage events linked to NMIs | ~200 |
| `workshop_au.regulatory.reference_docs` | Sample regulatory reference documents (CPS 234 summary, NEM Rules extracts) for Genie Spaces | ~10 docs |

All data is synthetic. NMIs, meter serials, and addresses are fictitious and do not correspond to real network assets.

---

## Support

For workshop delivery questions, reach out to the Databricks Australia field team. For technical issues with specific labs, open a GitHub issue on this repository with the lab name, error message, and your Databricks Runtime version.

| Contact | For |
|---------|-----|
| Workshop facilitator (see invite) | Day-of logistics, access issues |
| Databricks Australia SA team | Technical questions, follow-up POC support |
| GitHub Issues on this repo | Bug reports, lab errors, content feedback |
