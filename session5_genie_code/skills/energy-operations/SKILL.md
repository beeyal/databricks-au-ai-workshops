---
name: energy-operations
description: Australian energy network operations — NEM12 interval data quality flags, SAIDI/SAIFI reliability metrics, AER/AEMO regulatory context, DNO asset terminology, and common SQL patterns for energy analytics
---

# Australian Energy Operations Knowledge

Use this skill when working with meter data, outage records, network asset management, or regulatory reporting for Australian distribution network operators (DNOs) and transmission businesses.

---

## NEM12 Interval Data

### What is NEM12?
NEM12 is the AEMO-defined file format for electricity meter interval data exchanged in the National Electricity Market. In a database context, each row typically represents one 30-minute interval for one NMI (metering point).

### Quality Flags
| Flag | Code | Meaning | Include in analysis? |
|------|------|---------|---------------------|
| A | Actual | Meter reading recorded and validated | ✅ Yes — primary data |
| E | Estimated | MDFF-calculated estimate where meter was inaccessible | ✅ Yes — note in output |
| S | Substituted | Manually substituted by FRMP or LNSP | ⚠️ Flag prominently in output |
| N | Null / missing | No reading available; gap in data | ❌ Exclude from consumption totals |
| F | Final substituted | Substituted and finalised by market settlement | ⚠️ Flag — treated like S for analysis |

> **Important:** Always filter `quality_flag IN ('A', 'E')` for operational analysis unless the question specifically concerns data quality or gaps.

### Interval Calculations
- **One row = one 30-minute interval** → 48 rows per NMI per day when complete
- **Daily consumption:** `SUM(interval_kwh)` — values are already 30-min energy totals; do NOT multiply by 2
- **Half-hourly demand (kW):** `interval_kwh * 2` — converts 30-min energy (kWh) to instantaneous power (kW)
- **Peak demand window:** 4:00 PM – 8:00 PM local time (`HOUR(reading_datetime) BETWEEN 16 AND 19`)
- **Off-peak window:** 10:00 PM – 7:00 AM (`HOUR(reading_datetime) >= 22 OR HOUR(reading_datetime) < 7`)
- **Shoulder:** everything in between (7:00 AM – 4:00 PM, 8:00 PM – 10:00 PM)

### NMI Format
- 10-character alphanumeric identifier assigned by the local network service provider (LNSP)
- State prefix convention (not guaranteed, but typical):
  - VIC: `61XXXXXXXX`
  - NSW: `41XXXXXXXX`
  - QLD: `31XXXXXXXX`
  - SA: `21XXXXXXXX`
  - WA: `71XXXXXXXX` (WA is not part of NEM; uses AEMO WA market rules separately)
  - TAS: `81XXXXXXXX`

---

## SAIDI / SAIFI Reliability Metrics

### SAIDI — System Average Interruption Duration Index
Measures how many minutes of supply interruption an average customer experienced.

```
SAIDI = Σ(interruption_duration_minutes × affected_customers) / total_customers_served
```

- **Units:** minutes per customer per year (or reporting period)
- **AER STPIS target (typical urban network):** < 25 minutes/year unplanned
- **Lower is better**
- **Planned vs unplanned:** AER STPIS only penalises unplanned interruptions; planned maintenance is reported separately but not penalised

### SAIFI — System Average Interruption Frequency Index
Measures how many times an average customer lost supply.

```
SAIFI = Σ(number_of_interruption_events × affected_customers) / total_customers_served
```

- **Units:** interruptions per customer per year
- **AER STPIS target (typical urban network):** < 1.0 interruptions/year unplanned
- **Lower is better**

### CAIDI — Customer Average Interruption Duration Index
Average duration when an interruption does occur. Derived from SAIDI and SAIFI.

```
CAIDI = SAIDI / SAIFI
```

- Useful for understanding whether the problem is frequency (SAIFI high) or duration (CAIDI high) — they require different remediation strategies

### Exclusions
Networks may exclude from STPIS calculations:
- Major event days (MEDs): events exceeding a statistical threshold
- Events caused by customer equipment
- Force majeure (storms, floods — network-specific threshold definitions apply)

---

## Regulatory Bodies & Frameworks

| Body | Full Name | Role |
|------|-----------|------|
| AER | Australian Energy Regulator | Sets STPIS performance standards, approves revenue determinations, enforces NER |
| AEMO | Australian Energy Market Operator | Runs NEM dispatch, manages NEMDE, publishes market data |
| ESC | Essential Services Commission (VIC) | State-level consumer protection and retail licence compliance |
| IPART | Independent Pricing and Regulatory Tribunal (NSW) | Water and some energy pricing in NSW |
| QCA | Queensland Competition Authority | Pricing oversight for Energex / Ergon in QLD |
| ERA | Economic Regulation Authority (WA) | Western Power and Synergy regulation (outside NEM) |

### Key Regulatory Instruments
- **NER:** National Electricity Rules — the governing framework for the NEM
- **STPIS:** Service Target Performance Incentive Scheme — AER's financial reward/penalty framework for DNO reliability
- **DMIA:** Demand Management Innovation Allowance — funding for demand-side programs
- **LNSP:** Local Network Service Provider — the DNO responsible for the poles and wires
- **FRMP:** Financially Responsible Market Participant — the retailer responsible for settlement

