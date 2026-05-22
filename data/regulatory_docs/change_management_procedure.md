# IT/OT Change Management Procedure

**Document ID:** PROC-CHG-008  
**Version:** 3.0  
**Effective Date:** 15 February 2025  
**Review Date:** 15 February 2026  
**Owner:** Head of Technology Services  
**Classification:** Internal

---

## 1. Purpose

This procedure governs the planning, approval, testing, and deployment of changes to IT and OT systems. Poorly managed changes are among the leading causes of unplanned outages on electricity networks globally. This procedure ensures that changes are assessed for risk, tested appropriately, scheduled to minimise customer impact, and reversible where possible.

The procedure applies the requirements of the Australian Energy Sector Cyber Security Framework (AESCSF) Change Management control domain and aligns with ITIL 4 Change Enablement practices adapted for critical infrastructure environments.

---

## 2. Scope

This procedure covers all changes to:

- IT systems (corporate applications, ERP, GIS, data platforms, cloud environments)
- OT systems (SCADA, EMS, RTUs, PLCs, protection relay firmware, AEMO interfaces)
- Network infrastructure (routers, firewalls, switches across all network zones)
- AI/ML models deployed in production environments
- Metering systems (AMI head-end, MSATS interfaces, NEM12 processing)

---

## 3. Change Categories

### 3.1 Standard Changes

Pre-approved, low-risk, repeatable changes that follow a documented procedure. Standard changes do not require CAB approval.

Examples: routine patch deployment from approved patch list, password resets, adding a user to an approved role, software version upgrades within a pre-approved change envelope.

### 3.2 Normal Changes

Changes that are not standard and not emergency. These must be assessed and approved by the Change Advisory Board (CAB).

Sub-categories:

| Sub-type | Risk Profile | CAB Approval Required |
|---|---|---|
| Low | Minor functional change; easy rollback; no customer impact | CAB email approval (48 hours) |
| Medium | Some customer impact possible; tested in lower environment | CAB standard meeting |
| High | Significant customer or OT impact; complex rollback | CAB standard meeting + technical review |

### 3.3 Emergency Changes

Changes required to restore service or address a critical security vulnerability. Emergency changes are approved by the CAB Chair (CISO or Head of Technology Services) and ratified at the next CAB meeting.

Emergency changes to OT systems additionally require verbal authorisation from the OT Security Manager and the Network Control Centre Supervisor before implementation.

---

## 4. Change Advisory Board (CAB)

### 4.1 Composition

- Head of Technology Services (Chair)
- OT Security Manager
- Network Control Centre Supervisor
- Asset Management representative (for OT changes)
- AEMO Interface Manager (for changes touching AEMO market systems)
- Business Representative from the affected area
- CISO (standing member; attends for High and Emergency changes)

### 4.2 Meeting Cadence

The CAB meets every Tuesday at 10:00 AM. The change freeze calendar and agenda are published to the IT Service Management (ITSM) portal every Friday. Change requests must be submitted by Thursday 5:00 PM for inclusion in the following Tuesday meeting.

---

## 5. Testing Requirements

### 5.1 IT Systems

All Medium and High changes to IT systems must be deployed and tested in a non-production environment that reflects the production configuration. Test results must be documented in the change record before CAB approval is sought.

### 5.2 OT Systems

Changes to OT systems must be tested in the OT simulation environment before deployment to production. The following additional requirements apply:

- Changes to SCADA configuration (RTU polling, alarm thresholds, control logic) require functional acceptance testing by a qualified Control Systems Engineer
- Changes to protection relay firmware require staged deployment (single relay at a time) with performance verification over a minimum 48-hour monitoring period
- Changes to AEMO market interfaces (MSATS, EMMS) require testing in AEMO's test environment (NEMLink SIT) with AEMO sign-off before production deployment

### 5.3 AI/ML Model Changes

Deployment of a new AI/ML model version or significant retraining of an existing model in a production environment is classified as a High change. Testing requirements include:

- Regression testing against a validated historical dataset to confirm model performance is equal to or better than the prior version
- Bias and fairness assessment (for models affecting customer outcomes)
- Rollback capability confirmed before deployment
- Post-deployment monitoring plan activated, with model output reviewed daily for the first 14 days

---

## 6. Blackout Windows

Changes to IT systems that could affect customer-facing services, SCADA, or AEMO interfaces are prohibited during the following periods unless they are Emergency changes:

| Period | Restriction | Rationale |
|---|---|---|
| Summer Peak (Dec 1 – Feb 28) | No High changes; Medium changes require CISO approval | Network near-capacity; outage risk highest |
| NEM Quarterly Settlement Processing | No AEMO interface changes (48 hours around settlement) | Settlement data integrity |
| Major Public Events | No changes affecting NCC visibility systems (48 hours) | Demand spike; heightened operational risk |
| AEMO Declared System Strength Events | No OT changes (duration of event) | AEMO directions take precedence |

The blackout window calendar is published quarterly on the ITSM portal and communicated to all change requestors via email.

---

## 7. Rollback Procedure

All High changes must include a documented, tested rollback procedure. The rollback procedure must:

- Specify the decision trigger for initiating rollback (e.g., service degradation detected within 30 minutes of deployment)
- Assign a named individual responsible for initiating rollback
- Confirm estimated rollback time
- Have been tested in the non-production environment

Rollback must be initiated without waiting for CAB approval if the deployed change causes a service outage affecting more than 200 customers or any OT system alarm condition.

---

## 8. Post-Implementation Review

Changes rated High and all Emergency changes require a post-implementation review (PIR) documented in the change record within 5 business days. PIRs for OT changes are shared with the OT Security Manager and, where applicable, with AEMO's Change Manager.

---

## 9. Compliance and Audit

Change records are retained for a minimum of 7 years in the ITSM system and are subject to review by the AER, ESV, and ASD during compliance audits. The Head of Technology Services reports change compliance metrics (emergency change rate, failed changes, blackout violations) to the Audit and Risk Committee quarterly.

---

*This procedure should be read alongside the Cyber Security Incident Response Procedure (PROC-SEC-003) and the Network Access Control Policy (POL-IAM-006). Queries to the IT Service Desk or the Head of Technology Services.*
