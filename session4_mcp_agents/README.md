# Session 4: Building Production AI Agents with MCP on Databricks

**Track:** Developer / Agent Builder
**Duration:** 3 hours
**Audience:** Data engineers, software engineers, and ML engineers building agentic applications on Databricks
**Format:** Hands-on coding lab with step-by-step UI guidance

---

## Overview

This workshop takes you from zero to a production-deployed AI agent in three hours. You will build the **AEMO Operations Agent** — a ReAct agent that combines three Databricks MCP server types to answer natural language questions about Australian electricity market operations, retrieve relevant regulatory documents, and run live computations.

The agent is deployed as a **Databricks App** with a Gradio UI, secured behind Databricks OAuth, with full MLflow tracing enabled and AI Gateway governing every LLM call.

### What is MCP?

Model Context Protocol (MCP) is an open standard that lets AI agents discover and call tools provided by external servers. In Databricks, MCP enables your agent to interact with Genie Spaces, Vector Search indexes, Unity Catalog Functions, and other resources through a standardised tool interface — without writing custom integration code for each.

When your agent receives a question, it queries the MCP server to discover available tools, selects the right one based on the question, calls it, and incorporates the result into its response. The agent reasons over this loop (ReAct pattern) until it has enough information to answer.

### What You Will Build

The AEMO Operations Agent integrates all three Databricks MCP server types:

| MCP Server | Role in the Agent |
|------------|------------------|
| **Genie Space MCP** | Translates natural language questions about spot prices, dispatch data, and settlement into SQL, executes them, and returns structured results |
| **Vector Search MCP** | Retrieves relevant passages from the AEMO Market Rules, NEM Procedures, and incident reports when the question requires regulatory or procedural context |
| **UC Functions MCP** | Runs deterministic computations — NEM pricing calculations, SAIDI/SAIFI formulas, load factor estimates — that should not be delegated to the LLM |

The finished agent is deployed as a Databricks App, so business users access it through a browser URL with full Databricks SSO — no API keys, no separate auth, no infrastructure management.

---

## Data Residency

All five Databricks MCP server types are confirmed available in the **Australia East** (`australiaeast`) region as of May 2026. Every component of this workshop — Genie Space, Vector Search, UC Functions, Model Serving, Databricks Apps — processes data in-region.

| Component | Residency | Notes |
|-----------|-----------|-------|
| Genie Space MCP server | In-region (AU East) | Safe for regulated data |
| Vector Search MCP server | In-region (AU East) | Safe for regulated data |
| UC Functions MCP server | In-region (AU East) | Safe for regulated data |
| LLM (PT endpoint) | In-region (AU East) | Requires PT endpoint — do not use Pay-Per-Token |
| Databricks Apps | In-region (AU East) | OAuth is handled within AU East |
| MLflow tracing | In-region (AU East) | Traces stored in workspace-local MLflow |

> The PT endpoint (`databricks-claude-haiku-4-5` or equivalent) must be deployed and in `READY` state before this workshop begins. Pay-Per-Token models are cross-geo and must not be used as the agent's LLM backend.

---

## Prerequisites

Complete the following before attending this workshop. Ask your facilitator if you need access to any of these.

| Prerequisite | Where to find it | Required for |
|-------------|-----------------|--------------|
| Session 5 Labs 01–03 completed (or equivalent Genie Code familiarity) | `session5_genie_code/labs/` | Lab 01 concepts build on Genie Code knowledge |
| UC Functions created in the workshop catalog | `session5_genie_code/labs/03_mcp_intro.py` | Lab 02 (UC Functions MCP discovery) |
| PT endpoint running (`databricks-claude-haiku-4-5` or name from your facilitator) | Machine Learning > Serving | All agent labs |
| AEMO data loaded | `setup/00_workspace_setup.py` with the AEMO section run | Labs 02–04 |
| Genie Space created and verified | `session3_lob/genie_config/aemo_genie_space_setup.py` | Lab 02 (Genie MCP) |
| `SELECT` on `workshop_au.aemo.*` | Granted by facilitator during setup | Labs 02–05 |

**Your device needs no local installs.** All labs run in Databricks notebooks or the Databricks Apps environment. The only exception is Lab 04, which uses the Databricks CLI for app deployment — the CLI is pre-installed in the workshop environment.

---

## Package Requirements

The following packages are used across the labs. They are pre-installed in the workshop cluster environment. If you are running this outside the workshop, install them in your notebook or project environment:

```
databricks-mcp>=0.2.0
databricks-langchain>=0.4.0
databricks-openai>=0.2.0
langgraph>=0.2.0
gradio>=4.0.0
mlflow>=2.14.0
```

Install with pip if needed:

```bash
pip install databricks-mcp databricks-langchain databricks-openai langgraph gradio mlflow
```

