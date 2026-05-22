# Session 2 — Lab Reference

This folder contains **only Lab 04**, which is new content specific to Session 2.  
Labs 01, 02, 03, 05, and 06 are the existing Workshop 1 labs — do not duplicate them.

---

## Lab Locations

Open these paths in Databricks Repos. Run them in the order shown below.

| # | Lab | File location | Duration |
|---|-----|---------------|----------|
| **01** | Workspace AI Settings & Access Control | `workshop1_admin/labs/01_workspace_ai_settings.py` | 35 min |
| **02** | AI Gateway Setup & Configuration | `workshop1_admin/labs/02_ai_gateway_setup.py` | 40 min |
| **03** | Rate Limits & Guardrails | `workshop1_admin/labs/03_rate_limits_guardrails.py` | 40 min |
| **04** | Genie Space — Admin Setup & Operating Model | `session2_technical/labs/04_genie_space_admin_setup.py` | 45 min |
| **05** | Usage Tracking & Cost Attribution | `workshop1_admin/labs/04_usage_tracking.py` | 35 min |
| **06** | Data Residency & Compliance Evidence | `workshop1_admin/labs/05_data_residency_compliance.py` | 35 min |

**Note on numbering:** Workshop 1 originally had labs 01–05. In the Session 2 sequence, Usage Tracking becomes Lab 05 and Data Residency becomes Lab 06 because Genie Space setup (new Lab 04) is inserted between Rate Limits and Usage Tracking. The underlying files have not changed — only their position in the session sequence.

---

## What Is New in This Folder

`04_genie_space_admin_setup.py` — a 45-minute lab that combines:
- Genie Space creation and configuration (drawing on the best of Workshop 2b Labs 1–2)
- A new "Operating Model" section introducing the Exploratory vs Certified framework
- A runnable Session 3 prerequisites checklist that outputs pass/fail for each item

This lab is positioned for **data engineers and platform engineers**, not business users. It focuses on admin setup, operating model decisions, and handoff readiness — not on using Genie to answer questions (that is Session 3).

---

## Dependencies Between Labs

```
Lab 01 (settings)
    └── Lab 02 (AI Gateway) — needs workspace settings from Lab 01
            └── Lab 03 (rate limits) — needs gateway endpoint from Lab 02
                    └── Lab 04 (Genie Space) — needs PT endpoint from Lab 02; tables from Lab 01 UC grants
                            └── Lab 05 (usage tracking) — needs AI Gateway usage data from Labs 02-04
                                    └── Lab 06 (compliance) — needs all prior labs complete
```

Labs must be run in order within a session. Each lab saves outputs (endpoint name, space ID, etc.) that later labs depend on.