---

## Network Asset Types

| Asset | Description | Typical Failure Impact |
|-------|-------------|----------------------|
| Transmission line | 220 kV – 500 kV overhead or cable linking bulk supply points | Zone substation and all customers downstream |
| Zone substation (ZSS) | Steps 66/132 kV down to 11/22 kV; feeds distribution network | Entire suburb or industrial precinct |
| Transformer (distribution) | Steps 11 kV down to LV (415/240 V) at street level | 20–200 premises depending on rating |
| 11 kV feeder | Distribution circuit from zone substation | Section of suburb; typically 500–2,000 customers |
| Switchgear (recloser, sectionalisor) | Isolates faults automatically; enables switching | Reduces customer minutes if operating correctly |
| HV cable | Underground 11 kV cable (expensive to replace; 30–50 yr life) | Section of urban feeder |
| LV cable | Underground or overhead 415/240 V from transformer to premises | Individual street block |
| Pole (wooden) | Supports overhead conductors; 60–70 year design life | Single span; risk of cascading in storms |
| Service line | Last-mile connection from LV network to customer's meter | Individual customer |

**HV vs LV boundary:** High Voltage = above 1,000 V AC. Low Voltage = 1,000 V AC and below. The transformer at the top of a power pole marks the HV/LV boundary for most residential areas.

---

## Common SQL Patterns

### Daily consumption by NMI (excluding nulls)
```sql
SELECT
    nmi,
    DATE(reading_datetime)          AS reading_date,
    SUM(interval_kwh)               AS daily_kwh,
    COUNT(*)                        AS intervals_recorded,
    COUNT(*) / 48.0 * 100           AS completeness_pct
FROM meter_readings
WHERE quality_flag IN ('A', 'E')
GROUP BY nmi, DATE(reading_datetime)
ORDER BY nmi, reading_date
```

### Peak demand by NMI and date
```sql
SELECT
    nmi,
    DATE(reading_datetime)          AS reading_date,
    MAX(interval_kwh * 2)           AS peak_demand_kw,   -- kWh × 2 = kW for 30-min intervals
    MAX_BY(reading_datetime, interval_kwh * 2) AS peak_time
FROM meter_readings
WHERE HOUR(reading_datetime) BETWEEN 16 AND 19   -- 4 PM – 8 PM peak window
  AND quality_flag IN ('A', 'E')
GROUP BY nmi, DATE(reading_datetime)
```

### SAIDI by region and year
```sql
SELECT
    region,
    YEAR(start_time)                        AS year,
    SUM(saidi_minutes)                      AS total_saidi_minutes,
    SUM(saidi_minutes) / COUNT(DISTINCT
        DATE(start_time))                   AS avg_daily_saidi,
    COUNT(*)                                AS outage_count
FROM outage_events
WHERE event_type = 'unplanned'
  -- Note: outage_events has no major_event_day column; filter MEDs by duration or cause if needed
GROUP BY region, YEAR(start_time)
ORDER BY region, year
```

### SAIFI by region and year
```sql
SELECT
    region,
    YEAR(start_time)                        AS year,
    SUM(saifi_count)                        AS total_saifi,
    COUNT(*)                                AS interruption_events
FROM outage_events
WHERE event_type = 'unplanned'
GROUP BY region, YEAR(start_time)
ORDER BY region, year
```

### Asset health dashboard — transformers at risk
```sql
SELECT
    a.asset_id,
    a.asset_type,
    a.asset_name,
    a.region,
    a.installation_date,
    YEAR(CURRENT_DATE) - YEAR(a.installation_date)   AS age_years,
    COUNT(wo.work_order_id)                           AS work_orders_last_2yr,
    SUM(CASE WHEN wo.priority = 'critical' THEN 1 ELSE 0 END) AS critical_wos
FROM energy_assets a
LEFT JOIN maintenance_work_orders wo
    ON a.asset_id = wo.asset_id
    AND wo.created_date >= ADD_MONTHS(CURRENT_DATE, -24)
WHERE a.asset_type = 'transformer'
GROUP BY a.asset_id, a.asset_type, a.asset_name, a.region, a.installation_date
HAVING age_years > 40 OR critical_wos >= 2
ORDER BY critical_wos DESC, age_years DESC
```

---

## Glossary

| Term | Definition |
|------|-----------|
| DNO | Distribution Network Operator — the business that owns the poles and wires |
| NMI | National Metering Identifier — the 10-digit identifier for a metering point |
| NEM | National Electricity Market — the wholesale electricity market covering eastern and southern Australia |
| MDFF | Meter Data File Format — the format specification (NEM12 for interval, NEM13 for accumulation) |
| FRMP | Financially Responsible Market Participant — the retailer responsible for a NMI in settlement |
| LNSP | Local Network Service Provider — the DNO who maintains the wires to a given NMI |
| kWh | Kilowatt-hour — unit of energy (what the bill is based on) |
| kW | Kilowatt — unit of power / demand (the instantaneous rate of use) |
| MED | Major Event Day — a statistical threshold used to exclude catastrophic events from STPIS calculations |
| STPIS | Service Target Performance Incentive Scheme — the AER mechanism that financially rewards/penalises reliability |