---

## Lab Sequence

| Lab | Title | Duration | Focus |
|-----|-------|----------|-------|
| 01 | Agent Architecture & MCP Ecosystem | 30 min | Concepts, UI exploration, tool discovery |
| 02 | Connecting to Databricks MCP Servers | 40 min | Tool discovery with all three server types |
| 03 | Building a Multi-Tool ReAct Agent | 45 min | LangGraph + MCP integration, MLflow traces |
| 04 | Deploying as a Databricks App | 45 min | `app.py`, `app.yaml`, UI deployment |
| 05 | Monitoring & Governing MCP Agents | 30 min | AI Gateway, audit logs, trace inspection |

**Total: ~190 minutes of lab time.** The remaining ~10 minutes covers transitions and setup verification between labs.

---

## Lab Detail

### Lab 01 — Agent Architecture & the MCP Ecosystem

**File:** `labs/01_agent_architecture_mcp.py`
**Duration:** 30 minutes
**Difficulty:** Beginner to Intermediate

Understand why MCP matters for production agents before writing any code. This lab combines a short conceptual walkthrough with hands-on UI exploration: browsing available MCP tools in the Databricks UI, tracing a sample Genie Space query end-to-end, and sketching the architecture you will build across Labs 02–04.

Key exercises:
- Navigate to the MCP tools explorer in the Databricks UI and identify the three server types
- Trace a Genie Space query manually in the UI and correlate it with the SQL that was generated
- Sketch the AEMO Operations Agent architecture (inputs, tool selection logic, outputs, deployment target)
- Discussion: when should an agent call a UC Function rather than let the LLM calculate? Three concrete examples from NEM operations

No agent code in this lab — the goal is to build the mental model before the implementation.

---

### Lab 02 — Connecting to Databricks MCP Servers

**File:** `labs/02_connecting_mcp_servers.py`
**Duration:** 40 minutes
**Difficulty:** Intermediate

Connect to all three MCP server types and call each tool directly (outside of an agent loop) to understand what they return. This lab is essential foundation work — agents that misbehave almost always have a tool integration issue, not a reasoning issue, and understanding the raw tool output makes debugging much faster.

Key exercises:
- Connect to the Genie Space MCP server and call `genie_query` with three AEMO questions; inspect the returned SQL and result set
- Connect to the Vector Search MCP server; call `vector_search_query` with two regulatory question strings; inspect the returned document chunks and relevance scores
- Connect to the UC Functions MCP server; call `execute_function` for `calculate_nem_spot_price` and `calculate_load_factor`; verify the outputs against known values
- Understand the tool manifest: name, description, input schema, output schema — all of which become the LLM's decision surface in Lab 03

Common issues in this lab:
- Genie Space not yet set up — see facilitator
- UC Function permissions — your user needs `EXECUTE` on the function, not just `SELECT` on the catalog
- Vector Search index not yet built — index creation takes 5–10 minutes; start it at the beginning of the lab

---

### Lab 03 — Building a Multi-Tool ReAct Agent

**File:** `labs/03_react_agent_langgraph.py`
**Duration:** 45 minutes
**Difficulty:** Intermediate to Advanced

Build the AEMO Operations Agent using LangGraph's ReAct pattern with the three MCP tools from Lab 02. By the end of this lab, the agent can answer multi-step questions that require combining a Genie query (structured data) with a Vector Search lookup (regulatory context) and a UC Function call (computation).

MLflow autolog is enabled from the first cell so every agent run generates a trace you can inspect in the MLflow UI.

Key exercises:
- Wire the three MCP tools into a LangGraph `ToolNode` and confirm tool definitions appear in the LLM's context
- Implement the ReAct loop: reason → select tool → call tool → observe result → reason again
- Test with three multi-step questions requiring at least two tools each:
  1. "What was the average spot price in VIC1 last Tuesday, and is that above or below the cap defined in the Market Rules?"
  2. "How many intervals did the Latrobe Valley region have estimated readings last week, and what's the load factor for those intervals?"
  3. "Show me the dispatch instructions for unit YWPS4 on the last market day and explain the curtailment procedure that applies."
- Inspect the MLflow trace for question 1: identify each tool call, its inputs, and the reasoning step that selected it
- Add a system prompt that grounds the agent in AEMO operational context and prevents it from answering questions outside the NEM domain

---

### Lab 04 — Deploying as a Databricks App

**File:** `labs/04_databricks_app_deployment.py`
**Duration:** 45 minutes
**Difficulty:** Intermediate

Package the agent from Lab 03 as a Databricks App with a Gradio UI. The deployed app is accessible to all workshop participants via a browser URL with Databricks SSO — no additional authentication setup required.

