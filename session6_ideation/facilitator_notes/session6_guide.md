# Session 6 Facilitator Guide

This document is for the facilitator running Session 6. Do not share with participants.

---

## Pre-Session Setup (Day Before)

### 1. Genie Space verification — do this the day before, not the morning of

Run `session2_genie_space/genie_config/aemo_space_config.py` if it has not already been run. The notebook takes approximately 5 minutes to complete. It will:
- Check all 5 AEMO tables exist and have data
- Create (or validate) the Genie Space
- Add 15 golden queries
- Run 5 smoke test questions
- Print the Space URL

Save the Space URL somewhere accessible. You will need to share it at the start of the session.

If any smoke test fails, resolve it the day before. Common causes and fixes:

| Failure | Fix |
|---------|-----|
| Table missing or empty | Re-run `setup/00_workspace_setup.py` to reload data |
| Warehouse not running | Open the SQL Warehouse in the UI and check auto-start is enabled |
| API timeout on Space creation | Re-run the setup notebook — it is idempotent |
| Smoke test returns empty result | Check the golden query for that question type; the sample data may not have rows matching the default date range |

### 2. Grant participant access

Run the access grant for all participants before they arrive. Each participant needs:
- `CAN_USE` on the Genie Space
- `SELECT` on `workshop_au.aemo.*`

If the AEMO data platform team manages access, send them the Space ID and participant email list at least 24 hours before.

### 3. Test 5 questions as a participant account, not as admin

The admin account often has broader access than participants. Open the Genie Space in an incognito browser window using a participant-level account and ask these 5 questions. All 5 must work:

1. "What was the average spot price in each NEM region yesterday?"
2. "Show me the top 5 generators by dispatch in NSW1 yesterday."
3. "Were there any LOR notices issued in the last 7 days?"
4. "What was the total settlement amount in the most recent settlement run?"
5. "What was the total NEM dispatch by fuel type yesterday?"

If any of these fails for a participant account but works for the admin account, the issue is permissions — not the Genie Space configuration. Check UC `SELECT` grants.

### 4. Print or pre-share activity materials

- `activities/01_use_case_canvas.md` — one copy per participant. Printing double-sided A4 works well. Include 3–4 blank canvas templates per person so they can document multiple use cases.
- `activities/02_question_starter_library.md` — one copy per table, or share the link in the meeting chat at the start of the exploration block.

### 5. Prepare the room

| Item | Setup |
|------|-------|
| Tables | Groups of 4–6, not theatre seating. This is a workshop, not a lecture. |
| Whiteboard | Reserve one section for the 2x2 prioritisation grid (draw it before the session) |
| Sticky notes | One colour per team for the prioritisation exercise |
| Timer | Visible to the room — use your phone or a projected timer |
| Spare adapters / chargers | Participants always forget them |

---

## Timing Guide (Minute by Minute)

### Block 1: Context Setting (0:00 – 0:30)

**0:00 — Welcome and objectives (5 min)**
- Welcome participants; brief housekeeping
- One sentence on what today is not: "This is not a training on SQL or data engineering — you won't write any code today."
- One sentence on what today is: "By the end of this session, your team will have identified and prioritised 3 AI use cases that are ready to move into production."
- Share the Genie Space URL in chat and ask everyone to open it and confirm they can see the chat interface before you continue

**0:05 — What Genie can do for AEMO (15 min)**
- Live demo: ask 3 questions in the Genie Space that are directly relevant to the audience. Pick from the question starter library based on which teams are in the room (Market Ops, Finance, Compliance — ask one question per team type present).
- Show: asking the question, viewing the result, expanding the SQL, asking a follow-up
- Be honest about limitations: "Genie answers questions about historical data. It cannot run real-time SCADA queries. It cannot predict prices. It cannot override manual settlement processes."
- Show one example of a question Genie answers well, and one example of a question that requires a golden query to be added — both are realistic outcomes from today.

