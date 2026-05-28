# AI Use Case Canvas

Use one canvas per use case. Work through the fields in order — each field helps you sharpen the next one. A well-completed canvas takes 5–10 minutes to fill in.

---

## AI Use Case Canvas

**Business Question:** [What question do you want answered? Write it as a question you would type into a search bar or ask a colleague. Be specific — "show me spot prices" is not a question; "what was the average spot price in NSW1 yesterday compared to the same day last week?" is.]

**Current Process:** [How do you answer this today? Name the system, report, or person you go to. How long does it take from when you need the answer to when you have it? Include the time to find the data, process it, and share it with whoever needs it.]

**Data Available:** [Which tables, reports, or systems contain this data? Use the table names from the Genie Space if you know them. If you do not know the table names, describe where the data lives — e.g. "weekly settlement report from MSATS", "dispatch data from MMS extract".]

**Value if Automated:** [Pick at least one: time saved (minutes/hours per week), decisions improved (what decision gets better information faster?), risk reduced (what error or compliance gap does this prevent?), capacity freed (what does the analyst do instead?)]

**Genie Test Question:** [Write the exact question you will type into Genie during the hands-on block. Use region codes (NSW1/VIC1/QLD1/SA1/TAS1), time periods ("yesterday", "last 7 days"), and specific metrics. This is your hypothesis — you will find out in the next 60 minutes whether Genie can answer it.]

**Priority:** High / Medium / Low

**Dependencies:** [What needs to be true before Genie can answer this? Examples: the table needs to be added to the Space, historical data needs to be loaded further back, the settlement run needs to complete before querying, a column that does not currently exist needs to be derived.]

---

## Worked Examples

The five examples below are filled-in canvases from AEMO operational teams. Use them as a reference for the level of specificity that makes a canvas actionable.

---

### Example 1: Spot Price Monitoring (Market Operations)

**Business Question:** What was the average spot price in each NEM region over the last 24 hours, and which region had the highest price volatility?

**Current Process:** The market operations analyst pulls the NEM price export from MSATS each morning, pastes it into a pre-built Excel template, and manually calculates averages and standard deviation by region. The process takes approximately 25 minutes each morning and is done by one analyst who is the single point of knowledge for the format. When that analyst is on leave, the summary is not produced.

**Data Available:** `workshop_au.aemo.spot_prices` — contains 30-minute Regional Reference Price data for all five NEM regions. Columns: `settlement_date`, `region_id`, `rrp`, `total_demand_mw`.

**Value if Automated:** Saves approximately 25 minutes per analyst per day (125 minutes/week for 5 analysts). Removes single-point-of-knowledge risk. Enables ad-hoc intra-day price checks without analyst involvement — any team member can ask.

**Genie Test Question:** "What was the average spot price in each NEM region yesterday, and which region had the highest standard deviation?"

**Priority:** High

**Dependencies:** Data must be loaded for at least the last 30 days (currently loaded for last 6 months — no dependency). SQL warehouse must be running at 7am when the morning check happens.

---

### Example 2: Generator Performance Tracking (Operations)

**Business Question:** Which generators in NSW1 dispatched less than 50% of their registered capacity last week, and what was their average availability declaration?

**Current Process:** The operations team requests a custom report from the Market Analysis team each week. The request is submitted Monday morning, the report arrives Wednesday afternoon, and the information is 2–3 days stale by the time decisions are made. Market Analysis estimates 2 hours of analyst time per report.

**Data Available:** `workshop_au.aemo.dispatch_intervals` (actual dispatch and available MW per 5-minute interval) joined to `workshop_au.aemo.generator_registration` (registered capacity and fuel type). The capacity utilisation calculation is: `avg(dispatch_mw) / registered_capacity_mw`.

**Value if Automated:** Saves 2 analyst hours per week in Market Analysis. Reduces information lag from 2–3 days to on-demand. Enables the operations team to self-serve, freeing Market Analysis for higher-value analysis work. Better decisions on dispatch instructions when under-performing units are identified earlier.

**Genie Test Question:** "Show me all NSW1 generators that dispatched less than 50% of their registered capacity last week. Include their average available MW and fuel type."

**Priority:** High

**Dependencies:** The join between `dispatch_intervals.duid` and `generator_registration.duid` must be valid — spot-check 5 DUIDs to confirm the join works in the sample data. Registered capacity values must be current (generator_registration table is a point-in-time snapshot, not time-series — verify this is acceptable for the use case).

---

### Example 3: Settlement Reconciliation (Finance)

**Business Question:** Which participants had disputed or pending settlement amounts in the last four settlement weeks, and what is the total AUD exposure for each?

**Current Process:** The settlements finance team exports the settlement statement from MSATS, runs a VLOOKUP against a status tracker maintained in SharePoint, and produces a reconciliation summary in Excel. The process takes 3–4 hours per settlement week and involves two people because the MSATS export requires a specialist login. Errors in the VLOOKUP have caused mis-classification of disputed amounts twice in the past 12 months.

