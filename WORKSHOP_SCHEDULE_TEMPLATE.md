# Workshop Schedule Template

**Databricks AU AI Workshops — Australian Regulated Industries**  
Version 1.0 | Facilitator Reference

Use this template as a starting point. Adjust times based on group experience level, Q&A engagement, and whether the environment setup experienced any delays.

---

## Pre-Day Prerequisites (Must Be Completed Before Day 1)

The following must be confirmed at least **3 business days before the first workshop day**. If any item is unresolved the morning of the workshop, notify attendees and adjust to a demo-only format for affected labs.

### Workspace Setup

- [ ] Workshop Databricks workspace provisioned in **Australia East** (mandatory for data residency requirements discussed throughout)
- [ ] Unity Catalog enabled on the workspace
- [ ] `setup/00_workspace_setup.py` executed successfully by a workspace admin — verify by checking that the `workshop_au` catalog and sample tables exist
- [ ] Notebook Assistant (Genie Code) enabled in Workspace Settings → AI features
- [ ] `Workshop — Energy Analytics` Genie Space created and sample NEM12 data connected
- [ ] AI Gateway endpoint (`workshop-pt-endpoint`) configured pointing to a Provisioned Throughput FMAPI endpoint in Australia East
- [ ] Sample data loaded — confirm row counts in `workshop_au.default.nem12_interval_reads` and `workshop_au.default.nmi_registry`

### Participant Access

- [ ] All Workshop 1 participants have **Workspace Admin** role, or have an admin buddy they can pair with for settings labs
- [ ] All Workshop 2a participants have **Data Engineer** role + SELECT on `workshop_au.*`
- [ ] All Workshop 2b participants have at minimum **Viewer** role + `CAN_USE` on the `Workshop — Energy Analytics` Genie Space
- [ ] Each participant has logged into the workspace successfully from the venue network before day 1

### Venue and Environment

- [ ] Stable internet connection — test that `<workspace-url>.azuredatabricks.net` is accessible from the venue network (not blocked by proxy or firewall)
- [ ] Projection or screen share visible to all participants
- [ ] Whiteboard or flip chart available for architecture discussions
- [ ] Facilitator laptop has the workspace open and cluster attached before the room opens
- [ ] Cluster pre-started 20 minutes before the first lab (clusters can take 4–5 minutes to spin up — do not wait until participants are in the lab to start it)

---

## Option A: Half-Day (4 Hours) — Admin Track Only

**Audience:** Workspace admins, security architects, platform engineers, cloud infrastructure leads  
**Workshop:** Workshop 1 — Governing Databricks AI Features in Australian Regulated Industries  
**Room opens:** 8:15 AM (participants arrive, facilitator assists stragglers with workspace login)  
**Start:** 8:30 AM  

| Time | Duration | Session | Notes |
|---|---|---|---|
| 8:30 AM | 30 min | Welcome, context-setting, and environment check | Introduce the regulatory framing (APRA CPS 234/230, SOCI Act, Privacy Act). Confirm all participants can access the workspace. Start cluster now if not already running. |
| 9:00 AM | 45 min | **Lab 01** — Workspace AI Settings & Access Control | Inspect AI feature flags, verify geography enforcement setting, configure UC grants for AI assets, create a service principal. Hardest lab logistically — allocate extra time for participants without full admin rights. |
| 9:45 AM | 15 min | Break | Keep to 15 minutes. Use this time to start the cluster for Lab 02 if it recycled. |
| 10:00 AM | 45 min | **Lab 02** — AI Gateway Setup | Configure AI Gateway endpoint, routing rules, rate limits, guardrails. Demo the block on cross-geo Pay-Per-Token models. |
| 10:45 AM | 40 min | **Lab 03** — Audit Logging for AI Actions | Query `system.access.audit` for AI events. Build the audit view. Export pattern for SIEM integration. |
| 11:25 AM | 35 min | **Lab 04** — Unity Catalog Governance for AI Assets | Full permission chain from table to Genie Space. Governed tags on AI assets. Lineage through AI pipelines. |
| 12:00 PM | 30 min | Debrief, Q&A, and next steps | Review what was built. Distribute the controls checklist. Discuss how participants adapt this for their own workspace. Collect feedback forms before participants leave. |
| 12:30 PM | — | Close | |

