# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A5C 0%, #FF3621 100%); padding: 28px 36px; border-radius: 10px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; margin: 0 0 8px 0; font-size: 2em;">📋 MCP &amp; Skills Quick Reference</h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); margin: 0; font-size: 1.1em;">Keep this open during Workshop 2a — all the commands, URLs, and patterns you need</p>
# MAGIC </div>
# MAGIC <div style="background: #FFF8E7; border-left: 4px solid #FF3621; padding: 10px 18px; border-radius: 0 6px 6px 0; margin-top: 12px;">
# MAGIC   <strong>How to use this notebook:</strong> This is a reference card, not a lab. Nothing to run. Use <code>Cmd+F</code> / <code>Ctrl+F</code> to find what you need fast.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Genie Code — Three Ways to Extend It
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────────────────────────────┐
# MAGIC │  CUSTOM INSTRUCTIONS    │  SKILLS              │  TOOLS (UC Functions)  │
# MAGIC │  ─────────────────────  │  ──────────────────  │  ────────────────────  │
# MAGIC │  What: text in LLM      │  What: Markdown docs │  What: executable code │
# MAGIC │        system prompt    │  loaded on-demand    │        the agent runs  │
# MAGIC │                         │                      │                        │
# MAGIC │  Where: file on DBFS    │  Where: file on DBFS │  Where: Unity Catalog  │
# MAGIC │         or workspace    │         or workspace │         (SQL function) │
# MAGIC │                         │                      │                        │
# MAGIC │  When: every turn       │  When: when relevant │  When: agent decides   │
# MAGIC │        (always loaded)  │  or @mention         │        to call it      │
# MAGIC │                         │                      │                        │
# MAGIC │  Used by: chat + agent  │  Used by: agent only │  Used by: agent only   │
# MAGIC └─────────────────────────┴──────────────────────┴────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC > **TL;DR:** Custom instructions = always-on context. Skills = on-demand knowledge. Tools = real actions (queries, calculations, API calls).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. File Paths for Custom Instructions & Skills
# MAGIC
# MAGIC ### Custom Instructions
# MAGIC | Scope | Path | Who it applies to |
# MAGIC |-------|------|-------------------|
# MAGIC | Personal | `/Users/{you}/.assistant_instructions.md` | Only you |
# MAGIC | Workspace | `Workspace/.assistant_workspace_instructions.md` | Everyone in workspace |
# MAGIC
# MAGIC ### Skills
# MAGIC | Scope | Path |
# MAGIC |-------|------|
# MAGIC | Personal skill | `/Users/{you}/.assistant/skills/{name}/SKILL.md` |
# MAGIC | Workspace skill | `Workspace/.assistant/skills/{name}/SKILL.md` |
# MAGIC
# MAGIC ### Auto-discovered Project Files
# MAGIC ```
# MAGIC AGENTS.md      ← placed in a notebook directory; auto-loaded for notebooks in that folder
# MAGIC CLAUDE.md      ← same behaviour (alternative name)
# MAGIC ```
# MAGIC > Genie Code walks up the directory tree looking for these files. Put an `AGENTS.md` next to your lab notebooks and it loads automatically.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Skill File Template
# MAGIC
# MAGIC Minimal valid SKILL.md:
# MAGIC
# MAGIC ```markdown
# MAGIC ---
# MAGIC name: your-skill-name
# MAGIC description: One sentence — what this skill helps with
# MAGIC ---
# MAGIC
# MAGIC # Skill Title
# MAGIC
# MAGIC Content goes here. Write it like documentation you'd want to read yourself.
# MAGIC Use tables, code blocks, bullet lists — all standard Markdown.
# MAGIC ```
# MAGIC
# MAGIC ### Frontmatter fields
# MAGIC | Field | Required | Notes |
# MAGIC |-------|----------|-------|
# MAGIC | `name` | Yes | Slug used for `@mention` — no spaces, lowercase |
# MAGIC | `description` | Yes | The LLM reads this to decide whether to load the skill |
# MAGIC | `author` | No | Shown in skill browser |
# MAGIC | `version` | No | Useful for change tracking |
# MAGIC
# MAGIC > **Tip:** The `description` field is the selector. Write it to match the phrasing participants will actually use. "NEM12 data", "SAIDI calculations", "APRA audit" will match; vague descriptions like "energy stuff" won't.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. MCP Endpoint URL Patterns
# MAGIC
# MAGIC Replace `{workspace}` with your workspace URL (e.g. `adb-1234567890.12.azuredatabricks.net`).
# MAGIC
# MAGIC ```
# MAGIC UC Functions (entire schema):
# MAGIC   https://{workspace}/api/2.0/mcp/functions/{catalog}/{schema}
# MAGIC
# MAGIC UC Functions (single function):
# MAGIC   https://{workspace}/api/2.0/mcp/functions/{catalog}/{schema}/{function_name}
# MAGIC
# MAGIC Genie Space:
# MAGIC   https://{workspace}/api/2.0/mcp/genie/{space_id}
# MAGIC
# MAGIC Vector Search index:
# MAGIC   https://{workspace}/api/2.0/mcp/vector-search/{catalog}/{schema}/{index_name}
# MAGIC
# MAGIC Databricks SQL (query execution):
# MAGIC   https://{workspace}/api/2.0/mcp/sql
# MAGIC
# MAGIC External connection:
# MAGIC   https://{workspace}/api/2.0/mcp/external/{connection_name}
# MAGIC ```
# MAGIC
# MAGIC ### Authentication
# MAGIC All endpoints accept:
# MAGIC - **PAT** (Personal Access Token) — easiest for workshop/dev
# MAGIC - **M2M OAuth** (Service Principal + client secret) — preferred for production
# MAGIC - **U2M OAuth** — for user-facing applications

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Package → Use Case Matrix
# MAGIC
# MAGIC | Package | When to use | Install |
# MAGIC |---------|------------|---------|
# MAGIC | `databricks-openai` | OpenAI Agents SDK + Databricks MCP | `pip install databricks-openai` |
# MAGIC | `databricks-langchain` | LangGraph + LangChain + Databricks MCP | `pip install databricks-langchain` |
# MAGIC | `databricks-mcp` | Low-level MCP client (framework-agnostic) | `pip install databricks-mcp` |
# MAGIC | `databricks-sdk` | All Databricks APIs (auth, UC, clusters, etc.) | `pip install databricks-sdk` |
# MAGIC
# MAGIC > **When in doubt:** Use `databricks-openai` if you are writing code for OpenAI Agents SDK. Use `databricks-langchain` if you are writing LangGraph agents. Use `databricks-mcp` only if you need direct protocol-level access.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. OpenAI Agents SDK — Minimal Example
# MAGIC
# MAGIC ```python
# MAGIC # pip install databricks-openai openai
# MAGIC
# MAGIC from openai import OpenAI
# MAGIC from agents import Agent, Runner
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks_openai import UCFunctionToolkit
# MAGIC
# MAGIC # ── Auth ──────────────────────────────────────────────
# MAGIC w = WorkspaceClient()          # picks up env vars or ~/.databrickscfg
# MAGIC client = OpenAI(
# MAGIC     api_key=w.config.token,
# MAGIC     base_url=f"{w.config.host}/serving-endpoints/databricks-claude-sonnet-4-6/v1",
# MAGIC )
# MAGIC
# MAGIC # ── Tools: expose a whole UC schema as MCP tools ───────
# MAGIC toolkit = UCFunctionToolkit(
# MAGIC     warehouse_id="your-warehouse-id",   # SQL warehouse for function execution
# MAGIC     client=w,
# MAGIC )
# MAGIC tools = toolkit.get_tools(function_names=["workshop_au.energy.*"])
# MAGIC
# MAGIC # ── Agent ──────────────────────────────────────────────
# MAGIC agent = Agent(
# MAGIC     name="energy-analyst",
# MAGIC     model=client,                        # use the Databricks-hosted model
# MAGIC     tools=tools,
# MAGIC     instructions=(
# MAGIC         "You are an energy operations analyst. "
# MAGIC         "Always quote the NMI when discussing meter data. "
# MAGIC         "Express consumption in kWh."
# MAGIC     ),
# MAGIC )
# MAGIC
# MAGIC # ── Run ────────────────────────────────────────────────
# MAGIC result = Runner.run_sync(
# MAGIC     agent,
# MAGIC     "What was the peak demand for region VIC in January 2024?",
# MAGIC )
# MAGIC print(result.final_output)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. LangGraph — Minimal Example
# MAGIC
# MAGIC ```python
# MAGIC # pip install databricks-langchain langgraph
# MAGIC
# MAGIC from databricks_langchain import ChatDatabricks
# MAGIC from databricks_langchain.tools import UCFunctionToolkit as LCToolkit
# MAGIC from langgraph.prebuilt import create_react_agent
# MAGIC
# MAGIC # ── Model ──────────────────────────────────────────────
# MAGIC llm = ChatDatabricks(
# MAGIC     endpoint="databricks-claude-sonnet-4-6",
# MAGIC     temperature=0,
# MAGIC )
# MAGIC
# MAGIC # ── Tools ──────────────────────────────────────────────
# MAGIC toolkit = LCToolkit(
# MAGIC     warehouse_id="your-warehouse-id",
# MAGIC )
# MAGIC tools = toolkit.get_tools(function_names=["workshop_au.energy.*"])
# MAGIC
# MAGIC # ── Agent (ReAct loop) ─────────────────────────────────
# MAGIC agent = create_react_agent(
# MAGIC     model=llm,
# MAGIC     tools=tools,
# MAGIC     state_modifier=(                        # system prompt
# MAGIC         "You are an energy operations analyst for an Australian DNO. "
# MAGIC         "Apply @energy-operations skill context to all answers."
# MAGIC     ),
# MAGIC )
# MAGIC
# MAGIC # ── Invoke ────────────────────────────────────────────
# MAGIC response = agent.invoke({
# MAGIC     "messages": [
# MAGIC         {"role": "user", "content": "Summarise unplanned outages in NSW for Q1 2024"}
# MAGIC     ]
# MAGIC })
# MAGIC print(response["messages"][-1].content)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Claude Desktop Config
# MAGIC
# MAGIC Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
# MAGIC or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):
# MAGIC
# MAGIC ```json
# MAGIC {
# MAGIC   "mcpServers": {
# MAGIC     "databricks-uc-functions": {
# MAGIC       "command": "databricks",
# MAGIC       "args": [
# MAGIC         "mcp",
# MAGIC         "start",
# MAGIC         "--profile", "DEFAULT",
# MAGIC         "--transport", "stdio",
# MAGIC         "--server-type", "uc-functions",
# MAGIC         "--function-name-pattern", "workshop_au.energy.*"
# MAGIC       ]
# MAGIC     },
# MAGIC     "databricks-genie": {
# MAGIC       "command": "databricks",
# MAGIC       "args": [
# MAGIC         "mcp",
# MAGIC         "start",
# MAGIC         "--profile", "DEFAULT",
# MAGIC         "--transport", "stdio",
# MAGIC         "--server-type", "genie",
# MAGIC         "--space-id", "YOUR_GENIE_SPACE_ID"
# MAGIC       ]
# MAGIC     }
# MAGIC   }
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC > **Auth:** The Databricks CLI reads from `~/.databrickscfg`. Run `databricks auth login` once to configure. No secrets in the JSON.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Tool Naming Convention
# MAGIC
# MAGIC UC Functions use three-part names with dots. MCP converts these to tool names with double underscores:
# MAGIC
# MAGIC ```
# MAGIC UC function name:   workshop_au.energy.calculate_peak_demand
# MAGIC MCP tool name:      workshop_au__energy__calculate_peak_demand
# MAGIC                     (each dot becomes two underscores)
# MAGIC ```
# MAGIC
# MAGIC This matters when:
# MAGIC - Filtering tool calls in code (`if tool_name == "workshop_au__energy__..."`)
# MAGIC - Reading agent logs — you'll see the MCP form
# MAGIC - Building evals that check which tools were invoked
# MAGIC
# MAGIC ### Wildcard patterns (for `function_names` filter)
# MAGIC | Pattern | Matches |
# MAGIC |---------|---------|
# MAGIC | `workshop_au.energy.*` | All functions in the `energy` schema |
# MAGIC | `workshop_au.*.*` | All functions in the `workshop_au` catalog |
# MAGIC | `workshop_au.energy.calculate_peak_demand` | Exact match only |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. MCP Limits & Behaviour Notes
# MAGIC
# MAGIC ```
# MAGIC Max tools visible to an agent:   20 total (model context limit)
# MAGIC Max tools per MCP server:        15 (recommended; enforce via function_name filter)
# MAGIC Genie MCP:                       async — agent polls for long-running Genie queries
# MAGIC UC Function timeout:             default 300 s (configurable on warehouse)
# MAGIC Vector Search MCP:               returns top-k results as JSON; k configurable
# MAGIC ```
# MAGIC
# MAGIC ### AU East data residency
# MAGIC | Feature | AU East? |
# MAGIC |---------|----------|
# MAGIC | UC Functions MCP | ✅ In-region |
# MAGIC | Genie MCP | ✅ In-region |
# MAGIC | Vector Search MCP | ✅ In-region |
# MAGIC | Databricks SQL MCP | ✅ In-region |
# MAGIC | FMAPI Provisioned Throughput | ✅ In-region |
# MAGIC | FMAPI Pay-Per-Token | ❌ Cross-geo — do NOT use for regulated data |
# MAGIC | AI Functions default endpoints | ❌ Cross-geo — use `ai_query()` → PT endpoint |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Keyboard Shortcuts
# MAGIC
# MAGIC | Action | Mac | Windows / Linux |
# MAGIC |--------|-----|-----------------|
# MAGIC | Open Genie Code inline (in notebook) | `Cmd + I` | `Ctrl + I` |
# MAGIC | Invoke a skill by name | `@skill-name` in chat panel | same |
# MAGIC | Accept a code suggestion | `Tab` | `Tab` |
# MAGIC | Dismiss a suggestion | `Esc` | `Esc` |
# MAGIC | Open Genie Code side panel | Click ✨ in the notebook toolbar | same |
# MAGIC | Re-run last cell | `Shift + Enter` | `Shift + Enter` |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC <div style="background: #E8F4FD; border: 1px solid #1B3A5C; padding: 14px 20px; border-radius: 6px; margin-top: 16px;">
# MAGIC   <strong>Workshop labs:</strong>
# MAGIC   <code>01_genie_code_intro.py</code> →
# MAGIC   <code>02_notebook_ai_features.py</code> →
# MAGIC   <code>03_adding_skills_tools.py</code> →
# MAGIC   <code>04_mcp_integration.py</code>
# MAGIC   <br/><br/>
# MAGIC   <strong>Skills deployed to workspace:</strong> <code>@energy-operations</code> &nbsp;|&nbsp; <code>@apra-compliance</code>
# MAGIC   <br/>
# MAGIC   <strong>UC functions:</strong> <code>workshop_au.energy.*</code> (see Lab 3)
# MAGIC </div>
