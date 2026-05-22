# Vendor Risk Management Policy

**Document ID:** POL-VRM-005  
**Version:** 3.1  
**Effective Date:** 1 July 2024  
**Review Date:** 1 July 2025  
**Owner:** Chief Risk Officer  
**Classification:** Internal

---

## 1. Purpose

This policy establishes the framework for identifying, assessing, and managing risks arising from third-party vendors and service providers, with specific provisions for AI/ML service providers and cloud platforms. The policy implements the requirements of APRA Prudential Standard CPS 230 Operational Risk Management (effective 1 July 2025) and the Security of Critical Infrastructure Act 2018 (Cth).

CPS 230 requires regulated entities and their associated service providers to maintain operational resilience. As the company operates critical electricity infrastructure supporting the NEM, third-party failures can have consequences for market participants and energy consumers beyond the company's direct customer base.

---

## 2. Scope

This policy applies to all external vendors, suppliers, and service providers who:

- Access company IT or OT systems, networks, or data
- Process, store, or transmit Restricted or Internal classified data on the company's behalf
- Provide technology platforms or software used for business-critical operations
- Provide AI/ML services, data analytics platforms, or cloud computing infrastructure
- Support any function that is material to the company's ability to deliver safe, reliable electricity supply

---

## 3. Vendor Tiering

All active vendors are assigned a tier based on operational criticality and data sensitivity:

| Tier | Criteria | Assessment Frequency |
|---|---|---|
| Tier 1 — Critical | Supports SCADA, EMS, AEMO market interfaces, protection systems, or processes Restricted data at scale | Annual full assessment + continuous monitoring |
| Tier 2 — Important | Supports business-critical IT systems, processes customer data, or provides cloud AI/ML platforms | Annual assessment |
| Tier 3 — Standard | Provides commodity services with no access to company data or systems | Assessment at onboarding; tri-annual review |

---

## 4. Material Service Providers — APRA CPS 230

### 4.1 Identification

Under CPS 230 paragraph 55, the company must identify material service providers (MSPs) — those providers whose failure would have a material adverse impact on the company's operational continuity. The Risk team maintains the MSP Register, reviewed quarterly by the Risk and Audit Committee.

Current MSP categories include:

- EMS/SCADA platform vendors
- Network Management System (NMS) software providers
- Core enterprise systems (ERP, workforce management)
- Cloud infrastructure providers hosting operational data
- AI/ML platforms processing metering or operational data

### 4.2 MSP Requirements

Tier 1 and designated MSPs must contractually commit to:

- Providing the company with audited business continuity plans (BCPs) and disaster recovery (DR) test results annually
- Notifying the company of any material operational incident within 24 hours
- Allowing the company to conduct or commission security audits at reasonable notice
- Maintaining cyber security standards consistent with ASD Essential Eight Maturity Level 2 (minimum)
- Disclosing the use of sub-contractors who access company data and subjecting them to equivalent controls

### 4.3 Concentration Risk

The Risk team must assess and document concentration risk where multiple critical functions depend on a single vendor or cloud provider. Where concentration risk is assessed as High, a mitigation plan (e.g., secondary supplier, in-house fallback capability) must be approved by the Chief Executive Officer.

---

## 5. AI/ML Service Provider Due Diligence

The rapid adoption of AI/ML platforms introduces specific risks that must be assessed in addition to the standard vendor due diligence checklist:

### 5.1 Data Residency and Processing Location

The vendor must confirm that all data processed on the company's behalf remains within Australian jurisdictions, or provide a detailed cross-border data transfer risk assessment approved by Legal and the Privacy Officer.

### 5.2 Model Training on Customer Data

Vendors must confirm whether customer or operational data provided to their platform will be used to train shared AI models. Any use of company data for vendor model improvement is prohibited without explicit written consent from the Chief Risk Officer.

### 5.3 AI Output Explainability

For AI/ML services producing outputs that inform regulated decisions (e.g., network investment prioritisation, customer credit decisions, regulatory submissions), the vendor must demonstrate explainability capability allowing auditors to understand the basis for individual model outputs.

### 5.4 Model Drift and Monitoring

The vendor must provide documented model performance monitoring and drift detection capabilities. The company must have the ability to revert to a prior model version or halt AI-driven processes within 4 hours of detecting material model degradation.

### 5.5 AI Security Controls

Vendors must demonstrate controls against adversarial inputs, prompt injection (for LLM-based products), and model inversion attacks. Evidence must be provided as part of the annual security assessment.

---

## 6. Due Diligence Checklist

Before engagement of a Tier 1 or Tier 2 vendor, the Procurement team must obtain completed responses to the Vendor Due Diligence Questionnaire (VRM-F-001), which covers:

- [ ] Corporate structure, financial stability, and Australian entity status
- [ ] Information security certifications (ISO 27001, SOC 2 Type II, or equivalent)
- [ ] Data classification and handling practices
- [ ] Subcontractor and supply chain risk disclosures
- [ ] Business continuity and disaster recovery capabilities
- [ ] Incident notification obligations and historical incident record
- [ ] Regulatory compliance (Privacy Act, SOCI Act, NEM participation rules)
- [ ] For AI vendors: data residency, training data use, explainability, model monitoring

---

## 7. Ongoing Monitoring

Tier 1 vendors are subject to continuous monitoring via:

- Automated threat intelligence feeds for vendor cyber incidents
- Quarterly relationship reviews with the vendor account manager
- Annual on-site or virtual audit (right to audit must be contractually reserved)

Any vendor cyber security incident disclosed under Section 4.2 obligations triggers an immediate risk review by the CISO and Risk team.

---

## 8. Vendor Exit

All vendor contracts must include exit provisions ensuring that:

- Company data is returned or destroyed within 30 days of contract termination
- The vendor certifies data destruction in writing
- Knowledge transfer obligations are met before transition
- Regulatory records are provided for the required retention period

---

*Queries regarding this policy should be directed to the Procurement team or the Chief Risk Officer. This policy is reviewed annually or when APRA CPS 230 guidance is updated.*