**0:20 — Set expectations for today (10 min)**
- Walk through the session structure briefly
- Explain the use case canvas — hold up a printed example, point to each field
- Explain the outcome: "By 3pm, each team will have 3–5 canvas cards and we will have scored them together to find the top 3 across the group."
- Answer questions about format (not about Genie capability — redirect those to the discovery exercise)

---

### Block 2: Use Case Discovery (0:30 – 1:15)

**Facilitation technique: Jobs to Be Done**

The most common mistake in use case discovery is allowing participants to propose solutions rather than articulate problems. "We want a dashboard" is a solution. "We need to know by 8am each day whether any region had overnight price spikes above $1000/MWh, because that affects the morning briefing" is a problem with a job to be done.

The "jobs to be done" framing forces specificity:
- "When [trigger event], I need to know [information], so that I can [action]."
- Example: "When I start my shift, I need to know the overnight dispatch mix for VIC1, so that I can brief the market manager before the 8am call."

**0:30 — Brief the teams (5 min)**
- Distribute canvas cards
- Explain the jobs-to-be-done sentence structure. Write it on the whiteboard: "When [event], I need [information], so I can [action]."
- Tell teams: "I want each team to produce at least 3 canvas cards in the next 40 minutes. You do not need to complete every field — the 'Genie Test Question' is the most important one."

**0:35 — Teams work on canvases (40 min)**

Circulate between tables. Your job is to:
1. Listen for solution-first language and reframe it. "You want a dashboard — what question would the dashboard answer?" 
2. Push for specificity on the current process. "How long does it take today?" is the single most useful prompt. Teams underestimate current process time, and when they say it out loud (e.g., "I spend 2 hours every Monday on this") the value of automation becomes concrete.
3. Help teams identify which tables have the data. "Which report or system do you currently pull this from?" maps directly to a table in most cases.
4. Note use cases that are clearly out of scope (real-time, predictive, non-NEM). Do not shut them down in the room — write "Phase 2 - requires additional data" on the card and move on.

**Common stuck points and how to unblock:**

| Team says | Your response |
|-----------|--------------|
| "We don't have time for this, we already know what we want" | "Great — write that down on the canvas in the exact question format and we'll test it in 20 minutes." |
| "We're not sure what tables our data is in" | "That's exactly what the 'Data Available' field is for — write down the report name or system name and we'll figure out the table mapping together." |
| "We want to predict prices" | "That's a Phase 2 capability — it requires a forecasting model, not just a query. Write it on a card as a future use case. For today, let's find the historical version of that question: 'what patterns do we see before price spikes?'" |
| "Genie can do all of this, we don't need to prioritise" | "Our goal today is to find the 3 most valuable use cases to build first. Once those are working, we expand. Building everything at once is how you end up with nothing working well." |

**1:10 — 5-minute warning (1 min)**
Call time with 5 minutes remaining. Ask teams to complete their best canvas card and prepare one sentence describing their top use case.

**1:15 — Gallery walk (skippable if time is tight)**
Each team shares one card with the room — just the business question and the value. This takes 2 minutes per team. Skip this if you are behind schedule.

---

### Block 3: Hands-on Genie Exploration (1:15 – 2:15)

**1:15 — Brief the block (5 min)**
- Share the question starter library link / distribute printed copies
- Ask each person to pick one question from the library to start with, then switch to the Genie Test Question from their canvas card
- Explain: "When Genie answers your question, click the arrow to expand the SQL. If the SQL looks right, the answer is right. If the answer looks wrong, screenshot it and bring it to me."

**1:20 — Hands-on exploration (50 min)**

Your job during this block:
1. **Circulate quickly** — do not spend more than 3 minutes at any one person's screen
2. **Capture questions that fail** — note the exact question text and the error or bad result. These become golden query candidates for the production Genie Space.
3. **Capture questions that work well** — especially ones you did not anticipate. These validate the Space configuration.
4. **Watch for participants who are not typing anything** — they are either stuck or sceptical. Address them individually.