**Facilitator notes for Option A:**
- Lab 01 commonly runs 5–10 minutes long for groups with mixed admin experience. If you hit 9:55 AM and Lab 01 is not finished, checkpoint and move on — participants can complete the remainder async.
- The break at 9:45 AM is a hard stop. Do not let Lab 01 run into the break — cognitive load in this workshop is front-loaded.
- If the group is advanced (e.g., experienced Databricks admins), you can compress Lab 04 to 25 minutes and extend the debrief.

---

## Option B: Full Day (7 Hours) — Admin Track + One End-User Workshop

**Audience (Day 1 morning):** Workshop 1 audience — admins and security architects  
**Audience (Day 1 afternoon):** Workshop 2a OR Workshop 2b audience — choose based on your attendee split  
**Workshop 2a** suits data engineers and ML engineers  
**Workshop 2b** suits business analysts and operational managers

**Note on audience mixing:** Workshop 1 and Workshop 2x audiences often differ. If running both in the same room, expect some attendees to be present for both tracks and others only for one half. Design the seating and logistics accordingly. Participants who are not attending Workshop 1 should be scheduled to arrive for the 1:00 PM start.

| Time | Duration | Session | Track | Notes |
|---|---|---|---|---|
| 8:15 AM | — | Room opens | Admin | Facilitator and admin participants arrive. Verify environment. |
| 8:30 AM | 30 min | Welcome and context | Admin | Same as Option A opening. |
| 9:00 AM | 45 min | **Lab 01** — Workspace AI Settings & Access Control | Admin | See Option A notes. |
| 9:45 AM | 15 min | Break | — | |
| 10:00 AM | 45 min | **Lab 02** — AI Gateway Setup | Admin | |
| 10:45 AM | 40 min | **Lab 03** — Audit Logging for AI Actions | Admin | |
| 11:25 AM | 35 min | **Lab 04** — Unity Catalog Governance for AI Assets | Admin | |
| 12:00 PM | 30 min | Workshop 1 Debrief and Q&A | Admin | Collect feedback. Admin attendees not staying for the afternoon may leave. |
| 12:30 PM | 60 min | Lunch | — | Use this time to verify the Genie Space and Lab 2x environment are ready. Do a quick run-through of the first lab cell. |
| 1:30 PM | 15 min | Afternoon welcome and environment check | 2a or 2b | Fresh audience introduction. Confirm Genie Space access or notebook access for all. |

**Afternoon — Workshop 2a (Data Engineers):**

| Time | Duration | Session | Notes |
|---|---|---|---|
| 1:45 PM | 45 min | **Lab 01** — Genie Code Fundamentals | Generate, Fix, Explain, Optimise, Document. Uses NEM12 data. |
| 2:30 PM | 45 min | **Lab 02** — Notebook Assistant & Chat Panel | Multi-turn chat, cross-cell queries, regulatory audit trail extension. |
| 3:15 PM | 15 min | Break | |
| 3:30 PM | 30 min | **Lab 03** — Autocomplete Patterns & Productivity Tips | Keyboard shortcuts and prompt pattern practice. |
| 4:00 PM | 30 min | Debrief, Q&A, next steps | Prompt cheat sheet distribution. Discuss production environment considerations. Collect feedback. |
| 4:30 PM | — | Close | |

**Afternoon — Workshop 2b (Business Analysts):**

