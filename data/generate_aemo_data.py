"""
Generate AEMO/NEM synthetic data for the Databricks AU AI Workshops.
Session 3 (AEMO Business User) and Workshop 2c (MCP Agents).

Usage:
    pip install pandas numpy
    python generate_aemo_data.py

Outputs CSVs to ./data/sample_data/aemo/ (relative to this script's location).
No Databricks connection required — pure local generation.
"""

import os
import random
import textwrap
from datetime import datetime, timedelta
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
OUTPUT_DIR = SCRIPT_DIR / "sample_data" / "aemo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# NEM reference data
# ---------------------------------------------------------------------------

REGIONS = ["NSW1", "VIC1", "QLD1", "SA1", "TAS1"]

# Map NEM region ID -> state abbreviation
REGION_STATE = {
    "NSW1": "NSW",
    "VIC1": "VIC",
    "QLD1": "QLD",
    "SA1":  "SA",
    "TAS1": "TAS",
}

# Realistic AEMO-style DUIDs with fuel type and station details
# (duid, station_name, fuel_type, state, registered_capacity_mw, participant_id, connection_point_id)
GENERATOR_REGISTRY = [
    # Coal — NSW
    ("BAYSW1",  "Bayswater",            "coal",    "NSW", 660.0,  "AGL_ENERGY",       "BAYSW_CP"),
    ("BAYSW2",  "Bayswater",            "coal",    "NSW", 660.0,  "AGL_ENERGY",       "BAYSW_CP"),
    ("BAYSW3",  "Bayswater",            "coal",    "NSW", 660.0,  "AGL_ENERGY",       "BAYSW_CP"),
    ("BAYSW4",  "Bayswater",            "coal",    "NSW", 660.0,  "AGL_ENERGY",       "BAYSW_CP"),
    ("ERGT01",  "Eraring",              "coal",    "NSW", 720.0,  "ORIGIN",           "ERGT_CP"),
    ("ERGT02",  "Eraring",              "coal",    "NSW", 720.0,  "ORIGIN",           "ERGT_CP"),
    ("ERGT03",  "Eraring",              "coal",    "NSW", 720.0,  "ORIGIN",           "ERGT_CP"),
    ("ERGT04",  "Eraring",              "coal",    "NSW", 720.0,  "ORIGIN",           "ERGT_CP"),
    ("VALES1",  "Vales Point",          "coal",    "NSW", 660.0,  "DELTA_ELECTRICITY","VALES_CP"),
    ("VALES2",  "Vales Point",          "coal",    "NSW", 660.0,  "DELTA_ELECTRICITY","VALES_CP"),
    # Coal — VIC
    ("LOYA1",   "Loy Yang A",           "coal",    "VIC", 560.0,  "AGL_ENERGY",       "LOYA_CP"),
    ("LOYA2",   "Loy Yang A",           "coal",    "VIC", 560.0,  "AGL_ENERGY",       "LOYA_CP"),
    ("LOYA3",   "Loy Yang A",           "coal",    "VIC", 560.0,  "AGL_ENERGY",       "LOYA_CP"),
    ("LOYA4",   "Loy Yang A",           "coal",    "VIC", 560.0,  "AGL_ENERGY",       "LOYA_CP"),
    ("LOYB1",   "Loy Yang B",           "coal",    "VIC", 500.0,  "ENERGY_AUSTRALIA", "LOYB_CP"),
    ("LOYB2",   "Loy Yang B",           "coal",    "VIC", 500.0,  "ENERGY_AUSTRALIA", "LOYB_CP"),
    ("HAZEL1",  "Hazelwood",            "coal",    "VIC", 200.0,  "ENERGY_AUSTRALIA", "HAZEL_CP"),
    # Coal — QLD
    ("CALL1",   "Callide B",            "coal",    "QLD", 350.0,  "CS_ENERGY",        "CALL_CP"),
    ("CALL2",   "Callide B",            "coal",    "QLD", 350.0,  "CS_ENERGY",        "CALL_CP"),
    ("TARONG1", "Tarong",               "coal",    "QLD", 443.0,  "STANWELL",         "TARONG_CP"),
    ("TARONG2", "Tarong",               "coal",    "QLD", 443.0,  "STANWELL",         "TARONG_CP"),
    ("TARONG3", "Tarong",               "coal",    "QLD", 443.0,  "STANWELL",         "TARONG_CP"),
    ("TARONG4", "Tarong",               "coal",    "QLD", 443.0,  "STANWELL",         "TARONG_CP"),
    # Gas — NSW
    ("TALLWN2", "Tallawarra B",         "gas",     "NSW", 316.0,  "ENERGY_AUSTRALIA", "TALLWN_CP"),
    ("OCGT1",   "Uranquinty",           "gas",     "NSW", 160.0,  "ORIGIN",           "URANQ_CP"),
    ("OCGT2",   "Uranquinty",           "gas",     "NSW", 160.0,  "ORIGIN",           "URANQ_CP"),
    # Gas — VIC
    ("VPML",    "Valley Power",         "gas",     "VIC", 300.0,  "SNOWY_HYDRO",      "VPML_CP"),
    ("JBUTNS1", "Jeeralang",            "gas",     "VIC", 228.0,  "ENERGY_AUSTRALIA", "JEERL_CP"),
    ("MORTLK1", "Mortlake",             "gas",     "VIC", 282.5,  "ORIGIN",           "MORTL_CP"),
    ("MORTLK2", "Mortlake",             "gas",     "VIC", 282.5,  "ORIGIN",           "MORTL_CP"),
    # Gas — SA
    ("AGLHAL",  "Hallett",              "gas",     "SA",  203.0,  "AGL_ENERGY",       "HALT_CP"),
    ("AGLSOM",  "Somerton",             "gas",     "SA",  160.0,  "AGL_ENERGY",       "SOMT_CP"),
    ("LADBROK1","Ladbroke Grove",       "gas",     "SA",  80.0,   "ERM_POWER",        "LADB_CP"),
    ("PELICAN1","Pelican Point",        "gas",     "SA",  479.0,  "ENGIE",            "PELI_CP"),
    # Gas — QLD
    ("BRAEMAR1","Braemar",              "gas",     "QLD", 450.0,  "ORIGIN",           "BRAE_CP"),
    ("BRAEMAR2","Braemar",              "gas",     "QLD", 450.0,  "ORIGIN",           "BRAE_CP"),
    ("KAREEYA1","Kareeya",              "gas",     "QLD", 88.5,   "CS_ENERGY",        "KARE_CP"),
    # Wind — SA
    ("HDWF1",   "Hornsdale Wind Farm",  "wind",    "SA",  315.0,  "AGL_ENERGY",       "HDWF_CP"),
    ("HDWF2",   "Hornsdale Wind Farm",  "wind",    "SA",  99.0,   "AGL_ENERGY",       "HDWF_CP"),
    ("CLOVER1", "Clover Hill Wind Farm","wind",    "SA",  100.0,  "ERM_POWER",        "CLOV_CP"),
    ("MTMILLAR","Mt Millar Wind Farm",  "wind",    "SA",  70.0,   "AGL_ENERGY",       "MTML_CP"),
    # Wind — VIC
    ("ARWF1",   "Ararat Wind Farm",     "wind",    "VIC", 240.0,  "ENERGY_AUSTRALIA", "ARWF_CP"),
    ("MEWF1",   "Mt Mercer Wind Farm",  "wind",    "VIC", 131.0,  "GLENCORE",         "MEWF_CP"),
    ("WEMBLEY1","Waubra Wind Farm",     "wind",    "VIC", 192.0,  "AGL_ENERGY",       "WAUB_CP"),
    # Wind — NSW
    ("CAPTL_WF","Capital Wind Farm",    "wind",    "NSW", 140.7,  "WIND_LAB_NS",      "CAPTL_CP"),
    ("SNOWTWN1","Snow Town",            "wind",    "SA",  98.7,   "AGL_ENERGY",       "SNTW_CP"),
    # Solar — QLD
    ("RUGBYR1", "Rugby Run Solar Farm", "solar",   "QLD", 80.0,   "AGL_ENERGY",       "RUGB_CP"),
    ("DAYDREAMS","Daydream Solar Farm", "solar",   "QLD", 180.0,  "NEOEN",            "DAYD_CP"),
    ("GARDNR1", "Gannawarra Solar Farm","solar",   "VIC", 50.0,   "AGL_ENERGY",       "GANN_CP"),
    ("HLWF1",   "Haughton Solar Farm",  "solar",   "QLD", 102.0,  "ACCIONA",          "HAUG_CP"),
    # Solar — NSW
    ("STKLD1",  "Stockyard Hill Solar", "solar",   "VIC", 149.0,  "ORIGIN",           "STKY_CP"),
    ("NYNGAN1", "Nyngan Solar Plant",   "solar",   "NSW", 102.0,  "AGL_ENERGY",       "NYNG_CP"),
    ("BENBUL1", "Benbullen Solar Farm", "solar",   "NSW", 110.0,  "NEOEN",            "BENB_CP"),
    # Solar — SA
    ("LKBONNY4","Lake Bonney Solar",    "solar",   "SA",  57.0,   "ACCIONA",          "LKBN_CP"),
    # Hydro — NSW/TAS
    ("TUMUT1",  "Tumut 1",              "hydro",   "NSW", 320.0,  "SNOWY_HYDRO",      "TUMU1_CP"),
    ("TUMUT2",  "Tumut 2",              "hydro",   "NSW", 286.0,  "SNOWY_HYDRO",      "TUMU2_CP"),
    ("TUMUT3",  "Tumut 3",              "hydro",   "NSW", 1500.0, "SNOWY_HYDRO",      "TUMU3_CP"),
    ("MURRAY1", "Murray 1",             "hydro",   "NSW", 950.0,  "SNOWY_HYDRO",      "MURR1_CP"),
    ("MURRAY2", "Murray 2",             "hydro",   "NSW", 550.0,  "SNOWY_HYDRO",      "MURR2_CP"),
    ("JOHN_HF1","John Butters",         "hydro",   "TAS", 144.0,  "HYDRO_TASMANIA",   "JHNBT_CP"),
    ("GORDONS1","Gordon",               "hydro",   "TAS", 432.0,  "HYDRO_TASMANIA",   "GORD_CP"),
    ("POATINA1","Poatina",              "hydro",   "TAS", 300.0,  "HYDRO_TASMANIA",   "POAT_CP"),
    ("REECE1",  "Reece",                "hydro",   "TAS", 231.0,  "HYDRO_TASMANIA",   "REEC_CP"),
    ("DARWIN1", "Darwin",               "hydro",   "TAS", 60.0,   "HYDRO_TASMANIA",   "DARW_CP"),
    # Battery
    ("HPRL1",   "Hornsdale Power Reserve","battery","SA", 100.0,  "NEOEN",            "HPRL_CP"),
    ("VBBL1",   "Victorian Big Battery", "battery","VIC", 300.0,  "AGL_ENERGY",       "VBBL_CP"),
    ("WALGETT1","Waratah Super Battery", "battery","NSW", 850.0,  "AGL_ENERGY",       "WARB_CP"),
    ("GANNBAT1","Gannawarra Battery",   "battery", "VIC", 25.0,   "AGL_ENERGY",       "GANB_CP"),
    ("DALRNG1", "Dalrymple Battery",    "battery", "SA",  30.0,   "AGL_ENERGY",       "DALR_CP"),
]

