# Workshop Instructions — Getting Started

Welcome to the Databricks AI Workshops for Australian Regulated Industries. This guide walks you through importing the workshop repository into your Databricks workspace and starting the labs.

You do not need to install anything on your laptop. Everything runs in the browser.

---

## Contents

1. [Step 1 — Log into the workshop workspace](#step-1--log-into-the-workshop-workspace)
2. [Step 2 — Import the repository via Databricks Repos](#step-2--import-the-repository-via-databricks-repos)
3. [Step 3 — Navigate to your workshop folder](#step-3--navigate-to-your-workshop-folder)
4. [Step 4 — Start a cluster or connect to serverless](#step-4--start-a-cluster-or-connect-to-serverless)
5. [Step 5 — Run your first lab](#step-5--run-your-first-lab)
6. [Common Errors and Fixes](#common-errors-and-fixes)

---

## Step 1 — Log into the workshop workspace

Your facilitator will have sent you a workspace URL and login instructions before the workshop. The URL looks like:

```
https://adb-XXXXXXXXXXXXXXXX.X.azuredatabricks.net
```

1. Open the URL in Google Chrome or Microsoft Edge (recommended)
2. Log in with the credentials your facilitator provided, or with your corporate SSO if the workspace uses it
3. You should land on the Databricks home page showing the left-hand navigation bar

**If you cannot log in:**
- Check that you are using the correct workspace URL — do not use your regular production workspace
- If you are prompted for MFA and do not have access to your authenticator app, contact your facilitator
- If you see "You do not have permission to access this workspace", your facilitator needs to add your account — this takes under 2 minutes

---

## Step 2 — Import the repository via Databricks Repos

Databricks Repos lets you work with Git repositories directly inside the platform. You will clone this workshop repository so you have your own copy of all the lab notebooks.

### 2a — Open the Repos section

In the left navigation bar, click on **Repos** (it looks like a branching icon, or you may see it labelled "Workspace" depending on your UI version — look for the Git/Repos option).

Alternatively, use the search shortcut: press **Ctrl+K** (or **Cmd+K** on Mac) and type "Repos".

### 2b — Add the repository

1. Click **Add repo** (top right of the Repos page, or look for an **Add** button)
2. In the dialog that appears:
   - **Git repository URL:** Enter the GitHub URL your facilitator provided (or the public URL of this repository)
   - **Git provider:** Select **GitHub**
   - **Repository name:** Leave as the default (it will auto-populate from the URL)
3. Click **Create repo**

Databricks will clone the repository. This takes 5–15 seconds depending on the repository size.

### 2c — Confirm the import succeeded

You should now see the `databricks-au-ai-workshops` folder in your Repos view. Click on it to expand it and confirm you can see the following folders:

```
databricks-au-ai-workshops/
├── data/
├── setup/
├── session1_platform_admin/
├── session2_genie_space/
├── session4_mcp_agents/
├── session5_genie_code/
├── session6_ideation/
└── .github/
```

If the folder is empty or you see only a `.git` folder, the clone may have failed. Try the import again, or ask your facilitator.

**If you see an authentication error:**
The repository may require authentication. Ask your facilitator whether you need a GitHub Personal Access Token (PAT). If yes, your facilitator will provide one for the workshop duration. Enter it in the Git credentials dialog that appears after the authentication error.

---

## Step 3 — Navigate to your workshop folder

Navigate to the folder for your session:

| Session | Folder to open |
|---------|---------------|
| Session 1 (Platform Admin) | `session1_platform_admin/labs/` |
| Session 2 (Genie Space) | `session2_genie_space/labs/` |
| Session 4 (MCP Agents) | `session4_mcp_agents/labs/` |
| Session 5 (Genie Code) | `session5_genie_code/labs/` |

Start with the first file in numerical order, e.g. `01_workspace_ai_settings.py` for Session 1.

Do not run notebooks out of order — later labs sometimes depend on objects created in earlier ones.

---

## Step 4 — Start a cluster or connect to serverless

Each lab notebook needs compute to run. Your facilitator will tell you which option to use:

### Option A — Serverless (recommended when available)

Serverless compute is the fastest option and requires no cluster management. When you open a notebook, look for the **Connect** button in the top right of the notebook editor. Click it and select **Serverless** from the dropdown.

The first attachment takes 10–20 seconds. Subsequent cells run immediately.

### Option B — Shared cluster

Your facilitator may have provisioned a shared all-purpose cluster for the workshop. To connect:

1. Click **Connect** in the top right of the notebook editor
2. Select the shared cluster (it will be named something like `workshop-cluster`)
3. If the cluster shows as **Terminated**, click the play button next to it to start it — this takes 2–5 minutes
4. Wait for the status to show **Running**, then run your first cell

**Important:** All participants should attach to the **same** shared cluster, not start individual clusters. Starting a new cluster for each participant wastes time and resources.

---

## Step 5 — Run your first lab

### Opening a lab notebook

In Repos, navigate to your lab folder and click on a `.py` file (e.g., `01_workspace_ai_settings.py`). The file opens as a Databricks notebook.

The `.py` extension is a Databricks convention for Python notebook source files. The file looks like a Python file in GitHub but opens as a full interactive notebook in Databricks.

### Running cells

Run cells one at a time by:
- Clicking the **Run cell** button (triangle icon) on the left of the cell, or
- Pressing **Shift+Enter** (runs the current cell and moves to the next), or
- Pressing **Ctrl+Enter** (runs the current cell and stays on it)

Run cells **in order from top to bottom**. Do not skip setup cells — they often create tables or variables that later cells depend on.

### TODO cells

Many lab cells contain `# TODO:` comments indicating you need to fill in a value or uncomment a line before running. Read the comment carefully before running.

Example:
```python
# TODO: Replace with your workspace URL (no trailing slash)
WORKSPACE_URL = "https://<your-workspace>.azuredatabricks.net"
```

Replace `"https://<your-workspace>.azuredatabricks.net"` with the actual workspace URL shown in your browser address bar.

### Markdown cells

Cells that start with `# MAGIC %md` render as formatted text in the notebook. These are instructions, explanations, and reference tables. Read them before running the corresponding code cells.

---

## Common Errors and Fixes

### "Cannot find table workshop_au.meters.nem12_interval_reads"

**Cause:** The workspace setup notebook has not been run, or it ran with errors.

**Fix:** Ask your facilitator. The setup notebook (`setup/00_workspace_setup.py`) must be run before any lab notebooks. The facilitator runs this during pre-workshop preparation — it is not something participants need to run.

---

### "DATABRICKS_TOKEN environment variable not set" or "Authentication failed"

**Cause:** A lab cell is trying to use a token that has not been configured.

**Fix:** In Lab 1 specifically, Section 0 asks you to either set `WORKSPACE_URL` manually or retrieve a token from a secret scope. Follow the instructions in the `# TODO` comment in that cell. Your facilitator will tell you the secret scope name (it is `admin-workshop` for workshop environments).

---

### "Cluster not found" or "Cluster is terminated"

**Cause:** The shared cluster was terminated, or you are connected to a cluster you do not have access to.

**Fix:** Click the **Connect** button in the notebook header, then select either the shared workshop cluster (ask your facilitator for its name) or **Serverless** if it is available.

---

### The notebook editor shows "Loading..." and never loads

**Cause:** Usually a WebSocket connection issue — common on corporate networks with strict proxy settings.

**Fix:**
1. Try a hard refresh: **Ctrl+Shift+R** (Windows/Linux) or **Cmd+Shift+R** (Mac)
2. If that does not work, try a different network (e.g., mobile hotspot) — your corporate proxy may be blocking WebSocket connections
3. Ask your facilitator whether the network team has whitelisted `*.azuredatabricks.net` for WebSocket traffic

---

### "AnalysisException: Table or view not found"

**Cause:** A SQL cell references a table that does not exist, or you are using the wrong catalog or schema.

**Fix:** Check that your cluster or serverless session has the default catalog set to `workshop_au`. Run:
```sql
%sql
USE CATALOG workshop_au;
USE SCHEMA meters;
```
Then re-run the failing cell.

---

### Genie Code (Notebook Assistant) is not appearing

**Symptom:** There is no AI icon in the notebook toolbar, no "Generate with AI" option when you add a cell, and pressing `G` in command mode does nothing.

**Cause:** Notebook Assistant (Genie Code) is either disabled at the workspace level or your account does not have the AI features entitlement.

**Fix:** Ask your facilitator. They need to go to Workspace Settings → AI features → Notebook Assistant and toggle it on. This change takes effect immediately — refresh your browser after your facilitator confirms the change.

---

### "The `G` key opens a search bar instead of code generation"

**Cause:** You are in Edit mode (inside a cell) rather than Command mode (cell selected but not active).

**Fix:** Press **Escape** to exit Edit mode. The cell border should change from blue/green to grey. Now press `G` — it should trigger Generate with AI.

---

### The Genie Space is not in my left sidebar

**Cause:** Either Genie Spaces is disabled at the workspace level, or you do not have `CAN_USE` permission on the space.

**Fix:** Ask your facilitator. They need to either enable Genie Spaces in Workspace Settings (takes effect on refresh) or grant you access to the specific space.

---

### "ai_query() failed: external model endpoint requires model serving to be enabled"

**Cause:** Lab 4 in Session 4 requires the Provisioned Throughput endpoint (`databricks-claude-haiku-4-5`) to be running.

**Fix:** Ask your facilitator to verify the endpoint status in Serving. If it is in "Updating" state, wait 5 minutes and retry. If it is not created, your facilitator needs to provision it — this takes 15–30 minutes.

---

### I accidentally ran all cells at once and got errors

**Cause:** The "Run all" button was clicked before completing the `# TODO` sections.

**Fix:** This is safe to recover from. Fix the `# TODO` values in the setup cells at the top of the notebook, then run the cells individually from the top again. Running a cell multiple times is generally safe — most lab cells are idempotent.

---

## Tips for Getting the Most from the Labs

- **Read the markdown cells first.** They contain the context and instructions for each section. Skipping them and running code cells directly is a common source of confusion.
- **Do not race ahead.** The labs are designed with discussion pauses built in. If you finish a section early, read the next section's markdown or experiment with the prompts.
- **Ask questions aloud.** If something is not working, describe the error message to your facilitator or a neighbour. Most errors are quick to diagnose once someone reads the exact error text.
- **The solutions folder is there.** Each workshop has a `labs/solutions/` folder with completed versions of every lab. If you are stuck and cannot move forward, you can reference the solution — but try to work through it yourself first.
