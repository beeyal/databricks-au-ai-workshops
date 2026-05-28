# AEMO Genie Question Starter Library

50 questions organised by department. Use these during the hands-on exploration block — either as starting points for your own questions or to test Genie's responses before trying your specific use case question.

Each question shows: the question text, which table(s) the answer draws from, and a complexity rating (Easy = straightforward aggregate query; Medium = join or derived calculation; Hard = multi-step logic or time-series comparison).

Questions are written for the AEMO NEM Operations Genie Space configured from `workshop_au.aemo.*` tables.

---

## Market Operations (10 questions)

| # | Question | Data needed | Complexity |
|---|----------|------------|-----------|
| 1 | What was the average spot price in each NEM region yesterday? | `spot_prices` | Easy |
| 2 | Show me the top 5 highest spot price intervals in VIC1 in the last 30 days, including the date and time of each spike. | `spot_prices` | Easy |
| 3 | How many trading intervals had a spot price above $1,000/MWh in SA1 in the last 90 days? | `spot_prices` | Easy |
| 4 | Which NEM region had the highest price volatility last week, measured by standard deviation? | `spot_prices` | Medium |
| 5 | Show me the average spot price by hour of day for NSW1 over the last 7 days. Which hour consistently has the highest price? | `spot_prices` | Medium |
| 6 | How does the current month's average spot price in QLD1 compare to the same month last year? | `spot_prices` | Medium |
| 7 | Show me all trading intervals where the spot price was negative in any region in the last 30 days. How many negative price intervals were there per region? | `spot_prices` | Easy |
| 8 | What was the total NEM dispatch by fuel type yesterday? Which fuel type contributed the most energy? | `dispatch_intervals` | Easy |
| 9 | Which generators in NSW1 were dispatched above 90% of their registered capacity for more than 4 hours yesterday? | `dispatch_intervals`, `generator_registration` | Medium |
| 10 | Show me the net interconnector flow for VIC1 over the last 7 days. On which days was VIC1 a net exporter? | `spot_prices` | Medium |

---

## Asset Management / Network (10 questions)

| # | Question | Data needed | Complexity |
|---|----------|------------|-----------|
| 11 | Which generators in SA1 have a registered capacity above 200 MW and what fuel type are they? | `generator_registration` | Easy |
| 12 | Show me all generators with a maximum ramp rate above 50 MW/minute. Which ones are located in QLD1? | `generator_registration` | Easy |
| 13 | What is the total registered generation capacity in each NEM region, broken down by fuel type? | `generator_registration` | Easy |
| 14 | Which coal-fired generators dispatched less than 50% of their registered capacity last week? Include average dispatch MW and available MW. | `dispatch_intervals`, `generator_registration` | Medium |
| 15 | Show me the top 10 wind generators by total energy dispatched in the last 30 days. Which region are most of them in? | `dispatch_intervals`, `generator_registration` | Medium |
| 16 | How many battery storage units are registered in the NEM, and what is their total combined registered capacity in MW? | `generator_registration` | Easy |
| 17 | Which generators declared zero available MW yesterday even though they are registered as operational? | `dispatch_intervals`, `generator_registration` | Medium |
| 18 | Show me all generators with a minimum stable load above 100 MW. How many are in each region? | `generator_registration` | Easy |
| 19 | What was the average capacity utilisation (dispatch MW / registered capacity) for gas generators in VIC1 over the last 7 days? | `dispatch_intervals`, `generator_registration` | Medium |
| 20 | Which generators had the largest gap between their available MW declaration and their actual dispatch MW last week? Show the top 10. | `dispatch_intervals`, `generator_registration` | Hard |

---

## Settlements & Finance (10 questions)

| # | Question | Data needed | Complexity |
|---|----------|------------|-----------|
| 21 | What was the total settlement amount for each participant in the most recent settlement run? Show the top 10 by absolute value. | `settlement_amounts` | Easy |
| 22 | How many participants had a negative total settlement amount in the last 4 weeks? What was the average negative amount? | `settlement_amounts` | Easy |
| 23 | Show me all settlement runs in the last 3 months and their status (FINAL, REVISED, PRELIMINARY). | `settlement_amounts` | Easy |
| 24 | Which participants had disputed or pending settlement amounts in the last 4 weeks? Include the AUD amount for each. | `settlement_amounts` | Easy |
| 25 | What was the total FCAS settlement amount across all participants in the last month? Which participant received the most FCAS revenue? | `settlement_amounts` | Medium |
| 26 | Show me the energy settlement amount vs FCAS settlement amount for each participant in the most recent FINAL settlement run. | `settlement_amounts` | Medium |
| 27 | What is the total interconnector residue amount across all participants for the last settlement period? | `settlement_amounts` | Easy |
| 28 | Which participants had the largest swing between their PRELIMINARY and FINAL settlement amounts in the last quarter? | `settlement_amounts` | Hard |
| 29 | Show me the trend in total NEM settlement amounts by month over the last 6 months. Is the total increasing or decreasing? | `settlement_amounts` | Medium |
| 30 | Which settlement runs in the last 90 days are still showing REVISED status rather than FINAL? | `settlement_amounts` | Easy |

