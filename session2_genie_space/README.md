# Session 2: Building the Best Genie Space

**Audience:** Data engineers, analysts, power users who will build and maintain Genie Spaces
**Duration:** 2.5 hours
**Format:** Workshop — slides + hands-on labs (UI-first throughout)
**Slide deck:** (content pulled from official Databricks AI/BI deck, slides 55-87, with AEMO additions) [Building the Best Genie Space — AEMO Edition](https://docs.google.com/presentation/d/1Kw-mwE8kVvc-j70mXzFOVnUAURVoYBaoDKIVF6MKFoU/edit)

---

## What this session covers

Following the official Databricks Genie best practices (docs + internal field guidance):

1. **Design principles** — the 5-table rule, topic selection, gathering representative questions
2. **The instruction hierarchy** — UC metadata → SQL Expressions → Golden Queries → Text (in that order)
3. **Data curation** — column descriptions, synonyms, entity matching, join configuration
4. **Benchmarking** — creating benchmark sets, running regression tests, interpreting results
5. **Monitoring and iteration** — the Monitor tab, feedback alerts, the improvement loop
6. **Rollout** — pilot → permissions → production

---

## The key architecture insight

> "Genie checks golden queries FIRST. If the user's question matches a golden query title exactly — the pre-written SQL runs directly, labeled Trusted. Only if there's no match does Genie generate SQL. This means golden queries are routing rules, not just examples."

---

## The instruction priority stack

| Priority | Method | When to use |
|---|---|---|
| 1 (Highest) | UC Metadata | Always — table/column descriptions, PK/FK, entity matching |
| 2 | SQL Expressions | KPIs, metrics, standard aggregations, common filters |
| 3 | Golden Queries | Complex multi-table patterns, specific phrasing examples |
| 4 (Last resort) | Text Instructions | Universal rules only — formatting, fiscal year, mandatory ranges |

---

## Lab sequence

| Lab | Title | Duration | Focus |
|---|---|---|---|
| 01 | Designing and Setting Up Your Genie Space | 40 min | Design principles, UC metadata, create via UI |
| 02 | The Instruction Hierarchy | 35 min | SQL Expressions, golden queries, joins, text instructions |
| 03 | Benchmarks, Monitoring & Iteration | 30 min |
| 04 | Monitoring Usage, Cost & Feedback | 25 min |
| 05 | Operating Model — Exploratory vs Certified | 20 min | Benchmark loop, Monitor tab, feedback alerts, rollout |

---

## Prerequisites

- Session 1 (Platform Administrators) complete
- AEMO tables loaded in Unity Catalog: `workshop_au.aemo.*`
- Genie feature enabled in workspace
- A Pro or Serverless SQL warehouse available

---

## Facilitator setup (run before session)

```
session2_genie_space/genie_config/aemo_space_config.py
```

Runs in ~5 minutes. Creates and validates a reference AEMO Genie Space so the facilitator can demonstrate a complete, well-configured space.

---

## Key limits to know

| Element | Limit |
|---|---|
| Tables per space | 30 (aim for 5 or fewer) |
| Total instruction items | 100 per space |
| Knowledge store snippets | 200 per space |
| Entity matching columns | 120 per space |
| Benchmark questions | 500 per space |
| UI throughput | 20 questions/min per workspace |

---

## Reference

- [Official Databricks Genie docs](https://docs.databricks.com/aws/en/genie)
- [Genie best practices](https://docs.databricks.com/aws/en/genie/best-practices)
- [Tune quality guide](https://docs.databricks.com/aws/en/genie/tune-quality)
- [Benchmarks](https://docs.databricks.com/aws/en/genie/benchmarks)
