# Asset Management Policy — Electricity Network Assets

**Document ID:** POL-ASSET-007  
**Version:** 4.2  
**Effective Date:** 1 January 2025  
**Review Date:** 1 January 2026  
**Owner:** General Manager Asset Management  
**Classification:** Internal

---

## 1. Purpose

This policy establishes the requirements for managing the lifecycle of electricity network assets—from acquisition through to disposal—to ensure safe, reliable, and efficient delivery of electricity distribution services. It supports the company's compliance with the AER Expenditure Forecast Assessment Guideline, the National Electricity Rules (NER) Chapter 6, and the Electricity Safety Act obligations administered by Energy Safe Victoria (ESV) or the relevant state technical regulator.

Network asset management directly drives the company's SAIDI (System Average Interruption Duration Index) and SAIFI (System Average Interruption Frequency Index) performance, which are incentivised under the AER's Service Target Performance Incentive Scheme (STPIS) and form a key input to the company's regulated revenue.

---

## 2. Asset Register and Classification

### 2.1 Asset Register

All network assets with a replacement value exceeding $10,000 must be recorded in the Enterprise Asset Management (EAM) system. The Asset Register must capture:

- Asset unique identifier (aligned to GIS spatial reference)
- Asset class and sub-type (e.g., HV overhead conductor, zone substation power transformer)
- Installation date, manufacturer, and model
- Rated capacity and current operating condition score (1–5)
- Location coordinates (WGS84) and circuit/feeder association
- Responsible asset manager and maintenance crew assignment

### 2.2 Asset Classes

| Asset Class | Voltage Level | Regulatory Significance |
|---|---|---|
| Transmission lines and cables | 66 kV and above | AEMO system security; AER Chapter 6A |
| Zone substation transformers | 66/22 kV, 66/11 kV | Critical to feeder restoration |
| Distribution feeders (overhead) | 22 kV, 11 kV | Primary driver of SAIDI/SAIFI |
| Distribution feeders (underground) | 22 kV, 11 kV | Lower fault rate; higher repair cost |
| Distribution transformers (pole/pad) | 11/0.4 kV | LV customer supply |
| Secondary systems | Protection, SCADA RTUs, comms | OT criticality — AESCSF applicable |
| Metering assets | HV and LV | NER Chapter 7; MC obligations |

---

## 3. Condition Monitoring

### 3.1 Condition Assessment Framework

Assets are assessed on a 1–5 condition scale:

| Score | Condition | Action |
|---|---|---|
| 5 | As new | No action; standard monitoring cycle |
| 4 | Good | No action; monitor per schedule |
| 3 | Fair | Include in forward capital works programme |
| 2 | Poor | Prioritise for replacement or refurbishment within 3 years |
| 1 | Critical | Immediate action; include in urgent capital or emergency works |

Condition scores are updated following scheduled inspections, diagnostic testing results, and fault event records.

### 3.2 Inspection Schedules

| Asset Type | Ground Inspection | Aerial/Drone Inspection | Diagnostic Testing |
|---|---|---|---|
| HV overhead lines | Every 5 years | Every 3 years (fire risk zones: annually) | Thermographic: every 5 years |
| Zone substation transformers | Annual visual | N/A | DGA (oil) annually; FRA every 5 years |
| Pole structures | Every 5 years | Every 3 years | Pole testing per ESV Guidelines |
| Underground cables | N/A | N/A | Partial discharge testing: 10 years |
| Protection relays | Functional test: every 5 years | N/A | Secondary injection: every 5 years |
| SCADA RTUs | Functional check: annually | N/A | Comms testing: annually |

Assets in Bushfire Management Overlay (BMO) zones are subject to enhanced inspection frequencies under the Electricity Safety (Bushfire Mitigation) Regulations.

---

## 4. SAIDI/SAIFI Performance Obligations

### 4.1 Regulatory Targets

Under the AER's STPIS, the company has annual SAIDI and SAIFI targets determined by the Distribution Determination. Sustained outages (>1 minute) are included in SAIDI calculations. The company is exposed to financial incentives (positive or negative) based on performance against the target band.

### 4.2 Asset Contribution Tracking

Each sustained outage event is attributed to the failed asset in the EAM system. Assets with three or more outage contributions in a rolling 3-year period are automatically flagged for condition review and capital programme consideration.

### 4.3 Loss of Supply Events

Major Loss of Supply events — defined under NER Rule 4.8.7 as events affecting more than 1 MW of load or large numbers of residential customers — must be reported to AEMO and the AER. Asset records are updated with the fault cause code and an engineering assessment of whether the event was preventable through timely asset intervention.

---

## 5. Predictive Analytics and AI Integration

The Asset Management team uses predictive analytics to augment condition scoring and investment prioritisation. The following guidelines apply:

- AI/ML models used for asset condition prediction must be registered in the AI Model Register (per POL-AI-001)
- Model outputs are advisory; final investment decisions require sign-off by a registered engineering professional
- Model predictions must be explainable to the satisfaction of a regulatory reviewer (e.g., an AER Compliance Officer)
- Sensor data ingested by predictive models must comply with the Data Classification Policy (POL-DATA-002); SCADA historian data is classified Internal

---

## 6. Asset Disposal

Assets removed from service must be processed through the Asset Disposal procedure:

1. Condition recorded in EAM as "decommissioned"
2. Hazardous material check (e.g., PCB-containing equipment, asbestos) by Safety Officer
3. Environmental compliance review if the asset contains oil (transformer disposal under EPA guidelines)
4. Copper and conductor recovered via approved recyclers; financial credit allocated to asset class account
5. Restricted asset data (e.g., location of decommissioned substation) reviewed for security classification before deletion

---

## 7. Capital Programme Governance

Capital works programmes are developed annually, incorporating condition assessment outputs, SAIDI/SAIFI attribution data, and load growth forecasts. Programmes above $5 million require review by the Capital Programme Committee, comprising the GM Asset Management, CFO, and CE Network Operations. Programmes submitted to the AER as part of a regulatory proposal require Board endorsement.

---

*This policy is reviewed annually and in response to changes in AER regulatory guidelines, ESV technical requirements, or material changes to the company's asset portfolio.*