---

## Compliance & Regulatory Reporting (10 questions)

| # | Question | Data needed | Complexity |
|---|----------|------------|-----------|
| 31 | How many LOR notices were issued in each NEM region in the last 90 days? Break down by LOR1, LOR2, and LOR3. | `market_notices` | Easy |
| 32 | Show me all LOR3 notices issued in any region in the last 12 months. Include the effective date, region, and the first 200 characters of the notice text. | `market_notices` | Easy |
| 33 | Were there any market intervention notices issued in the last 6 months? If so, which regions were affected? | `market_notices` | Easy |
| 34 | How many RERT (Reliability and Emergency Reserve Trader) notices were issued this financial year compared to last financial year? | `market_notices` | Hard |
| 35 | Show me all market notices issued in SA1 in the last 30 days. Group them by notice type and sort by most recent. | `market_notices` | Easy |
| 36 | What was the average time between issue_time and effective_date for LOR2 notices in the last 6 months? | `market_notices` | Medium |
| 37 | Which months in the last 12 months had the highest number of LOR notices of any type? | `market_notices` | Medium |
| 38 | Show me all market notices that mention the word "shortfall" in their reason text in the last 90 days. | `market_notices` | Easy |
| 39 | How many trading intervals in VIC1 had a spot price above the Administered Price Cap threshold of $17,500/MWh in the last 12 months? | `spot_prices` | Easy |
| 40 | Show me the total number of market notices by type for the last 3 months. Which notice type was most common? | `market_notices` | Easy |

---

## IT & Platform (10 questions)

| # | Question | Data needed | Complexity |
|---|----------|------------|-----------|
| 41 | What is the date range of data available in the spot_prices table? What is the earliest and latest settlement date? | `spot_prices` | Easy |
| 42 | How many rows are in each of the five AEMO tables? List the table name and row count. | All tables | Easy |
| 43 | Are there any NEM regions missing from the spot_prices data in the last 30 days? I expect data for NSW1, VIC1, QLD1, SA1, and TAS1. | `spot_prices` | Medium |
| 44 | What is the most recent settlement_date in the dispatch_intervals table? Is it within the last 24 hours? | `dispatch_intervals` | Easy |
| 45 | Show me a count of rows in the dispatch_intervals table by day for the last 14 days. Are there any days with significantly fewer rows than others? | `dispatch_intervals` | Medium |
| 46 | How many distinct DUIDs are in the dispatch_intervals table? How does that compare to the number of DUIDs in generator_registration? | `dispatch_intervals`, `generator_registration` | Medium |
| 47 | Are there any DUIDs in dispatch_intervals that do not appear in generator_registration? List the first 20. | `dispatch_intervals`, `generator_registration` | Hard |
| 48 | What percentage of dispatch interval rows have a null or zero available_mw value in the last 7 days? | `dispatch_intervals` | Medium |
| 49 | Show me the count of market_notices rows by notice_type. Are there any notice_type values that are unexpected or appear to be data quality issues? | `market_notices` | Easy |
| 50 | What is the distribution of settlement_status values in the settlement_amounts table for the last 6 months? Show the count and percentage for each status. | `settlement_amounts` | Easy |

---

## Tips for Using This Library

**Start easy.** Questions 1, 11, 21, 31, and 41 are all easy questions that should work reliably. If one of these fails, there is likely a setup issue with the Genie Space — flag it to the facilitator before moving on.

**Customise the questions.** These are starting points. Change the region, the time window, or the threshold to match what is relevant to your team. "Last 90 days" can become "last financial year." "NSW1" can become "SA1."

**Use your own question.** The best Genie question you will ask today is the one from your use case canvas — the specific question your team needs answered in their daily work. Start with a question from this library to build confidence, then switch to your own question.

**When Genie gives an unexpected answer.** Click the down-arrow next to the result to expand the SQL. Check: is it querying the right table? Is the date filter correct? Is the aggregation what you expected? The SQL is the ground truth — if the SQL is right, the answer is right.

**Questions that involve the word "SAIDI."** SAIDI requires a calculation across outage events and customer counts. The starter library does not include SAIDI questions because they require derived logic that must be configured as a golden query. If SAIDI tracking is a priority use case, note it on your canvas card and discuss with the facilitator — it is a Phase 2 implementation.
