# Workshop 2b: Genie Spaces for Business Users — Australian Regulated Industries

**Track:** Analyst / Business Stakeholder  
**Duration:** 3 hours  
**Audience:** Business analysts, data analysts, reporting leads, operational managers who work with data but do not write code

---

## Overview

This workshop introduces business users to Genie Spaces — the Databricks feature that lets you ask questions about your data in plain English and receive accurate, verifiable answers backed by SQL queries running directly in your data platform.

Unlike AI chatbots that generate text responses from the internet, Genie Spaces run real queries against your actual data, in your Databricks workspace, in the Australian East region. Every answer comes with the SQL that produced it, so you can verify results and understand exactly what was computed.

The workshop uses synthetic National Electricity Market (NEM) energy data that reflects the structure of real data used by Australian electricity network operators, retailers, and market participants.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Role | At minimum, Viewer on the workshop Genie Space. Data Engineer role if participating in Labs 2–3. |
| Access | `CAN_USE` on the `Workshop — Energy Analytics` Genie Space (granted during setup) |
| Workspace | UC-enabled, Australia East |
| Prior knowledge | No coding required. Familiarity with data concepts (tables, columns, filters) is helpful but not required. |
| Device | A modern browser (Chrome or Edge recommended). No software to install. |

If you cannot access the Genie Space when you log in, contact your facilitator — access is granted at the workspace level and takes under a minute to fix.

---

## What You Will Learn

By the end of this workshop, you will be able to:

1. Ask natural language questions in Genie Spaces and interpret the results
2. Verify an answer by reviewing the underlying SQL query
3. Refine questions iteratively when the first answer is not quite right
4. Understand what makes data "Genie-ready" and how to work with your data team to improve it
5. Identify when to trust a Genie answer and when to escalate for human review — critical for regulatory reporting
6. Understand the data residency posture of Genie Spaces (in-region for AU East)
7. Use AI SQL functions responsibly, with awareness of which functions process data in-region vs. cross-geo

---

## Labs

### Lab 01 — Genie Spaces Fundamentals

**File:** `labs/01_genie_spaces_intro.sql`  
**Duration:** 35 minutes  
**Difficulty:** Beginner

Open the `Workshop — Energy Analytics` Genie Space and start asking questions. You will learn the basic interaction model: ask a question, review the SQL, verify the result, ask a follow-up. Work through a series of guided questions about NEM interval meter data — daily consumption, peak demand periods, data quality flags — and practice refining questions when the first result needs adjustment.

Key exercises:
- Ask your first question: total energy consumption per NMI
- Follow-up: filter to a specific date range
- Interpret an estimated-reading flag: "Which meters have more than 5% estimated intervals this month?"
- View the SQL behind an answer and explain what it does
- Deliberately ask a question the space cannot answer (data not in scope) — understand why

---

### Lab 02 — Curating Data for Genie

**File:** `labs/02_curating_data_for_genie.py`  
**Duration:** 30 minutes  
**Difficulty:** Intermediate (facilitator-led for business analyst track; hands-on for data analyst track)

The quality of Genie Spaces answers depends on the quality of your data's metadata: column descriptions, table descriptions, and the certified table badge in Unity Catalog. In this lab, you will add column comments to the NEM meter tables and see directly how this changes (improves) the questions Genie can answer. This lab bridges the gap between business users and the data platform team.

Key exercises:
- Add a column comment to `interval_number` explaining that it represents 30-minute intervals numbered 1–48 per day
- Observe how Genie's answer to "what time of day had peak consumption?" improves
- Review the certified table badge and understand how it signals trust to Genie
- Draft a set of column descriptions for `nmi_registry` that a business user would write and a data engineer would implement

---

### Lab 03 — Genie Quality and Trust

**File:** `labs/03_genie_quality.py`  
**Duration:** 25 minutes  
**Difficulty:** Intermediate

Learn to evaluate whether a Genie answer is trustworthy enough for a given use case. For operational queries (informal decision support), a quick review of the SQL is sufficient. For regulatory reporting, the SQL must be reviewed and approved by a data analyst before the output is submitted. This lab walks through a decision framework for different trust levels and common failure patterns.

Key exercises:
- Run four queries and classify each as "trust immediately", "review before use", or "escalate"
- Identify three common Genie failure modes: ambiguous question, missing data, wrong aggregation level
- Write a set of Genie Space instructions that improve answer quality for common queries
- Discuss: what does your organisation's current review process look like for AI-generated analytics?

---

### Lab 04 — AI Functions in a Regulated Context

**File:** `labs/04_ai_functions_regulated.sql`  
**Duration:** 25 minutes  
**Difficulty:** Intermediate

Databricks SQL includes AI functions like `ai_query()`, `ai_classify()`, `ai_extract()`, and `ai_gen()`. These enable AI-powered transformations directly in SQL queries. However, the residency posture of these functions depends critically on which endpoint they call. This lab covers the safe pattern for regulated environments and shows how to use AI functions for practical regulatory analytics tasks.

**Read this before starting the lab:**

> `ai_query()` can call either a Provisioned Throughput endpoint (in-region, safe for regulated data) or a Pay-Per-Token external endpoint (cross-geo, **not safe for regulated data**). The difference is determined by the endpoint name you specify. In this workshop, all AI function exercises use the `workshop-pt-endpoint` Provisioned Throughput endpoint. Do not change the endpoint name in any exercise cell.

Key exercises:
- Use `ai_classify()` to categorise compliance events as High/Medium/Low severity
- Use `ai_extract()` to pull structured fields from free-text compliance event descriptions
- Use `ai_query()` with the PT endpoint to summarise a set of regulatory events
- Compare the output using the PT endpoint vs. what would happen with the cross-geo endpoint (discussed, not run)

---

## What You Will Have Built by the End

By the end of this workshop, you will have:

- Hands-on experience asking natural language questions in Genie Spaces against real energy data structures
- A practical framework for deciding when to trust a Genie answer vs. when to verify it — directly applicable to regulatory reporting workflows
- A set of column descriptions and Genie Space instructions you can take back to your data team
- An understanding of the data residency posture of every Genie feature you used today
- Familiarity with AI SQL functions and their safe usage pattern in critical infrastructure regulated environments

---

## Data Residency for Business Users

Genie Spaces process all queries — including the natural language question you type and the SQL it generates — within the **Australia East** region. The following applies to every feature used in this workshop:

| What you do | Where it's processed |
|-------------|---------------------|
| Type a question in Genie Spaces | AU East (in-region) |
| View the SQL behind an answer | AU East (the SQL ran in your workspace) |
| Run an `ai_classify()` via PT endpoint | AU East (in-region) |
| Run an `ai_query()` via Pay-Per-Token | **Cross-geo — do not use for regulated data** |

Your facilitator will flag any exercise that touches the cross-geo boundary before you run it.

---

## Genie Spaces — Quick Tips

**Asking better questions:**
- Include time periods explicitly: "last 30 days", "July 2024", "financial year 2025"
- Name the metric you want: "total kWh", "count of NMIs", "average consumption"
- Say what level of detail you need: "per NMI", "per day", "per NEM region"

**When to refine a question:**
- If Genie returns "I don't know" — the data may not be in this space, or the question is ambiguous
- If the numbers look wrong — click "View SQL" and check whether the filter or grouping matches your intent
- If the date range is wrong — rephrase with explicit dates rather than relative terms like "recently"

**When to verify with your data team:**
- Before including Genie output in a regulatory submission or board report
- When the SQL contains a complex multi-table join you did not expect
- When the answer changes significantly after you rephrase a question that should be equivalent
