---
name: apra-compliance
description: APRA CPS 230 and CPS 234 compliance context for Databricks AI features — data residency classification, audit evidence templates, operational risk obligations, and regulatory safe patterns for Australian regulated entities
---

# APRA Compliance Context for Databricks AI

Use this skill when working with APRA-regulated entities (banks, insurers, superannuation funds, private health insurers) that must comply with CPS 234 (Information Security) and CPS 230 (Operational Resilience). Also applies to RSE Licensees subject to SPS 234 and SPS 230.

---

## Data Classification Reminder

Before applying any guidance, confirm the data classification of the information being processed:

| Classification | Examples | Databricks AI guidance |
|----------------|----------|----------------------|
| Public | Published pricing, regulatory filings already public | Any feature |
| Internal | Internal reports, non-customer operational data | In-region features preferred |
| Confidential | Customer PII, account data, financial positions | **In-region only; see table below** |
| Restricted / Secret | Authentication secrets, fraud models, prudential calculations | In-region only; Provisioned Throughput only; no logging to external systems |

---

## CPS 234 — Information Security

### Data Residency for AI Features (Australia East)

**In-region — safe for confidential and restricted data:**

| Feature | Notes |
|---------|-------|
| Genie Spaces (Chat mode) | Data stays in australiaeast |
| Genie Spaces (Agent mode) | Data stays in australiaeast |
| Genie Code (inline + panel) | Data stays in australiaeast |
| AI Gateway (all route types) | Proxy stays in-region; model must also be in-region |
| FMAPI Provisioned Throughput — Claude Sonnet 4.6 | In-region model deployment |
| FMAPI Provisioned Throughput — Claude Haiku 4.5 | In-region model deployment |
| FMAPI Provisioned Throughput — Llama 3.3 70B Instruct | In-region model deployment |
| Vector Search (qwen3-embedding-4b) | Embedding model hosted in australiaeast |
| UC Functions MCP | Execution on SQL warehouse in australiaeast |
| Genie MCP | Queries run in-region Genie Space |
| Databricks SQL MCP | Execution on warehouse in australiaeast |

**Cross-geo — do NOT use for confidential or restricted data:**

| Feature | Why it's cross-geo | Workaround |
|---------|-------------------|------------|
| FMAPI Pay-Per-Token (default) | Routes to nearest global region | Deploy Provisioned Throughput endpoint in australiaeast |
| AI Functions — `ai_query()` default | Uses global shared model pool | Point `ai_query()` at your PT endpoint explicitly |
| AI Functions — `ai_summarize()`, `ai_classify()`, `ai_extract()` | Built-in functions use global pool | Use `ai_query()` with PT endpoint |
| Knowledge Assistant (KA) | No committed AU East date as of May 2026 | Use Genie Spaces Agent mode instead |
| Multi-Agent Supervisor (MAS) | No committed AU East date as of May 2026 | Build with LangGraph + Databricks MCP |

> **Enforce residency:** Enable "Enforce data processing within workspace Geography" in the workspace admin console under AI & Machine Learning settings. This blocks cross-geo AI calls at the platform level.

### CPS 234 Audit Evidence Template

When asked to produce APRA CPS 234 audit evidence for an AI feature, include all of the following:

1. **Feature identification:** Full feature name and whether it is GA, Public Preview, or Private Preview
2. **Residency status:** In-region (✅) or cross-geo (❌), with date of verification
3. **Workspace geography enforcement:** Whether "Enforce data processing within workspace Geography" is enabled (provide screenshot or API verification)
4. **Access control:** How the feature is access-controlled (UC privileges, workspace admin, IP access lists)
5. **Payload logging:** Whether AI Gateway payload logging is enabled; the location of the logging table (must be in australiaeast)
6. **Audit trail query:** UC audit log query that surfaces model access events for this feature (see SQL below)
7. **Incident and change management:** Reference to the entity's IT change management procedure that covers model updates

### UC Audit Log Queries for AI Features

```sql
-- All Genie query events for a workspace (last 30 days)
SELECT
    event_time,
    user_identity.email           AS user_email,
    source_ip_address,
    request_params.space_id       AS genie_space_id,
    request_params.conversation_id,
    response.status_code
FROM system.access.audit
WHERE event_date >= CURRENT_DATE - INTERVAL 30 DAYS
  AND service_name = 'genieService'
  AND action_name IN ('genieCreateConversation', 'genieCreateMessage')
ORDER BY event_time DESC

-- All model serving endpoint calls (FMAPI + custom endpoints)
SELECT
    event_time,
    user_identity.email           AS user_email,
    request_params.endpoint_name  AS endpoint,
    response.status_code,
    response.error_message
FROM system.access.audit
WHERE event_date >= CURRENT_DATE - INTERVAL 30 DAYS
  AND service_name = 'modelServing'
  AND action_name = 'serveQueryEndpoint'
ORDER BY event_time DESC

-- AI Gateway requests (if gateway logging is enabled)
SELECT
    event_time,
    user_identity.email           AS user_email,
    request_params.route_name     AS gateway_route,
    request_params.endpoint_name  AS target_endpoint,
    response.status_code
FROM system.access.audit
WHERE event_date >= CURRENT_DATE - INTERVAL 30 DAYS
  AND service_name = 'aiGateway'
ORDER BY event_time DESC
```