The lab covers both the Python application structure (`app.py`) and the Databricks App configuration (`app.yaml`), and walks through the UI-based deployment workflow in the Databricks workspace.

Key exercises:
- Structure `app.py`: Gradio `ChatInterface` wrapping the LangGraph agent, streaming responses enabled, session state for multi-turn conversation
- Write `app.yaml`: resource declarations for the PT endpoint and UC Functions the app needs, compute size (1 CPU recommended for this workload)
- Deploy via the Databricks Apps UI: navigate to Compute > Apps, create a new app, point at the `session4_mcp_agents/app/` directory
- Verify deployment: open the app URL, ask a test question, confirm the MLflow trace appears in the MLflow UI
- Access control: understand how the app inherits Databricks workspace permissions — participants with `CAN_USE` on the app can access it; the app's service principal handles MCP server calls

Common deployment issues:
- `app.yaml` resource name does not match the endpoint name in the workspace — names must match exactly
- Gradio version mismatch — pin to the version in `requirements.txt` in the app directory
- Cold start on first request — the app container initialises on first call; expect 15–30 seconds on first use

---

### Lab 05 — Monitoring & Governing MCP Agents

**File:** `labs/05_monitoring_governance.py`
**Duration:** 30 minutes
**Difficulty:** Intermediate

A deployed agent that nobody is watching is a governance gap. This lab covers the three layers of agent observability available in Databricks: AI Gateway usage metrics, `system.access.audit` events for MCP tool calls, and MLflow traces for per-request debugging.

Key exercises:
- Query `system.ai_gateway.usage` to see request counts, latency distribution, and token usage for the agent's PT endpoint since deployment
- Query `system.access.audit` to find MCP tool call events — correlate a specific Genie Space query back to the agent session that triggered it
- Open the MLflow experiment for the agent app and filter traces by duration > 10 seconds (these are the slow requests worth investigating)
- Inspect a trace where the agent made more than three tool calls — identify whether the extra calls were necessary or indicate a prompt improvement opportunity
- Add a `cost_centre` tag to all traces from the app (one-line change in `app.py`) so usage can be attributed for financial reporting

Discussion: when would you escalate from trace inspection to a full evaluation run? What would trigger a rollback of the deployed agent?

---

## What You Will Have Built by the End

By the end of this workshop, you will have:

- A production-quality AI agent that calls three different Databricks MCP server types in a single reasoning loop
- A deployed Databricks App accessible via browser with Databricks SSO — shareable with business users immediately
- Full MLflow tracing on every agent run, queryable via the MLflow UI and `system.access.audit`
- AI Gateway governance on the agent's LLM calls — rate limits, usage metrics, and cross-geo blocking in place
- An `app.py` + `app.yaml` pattern you can adapt for other domains and other MCP tool combinations

The AEMO Operations Agent code lives in `session4_mcp_agents/app/` and is ready to be copied to your organisation's repository as a starting point for a real deployment.

---

## Facilitator Notes

See `facilitator_notes/` for:
- Pre-workshop setup checklist (Genie Space verification, Vector Search index build, UC Function permissions)
- Known issues and mitigations for each lab
- Timing guidance: Labs 02 and 03 routinely run long if the Genie Space or Vector Search index is not pre-warmed
- Extension exercises for fast finishers in Labs 03 and 04

---

## AU East Residency Reference

Quick reference for questions that arise on the day. Status as of May 2026.

| Feature | Residency | Notes |
|---------|-----------|-------|
| MCP — Genie Space server | In-region (AU East) | All 5 MCP server types confirmed in-region |
| MCP — Vector Search server | In-region (AU East) | |
| MCP — UC Functions server | In-region (AU East) | |
| MCP — Model Serving server | In-region (AU East) | |
| MCP — UC AI Gateway server | In-region (AU East) | |
| LangGraph (open-source, runs in notebook) | In-region | Library runs on cluster/serverless; no external calls |
| MLflow tracing | In-region (AU East) | Traces stored in workspace-local MLflow tracking server |
| Databricks Apps | In-region (AU East) | App container runs in AU East; Gradio traffic stays in-region |
| FMAPI Pay-Per-Token | **Cross-geo** | **Do not use as the agent's LLM backend** |

---

## Next Steps After This Workshop

- Adapt the AEMO Operations Agent for your domain: swap the Genie Space, Vector Search index, and UC Functions for your own data and tools
- Review the AI Gateway configuration from Session 2 — all agent LLM calls should route through the gateway, not directly to the endpoint
- Consider adding an evaluation harness: use the `labs/solutions/` examples as your golden dataset and add MLflow `mlflow.evaluate()` to measure answer quality over time
- If your organisation uses Databricks Agent Bricks, the patterns from this workshop apply directly — Agent Bricks uses the same MCP tool integration under the hood
