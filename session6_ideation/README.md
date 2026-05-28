# Session 6: AI Ideation and Building

**Track:** Business AI Adoption
**Duration:** Half-day (3–4 hours)
**Audience:** 20–30 business participants — operations staff, analysts, team leads, and managers who will be the primary consumers of AI tools, not the builders
**Format:** Facilitated in-person workshop. No coding. Participants need a laptop and access to the pre-configured Genie Space.

---

## Purpose

Sessions 1–5 configure the platform and demonstrate capability to technical teams. Session 6 converts that platform investment into a business-owned backlog of prioritised AI use cases.

By the end of this session, participants leave with three things:

1. A shared understanding of what Genie can — and cannot — do for their specific team
2. A set of discovered and documented AI use cases grounded in their real daily work
3. A prioritised shortlist of 3 use cases to take into production, with owners and acceptance criteria assigned

This session is the bridge between "we have the technology" and "we have a plan to use it."

---

## What Participants Will Produce

The primary output is a **prioritised use case backlog** — a set of completed AI Use Case Canvas cards, scored and ranked by value and effort, with the top 3 identified as production candidates.

Each canvas card captures:
- The business question being answered
- The current manual process it replaces
- Which data tables are needed
- The value delivered (time saved, risk reduced, decisions improved)
- A testable Genie question that can be verified on the day
- A priority score and key dependencies

This backlog is a living document. After the session it is shared with the AEMO data platform team and the Databricks SA to sequence production Genie Space development.

---

## Session Structure

| Block | Duration | Activity | Facilitator role |
|-------|----------|----------|-----------------|
| Context setting | 30 min | What AI can do for AEMO — show real examples from the configured Genie Space. Set expectations: what Genie is good at, where it struggles, what requires configuration. | Presenter |
| Use case discovery | 45 min | Facilitated "jobs to be done" exercise. Teams identify their top 3 data questions that currently take too long to answer. Each question becomes a partially completed canvas card. | Active facilitator — circulate between tables, prompt with domain questions |
| Hands-on Genie exploration | 60 min | Teams take their best use case question and test it in the live Genie Space. Guided by the starter question library. Facilitator captures which questions work well and which need golden query tuning. | Circulate, troubleshoot, note what's working |
| Prioritisation and roadmap | 30 min | Score all use cases on the 2x2 value/effort matrix. Group identifies top 3 for production. Assign an owner to each. Document dependencies. | Facilitate the scoring exercise, resolve disagreements |
| Wrap-up | 15 min | Next steps — how to request a Genie Space for their team, who owns the production roadmap, feedback form. | Facilitator |

**Total: 3 hours.** With a 15-minute break after the discovery block, the session runs to 3h15m. Plan 3h30m on the calendar.

---

## What Participants Need Before They Arrive

| Requirement | Who arranges it | When |
|-------------|----------------|------|
| Databricks workspace login | IT / platform team | At least 48 hours before |
| `CAN_USE` on the AEMO Genie Space | Facilitator (part of this session's setup) | Day before |
| `SELECT` on `workshop_au.aemo.*` tables | Facilitator | Day before |
| Laptop with modern browser (Chrome or Edge recommended) | Participant | — |
| Nothing else | — | — |

Participants do not install anything. No SQL or Python knowledge is required.

---

## Facilitator Prerequisites

### 1. Genie Space must be live before the session

The `session2_genie_space/genie_config/aemo_space_config.py` notebook must have been run successfully and the Space must be responding. Test it yourself the morning of the session before participants arrive.

If you are running Session 6 as a standalone engagement (not following Sessions 1–5), run the Genie Space setup notebook at least **one day before** the session to allow time to resolve any issues with tables, warehouse auto-start, or permissions.

### 2. Verify 5 smoke test questions

Before participants arrive, open the Genie Space and ask all five questions from the smoke test list in `aemo_space_config.py`. All five must return a correct, data-bearing answer. If any fails, the hands-on block will not work and participant trust will be damaged. Reschedule rather than run a broken session.

### 3. Print or share activities

- `activities/01_use_case_canvas.md` — one per participant (print double-sided or share via email/Teams)
- `activities/02_question_starter_library.md` — one per table or shared on screen during the exploration block

### 4. Prepare the 2x2 scoring grid

During the prioritisation block, draw a 2x2 on a whiteboard or bring printed templates:

```
             HIGH VALUE
                  │
  Complex ────────┼──────── Quick win
  (Phase 2)       │         (Do first)
                  │
LOW EFFORT ───────┼───────── HIGH EFFORT
                  │
  Low priority    │         Investigate
                  │         further
             LOW VALUE
```

Participants place their canvas cards on the grid and discuss.

---

## Facilitator Requirements

| Requirement | Detail |
|-------------|--------|
| Familiarity with Genie | Facilitator must have used the Genie Space themselves before the session — not just read about it |
| AEMO domain knowledge | Working knowledge of NEM operations, settlement, and compliance terminology. See `facilitator_notes/session6_guide.md` for a terminology primer. |
| Time-keeping | This session has tight blocks. Bring a timer and call transitions confidently. The discovery block especially tends to run long. |
| Co-facilitator (recommended) | For groups of 20+, a second facilitator significantly improves the quality of canvas cards produced during discovery. The co-facilitator circulates while the lead facilitator addresses the room. |

---

## Activities

| File | When used |
|------|-----------|
| `activities/01_use_case_canvas.md` | Use case discovery block + hands-on exploration |
| `activities/02_question_starter_library.md` | Hands-on Genie exploration block |
| `facilitator_notes/session6_guide.md` | Facilitator reference throughout |

---

## Outputs and Handoffs

| Output | Owner after session | Format |
|--------|---------------------|--------|
| Completed use case canvas cards (all discovered) | Business team lead | Physical cards + photos, or digital copies |
| Top 3 prioritised use cases | Business team lead + AEMO data platform team | Backlog items in customer's tracking system |
| Genie questions that worked well | Facilitator → Databricks SA | Notes fed back into golden query library |
| Genie questions that failed or returned poor answers | Facilitator → Databricks SA | Input to Genie Space tuning before production |
| Feedback form responses | Facilitator | Shared with Databricks AU SA |

---

## Common Failure Modes

| Issue | Prevention |
|-------|-----------|
| Genie Space not ready when participants arrive | Run `aemo_space_config.py` the day before; verify 5 questions the morning of |
| Discovery block produces vague use cases ("I want a dashboard") | Use the "jobs to be done" facilitation technique from `session6_guide.md` — it forces specificity |
| Prioritisation exercise becomes political | Use the 2x2 matrix and time-box debates to 2 minutes per use case |
| Participants ask questions outside the Space's scope | Use the "outside scope" framing from `session6_guide.md` — redirect to what can be explored today |
| Top 3 use cases have no data available | The canvas requires participants to identify which tables have the data — if the data is not in the Space, note it as a dependency and include it in the roadmap |

---

## Session 6 in the Programme Context

Session 6 is designed to be run after Sessions 1–5 but can also be run as a standalone engagement when a customer already has a Genie Space deployed and wants to drive adoption with business teams.

If running standalone:
- The `session2_genie_space/genie_config/aemo_space_config.py` setup notebook must be run first
- Replace workshop sample data references with the customer's actual production table names
- Allow additional time (up to 15 min) at the start of context-setting to orient participants who have not attended the earlier sessions
