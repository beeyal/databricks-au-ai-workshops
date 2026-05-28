# Databricks AU AI Workshop 2a — Project Context

This is a hands-on workshop on Genie Code, Skills, and MCP for Australian regulated industries.
Auto-discovered by Genie Code when working in any notebook within this directory.

## Workshop Context

- **Catalog / Schema:** `workshop_au.energy` (or as configured by the `CATALOG` and `SCHEMA` widgets)
- **Region:** All AI features must be Australia East (`australiaeast`) — no cross-geo calls
- **Synthetic data:** 56,000 rows of Australian energy sector data across 5 tables
- **Compute:** Serverless (no cluster required for any lab)
- **Model:** `databricks-claude-sonnet-4-6` via FMAPI Provisioned Throughput (in-region)

## Data Schema

| Table | Row count | Description |
|-------|-----------|-------------|
| `workshop_au.energy.energy_assets` | 500 | Network assets: transformers, substations, poles, cables, meters |
| `workshop_au.energy.meter_readings` | 50,000 | NEM12-style 30-minute interval readings with quality flags |
| `workshop_au.energy.outage_events` | 2,000 | Network outage events with SAIDI/SAIFI fields |
| `workshop_au.energy.maintenance_work_orders` | 3,000 | Work orders with priority, status, and unstructured description text |
| `workshop_au.energy.regulatory_reports` | 500 | AER/AEMO/ESC compliance reports with free-text narrative |

### Key Column Notes

**meter_readings:** `nmi` (10-char), `reading_datetime` (timestamp), `interval_kwh` (DECIMAL), `quality_flag` (A/E/S/N)

**outage_events:** `event_type` ('planned'/'unplanned'/'emergency'), `saidi_minutes` (DECIMAL), `saifi_count` (DECIMAL), `affected_customers` (INT), `duration_minutes` (INT), `region` (VIC/NSW/QLD/SA/WA)

**energy_assets:** `asset_type` ('transformer'/'substation'/'pole'/'cable'/'meter'), `installation_date` (DATE), `region`, `asset_name`, `rated_capacity_kva` (DECIMAL)

**maintenance_work_orders:** `priority` ('critical'/'high'/'medium'/'low'), `status` ('open'/'in_progress'/'closed'), `description` (STRING — unstructured text, suitable for AI extraction)

## UC Functions Available

These are callable by Genie Code agent mode and via MCP:

| Function | Signature | Returns |
|----------|-----------|---------|
| `workshop_au.energy.calculate_peak_demand` | `(start_date DATE, end_date DATE, region STRING)` | Peak demand kW by NMI and date for the given region/period |
| `workshop_au.energy.get_meter_readings_summary` | `(nmi STRING, date_range STRING)` | Daily totals, completeness %, and quality flag breakdown for one NMI |
| `workshop_au.energy.lookup_asset_status` | `(asset_id STRING)` | Current status, open work orders, and last inspection date for one asset |

**MCP tool names** (dots → double underscores):
- `workshop_au__energy__calculate_peak_demand`
- `workshop_au__energy__get_meter_readings_summary`
- `workshop_au__energy__lookup_asset_status`

## Code Conventions

- Use Delta Lake format for all output tables (`USING DELTA` or default in Unity Catalog)
- Use Australian date format `DD/MM/YYYY` in comments and display strings; use `YYYY-MM-DD` in SQL predicates
- Reference catalog and schema via widget variables, not hardcoded strings:
  ```python
  CATALOG = dbutils.widgets.get("CATALOG")   # default: workshop_au
  SCHEMA  = dbutils.widgets.get("SCHEMA")    # default: energy
  ```
- All cells should be idempotent (safe to re-run); use `CREATE OR REPLACE` not `CREATE`
- Serverless only — do not attach a cluster; use `%sql` magic or `spark.sql()` directly

## Domain Knowledge

- See `@energy-operations` skill for NEM12 quality flags, SAIDI/SAIFI formulas, AER regulatory context, asset terminology, and SQL patterns
- See `@apra-compliance` skill for data residency classification, CPS 230/234 audit evidence requirements, and approved/rejected AI feature patterns for regulated data

## Lab Navigation

| Lab | File | Topic |
|-----|------|-------|
| 1 | `labs/01_genie_code_intro.py` | Genie Code basics — inline AI, chat panel, fix/explain |
| 2 | `labs/02_notebook_ai_features.py` | AI-assisted data exploration and transformation |
| 3 | `labs/03_adding_skills_tools.py` | Deploy a skill to workspace; create a UC Function |
| 4 | `labs/04_mcp_integration.py` | Connect an agent to MCP; test with OpenAI Agents SDK or LangGraph |
| — | `labs/00_mcp_skills_reference.py` | **Reference card** — keep open during all labs |

Solutions are in `labs/solutions/` if you get stuck.
