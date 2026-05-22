# Artificial Intelligence Usage Policy

**Document ID:** POL-AI-001  
**Version:** 2.1  
**Effective Date:** 1 March 2025  
**Review Date:** 1 March 2026  
**Owner:** Chief Digital & Information Officer  
**Classification:** Internal

---

## 1. Purpose

This policy establishes the governance framework for the use of artificial intelligence (AI) and machine learning (ML) technologies across all business functions. It ensures that AI adoption aligns with the company's obligations under the Australian Energy Regulator (AER) Cyber Security Guidelines, APRA Prudential Standard CPS 230 Operational Risk Management, and the Privacy Act 1988 (Cth).

The company recognises AI as a strategic enabler but acknowledges the material operational risks that poorly governed AI introduces to critical electricity infrastructure.

---

## 2. Scope

This policy applies to:

- All employees, contractors, and third-party service providers operating on behalf of the company
- All AI/ML tools, platforms, and models used to process company data or inform operational decisions
- Both information technology (IT) and operational technology (OT) environments
- Generative AI tools (including large language models) accessed via corporate or personal devices for work purposes

---

## 3. Data Governance Requirements

### 3.1 Data Minimisation

AI systems must operate on the minimum data necessary to achieve the stated purpose. Systems must not be granted access to Restricted data (as defined in the Data Classification Policy POL-DATA-002) unless a formal Data Access Request has been approved by the Data Governance Committee.

### 3.2 Training Data Controls

Any use of operational data—including SCADA historian data, NMI-linked customer records, or network topology files—for AI model training requires prior written approval from the Data Owner. Training datasets must be documented in the AI Model Register maintained by the Data & Analytics team.

### 3.3 Data Residency

All AI processing of Restricted or Internal data must occur within Australian data centres. Cloud-based AI services must be assessed for data residency compliance before procurement. The use of offshore AI inference endpoints for unencrypted operational data is prohibited.

---

## 4. Approved Use Cases

The following categories of AI use are pre-approved subject to standard change management procedures:

- **Asset condition monitoring:** Predictive analytics applied to sensor and SCADA data to inform maintenance scheduling
- **Demand forecasting:** Short-term and medium-term load forecasting to support network planning
- **Vegetation management optimisation:** Image classification and geospatial ML for inspection prioritisation
- **Document search and summarisation:** Internal policy and procedure Q&A using retrieval-augmented generation (RAG) over approved Internal-classified document repositories
- **Customer communications drafting:** AI-assisted drafting of routine outage notifications and correspondence, subject to human review before dispatch

---

## 5. Prohibited Uses

The following uses of AI are prohibited without express written approval from the Executive Leadership Team and, where applicable, the AER:

- Autonomous switching or load-shedding decisions on the HV or LV network without human operator authorisation
- Processing of biometric data for access control without Privacy Act compliance assessment
- Use of public generative AI tools (e.g., consumer-grade chatbots) to process customer NMI data, network diagrams, or any Restricted-classified material
- AI-driven credit or debt decisions affecting residential customers without explainability review
- Automated submission of data to AEMO market systems without validated override controls

---

## 6. Oversight and Accountability

### 6.1 AI Governance Committee

An AI Governance Committee, chaired by the Chief Digital & Information Officer, meets quarterly to review the AI Model Register, assess emerging risks, and approve new high-risk use cases. The committee reports to the Audit and Risk Committee.

### 6.2 Human-in-the-Loop Requirements

All AI outputs that inform regulatory reporting, network switching decisions, or customer-affecting actions must be reviewed and approved by a qualified human operator before execution. This requirement cannot be waived by operational urgency.

### 6.3 Incident Reporting

AI-related incidents—including model errors resulting in incorrect operational decisions, data breaches involving AI-processed data, and adversarial inputs detected on AI systems—must be reported via the Cyber Security Incident Response Procedure (PROC-SEC-003) within 24 hours of detection.

---

## 7. APRA CPS 230 Alignment

In accordance with APRA CPS 230, AI services provided by third-party vendors that support material business activities must be subject to the Vendor Risk Management Policy (POL-VRM-005). Material service providers delivering AI platforms must demonstrate adequate operational resilience, including documented business continuity and disaster recovery capabilities.

---

## 8. Policy Exceptions

Exceptions to this policy must be submitted to the CDIO in writing, with documented risk justification and proposed compensating controls. Exceptions are valid for a maximum of 90 days and must be reviewed before renewal.

---

## 9. Breach and Enforcement

Breach of this policy may result in disciplinary action up to and including termination of employment or contract. Breaches involving Restricted data or OT systems will be escalated to the Chief Executive Officer and notified to relevant regulators as required by law.

---

*This policy is reviewed annually or following a significant AI-related incident, regulatory change, or material change to the company's AI technology landscape.*
