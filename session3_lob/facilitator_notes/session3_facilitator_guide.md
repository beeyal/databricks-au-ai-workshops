# Session 3 Facilitator Guide — AEMO Genie Experience

**Session:** Business User Enablement | Genie for NEM Operations
**Audience:** 30 non-technical business users
**Duration:** 2 hours
**Location:** [TODO: insert room/link]
**Facilitator:** [TODO: insert name]
**Technical support:** [TODO: insert name and mobile]

---

## 1. Pre-session setup checklist

Complete these steps the day before, then again on the morning of the session.

### Day before

| Task | How | Done? |
|---|---|---|
| Run `genie_config/aemo_genie_space_setup.py` from start to finish | Open the notebook on the workshop cluster and run all cells. All cells must show green or ✅ output. | |
| Verify all 5 tables have data | Step 1 cell output — each table must show > 0 rows | |
| Confirm the SQL Warehouse is set to auto-start | SQL → SQL Warehouses → your warehouse → Edit → ensure "Auto stop" is set to at least 60 min idle | |
| Test the Genie Space URL works from outside your account | Open the URL in an incognito/private browser window, log in as a test participant, confirm the Space loads | |
| Confirm all 30 participants have workspace access | Check with IT or workspace admin — every participant email must be in the workspace user list | |
| Share the lab notebook with participants | Repos or Workspace Files → right-click → Permissions → Add all participants with "Can Run" permission | |
| Prepare the Genie URL slide | Add the Space URL to slide 2 of the session deck so it is visible when people walk in | |
| Print question card library (optional) | Print `activities/question_card_library.md` — one copy per table group of 5–6 people | |

### Morning of the session (at least 30 minutes before start)

| Task | How to verify | Expected result |
|---|---|---|
| All 5 tables have data | Run Step 1 in `genie_config/aemo_genie_space_setup.py` | Each table: > 0 rows, ✅ |
| SQL Warehouse is running (not starting) | SQL → SQL Warehouses | Green dot |
| Genie Space is visible | Left sidebar → Genie → "AEMO NEM Operations" | Space appears, chat loads |
| 5 smoke tests pass | Run Step 6 in the setup notebook | All ✅ PASSED |
| Participant URL is accessible | Open in incognito and log in | Genie chat loads and responds |
| Projector/screen shows the URL | Display slide 2 of session deck | URL visible from back of room |
| Slack/Teams message sent | Post the URL and session agenda to the participant channel 30 min before start | Message delivered |

---

## 2. Timing breakdown (minute by minute)

| Clock time | Duration | What happens | Facilitator action |
|---|---|---|---|
| T+0:00 | 5 min | Welcome and context | Introduce yourself; explain the goal of the session in one sentence: "Today you will learn to get answers from NEM data by asking plain English questions — no SQL, no spreadsheets." Show the Genie URL on screen. |
| T+0:05 | 10 min | Connection check | Ask everyone to open the lab notebook and run the two connection-check cells. Walk the room. Anyone with a red error gets individual help — see Section 5 for common errors. |
| T+0:15 | 20 min | Part 1: Interface walkthrough | Screen-share your own Genie session. Walk through the 6 interface elements in the lab notebook (ask a question, Show SQL, download, verify, add to dashboard, share). Run the first example question live. |
| T+0:35 | 5 min | Task card briefing | Explain the task card format: scenario, question, expected output, follow-up, verify. Tell participants to work at their own pace — some will finish early, some won't finish all 6. |
| T+0:40 | 55 min | Part 2: Guided task cards | Participants work through Tasks 1–6. Circulate the room. See Section 4 for how to handle wrong Genie answers. At T+0:55 give a "halfway" reminder. At T+1:15 move everyone to Task 6 (dashboard creation) even if they haven't finished earlier tasks. |
| T+1:35 | 3 min | Part 3 intro | Briefly introduce "open question time." Show the question pattern guide on screen. Encourage participants to ask something from their actual job. |
| T+1:38 | 17 min | Part 3: Open questions | Circulate. Take note of questions that Genie cannot answer — these are data pipeline requests for the data team. |
| T+1:55 | 5 min | Part 4: Wrap-up | Cover next steps: how to request a Space for your team, how to report a wrong answer, who to contact. Remind everyone to complete the feedback form. |

