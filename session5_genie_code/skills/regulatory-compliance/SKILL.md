---
name: regulatory-compliance
description: Australian energy sector regulatory context for Databricks AI features — SOCI Act 2018 critical infrastructure obligations, AER reporting requirements, AESCSF cyber security framework, Privacy Act 1988, data residency classification, and audit evidence patterns for AEMO, APA, and DNOs
---

# Australian Energy Sector Regulatory Compliance

Use this skill when working with energy sector entities governed by the **SOCI Act 2018** and **AER** regulatory framework: AEMO, APA Group, AusNet, Ausgrid, Endeavour Energy, and other DNOs, TNSPs, or market participants.

> **APRA does not apply to energy sector entities.** APRA governs banks, insurers, and superannuation funds. AEMO, APA, and Australian DNOs are regulated under the SOCI Act, NER, and state energy legislation — not APRA CPS 230/234.

---

## Applicable Regulatory Frameworks

| Framework | Body | What it covers |
|-----------|------|---------------|
| SOCI Act 2018 (Cth) | Home Affairs / ASD | Critical infrastructure protection; sector-specific risk management programs (CIRMP) mandatory from Aug 2024 |
| AESCSF | AEMO + ASD | Australian Energy Sector Cyber Security Framework — 4-tier maturity model; applies to all NEM participants |
| Privacy Act 1988 (Cth) | OAIC | APPs covering NMI/customer data; Australian Privacy Principles 6, 11 key for meter data |
| NER / NERL | AER | National Electricity Rules and Retail Law; Chapter 7 data retention (7 years) |
| AER STPIS | AER | Service Target Performance Incentive Scheme — reliability reporting obligations for DNOs |
| Notifiable Data Breaches | OAIC | Mandatory notification for eligible data breaches involving personal information |

---

## Data Classification for AI Features

| Classification | Examples | Databricks AI guidance |
|----------------|----------|----------------------|
| Public | Published market data, AEMO NEMWEB data | Any feature |
| Internal | Operational reports, non-customer network data | In-region features preferred |
| Sensitive | Customer NMI data, settlement amounts, dispatch positions | **In-region only — see table below** |
| Critical / Restricted | SCADA feeds, control system data, security incident data | In-region only; PT endpoints only; no external payload logging |

---

## Data Residency (Azure Australia East)

**In-region — safe for sensitive and critical data:**

| Feature | Notes |
|---------|-------|
| Genie Spaces (Chat + Agent mode) | Queries stay in australiaeast |
| Genie Code (inline + panel) | Model and data stay in australiaeast |
| AI Gateway (all route types) | Proxy in-region; target model must also be in-region |
| FMAPI Provisioned Throughput — Claude Haiku 4.5 | In-region model deployment |
| FMAPI Provisioned Throughput — Claude Sonnet 4.6 | In-region model deployment |
| Vector Search (qwen3-embedding-4b) | Embedding model in australiaeast |
| UC Functions MCP | Execution on SQL warehouse in australiaeast |
| Databricks SQL MCP | Execution on warehouse in australiaeast |

**Cross-geo — do NOT use for sensitive or critical data:**

| Feature | Why it's cross-geo | Workaround |
|---------|-------------------|------------|
| FMAPI Pay-Per-Token (default) | Routes to nearest global region | Deploy PT endpoint in australiaeast |
| `ai_summarize()`, `ai_classify()`, `ai_extract()` | Use global shared model pool | Use `ai_query()` pointed at your PT endpoint |
| Knowledge Assistant (KA) | No committed AU East date as of Jun 2026 | Use Genie Spaces Agent mode instead |
| Multi-Agent Supervisor (MAS) | No committed AU East date as of Jun 2026 | Build with LangGraph + Databricks MCP |

> **Enforce residency:** Enable "Enforce data processing within workspace Geography" in Account Console → Workspaces → Security and Compliance. This blocks cross-geo AI calls at the platform level — mandatory for SOCI Act CIRMP compliance.

---

## SOCI Act 2018 — Critical Infrastructure Risk Management

### CIRMP Obligations (from Aug 2024)