| Time | Duration | Session | Notes |
|---|---|---|---|
| 1:45 PM | 35 min | **Lab 01** — Genie Spaces Fundamentals | First questions, reviewing SQL, iterative refinement. |
| 2:20 PM | 30 min | **Lab 02** — Curating Data for Genie | Column descriptions, certified badge, bridging business user and data team. Facilitator-led for non-technical groups. |
| 2:50 PM | 25 min | **Lab 03** — Genie Quality and Trust | Decision framework: when to trust, when to verify, when to escalate. |
| 3:15 PM | 15 min | Break | |
| 3:30 PM | 25 min | **Lab 04** — AI Functions in a Regulated Context | `ai_classify()`, `ai_extract()`, `ai_query()` with PT endpoint. Explicit residency discussion before starting. |
| 3:55 PM | 35 min | Debrief, Q&A, next steps | What makes data Genie-ready? How to bring this back to their team. Collect feedback. |
| 4:30 PM | — | Close | |

**Facilitator notes for Option B:**
- Lunch is a hard boundary. The afternoon audience arrives at 1:30 PM — if the morning overruns into lunch, you lose setup time. Enforce the 12:00 PM debrief start.
- For Workshop 2b: Lab 02 (Curating Data for Genie) is the lab most likely to confuse non-technical audiences. If you sense the group struggling, convert it to a facilitator-led demo rather than hands-on and use the recovered time to extend the Lab 03 trust discussion, which has higher business value for this audience.
- For Workshop 2a: Lab 03 (Autocomplete) can be shortened if Labs 01 and 02 generated strong Q&A. The productivity patterns are quick to cover as a walkthrough.

---

## Option C: Two-Day Immersive — All Three Workshops

**Audience:** Mix of admins, engineers, and business analysts  
**Structure:** Day 1 = Workshop 1 (full day + extension). Day 2 = Workshop 2a (morning) + Workshop 2b (afternoon)

### Day 1 — Admin and Governance Track

Same as Option A but with an extended afternoon for deeper content and cross-functional discussion.

| Time | Duration | Session | Notes |
|---|---|---|---|
| 8:15 AM | — | Room opens | |
| 8:30 AM | 40 min | Welcome, objectives, and regulatory landscape | Expanded opening: APRA CPS 230/234, SOCI Act, Privacy Act, NER Chapter 7. Draw the connection between each to a specific lab. |
| 9:10 AM | 50 min | **Lab 01** — Workspace AI Settings & Access Control | Extra time for mixed-experience groups. |
| 10:00 AM | 15 min | Break | |
| 10:15 AM | 50 min | **Lab 02** — AI Gateway Setup | |
| 11:05 AM | 40 min | **Lab 03** — Audit Logging for AI Actions | |
| 11:45 AM | 15 min | Morning retrospective | What have we controlled? What's still open? Set up the afternoon framing. |
| 12:00 PM | 60 min | Lunch | |
| 1:00 PM | 40 min | **Lab 04** — Unity Catalog Governance for AI Assets | |
| 1:40 PM | 60 min | Architecture workshop (facilitated whiteboard) | Participants map their own organisation's AI governance posture against what they built today. Identify the top 3 gaps they will address in the next 30 days. |
| 2:40 PM | 15 min | Break | |
| 2:55 PM | 45 min | Controls framework review and customisation | Work through the controls checklist together. Each participant adapts it for their organisational context. |
| 3:40 PM | 40 min | Day 1 debrief, Q&A, and preview of Day 2 | Cover what Day 2 audiences will experience. Admins are encouraged to stay to understand what their engineers and analysts will be using. |
| 4:20 PM | — | Day 1 close | |

**Day 1 evening prep (facilitator):**
- Verify that the Genie Space is populated and working before you leave
- Confirm Day 2 participant access has been provisioned (Data Engineer role for 2a, Viewer + CAN_USE for 2b)
- Start a test cluster run to confirm it spins up cleanly on Day 2 hardware

### Day 2 — End User Tracks (Parallel or Sequential)

