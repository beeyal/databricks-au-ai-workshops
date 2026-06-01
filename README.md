# AEMO AI Enablement Workshops — Databricks

Six-session hands-on AI enablement programme for AEMO on Azure Australia East. All content is scoped to in-region features only and governed under the SOCI Act 2018, Privacy Act 1988, and the Australian Energy Sector Cyber Security Framework (AESCSF).

---

## Quick Start

1. **Clone the repo** into Databricks Repos: `https://github.com/beeyal/databricks-au-ai-workshops`
2. **Run the session setup** — navigate to `<session_folder>/setup/setup.py` and run it top to bottom before the session starts
3. **Open the labs** — work through `<session_folder>/labs/` in order

Each session is self-contained. Run `setup/setup.py`, do the labs, run `setup/cleanup.py` when done.

---

## Session Overview

| Session | Folder | Audience | Duration |
|---------|--------|----------|----------|
| 1: Platform Admins | `session1_platform_admin/` | Workspace admins | 2 hrs |
| 2: Building Genie Space | `session2_genie_space/` | Data engineers, analysts | 2.5 hrs |
| 3: Line-of-Business | `session3_lob/` | 100 business users | Half day — LDT team |
| 4: MCP Agents (optional) | `session4_mcp_agents/` | Data engineers | Half day |
| 5: Genie Code (optional) | `session5_genie_code/` | Data scientists | 1 hr |
| 6: AI Ideation (optional) | `session6_ideation/` | 20–30 business users | Half day |

Session 3 is delivered by the Databricks Learning & Development Team (LDT) and is not in this repository.

---

## Key Principle

Each session folder contains:

- `setup/setup.py` — loads data, grants permissions, runs a smoke test. Run this once before participants arrive.
- `labs/` — the actual workshop labs (mix of UI walkthroughs and automated scripts).
- `setup/cleanup.py` — removes everything created in the session, revokes grants. Run this after the workshop.

Sessions share the `workshop_au` Unity Catalog. If you are running multiple sessions in the same workspace, run each session's setup in order (Session 1 → 2 → ...) and clean up in reverse order.

---

## Data

The workshops use two sets of synthetic data — no actual customer or network data is used.

**AEMO NEM data** (in `workshop_au.aemo`):

| Table | Description |
|-------|-------------|
| `dispatch_intervals` | 5-minute generator dispatch data by DUID and region |
| `spot_prices` | 30-minute NEM spot prices (RRP) by region |
| `market_notices` | AEMO market and system notices including LOR events |
| `generator_registration` | Registered NEM generator details |
| `settlement_amounts` | Weekly settlement amounts by participant |

**Energy grid data** (in `workshop_au.energy`):

| Table | Description |
|-------|-------------|
| `energy_assets` | Asset registry — substations, lines, transformers |
| `outage_events` | Planned and unplanned outage events |
| `maintenance_work_orders` | Scheduled maintenance records |
| `meter_readings` | Interval meter reads |

Raw CSVs and generator scripts are in `data/`.

---

## Requirements

- Python 3.11+
- Databricks workspace on Azure `australiaeast`
- Unity Catalog enabled
- Workspace admin role for setup steps

---

## Repository

`https://github.com/beeyal/databricks-au-ai-workshops`
