# Session 3: Databricks for Business — AEMO Genie Enablement

**Track:** Business User Enablement
**Duration:** 2 hours
**Audience:** Business users, operations staff, and analysts who will use Genie — not build it
**Format:** 30-person facilitated workshop, entirely through the Genie UI. No coding.

---

## Overview

Session 3 is where the work done in Sessions 1 and 2 pays off for the business. Participants arrive, open their browser, and immediately start asking questions about AEMO data in plain English — no training on SQL, no PySpark, no notebooks required.

The session is structured around six guided tasks that cover the core AEMO operational use cases: spot prices, dispatch instructions, market notices, settlement summaries, and network outage queries. After the guided tasks, participants work through their own questions with facilitator support. The session closes with a short segment on creating and sharing a simple NEM operations dashboard from Genie results.

### Why this session matters

Business users who experience a well-configured Genie Space for the first time tend to go back to it. The goal of Session 3 is not just to demonstrate the capability — it is to give participants enough successful interactions that they form a habit of using Genie for their day-to-day operational questions.

The session is deliberately short and focused. Two hours is long enough for participants to ask 15–20 questions and get comfortable with the interface, but short enough to maintain energy and avoid cognitive overload. Resist the temptation to add more content.

---

## What Participants Will Do

| Activity | Duration | What they walk away with |
|----------|----------|--------------------------|
| Orientation — Genie UI tour (facilitator-led) | 15 min | Confidence to navigate the space independently |
| Guided Task 1: Spot Prices | 15 min | Know how to query price data across regions and time periods |
| Guided Task 2: Dispatch Instructions | 15 min | Understand how to ask about unit-level dispatch |
| Guided Task 3: Market Notices | 15 min | Can find and filter market notices by type and date |
| Guided Task 4: Settlement Summaries | 15 min | Can retrieve settlement period summaries |
| Guided Task 5: Network Outages & Incidents | 15 min | Can query compliance event data |
| Guided Task 6: Build a Dashboard | 15 min | Have created and shared a simple NEM operations view |
| Open exploration — your own questions | 15 min | Confidence that Genie handles questions from their actual work |

**There is no coding in this session.** Every activity is through the Genie Space UI in a standard browser.

---

## What Participants Need Before They Arrive

Participants need a Databricks workspace account and access to the AEMO Genie Space. Nothing else.

| Requirement | Who arranges it |
|-------------|----------------|
| Databricks workspace login | IT / platform team (should be arranged 48 hours before) |
| Access to the AEMO Genie Space | Facilitator (part of Session 2 Admin setup) |
| `SELECT` on `workshop_au.aemo.*` | Facilitator (part of Session 2 Admin setup) |
| Laptop or desktop with a modern browser | Participant |

Participants do not need to install anything. Chrome and Edge are recommended. Safari works but has occasional rendering differences with the Genie dashboard builder.

---

## Facilitator Setup Required

**Allow approximately 30 minutes before the session starts** to complete the following. This setup is only required once per session delivery — not once per participant.

### Step 1 — Create or validate the AEMO Genie Space

```
session3_business/genie_config/aemo_genie_space_setup.py
```

Run this notebook in the workshop workspace. It:
- Creates the `Workshop — AEMO Operations` Genie Space if it does not exist, or validates an existing one
- Adds `workshop_au.aemo.*` tables as trusted assets
- Loads 10 validated golden queries covering spot prices, dispatch, notices, settlement, and outages
- Sets the Genie Space instructions with AEMO domain context (NEM regions, interval numbering, financial year definition, data quality flag meanings)
- Prints a verification summary and the Genie Space URL

If the script exits cleanly with `[PASS]` on all checks, the Genie Space is ready. If any check fails, the script will print a remediation instruction — follow it before proceeding.

### Step 2 — Verify participant access

Confirm all participant accounts have `CAN_USE` on the Genie Space and `SELECT` on the trusted tables. The fastest way:

1. In the Genie Space, click the permissions icon (top-right)
2. Confirm the `aemo-genie-users` group (or the equivalent group for this workshop) has `Can Use`
3. If participants are not in a group, add them individually — they only need `Can Use`, not `Can Manage`

If access is not yet granted, run the access grant script:

```
session3_business/genie_config/grant_participant_access.py
```

This script accepts a list of participant emails and applies `CAN_USE` on the Genie Space and `SELECT` on the tables in bulk.

### Step 3 — Test 5 questions in the Genie Space

Open the Genie Space as a participant (not as the workspace admin) and ask the following five questions. All five must return a correct, complete answer before participants arrive.

1. "What was the average spot price in VIC1 last Tuesday?"
2. "Show me dispatch instructions for all units in NSW1 in the last 24 hours."
3. "How many market notices were issued this week? Break them down by category."
4. "What was the total energy settlement for QLD1 in the last billing period?"
5. "List all network outages in SA1 in the last 30 days."

If any question produces an incorrect answer or an error, check the Genie Space golden queries and add or edit the relevant query before the session. Do not run Session 3 if questions 1 or 2 above are failing — those are in the first two guided tasks and a failure there will undermine participant confidence for the rest of the session.