For participants struggling to get Genie to answer correctly, try these reframings:
- Add specificity: "What was the spot price in NSW1 yesterday?" instead of "What are prices?"
- Add a time range: "...in the last 7 days" or "...yesterday"
- Use the exact region codes: "NSW1" not "NSW" or "New South Wales"
- Break compound questions apart: ask for the average first, then ask for the comparison

**2:10 — Wrap-up the block (5 min)**
Ask: "Who found a question that Genie answered well and surprised them?" — get 2–3 responses.
Ask: "Who found a question that Genie could not answer?" — note those. They are Phase 2 items.

---

### Block 4: Prioritisation and Roadmap (2:15 – 2:45)

**2:15 — Scoring exercise setup (5 min)**

Explain the 2x2:
- Y-axis: Value to the business (high = saves significant time, reduces significant risk, or enables better decisions)
- X-axis: Effort to implement (low effort = data already in the Space, question works today; high effort = requires new data, custom logic, or integration work)

Quick win = high value + low effort → **do first**
Phase 2 = high value + high effort → **plan and sequence**
Low priority = low value + low effort → **nice to have, do later**
Investigate further = low value + high effort → **question whether to do at all**

**2:20 — Teams score their canvases (15 min)**

Each team:
1. Scores each canvas card (High/Medium/Low value; Easy/Medium/Hard effort)
2. Places sticky notes on the 2x2 (one sticky per canvas card, team name written on the sticky)
3. Nominates their team's top pick for the room-wide discussion

**2:35 — Room-wide prioritisation (10 min)**

Look at the 2x2 together. The "quick wins" quadrant is where you start.

- If fewer than 3 quick wins are visible: discuss which Medium-effort, High-value items could become quick wins with a small data engineering change.
- If more than 6 items are in the quick wins quadrant: ask each team to rank their quick win — "if you could only do one of these, which one?" Use dots for dot-voting if helpful.
- Identify the top 3 across the group. For each, ask: "Who will own this?" Write a name next to the sticky.

**Common prioritisation traps:**

| Situation | How to handle |
|-----------|--------------|
| Teams horse-trade ("we'll vote for yours if you vote for ours") | Refocus on value to the business, not to the team. "Which of these will save the most analyst time across AEMO?" |
| A use case that worked perfectly in Genie is still rated "high effort" | Clarify the effort axis: "Effort to get into production, not effort to answer the question in today's demo. What would actually need to happen?" |
| Everyone wants the same use case | That is a good outcome. Confirm the owner and dependencies, and document it as the first production item. |
| The top 3 selected are all from the same team | Check whether the other teams' use cases were understood. Sometimes teams with less domain knowledge in the room have genuinely important use cases that get overlooked. |

---

### Block 5: Wrap-Up (2:45 – 3:00)

**2:45 — Summary (5 min)**
- Read back the top 3 use cases with their owners
- Confirm dependencies for each
- Note which questions failed today and need golden query work before production

**2:50 — Next steps (5 min)**
- How to request a Genie Space for their team: contact [AEMO data platform team / Databricks SA]
- Timeline expectation: a production Genie Space for a single use case takes 2–4 weeks to configure, test, and certify
- The canvas cards from today feed directly into the production backlog — the data platform team will use them to prioritise data onboarding
- Participant access to today's Genie Space: "You can keep using the Space you used today. The data is sample data, not your production data, but the questions work the same way."

**2:55 — Feedback form (5 min)**
Share the link in chat and ask participants to complete it before they leave. Five questions, 2 minutes. If participants leave without filling it in, follow up with a one-click survey via email that day.

---

## Handling Sceptical Participants

Scepticism in this session usually takes three forms. Handle each differently.

### "What if Genie is wrong?"

This is the most common objection and it is legitimate. Address it directly.

**Response:** "That is exactly the right question to ask. Genie generates SQL and runs it against the real data. You can always expand the SQL and see exactly what query it ran. If the SQL looks right, the answer is right. If the SQL is wrong, you can see why and correct it. Genie is not a black box — the SQL is always visible."

**Follow-up action:** Show them how to expand the SQL in the Genie Space. This is the single most effective trust-building move. Once a sceptical participant sees the underlying SQL, they shift from "I don't trust this" to "I can verify this."

