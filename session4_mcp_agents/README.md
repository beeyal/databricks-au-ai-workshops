# Session 4: Building AI Agents with MCP on Databricks

**Track:** Developer / Agent Builder
**Level:** 200 (guided, hands-on — no prior agent-building experience required)
**Duration:** ~2.5–3 hours
**Audience:** Data engineers, analysts, and ML engineers building their first governed agent on Databricks
**Format:** Hands-on coding labs with step-by-step UI guidance
**Slides:** [Building Agents, MCPs & Apps](https://docs.google.com/presentation/d/1vwV4xr3xFJ6ypqL0hKe-up7hH0rsGEvCraEfwGbQQ4M/edit) (Google Slides)

---

## Overview

This session teaches you to build a real AI agent by walking it through its whole lifecycle — one
lab per phase:

> **Build → Evaluate → Govern → Deploy → Improve**

You build the **AEMO Operations Agent**: a LangGraph ReAct agent that answers natural-language
questions about the Australian National Electricity Market (NEM) by calling three Databricks MCP
servers (Genie, Vector Search, UC Functions). You give it **Lakebase memory** so it handles
follow-up questions, **evaluate** its answers with LLM judges, **govern** it (residency, guardrails,
audit), **deploy** it as a React app, and close the loop by turning user feedback into new
evaluation cases.

Compared with the previous version of this session, this is deliberately **Level 200**: managed,
guided, fewer raw-plumbing detours, with a clear lifecycle spine and deeper coverage of evaluation
and memory.

### What is MCP?

Model Context Protocol (MCP) is an open standard that lets an agent discover and call tools provided
by external servers. On Databricks, MCP exposes Genie Spaces, Vector Search indexes, and Unity
Catalog Functions through one standard tool interface — no custom integration code per resource. The
agent discovers the available tools, picks one based on the question, calls it, and reasons over the
result (the ReAct loop) until it can answer.

### What you'll build

- A **LangGraph ReAct agent** on an in-region provisioned-throughput (PT) endpoint
- Wired to **three Databricks MCP servers**: UC Functions, Genie, Vector Search
- With **Lakebase short-term memory** for multi-turn conversations
- **Evaluated** with LLM-judge metrics (correctness, relevance, groundedness, no-hallucination)
- **Governed**: residency guardrail, AI Gateway rate limits, PII/safety guardrails, UC access
  controls, and a `system.access.audit` trail
- **Deployed** as a React app in Databricks Apps (SSO + service principal)
- **Continuously improved** via a human-in-the-loop feedback loop back into evaluation

---

## Getting started

1. **Facilitator (once, before the session):** run `setup/setup.py`. It creates the sample data, the
   Vector Search index, and the UC functions, and grants participants access. See the notebook header
   for prerequisites (an in-region PT endpoint that's `READY`, and the CSVs staged to DBFS or a UC Volume).
2. **Participants:** open the `labs/` folder and work through the notebooks **in order, 01 → 05**. Each
   one is a Databricks notebook — attach it to serverless (or a cluster), set the widgets at the top
   (the defaults match setup), and run the cells top to bottom. Every lab ends by pointing you to the next.
3. Lab 04 also builds and deploys the React app in `app/`.

**New to the terms?** *PT endpoint* = a provisioned-throughput model-serving endpoint that runs
in-region; *Genie* = natural-language-to-SQL over your tables; *MCP* = the open tool protocol the agent
uses to call Genie / Vector Search / UC Functions; *Lakebase* = managed Postgres that stores the agent's
conversation memory. Each is explained again where it first appears.

---

## Australia East residency (read this first)

This workshop exists because of a hard rule: **model calls must stay in Australia East**. AEMO
workloads must not route inference cross-geo.

| Rule | Detail |
|------|--------|
| **PT endpoint required** | The agent's LLM MUST be an in-region **provisioned-throughput (PT)** serving endpoint (default `au_east_llm_inregion`). The PT endpoint runs the model inside your workspace region. |
| **Pay-per-token forbidden** | Pay-per-token / Foundation Model API endpoints may route inference cross-geo and are **not permitted** as the agent's or the judge's LLM backend. |
| **All MCP servers in-region** | Genie, Vector Search, and UC Functions MCP servers are workspace-local and run in Australia East. |
| **Judge is in-region too** | The LLM-judge scorers in Lab 02/05 use the same PT endpoint (`databricks:/au_east_llm_inregion`) — the judge is an LLM call and obeys the same rule. |

### Residency reference table

| Component | Residency | Notes |
|-----------|-----------|-------|
| MCP — Genie Space server | In-region (AU East) | Safe for regulated data |
| MCP — Vector Search server | In-region (AU East) | Safe for regulated data |
| MCP — UC Functions server | In-region (AU East) | Safe for regulated data |
| LLM (PT endpoint) | In-region (AU East) | **Requires PT endpoint — pay-per-token forbidden** |
| MLflow tracing + evaluation | In-region (AU East) | Traces/evals stored in workspace-local MLflow |
| Lakebase (agent memory) | In-region (AU East) | Managed Postgres in the workspace region |
| Databricks Apps | In-region (AU East) | App container + OAuth handled in AU East |
| FMAPI Pay-Per-Token | **Cross-geo** | **Do not use as the agent's or judge's LLM backend** |

### Choosing the agent model (Australia East)

In the [Databricks region docs](https://learn.microsoft.com/en-us/azure/databricks/resources/feature-region-support), a `⥂` on a model means it **requires cross-geography routing** — it leaves the region, so it is off-limits for AEMO. In `australiaeast`:

| Model | In-region? | Use as the agent LLM? |
|-------|-----------|-----------------------|
| **`databricks-gpt-oss-120b`** | ✅ in-region (pay-per-token **and** provisioned throughput) | ✅ **Recommended** — reliable tool calling; ran all five labs clean |
| `databricks-gpt-oss-20b` | ✅ in-region | ✅ (lighter/faster) |
| Claude (Opus 4.6–4.8, Sonnet 4.5/4.6, Haiku 4.5) | ✅ in-region (Databricks security perimeter) | ⚠️ excellent at tools, but `databricks-langchain` currently mis-serializes the tool result for the Anthropic endpoint (`tool_result…id: Extra inputs are not permitted`) — prefer GPT-OSS until that's fixed |
| Llama 3.1/3.3/4, Qwen3/3.5, Claude Sonnet 5 / Fable 5 | ❌ `⥂` cross-geo | ❌ breaks residency (Llama also emitted malformed tool calls in testing) |
| Gemini, OpenAI GPT | ❌ global / ADI Services | ❌ breaks residency |

**Recommendation:** back the `au_east_llm_inregion` provisioned-throughput endpoint with **GPT-OSS-120B**, and use that same endpoint for the Lab 02/05 LLM judge.

---

## The lifecycle spine

Each lab is one phase. Lab 05 loops back to Lab 02, making the lifecycle a cycle:

```
   Build   →   Evaluate   →   Govern   →   Deploy   →   Improve
  (Lab 01)     (Lab 02)      (Lab 03)     (Lab 04)     (Lab 05) ──┐
     ▲                                                            │
     └───────────────────── loop back ───────────────────────────┘
```

---

## Lab sequence

| Lab | Title | File | Duration | Lifecycle phase |
|-----|-------|------|----------|-----------------|
| 01 | Build an MCP agent (+ Lakebase memory) | `labs/01_build_agent.py` | 40 min | **Build** |
| 02 | Evaluate the agent with LLM judges | `labs/02_evaluate_agent.py` | 35 min | **Evaluate** |
| 03 | Govern: guardrails, residency, audit | `labs/03_govern_agent.py` | 30 min | **Govern** |
| 04 | Deploy the React app | `labs/04_deploy_react_app.py` | 40 min | **Deploy** |
| 05 | Improve: human-in-the-loop feedback | `labs/05_improve_feedback_loop.py` | 30 min | **Improve** |

**Total: ~175 minutes of lab time** (~2.9 hours), plus short transitions between labs.

---

## Lab detail

### Lab 01 — BUILD: Your first MCP agent (with Lakebase memory)
**File:** `labs/01_build_agent.py`

Set up an MLflow experiment for tracing, configure the three MCP servers, and build a LangGraph
ReAct agent with `create_react_agent` + `ChatDatabricks` on the in-region PT endpoint. Run three
AEMO questions (Genie / Vector Search / UC Function routing). Then add **Lakebase short-term
memory**: create `app_memory.conversation_turns(session_id, turn_index, role, content, ts)`, wrap
the agent so each turn loads prior history and saves the new turn, and demonstrate a multi-turn
follow-up (*"...and what about NSW?"*). A Delta fallback keeps the lab running if Lakebase is not
provisioned.

### Lab 02 — EVALUATE: Measure quality with LLM judges
**File:** `labs/02_evaluate_agent.py`

Load the golden dataset from `../eval/golden_questions.jsonl`, wrap the agent as a `predict_fn`, and
run `mlflow.genai.evaluate()` with four LLM-judge scorers — **Correctness**, **RelevanceToQuery**
(answer quality), **RetrievalGroundedness**, and a custom **no-hallucination / faithfulness**
Guidelines judge — all pinned to the in-region PT endpoint. Read the aggregate metrics and drill
into per-question traces. Captures `lab02_eval_baseline` for later comparison.

### Lab 03 — GOVERN: Guardrails, residency, and audit
**File:** `labs/03_govern_agent.py`

Verify the agent's endpoint is PT (in-region) and document how to block the cross-geo pay-per-token
path. Configure **AI Gateway** (rate limits per service principal, usage tracking, inference
tables), **content guardrails** (PII, safety), **UC access controls** scoping the agent's service
principal to `workshop_au.aemo`, and query **`system.access.audit`** to correlate every MCP tool
call to an identity. Residency-forward throughout.

### Lab 04 — DEPLOY: Ship the agent as a React app
**File:** `labs/04_deploy_react_app.py`

Deploy the React app in `session4_mcp_agents/app/` (owned/provided; you don't write app code). Build
the frontend (`cd app/frontend && npm install && npm run build`), review `app/app.yaml` and its
resources (the `au_east_llm_inregion` endpoint with `CAN_QUERY`), deploy via **both** the Databricks
Apps UI **and** the CLI (`databricks apps deploy`), verify `/api/health`, and confirm SSO +
service-principal auth.

### Lab 05 — IMPROVE: Close the feedback loop
**File:** `labs/05_improve_feedback_loop.py`

Capture thumbs-up/down + free-text corrections from the deployed app into
`app_feedback.agent_feedback`, convert negatives into **new golden-dataset rows**, re-run the Lab 02
evaluation to measure improvement against the baseline, and refine the prompt / tool descriptions.
Explicitly closes the loop back to EVALUATE.

---

## Prerequisites

Simplified for Level 200 — the facilitator handles most setup.

| Prerequisite | Where | Required for |
|--------------|-------|--------------|
| Setup notebook run | `setup/setup.py` (loads `workshop_au.aemo` tables + grants) | All labs |
| PT endpoint READY (`au_east_llm_inregion`) | Serving (facilitator deploys) | All labs |
| Vector Search endpoint (`workshop_vs`) + index on `market_notices` | Facilitator | Labs 01, 02, 05 |
| Genie Space (optional) — set `genie_space_id` widget | Facilitator | Genie routing (labs still run without it) |
| Lakebase instance (optional) | Facilitator | Lab 01 memory (Delta fallback otherwise) |
| Databricks CLI + Node.js | Pre-installed in workshop env | Lab 04 only |

**No local installs on your device** — labs run in Databricks notebooks. Lab 04 uses the
pre-installed CLI/Node.js for app deployment.

### Config defaults (widgets)

| Widget | Default |
|--------|---------|
| `catalog` | `workshop_au` |
| `schema_aemo` | `aemo` |
| `pt_endpoint` | `au_east_llm_inregion` |
| `vs_endpoint` | `workshop_vs` |
| `genie_space_id` | *(optional)* |

---

## Packages

Pre-installed in the workshop cluster; installed at the top of each lab if needed:

```
databricks-langchain     # ChatDatabricks, DatabricksMCPServer, DatabricksMultiServerMCPClient
langgraph                # create_react_agent (ReAct loop)
mlflow>=3.0              # tracing + mlflow.genai.evaluate() LLM-judge scorers
psycopg2-binary          # Lakebase Postgres connection (Lab 01)
databricks-sdk           # WorkspaceClient, Lakebase credentials, Apps API
```

MCP server URLs (constructed in each lab from the workspace host):

```
UC Functions   : {HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}
Genie          : {HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}
Vector Search  : {HOST}/api/2.0/mcp/vector-search/{VS_ENDPOINT}/{CATALOG}/{SCHEMA_AEMO}
```

---

## Data

`workshop_au.aemo` sample tables (loaded by `setup/setup.py`):

| Table | Contents |
|-------|----------|
| `dispatch_intervals` | 5-min generator dispatch by DUID, fuel type, region |
| `spot_prices` | Regional Reference Price (`rrp`, $/MWh), demand, interchange |
| `market_notices` | AEMO bulletins incl. LOR1/LOR2/LOR3 events |
| `generator_registration` | DUIDs, station names, fuel types, registered capacity |
| `settlement_amounts` | Energy / FCAS / interconnector settlement in AUD |

UC Functions used as agent tools (registered by `setup/setup.py` in the `aemo` schema, exposed via
the UC Functions MCP server): `calculate_peak_demand`, `get_region_summary`, `lookup_duid_info`.

The golden evaluation set is `eval/golden_questions.jsonl` — 10 AEMO questions grounded in these
tables, with `inputs` (question) and `expectations` (`expected_facts` + a directional reference
answer).

---

## The React app

The deployed app lives in `session4_mcp_agents/app/` (React frontend + Python backend). It wraps the
same governed agent, uses Lakebase for multi-turn memory where enabled, exposes `/api/health`, and
runs in AU East as a managed service principal with `CAN_QUERY` on the in-region PT endpoint only.
Lab 04 builds and deploys it; you do not author app code.

---

## What you'll have by the end

- A working ReAct agent over three MCP servers, with conversation memory in Lakebase
- A repeatable evaluation harness with LLM judges and a growing golden dataset
- A governed, residency-compliant deployment (AI Gateway, guardrails, audit, least-privilege SP)
- A live React app your colleagues can use via SSO
- A closed feedback loop that turns real user corrections into measurable quality improvement

Everything runs in **Azure Australia East** on an **in-region PT endpoint** — no cross-geo inference.
