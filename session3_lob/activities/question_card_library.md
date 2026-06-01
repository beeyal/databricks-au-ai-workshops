# AEMO Genie Question Card Library

**Purpose:** Reference cards for business users exploring the AEMO NEM Operations Genie Space.
Each card includes the question text, which table Genie will query, difficulty level, and whether it works well in Agent mode (multi-step reasoning).

**Difficulty key:**
- **Easy** — Single table, simple filter, direct answer
- **Medium** — Multiple tables or aggregation required; Genie may ask a clarifying question
- **Hard** — Complex logic, window functions, or cross-table joins; always verify with "Show SQL"

**Agent mode:** Genie Agent mode can break a question into sub-queries and reason across the results. Mark "Yes" means the question benefits from Agent mode.

---

## Category 1 — Market Operations (10 questions)

| # | Question | Primary table | Difficulty | Agent mode |
|---|---|---|---|---|
| MO-01 | "What was the average spot price in each NEM region yesterday?" | `spot_prices` | Easy | No |
| MO-02 | "Which NEM region had the highest average spot price this month?" | `spot_prices` | Easy | No |
| MO-03 | "Were there any price separations between NSW1 and VIC1 last week? (times when their prices diverged by more than $50/MWh)" | `spot_prices` | Medium | No |
| MO-04 | "How many 30-minute intervals had negative spot prices in SA1 in the last 90 days?" | `spot_prices` | Easy | No |
| MO-05 | "What was the demand-weighted average price across all NEM regions in the last 30 days?" | `spot_prices` | Medium | No |
| MO-06 | "Which trading intervals had the Administered Price Cap (APC) active this year, and in which regions?" | `spot_prices` | Easy | No |
| MO-07 | "Show me the hourly average spot price for VIC1 for each day this week" | `spot_prices` | Medium | No |
| MO-08 | "How has the average monthly spot price in NSW1 trended over the last 24 months?" | `spot_prices` | Medium | No |
| MO-09 | "What is the total megawatt-hours of energy traded in the NEM this week? (sum of demand across all intervals and regions)" | `spot_prices` | Medium | No |
| MO-10 | "Compare the evening peak price (5pm–8pm) versus the overnight price (midnight–6am) for each region this month" | `spot_prices` | Hard | Yes |

---

## Category 2 — Generator Performance (10 questions)

| # | Question | Primary table | Difficulty | Agent mode |
|---|---|---|---|---|
| GP-01 | "Show me the top 10 generators by total dispatch in QLD1 yesterday" | `dispatch_intervals`, `generator_registration` | Easy | No |
| GP-02 | "What is the total registered capacity of all wind farms in SA1?" | `generator_registration` | Easy | No |
| GP-03 | "Which coal generators had a capacity factor below 50% last month?" | `dispatch_intervals`, `generator_registration` | Medium | No |
| GP-04 | "How has battery storage dispatch in VIC1 changed month-by-month over the last 12 months?" | `dispatch_intervals`, `generator_registration` | Medium | No |
| GP-05 | "Which generators in NSW1 were dispatched above their registered capacity at any point this week?" | `dispatch_intervals`, `generator_registration` | Hard | Yes |
| GP-06 | "Show me the average dispatch by fuel type for each hour of the day in SA1 this month" | `dispatch_intervals`, `generator_registration` | Medium | Yes |
| GP-07 | "Which participant operates the most generation capacity in the NEM by registered MW?" | `generator_registration` | Easy | No |
| GP-08 | "What fuel types were dispatched during the evening peak (5pm–8pm) in NSW1 yesterday, and how much?" | `dispatch_intervals`, `generator_registration` | Medium | No |
| GP-09 | "Are there any generators that have had zero dispatch for the last 7 days but are registered as available?" | `dispatch_intervals`, `generator_registration` | Hard | Yes |
| GP-10 | "What is the average dispatch ramp rate for gas generators in VIC1 this month? (change in MW per interval)" | `dispatch_intervals`, `generator_registration` | Hard | Yes |

---

## Category 3 — Price Analysis (10 questions)

| # | Question | Primary table | Difficulty | Agent mode |
|---|---|---|---|---|
| PA-01 | "Were there any spot prices above $1000/MWh last month, and if so when and where?" | `spot_prices` | Easy | No |
| PA-02 | "What was the maximum price spike in SA1 this year, and what date did it occur?" | `spot_prices` | Easy | No |
| PA-03 | "Which region had the highest price volatility (standard deviation) last quarter?" | `spot_prices` | Medium | No |
| PA-04 | "Compare this month's average spot price with the same month last year across all regions" | `spot_prices` | Medium | No |
| PA-05 | "How long did the most recent price spike above $5000/MWh in NSW1 last? (number of 30-min intervals)" | `spot_prices` | Hard | Yes |
| PA-06 | "Show me the distribution of spot prices in QLD1 this month — how many intervals were in each $100 price band?" | `spot_prices` | Hard | Yes |
| PA-07 | "What percentage of trading intervals this year had a negative spot price in SA1?" | `spot_prices` | Medium | No |
| PA-08 | "What is the correlation between SA1 spot prices and TAS1 spot prices this month?" | `spot_prices` | Hard | Yes |
| PA-09 | "How does the morning ramp price (6am–9am) compare to the evening ramp price (5pm–8pm) in VIC1 this month?" | `spot_prices` | Medium | Yes |
| PA-10 | "Which week this year had the highest total settlement value across all regions?" | `spot_prices`, `settlement_amounts` | Hard | Yes |

