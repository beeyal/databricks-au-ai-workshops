# Workshop 2a: Genie Code for Developers — Australian Regulated Industries

**Track:** Data Engineer / ML Engineer  
**Duration:** 3 hours  
**Audience:** Data engineers, analytics engineers, ML engineers, Python/SQL developers on Databricks

---

## Overview

This workshop teaches data engineers and ML engineers to get productive with Genie Code — the AI-powered coding assistant embedded in Databricks notebooks. Every exercise uses Australian National Electricity Market (NEM) data structures, so the patterns you learn are immediately applicable to real energy, utility, and regulated-data workloads.

The workshop is hands-on from the first minute. Rather than watching demonstrations, you will use Genie Code to generate, fix, explain, optimise, and document code throughout each lab.

### What is Genie Code?

Genie Code is the AI assistant embedded directly in the Databricks notebook editor. It:
- Generates PySpark, SQL, and Python code from natural language descriptions
- Explains what unfamiliar code does (useful for inherited notebooks)
- Fixes errors automatically — including runtime errors and logic bugs
- Optimises slow transformations (e.g., replaces Python loops with native Spark operations)
- Documents functions with generated docstrings
- Provides a multi-turn chat panel for complex, context-rich conversations

Genie Code runs **in-region for Australia East** using Azure AI Services for completions. Your code and data do not leave the AU East region.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Role | Data Engineer or above on the workshop workspace |
| Access | SELECT on `workshop_au.*` (granted during setup) |
| Workspace | UC-enabled, Australia East, sample data loaded |
| DBR | 14.3 LTS or later |
| Feature | Notebook Assistant (Genie Code) enabled — verify in Workspace Settings |
| Prior knowledge | Comfortable with PySpark and SQL; no AI experience required |

If you have not yet run the workspace setup, ask your facilitator. The setup notebook (`setup/00_workspace_setup.py`) must be completed before Lab 1.

---

## What You Will Learn

By the end of this workshop, you will be able to:

1. Generate correct PySpark and SQL code from natural language prompts using domain-specific terminology
2. Write effective prompts that produce high-quality code on the first attempt
3. Use the Fix action to diagnose and resolve runtime errors and logic bugs
4. Use the Explain action to understand unfamiliar code (useful for onboarding and code review)
5. Use the Optimise action to replace inefficient patterns (Python loops over Spark data, repeated collects) with vectorised equivalents
6. Use the Document action to generate docstrings for existing functions
7. Use the multi-turn chat panel for complex, iterative problem-solving
8. Apply Genie Code patterns that respect data security (avoid sending production data to prompts)

---

## Labs

### Lab 01 — Genie Code Fundamentals

**File:** `labs/01_genie_code_intro.py`  
**Duration:** 40–45 minutes  
**Difficulty:** Beginner to Intermediate

Start with the core Genie Code workflow: generate, explain, fix, optimise, document. All exercises use the `nem12_interval_reads` NEM meter data view. You will generate aggregations, explain a demand profiling transformation, debug three intentional bugs (column name error, logic inversion, format typo), and practice the Document and Optimise actions on real energy-domain functions.

Key exercises:
- Generate: total daily consumption per NMI, peak 30-minute interval identification
- Explain: demand profile classification logic (morning peak, evening peak, shoulder, off-peak)
- Fix: `quality_flg` column name bug, `< 0.05` logic inversion, `"dleta"` format typo
- Optimise: Python loop over collected Spark rows — rewrite with native Spark filter
- Document: `calculate_load_factor()` function with NEM business logic

---

### Lab 02 — Notebook Assistant & Chat Panel

**File:** `labs/02_notebook_assistant.py`  
**Duration:** 40–45 minutes  
**Difficulty:** Intermediate

The chat panel extends Genie Code from single-cell actions to full notebook-level conversations. In this lab, you will use the chat panel to work through multi-step problems: designing a pipeline, debugging a sequence of cells, and asking domain-specific questions that require context across multiple cells. You will also learn how to drag cells into the chat for targeted questions and how to use `@cell` references.

Key exercises:
- Design a NEM12 data quality pipeline end-to-end using only chat prompts
- Debug a 4-cell pipeline where the error surfaces 3 cells after the root cause
- Ask cross-cell questions: "Why does the result in cell 7 differ from what I computed in cell 4?"
- Regulatory extension: ask Genie Code to add regulatory audit trail fields to a pipeline

---

### Lab 03 — Autocomplete Patterns & Productivity Tips

**File:** `labs/03_autocomplete_patterns.py`  
**Duration:** 30 minutes  
**Difficulty:** Beginner

Build the typing patterns that make Genie Code fast in daily work. Inline autocomplete, keyboard shortcuts, effective partial prompts, and what to do when Genie generates subtly wrong results. This lab is heavier on practice and lighter on explanation — the goal is building muscle memory.

Key exercises:
- Autocomplete a PySpark window function from a partial signature
- Use `Ctrl+Shift+P` → AI actions to navigate without the mouse
- Practice the "schema-first prompt" pattern for consistently accurate generation
- Review: five anti-patterns that produce poor Genie Code results, with correct alternatives

---

## What You Will Have Built by the End

By the end of this workshop, you will have:

- A completed NEM12 data quality analysis notebook, generated almost entirely via Genie Code prompts
- A personal cheat sheet of prompt patterns that produce reliable results for energy/utility data workloads
- Hands-on experience with every major Genie Code interaction mode (Generate, Fix, Explain, Optimise, Document, Chat)
- A set of before/after examples (slow Python → fast Spark) you can share with your team

---

## Data Residency Note

Genie Code processes your prompts and code using Azure AI Services hosted in **Australia East**. The content of your notebook cells — including code and comments — is sent to the AI service for completion.

**What this means for your work:**
- Do not include actual customer data, real NMIs, real meter readings, or PII in prompts or cells you send to Genie Code
- The workshop sample dataset is synthetic — it is safe to use in all exercises
- In your production environment, avoid putting production data values into notebook cells that will be processed by Genie Code; use parameterised queries instead

The underlying model does not retain your code between sessions. Refer to your organisation's Databricks Data Processing Agreement for the full data handling terms.

---

## Keyboard Shortcuts Reference

| Shortcut | Action |
|----------|--------|
| `G` (command mode) | Open Generate with AI on the current cell |
| `Escape` | Switch from Edit mode to Command mode |
| `Ctrl+Shift+P` | Command palette (search all AI actions) |
| `Alt+Enter` | Run cell and insert a new cell below |
| Right-click cell | Access Fix, Explain, Optimise, Document actions |

---

## Effective Prompt Patterns

The following patterns produce consistently better results. Practice them throughout the labs.

**Include schema context:**
> "Using the `nem12_interval_reads` view with columns nmi (string), interval_date (date), interval_number (int, 1–48), read_kwh (double), quality_flag (string: A or E), region (string: NSW1/VIC1/etc.)…"

**State the output shape:**
> "Return a DataFrame with columns: nmi, interval_date, peak_kwh. One row per NMI per day."

**Include domain terms:**
> "Using NEM standard half-hour intervals (interval 1 = 00:00–00:30 AEST)…"

**Say what to avoid:**
> "Use a Spark window function — no Python loops, no collect()."

**For the Fix/Chat panel:**
> "This filter is wrong. I want meters where MORE than 5% of intervals are estimated, not fewer. Fix the filter condition."
