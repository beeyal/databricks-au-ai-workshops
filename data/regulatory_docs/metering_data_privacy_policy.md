# Metering Data Privacy Policy

**Document ID:** POL-PRIV-004  
**Version:** 2.0  
**Effective Date:** 1 June 2024  
**Review Date:** 1 June 2025  
**Owner:** Privacy Officer  
**Classification:** Internal

---

## 1. Purpose

This policy governs the collection, use, storage, disclosure, and disposal of metering data held by the company in its capacity as a Network Service Provider (NSP) and Metering Coordinator (MC) under the National Electricity Market. It implements the obligations of the National Electricity (Privacy) Code (NEM Privacy Code), the Privacy Act 1988 (Cth) Australian Privacy Principles (APPs), and the National Electricity Rules (NER) Chapter 7.

Metering data—particularly interval data linked to a National Metering Identifier (NMI)—can reveal highly personal information about a customer's household routines, occupancy patterns, and energy-consuming activities. This policy treats such data with the same sensitivity as health or financial records.

---

## 2. Scope

This policy applies to all employees, contractors, and systems that handle:

- NEM12 and NEM13 metering data files (half-hourly and five-minute interval data)
- NMI standing data and meter configuration records held in MSATS
- Smart meter telemetry data from advanced metering infrastructure (AMI)
- Distributor-read accumulation meter data
- Network tariff and billing metering used for settlement

---

## 3. National Metering Identifier (NMI) Privacy

### 3.1 NMI as Personal Information

A NMI, when combined with address data, customer name, or interval consumption data, constitutes personal information under the Privacy Act 1988 (Cth). It may also constitute sensitive personal information where consumption patterns reveal religious practices, medical equipment use, or other sensitive attributes.

### 3.2 NMI Linkage Controls

Systems that process NMI data must enforce the following controls:

- NMI-to-address and NMI-to-customer-name linkage is permitted only in systems with a documented, approved business purpose
- NMI data must not be used as a join key in analytics datasets without pseudonymisation (replacing the NMI with a non-reversible hash)
- Any dataset containing more than 50 linked NMI records is automatically classified as Restricted under the Data Classification Policy (POL-DATA-002)
- NMI data must not be exposed in system logs, error messages, or audit trails beyond the minimum required for traceability

---

## 4. Customer Consent for Data Use

### 4.1 Permitted Uses Without Additional Consent

The company may use metering data without additional customer consent for the following purposes, which are authorised under the NEM Privacy Code and NER:

- Network billing, settlement, and reconciliation with AEMO
- Network planning and demand forecasting (in aggregated or de-identified form)
- Regulatory reporting to the AER, ESC (Essential Services Commission of Victoria), or ESCOSA (South Australia)
- Safety investigations (e.g., identifying high consumption indicating faulty equipment)
- Outage management and restoration planning

### 4.2 Uses Requiring Explicit Consent

The following uses require the customer's prior, informed, written or electronic consent before metering data is accessed or disclosed:

- Sharing NMI interval data with energy retailers for products or services not directly related to network supply
- Use of interval data to train AI/ML models for commercial applications (e.g., customer behaviour profiling)
- Providing data to third parties for research, even if de-identified, unless specifically exempted
- Any use that a reasonable customer would not expect from a network service provider

Consent must be obtained using approved consent forms that meet the standard of informed consent under APP 3.3. Consent records must be retained for the duration of the customer's connection plus 7 years.

---

## 5. Data Retention Requirements

### 5.1 Minimum Retention Periods

| Data Type | Minimum Retention Period | Authority |
|---|---|---|
| NEM12 interval metering data | 7 years from date of meter read | NER Rule 7.15.5 |
| NEM13 accumulation meter data | 7 years from date of meter read | NER Rule 7.15.5 |
| Meter standing data (MSATS records) | 7 years after connection point deenergised | NER Chapter 7 |
| Customer consent records | Duration of connection + 7 years | Privacy Act 1988 |
| Meter installation and maintenance records | 7 years after meter removal | Electricity Safety Act |
| AEMO data submission logs | 7 years | NER Rule 3.13 |

### 5.2 Retention Beyond Minimum

Data may be retained beyond the minimum period where:

- Required for ongoing regulatory proceedings or litigation
- Specifically authorised by written agreement with the AER or AEMO
- Retained in a de-identified and aggregated form for network planning purposes

### 5.3 Disposal

Upon expiry of the retention period, metering data must be securely disposed of using approved methods (cryptographic erasure for cloud storage, DoD 5220.22-M compliant wiping for on-premise storage, or physical destruction for portable media). Disposal must be documented in the Asset Disposal Register.

---

## 6. Third-Party Data Sharing

Metering data may only be shared with third parties where one or more of the following applies:

- The recipient is a Registered Participant under the NEM with a legitimate NER entitlement to the data
- The customer has provided explicit consent (see Section 4.2)
- Disclosure is required by law or court order
- Disclosure is to AEMO for market operations purposes

All third-party data sharing must be covered by a Data Sharing Agreement reviewed by Legal and the Privacy Officer before execution. The agreement must specify the purpose, data fields, retention limits, and security requirements.

---

## 7. Data Breach Response

Suspected or confirmed breaches involving NMI data or customer metering records must be reported to the Privacy Officer within 1 hour of detection. The Privacy Officer will assess whether the breach constitutes an Eligible Data Breach under Part IIIC of the Privacy Act 1988. If so, notification to the OAIC and affected customers must occur within 30 days.

---

## 8. Staff Training

All staff and contractors with access to metering data must complete the Privacy and Metering Data Handling training module (PRI-001) at onboarding and annually thereafter. Completion is recorded in the Learning Management System.

---

*This policy is to be read alongside the Data Classification Policy (POL-DATA-002), the AI Usage Policy (POL-AI-001), and the NEM Privacy Code (as amended). For queries contact the Privacy Officer.*