**Total: 2 hours**

> **Buffer advice:** Tasks 4 (price spike duration) and 5 (settlement summary) are the most likely to overrun because Genie sometimes asks clarifying questions. If the room is running behind at T+1:10, skip Task 5 and go straight to Task 6 (dashboard creation) — it is the most visually engaging and sends people home with something tangible.

---

## 3. How to handle wrong Genie answers in front of the room

Wrong or unexpected Genie answers will happen. How you handle them determines whether participants trust the tool or not. Use this framework:

### The four-step response

1. **Name it calmly.** "That answer doesn't look right — let's check it together." Do not skip past it; participants will notice and lose confidence if you do.

2. **Click Show SQL.** Say: "The first thing we always do when something looks wrong is look at the SQL Genie wrote. This shows us exactly what it queried." Read the SQL out loud at a high level.

3. **Identify the most likely cause.** Use the table below:

| Symptom | Most likely cause | Fix |
|---|---|---|
| Returns zero rows | Date filter uses a date with no data | Ask Genie: "What is the most recent date available in [table]?" then reframe the question with that date |
| Numbers are much too large | Genie summed when it should have averaged, or missed a filter | Reframe: "What was the *average* (not total) price..." or add an explicit region filter |
| Numbers are much too small | Genie filtered to one region when the question was NEM-wide | Reframe: "...across all NEM regions combined" |
| Shows wrong column | Column name ambiguity (e.g. "dispatch" could be dispatch_mw or scheduled_mw) | Ask Genie: "Use the dispatch_mw column for actual dispatch, not scheduled_mw" |
| Genie says "I don't have access to this data" | Table is not in the Space, or the column is named differently | Note it as a data gap; move on |
| Genie asks a clarifying question | Question was genuinely ambiguous | Answer the clarifying question — this is Genie working correctly |

4. **Reframe and show success.** After you fix the question, run it again and show the correct result. End with: "That's why we always verify before sharing a number with stakeholders — and now you know exactly how to do it."

### What to say if Genie is wrong and you cannot fix it quickly

"This is a great example of something to report using the thumbs down button. Let's keep moving and I'll make a note to report this to the data team after the session."

Then note it on a sticky note or in your own Genie chat and move on. Do not spend more than 3 minutes troubleshooting a single wrong answer in front of the room.

---

## 4. How to facilitate the open question time (Part 3)

The 17 minutes of open question time is the most valuable part of the session — and the most unpredictable.

### Before you start

Display the question pattern guide from the lab notebook on the projector while participants type their own questions.

### Seeding the room

If the room is quiet for the first 30 seconds, ask a planted question yourself: "I'm going to try one from my own curiosity — let me ask: 'Which fuel type has been growing the most as a share of NEM dispatch over the last 2 years?'" This gives everyone permission to experiment.

### Circulating

- Spend no more than 2 minutes with any one person
- When you see a good result, ask the participant to share their screen with the room: "That's a great question — would you mind sharing what Genie came back with?"
- When you see someone stuck, suggest they break their question into two simpler ones

### Collecting data gaps

Keep a running list of questions that Genie could not answer. At wrap-up, read these out as "things we're going to take back to the data team." This turns gaps into action items rather than failures.

### If the room is noisy and people are engaged

That is success. Do not interrupt to give more instructions. Let them explore.

### If the room is quiet and people seem stuck

Walk to one table and say: "What does your team check every morning before the stand-up?" That question almost always generates a useful Genie question.

---

## 5. Common technical issues and fixes

### Participant cannot log in

**Symptom:** "I can't log in" or "Access denied"
**Cause:** Participant email not added to the workspace
**Fix:** Ask them to give you their email. Contact the workspace admin (number on your phone). While waiting, they can pair with the person sitting next to them and work on one screen.

### Cluster takes too long to start

**Symptom:** Spinning wheel in the notebook, "Starting cluster" message
**Cause:** Cluster was not pre-started
**Fix:** Navigate to Compute → click the cluster → Start. This takes 3–5 minutes. Tell participants to read Part 1 of the lab notebook (markdown only) while the cluster starts. The connection-check cells can be run after the cluster is ready — they are not needed for Genie.

### Genie Space does not appear in the sidebar