# Build lookup dict by duid
DUID_INFO = {row[0]: row for row in GENERATOR_REGISTRY}

# Derive region_id from state
STATE_REGION = {v: k for k, v in REGION_STATE.items()}
# TAS maps to TAS1
STATE_REGION["TAS"] = "TAS1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def snap_to_interval(dt: datetime, minutes: int) -> datetime:
    """Snap datetime down to the nearest interval boundary."""
    total = int(dt.timestamp())
    interval_secs = minutes * 60
    snapped = (total // interval_secs) * interval_secs
    return datetime.fromtimestamp(snapped)


def date_range_intervals(start_dt: datetime, end_dt: datetime, minutes: int):
    """Generate all interval timestamps between start and end."""
    current = snap_to_interval(start_dt, minutes)
    while current <= end_dt:
        yield current
        current += timedelta(minutes=minutes)


def solar_factor(dt: datetime, state: str) -> float:
    """
    Solar output factor 0-1 based on time of day and season.
    Peak around solar noon (12:30 local time, approx).
    Summer (DJF) higher than winter (JJA).
    """
    hour = dt.hour + dt.minute / 60.0
    month = dt.month
    # Night — no output
    if hour < 5.5 or hour > 20.5:
        return 0.0
    # Seasonal capacity factor adjustment: summer ~0.9 peak, winter ~0.55 peak
    summer_months = {12, 1, 2}
    winter_months = {6, 7, 8}
    if month in summer_months:
        season_peak = 0.92
    elif month in winter_months:
        season_peak = 0.55
    else:
        season_peak = 0.72
    # Bell curve centred on 12.5 (solar noon)
    factor = season_peak * np.exp(-0.5 * ((hour - 12.5) / 3.5) ** 2)
    # Add some cloud/stochastic noise
    noise = np.random.uniform(0.85, 1.05)
    return float(np.clip(factor * noise, 0.0, 1.0))


def wind_factor() -> float:
    """Random wind output factor 0-1 (Weibull-ish)."""
    # Weibull shape=2, scale=0.55 gives realistic wind distribution
    raw = np.random.weibull(2.0) * 0.55
    return float(np.clip(raw, 0.0, 1.0))


def is_afternoon_peak(dt: datetime) -> bool:
    """True during afternoon peak demand hours (4pm–8pm)."""
    return 16 <= dt.hour < 20


def is_summer(dt: datetime) -> bool:
    """True in Australian summer: Dec, Jan, Feb."""
    return dt.month in {12, 1, 2}


# ---------------------------------------------------------------------------
# TABLE 1: dispatch_intervals (50,000 rows)
# ---------------------------------------------------------------------------

def generate_dispatch_intervals(n: int = 50_000) -> pd.DataFrame:
    print(f"  Generating dispatch_intervals ({n:,} rows)...")

    end_dt   = datetime(2025, 11, 22, 0, 0)
    start_dt = end_dt - timedelta(days=182)  # ~6 months

    # Build a pool of all 5-min timestamps for each region
    all_intervals = list(date_range_intervals(start_dt, end_dt, 5))
    n_intervals = len(all_intervals)

    rows = []
    rng  = np.random.default_rng(SEED)

    # Sample n rows — pick a random timestamp and a random DUID
    sampled_indices = rng.integers(0, n_intervals, size=n)
    sampled_duids   = rng.integers(0, len(GENERATOR_REGISTRY), size=n)

    for i in range(n):
        dt   = all_intervals[sampled_indices[i]]
        info = GENERATOR_REGISTRY[sampled_duids[i]]
        duid, station, fuel, state, cap, participant, _ = info

        region_id = STATE_REGION.get(state, "NSW1")

        # Dispatch logic by fuel type
        if fuel == "coal":
            # Runs 24/7 at 70-90% load factor
            load_factor = rng.uniform(0.70, 0.90)
            # Occasionally forced outage — 2% chance
            if rng.random() < 0.02:
                load_factor = rng.uniform(0.0, 0.15)
            dispatch_mw  = round(cap * load_factor, 1)
            available_mw = round(cap * rng.uniform(load_factor, min(load_factor + 0.08, 1.0)), 1)
            initial_mw   = round(dispatch_mw * rng.uniform(0.97, 1.03), 1)
            ramp_rate    = round(rng.uniform(3.0, 8.0), 1)

        elif fuel == "gas":
            # Peakers: mostly off, run at peak demand events
            if is_afternoon_peak(dt) and (is_summer(dt) or rng.random() < 0.3):
                load_factor = rng.uniform(0.50, 0.95)
            elif rng.random() < 0.15:
                load_factor = rng.uniform(0.10, 0.50)
            else:
                load_factor = rng.uniform(0.0, 0.05)
            dispatch_mw  = round(cap * load_factor, 1)
            available_mw = round(cap * rng.uniform(max(load_factor, 0.1), 1.0), 1)
            initial_mw   = round(dispatch_mw * rng.uniform(0.9, 1.1), 1)
            ramp_rate    = round(rng.uniform(10.0, 30.0), 1)

        elif fuel == "solar":
            sf = solar_factor(dt, state)
            # Add panel-level noise
            load_factor  = sf * rng.uniform(0.90, 1.0)
            dispatch_mw  = round(cap * load_factor, 1)
            available_mw = round(cap * sf, 1)
            initial_mw   = round(dispatch_mw * rng.uniform(0.98, 1.02), 1)
            ramp_rate    = round(rng.uniform(50.0, 200.0), 1)  # fast ramp (inverter)

        elif fuel == "wind":
            wf = wind_factor()
            dispatch_mw  = round(cap * wf, 1)
            available_mw = round(cap * min(wf * rng.uniform(1.0, 1.1), 1.0), 1)
            initial_mw   = round(dispatch_mw * rng.uniform(0.95, 1.05), 1)
            ramp_rate    = round(rng.uniform(30.0, 120.0), 1)

        elif fuel == "hydro":
            # Hydro: flexible, responds to prices
            if is_afternoon_peak(dt):
                load_factor = rng.uniform(0.60, 1.0)
            else:
                load_factor = rng.uniform(0.05, 0.50)
            dispatch_mw  = round(cap * load_factor, 1)
            available_mw = round(cap * rng.uniform(load_factor, 1.0), 1)
            initial_mw   = round(dispatch_mw * rng.uniform(0.98, 1.02), 1)
            ramp_rate    = round(rng.uniform(30.0, 90.0), 1)

        elif fuel == "battery":
            # Battery: charge/discharge; net dispatch can be negative (charging)
            if is_afternoon_peak(dt) and rng.random() < 0.70:
                # Discharging
                load_factor = rng.uniform(0.30, 1.0)
                dispatch_mw = round(cap * load_factor, 1)
            elif rng.random() < 0.40:
                # Charging (negative MW)
                dispatch_mw = round(-cap * rng.uniform(0.10, 0.80), 1)
            else:
                dispatch_mw = round(cap * rng.uniform(0.0, 0.05), 1)
            available_mw = round(cap, 1)
            initial_mw   = round(dispatch_mw * rng.uniform(0.95, 1.05), 1)
            ramp_rate    = round(rng.uniform(200.0, 600.0), 1)  # very fast

        else:
            dispatch_mw  = 0.0
            available_mw = cap
            initial_mw   = 0.0
            ramp_rate    = 0.0

        # Clamp to non-negative (except battery)
        if fuel != "battery":
            dispatch_mw  = max(0.0, dispatch_mw)
            initial_mw   = max(0.0, initial_mw)
        available_mw = max(dispatch_mw, available_mw)

        rows.append({
            "settlement_date": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "region_id":       region_id,
            "duid":            duid,
            "dispatch_mw":     dispatch_mw,
            "initial_mw":      initial_mw,
            "available_mw":    available_mw,
            "ramp_rate":       ramp_rate,
            "fuel_type":       fuel,
            "station_name":    station,
            "state":           state,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 2: spot_prices (20,000 rows)
# ---------------------------------------------------------------------------

def generate_spot_prices(n: int = 20_000) -> pd.DataFrame:
    print(f"  Generating spot_prices ({n:,} rows)...")

    end_dt   = datetime(2025, 11, 22, 0, 0)
    start_dt = end_dt - timedelta(days=182)

    all_intervals = list(date_range_intervals(start_dt, end_dt, 30))
    n_intervals   = len(all_intervals)

    # Typical demand levels by region (MW)
    BASE_DEMAND = {
        "NSW1": 7500,
        "VIC1": 5500,
        "QLD1": 6800,
        "SA1":  1600,
        "TAS1": 1100,
    }

    # Region volatility multipliers (SA and QLD more volatile)
    VOLATILITY = {
        "NSW1": 1.0,
        "VIC1": 1.0,
        "QLD1": 1.4,
        "SA1":  2.0,
        "TAS1": 0.7,
    }

    rng = np.random.default_rng(SEED + 1)
    sampled_indices = rng.integers(0, n_intervals, size=n)
    sampled_regions = rng.integers(0, len(REGIONS), size=n)

    rows = []
    for i in range(n):
        dt        = all_intervals[sampled_indices[i]]
        region_id = REGIONS[sampled_regions[i]]
        vol       = VOLATILITY[region_id]
        base_dem  = BASE_DEMAND[region_id]

        # Base price from log-normal, centred at ~$80/MWh
        base_price = float(rng.lognormal(mean=np.log(80), sigma=0.5))

        # Afternoon peak premium
        if is_afternoon_peak(dt):
            base_price *= rng.uniform(1.5, 3.5) * vol

        # Summer additional heat stress
        if is_summer(dt) and is_afternoon_peak(dt):
            base_price *= rng.uniform(1.2, 2.5) * vol

        # Spike events: 3% probability during peak, otherwise 0.5%
        spike_prob = 0.03 if (is_afternoon_peak(dt) and is_summer(dt)) else 0.005
        if rng.random() < spike_prob * vol:
            # Spike to market price cap range
            base_price = float(rng.uniform(1000, 15300))

        # Negative price: high wind overnight or low demand
        neg_prob = 0.04 if (not is_afternoon_peak(dt) and region_id in {"SA1", "VIC1"}) else 0.01
        if rng.random() < neg_prob:
            base_price = float(rng.uniform(-1000, 0))

        rrp = round(float(np.clip(base_price, -1000.0, 15300.0)), 2)

        # FCAS prices — correlated with energy price but much smaller
        raise_6sec = round(abs(float(rng.lognormal(np.log(max(1, abs(rrp) * 0.02)), 0.8))), 2)
        lower_6sec = round(abs(float(rng.lognormal(np.log(max(1, abs(rrp) * 0.015)), 0.8))), 2)

        # Demand: log-normal around base with time-of-day and seasonal effects
        hour = dt.hour
        tod_factor = 1.0
        if is_afternoon_peak(dt):
            tod_factor = rng.uniform(1.1, 1.3)
        elif 0 <= hour < 6:
            tod_factor = rng.uniform(0.65, 0.80)
        elif 7 <= hour <= 9:
            tod_factor = rng.uniform(0.90, 1.05)

        seasonal_factor = rng.uniform(1.05, 1.25) if is_summer(dt) else rng.uniform(0.85, 1.0)
        total_demand = round(float(base_dem * tod_factor * seasonal_factor * rng.lognormal(0, 0.05)), 1)

        # Interconnector net flow — positive = importing
        net_interchange = round(float(rng.normal(0, base_dem * 0.08)), 1)
        scheduled_gen   = round(float(max(0, total_demand - net_interchange) * rng.uniform(0.85, 1.05)), 1)

        rows.append({
            "settlement_date":   dt.strftime("%Y-%m-%d %H:%M:%S"),
            "region_id":         region_id,
            "rrp":               rrp,
            "raise_6sec":        raise_6sec,
            "lower_6sec":        lower_6sec,
            "total_demand_mw":   total_demand,
            "net_interchange":   net_interchange,
            "scheduled_generation": scheduled_gen,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 3: market_notices (500 rows)
# ---------------------------------------------------------------------------

# Realistic NEM market notice text templates
NOTICE_TEMPLATES = {
    "LOR1": [
        "LACK OF RESERVE LEVEL 1 NOTICE — {region}: Projected reserve margin is {margin:.0f} MW, below the LOR1 threshold of {threshold:.0f} MW for the trading interval commencing {time}. Participants are requested to make available any additional capacity. AEMO is monitoring the situation and will issue further notices as conditions evolve.",
        "LOR1 DECLARED — {region}: Reserve shortfall forecast for {time}. Available generation {avail:.0f} MW against requirement {req:.0f} MW. Net shortfall {shortage:.0f} MW. Demand response providers and semi-scheduled generators requested to maximise output. Direction may be issued if reserve levels deteriorate further.",
    ],
    "LOR2": [
        "LACK OF RESERVE LEVEL 2 — {region}: AEMO declares LOR2 for {time}. Forecast reserve {margin:.0f} MW below threshold. All available FCAS providers must register to bid. AEMO is in contact with large industrial loads regarding voluntary demand response. Interconnector flows being optimised.",
        "LACK OF RESERVE LEVEL 2 NOTICE — {region}: Directed reserve shortfall. Available capacity {avail:.0f} MW, requirement {req:.0f} MW. AEMO is directing semi-scheduled generators and will consider emergency directions under clause 4.8.9 of the NER if the situation does not improve within the next two dispatch intervals.",
    ],
    "LOR3": [
        "LACK OF RESERVE LEVEL 3 — EMERGENCY: {region} is experiencing a reserve deficit of {shortage:.0f} MW. AEMO is issuing directions under NER clause 4.8.9 to all available generators in {region} and adjacent regions. Load shedding may be required to maintain system security. AEMO is in contact with {region} DNSP to coordinate emergency actions.",
        "LOR3 EMERGENCY DECLARED — {region}: Emergency directions issued. Available capacity {avail:.0f} MW against minimum requirement {req:.0f} MW. AEMO has contacted all registered participants. Involuntary load shedding {lshed:.0f} MW now active. Situation is being monitored continuously.",
    ],
    "RESERVE NOTICE": [
        "SUMMER DEMAND RESERVE NOTICE — {region}: Elevated demand forecast for the period {date}. Peak demand forecast {peak:.0f} MW, representing {pct:.0f}% above seasonal average. Participants are reminded that additional capacity must be registered and available for dispatch. AEMO will publish updated forecasts via MT PASA on a rolling basis.",
        "ADVANCE RESERVE NOTICE — {region}: AEMO is advising market participants of forecast tight reserve conditions for trading day {date}. Forecast demand {peak:.0f} MW. Current committed generation {gen:.0f} MW. Participants with mothballed or decommissioned units are invited to advise AEMO of availability within 72 hours.",
    ],
    "MARKET NOTICE": [
        "INTERCONNECTOR LIMIT REDUCTION — {interconnector}: The transfer capability of {interconnector} has been reduced to {limit:.0f} MW in the {direction} direction from {time} until further notice due to {reason}. Constraint set {constraint_id} has been applied. NEMDE will observe the reduced limit from the next dispatch interval.",
        "CONSTRAINT ACTIVATION NOTICE: Constraint set {constraint_id} has been activated from {time}. The constraint applies to {region}. RHS value: {rhs:.0f} MW. Reason: {reason}. Affected generators have been notified via EMMS. The constraint will remain active until {end_time} or until AEMO advises otherwise.",
        "MARKET PRICE CAP DECLARATION — {region}: The Regional Reference Price for {region} has reached the Market Price Cap of $15,300/MWh for the dispatch interval ending {time}. This is consistent with the dispatch conditions at the time. AEMO reminds participants of their obligations under NER clause 3.8.22. The market price cap event has been logged for the purpose of the cumulative price threshold calculation.",
        "ADMINISTERED PRICE CAP NOTICE — {region}: The cumulative price threshold has been breached in {region}. The Administered Price Cap of $300/MWh will apply from trading interval {time} for a period of 7 trading days, or until AEMO advises that the cumulative price threshold is no longer breached. Bids and offers during this period will be capped at the administered price.",
    ],
    "SYSTEM NORMAL": [
        "SYSTEM NORMAL — {region}: Reserve conditions have returned to normal levels in {region}. The LOR{lor} notice issued at {prev_time} is hereby cancelled. All directed participants may resume normal bidding. AEMO thanks participants for their response. No further action is required at this time.",
        "SYSTEM NORMAL: All regions operating within normal reserve margins. No directions currently active. The notice issued at {prev_time} has been cancelled. AEMO will continue to monitor conditions and will issue further notices if required.",
    ],
}

INTERCONNECTORS = [
    ("VIC1-NSW1", "Victoria to New South Wales", "northward"),
    ("NSW1-QLD1", "New South Wales to Queensland", "northward"),
    ("V-SA",      "Victoria to South Australia", "westward"),
    ("V-S-MNSP1", "Murraylink", "westward"),
    ("T-V-MNSP1", "Basslink — Tasmania to Victoria", "northward"),
]

CONSTRAINT_IDS = [
    "V^MLTS1-HYTS_E", "S^NIL_PEAK_1530_3", "F_I+LREG+ML_RREG_0600",
    "N^^Q_NIL_1", "V^GUNNQ_MUGG_E", "Q^^Q_NIL_PEAK_1530",
    "N_X_HYTS_GUN_1", "S_RADIAL_SA_1", "V^HYTS_MLTS_N", "F_MAIN+ML_MR_0600",
    "Q_PQ_NIL_RADL_1", "NSW_VIC_LOCAT_1", "V_XEMPT_MAIN+ML",
]

CONSTRAINT_REASONS = [
    "thermal overload risk on Moorabool-Hazelwood 220kV line",
    "voltage stability limit following contingency N-1 on Heywood interconnector",
    "transient stability limit for loss of Loy Yang A unit 4",
    "network overload protection — South Australia radial supply risk",
    "frequency control ancillary service shortfall in lower 60-second service",
    "Basslink power flow control — thermal limit in wet end equipment",
    "maintenance outage on Tumut 3 transformer 2 reducing available transfer capability",
    "bushfire-related pre-emptive constraint — high fire danger in transmission corridor",
    "vegetation growth reducing conductor-to-ground clearance below statutory limit",
    "planned works on Snowy 2.0 transmission connection — commissioning phase restriction",
]


def _notice_text(notice_type: str, region: str, dt: datetime) -> str:
    templates = NOTICE_TEMPLATES.get(notice_type, NOTICE_TEMPLATES["MARKET NOTICE"])
    template  = random.choice(templates)
    interc    = random.choice(INTERCONNECTORS)
    constr    = random.choice(CONSTRAINT_IDS)
    reason    = random.choice(CONSTRAINT_REASONS)
    margin    = random.uniform(50, 400)
    threshold = margin + random.uniform(100, 300)
    avail     = random.uniform(1000, 5000)
    req       = avail + margin
    shortage  = random.uniform(50, 400)
    limit     = random.uniform(400, 1800)
    peak      = random.uniform(5000, 14000)
    pct       = random.uniform(5, 25)
    gen       = peak * random.uniform(0.88, 0.99)
    rhs       = random.uniform(200, 1200)
    lshed     = random.uniform(50, 300)
    prev_dt   = dt - timedelta(hours=random.randint(1, 6))

    try:
        text = template.format(
            region=region,
            time=dt.strftime("%H:%M AEST"),
            date=(dt + timedelta(days=random.randint(1, 5))).strftime("%d %B %Y"),
            end_time=(dt + timedelta(hours=random.randint(2, 12))).strftime("%H:%M AEST"),
            margin=margin,
            threshold=threshold,
            avail=avail,
            req=req,
            shortage=shortage,
            lshed=lshed,
            limit=limit,
            direction=interc[2],
            interconnector=interc[0],
            reason=reason,
            constraint_id=constr,
            rhs=rhs,
            peak=peak,
            pct=pct,
            gen=gen,
            lor=random.randint(1, 3),
            prev_time=prev_dt.strftime("%H:%M AEST on %d %B %Y"),
        )
    except KeyError:
        text = template  # fallback to raw template if a key is missing

    # Trim to 100-300 chars for the reason column
    if len(text) > 300:
        text = text[:297] + "..."
    return text


def generate_market_notices(n: int = 500) -> pd.DataFrame:
    print(f"  Generating market_notices ({n} rows)...")

    end_dt   = datetime(2025, 11, 22)
    start_dt = end_dt - timedelta(days=365)

    notice_types = list(NOTICE_TEMPLATES.keys())
    nt_weights   = [0.12, 0.10, 0.04, 0.08, 0.42, 0.24]  # MARKET NOTICE most common

    rows = []
    for notice_id in range(1, n + 1):
        span_secs = int((end_dt - start_dt).total_seconds())
        issue_dt  = start_dt + timedelta(seconds=random.randint(0, span_secs))
        ntype     = random.choices(notice_types, weights=nt_weights)[0]

        # Some notices are regional, some national
        is_regional = ntype in {"LOR1", "LOR2", "LOR3", "RESERVE NOTICE"}
        region_id   = random.choice(REGIONS) if is_regional else None

        # Display region for text generation
        text_region = region_id if region_id else random.choice(REGIONS)

        effective_dt = issue_dt + timedelta(minutes=random.randint(5, 120))
        intervention = ntype in {"LOR2", "LOR3"}

        rows.append({
            "notice_id":      notice_id,
            "notice_type":    ntype,
            "issue_time":     issue_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "reason":         _notice_text(ntype, text_region, issue_dt),
            "effective_date": effective_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "region_id":      region_id,
            "intervention":   intervention,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 4: generator_registration (200 rows)
# ---------------------------------------------------------------------------

def generate_generator_registration(n: int = 200) -> pd.DataFrame:
    print(f"  Generating generator_registration ({n} rows)...")

    # Use real registry entries + pad with synthetic additions
    rows = []
    rng  = np.random.default_rng(SEED + 2)

    # First include all real registry entries
    for duid, station, fuel, state, cap, participant, cp_id in GENERATOR_REGISTRY:
        region_id = STATE_REGION.get(state, "NSW1")

        # Ramp rate by fuel type
        ramp_map = {
            "coal":    rng.uniform(3.0, 8.0),
            "gas":     rng.uniform(10.0, 35.0),
            "wind":    rng.uniform(30.0, 120.0),
            "solar":   rng.uniform(50.0, 200.0),
            "hydro":   rng.uniform(30.0, 90.0),
            "battery": rng.uniform(200.0, 600.0),
        }
        max_ramp = round(ramp_map.get(fuel, 10.0), 1)

        # Min load (coal has high minimum, others low/zero)
        min_load_pct = {"coal": 0.40, "gas": 0.0, "wind": 0.0, "solar": 0.0, "hydro": 0.02, "battery": 0.0}
        min_load     = round(cap * min_load_pct.get(fuel, 0.0), 1)

        # Dispatch type — battery is bidirectional
        if fuel == "battery":
            dispatch_type = "BIDIRECTIONAL"
        elif fuel in ("coal", "gas", "wind", "solar", "hydro"):
            dispatch_type = "GENERATOR"
        else:
            dispatch_type = "GENERATOR"

        rows.append({
            "duid":                   duid,
            "station_name":           station,
            "participant_id":         participant,
            "region_id":              region_id,
            "fuel_type":              fuel,
            "registered_capacity_mw": cap,
            "connection_point_id":    cp_id,
            "dispatch_type":          dispatch_type,
            "max_ramp_rate":          max_ramp,
            "min_load":               min_load,
        })

    # Pad to n rows with synthetic small renewable/demand response units
    synthetic_fuels  = ["wind", "solar", "battery", "gas"]
    synthetic_states = ["NSW", "VIC", "QLD", "SA", "TAS"]
    participants      = ["AGL_ENERGY", "ORIGIN", "ENERGY_AUSTRALIA", "SNOWY_HYDRO",
                         "CS_ENERGY", "STANWELL", "NEOEN", "ERM_POWER", "ACCIONA", "ENGIE"]
    existing_count    = len(rows)

    for j in range(existing_count, n):
        fuel     = random.choice(synthetic_fuels)
        state    = random.choice(synthetic_states)
        region   = STATE_REGION.get(state, "NSW1")
        cap_mw   = round(random.choice([10, 20, 30, 50, 75, 100, 150, 200]), 1)
        part     = random.choice(participants)
        duid_syn = f"SYN{j:04d}"
        cp_syn   = f"SYN{j:04d}_CP"

        ramp_map2 = {
            "wind":    random.uniform(30.0, 120.0),
            "solar":   random.uniform(50.0, 200.0),
            "battery": random.uniform(200.0, 600.0),
            "gas":     random.uniform(10.0, 35.0),
        }

        rows.append({
            "duid":                   duid_syn,
            "station_name":           f"Synthetic {fuel.title()} Farm {j}",
            "participant_id":         part,
            "region_id":              region,
            "fuel_type":              fuel,
            "registered_capacity_mw": cap_mw,
            "connection_point_id":    cp_syn,
            "dispatch_type":          "BIDIRECTIONAL" if fuel == "battery" else "GENERATOR",
            "max_ramp_rate":          round(ramp_map2[fuel], 1),
            "min_load":               0.0,
        })

    return pd.DataFrame(rows[:n])


# ---------------------------------------------------------------------------
# TABLE 5: constraint_sets (2,000 rows)
# ---------------------------------------------------------------------------

CONSTRAINT_TYPES = ["thermal", "voltage", "stability"]

CONSTRAINT_REASONS_FULL = [
    "Thermal overload risk on 330kV transmission corridor following forced outage of parallel circuit.",
    "Voltage stability margin insufficient following contingency N-1 on Heywood interconnector.",
    "Transient stability limit for loss of Loy Yang A unit following high renewable penetration.",
    "Radial supply security constraint — South Australia import capacity limit reached.",
    "Frequency control constraint — insufficient inertia from synchronous generation online.",
    "Basslink thermal constraint — sustained high power flow activating wet-end protection.",
    "Maintenance outage on Tumut 3 transformer reducing available NEM north-south transfer capability.",
    "Bushfire proximity pre-emptive constraint — high fire danger index in Snowy transmission corridor.",
    "Vegetation growth reducing conductor-to-ground clearance below National Electricity Rules minimum.",
    "Commissioning restriction on Snowy 2.0 underground cable section — progressive energisation sequence.",
    "Post-fault voltage recovery limit — Hazelwood to Melbourne corridor following unit trip.",
    "Dynamic stability limit triggered by loss of synchronism risk for Northern Queensland generation.",
    "Overload protection — Moorabool substation transformer loading above summer rating.",
    "Constraint activated following trip of New England 330kV double circuit — low probability high impact contingency active.",
    "Basslink frequency constraint — Tasmania operating in islanded mode following communication fault.",
    "Inverter-based resource stability constraint — high IBR penetration threshold reached in SA island mode.",
    "Load shedding avoidance constraint — demand management activated in SA following gas curtailment.",
    "Contingency overload constraint on VIC to NSW interconnector following loss of Tumut 3.",
]


def generate_constraint_sets(n: int = 2_000) -> pd.DataFrame:
    print(f"  Generating constraint_sets ({n:,} rows)...")

    end_dt   = datetime(2025, 11, 22)
    start_dt = end_dt - timedelta(days=365)
    rng      = np.random.default_rng(SEED + 3)
    span     = int((end_dt - start_dt).total_seconds())

    rows = []
    for _ in range(n):
        c_id  = random.choice(CONSTRAINT_IDS)
        ctype = random.choice(CONSTRAINT_TYPES)

        activated_ts   = start_dt + timedelta(seconds=int(rng.integers(0, span)))
        duration_hours = float(rng.lognormal(mean=np.log(4), sigma=1.2))
        duration_hours = max(0.08, min(duration_hours, 168))  # 5 min to 7 days
        deactivated_ts = activated_ts + timedelta(hours=duration_hours)

        rhs_val     = round(float(rng.uniform(50, 1800)), 1)
        region      = random.choice(REGIONS)
        is_interc   = ctype == "thermal" and rng.random() < 0.4
        reason      = random.choice(CONSTRAINT_REASONS_FULL)

        rows.append({
            "constraint_id":       c_id,
            "constraint_type":     ctype,
            "activated_datetime":  activated_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "deactivated_datetime":deactivated_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "reason":              reason,
            "rhs_value":           rhs_val,
            "region_affected":     region,
            "interconnector":      bool(is_interc),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# TABLE 6: settlement_amounts (3,000 rows)
# ---------------------------------------------------------------------------

PARTICIPANTS = [
    "AGL_ENERGY", "ORIGIN", "ENERGY_AUSTRALIA", "SNOWY_HYDRO",
    "CS_ENERGY", "STANWELL", "NEOEN", "ERM_POWER", "ACCIONA",
    "ENGIE", "DELTA_ELECTRICITY", "HYDRO_TASMANIA", "WIND_LAB_NS", "GLENCORE",
]

RUN_TYPES = ["PRELIMINARY", "REVISED", "FINAL"]
SETTLEMENT_STATUS = ["PENDING", "FINAL", "DISPUTED"]


def generate_settlement_amounts(n: int = 3_000) -> pd.DataFrame:
    print(f"  Generating settlement_amounts ({n:,} rows)...")

    # Weekly settlement dates for last 2 years
    end_dt   = datetime(2025, 11, 15)
    start_dt = end_dt - timedelta(days=730)
    rng      = np.random.default_rng(SEED + 4)

    # Build list of weekly settlement dates
    weekly_dates = []
    current = start_dt
    while current <= end_dt:
        weekly_dates.append(current.date())
        current += timedelta(weeks=1)

    rows = []
    for _ in range(n):
        sdate       = random.choice(weekly_dates)
        participant = random.choice(PARTICIPANTS)
        run_type    = random.choices(RUN_TYPES, weights=[0.15, 0.25, 0.60])[0]

        # Financial amounts — log-normal, sign varies by type of participant
        # Large generators have large positive energy amounts
        energy_sign = 1 if random.random() < 0.70 else -1  # most are net sellers
        energy_amt  = energy_sign * round(float(rng.lognormal(np.log(500_000), 1.2)), 2)
        fcas_amt    = round(float(rng.lognormal(np.log(20_000), 1.0)) * random.choice([1, -1, 1, 1]), 2)
        ic_residue  = round(float(rng.normal(0, 15_000)), 2)
        total_aud   = round(energy_amt + fcas_amt + ic_residue, 2)

        if run_type == "FINAL":
            status = random.choices(
                SETTLEMENT_STATUS, weights=[0.02, 0.94, 0.04]
            )[0]
        elif run_type == "REVISED":
            status = random.choices(
                SETTLEMENT_STATUS, weights=[0.20, 0.75, 0.05]
            )[0]
        else:
            status = "PENDING"

        rows.append({
            "settlement_date":         sdate.isoformat(),
            "participant_id":          participant,
            "run_type":                run_type,
            "energy_amount_aud":       energy_amt,
            "fcas_amount_aud":         fcas_amt,
            "interconnector_residue_aud": ic_residue,
            "total_aud":               total_aud,
            "settlement_status":       status,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("AU AI Workshops — AEMO/NEM Data Generator")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    # 1. dispatch_intervals
    df_dispatch = generate_dispatch_intervals(50_000)
    out = OUTPUT_DIR / "dispatch_intervals.csv"
    df_dispatch.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(df_dispatch):,} rows)")

    # 2. spot_prices
    df_prices = generate_spot_prices(20_000)
    out = OUTPUT_DIR / "spot_prices.csv"
    df_prices.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(df_prices):,} rows)")

    # 3. market_notices
    df_notices = generate_market_notices(500)
    out = OUTPUT_DIR / "market_notices.csv"
    df_notices.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(df_notices):,} rows)")

    # 4. generator_registration
    df_generators = generate_generator_registration(200)
    out = OUTPUT_DIR / "generator_registration.csv"
    df_generators.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(df_generators):,} rows)")

    # 5. constraint_sets
    df_constraints = generate_constraint_sets(2_000)
    out = OUTPUT_DIR / "constraint_sets.csv"
    df_constraints.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(df_constraints):,} rows)")

    # 6. settlement_amounts
    df_settlement = generate_settlement_amounts(3_000)
    out = OUTPUT_DIR / "settlement_amounts.csv"
    df_settlement.to_csv(out, index=False)
    print(f"  Saved: {out} ({len(df_settlement):,} rows)")

    print("=" * 60)
    print("Done. Summary:")
    print(f"  dispatch_intervals:     {len(df_dispatch):>8,} rows")
    print(f"  spot_prices:            {len(df_prices):>8,} rows")
    print(f"  market_notices:         {len(df_notices):>8,} rows")
    print(f"  generator_registration: {len(df_generators):>8,} rows")
    print(f"  constraint_sets:        {len(df_constraints):>8,} rows")
    print(f"  settlement_amounts:     {len(df_settlement):>8,} rows")
    total = sum([
        len(df_dispatch), len(df_prices), len(df_notices),
        len(df_generators), len(df_constraints), len(df_settlement),
    ])
    print(f"  TOTAL:                  {total:>8,} rows")
    print("=" * 60)


if __name__ == "__main__":
    main()