---

## CPS 230 — Operational Resilience

### Effective Date
CPS 230 took effect **1 July 2025**. All APRA-regulated entities must comply. RSE Licensees are subject to SPS 230 (substantially identical requirements).

### AI as a Service Provider Dependency

Under CPS 230, where an APRA-regulated entity uses Databricks to support a critical operation, Databricks is a **material service provider (MSP)**. This triggers:

| Obligation | What it means in practice |
|------------|--------------------------|
| Service provider register | Databricks must appear on the entity's service provider register with criticality rating |
| Due diligence | Entity must conduct and document due diligence on Databricks AI features before production use |
| Contractual requirements | The Databricks agreement must contain CPS 230 Schedule 1 clauses (contact Databricks legal) |
| Change management | Model updates and feature changes are subject to the entity's IT change management process |
| Incident notification | Databricks service incidents affecting critical operations must be reported to APRA within prescribed timeframes |
| Business continuity | Entity must document how critical operations continue if Databricks is unavailable |
| Exit strategy | Entity must document and test the ability to exit the Databricks arrangement |

### AI Model Change Risk

Model updates are a specific risk under CPS 230. When a model is updated (e.g. Sonnet 4.5 → Sonnet 4.6), the model's outputs may change in ways that affect critical operations. Recommended controls:

1. **Pin model versions** where possible via Provisioned Throughput endpoint configuration
2. **Maintain a model registry** in MLflow tracking which model version is in production
3. **Run regression tests** (MLflow evaluate) before promoting a new model version
4. **Log all production inferences** via AI Gateway payload logging for retrospective review

### Audit Trail for AI (CPS 230 Operational Risk Evidence)

Every production AI call should be traceable. The chain of evidence should cover:

```
User request → AI Gateway log (entry point)
             → Unity Catalog audit log (access event)
             → MLflow trace (request, response, tool calls, latency)
             → Payload logging table (actual input/output text, if required)
```

MLflow trace query example:

```sql
-- Recent traces from a production endpoint
SELECT
    trace_id,
    client_request_id,
    request_time,
    execution_time_ms,
    status,
    request.messages[0].content    AS user_input_preview,
    response.choices[0].message.content AS model_output_preview
FROM mlflow.production.traces           -- adjust to your experiment/schema
WHERE request_time >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
ORDER BY request_time DESC
LIMIT 100
```

---

## Common APRA-related Questions and Answers

### "Can we use Genie for customer-facing interactions?"
Genie (both Spaces and Code) is designed as an internal analytics tool for employees. It is not certified for customer-facing deployments. For customer-facing AI, use Model Serving with an application layer.

### "Does Databricks keep our prompts for model training?"
No. Under the Databricks Enterprise agreement, customer data (including prompts and completions) is not used to train foundation models. Request the DPA (Data Processing Addendum) from your account team for contractual confirmation.

### "Can we use Claude (via FMAPI) for regulated data?"
Yes, provided you use a Provisioned Throughput endpoint in australiaeast and do not use Pay-Per-Token. The Anthropic model weights are hosted in Databricks infrastructure; your data does not go to Anthropic.

### "What is the data retention period for AI Gateway logs?"
Payload logging tables are Delta tables in your Unity Catalog. You control retention via Delta table properties and VACUUM. Default is no automatic deletion — configure retention to match your records management policy.

### "We need to demonstrate model explainability for credit decisions."
AI Gateway and MLflow Tracing provide full audit trails of inputs, outputs, and tool calls. For credit decision explainability (ASIC RG 271), you will additionally need to log feature contributions at inference time — discuss with your Databricks SA.

---

## Quick Reference: Approved Patterns for Regulated Workloads

```python
# ✅ APPROVED: Use PT endpoint in australiaeast for regulated data
from databricks.sdk import WorkspaceClient
from openai import OpenAI

w = WorkspaceClient()
client = OpenAI(
    api_key=w.config.token,
    base_url=f"{w.config.host}/serving-endpoints/your-pt-endpoint-au-east/v1",
)

# ✅ APPROVED: Route ai_query() to your PT endpoint, not the default
-- In a SQL notebook:
SELECT ai_query(
    'your-pt-endpoint-au-east',     -- your PT endpoint name
    'Summarise the following outage report: ' || report_text
) AS summary
FROM regulatory_reports
WHERE region = 'VIC' AND report_year = 2024

# ❌ NOT APPROVED for regulated data: default ai_summarize()
-- This routes to global shared pool (cross-geo)
SELECT ai_summarize(report_text) FROM regulatory_reports  -- DO NOT USE
```