**Symptom:** Participant sees Genie in the sidebar but "AEMO NEM Operations" is not listed
**Cause:** Participant does not have the "Can Use" permission on the Space
**Fix:** In the workspace admin panel, add the participant to the Genie Space permissions. If you cannot do this during the session, share the direct URL (from the setup notebook Step 7) — anyone with the link and workspace access can open it.

### Genie returns "I don't have enough information to answer this"

**Symptom:** Genie refuses to answer a question from the guided tasks
**Cause:** Usually the question uses a column name or region name that is not in the instruction text
**Workaround:** Ask the participant to add a hint: e.g. "in the spot_prices table" or "using the rrp column". Golden queries handle this automatically, but free-text questions may not.

### Genie is slow (more than 20 seconds to respond)

**Symptom:** The Genie chat spinner runs for more than 20 seconds
**Cause 1:** SQL Warehouse is cold-starting (first query after idle)
**Fix:** The first query after a cold start takes 15–30 seconds. Tell participants: "The first question is always a little slow — this is the warehouse waking up. After this it will be much faster."
**Cause 2:** Warehouse is at capacity (all 30 participants querying simultaneously)
**Fix:** If the warehouse was set to 1 cluster, upgrade it to 2 clusters in SQL → SQL Warehouses → Edit → Max clusters → 2. This takes 2 minutes.
**Cause 3:** A complex query (Hard-rated) is running
**Fix:** Tell the participant: "That's a complex question — give it up to 30 seconds. If it's still running, try breaking it into two simpler questions."

### Dashboard creation fails (Task 6)

**Symptom:** "Add to dashboard" button is greyed out or returns an error
**Cause:** Participant does not have "Can Edit" permission on dashboards
**Fix:** Check that the participant's role is "User" or above (not "Guest") in workspace settings. Guest users cannot create dashboards. As a workaround, have the participant screenshot the Genie answer instead.

### "Show SQL" shows a query that references the wrong table

**Symptom:** SQL references a different schema or catalog (e.g. `samples.nyctaxi` instead of `aemo.spot_prices`)
**Cause:** Genie hallucinated a table reference, usually because the question used generic terms not in the instruction text
**Fix:** Tell the participant to be more specific: "Add 'from the NEM spot prices data' to your question." The instruction text will steer Genie to the correct table.

---

## 6. What to do if Genie is slow for the whole session

If the warehouse is consistently slow (every response takes > 30 seconds), and upgrading to 2 clusters does not help:

1. Move to a demo-mode facilitation style: you ask the questions, share your screen, and participants follow along rather than typing themselves
2. Pair participants at each table so only 10–15 sessions are running simultaneously instead of 30
3. Focus on the question card library (`activities/question_card_library.md`) as a discussion exercise: participants discuss what they expect Genie to return, then you run the question once to show the result

The learning objectives are still met — participants understand what questions Genie can answer and how to ask them — even if they do not have hands-on time on every task.

---

## 7. Post-session actions

Complete these within 24 hours of the session:

| Action | Owner | Notes |
|---|---|---|
| Send feedback form to all participants | Facilitator | Use the workshop attendee list |
| Compile list of unanswered questions | Facilitator | From your notes during Part 3 open question time |
| File data gap requests | Facilitator + Data Team | For each question Genie couldn't answer |
| Report wrong answers via thumbs-down | Facilitator | Any questions where Genie was demonstrably wrong |
| Share the Genie Space URL in the team channel | Facilitator | So participants can access it independently |
| Follow up with participants who had access issues | Facilitator + IT | Ensure they can log in before their next use |
| Send session recording (if recorded) | Facilitator | Via the participant Slack/Teams channel |

---

## 8. Session objectives and success criteria

After this session, participants should be able to:

- Navigate to the AEMO NEM Operations Genie Space independently
- Ask an operational question in plain English and get a data-backed answer
- Use "Show SQL" to verify that an answer is correct before sharing it
- Download results as a CSV
- Create a simple dashboard from a Genie answer
- Know who to contact when data is missing or an answer is wrong

**Success criteria for the facilitator:**
- At least 25 of 30 participants complete Tasks 1–3 successfully
- At least 20 of 30 participants complete Task 6 (dashboard creation)
- Zero participants leave with an unresolved login issue
- At least 5 "own questions" are asked during Part 3 open question time