**Data Available:** `workshop_au.aemo.settlement_amounts` — contains `participant_id`, `settlement_date`, `total_aud`, `settlement_status` (`FINAL`, `REVISED`, `PRELIMINARY`, `DISPUTED`, `PENDING`), and `run_type`.

**Value if Automated:** Saves 3–4 hours per settlement week (approximately 1 day per month). Eliminates VLOOKUP error risk. Finance manager can self-serve dispute status checks without requiring the settlements specialist to be available. Audit trail is maintained in Genie query history.

**Genie Test Question:** "Show me all participants with DISPUTED or PENDING settlement status in the last 4 weeks. Include the settlement date, amount in AUD, and run type."

**Priority:** High

**Dependencies:** Settlement data must be loaded within 24 hours of the MSATS settlement run completing. Confirm data pipeline latency with the data engineering team before committing to a real-time use case. If latency is 48+ hours, the use case scope may need to be adjusted to "last confirmed settlement run" rather than "last 4 weeks."

---

### Example 4: LOR Event Tracking (Compliance)

**Business Question:** How many LOR notices were issued in each NEM region in the last 90 days, and what was the average duration between LOR1 declaration and LOR3 escalation for events that escalated?

**Current Process:** The compliance team searches NEMWEB manually for LOR notices, copies them into a spreadsheet, and manually cross-references LOR1/LOR2/LOR3 sequences by region and time. For a 90-day lookback, this takes one full day. The report is produced quarterly for the compliance manager and is not available on demand.

**Data Available:** `workshop_au.aemo.market_notices` — contains `notice_type` (`LOR1`, `LOR2`, `LOR3`), `region_id`, `effective_date`, `issue_time`, `reason`. LOR sequences can be identified by matching `region_id` and `effective_date` across notice types.

**Value if Automated:** Reduces quarterly compliance reporting time from 1 day to minutes. Enables real-time LOR tracking during high-risk periods (summer demand peaks, planned outages). Supports the compliance manager's regulatory reporting obligations to the AER without manual data collection.

**Genie Test Question:** "How many LOR notices were issued in each NEM region in the last 90 days? Break down by LOR1, LOR2, and LOR3."

**Priority:** High

**Dependencies:** Matching LOR1/LOR2/LOR3 sequences by region and time requires careful date logic — the golden query should be reviewed by the compliance team before production use. The `effective_date` field is the event start time; some LOR notices are issued retrospectively. Confirm with compliance whether `effective_date` or `issue_time` is the correct field for regulatory reporting.

---

### Example 5: SAIDI Performance Reporting (Regulation)

**Business Question:** What was the total SAIDI minutes per customer for each distribution region in the last financial year, broken down by planned and unplanned outages?

**Current Process:** Regulatory reporting produces the SAIDI figure annually from the outage management system, which requires a data extract, manual calculation in Excel, and sign-off by three managers. The process runs across two teams and takes approximately two weeks each year. Ad-hoc SAIDI queries during the year are not possible without running a partial version of the annual process.

**Data Available:** SAIDI is derived from outage event data — `workshop_au.aemo.market_notices` contains planned and unplanned outage events with start time, end time, and customers affected. SAIDI formula: sum of (customers affected * outage duration in minutes) / total customers in the region.

**Value if Automated:** Enables real-time SAIDI tracking throughout the year, not just at year-end. Allows operations managers to intervene earlier when SAIDI trends toward regulatory limits. Reduces annual reporting preparation time from 2 weeks to hours. Provides AER-ready numbers on demand for regulatory inquiries.

**Genie Test Question:** "What was the total outage duration in minutes per market notice type in each NEM region in the last 12 months? Show planned and unplanned separately."

**Priority:** Medium (the exact SAIDI formula requires a derived calculation that may need a custom golden query — this is a Phase 2 item after the simpler use cases are live)

**Dependencies:** SAIDI calculation requires `customers_affected` and total customers per region. Check whether the `market_notices` table includes a `customers_affected` column in the sample data, or whether this needs to be joined from a separate customer count table. If the column is missing, this use case requires a data engineering task before it can be implemented in Genie.

---

## Blank Canvas (Copy This for Each Use Case)

---

**Business Question:**

**Current Process:**

**Data Available:**

**Value if Automated:**

**Genie Test Question:**

**Priority:** High / Medium / Low

**Dependencies:**

---

**Business Question:**

**Current Process:**

**Data Available:**

**Value if Automated:**

**Genie Test Question:**

**Priority:** High / Medium / Low

**Dependencies:**

---

**Business Question:**

**Current Process:**

**Data Available:**

**Value if Automated:**

**Genie Test Question:**

**Priority:** High / Medium / Low

**Dependencies:**
