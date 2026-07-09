"""
Generate sample data for the Databricks AU AI Workshops.
Australian energy sector datasets for regulated industry use cases.

Usage:
    pip install pandas numpy faker
    python generate_sample_data.py

Outputs CSVs to ./data/sample_data/ (relative to this script's location).
No Databricks connection required — pure local generation.
"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ---------------------------------------------------------------------------
# Output location
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / "sample_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rand_date(start: str, end: str) -> datetime:
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    return s + timedelta(seconds=random.randint(0, int((e - s).total_seconds())))


def rand_dates(start: str, end: str, n: int) -> list[datetime]:
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    span = int((e - s).total_seconds())
    offsets = np.random.randint(0, span, size=n)
    return [s + timedelta(seconds=int(o)) for o in offsets]


# ---------------------------------------------------------------------------
# Australian geography
# ---------------------------------------------------------------------------

REGIONS = ["VIC", "NSW", "QLD", "SA", "WA"]

SUBREGIONS = {
    "VIC": ["Melbourne CBD", "Geelong", "Ballarat", "Bendigo", "Shepparton",
            "Latrobe Valley", "Mornington Peninsula", "Sunbury", "Wodonga"],
    "NSW": ["Sydney CBD", "Parramatta", "Newcastle", "Wollongong", "Albury",
            "Orange", "Tamworth", "Dubbo", "Port Macquarie"],
    "QLD": ["Brisbane CBD", "Gold Coast", "Sunshine Coast", "Townsville",
            "Cairns", "Toowoomba", "Mackay", "Rockhampton", "Bundaberg"],
    "SA":  ["Adelaide CBD", "Mount Gambier", "Whyalla", "Port Augusta",
            "Port Pirie", "Victor Harbor", "Murray Bridge", "Renmark"],
    "WA":  ["Perth CBD", "Fremantle", "Bunbury", "Geraldton", "Kalgoorlie",
            "Albany", "Broome", "Mandurah", "Rockingham"],
}

REGION_LAT_LON = {
    "VIC": (-37.8 , 144.9, 0.8, 2.5),
    "NSW": (-33.9 , 151.2, 1.5, 3.0),
    "QLD": (-27.5 , 153.0, 2.0, 3.5),
    "SA":  (-34.9 , 138.6, 1.2, 2.8),
    "WA":  (-31.9 , 115.9, 1.5, 4.0),
}

MANUFACTURERS = [
    "ABB", "Siemens", "Schneider Electric", "Eaton", "GE Grid Solutions",
    "Mitsubishi Electric", "Toshiba Energy Systems", "Hitachi Energy",
    "Lucy Electric", "Ormazabal",
]

ASSET_MODELS = {
    "transformer":  ["T800", "T1200", "PowerGard 500", "EcoStar 800", "UniTrans 1000"],
    "substation":   ["SS-Primary-132kV", "SS-Zone-66kV", "SS-Distribution-11kV", "CompactSS-400"],
    "cable":        ["XLPE-11kV-300", "XLPE-33kV-150", "PILC-11kV-185", "HDPE-LV-95"],
    "pole":         ["WoodPole-12m", "SteelPole-15m", "CompositePole-11m", "ConcretePole-14m"],
    "meter":        ["Landis+Gyr E470", "Itron Riva", "Honeywell Elster AS3500", "Genus PRANA"],
}

EQUIPMENT_ISSUES = [
    "Oil leakage detected on lower tank seam.",
    "Abnormal humming noise observed during peak load.",
    "Corrosion on clamp hardware — recommend replacement within 6 months.",
    "Partial discharge measured at 450 pC — monitor monthly.",
    "Insulation resistance degraded to 85 MΩ; below 100 MΩ threshold.",
    "Fuse links showing signs of heat damage.",
    "Thermal imaging shows hot spot at LV busbar connection.",
    "Vegetation encroachment within 0.5 m of conductors.",
    "Animal damage to cable conduit — temporary repair applied.",
    "Gasket seal worn; minor moisture ingress risk.",
    "Lightning arrestor earthing lead corroded.",
    "Metering discrepancy — potential CT saturation under fault conditions.",
    "Paint delamination on weathering-steel structure.",
    "No visible issues at time of inspection.",
    "Earthing mat connection verified and in good condition.",
    "Nameplate illegible — asset records confirm ratings.",
    "Switchgear SF6 pressure low — schedule refill.",
    "Relay coordination settings require review after network topology change.",
]


# ---------------------------------------------------------------------------
# TABLE 1: energy_assets  (500 rows)
# ---------------------------------------------------------------------------

def generate_energy_assets(n: int = 500) -> pd.DataFrame:
    print(f"  Generating energy_assets ({n} rows)...")
    asset_types = ["transformer", "substation", "cable", "pole", "meter"]
    # Weighted: meters and poles most common
    weights     = [0.20,         0.08,         0.15,   0.35, 0.22]

    rows = []
    for i in range(n):
        region = random.choices(REGIONS, weights=[22, 28, 22, 15, 13])[0]
        subregion = random.choice(SUBREGIONS[region])
        lat_c, lon_c, lat_r, lon_r = REGION_LAT_LON[region]
        atype = random.choices(asset_types, weights=weights)[0]
        manufacturer = random.choice(MANUFACTURERS)
        model = random.choice(ASSET_MODELS[atype])
        install_dt = rand_date("1985-01-01", "2023-12-31")
        last_insp = rand_date(max("2019-01-01", install_dt.strftime("%Y-%m-%d")), "2025-12-31")
        condition = round(np.clip(np.random.normal(6.5, 1.8), 1, 10), 1)
        # Older assets trend worse
        age_years = (datetime(2026, 1, 1) - install_dt).days / 365.25
        condition = round(float(np.clip(condition - age_years * 0.04 + random.uniform(-0.5, 0.5), 1.0, 10.0)), 1)
        capacity = {
            "transformer": random.choice([100, 200, 315, 500, 750, 1000, 2000, 5000]),
            "substation":  random.choice([10000, 25000, 50000, 100000, 200000]),
            "cable":       random.choice([50, 100, 150, 200, 300, 400]),
            "pole":        None,
            "meter":       random.choice([10, 20, 80, 160]),
        }[atype]
        # Pick notes: assets in poor condition get issue notes
        if condition < 4.0:
            note = random.choice(EQUIPMENT_ISSUES[:12])  # issue-heavy notes
        elif condition < 6.5:
            note = random.choice(EQUIPMENT_ISSUES)
        else:
            note = random.choice(EQUIPMENT_ISSUES[-6:])  # good-condition notes

        rows.append({
            "asset_id":           str(uuid.uuid4()),
            "asset_type":         atype,
            "asset_name":         f"{atype.title()}-{region}-{i+1:04d}",
            "region":             region,
            "subregion":          subregion,
            "installation_date":  install_dt.date().isoformat(),
            "manufacturer":       manufacturer,
            "model":              model,
            "rated_capacity_kva": capacity,
            "last_inspection_date": last_insp.date().isoformat(),
            "condition_score":    condition,
            "latitude":           round(-(lat_c + random.uniform(0, lat_r)), 5),
            "longitude":          round(  lon_c + random.uniform(-lon_r/2, lon_r), 5),
            "notes":              note,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 2: meter_readings  (50,000 rows) — NEM12-style
# ---------------------------------------------------------------------------

def generate_nmi(region: str) -> str:
    """Generate a plausible NMI (10 chars, starts with state prefix)."""
    prefix_map = {"VIC": "61", "NSW": "41", "QLD": "31", "SA": "21", "WA": "71"}
    prefix = prefix_map.get(region, "61")
    return prefix + "".join([str(random.randint(0, 9)) for _ in range(8)])


def generate_meter_readings(n: int = 50_000) -> pd.DataFrame:
    print(f"  Generating meter_readings ({n:,} rows)...")

    # Create ~500 distinct meters across regions
    n_meters = 500
    meter_pool = []
    for _ in range(n_meters):
        region = random.choices(REGIONS, weights=[22, 28, 22, 15, 13])[0]
        nmi = generate_nmi(region)
        meter_id = "MTR" + "".join([str(random.randint(0, 9)) for _ in range(7)])
        site_id  = "SITE" + str(random.randint(10000, 99999))
        ctype = random.choices(
            ["residential", "commercial", "industrial"],
            weights=[0.65, 0.25, 0.10]
        )[0]
        meter_pool.append((nmi, meter_id, site_id, region, ctype))

    # Base load profiles by customer type (30-min interval kWh)
    BASE_LOAD = {
        "residential": 0.3,
        "commercial":  2.5,
        "industrial":  18.0,
    }

    quality_flags = ["A", "A", "A", "A", "A", "E", "S", "N"]  # A heavily weighted

    rows = []
    for i in range(n):
        nmi, meter_id, site_id, region, ctype = random.choice(meter_pool)
        # Random datetime in 2024-2025
        dt = rand_date("2024-01-01", "2025-12-31")
        # Snap to 30-min interval
        dt = dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)
        # Hour-of-day load shape
        hour = dt.hour
        if ctype == "residential":
            tod_factor = 0.4 + 0.6 * (
                0.8 if 7 <= hour <= 9
                else 1.0 if 17 <= hour <= 21
                else 0.3
            )
        elif ctype == "commercial":
            tod_factor = 0.2 if hour < 7 or hour > 20 else 0.9 + 0.1 * random.random()
        else:  # industrial
            tod_factor = 0.85 + 0.15 * random.random()

        base = BASE_LOAD[ctype]
        interval_kwh = round(max(0.0, np.random.normal(base * tod_factor, base * 0.1)), 4)

        # Occasional anomalies for realism
        if random.random() < 0.005:
            interval_kwh = round(interval_kwh * random.uniform(3, 6), 4)  # demand spike
        elif random.random() < 0.003:
            interval_kwh = 0.0  # zero read / outage

        rows.append({
            "reading_id":       str(uuid.uuid4()),
            "nmi":              nmi,
            "meter_id":         meter_id,
            "reading_datetime": dt.isoformat(),
            "interval_kwh":     interval_kwh,
            "quality_flag":     random.choice(quality_flags),
            "site_id":          site_id,
            "customer_type":    ctype,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 3: outage_events  (2,000 rows)
# ---------------------------------------------------------------------------

CAUSE_DESCRIPTIONS = {
    "equipment_failure": [
        "Transformer failed due to insulation breakdown after 28 years of service. Post-incident analysis confirmed moisture ingress through degraded bushing seal.",
        "Circuit breaker mal-operated during routine switching sequence. Root cause: mechanical latch fatigue on main trip mechanism.",
        "Cable joint failure on 11kV underground circuit — XLPE splice integrity compromised following trenching works by third party three months prior.",
        "Protection relay mis-trip caused by CT secondary open circuit during maintenance access. Maintenance management process review initiated.",
        "Switchgear flashover triggered by contaminated busbar surface. Atmospheric salt pollution elevated following coastal storm event.",
        "Pole-mounted recloser lockout — auto-reclose function disabled in error after firmware update. Crew deployed for manual restoration.",
        "Fuse failure on 11kV overhead spur — overloaded following load transfer from adjacent feeder under planned outage conditions.",
        "Voltage regulator malfunction caused sustained over-voltage condition. Customer voltage complaints triggered investigation.",
        "Underground cable fault detected at 2.3 km from substation. TDR testing localised fault to road crossing duct section.",
        "SCADA communication loss to remote switching station delayed fault isolation by 42 minutes.",
    ],
    "weather": [
        "Severe thunderstorm with gusts exceeding 110 km/h brought down three 132kV towers across a 1.4 km section of transmission corridor.",
        "Lightning strike on unshielded 22kV overhead line caused conductor burndown at dead-end structure.",
        "Bushfire front crossed the transmission corridor, triggering two-pole flashover on 275kV circuit. Pre-emptive public safety power shutoff enacted for 8 feeders.",
        "Flooding inundated ground-mounted switchgear at zone substation. 600 mm above design flood level recorded.",
        "Ice accretion on conductors near Mount Buller feeder — progressive galloping led to phase-to-phase contact.",
        "Heatwave caused thermal overloading on three 11kV feeders serving Melbourne outer suburb load pocket.",
        "Salt spray deposited on insulator strings during northerly wind event — surface tracking caused fault on 66kV line.",
        "Cyclone-force winds in North Queensland caused widespread pole damage across 37 km of rural distribution network.",
        "Dust storm reduced visibility and deposited abrasive particulates in open-type switchgear — accelerated wear on contacts identified.",
        "Heavy rainfall caused landslip, undermining pole foundations on steep terrain section of distribution feeder.",
    ],
    "vegetation": [
        "Eucalyptus tree contact during high-wind event. Vegetation inspection history shows compliance with minimum clearance standards — extreme wind deflection beyond design assumption.",
        "Unplanned vegetation growth on private property contacted 11kV conductors — property owner notification and clearance order issued.",
        "Palm frond in high-wind conditions bridged gap between conductors on uninsulated overhead line in residential precinct.",
        "Weed tree fell across 22kV line — species not present during last annual patrol. Ground crew responded within target response time.",
        "Bamboo encroachment from adjacent residential boundary — multiple contacts in 12-month period. Formal notice issued to landowner.",
        "Tree fell across multiple spans during night storm. Difficult terrain access extended restoration time by 3.5 hours.",
        "Vegetation contact on 66kV line during prescribed burn — firefighting aircraft operating in same corridor; additional hazard for crews.",
    ],
    "third_party": [
        "Excavation contractor struck 11kV underground cable while trenching for gas main — DBYD lodgement confirmed, incorrect as-built drawings contributed to misalignment.",
        "Crane boom contact with 33kV overhead line on construction site adjacent to substation. Site access permit issued by network — subsequent investigation found boom height exceeded permit conditions.",
        "Vehicle strike on pole — B-double truck misjudged clearance on narrow rural road. Pole fractured at base; conductor fell to road surface.",
        "Vandalism at remote switching station — padlock cut and isolator operated without authorisation. Network access policy breach referred to police.",
        "Telecommunications contractor inadvertently disconnected control cable at zone substation while working in cable management area.",
        "Planned civil works by local council exposed and damaged cable duct bank — as-built records not provided to council prior to works.",
        "High-load transport escort failed to contact network operations for clearance confirmation — HV conductor contacted by oversized load.",
    ],
    "unknown": [
        "Fault cause under investigation — protection operated correctly, fault current consistent with phase-to-earth event. No obvious cause identified during daylight patrol.",
        "Transient fault — auto-reclose successful after single attempt. No damage or clear cause identified on patrol.",
        "Cause not determined following detailed post-event investigation. Historical fault record suggests intermittent insulation weakness on this circuit section.",
        "Fault occurred during night hours. Patrol conducted at first light — no cause identified. Thermal camera deployed on re-energisation.",
    ],
}

RESOLUTION_DESCRIPTIONS = [
    "Replacement transformer installed from strategic spare. Network restored within 8 hours of fault. Post-energisation monitoring in place for 72 hours.",
    "Damaged conductors reconductored over two-day planned outage window. Hot-line clamp used to restore partial supply ahead of full conductor replacement.",
    "Temporary bypass cable installed to restore supply while permanent joint repair scheduled. Excavation permit obtained; repair completed within 5 business days.",
    "Manual switching restored supply from alternative source. Defective equipment isolated and locked out pending engineering assessment.",
    "Fault located using TDR and cable sectionalisation. Failed joint excavated and replaced with factory-made joint kit. Pressure test passed.",
    "Circuit manually reconfigured from redundant path. Failed component removed and sent for post-incident investigation to OEM.",
    "Cleared vegetation and re-tensioned conductors where sag had reduced clearances. Inspection regime increased to 6-monthly for this span.",
    "Emergency crew mobilised overnight. Damaged poles replaced using hydraulic digger-derrick. Supply restored by 06:15 following morning.",
    "Protection settings reviewed and corrected following investigation. Coordination test conducted prior to re-energisation.",
    "Supply restored via generator bridge while cable fault repaired. Generator demobilised following successful cable repair and testing.",
]


def generate_outage_events(n: int = 2_000) -> pd.DataFrame:
    print(f"  Generating outage_events ({n:,} rows)...")
    cause_cats = list(CAUSE_DESCRIPTIONS.keys())
    cause_weights = [0.35, 0.28, 0.15, 0.12, 0.10]

    rows = []
    for _ in range(n):
        region = random.choices(REGIONS, weights=[22, 28, 22, 15, 13])[0]
        subregion = random.choice(SUBREGIONS[region])
        event_type = random.choices(
            ["planned", "unplanned", "emergency"],
            weights=[0.30, 0.55, 0.15]
        )[0]
        cause_cat = random.choices(cause_cats, weights=cause_weights)[0]

        # Duration distribution: log-normal, ~minutes
        if event_type == "planned":
            duration_min = round(float(np.random.lognormal(4.5, 0.6)))  # ~90 min typical
        elif event_type == "emergency":
            duration_min = round(float(np.random.lognormal(5.0, 0.8)))  # ~150 min
        else:
            duration_min = round(float(np.random.lognormal(4.2, 0.7)))  # ~67 min
        duration_min = max(1, min(duration_min, 4320))  # cap at 3 days

        start_dt = rand_date("2023-01-01", "2025-12-31")
        end_dt   = start_dt + timedelta(minutes=duration_min)

        # Affected customers ~ log-normal, varies by region density
        base_cust = {"VIC": 600, "NSW": 700, "QLD": 350, "SA": 200, "WA": 150}[region]
        affected = max(1, int(np.random.lognormal(np.log(base_cust), 0.9)))

        # SAIDI/SAIFI — AEMC/AER style
        saidi = round(affected * duration_min / 60 / 1_000_000 * random.uniform(0.8, 1.2), 6)
        saifi = round(affected / 1_000_000 * random.uniform(0.8, 1.2), 6)

        rows.append({
            "event_id":            str(uuid.uuid4()),
            "event_type":          event_type,
            "region":              region,
            "subregion":           subregion,
            "affected_customers":  affected,
            "start_time":          start_dt.isoformat(),
            "end_time":            end_dt.isoformat(),
            "duration_minutes":    duration_min,
            "cause_category":      cause_cat,
            "cause_description":   random.choice(CAUSE_DESCRIPTIONS[cause_cat]),
            "resolution_description": random.choice(RESOLUTION_DESCRIPTIONS),
            "saidi_minutes":       saidi,
            "saifi_count":         saifi,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 4: maintenance_work_orders  (3,000 rows)
# ---------------------------------------------------------------------------

MAINTENANCE_DESCRIPTIONS = [
    "Annual thermographic inspection of 11kV ring main unit — all connections within acceptable temperature limits.",
    "Scheduled oil sampling and dissolved gas analysis (DGA) on 33kV power transformer. Results pending laboratory analysis.",
    "Replace all primary fuse links on overhead distribution feeder following end-of-life assessment.",
    "Ground-level visual inspection of pole line — check for storm damage, vegetation encroachment, and structural defects.",
    "Clean and test protection relay — calibrate overcurrent and earth-fault trip thresholds per current settings file.",
    "Switchgear maintenance: lubrication of mechanism, contact resistance measurement, SF6 pressure check.",
    "Cable joint excavation and re-termination at 66kV underground circuit following water ingress identification.",
    "Upgrade pole-top hardware to meet updated network clearance standards — install insulated cross-arms.",
    "Inspection and torque-check of all bolted connections on 132kV bus section following conductor galloping incident.",
    "Install wildlife protection devices on exposed live conductors at bird-strike-prone section of 11kV overhead line.",
    "Replace deteriorated conductor on 300 m span — conductor grade reduced from AAAC to below acceptable limit.",
    "Commission new protection scheme for ring feed arrangement — loop automation configuration and testing.",
    "Earth testing of transmission tower footings — ensure resistance below 10 Ω per specification.",
    "SCADA RTU battery replacement — UPS autonomy test passed post-replacement.",
    "Inspect and service on-load tap changer (OLTC) — check drive mechanism, contacts, and oil compartment.",
    "Emergency repair to storm-damaged pole — excavate, set, and back-fill new Class 3 hardwood pole.",
    "Reconductor 2.5 km section of rural feeder — upgrade to larger conductor size to improve voltage regulation.",
    "Install overhead line spacers on bundled conductor to prevent clashing in high-wind conditions.",
    "Substation security audit — CCTV operational, perimeter fencing integrity, lock audit.",
    "Battery string replacement in protection DC system — individual cell voltage and internal resistance within specification.",
]

FINDINGS = [
    "No defects found. Asset in good condition. Recommend next scheduled inspection in 12 months.",
    "Insulation resistance below threshold — recommend replacement before next scheduled maintenance cycle.",
    "Oil sample shows elevated dissolved hydrogen: 85 ppm. Repeat DGA in 3 months; schedule investigation if trend continues.",
    "Three fuse links approaching end of service life — replacement scheduled within 30 days.",
    "Two intermediate cross-arms showing advanced weathering. Replacement required within 6 months to maintain clearance.",
    "Protection relay trip time confirmed within tolerance. Settings match approved coordination study.",
    "Cable sheath integrity verified — no evidence of moisture ingress. Joint resealed with approved compound.",
    "Vegetation clearance adequate for current conditions. Note: summer growth may reduce clearance by October.",
    "Hot spot identified at phase B terminal — thermal image attached. Torque and re-test prior to closing out work order.",
    "OLTC mechanism stiff on positions 3 and 4. Apply approved lubricant — retest confirmed full range of travel.",
    "Corrosion found on earth rod connection — cleaned and re-terminated. Measured resistance: 7.2 Ω (within 10 Ω limit).",
    "All connections within specification. No evidence of partial discharge or tracking on insulators.",
    "Minor bird nesting detected in cable management duct — removed and deterrent installed.",
    "Structure footing exposed by erosion — restore with compacted fill and inspect after next rainfall event.",
    "Meter reading discrepancy noted — field check confirms meter operating correctly, likely data comms issue at head-end.",
]

MATERIALS = [
    "Conductor — ACSR Lark 150mm², 200m; 6 x strain insulators; compression fittings.",
    "Transformer oil — IEC 60296 mineral, 800 L; degassing and reconditioning reagents.",
    "Fuse links — 100A HRC (12 off); fuse carriers; insulating gloves.",
    "Cross-arm hardwood Class 2, 2.4m (4 off); bolts and washers; galvanised staples.",
    "Cable joint kit — heat-shrink straight joint, 11kV XLPE (2 off); joint compound.",
    "Protection relay — Schneider MiCOM P14D; CT secondary test plugs.",
    "Pole — Class 3 hardwood 12m (1 off); footings concrete 0.5 m3.",
    "Wildlife protection — silicon rubber insulating covers (24 off); P-clips.",
    "Spacers — oval-profile 11kV bundled conductor spacer (40 off); installation tool.",
    "No materials consumed — inspection and condition assessment only.",
    "SF6 gas — grade 2.8 industrial (5 kg); refill adapter; leak detector.",
    "Battery cells — 2V, 200Ah valve-regulated lead-acid (12 off); terminal grease.",
    "Earth rod — copper-bonded 16mm x 1.5m (2 off); compression coupler; driving cap.",
    "SCADA RTU backup battery — 12V 7Ah sealed lead-acid (4 off).",
]

CONTRACTORS = [
    "AusGrid Network Services", "ElectroPower Pty Ltd", "Ventia Infrastructure",
    "Downer EDI", "Fulton Hogan", "John Holland Group", "CPB Contractors",
    "ServiceStream", "Zinfra Group", "Lendlease Engineering",
]


def generate_maintenance_work_orders(assets_df: pd.DataFrame, n: int = 3_000) -> pd.DataFrame:
    print(f"  Generating maintenance_work_orders ({n:,} rows)...")
    asset_ids = assets_df["asset_id"].tolist()

    work_types   = ["inspection", "repair", "replacement", "emergency"]
    wt_weights   = [0.45, 0.30, 0.15, 0.10]
    priorities   = ["P1", "P2", "P3", "P4"]
    p_weights    = [0.05, 0.20, 0.50, 0.25]
    statuses     = ["open", "in_progress", "completed", "cancelled"]
    st_weights   = [0.05, 0.10, 0.82, 0.03]

    rows = []
    for _ in range(n):
        asset_id  = random.choice(asset_ids)
        work_type = random.choices(work_types, weights=wt_weights)[0]
        priority  = random.choices(priorities, weights=p_weights)[0]

        # Emergency always P1 or P2
        if work_type == "emergency":
            priority = random.choice(["P1", "P2"])

        status = random.choices(statuses, weights=st_weights)[0]

        created_dt = rand_date("2022-01-01", "2025-12-01")

        # Completion date
        if status == "completed":
            # P1: complete in hours/days; P4: weeks
            lead_days = {"P1": 1, "P2": 5, "P3": 30, "P4": 90}[priority]
            completed_dt = created_dt + timedelta(days=random.randint(0, lead_days * 2))
            completed_dt = min(completed_dt, datetime(2025, 12, 31))
        else:
            completed_dt = None

        crew_size = random.choices([1, 2, 3, 4, 5, 6], weights=[10, 30, 30, 20, 7, 3])[0]
        tech_id   = f"TECH{random.randint(1000, 9999)}"
        is_contractor = random.random() < 0.35

        # Cost: varies by work type and priority
        base_cost = {
            "inspection":  800,
            "repair":      4_500,
            "replacement": 18_000,
            "emergency":   25_000,
        }[work_type]
        cost = round(base_cost * crew_size * float(np.random.lognormal(0, 0.4)), 2)

        rows.append({
            "work_order_id":    f"WO-{str(uuid.uuid4())[:8].upper()}",
            "asset_id":         asset_id,
            "work_type":        work_type,
            "priority":         priority,
            "status":           status,
            "created_date":     created_dt.date().isoformat(),
            "completed_date":   completed_dt.date().isoformat() if completed_dt else None,
            "technician_id":    tech_id,
            "crew_size":        crew_size,
            "description":      random.choice(MAINTENANCE_DESCRIPTIONS),
            "findings":         random.choice(FINDINGS) if status in ("completed", "in_progress") else None,
            "materials_used":   random.choice(MATERIALS) if work_type != "inspection" else "No materials consumed — inspection and condition assessment only.",
            "cost_aud":         cost,
            "contractor":       is_contractor,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 5: regulatory_reports  (500 rows)
# ---------------------------------------------------------------------------

REPORT_CONTENT_TEMPLATES = {
    "SAIDI_monthly": (
        "Monthly SAIDI Performance Report — {period}. "
        "Total System Average Interruption Duration Index for the reporting period: {saidi:.2f} minutes. "
        "Target threshold per Distribution Licence Condition 7.3: {target:.1f} minutes. "
        "Performance is {status} target. "
        "Major contributing event categories: equipment failure ({ef_pct}%), weather-related ({wx_pct}%), vegetation ({veg_pct}%). "
        "Three significant outage events contributed {sig_pct}% of total SAIDI. "
        "Corrective action plans active for reliability hotspot feeders F47-{region} and F83-{region}. "
        "Next reporting period data to be submitted by the 15th of the following month in accordance with AER reporting guidelines."
    ),
    "SAIFI_annual": (
        "Annual SAIFI Performance Summary — Financial Year {period}. "
        "System Average Interruption Frequency Index: {saifi:.4f} interruptions per customer. "
        "Regulatory target: {target:.4f} interruptions per customer. Status: {status}. "
        "Total customer-interruptions recorded: {ci:,}. "
        "Frequency performance improvement of {delta:.1f}% achieved compared to prior year through targeted pole-line vegetation management programme and overhead line automation upgrades. "
        "Detailed event-level data appended as Schedule 1 per AER Electricity Distribution Network Service Providers Reporting Guidelines. "
        "Report prepared by Network Regulation team and certified by General Manager Network Services."
    ),
    "AER_performance": (
        "AER Annual Performance Report — {period}. "
        "Submitted pursuant to the National Electricity Rules clause 7.3.1 and Distribution Determination obligations. "
        "Capital expenditure for the period: ${capex:.1f}M (approved allowance: ${capex_allow:.1f}M). "
        "Operating expenditure: ${opex:.1f}M (approved allowance: ${opex_allow:.1f}M). "
        "Network reliability: SAIDI {saidi:.2f} min (target {target:.1f} min), SAIFI {saifi:.4f} (target {t_saifi:.4f}). "
        "Customer complaints: {complaints} (prior year: {prev_complaints}). "
        "Demand-side participation programme enrolled {dsm:,} customers, reducing peak demand by {peak_red:.1f} MW. "
        "Pricing methodology compliant with approved tariff structure statement."
    ),
    "AEMO_market": (
        "AEMO Market Operations Report — {period}. "
        "Submitted in accordance with NER clause 3.7.4 and AEMO Participant Guidelines. "
        "Total metered energy injected to NEM: {injection:.1f} GWh. "
        "Demand response activations: {dr} events, total volume {dr_vol:.1f} MWh. "
        "Frequency performance: {freq_pass:.1f}% of settlement intervals within ±0.15 Hz. "
        "Dispatch non-compliance events: {dne}. "
        "Causer pays liability for period: ${cp_liability:,.0f}. "
        "Market systems availability: {avail:.2f}%. "
        "Data quality validation completed; no material errors or omissions identified. All metering data submitted within statutory timeframes."
    ),
    "ESC_compliance": (
        "Energy and Water Ombudsman / ESC Compliance Report — {period}. "
        "Submitted pursuant to Electricity Distribution Code s4.2 and Electricity Industry Act 2000 (Vic). "
        "Customer complaints received: {complaints}. Complaints resolved within 10 business days: {resolved_pct:.0f}%. "
        "Unplanned interruptions — guaranteed service levels met: {gsl_met:.0f}%. GSL payments made: {gsl_payments} totalling ${gsl_value:,.0f}. "
        "Wrongful disconnection events: {wd}. Hardship programme enrolments: {hardship:,}. "
        "Planned interruption notice compliance: {notice_pct:.0f}% (minimum 4 business days' notice). "
        "Privacy compliance: no reportable data breaches under the Privacy Act 1988 during the period. "
        "Report certified by Chief Regulatory Officer and submitted via ESC Online portal."
    ),
}

JURISDICTIONS = {"VIC": "VIC", "NSW": "NSW", "QLD": "QLD", "SA": "SA", "WA": "WA", "AEMO": "AEMO"}

REPORT_JURISDICTION_MAP = {
    "SAIDI_monthly":   ["VIC", "NSW", "QLD", "SA", "WA"],
    "SAIFI_annual":    ["VIC", "NSW", "QLD", "SA", "WA"],
    "AER_performance": ["VIC", "NSW", "QLD", "SA", "WA"],
    "AEMO_market":     ["AEMO"],
    "ESC_compliance":  ["VIC"],
}

SUBMITTERS = [
    "J.Thornton@network.com.au", "S.Mehta@regulation.com.au", "P.Kavanagh@network.com.au",
    "L.Anderson@corp.com.au", "R.Krishnamurthy@network.com.au", "D.O'Brien@regulation.com.au",
    "F.Nakamura@corp.com.au", "A.Vasquez@network.com.au", "C.Williamson@regulation.com.au",
]


def _random_content(rtype: str, region: str, period: str) -> str:
    template = REPORT_CONTENT_TEMPLATES.get(rtype, REPORT_CONTENT_TEMPLATES["SAIDI_monthly"])
    saidi = round(random.uniform(25, 120), 2)
    saifi = round(random.uniform(0.4, 1.8), 4)
    target_saidi = round(random.uniform(80, 140), 1)
    target_saifi = round(random.uniform(1.2, 2.0), 4)
    is_compliant = saidi <= target_saidi
    status_word = "within" if is_compliant else "exceeding"
    ef_pct  = random.randint(25, 45)
    wx_pct  = random.randint(20, 40)
    veg_pct = 100 - ef_pct - wx_pct
    sig_pct = random.randint(30, 60)
    ci  = random.randint(5_000, 200_000)
    delta = round(random.uniform(-5, 15), 1)
    capex = round(random.uniform(80, 400), 1)
    capex_allow = round(capex * random.uniform(0.9, 1.2), 1)
    opex  = round(random.uniform(60, 200), 1)
    opex_allow = round(opex * random.uniform(0.9, 1.15), 1)
    complaints = random.randint(50, 3000)
    prev_complaints = random.randint(50, 3000)
    dsm  = random.randint(500, 8000)
    peak_red = round(random.uniform(5, 80), 1)
    injection = round(random.uniform(500, 5000), 1)
    dr = random.randint(0, 20)
    dr_vol = round(random.uniform(0, 500), 1)
    freq_pass = round(random.uniform(95, 99.9), 1)
    dne  = random.randint(0, 10)
    cp_liability = round(random.uniform(0, 250000), 0)
    avail = round(random.uniform(99.0, 99.99), 2)
    resolved_pct = round(random.uniform(85, 100), 0)
    gsl_met = round(random.uniform(90, 100), 0)
    gsl_payments = random.randint(0, 200)
    gsl_value = round(random.uniform(0, 50000), 0)
    wd = random.randint(0, 10)
    hardship = random.randint(100, 5000)
    notice_pct = round(random.uniform(88, 100), 0)
    t_saifi = target_saifi
    try:
        return template.format(
            period=period, saidi=saidi, saifi=saifi, target=target_saidi, t_saifi=t_saifi,
            status=status_word, ef_pct=ef_pct, wx_pct=wx_pct, veg_pct=veg_pct,
            sig_pct=sig_pct, region=region, ci=ci, delta=delta, capex=capex,
            capex_allow=capex_allow, opex=opex, opex_allow=opex_allow,
            complaints=complaints, prev_complaints=prev_complaints, dsm=dsm,
            peak_red=peak_red, injection=injection, dr=dr, dr_vol=dr_vol,
            freq_pass=freq_pass, dne=dne, cp_liability=cp_liability, avail=avail,
            resolved_pct=resolved_pct, gsl_met=gsl_met, gsl_payments=gsl_payments,
            gsl_value=gsl_value, wd=wd, hardship=hardship, notice_pct=notice_pct,
        )
    except KeyError:
        return template  # fallback


def generate_regulatory_reports(n: int = 500) -> pd.DataFrame:
    print(f"  Generating regulatory_reports ({n:,} rows)...")
    report_types = list(REPORT_CONTENT_TEMPLATES.keys())
    rt_weights   = [0.25, 0.20, 0.20, 0.20, 0.15]

    rows = []
    for _ in range(n):
        rtype = random.choices(report_types, weights=rt_weights)[0]
        jurisdictions = REPORT_JURISDICTION_MAP[rtype]
        jurisdiction  = random.choice(jurisdictions)
        region        = jurisdiction if jurisdiction != "AEMO" else random.choice(REGIONS)

        # Period
        year  = random.randint(2022, 2025)
        month = random.randint(1, 12)
        if "monthly" in rtype.lower():
            period = f"{year}-{month:02d}"
        elif "annual" in rtype.lower() or "performance" in rtype.lower():
            period = f"FY{year-2000}{(year-2000+1):02d}"
        else:
            period = f"Q{random.randint(1,4)}-{year}"

        submit_dt = rand_date(f"{year}-{month:02d}-01", "2026-01-31")
        submit_dt = min(submit_dt, datetime(2026, 1, 31))

        status = random.choices(
            ["draft", "submitted", "accepted", "rejected"],
            weights=[0.05, 0.15, 0.75, 0.05]
        )[0]

        compliance = random.choices(
            ["compliant", "non_compliant", "pending_review"],
            weights=[0.78, 0.12, 0.10]
        )[0]
        if status == "rejected":
            compliance = "non_compliant"

        rows.append({
            "report_id":         f"RPT-{str(uuid.uuid4())[:8].upper()}",
            "report_type":       rtype,
            "reporting_period":  period,
            "region":            region,
            "jurisdiction":      jurisdiction,
            "submission_date":   submit_dt.date().isoformat(),
            "submitted_by":      random.choice(SUBMITTERS),
            "status":            status,
            "report_content":    _random_content(rtype, region, period),
            "compliance_status": compliance,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 6: policy_documents  (50 rows)
# ---------------------------------------------------------------------------

POLICY_CONTENT = {
    "network_access_policy": [
        (
            "Network Access Policy v{ver} — {dept}\n\n"
            "1. PURPOSE\nThis policy establishes the conditions under which third parties, contractors, and internal personnel may access the {dept} high-voltage network, substations, and associated infrastructure.\n\n"
            "2. SCOPE\nApplicable to all staff, contractors, visitors, and authorised third parties performing work on or near electrical infrastructure rated 415V and above.\n\n"
            "3. AUTHORISATION REQUIREMENTS\nAll network access must be authorised by a Network Access Permit (NAP) issued by the duty Network Operations Controller. "
            "No work may commence without a valid NAP. Permits are valid for the stated shift period only and must be surrendered upon completion of work.\n\n"
            "4. MINIMUM APPROACH DISTANCES\nPersonnel must maintain minimum approach distances as specified in AS/NZS 4836 — Safe Working on or near Low-Voltage Electrical Installations, "
            "and the relevant state network safety rules.\n\n"
            "5. COMPLIANCE\nBreaches of this policy may result in removal from site, suspension of access privileges, and disciplinary or legal action. "
            "All breaches must be reported to the Network Operations Manager within 4 hours."
        ),
    ],
    "safety_procedure": [
        (
            "Safety Procedure SP-{ver} — Isolation and Earthing of High-Voltage Equipment — {dept}\n\n"
            "1. OBJECTIVE\nTo prevent injury or death from unintended energisation of high-voltage equipment during maintenance or construction activities.\n\n"
            "2. APPLICABILITY\nAll authorised HV switching operators and maintenance personnel working on assets rated 1kV to 275kV.\n\n"
            "3. PROCEDURE\n"
            "Step 1: Obtain isolation authority from the Network Operations Controller.\n"
            "Step 2: Identify and confirm correct isolation points using approved single-line diagrams.\n"
            "Step 3: Operate isolation devices in the correct sequence — open circuit breaker, open isolator, apply locks and danger tags.\n"
            "Step 4: Apply high-voltage earths to all potentially energised conductors on both source and load sides of work zone.\n"
            "Step 5: Test for absence of voltage using approved HV test equipment before commencing work.\n\n"
            "4. RESTORATION\nRestoration must follow reverse sequence. All earths must be removed and accounted for. Confirmation must be given to NOC before any switching.\n\n"
            "5. REFERENCES\nAS/NZS 3000, Electricity Safety Act 1998, Network Safety Rules v4.2."
        ),
    ],
    "emergency_response": [
        (
            "Emergency Response Plan — Major Network Incident — {dept} v{ver}\n\n"
            "1. ACTIVATION CRITERIA\nThis plan is activated for any event affecting more than 10,000 customers, any 132kV or above circuit fault, "
            "or any event declared a Public Safety Power Shutoff (PSPS).\n\n"
            "2. INCIDENT COMMAND\nThe Network Operations Manager assumes the role of Incident Commander on activation. "
            "An Emergency Response Team (ERT) is stood up within 30 minutes, comprising representatives from Operations, Engineering, Media, and Customer Service.\n\n"
            "3. NOTIFICATION\nWithin 15 minutes of activation: notify General Manager Networks, AER (if affecting reliability targets), AEMO (if affecting wholesale market), "
            "state energy regulator, and emergency services if life safety risk exists.\n\n"
            "4. CUSTOMER COMMUNICATIONS\nEstimated restoration times must be published via SMS, web, and IVR within 30 minutes. Updates every 60 minutes until restoration.\n\n"
            "5. POST-INCIDENT\nA post-incident review must be completed within 5 business days. Findings and corrective actions registered in the asset management system."
        ),
    ],
    "data_governance": [
        (
            "Data Governance Policy v{ver} — {dept}\n\n"
            "1. PURPOSE\nEstablish accountabilities, standards, and controls for the management of data assets across the organisation, "
            "ensuring data quality, security, lineage, and regulatory compliance.\n\n"
            "2. DATA CLASSIFICATION\nAll data assets must be classified as: Public, Internal, Restricted, or Confidential. "
            "Customer metering data, personal information, and grid operational data are classified Restricted by default.\n\n"
            "3. DATA STEWARDSHIP\nEach business unit must appoint a Data Steward responsible for cataloguing, quality monitoring, and access management of their data products. "
            "Data Stewards report quarterly to the Data Governance Committee.\n\n"
            "4. RETENTION AND DISPOSAL\nMeter data: retain for 7 years per NEM Rules. Customer personal data: retain for 7 years post-contract end. "
            "Operational logs: retain for 3 years. Disposal must be documented and approved.\n\n"
            "5. PRIVACY\nAll data handling involving personal information must comply with the Privacy Act 1988 (Cth), Australian Privacy Principles, and state privacy legislation. "
            "Privacy Impact Assessments are mandatory for new data sharing arrangements and analytics use cases involving personal data."
        ),
    ],
    "ai_usage_policy": [
        (
            "Artificial Intelligence Usage Policy v{ver} — {dept}\n\n"
            "1. PURPOSE\nGovern the responsible use of artificial intelligence (AI) and machine learning (ML) systems across the organisation to ensure safety, "
            "fairness, transparency, and compliance with regulatory obligations.\n\n"
            "2. PROHIBITED USES\nAI must not be used to: make fully automated decisions that affect customer financial outcomes without human review; "
            "process sensitive personal information without a completed Privacy Impact Assessment; "
            "operate or directly control protection systems without certification under IEC 61511 functional safety standards.\n\n"
            "3. AI RISK TIERS\nTier 1 (High Risk): AI systems that inform regulatory submissions, affect safety-critical operations, or process >10,000 customer records. "
            "Require Board approval, independent validation, and ongoing monitoring.\n"
            "Tier 2 (Medium Risk): AI systems used for internal operational decisions. Require GM approval and documented testing.\n"
            "Tier 3 (Low Risk): AI productivity tools, summarisation, and document assistance. Require IT risk assessment only.\n\n"
            "4. DATA RESIDENCY\nAll AI model training, inference, and data processing involving customer or grid data must occur within Australian jurisdiction. "
            "Use of offshore AI services requires CISO approval and a Data Processing Agreement meeting Australian Privacy Principle 8 requirements.\n\n"
            "5. HUMAN OVERSIGHT\nAll AI-generated outputs that inform consequential decisions must be reviewed by a qualified human before action. "
            "AI systems must log all inputs and outputs for audit purposes for a minimum of 3 years.\n\n"
            "6. REVIEW\nThis policy is reviewed annually or following any material AI incident or regulatory change."
        ),
    ],
}

DEPARTMENTS = [
    "Network Operations", "Asset Management", "Regulatory Affairs",
    "Information Technology", "Safety and Environment", "Customer Experience",
    "Engineering Services", "Finance and Strategy",
]


def generate_policy_documents(n: int = 50) -> pd.DataFrame:
    print(f"  Generating policy_documents ({n} rows)...")
    doc_types = list(POLICY_CONTENT.keys())
    dt_weights = [0.20, 0.20, 0.15, 0.25, 0.20]

    rows = []
    for i in range(n):
        dtype = random.choices(doc_types, weights=dt_weights)[0]
        dept  = random.choice(DEPARTMENTS)
        version = f"{random.randint(1, 4)}.{random.randint(0, 9)}"
        effective_dt = rand_date("2018-01-01", "2024-12-31")
        review_dt    = effective_dt + timedelta(days=random.choice([365, 730, 1095]))
        classification = random.choices(
            ["internal", "restricted", "public"],
            weights=[0.55, 0.35, 0.10]
        )[0]

        template = random.choice(POLICY_CONTENT[dtype])
        content  = template.format(ver=version, dept=dept)

        rows.append({
            "doc_id":         f"DOC-{i+1:04d}",
            "doc_type":       dtype,
            "title":          f"{dtype.replace('_', ' ').title()} — {dept} v{version}",
            "department":     dept,
            "effective_date": effective_dt.date().isoformat(),
            "review_date":    review_dt.date().isoformat(),
            "content":        content,
            "version":        version,
            "classification": classification,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("AU AI Workshops — Sample Data Generator")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    # 1. energy_assets
    assets_df = generate_energy_assets(500)
    out = OUTPUT_DIR / "energy_assets.csv"
    assets_df.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(assets_df):,} rows)")

    # 2. meter_readings
    readings_df = generate_meter_readings(50_000)
    out = OUTPUT_DIR / "meter_readings.csv"
    readings_df.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(readings_df):,} rows)")

    # 3. outage_events
    outages_df = generate_outage_events(2_000)
    out = OUTPUT_DIR / "outage_events.csv"
    outages_df.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(outages_df):,} rows)")

    # 4. maintenance_work_orders
    work_orders_df = generate_maintenance_work_orders(assets_df, 3_000)
    out = OUTPUT_DIR / "maintenance_work_orders.csv"
    work_orders_df.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(work_orders_df):,} rows)")

    # 5. regulatory_reports
    reports_df = generate_regulatory_reports(500)
    out = OUTPUT_DIR / "regulatory_reports.csv"
    reports_df.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(reports_df):,} rows)")

    # 6. policy_documents
    policies_df = generate_policy_documents(50)
    out = OUTPUT_DIR / "policy_documents.csv"
    policies_df.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(policies_df):,} rows)")

    print("=" * 60)
    print("Done. Summary:")
    print(f"  energy_assets:           {len(assets_df):>7,} rows")
    print(f"  meter_readings:          {len(readings_df):>7,} rows")
    print(f"  outage_events:           {len(outages_df):>7,} rows")
    print(f"  maintenance_work_orders: {len(work_orders_df):>7,} rows")
    print(f"  regulatory_reports:      {len(reports_df):>7,} rows")
    print(f"  policy_documents:        {len(policies_df):>7,} rows")
    total = sum([len(assets_df), len(readings_df), len(outages_df),
                 len(work_orders_df), len(reports_df), len(policies_df)])
    print(f"  TOTAL:                   {total:>7,} rows")
    print("=" * 60)


if __name__ == "__main__":
    main()
