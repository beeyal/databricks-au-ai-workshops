# AI Model Governance Framework

**Document ID:** FRAME-AI-002  
**Version:** 1.2  
**Effective Date:** 1 April 2025  
**Review Date:** 1 April 2026  
**Owner:** Chief Data & Analytics Officer  
**Classification:** Internal

---

## 1. Purpose

This framework defines the governance requirements for the full lifecycle of AI and machine learning models developed, procured, or deployed by the company. It supplements the AI Usage Policy (POL-AI-001) with specific requirements for model development, validation, production deployment, ongoing monitoring, and retirement.

The framework responds to the increasing use of AI in regulated activities—including asset condition assessment, load forecasting for AEMO market participation, and customer interaction—and the expectation from the AER and APRA CPS 230 that regulated entities demonstrate control over technology risks, including algorithmic risk.

---

## 2. Scope

This framework applies to all models that:

- Are deployed in a production environment and produce outputs used to inform business decisions
- Process Restricted or Internal data as defined by the Data Classification Policy (POL-DATA-002)
- Produce outputs affecting customers, network operations, regulatory reporting, or financial outcomes
- Are provided by third-party vendors and integrated into company workflows

Point-in-time analytical models used solely for internal research or exploration, with no production deployment, are exempt but should follow good practice where practicable.

---

## 3. Model Risk Classification

Models are assigned a risk tier based on the consequence of model failure or error:

| Tier | Risk Level | Criteria | Governance Intensity |
|---|---|---|---|
| A | Critical | Outputs directly control network switching, protection settings, or AEMO market submissions | Full lifecycle governance; mandatory independent validation |
| B | High | Outputs inform regulatory reports (AER submissions, STPIS data), customer decisions, or capital investment prioritisation | Full lifecycle governance; internal validation with documented independence |
| C | Medium | Outputs inform operational planning, maintenance scheduling, or internal analytics | Development governance and basic validation; monitoring required |
| D | Low | Outputs advisory only; human reviews all recommendations before any action | Development governance; periodic accuracy review |

---

## 4. Model Development Lifecycle

### 4.1 Problem Definition and Data Sourcing

Before model development begins, the model sponsor must document:

- The business problem the model will address and the intended decision it informs
- The data sources to be used and their classification level
- The intended user and the level of autonomy (human-in-the-loop or automated)
- The risk tier assessment (submitted to AI Governance Committee for Tier A/B)
- Data Access Requests for any Restricted data required for training (per POL-DATA-002)

### 4.2 Development Standards

Models must be developed following the company's ML Engineering Standards (ENG-ML-001), which require:

- Version-controlled code in the company's approved code repository
- Experiment tracking using an approved ML tracking platform (e.g., MLflow on the company's data platform)
- Training, validation, and test datasets must be separate; no data leakage permitted
- Model cards documenting architecture, training data summary, performance metrics, known limitations, and intended use

### 4.3 Bias and Fairness Assessment

For models affecting individual customers or groups of customers (Tier B/C), a bias and fairness assessment must be completed before deployment. The assessment must evaluate whether the model produces materially different outcomes for identifiable customer segments (e.g., by geography, tariff class, or socioeconomic proxy). Results are documented in the model card.

---

## 5. Validation Requirements

### 5.1 Tier A and B Models

Independent validation must be performed before production deployment. Validation is independent when the validator:

- Was not part of the team that developed or trained the model
- Does not report to the model development team lead
- Has documented data science or statistical competency

Validation activities must include:

- Replication of reported performance metrics on the hold-out test set
- Sensitivity analysis to understand model behaviour at distribution boundaries
- Robustness testing (performance under data quality degradation scenarios)
- Challenge of assumptions in feature engineering and target variable definition
- Review of model card completeness

Validation findings and sign-off are documented in the Model Validation Report, reviewed by the AI Governance Committee.

### 5.2 Tier C and D Models

Internal peer review by at least one data scientist not on the development team. Peer review documents performance metrics and a check that the model card is complete.

---

## 6. Production Deployment

### 6.1 Change Management

Model deployment into production is treated as a High change under the IT/OT Change Management Procedure (PROC-CHG-008). The change record must reference the approved Model Validation Report.

### 6.2 Explainability for Regulated Decisions

Models producing outputs that support regulated decisions (AER submissions, STPIS calculations, AEMO settlement data, customer credit assessments) must implement explainability sufficient to allow a qualified reviewer to reconstruct the basis for an individual model output. Accepted approaches include:

- Feature importance summaries (SHAP values) stored alongside predictions in the output dataset
- Rule extraction or surrogate model summaries for complex ensemble models
- Documented decision thresholds and logic for classification outputs

Explainability outputs must be retained for the same period as the associated regulatory record (minimum 7 years).

### 6.3 Model Register

All models deployed to production must be registered in the AI Model Register maintained by the Chief Data & Analytics Office. The register records: model name and version, risk tier, owner, deployment date, validation status, monitoring status, and retirement date.

---

## 7. Monitoring Obligations

### 7.1 Performance Monitoring

Production models must be monitored for performance drift at intervals proportional to their risk tier:

| Tier | Monitoring Frequency | Drift Alert Threshold |
|---|---|---|
| A | Continuous (automated alerts) | Any statistically significant degradation |
| B | Weekly automated report; human review monthly | >5% degradation in primary metric |
| C | Monthly automated report | >10% degradation in primary metric |
| D | Quarterly review | Qualitative assessment |

### 7.2 Data Drift Monitoring

Input feature distributions must be monitored against the training baseline. Significant data drift (e.g., caused by changes in SCADA sensor configuration, NEM rule changes affecting metering data formats, or changes in customer load profiles following tariff reform) must trigger a model re-evaluation.

### 7.3 Incident Reporting

Monitoring findings that indicate a model is producing materially incorrect outputs in production must be escalated to the model owner and AI Governance Committee within 24 hours. If the model supports a Tier A function, the NCC Supervisor must be notified immediately and the model output suspended pending investigation.

---

## 8. Model Retirement

Models that are replaced by a newer version or no longer serve a business purpose must be retired within 30 days. Retirement requires:

- Confirmation that all downstream dependencies have been updated to the replacement model
- Archiving of model artefacts (code, weights, training data reference) for the retention period
- Closure of the model record in the AI Model Register
- Post-retirement review for Tier A/B models documenting lessons learned

---

## 9. Roles and Responsibilities

| Role | Responsibility |
|---|---|
| Model Sponsor (Business) | Problem definition; regulatory impact assessment; ongoing use authorisation |
| Model Developer (Data Science team) | Model development to standards; model card; experiment tracking |
| Model Validator | Independent validation; validation report |
| Chief Data & Analytics Officer | Framework ownership; AI Model Register; AI Governance Committee chair |
| AI Governance Committee | Tier A/B approval; exception approvals; escalated monitoring findings |
| CISO | Security review of AI systems; adversarial risk assessment |

---

*This framework is reviewed annually and upon any material change to AI regulatory guidance in Australia, including guidance from APRA, the AER, or the Office of the Australian Information Commissioner.*
