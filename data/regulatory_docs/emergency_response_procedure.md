# Emergency Response Procedure — Major Network Outages

**Document ID:** PROC-OPS-011  
**Version:** 5.1  
**Effective Date:** 1 March 2025  
**Review Date:** 1 March 2026  
**Owner:** General Manager Network Operations  
**Classification:** Internal

---

## 1. Purpose

This procedure defines the structured response to major unplanned outage events on the electricity network, including activation of emergency operations, coordination with the Australian Energy Market Operator (AEMO), and community notification obligations. It supports compliance with the National Electricity Rules (NER) Chapter 4 (Power System Security) and the obligations of a Network Service Provider under the Electricity Safety Act.

A major outage is defined as any single event resulting in loss of supply to more than 500 customers for more than 2 hours, or any outage affecting life support customers, hospitals, or emergency services.

---

## 2. Roles and Responsibilities

| Role | Responsibility |
|---|---|
| Network Control Centre (NCC) Supervisor | First response coordination; AEMO notification; switching authorisation |
| On-Call Network Engineer | Field assessment and technical direction for restoration works |
| Emergency Response Manager | Overall incident command; stakeholder communications; media liaison |
| Customer Communications Team | Outage notifications; life support contact; AEMO portal updates |
| Asset Management Team | Specialist support for HV asset failures (transformers, cables, overhead lines) |
| Safety Officer | Ensuring public and worker safety around downed conductors and live assets |
| Executive On-Call | Activated for events >10,000 customers or media-significant incidents |

The Emergency Response Manager is the single point of command once an event is declared a major outage. Field crews report to the On-Call Network Engineer. All external communications are authorised by the Emergency Response Manager.

---

## 3. Activation Triggers

The Emergency Response Procedure is activated when any of the following thresholds are met:

- More than 500 customers off supply from a single cause
- Any fault on the transmission network (>66 kV)
- Any outage affecting a registered life support customer who cannot be reached for welfare check
- Any event involving conductor on ground in an accessible public area
- Sustained system frequency deviation outside 49.85–50.15 Hz as advised by AEMO
- AEMO direction to shed load under Administered Price Cap or Emergency Reserve Trader conditions

---

## 4. Response Phases

### Phase 1: Detection and Initial Response (0–30 minutes)

1. NCC SCADA/DMS alarm triggers; NCC Supervisor confirms extent of outage
2. NCC Supervisor contacts On-Call Network Engineer and dispatches field crew
3. NCC Supervisor calls AEMO Participant Operations if any transmission asset is involved or if system security is affected
4. Customer Communications Team activates outage notification system; life support customers contacted first
5. Emergency Response Manager paged automatically via on-call roster system

### Phase 2: Assessment and Escalation (30 minutes – 2 hours)

1. Field crew provides initial fault assessment via the Network Operations mobile app
2. Emergency Response Manager assesses need for Executive On-Call activation
3. Customer Communications Team publishes outage to company website and electricity network app; estimated restoration time (ERT) communicated
4. Mutual aid activation considered if the event exceeds in-house crew capacity
5. NCC reviews system topology for switching alternatives to restore supply to healthy feeders

### Phase 3: Restoration (2 hours onwards)

1. NCC Supervisor directs isolation of faulted section and back-feed switching via approved switching sheets
2. All switching on HV assets requires written or recorded verbal authorisation from NCC (no autonomous switching)
3. Restoration progress updated to customer portal and media every 60 minutes
4. Life support customers with ERT >4 hours offered welfare check and referral to local council support

### Phase 4: Closeout and Review

1. All supply restored; NCC Supervisor confirms outage closed in NMS
2. Emergency Response Manager initiates post-event review within 5 business days for events >2,000 customers
3. SAIDI/SAIFI data recorded in asset management system for AER annual performance reporting
4. Reportable outages submitted to AER via the Service Target Performance Incentive Scheme (STPIS) portal within 10 business days

---

## 5. AEMO Coordination

### 5.1 Routine Notifications

For planned outages on transmission-connected equipment, AEMO must be notified at least 2 business days in advance via the AEMO Outage Scheduler. For unplanned outages, the NCC Supervisor notifies AEMO Participant Operations by phone within 30 minutes and follows up with a formal Constraint Advice if system security is affected.

### 5.2 System Security Directions

If AEMO issues a Direction under NER Rule 4.8.9 to curtail load or alter network configuration, the NCC Supervisor must implement the Direction as instructed. Any technical inability to comply must be communicated to AEMO immediately.

### 5.3 Low Reserve Notices

When AEMO issues a Lack of Reserve Level 1, 2, or 3 notice, the NCC Supervisor activates the demand management protocol and contacts large industrial customers enrolled in the Demand Response Mechanism.

---

## 6. Community Notification Thresholds

| Affected Customers | Notification Actions |
|---|---|
| >100 customers | Outage notification published to website and app |
| >500 customers | Media release issued; social media update; council advised |
| >2,000 customers | Executive notification; State Emergency Management (EMV/SASES) advised |
| >10,000 customers | Ministerial briefing by General Manager; AER notified; joint media statement with AEMO |
| Life support affected | Immediate individual contact regardless of customer count |

---

## 7. Escalation to State Emergency Management

Where a major network outage is caused by or coincides with a natural disaster (e.g., bushfire, flood, severe storm), the Emergency Response Manager coordinates with the relevant State Emergency Management agency (Emergency Management Victoria, SA State Emergency Service, or equivalent). Joint public communications are coordinated through the Emergency Response Manager and the agency's Public Information Officer.

---

## 8. Training and Exercises

The Emergency Response procedure is exercised via a desktop simulation twice per year and a full operational exercise once per year involving AEMO, emergency services, and council representatives. Post-exercise debrief outcomes are incorporated into the next procedure review.

---

*This procedure is reviewed annually, after any major activation, and whenever AEMO changes relevant market rules. Queries to the General Manager Network Operations or the Network Control Centre.*