For groups where engineers and business analysts attend together: run Workshop 2a and 2b in sequence, with business analysts joining at 1:30 PM. For large groups where the tracks benefit from separation: run in parallel rooms if available.

| Time | Duration | Session | Track | Notes |
|---|---|---|---|---|
| 8:15 AM | — | Room opens | 2a | |
| 8:30 AM | 20 min | Day 2 welcome and data residency recap | 2a | Quick recap of what the admin team built yesterday. Connect governance to today's tools. |
| 8:50 AM | 50 min | **Lab 01** — Genie Code Fundamentals | 2a | |
| 9:40 AM | 50 min | **Lab 02** — Notebook Assistant & Chat Panel | 2a | |
| 10:30 AM | 15 min | Break | — | |
| 10:45 AM | 35 min | **Lab 03** — Autocomplete Patterns & Productivity Tips | 2a | |
| 11:20 AM | 40 min | Debrief, Q&A, and prompt pattern sharing | 2a | Group shares the most useful prompts they discovered. Facilitator captures on whiteboard. |
| 12:00 PM | 60 min | Lunch | — | Business analyst group arrives at 1:00 PM. |
| 1:00 PM | 15 min | Workshop 2b welcome and environment check | 2b | Confirm Genie Space access for all new arrivals. |
| 1:15 PM | 35 min | **Lab 01** — Genie Spaces Fundamentals | 2b | |
| 1:50 PM | 30 min | **Lab 02** — Curating Data for Genie | 2b | Facilitator-led if audience is non-technical. |
| 2:20 PM | 25 min | **Lab 03** — Genie Quality and Trust | 2b | |
| 2:45 PM | 15 min | Break | — | |
| 3:00 PM | 30 min | **Lab 04** — AI Functions in a Regulated Context | 2b | |
| 3:30 PM | 45 min | Cross-track discussion (if both audiences are in the room) | Both | Engineers and analysts discuss the same data: how would you use Genie Code to build something the analyst team could then query in Genie Spaces? This session bridges the two audiences and is one of the highest-value sessions of the two-day format. |
| 4:15 PM | 30 min | Two-day wrap-up, commitments, and next steps | Both | Each team identifies their top action item. Collect feedback. Share follow-up resource list. |
| 4:45 PM | — | Close | | |

**Facilitator notes for Option C:**
- The Day 1 architecture workshop (1:40 PM) is the most differentiated session of the two-day format. Do not skip it to recover time — it is where the most lasting value is created.
- Day 2 cross-track discussion (3:30 PM) works best when at least 3–4 engineers and 3–4 analysts are in the room together. If one group is significantly smaller, adjust to a structured show-and-tell where each track demos their highlight moment to the other.
- For the two-day format, appoint a technical facilitator for the hands-on labs (someone who knows Databricks well) and a separate lead facilitator who manages timing and discussion sessions. Running both simultaneously is exhausting and causes the discussion sessions to suffer.

---

## Timing Adjustment Guide

| Situation | Adjustment |
|---|---|
| Environment setup issues eating into Lab 1 | Convert Lab 1 to facilitator-led demo. Participants follow along in their own workspace in the background. Move to Lab 2 on schedule. |
| Group is more advanced than expected | Trim intro content in each lab by 10 min. Use recovered time for deeper Q&A or a custom scenario from a participant's real workload. |
| Group is less experienced than expected | Drop the final lab of the track. Better to finish 3 labs well than to rush through all 4. Use the final slot for Q&A. |
| Strong Q&A in progress at a break time | Honour the break. Capture the question, tell the participant you will return to it, and continue after the break — a group that stays mentally fresh through breaks retains more. |
| Cluster not available at lab start | Use the 10-minute wait to run the architecture discussion or debrief points you were going to cover later. Never just wait in silence. |

---

*Template version 1.0 — May 2026. For questions contact the Databricks AU Solutions Architecture team.*