Responsible entities for critical infrastructure assets (electricity generation > 30 MW, major network assets) must maintain a **Critical Infrastructure Risk Management Programme** covering:

1. **Asset identification:** Register all critical assets in the CISC portal
2. **Risk identification and mitigation:** Document AI/data platform dependencies as part of supply chain risk
3. **Incident reporting:** Notify Home Affairs of cyber security incidents within:
   - **12 hours** for significant cyber security incidents (immediate impact on operations)
   - **72 hours** for other reportable cyber security incidents
4. **Annual review:** CIRMP must be reviewed annually and board-approved

### Databricks as a Critical Dependency

If Databricks supports operational systems (e.g. market settlement analysis, dispatch forecasting, outage management), it is a **critical dependency** under SOCI Act CIRMP:
- Document Databricks in the supply chain risk section of your CIRMP
- Maintain a business continuity plan for Databricks unavailability
- Include Databricks model/feature updates in your change management process
- Test recovery from a Databricks outage at least annually

---

## Privacy Act 1988 — NMI and Customer Data

### APP 6 — Use and Disclosure

NMI-level interval data is personal information when it can identify an individual customer. Under APP 6:
- Use it only for the purpose for which it was collected (metering, billing, network planning)
- Do not use for AI model training without explicit consent
- Do not include in AI prompts sent to external models — use PT endpoints in australiaeast

### APP 11 — Security

Take reasonable steps to protect personal information including:
- Logging all access to NMI data tables via Unity Catalog audit logs
- Applying UC column-level security masks to PII columns in production tables
- Retaining AI Gateway payload logs (if enabled) in australiaeast only
- Setting data retention consistent with NER Chapter 7 (7 years for market data)

---

## AER STPIS — Reliability Reporting

Typical targets for urban networks (verify against your current AER revenue determination):

| Metric | Typical urban target | Penalty trigger |
|--------|---------------------|----------------|
| SAIDI (unplanned) | < 25 min/customer/year | Exceeding target by > 5% |
| SAIFI (unplanned) | < 1.0 events/customer/year | Exceeding target by > 5% |
| CAIDI | < 30 min average | Derived from SAIDI/SAIFI |

Major Event Days (MEDs) are excluded from STPIS calculations. The MED threshold is network-specific.

---

## UC Audit Log Queries for AI Features

```sql
-- All Genie query events (last 30 days)
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

-- All PT endpoint calls
SELECT
    event_time,
    user_identity.email           AS user_email,
    request_params.endpoint_name  AS endpoint,
    response.status_code
FROM system.access.audit
WHERE event_date >= CURRENT_DATE - INTERVAL 30 DAYS
  AND service_name = 'modelServing'
  AND action_name = 'serveQueryEndpoint'
ORDER BY event_time DESC

-- NMI table access (Privacy Act audit trail)
SELECT
    event_time,
    user_identity.email           AS user_email,
    request_params.table_full_name AS table_accessed,
    action_name
FROM system.access.audit
WHERE event_date >= CURRENT_DATE - INTERVAL 30 DAYS
  AND service_name = 'unityCatalog'
  AND request_params.table_full_name LIKE '%meter%'
ORDER BY event_time DESC
```

---

## Common Questions

### "Can we use Genie for NMI-level customer data?"
Yes, provided: (1) Genie is in an AU East workspace with geography enforcement ON, (2) the underlying tables have UC column masks on PII columns, and (3) you are not routing through Pay-Per-Token. Genie Spaces in australiaeast are in-region.

### "Does Databricks use our prompts or data for model training?"
No. Under the Databricks Enterprise agreement, customer data including prompts and completions is not used to train foundation models. Request the DPA from your account team.

### "We need to evidence data residency for our CIRMP."
Three artefacts: (1) UC audit log showing model serving events in-region, (2) screenshot of geography enforcement setting ON in Account Console, (3) PT endpoint status showing `australiaeast` region. Together these constitute residency evidence for a CIRMP review.

### "What is the retention period for AI Gateway payload logs?"
Payload logging tables are Delta tables in your Unity Catalog. Set retention to match NER Chapter 7 (7 years for market participant records) via `TBLPROPERTIES` and `VACUUM`, or your records management policy, whichever is longer.