---

## Category 4 — Settlements & Finance (5 questions)

| # | Question | Primary table | Difficulty | Agent mode |
|---|---|---|---|---|
| SF-01 | "What is the total settlement amount for the most recent settlement run, broken down by participant?" | `settlement_amounts` | Easy | No |
| SF-02 | "Which participants have had disputed settlement amounts in the last 4 weeks?" | `settlement_amounts` | Easy | No |
| SF-03 | "What is the trend in total weekly settlement amounts over the last 12 weeks?" | `settlement_amounts` | Medium | No |
| SF-04 | "Which 5 participants received the largest net settlement payments last month?" | `settlement_amounts` | Easy | No |
| SF-05 | "How many settlement runs have been revised (run number > 1) in the last quarter, and which participants were affected?" | `settlement_amounts` | Medium | Yes |

---

## Category 5 — Compliance & Reporting (5 questions)

| # | Question | Primary table | Difficulty | Agent mode |
|---|---|---|---|---|
| CR-01 | "List all market notices issued by AEMO in the last 30 days" | `market_notices` | Easy | No |
| CR-02 | "Which NEM region has had the most LOR events (LOR1, LOR2, or LOR3) this year?" | `market_notices` | Easy | No |
| CR-03 | "Were there any RERT (Reliability and Emergency Reserve Trader) activations this month?" | `market_notices` | Easy | No |
| CR-04 | "How many high-price events (above $5000/MWh) occurred in each region this financial year?" | `spot_prices`, `market_notices` | Medium | Yes |
| CR-05 | "Which generators in SA1 were the subject of dispatch directions or notices in the last 90 days?" | `market_notices`, `generator_registration` | Hard | Yes |

---

## Quick-reference: all 40 questions at a glance

| Code | Question (abbreviated) | Difficulty |
|---|---|---|
| MO-01 | Average spot price each region yesterday | Easy |
| MO-02 | Highest average price region this month | Easy |
| MO-03 | NSW1/VIC1 price separations last week | Medium |
| MO-04 | Negative price intervals SA1 last 90 days | Easy |
| MO-05 | Demand-weighted average price last 30 days | Medium |
| MO-06 | APC active intervals this year | Easy |
| MO-07 | Hourly average VIC1 this week | Medium |
| MO-08 | NSW1 monthly price trend 24 months | Medium |
| MO-09 | Total NEM MWh traded this week | Medium |
| MO-10 | Evening peak vs overnight price comparison | Hard |
| GP-01 | Top 10 generators QLD1 yesterday | Easy |
| GP-02 | Total wind capacity SA1 | Easy |
| GP-03 | Low capacity-factor coal generators last month | Medium |
| GP-04 | Battery dispatch VIC1 monthly trend | Medium |
| GP-05 | Generators dispatched above registered capacity | Hard |
| GP-06 | Dispatch by fuel by hour SA1 this month | Medium |
| GP-07 | Participant with most registered capacity | Easy |
| GP-08 | Fuel type dispatch during evening peak NSW1 | Medium |
| GP-09 | Zero-dispatch but available generators | Hard |
| GP-10 | Gas ramp rate VIC1 this month | Hard |
| PA-01 | Prices above $1000/MWh last month | Easy |
| PA-02 | Maximum price spike SA1 this year | Easy |
| PA-03 | Highest price volatility region last quarter | Medium |
| PA-04 | Month-on-month price comparison YoY | Medium |
| PA-05 | Duration of most recent price spike NSW1 | Hard |
| PA-06 | Price distribution QLD1 this month | Hard |
| PA-07 | Percentage negative price intervals SA1 | Medium |
| PA-08 | SA1/TAS1 price correlation this month | Hard |
| PA-09 | Morning vs evening ramp price VIC1 | Medium |
| PA-10 | Highest settlement week this year | Hard |
| SF-01 | Settlement totals by participant latest run | Easy |
| SF-02 | Disputed settlements last 4 weeks | Easy |
| SF-03 | Weekly settlement trend last 12 weeks | Medium |
| SF-04 | Top 5 net settlement receivers last month | Easy |
| SF-05 | Revised settlement runs last quarter | Medium |
| CR-01 | All market notices last 30 days | Easy |
| CR-02 | Most LOR events by region this year | Easy |
| CR-03 | RERT activations this month | Easy |
| CR-04 | High-price events by region this FY | Medium |
| CR-05 | SA1 generators subject to dispatch directions | Hard |

---

## Notes for facilitators

**Agent mode** questions benefit from turning on Genie's Agent mode (the toggle in the Genie chat header). Agent mode lets Genie chain multiple queries and reason across the results, which is useful for the Hard questions above. It takes longer but produces more reliable answers for complex requests.

**Hard questions in workshops:** Do not use Hard-rated questions as guided tasks for new users. Reserve them for the "open question time" in Part 3, or for advanced follow-up sessions.

**Data lag reminder:** All data has a 30–60 minute minimum lag. Questions about "right now" or "live" conditions should be directed to AEMO NEMWEB for real-time data.

**Updating this library:** When the AEMO data team adds new tables to the Genie Space, add new question cards here following the same format. Include the primary table name so participants know where the data comes from.
