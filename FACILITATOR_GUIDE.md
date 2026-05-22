# Facilitator Guide — Databricks AI Workshops (Australian Regulated Industries)

This guide is for the person running the workshops. Participants do not need to read this document — direct them to [.github/WORKSHOP_INSTRUCTIONS.md](.github/WORKSHOP_INSTRUCTIONS.md) and the individual workshop READMEs.

---

## Contents

1. [Pre-Workshop Checklist (1 week before)](#1-pre-workshop-checklist-1-week-before)
2. [Day-of Checklist (1 hour before)](#2-day-of-checklist-1-hour-before)
3. [Workshop 1: Admin Track — Facilitation Guide](#3-workshop-1-admin-track-facilitation-guide)
4. [Workshop 2a: Genie Code Track — Facilitation Guide](#4-workshop-2a-genie-code-track-facilitation-guide)
5. [Workshop 2b: Genie Spaces Track — Facilitation Guide](#5-workshop-2b-genie-spaces-track-facilitation-guide)
6. [Common Issues and Fixes](#6-common-issues-and-fixes)
7. [Environment Requirements](#7-environment-requirements)

---

## 1. Pre-Workshop Checklist (1 week before)

Work through the following in order. Most steps have dependencies on earlier ones, so do not skip ahead.

### 1.1 Provision the workshop workspace

- [ ] Submit a request via [go/workshops-studio](https://go/workshops-studio) to obtain a Databricks Credit Program workspace. Allow **at least 1 week lead time** — provisioning can take several business days for Australian regions.
- [ ] Confirm the workspace is provisioned in **Australia East** (`australiaeast`). Check the workspace URL — it should resolve to `*.azuredatabricks.net` and the Account Console should show `Azure / Australia East`.
- [ ] Verify that the workspace subscription is the Databricks Credit Program (not a customer subscription that has cost alerts or policy restrictions).

### 1.2 Unity Catalog

- [ ] Confirm Unity Catalog is enabled on the workspace. Go to **Account Console → Workspaces → [your workspace] → Features** and verify UC is toggled on.
- [ ] Unity Catalog **must** be enabled before the day of the workshop. You cannot enable it during the session without downtime.
- [ ] Create a metastore in Australia East if one does not exist for this account. Assign it to the workshop workspace.
- [ ] Confirm you have `metastore_admin` or `account_admin` to create catalogs during setup.

### 1.3 Serverless compute

- [ ] Go to **Account Console → Workspaces → [your workspace] → Compute** and enable **Serverless** for the workspace.
- [ ] Verify that at least one serverless SQL warehouse can be created. Create a test warehouse and confirm it starts in under 2 minutes.
- [ ] If serverless is not available on the subscription (rare), fall back to a shared all-purpose cluster running DBR 14.3 LTS or later.

### 1.4 Data residency enforcement (CRITICAL)

- [ ] Log into the **Account Console** (not the workspace) as an Account Admin.
- [ ] Navigate to **Settings → Compliance & Security**.
- [ ] Locate **"Enforce data processing within workspace Geography"** and confirm it is **enabled**.
- [ ] If it is not enabled, enable it now. This setting may take up to 30 minutes to propagate.

> This is the single most important compliance control for APRA-regulated participants. If you cannot enable it (e.g., the customer's Account Admin has not approved it), Workshop 1 Lab 3 will still walk through the API call to check it — but you should communicate clearly to participants that their production workspace should have this enabled before they run any regulated workloads.

### 1.5 AI features

Enable the following features in the workspace. Most are enabled by default but verify each one:

- [ ] **Genie Spaces** — Workspace Settings → AI features → Genie Spaces: On
- [ ] **AI Playground** — Workspace Settings → AI features → AI Playground: On
- [ ] **Notebook Assistant (Genie Code)** — Workspace Settings → AI features → Notebook Assistant: On
- [ ] **Model Serving** — Enabled by default; confirm under Workspace → Serving
- [ ] **AI Gateway** — Enabled by default alongside Model Serving

### 1.6 Deploy a Provisioned Throughput endpoint

This is required for Workshop 1 Lab 2, Workshop 2a Lab 2, and Workshop 2b Lab 4. It takes 15–30 minutes to become available.

- [ ] Go to **Serving → Create serving endpoint**
- [ ] Select a Foundation Model — **AU East in-region options only**: `databricks-claude-haiku-4-5` (recommended) or `databricks-claude-sonnet-4-6`. Do NOT use `databricks-meta-llama-*` — Llama models route cross-geo for AU.
- [ ] Endpoint name: `workshop-pt-endpoint`
- [ ] Set throughput: minimum 1 token unit (sufficient for workshop volume)
- [ ] Create the endpoint and confirm status reaches **Ready** before the workshop day

> Provisioned Throughput endpoints are in-region for AU East. Do **not** use Pay-Per-Token endpoints for labs that handle simulated regulated data — the workshop narrative breaks if you do, and participants will ask about it.

### 1.7 Load sample data

- [ ] Import this repository into the workshop workspace Repos (see [.github/WORKSHOP_INSTRUCTIONS.md](.github/WORKSHOP_INSTRUCTIONS.md))
- [ ] Open `setup/00_workspace_setup.py` and run it top to bottom on a cluster or serverless environment
- [ ] The setup notebook takes approximately **15 minutes** on a fresh workspace
- [ ] Confirm the following tables exist when setup completes:
  - `workshop_au.meters.nem12_interval_reads`
  - `workshop_au.meters.nmi_registry`
  - `workshop_au.regulatory.compliance_events`
  - `workshop_au.regulatory.reference_docs`

### 1.8 Run the preflight check

- [ ] Open `setup/preflight_check.py` and run all cells
- [ ] All checks must return `[PASS]` before you proceed
- [ ] Fix any `[FAIL]` items before the workshop day — do not leave them for the morning

### 1.9 Create a Genie Space for Workshop 2b

- [ ] Go to **Genie** in the left sidebar → **Create Genie Space**
- [ ] Add the following tables to the space:
  - `workshop_au.meters.nem12_interval_reads`
  - `workshop_au.meters.nmi_registry`
  - `workshop_au.regulatory.compliance_events`
- [ ] Space name: `Workshop — Energy Analytics`
- [ ] Add a description: "Natural language analytics for NEM meter data and compliance events"
- [ ] Grant `CAN_USE` to the `account users` group (participants need this to access it)
- [ ] Test it with: *"What is the total energy consumption in kWh for each NMI last week?"*
- [ ] Confirm the query executes and returns results without error

### 1.10 Share workspace with participants

- [ ] Add all participants as workspace users with at least **Workspace User** entitlement
- [ ] For Workshop 1 participants who need admin access for labs: add them as **Workspace Admins** on the workshop workspace (not production)
- [ ] Confirm participants have `SELECT` on `workshop_au.*`
- [ ] Send participants the workspace URL and login instructions at least 24 hours before the workshop

---

## 2. Day-of Checklist (1 hour before)

Run through this list in the 60 minutes before participants arrive.

- [ ] Log into the workshop workspace and confirm your session is active
- [ ] Open `setup/preflight_check.py` and run it — all checks should still be `[PASS]`
- [ ] Verify the three key sample tables exist and are queryable:
  ```sql
  SELECT COUNT(*) FROM workshop_au.meters.nem12_interval_reads;
  -- Expected: ~6,700 rows
  ```
- [ ] Go to **Serving** and confirm the `workshop-pt-endpoint` status is **Ready** (green). If it shows "Updating" or "Not Ready", wait — do not restart it unless it has been in that state for more than 20 minutes.
- [ ] Open the Genie Space you created and ask one test question to confirm it is responsive
- [ ] Have the slide deck open in a separate tab/window and confirm you can share your screen
- [ ] Confirm the room / video call setup is working (screen share, audio, if virtual)
- [ ] Verify at least 2–3 participants have logged in early and can access the workspace — this is your smoke test
- [ ] If any participant cannot log in, the most common cause is a missing workspace user record — add them via Account Console → User Management

---

## 3. Workshop 1: Admin Track — Facilitation Guide

**Total time:** 4 hours  
**Audience:** Workspace admins, security architects, platform engineers  
**Labs:** 4 labs, each 35–55 minutes

### Timing guide

| Time | Activity |
|------|----------|
| 0:00 | Welcome and introductions (10 min) |
| 0:10 | Scene-setting: AI in regulated industries, APRA context (15 min) |
| 0:25 | **Lab 1: Workspace AI Settings & Access Control** (35–40 min) |
| 1:05 | Debrief Lab 1, Q&A (10 min) |
| 1:15 | Break (10 min) |
| 1:25 | **Lab 2: AI Gateway Setup** (40–45 min) |
| 2:10 | Debrief Lab 2, Q&A (10 min) |
| 2:20 | Break (10 min) |
| 2:30 | **Lab 3: Audit Logging for AI Actions** (35–40 min) |
| 3:10 | Debrief Lab 3, Q&A (10 min) |
| 3:20 | **Lab 4: Unity Catalog Governance for AI Assets** (30–35 min) |
| 3:55 | Wrap-up, next steps, feedback (15 min) |
| 4:10 | End |

### Lab 1 facilitation notes

**Before participants start:** Walk through the AU East residency table in the lab header (the green/red matrix). Spend 2 minutes on it. This sets up the entire governance narrative for the day. Participants from APRA-regulated entities will have questions about Pay-Per-Token — acknowledge the concern, tell them Workshop 1 Lab 2 covers how to block it at the AI Gateway.

**Section 3 (Geography enforcement):** This is the most important section. Most participants will get a 403 Forbidden because they are not Account Admins on the workshop workspace. That is intentional — show the correct response from a machine where you have Account Admin, or show a screenshot. The point is to know *where* to check, not necessarily to change the setting live.

**Section 4 (UC GRANT SQL):** These cells are deliberately commented out. Do not uncomment them for participants unless they are on a lab-only workspace. In regulated environments, participants are accustomed to "review the pattern, don't run it in production." Reinforce that habit.

**Common questions in Lab 1:**
- *"What's the difference between a Workspace Admin and an Account Admin?"* — Account Admin governs the entire Databricks account (all workspaces, billing, UC metastores). Workspace Admin governs a single workspace. The geography enforcement setting lives at Account level.
- *"Can we use OAuth tokens instead of PATs?"* — Yes, and you should. Section 5 of the lab shows service principals with OAuth secrets. Personal Access Tokens are shown only as a workshop convenience.
- *"Does SCIM sync replace the need to manage groups here?"* — SCIM syncs users and groups from your IdP (Azure AD / Entra ID) but the Databricks GRANT statements still need to be applied. SCIM handles identity; Unity Catalog handles authorisation.

### Lab 2 facilitation notes

AI Gateway is the control plane for routing, rate limiting, and guardrailing LLM calls. The key message for regulated entities: AI Gateway lets you enforce that only the in-region Provisioned Throughput endpoint is used for any given workload — it effectively makes Pay-Per-Token unavailable to a specific group.

**Watch for:** Participants may not have CAN_MANAGE on the serving endpoint if their workspace user entitlement was set up as Workspace User only. Remind them this is a workshop — in their environment they would be admins.

### Lab 3 facilitation notes

`system.access.audit` is where every AI action (Genie query, model serving call, AI Gateway request) is logged. This section resonates strongly with APRA audiences because CPS 234 requires audit trails for all access to sensitive data and systems.

**Key moment:** Run the live audit query that shows Genie Space queries in the audit log. If the Genie Space was tested in the pre-workshop checklist, those queries will appear. This is a powerful demo — participants can see their own test query in the log.

**Common question:** *"How long is audit data retained?"* — System tables retain data for 365 days by default. You can export to external storage via Delta Sharing for longer retention.

### Lab 4 facilitation notes

Unity Catalog governance for AI assets follows the same pattern as data governance — catalogs, schemas, grants. The novelty is the asset types: registered models, serving endpoints, AI Gateway routes, Genie Spaces.

**Pause for discussion:** After the GRANT examples, ask the room: "In your current environment, who approves access to a new AI model endpoint? Is that a manual process or automated?" This surfaced well in APRA-regulated workshop runs — most teams have no defined process yet, which creates a compelling reason to build one using UC.

---

## 4. Workshop 2a: Genie Code Track — Facilitation Guide

**Total time:** 3 hours  
**Audience:** Data engineers, ML engineers, analytics engineers  
**Labs:** 3 labs, each 40–55 minutes

### Timing guide

| Time | Activity |
|------|----------|
| 0:00 | Welcome and setup verification (10 min) |
| 0:10 | What is Genie Code, residency explainer (10 min) |
| 0:20 | **Lab 1: Genie Code Fundamentals** (45 min) |
| 1:05 | Debrief, Q&A (10 min) |
| 1:15 | Break (10 min) |
| 1:25 | **Lab 2: Notebook Assistant & Chat Panel** (45 min) |
| 2:10 | Debrief, Q&A (10 min) |
| 2:20 | **Lab 3: Autocomplete Patterns & Productivity Tips** (30 min) |
| 2:50 | Wrap-up, what to try next week (10 min) |
| 3:00 | End |

### Lab 1 facilitation notes

Lab 1 is structured around NEM12 interval meter data — the same data participants would encounter working with AEMO, APA, or an electricity retailer. Reinforce the domain framing early: "This is real Australian energy data structure."

**Section 2 (Code generation):** The "TODO: Use Genie Code to write this cell" pattern is intentional. Do not pre-fill these cells. The learning objective is prompting practice. Give participants 5 minutes of silence to work before sharing answers — most will not have used Genie Code seriously before and need time to discover the interaction model.

**Section 4 (Debugging):** The intentional bugs in Exercise 4.1–4.3 are:
1. `quality_flg` (wrong column name) — Genie Code Fix is very reliable here
2. Logic inversion (`< 0.05` instead of `> 0.05`) — Genie Code Fix may or may not catch this; the teaching point is to always review suggested fixes
3. `"dleta"` format typo — Genie Code Fix catches this reliably

**Key demo moment:** After Section 4.2, show the chat panel and ask Genie Code to explain *why* the logic was wrong. The multi-turn nature of the chat panel is often the "aha" moment for engineers who are used to one-shot code completion tools.

**Common participant issues:**
- *"The Generate cell doesn't appear when I press G"* — They may be in Edit mode. Press Escape first to enter Command mode, then press G.
- *"Genie Code suggested code that uses a column that doesn't exist"* — This is expected and important. Reinforce: always provide explicit column names in prompts. If schema context is wrong, add it explicitly: "The columns are: nmi, interval_date, interval_number, read_kwh, quality_flag, meter_serial, region."
- *"The cluster is still starting"* — If using serverless, it should attach in under 30 seconds. If using a shared cluster, ensure participants are all attaching to the same cluster rather than each starting a new one.

### Lab 2 facilitation notes

Lab 2 focuses on the chat panel for multi-turn, context-rich conversations with the notebook assistant. The key pattern is: drag a cell into chat, provide context, ask follow-up questions.

**Key moment:** The exercise where participants ask Genie Code to review a full notebook section for potential issues is highly effective for engineers. It mirrors a code review workflow they already know.

### Lab 3 facilitation notes

Lab 3 covers autocomplete and inline suggestions. This is the "install muscle memory" lab — there is less explanation and more typing.

**Tip:** Pair participants up for this lab and have them peer-review each other's prompts. The social comparison ("your prompt got better results than mine — what did you include?") accelerates learning.

---

## 5. Workshop 2b: Genie Spaces Track — Facilitation Guide

**Total time:** 3 hours  
**Audience:** Business analysts, data analysts, reporting leads  
**Labs:** 4 labs, each 20–40 minutes

### Timing guide

| Time | Activity |
|------|----------|
| 0:00 | Welcome, what is Genie Spaces (15 min) |
| 0:15 | **Lab 1: Genie Spaces Fundamentals** (35 min) |
| 0:50 | Debrief, Q&A (10 min) |
| 1:00 | Break (10 min) |
| 1:10 | **Lab 2: Curating Data for Genie** (30 min) |
| 1:40 | Debrief (10 min) |
| 1:50 | **Lab 3: Genie Quality and Trust** (25 min) |
| 2:15 | Debrief (10 min) |
| 2:25 | **Lab 4: AI Functions in a Regulated Context** (25 min) |
| 2:50 | Wrap-up, feedback (10 min) |
| 3:00 | End |

### Lab 1 facilitation notes

Lab 1 is the "wow" lab. The goal is to get participants asking natural language questions against real (simulated) energy data and seeing correct SQL returned within the first 10 minutes.

**Good starter questions to suggest:**
- "Show total daily energy consumption per NMI for last week"
- "Which NMI had the highest consumption on a single day?"
- "How many intervals had an Estimated quality flag this month?"

**What to watch for:** Some participants will ask questions the space cannot answer because the data is not there (e.g., pricing data, customer names). Use these moments to explain how Genie Spaces are scoped to their data: it is a feature, not a bug. In a regulated environment, you *want* Genie to only access the data you have explicitly added.

### Lab 2 facilitation notes

Lab 2 covers the data curation patterns that make Genie Spaces work well: column comments, table-level descriptions, and the certified table badge in Unity Catalog.

**Key insight to reinforce:** Genie Spaces use your Unity Catalog metadata (column descriptions, table descriptions, certified tags) as context for query generation. The better your metadata, the better Genie's answers. This directly connects to the data governance work covered in Workshop 1.

**Common question:** *"Do I need to add all my tables to get good results?"* — No. Start with a focused set of well-described tables. Fewer tables with better metadata outperforms many tables with no metadata.

### Lab 3 facilitation notes

Lab 3 covers how to interpret Genie's confidence indicators and when to verify a result.

**Key pattern to teach:** The "Check SQL" workflow — when Genie gives an answer, always check the underlying SQL it generated. Click "View SQL" on any Genie response. For regulated reporting, this SQL should be reviewed by a data analyst before the output is used in a regulatory submission.

**Discussion question to pose:** "In your team, who owns verifying that an AI-generated SQL query is correct before the output goes into a report? Is that a defined role?" This question consistently lands well with governance-minded participants and generates good discussion about process.

### Lab 4 facilitation notes (THE CROSS-GEO GOTCHA)

Lab 4 covers `ai_query()` and related AI SQL functions. **This lab contains the most important residency gotcha in the entire workshop series. Explain it clearly before participants start.**

**What to say before participants start Lab 4:**

> "Before you run any cells in this lab, I need to flag something important. The `ai_query()` function in Databricks SQL calls a Foundation Model API endpoint. Which endpoint it calls depends entirely on how you configure it. If you call `ai_query('databricks-claude-sonnet-4-5', ...)` with no endpoint configuration, it will use the Pay-Per-Token external endpoint, which processes data **outside Australia East**. In a regulated environment, that is a compliance violation.
>
> In this lab, we are going to show you the safe pattern: always specify your Provisioned Throughput endpoint explicitly, like this: `ai_query('workshop-pt-endpoint', ...)`. Your IT team or platform admin should configure AI Gateway to make the PT endpoint the default, and block unapproved endpoints. We walked through that in Workshop 1, Lab 2.
>
> For the purposes of this workshop, we are only using our in-region PT endpoint. Do not change the endpoint name in the lab notebooks."

**This message cannot be delivered as a note in the lab notebook alone — say it verbally before the lab starts.**

**Common Genie quality issues and how to diagnose them:**

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Genie returns "I don't know" | The question refers to data not in the space | Add the relevant table, or rephrase the question |
| Genie returns a SQL error | Column name in question doesn't match the actual column name | Add a column comment to the UC table explaining the column name |
| Genie returns plausible but wrong numbers | The question was ambiguous (e.g., "last week" without a date context) | Add an instruction to the Genie Space: "When the user says 'last week', use the 7 days prior to today" |
| Genie hallucinating table names | The space has too many tables with similar names | Remove ambiguous tables; ensure table descriptions are distinct |
| Slow responses | The serving endpoint is under load or the SQL warehouse is cold | Check endpoint status; pre-warm the SQL warehouse |

---

## 6. Common Issues and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Participant cannot log into workspace | User not added to workspace | Add via Account Console → User Management → Add to workspace |
| Workspace shows "Unity Catalog not enabled" | UC was not enabled at workspace creation | Enable via Account Console → Workspaces → [workspace] → Features → Unity Catalog. Restart workspace. |
| `workshop_au` catalog not found | Setup notebook not yet run, or ran with errors | Run `setup/00_workspace_setup.py` again; check for error cells |
| Preflight check shows `[FAIL] Geography enforcement` | "Enforce data processing within Geography" not enabled | Enable in Account Console → Settings → Compliance & Security. Takes up to 30 min to propagate. |
| PT endpoint stuck in "Updating" | Cold start or resource contention | Wait up to 30 minutes. If still not Ready, delete and recreate. Provision at least 15 min before workshop start. |
| Genie Code (Notebook Assistant) not appearing | Feature disabled at workspace level | Workspace Settings → AI features → Notebook Assistant: On |
| Genie Spaces not in left sidebar | Feature disabled, or user does not have access | Workspace Settings → AI features → Genie Spaces: On; also check workspace user entitlement includes AI features |
| `G` key not triggering Generate in notebook | User is in Edit mode | Press Escape to enter Command mode, then G |
| `ai_query()` returns a permissions error | The service principal or user lacks permission to call the endpoint | GRANT CAN_QUERY ON SERVING ENDPOINT `workshop-pt-endpoint` TO `account users` |
| Genie Space query returns wrong SQL | Table or column names ambiguous | Add descriptive comments to Unity Catalog table and column metadata |
| Secret scope `admin-workshop` not found | Lab 1 setup cell requires a pre-created secret scope | Create the scope: `databricks secrets create-scope --scope admin-workshop` |
| SCIM / group sync not reflecting in workspace | SCIM provisioning delay (up to 15 min) | Wait, or manually add the user directly in the workspace UI |
| Serverless SQL warehouse not available | Serverless not enabled on account/workspace | Enable via Account Console → Workspaces → Compute → Serverless |
| `403 Forbidden` on Account API calls | Workshop participant is not an Account Admin | Expected for most participants; show correct response from facilitator machine |
| Import repo fails in Databricks Repos | GitHub URL requires authentication | Use HTTPS with a GitHub PAT, or ensure the repo is public |
| Cluster attach fails with "cluster not found" | Shared cluster was terminated between sessions | Restart the shared cluster; or switch to serverless |
| `databricks-sdk` import error | Old DBR version | Use DBR 13.3 LTS or later; `databricks-sdk` is pre-installed from DBR 13+ |

---

## 7. Environment Requirements

### Participants

Participants need only a modern web browser. No local software installation is required.

| Requirement | Detail |
|-------------|--------|
| Browser | Google Chrome 110+ or Microsoft Edge 110+ (recommended). Firefox supported but some notebook keyboard shortcuts differ. Safari not recommended. |
| Network | HTTPS (port 443) outbound access to `*.azuredatabricks.net` and `*.blob.core.windows.net` |
| Screen resolution | 1280×800 minimum; 1920×1080 recommended for the notebook + chat panel side-by-side layout |
| No local install needed | All compute, storage, and AI processing runs in the Databricks workspace |

### Workspace (facilitator-provisioned)

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Databricks Runtime | DBR 14.3 LTS | DBR 15.4 LTS |
| Cluster type | Standard (single-user or shared) | Serverless |
| UC metastore | Required | Required |
| Unity Catalog | Enabled | Enabled |
| Serverless compute | Enabled | Enabled |
| AI features | Genie Spaces, AI Playground, Notebook Assistant all On | All AI features On |
| Provisioned Throughput | 1 endpoint, 1 token unit | 1 endpoint, 2 token units for > 20 participants |
| Storage | Azure Data Lake Storage Gen2 (auto-provisioned with workspace) | — |

### Network (corporate/office delivery)

If running the workshop in a corporate office environment (common for APRA-regulated entities), confirm the following with the customer's network team at least 3 days before:

| Traffic | Destination | Port |
|---------|-------------|------|
| Databricks workspace UI | `*.azuredatabricks.net` | 443 |
| Azure Blob / ADLS Gen2 (data plane) | `*.blob.core.windows.net`, `*.dfs.core.windows.net` | 443 |
| Unity Catalog metastore | Embedded in workspace, no additional rule needed | — |
| Genie Spaces | Served from workspace, in-region | — |

**Common corporate network blocker:** Some organisations proxy all HTTPS traffic through a Zscaler or Cisco Umbrella gateway. This can break WebSocket connections used by the Databricks notebook editor. If participants see a spinning loader when opening a notebook, ask the network team to whitelist `*.azuredatabricks.net` for WebSocket (Upgrade: websocket) traffic.

### Virtual delivery

For virtual workshops, all the above applies. Additionally:

- Use Zoom or Teams screen sharing with participants following along in their own browser tabs simultaneously
- Recommend participants have two screens (one for the video call, one for Databricks) or two browser windows side by side
- Increase lab time estimates by 10–15% — virtual participants take longer to navigate without in-person guidance
- Use the video call chat window for participants to post error messages — faster than verbal descriptions