For critical compliance reporting, add: "Genie is a query assistant, not a sign-off authority. The analyst still reviews and approves the output before it goes to the regulator. What changes is the 2 hours of manual data preparation before the analyst can even start reviewing."

### "Our data is too sensitive to put in Genie"

**Response:** "The Genie Space only has access to the tables that have been explicitly granted to it. It cannot reach data you have not added. And the AI model that Genie uses is the in-region Provisioned Throughput model — your questions and your data do not leave the Australian East region."

If they are concerned about specific data types (e.g., bilateral contract details): "You are right that [specific data type] should not be in this Space. We would handle that by not adding those tables as trusted assets. Genie only answers questions about the data it has been given access to."

### "We tried this before and it didn't work"

**Response:** Probe what "this" means — it is rarely the same product or configuration. Common prior experiences: a generic LLM chatbot that hallucinated, a legacy BI tool with unreliable results, or a pilot that was not properly configured.

"What did you try? And what did you mean by 'didn't work'?" Listen carefully. Then: "The specific issue you had was [problem]. What we have set up today is different in these ways: [specific differences]." Then ask them to try a question from the starter library. The hands-on test is more persuasive than any argument.

Do not dismiss prior bad experiences. Acknowledge them, distinguish the current situation, and let the product speak for itself.

---

## AEMO Terminology Quick Reference

Use this if you need to clarify a term during facilitation. Participants will use these terms assuming you know them.

| Term | What it means |
|------|--------------|
| NEM | National Electricity Market — the interconnected electricity market covering QLD, NSW, VIC, SA, TAS |
| DUID | Dispatchable Unit Identifier — a unique code for each generator unit |
| RRP | Regional Reference Price — the spot price for a 30-minute trading period in a specific region |
| LOR | Lack of Reserve — notice issued when reserve levels fall below thresholds (LOR1/LOR2/LOR3 by severity) |
| RERT | Reliability and Emergency Reserve Trader — mechanism AEMO uses to contract reserve capacity during LOR events |
| FCAS | Frequency Control Ancillary Services — services that maintain system frequency at 50 Hz |
| MSATS | Market Settlement and Transfer Solution — AEMO's metering and settlement database |
| NEMWEB | AEMO's public data portal — where market notices are published |
| SAIDI | System Average Interruption Duration Index — minutes of outage per customer per year; regulatory metric |
| APC | Administered Price Cap — $17,500/MWh ceiling on spot prices |
| 5-minute dispatch | NEM dispatch runs in 5-minute intervals; settlement runs in 30-minute trading periods |
| AEST / AEDT | Australian Eastern Standard/Daylight Time — all NEM data is timestamped in AEST (UTC+10) or AEDT (UTC+11) |
| Financial year | AEMO financial year runs 1 July – 30 June, same as the Australian government fiscal year |

---

## After the Session

### What to do within 24 hours

1. **Photograph the 2x2 grid** before the room is cleaned up. Send the photo to the AEMO data platform team and the Databricks SA with a one-line summary of the top 3 use cases and their owners.

2. **Record the Genie question failures.** For each question that returned a wrong answer or an error, note: the exact question text, the table it should have queried, and what the correct answer should be. These are golden query candidates.

3. **Send the participant feedback form link** to anyone who did not fill it in during the session.

4. **Update the session log** with: attendance count, use cases discovered, use cases prioritised, questions that failed.

### What to hand off to the Databricks SA

- Top 3 use cases with owners and dependencies
- List of failed questions (golden query backlog)
- Any data quality issues observed (wrong numbers, missing regions, date gaps)
- Participant feedback themes (what was well received, what caused confusion)

### What happens next

The top 3 prioritised use cases become the production backlog. The typical path:
1. Data engineering team confirms the production tables for each use case and adds them to a production Genie Space
2. Databricks SA adds golden queries for each use case
3. The Space is tested against production data and certified
4. Business user group is granted access to the production Space

Timeline: 2–4 weeks per use case, depending on data availability and golden query complexity.