### Step 4 — Prepare the question card library

Print or share `activities/question_card_library.md` with participants at the start of the session. This document contains 30 questions participants can ask during the guided tasks and open exploration — sorted by topic area, graduated by complexity, with notes on what a good answer looks like.

Digital sharing works fine: paste the link in the meeting chat or share via email before the session.

---

## Session Run Sheet

The following is a guide for the facilitator. Times are approximate — adjust based on group pace and questions.

| Time | Activity | Notes |
|------|----------|-------|
| 0:00 | Welcome and housekeeping | Share Genie Space URL; ask all participants to open it before continuing |
| 0:05 | UI orientation tour | Walk through the Genie Space interface: asking a question, viewing SQL, accepting/rejecting results, bookmarking |
| 0:15 | Guided Task 1 — Spot Prices | Participants ask from the question card; facilitator demos the first question, then participants do the rest independently |
| 0:30 | Guided Task 2 — Dispatch Instructions | |
| 0:45 | Guided Task 3 — Market Notices | |
| 1:00 | Guided Task 4 — Settlement Summaries | |
| 1:15 | Guided Task 5 — Network Outages & Incidents | |
| 1:30 | Guided Task 6 — Build a Dashboard | Each participant creates a 2-panel dashboard from their Genie results and shares it with the group |
| 1:45 | Open exploration | Participants ask their own questions; facilitator circulates |
| 1:55 | Wrap-up and next steps | How to request access for colleagues; who to contact with questions; feedback form |
| 2:00 | End |  |

---

## Activities

The `activities/` folder contains:

| File | Contents |
|------|----------|
| `question_card_library.md` | 30 questions for use during guided tasks and open exploration, sorted by topic, with notes on expected answers |
| `dashboard_building_guide.md` | Step-by-step guide for creating a simple 2-panel NEM operations dashboard from Genie results (used in Guided Task 6) |

---

## Common Issues on the Day

| Issue | Likely cause | Resolution |
|-------|-------------|------------|
| Participant cannot open the Genie Space | Access not granted | Run `grant_participant_access.py` or add the user manually via the Genie Space permissions panel |
| Genie returns wrong answer for a spot price question | Golden query not loaded or question phrasing mismatch | Open the Genie Space management panel, check SQL queries; add or edit the relevant golden query |
| "I can't find the SQL" | Participant is in the simplified view | Click the caret (▾) next to the answer to expand and show the SQL |
| Dashboard builder is unavailable | Feature not enabled or wrong UI version | Verify that the workspace is on the current Genie Spaces version; use the AI/BI dashboard builder as an alternative |
| Participant's question takes more than 30 seconds | Warehouse cold start or large result set | Check the SQL warehouse is set to `Auto` scaling with at least 1 cluster; pre-warm by running a query before participants arrive |
| "Genie says it doesn't have access to that data" | Trusted asset not added to the Space | Add the relevant table in the Genie Space management panel under Data |

---

## Prerequisites for Running This Session

This session cannot run until Session 2 (Technical Enablement) has been completed for the same workspace. The following must be true before participants arrive:

- [ ] AEMO Genie Space created and verified (Session 2 Lab 04 output)
- [ ] PT endpoint in `READY` state (Session 2 prerequisite)
- [ ] AI Gateway enabled on the Space's SQL warehouse (Session 2 Lab 02 output)
- [ ] `workshop_au.aemo.*` tables loaded with AEMO sample data (`setup/00_workspace_setup.py`)
- [ ] All participants have workspace accounts (Viewer level or above)
- [ ] Participant group has `CAN_USE` on the Genie Space and `SELECT` on trusted tables
- [ ] 10+ golden queries loaded in the Genie Space knowledge store

If any of the above is not in place, do not start the session. The experience will be poor and will undermine participant confidence in Genie for weeks. Reschedule if necessary — it is better to delay by a day than to run a session where the tool does not work.

---

## After the Session

### Participant next steps

- Participants can continue using the Genie Space in their normal browser after the session
- To get access for a colleague, they should contact the workshop facilitator or their workspace admin
- For questions about the data in the Space (why a number looks wrong, what a column means), the first step is always to expand the SQL and check what query Genie generated

### Facilitator next steps

- Export the session feedback form responses and share with the Databricks SA
- Note any questions that Genie answered poorly — add them as golden queries to improve the Space before it goes to production users
- Flag any data quality issues noticed during the session (wrong totals, missing regions, unexpected nulls) to the data team
- If the customer plans to move to a production Genie Space for this use case, share the `genie_config/aemo_genie_space_setup.py` script as a starting template for their production configuration

### Transitioning to production

Session 3 uses the workshop Genie Space. Moving to a production deployment involves:

1. Creating a new Genie Space pointed at the customer's production AEMO data tables (not the synthetic workshop data)
2. Rebuilding the golden queries against production table schemas
3. Certifying the Space (`space_certification_status` tag) following the customer's internal data governance process
4. Setting up an AI Gateway endpoint with the customer's own PT model deployment
5. Granting access to the production business user group

The Databricks AU SA team can support each of these steps — reach out after the session.
