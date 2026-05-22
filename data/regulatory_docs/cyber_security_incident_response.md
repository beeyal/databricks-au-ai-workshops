# Cyber Security Incident Response Procedure

**Document ID:** PROC-SEC-003  
**Version:** 4.0  
**Effective Date:** 1 February 2025  
**Review Date:** 1 February 2026  
**Owner:** Chief Information Security Officer  
**Classification:** Restricted

---

## 1. Purpose

This procedure defines the end-to-end response to cyber security incidents affecting IT and OT systems. It aligns with the Australian Signals Directorate (ASD) Essential Eight Maturity Model, the Australian Energy Sector Cyber Security Framework (AESCSF), and the obligations under the Security of Critical Infrastructure Act 2018 (Cth) (SOCI Act). Timely and structured response limits operational impact, protects customer data, and fulfils mandatory notification obligations.

---

## 2. Incident Severity Classification

| Level | Name | Description | Initial Response Time |
|---|---|---|---|
| P1 | Critical | Active compromise of OT/SCADA systems; ransomware with network spread; confirmed data exfiltration of Restricted data | Immediate — within 15 minutes |
| P2 | High | Suspected breach of IT network perimeter; malware detected on corporate systems; unauthorised access to NMI data | Within 1 hour |
| P3 | Medium | Phishing campaign targeting staff; anomalous access patterns; failed intrusion attempt on externally facing systems | Within 4 hours |
| P4 | Low | Policy violation (e.g., unapproved USB use); suspicious email quarantined; minor vulnerability discovered | Within 1 business day |

---

## 3. Detection and Initial Assessment

### 3.1 Detection Sources

Incidents may be detected through:

- Security Information and Event Management (SIEM) platform alerts
- OT-specific intrusion detection system (IDS) monitoring SCADA and EMS traffic
- ASD ACSC threat intelligence feeds
- AEMO Cyber Security Operations Centre notifications
- Employee reports via the security incident hotline or email alias
- Third-party managed security service provider (MSSP) alert triage

### 3.2 Initial Triage

Upon receiving an alert, the Security Operations Centre (SOC) analyst performs an initial triage within 15 minutes to determine:

- Whether the event constitutes a genuine incident or a false positive
- The likely affected systems and data types
- Whether OT systems, AEMO market interfaces, or customer data are potentially involved
- The initial severity level

---

## 4. Escalation Paths

### 4.1 Internal Escalation

**P1/P2 incidents — immediate notifications required:**

1. SOC Lead (primary on-call)
2. Chief Information Security Officer (CISO)
3. Chief Digital & Information Officer (CDIO)
4. OT Security Manager (if OT systems are involved)
5. Chief Executive Officer (if P1 or likely regulatory notification required)
6. Legal Counsel (for breach notification assessment)

**P3/P4 incidents:**

Escalation to SOC Lead only; CISO briefed at next business day unless the incident escalates.

### 4.2 Notification to ASD / ACSC

Under the SOCI Act, the company is a responsible entity for critical infrastructure assets (Category D — electricity). The following notification obligations apply:

- **Significant cyber security incident:** Report to the ACSC within **12 hours** of becoming aware
- **Other reportable incident:** Report to the ACSC within **72 hours**
- Notifications must be made via the ACSC 24/7 hotline (1300 CYBER1) or ReportCyber portal

The CISO is the nominated contact for all ACSC notifications. In the CISO's absence, the CDIO assumes this responsibility.

### 4.3 AEMO Coordination and Market Suspension Triggers

Incidents affecting systems that interface with AEMO — including MSATS, EMMS, web services, or the Energy Web Portal — must be escalated to the AEMO Participant Operations team immediately.

**Market suspension triggers:** If the incident results in or threatens to result in any of the following, the CISO must directly contact AEMO Participant Operations to initiate market protocols:

- Inability to receive or process five-minute dispatch instructions
- Compromise of metering data submission systems affecting NEM settlement
- Suspected manipulation of bid or offer data submitted to AEMO
- Loss of visibility of HV network real-time state for AEMO's system security assessment

AEMO Participant Operations: +61 3 9648 9748 (24/7)

### 4.4 Office of the Australian Information Commissioner (OAIC)

If the incident constitutes an Eligible Data Breach under the Privacy Act 1988 (Cth) Part IIIC (Notifiable Data Breaches scheme), the Privacy Officer must be engaged within 2 hours of P1/P2 incident confirmation. The 30-day assessment clock begins on the day the entity becomes aware of reasonable grounds to suspect a breach.

---

## 5. Containment, Eradication, and Recovery

### 5.1 Containment Principles

Network segmentation between IT and OT is the primary containment tool. Under no circumstances should an incident responder disable OT safety systems (protection relays, emergency shutdown controllers) as a containment measure without direct authorisation from the OT Security Manager and Network Control Centre Supervisor.

### 5.2 Evidence Preservation

Before any remediation action is taken, digital forensic images of affected systems must be captured where operationally feasible. Chain of custody must be maintained using the Forensic Evidence Form (SEC-F-001).

### 5.3 Recovery Approval

Return to operations of any SCADA, EMS, or AEMO-connected system after a P1 incident requires written sign-off from the CISO, OT Security Manager, and Network Control Centre Manager.

---

## 6. Post-Incident Review

All P1 and P2 incidents require a formal post-incident review (PIR) within 10 business days. The PIR report must be presented to the Audit and Risk Committee and retained for a minimum of seven years in accordance with record-keeping obligations under the Electricity Safety Act.

---

## 7. Testing

This procedure must be exercised via tabletop simulation at least annually, with a live OT incident scenario conducted every two years. Results are reported to the Board Risk Committee.

---

*This procedure is classified Restricted. Distribution is limited to the CISO, SOC staff, OT Security team, Executive Leadership Team, and Legal Counsel. Printed copies must be destroyed by cross-cut shredding when superseded.*
