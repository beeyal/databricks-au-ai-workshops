# Data Classification Policy

**Document ID:** POL-DATA-002  
**Version:** 3.4  
**Effective Date:** 15 January 2025  
**Review Date:** 15 January 2026  
**Owner:** Chief Information Security Officer  
**Classification:** Internal

---

## 1. Purpose

This policy defines the data classification framework for all information assets held or processed by the company. Correct classification ensures that data is protected in proportion to its sensitivity, supports compliance with the Privacy Act 1988 (Cth), the National Electricity Rules (NER), and the Australian Energy Sector Cyber Security Framework (AESCSF), and enables appropriate access controls across IT and OT environments.

---

## 2. Classification Tiers

### 2.1 Restricted

**Definition:** Information whose unauthorised disclosure would cause serious harm to the company, customers, the national electricity market, or national security.

**Handling requirements:**
- Encrypted at rest (AES-256 minimum) and in transit (TLS 1.2+)
- Access granted on a need-to-know basis only, with individual accountability logging
- Must not be processed by unapproved cloud services or AI tools
- Physical documents must be stored in locked cabinets and destroyed by cross-cut shredding
- Data transfers require dual authorisation and audit trail

**Examples:**
- Network topology diagrams and SCADA system architecture documents
- NEM12 interval meter data linked to a National Metering Identifier (NMI)
- Customer financial information and payment card data
- Vulnerability assessments, penetration test results
- Critical infrastructure protection (CIP) asset registers
- Credentials, certificates, and cryptographic keys

**NEM12 classification note:** All NEM12 files containing half-hourly or five-minute interval energy consumption data are classified as Restricted by default, regardless of whether the NMI is pseudonymised, due to the potential for re-identification when correlated with address records. Aggregated load data with more than 100 NMIs may be downgraded to Internal upon written approval from the Privacy Officer.

### 2.2 Internal

**Definition:** Information intended for use within the company that, if disclosed externally, could cause moderate reputational, commercial, or operational harm.

**Handling requirements:**
- Stored on company-approved systems only
- Must not be shared externally without authorisation from the relevant business owner
- Email transmission permitted within the corporate domain; external email requires encryption
- May be processed by approved cloud platforms subject to data residency controls

**Examples:**
- Network performance reports (SAIDI, SAIFI statistics) prior to AER publication
- Internal audit findings and risk registers
- Operational procedures and maintenance schedules for non-critical assets
- Vendor contracts and commercial pricing
- Aggregated NEM12 data (100+ NMIs, no address linkage)
- OT asset registers for LV distribution assets

### 2.3 Public

**Definition:** Information approved for release to the public or already in the public domain. Disclosure causes no harm.

**Handling requirements:**
- No special handling beyond accuracy controls
- Must be reviewed and approved by Corporate Affairs before publication
- Should not be co-mingled with Internal or Restricted data in the same document without re-classification

**Examples:**
- Published AER regulatory submissions and annual performance reports
- Outage notifications published to the company website
- Environmental and sustainability reports
- Network pricing schedules and connection applications
- Media releases and stakeholder newsletters

---

## 3. Operational Technology Data

OT data presents unique classification challenges because its sensitivity may not be obvious from the data values alone. The following rules apply:

| Data Type | Default Classification | Rationale |
|---|---|---|
| SCADA real-time telemetry (live) | Restricted | Real-time topology visibility enables targeted attack planning |
| SCADA historian data (>30 days old, aggregated) | Internal | Reduced operational risk; still commercially sensitive |
| Protection relay settings and fault records | Restricted | Enables bypass of protection systems |
| Asset GPS coordinates (HV substations) | Restricted | Critical infrastructure location data |
| Asset GPS coordinates (LV equipment) | Internal | Lower criticality |
| Environmental sensor data (non-network) | Public | No operational linkage |
| Condition monitoring data (single asset, identified) | Internal | Asset intelligence value |

All OT data originating from AEMO-connected systems (e.g., energy market data submitted via MSATS) must be treated as Restricted until market closure.

---

## 4. Customer Data

Customer data classification follows the National Electricity Market Privacy Code and the Privacy Act 1988 (Cth) Australian Privacy Principles (APPs).

- Customer name + NMI + address combination: **Restricted**
- Customer name + contact details (no NMI): **Internal**
- Anonymised customer count statistics: **Public** (after Privacy Officer review)
- Smart meter data at 5-minute granularity: **Restricted**
- Smart meter data at daily or monthly granularity (no address link): **Internal**

---

## 5. Market Data

Participation in the National Electricity Market (NEM) creates specific confidentiality obligations under the NER. Pre-dispatch and dispatch data, bid information, and confidential AEMO system notices must be classified as Restricted and handled in accordance with NER Chapter 8 information confidentiality provisions.

---

## 6. Data Labelling

All documents, datasets, and files containing Internal or Restricted data must be labelled with the appropriate classification marker in the document header or file metadata. Unlabelled documents discovered during audits will be treated as Internal pending reclassification review.

---

## 7. Reclassification

Data may be reclassified downward by the Data Owner only. Requests for reclassification must be documented and approved by the Chief Information Security Officer. Reclassification of NMI-linked data always requires Privacy Officer concurrence.

---

*This policy is to be read in conjunction with the Access Control Policy (POL-IAM-006), the Metering Data Privacy Policy (POL-PRIV-004), and the AI Usage Policy (POL-AI-001).*
