# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     📊 Lab 05: Monitoring & Governing Your MCP Agent
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Workshop 2c: Building AI Agents with MCP — Australian Regulated Industries
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     From demo to production: visibility, cost control, and audit trail
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>30 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01–04 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>All audit data in AU East ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">APRA relevance</strong><br>CPS 234 evidence trail
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will learn
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | AI Gateway | Usage dashboard, inference table, rate limits for agent SPs | 10 min |
# MAGIC | 2 | MLflow Traces | Trace UI walkthrough, programmatic trace queries, finding slow/failed MCP calls | 10 min |
# MAGIC | 3 | Audit Logging | `system.access.audit` for MCP calls, APRA evidence framing, per-SP rate limits | 10 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Why governance matters more for AI agents than for notebooks
# MAGIC
# MAGIC A notebook running a SQL query touches one asset and produces one output.
# MAGIC An MCP agent in a loop can call ten tools, synthesise results from three systems,
# MAGIC and return an answer — all in one user message. The governance surface is larger.
# MAGIC
# MAGIC | Risk | Without governance | With this lab's controls |
# MAGIC |------|-------------------|--------------------------|
# MAGIC | Cost overrun | Agent calls PT endpoint unbounded | AI Gateway rate limits per SP |
# MAGIC | Data exfiltration | No record of which tables agent queried | `system.access.audit` logs every MCP call |
# MAGIC | Incident investigation | "Something went wrong" — no detail | MLflow traces show every tool call and LLM reasoning step |
# MAGIC | APRA CPS 234 audit | Cannot demonstrate AI access controls | Full audit trail: user → agent → tool → data asset |
# MAGIC | Model hallucination | No visibility into tool results vs. final answer | MLflow traces show input/output at every node |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Workshop configuration
# MAGIC
# MAGIC Run this cell once. All subsequent cells read from these widgets.

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo",    "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint name")
dbutils.widgets.text("app_name",       "aemo-operations-agent","App name (from Lab 04)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
APP_NAME       = dbutils.widgets.get("app_name")

from databricks.sdk import WorkspaceClient
ws = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

print(f"Workspace host  : {HOST}")
print(f"Catalog.Schema  : {CATALOG}.{SCHEMA_AEMO}")
print(f"PT endpoint     : {PT_ENDPOINT}")
print(f"App name        : {APP_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Workspace host  : https://adb-1234567890123456.7.azuredatabricks.net
# MAGIC Catalog.Schema  : workshop_au.aemo
# MAGIC PT endpoint     : au_east_llm_inregion
# MAGIC App name        : aemo-operations-agent
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — AI Gateway for MCP Agents (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Navigate to the AI Gateway usage dashboard
# MAGIC
# MAGIC The AI Gateway records every call made to your PT endpoint — whether from a
# MAGIC notebook, an App, or a direct API call. This is your first stop when investigating
# MAGIC cost or performance questions.
# MAGIC
# MAGIC **How to get there:**
# MAGIC ```
# MAGIC Left sidebar → Machine Learning
# MAGIC             → Serving
# MAGIC             → click "au_east_llm_inregion" (your PT endpoint)
# MAGIC             → Metrics tab (top of the endpoint page)
# MAGIC ```
# MAGIC
# MAGIC **What you should see:**
# MAGIC ```
# MAGIC ┌─── au_east_llm_inregion — Metrics ─────────────────────────────────────────┐
# MAGIC │                                                                             │
# MAGIC │  Time range: [Last 24 hours ▼]   Granularity: [5 minutes ▼]               │
# MAGIC │                                                                             │
# MAGIC │  ┌─ Token usage ─────────────────────────────────────────────────────┐     │
# MAGIC │  │                                                                   │     │
# MAGIC │  │  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Input tokens (prompt)    │     │
# MAGIC │  │  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Output tokens            │     │
# MAGIC │  │                                                                   │     │
# MAGIC │  │  Total (24h):  4,523 tokens                                       │     │
# MAGIC │  │  Input:        3,891  (86%)                                       │     │
# MAGIC │  │  Output:         632  (14%)                                       │     │
# MAGIC │  │                                                                   │     │
# MAGIC │  │  For MCP agents, input tokens are typically high relative to      │     │
# MAGIC │  │  output — the system prompt + tool schemas + tool results all     │     │
# MAGIC │  │  count as input on every turn.                                    │     │
# MAGIC │  └───────────────────────────────────────────────────────────────────┘     │
# MAGIC │                                                                             │
# MAGIC │  ┌─ Request volume ──────────────────────────────────────────────────┐     │
# MAGIC │  │  Total requests: 47                                               │     │
# MAGIC │  │  Success (2xx):  44 (93.6%)                                       │     │
# MAGIC │  │  Rate limited:    3 (6.4%)    ← 429 status code                  │     │
# MAGIC │  │  Errors (5xx):    0                                               │     │
# MAGIC │  └───────────────────────────────────────────────────────────────────┘     │
# MAGIC │                                                                             │
# MAGIC │  ┌─ Latency ─────────────────────────────────────────────────────────┐     │
# MAGIC │  │  p50:   987ms   p90:  2,341ms   p99:  4,892ms                    │     │
# MAGIC │  │  For context: multi-step MCP agent calls are TTFT + N × tool RTT │     │
# MAGIC │  └───────────────────────────────────────────────────────────────────┘     │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — Navigate to the AI Gateway inference table
# MAGIC
# MAGIC The inference table stores a row for every request — richer than the metrics chart.
# MAGIC It is what you query in SQL to answer "who called the endpoint, when, and how many tokens?"
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning → Serving → au_east_llm_inregion
# MAGIC                           → AI Gateway tab (next to Metrics)
# MAGIC
# MAGIC ┌─── au_east_llm_inregion — AI Gateway ──────────────────────────────────────┐
# MAGIC │                                                                             │
# MAGIC │  Inference table:  workshop_au.aemo.inference_au_east_llm_inregion         │
# MAGIC │  Status:           Enabled ✅                                              │
# MAGIC │                                                                             │
# MAGIC │  Usage (last 24 hours):                                                     │
# MAGIC │  ┌───────────────────────────────────────────────────────────────────────┐ │
# MAGIC │  │  timestamp    client_user_id           tokens  latency_ms  status     │ │
# MAGIC │  │  ─────────    ──────────────────────   ──────  ──────────  ──────     │ │
# MAGIC │  │  09:23:14     beyza.yalavac@...         423    1,234       200 OK     │ │
# MAGIC │  │  09:31:02     beyza.yalavac@...         512      987       200 OK     │ │
# MAGIC │  │  09:45:17     beyza.yalavac@...           0       <1       429 ←      │ │
# MAGIC │  │                                                      rate limited      │ │
# MAGIC │  │  09:52:44     app-sp-aemo-...@...        891    2,341       200 OK    │ │
# MAGIC │  │  10:03:11     app-sp-aemo-...@...        634    1,102       200 OK    │ │
# MAGIC │  └───────────────────────────────────────────────────────────────────────┘ │
# MAGIC │                                                                             │
# MAGIC │  Note: "app-sp-aemo-...@..." is the App's service principal.              │
# MAGIC │  Calls from the deployed App appear with the App SP identity, not yours.   │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Query the AI Gateway inference table with SQL

# COMMAND ----------

# Query the AI Gateway inference table for agent activity
# The table name follows the pattern: <catalog>.<schema>.inference_<endpoint_name>
# with hyphens replaced by underscores

INFERENCE_TABLE = f"{CATALOG}.{SCHEMA_AEMO}.inference_{PT_ENDPOINT.replace('-', '_')}"
print(f"Inference table: {INFERENCE_TABLE}")
print()
print("Run the SQL below in a SQL cell or a DBSQL editor:\n")

sql_usage_summary = f"""
-- AI Gateway usage summary — last 24 hours
SELECT
  DATE_TRUNC('hour', timestamp)                           AS hour,
  client_user_id,
  COUNT(*)                                                AS request_count,
  SUM(usage.prompt_tokens)                               AS input_tokens,
  SUM(usage.completion_tokens)                           AS output_tokens,
  SUM(usage.total_tokens)                                AS total_tokens,
  ROUND(AVG(databricks_output.latency_ms), 0)            AS avg_latency_ms,
  SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END)    AS rate_limited_count
FROM {INFERENCE_TABLE}
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
GROUP BY 1, 2
ORDER BY 1 DESC, 4 DESC
"""

print(sql_usage_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (results after running the SQL query above):**
# MAGIC ```
# MAGIC hour                client_user_id               req_count  input_tok  output_tok  total_tok  avg_lat_ms  rate_limited
# MAGIC ───────────────     ──────────────────────────   ─────────  ─────────  ──────────  ─────────  ──────────  ────────────
# MAGIC 2025-06-12 10:00    app-sp-aemo-...@company.com      12       5,234         892       6,126       1,842            0
# MAGIC 2025-06-12 09:00    beyza.yalavac@databricks.com      8       3,891         632       4,523         987            3
# MAGIC 2025-06-12 08:00    app-sp-aemo-...@company.com       6       2,103         441       2,544       2,103            0
# MAGIC ```
# MAGIC
# MAGIC **What to notice:**
# MAGIC - The App SP (`app-sp-aemo-...`) is the identity for all calls from the deployed App
# MAGIC - Rate-limited calls (429) show 0 tokens and sub-millisecond latency — they never reached the LLM
# MAGIC - Input tokens are consistently much higher than output tokens for an agent with tool use

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 — Query the inference table programmatically with PySpark

# COMMAND ----------

# Query inference table — top callers this week
try:
    df = spark.sql(f"""
        SELECT
            client_user_id,
            COUNT(*)                                          AS requests,
            SUM(usage.total_tokens)                          AS total_tokens,
            ROUND(AVG(databricks_output.latency_ms), 0)      AS avg_latency_ms,
            MAX(databricks_output.latency_ms)                AS max_latency_ms,
            SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) AS errors
        FROM {INFERENCE_TABLE}
        WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
        GROUP BY client_user_id
        ORDER BY total_tokens DESC
        LIMIT 10
    """)

    print(f"Top callers to {PT_ENDPOINT} — last 7 days:\n")
    df.show(truncate=60)

except Exception as e:
    print(f"Could not query inference table: {e}")
    print()
    print("Possible causes:")
    print("  • AI Gateway inference logging not enabled on the endpoint")
    print("    → Machine Learning → Serving → endpoint → AI Gateway tab → enable logging")
    print("  • No calls to the endpoint in the last 7 days")
    print("  • Table name mismatch — check the endpoint name and table naming pattern")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Top callers to au_east_llm_inregion — last 7 days:
# MAGIC
# MAGIC +-----------------------------+--------+------------+---------------+---------------+------+
# MAGIC | client_user_id              |requests|total_tokens|avg_latency_ms |max_latency_ms |errors|
# MAGIC +-----------------------------+--------+------------+---------------+---------------+------+
# MAGIC | app-sp-aemo-op...           |    157 |     72,341 |          1,892|          8,203|     2|
# MAGIC | beyza.yalavac@databricks.com|     43 |     18,923 |            987|          4,102|     5|
# MAGIC +-----------------------------+--------+------------+---------------+---------------+------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 — Set rate limits specifically for the agent's service principal
# MAGIC
# MAGIC In a production deployment you want the App's service principal to have
# MAGIC a budget separate from interactive notebook users.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning → Serving → au_east_llm_inregion
# MAGIC                           → AI Gateway tab → Rate limits
# MAGIC
# MAGIC ┌─── Rate limits — au_east_llm_inregion ─────────────────────────────────────┐
# MAGIC │                                                                             │
# MAGIC │  Default limit (all users):  1,000 requests/minute                         │
# MAGIC │                                                                             │
# MAGIC │  Per-principal overrides:                                                   │
# MAGIC │  ┌───────────────────────────────────────┬──────────────────────────────┐  │
# MAGIC │  │ Principal                             │ Limit                        │  │
# MAGIC │  ├───────────────────────────────────────┼──────────────────────────────┤  │
# MAGIC │  │ app-sp-aemo-operations-agent@...      │ 100 requests/minute          │  │
# MAGIC │  │ beyza.yalavac@databricks.com          │ 50 requests/minute           │  │
# MAGIC │  └───────────────────────────────────────┴──────────────────────────────┘  │
# MAGIC │                                                                             │
# MAGIC │  [+ Add rate limit]                                                         │
# MAGIC │                                                                             │
# MAGIC │  Rate limit types:                                                          │
# MAGIC │    requests/minute  — total number of API calls                            │
# MAGIC │    tokens/minute    — total tokens (input + output)                        │
# MAGIC │    tokens/day       — daily budget cap (useful for cost control)           │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **Recommended limits for an MCP agent on a regulated system:**
# MAGIC
# MAGIC | Limit type | Suggested value | Rationale |
# MAGIC |-----------|----------------|-----------|
# MAGIC | `tokens/day` per App SP | 500,000 | Approx AUD ~$5–10/day at PT pricing — sets a daily budget ceiling |
# MAGIC | `requests/minute` per App SP | 60 | Throttles runaway loops — a healthy agent handles <10 req/min |
# MAGIC | `requests/minute` default | 200 | Headroom for interactive notebook users |

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — MLflow Traces for Agent Debugging (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 — Navigate to the MLflow Traces UI
# MAGIC
# MAGIC MLflow Tracing records every step of an agent run — the user's question,
# MAGIC each LLM call, each tool invocation, inputs/outputs, latency, and errors.
# MAGIC This is the primary debugging tool for MCP agents.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Machine Learning (left sidebar)
# MAGIC           → Experiments
# MAGIC           → find "/Apps/aemo-operations-agent"
# MAGIC              (or the experiment set in mlflow.set_experiment() in app.py)
# MAGIC           → Traces tab (next to Runs)
# MAGIC
# MAGIC ┌─── Experiment: /Apps/aemo-operations-agent — Traces ──────────────────────┐
# MAGIC │                                                                            │
# MAGIC │  🔍 Filter: [status: all ▼]  [tag: ▼]  [model: ▼]   [last 7 days ▼]     │
# MAGIC │                                                                            │
# MAGIC │  Trace ID        Timestamp         Latency   Status   Input preview       │
# MAGIC │  ────────────    ─────────────────  ───────   ──────   ─────────────────  │
# MAGIC │  tr-a3f8c1d...   2025-06-12 10:23  2,341ms   OK       "What was the av…" │
# MAGIC │  tr-b721e4a...   2025-06-12 09:51  8,203ms   OK       "Were there any L…"│
# MAGIC │  tr-c9d3f82...   2025-06-12 09:31  TIMEOUT   ERROR    "Show me the five" │
# MAGIC │  tr-d4e1a9b...   2025-06-12 09:15    987ms   OK       "Which generator…" │
# MAGIC │                                                                            │
# MAGIC │  Click any row to see the full trace tree →                               │
# MAGIC └────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 — Reading a trace: the tree view
# MAGIC
# MAGIC Click into any trace row to open the tree view. This shows every node of the
# MAGIC agent's reasoning and tool calling chain:
# MAGIC
# MAGIC ```
# MAGIC ┌─── Trace: tr-a3f8c1d — "What was the average spot price in VIC yesterday?" ─┐
# MAGIC │                                                                               │
# MAGIC │  Total duration: 2,341ms     Status: OK     Tokens: 1,203 in / 189 out       │
# MAGIC │                                                                               │
# MAGIC │  ▼ AgentRun (2,341ms total)                                                   │
# MAGIC │    │                                                                          │
# MAGIC │    ├── ▼ LLMCall — "Which tool should I use?" (456ms)                        │
# MAGIC │    │       Input:  system_prompt + user message + tool schemas                │
# MAGIC │    │       Output: tool_call { name: "ask_genie", args: {query: "avg VIC…"}} │
# MAGIC │    │                                                                          │
# MAGIC │    ├── ▼ MCPToolCall — ask_genie (1,203ms)                                   │
# MAGIC │    │       Input:  { query: "average spot price VIC yesterday" }              │
# MAGIC │    │       Output: {                                                          │
# MAGIC │    │                 sql: "SELECT AVG(RRP) FROM dispatch_price              │
# MAGIC │    │                       WHERE REGIONID='VIC1'                            │
# MAGIC │    │                       AND SETTLEMENTDATE >= CURRENT_DATE - 1",         │
# MAGIC │    │                 result: [{"avg(RRP)": 142.50}]                          │
# MAGIC │    │               }                                                          │
# MAGIC │    │                                                                          │
# MAGIC │    └── ▼ LLMCall — "Synthesise answer" (682ms)                               │
# MAGIC │            Input:  tool result + conversation history                         │
# MAGIC │            Output: "The average spot price in Victoria (VIC1)                │
# MAGIC │                     yesterday was $142.50/MWh. This was ..."                 │
# MAGIC │                                                                               │
# MAGIC └───────────────────────────────────────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC **What to look for when debugging:**
# MAGIC
# MAGIC | Symptom | Where to look in the trace |
# MAGIC |---------|--------------------------|
# MAGIC | Wrong answer | LLMCall (synthesis) input — did the tool return what you expected? |
# MAGIC | Slow response | Which node has the highest duration? Is it LLM or MCP tool? |
# MAGIC | Tool not called | First LLMCall output — did the LLM select the right tool? |
# MAGIC | Tool call failed | MCPToolCall output — error message from the UC function |
# MAGIC | High token count | LLMCall input — large system prompt or verbose tool results |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 — Query MLflow traces programmatically

# COMMAND ----------

import mlflow
from mlflow.entities import ViewType

# Set the experiment to match what app.py configured
EXPERIMENT_NAME = "/Apps/aemo-operations-agent"

try:
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        print(f"Experiment '{EXPERIMENT_NAME}' not found.")
        print("Run some queries through the deployed app first, then re-run this cell.")
    else:
        print(f"Experiment found: {experiment.name}")
        print(f"Experiment ID:    {experiment.experiment_id}")
        print()

        # Search for recent traces (MLflow 2.17+ traces API)
        # Traces are stored as Runs with a special tag in recent MLflow versions
        recent_runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="",
            run_view_type=ViewType.ACTIVE_ONLY,
            max_results=20,
            order_by=["start_time DESC"],
        )

        if recent_runs.empty:
            print("No runs found yet. Run some queries through the app to generate traces.")
        else:
            print(f"Recent agent runs ({len(recent_runs)} found):\n")
            display_cols = [
                c for c in recent_runs.columns
                if any(k in c for k in ["start_time", "end_time", "status", "metrics", "params"])
            ]
            print(recent_runs[display_cols[:8]].to_string(index=False))

except Exception as e:
    print(f"Could not query MLflow: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.4 — Find the slowest MCP tool calls
# MAGIC
# MAGIC This is the most practical debugging query: which MCP tool calls are adding latency?

# COMMAND ----------

# Query MLflow traces to find slow MCP tool calls
# Uses the MLflow Tracing API (MLflow 2.17+)

try:
    from mlflow.tracing.fluent import get_traces

    traces = mlflow.search_traces(
        experiment_names=[EXPERIMENT_NAME],
        filter_string="",
        max_results=50,
    )

    if not traces:
        print("No traces found. Run some queries through the app first.")
    else:
        print(f"Found {len(traces)} traces. Analysing MCP tool call latencies...\n")

        tool_latencies = []
        for trace in traces:
            for span in trace.data.spans:
                if span.span_type in ("TOOL", "RETRIEVER") or "mcp" in span.name.lower():
                    duration_ms = (span.end_time_ns - span.start_time_ns) / 1_000_000
                    tool_latencies.append({
                        "trace_id":    trace.info.trace_id[:12] + "...",
                        "tool_name":   span.name[:40],
                        "duration_ms": round(duration_ms, 0),
                        "status":      span.status.status_code if span.status else "unknown",
                    })

        if tool_latencies:
            tool_latencies.sort(key=lambda x: x["duration_ms"], reverse=True)
            print(f"{'Tool name':<42} {'Duration ms':>12} {'Status':<12} {'Trace'}")
            print("-" * 90)
            for row in tool_latencies[:15]:
                print(
                    f"{row['tool_name']:<42} "
                    f"{row['duration_ms']:>12.0f} "
                    f"{str(row['status']):<12} "
                    f"{row['trace_id']}"
                )
        else:
            print("No MCP tool call spans found in recent traces.")
            print("Ensure the agent in app.py has MLflow autolog or manual tracing enabled.")

except Exception as e:
    print(f"Trace query failed: {e}")
    print()
    print("MLflow search_traces requires MLflow 2.17+.")
    print(f"Installed version: {mlflow.__version__}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC Found 12 traces. Analysing MCP tool call latencies...
# MAGIC
# MAGIC Tool name                                  Duration ms    Status       Trace
# MAGIC ------------------------------------------------------------------------------------------
# MAGIC workshop_au__aemo__ask_genie                      1,891    OK           tr-a3f8c1d...
# MAGIC workshop_au__aemo__ask_genie                      1,203    OK           tr-b721e4a...
# MAGIC workshop_au__aemo__get_dispatch_intervals           842    OK           tr-d4e1a9b...
# MAGIC workshop_au__aemo__get_market_notices               634    OK           tr-c9d3f82...
# MAGIC workshop_au__aemo__get_dispatch_intervals           298    OK           tr-e2f5b8a...
# MAGIC ```
# MAGIC
# MAGIC > **What this tells you:**
# MAGIC > `ask_genie` is consistently the slowest tool — it runs NL→SQL on Genie which
# MAGIC > involves an extra LLM call. If latency is a concern, pre-materialise common
# MAGIC > queries as UC functions with embedded SQL instead of routing through Genie.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.5 — Find failed tool calls

# COMMAND ----------

try:
    traces = mlflow.search_traces(
        experiment_names=[EXPERIMENT_NAME],
        filter_string="",
        max_results=100,
    )

    failed_spans = []
    for trace in traces:
        for span in trace.data.spans:
            status = span.status.status_code if span.status else "UNSET"
            if str(status) in ("ERROR", "INTERNAL_ERROR", "UNSET"):
                failed_spans.append({
                    "trace_id":    trace.info.trace_id[:16] + "...",
                    "span_name":   span.name[:40],
                    "status":      str(status),
                    "error":       (span.attributes or {}).get("exception.message", "—")[:60],
                })

    if not failed_spans:
        print("No failed spans found in recent traces.")
        print("All MCP tool calls completed successfully.")
    else:
        print(f"Found {len(failed_spans)} failed span(s):\n")
        for row in failed_spans:
            print(f"  Trace:  {row['trace_id']}")
            print(f"  Span:   {row['span_name']}")
            print(f"  Status: {row['status']}")
            print(f"  Error:  {row['error']}")
            print()

except Exception as e:
    print(f"Trace query failed: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output (all healthy):**
# MAGIC ```
# MAGIC No failed spans found in recent traces.
# MAGIC All MCP tool calls completed successfully.
# MAGIC ```
# MAGIC
# MAGIC **Expected output (if a UC function raised an error):**
# MAGIC ```
# MAGIC Found 1 failed span(s):
# MAGIC
# MAGIC   Trace:  tr-c9d3f82abc...
# MAGIC   Span:   workshop_au__aemo__get_dispatch_intervals
# MAGIC   Status: ERROR
# MAGIC   Error:  Table or view not found: workshop_au.aemo.dispatch_5min
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Audit Logging for MCP Calls (10 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — What `system.access.audit` records for MCP
# MAGIC
# MAGIC Every MCP call — whether from a notebook, an App, or an external tool — is
# MAGIC written to `system.access.audit` with a `service_name = 'mcpServer'` row.
# MAGIC
# MAGIC This means you can answer the question: **"Which AI agent called which data asset,
# MAGIC on behalf of which user, at what time?"** — a requirement for APRA CPS 234 audits.
# MAGIC
# MAGIC ```
# MAGIC Navigate: Catalog (left sidebar) → system catalog → access schema
# MAGIC                                  → audit table → Data tab or Sample Data
# MAGIC
# MAGIC Key columns for MCP audit rows:
# MAGIC
# MAGIC   event_time              — when the call happened
# MAGIC   user_identity.email     — who made the call (user or service principal)
# MAGIC   service_name            — "mcpServer" for all MCP calls
# MAGIC   action_name             — the specific MCP action (tools/call, tools/list)
# MAGIC   request_params          — { action_name: "tool_name", request_id: "..." }
# MAGIC   response.status_code    — 200 = success, 4xx/5xx = error
# MAGIC   workspace_id            — which workspace (important for multi-workspace setups)
# MAGIC
# MAGIC One agent call with 3 tool invocations → 3 rows in system.access.audit
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 — Query all MCP calls from your agent

# COMMAND ----------

# MAGIC %sql
# MAGIC -- All MCP tool calls in the last hour
# MAGIC -- Run this in a SQL cell or DBSQL editor
# MAGIC
# MAGIC SELECT
# MAGIC   event_time,
# MAGIC   user_identity.email                           AS user,
# MAGIC   request_params.action_name                    AS mcp_tool_called,
# MAGIC   request_params.request_id                     AS request_id,
# MAGIC   response.status_code                          AS http_status,
# MAGIC   DATEDIFF(ms, event_time, response_time)       AS latency_ms
# MAGIC FROM system.access.audit
# MAGIC WHERE service_name     = 'mcpServer'
# MAGIC   AND action_name      = 'mcpToolsCall'
# MAGIC   AND event_time      >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 50

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC event_time                    user                              mcp_tool_called                                req_id      status  latency_ms
# MAGIC ──────────────────────────    ──────────────────────────────    ──────────────────────────────────────────     ──────────  ──────  ──────────
# MAGIC 2025-06-12 10:23:14.321 UTC  app-sp-aemo-op...@company.com    workshop_au__aemo__get_dispatch_intervals      req-a3f8    200        842
# MAGIC 2025-06-12 10:23:12.891 UTC  app-sp-aemo-op...@company.com    ask_genie_aemo_operations_workshop             req-b1e2    200      1,891
# MAGIC 2025-06-12 09:51:04.102 UTC  beyza.yalavac@databricks.com     workshop_au__aemo__get_market_notices          req-c9d3    200        634
# MAGIC 2025-06-12 09:51:03.247 UTC  beyza.yalavac@databricks.com     ask_genie_aemo_operations_workshop             req-d4e1    200      1,203
# MAGIC ```
# MAGIC
# MAGIC > **What this shows for APRA:**
# MAGIC > - Every agent tool call is attributed to an identity (human user or App SP)
# MAGIC > - The MCP tool name identifies exactly which data asset was accessed
# MAGIC > - Latency and status confirm whether the call succeeded

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 — Find which data assets the agent accessed most

# COMMAND ----------

sql_asset_access = """
-- Data asset access frequency via MCP — last 7 days
-- Useful for: capacity planning, cost allocation, APRA evidence
SELECT
  request_params.action_name                          AS mcp_tool_called,
  user_identity.email                                 AS accessed_by,
  COUNT(*)                                            AS call_count,
  SUM(CASE WHEN response.status_code = 200 THEN 1
           ELSE 0 END)                                AS success_count,
  SUM(CASE WHEN response.status_code != 200 THEN 1
           ELSE 0 END)                                AS error_count,
  MIN(event_time)                                     AS first_seen,
  MAX(event_time)                                     AS last_seen
FROM system.access.audit
WHERE service_name  = 'mcpServer'
  AND action_name   = 'mcpToolsCall'
  AND event_time   >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
GROUP BY 1, 2
ORDER BY call_count DESC
"""

print("Run this in a SQL cell or DBSQL editor to see data asset access by agent:\n")
print(sql_asset_access)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 — MCP audit for APRA CPS 234 — what to tell the auditor
# MAGIC
# MAGIC APRA CPS 234 (Information Security) requires regulated entities to maintain
# MAGIC audit trails for information asset access, including access by automated systems.
# MAGIC
# MAGIC Here is how the controls in this workshop map to CPS 234 evidence:
# MAGIC
# MAGIC | CPS 234 requirement | Control in this workshop | Evidence location |
# MAGIC |--------------------|--------------------------|--------------------|
# MAGIC | Access to information assets is logged | Every MCP call → `system.access.audit` | `system.access.audit WHERE service_name='mcpServer'` |
# MAGIC | Access is attributed to an identity | App runs as a named service principal; notebook calls attributed to user email | `user_identity.email` column |
# MAGIC | Access controls are enforced | UC function permissions control which tools the agent can call | UC audit events + function GRANT history |
# MAGIC | Rate limits prevent abuse | AI Gateway per-SP rate limits | `system.access.audit` + AI Gateway metrics |
# MAGIC | Agent behaviour is traceable | MLflow traces record every reasoning step | MLflow experiment traces UI |
# MAGIC | Data does not leave the region | All MCP endpoints are workspace-local AU East | No egress in Azure network logs |
# MAGIC
# MAGIC ```
# MAGIC The audit story in plain English for a CPS 234 auditor:
# MAGIC
# MAGIC "When an AEMO operations analyst asks the agent a question,
# MAGIC  the query is routed to our Databricks workspace in Australia East.
# MAGIC  The agent calls only approved MCP tools, identified by UC function
# MAGIC  permissions. Every tool call is recorded in system.access.audit
# MAGIC  with the user's identity and the exact tool called. The full
# MAGIC  reasoning chain is stored in MLflow traces for post-hoc review.
# MAGIC  No data leaves Australia East at any point in the flow."
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 — List all MCP tools called in the last 24 hours (detection query)
# MAGIC
# MAGIC This query is useful for anomaly detection: are tools being called that
# MAGIC should not be accessible to the agent?

# COMMAND ----------

try:
    df = spark.sql("""
        SELECT
            request_params.action_name                                  AS tool_name,
            COUNT(DISTINCT user_identity.email)                         AS distinct_callers,
            COUNT(*)                                                     AS total_calls,
            MIN(event_time)                                              AS first_call,
            MAX(event_time)                                              AS last_call
        FROM system.access.audit
        WHERE service_name = 'mcpServer'
          AND action_name  = 'mcpToolsCall'
          AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
        GROUP BY tool_name
        ORDER BY total_calls DESC
    """)

    if df.count() == 0:
        print("No MCP tool calls found in the last 24 hours.")
        print("Trigger some queries through the app or notebook, then re-run.")
    else:
        print("MCP tool calls — last 24 hours:\n")
        df.show(truncate=50)

except Exception as e:
    print(f"Could not query system.access.audit: {e}")
    print()
    print("Ensure you have USAGE privilege on the system catalog.")
    print("Ask your workspace admin: GRANT USAGE ON CATALOG system TO <your-user>")

# COMMAND ----------

# MAGIC %md
# MAGIC **Expected output:**
# MAGIC ```
# MAGIC MCP tool calls — last 24 hours:
# MAGIC
# MAGIC +----------------------------------------------+-----------------+-----------+--------------------+--------------------+
# MAGIC | tool_name                                    |distinct_callers | total_calls| first_call         | last_call          |
# MAGIC +----------------------------------------------+-----------------+------------+--------------------+--------------------+
# MAGIC | ask_genie_aemo_operations_workshop           |               2 |         28 | 2025-06-12 08:01   | 2025-06-12 10:23   |
# MAGIC | workshop_au__aemo__get_dispatch_intervals    |               2 |         19 | 2025-06-12 08:03   | 2025-06-12 10:22   |
# MAGIC | workshop_au__aemo__get_market_notices        |               1 |          8 | 2025-06-12 09:15   | 2025-06-12 09:51   |
# MAGIC +----------------------------------------------+-----------------+------------+--------------------+--------------------+
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.6 — Detect tool calls outside business hours (anomaly pattern)
# MAGIC
# MAGIC For regulated environments you may want to alert when AI agents call data assets
# MAGIC outside expected operating windows.

# COMMAND ----------

sql_after_hours = """
-- MCP calls outside business hours (before 7am or after 7pm AEST)
-- AEST = UTC+10, AEDT = UTC+11 (use CONVERT_TIMEZONE in practice)

SELECT
  event_time,
  user_identity.email                        AS caller,
  request_params.action_name                 AS tool_called,
  HOUR(CONVERT_TIMEZONE('UTC', 'Australia/Sydney', event_time)) AS hour_aest
FROM system.access.audit
WHERE service_name = 'mcpServer'
  AND action_name  = 'mcpToolsCall'
  AND event_time  >= CURRENT_TIMESTAMP - INTERVAL 30 DAYS
  AND (
    HOUR(CONVERT_TIMEZONE('UTC', 'Australia/Sydney', event_time)) < 7
    OR
    HOUR(CONVERT_TIMEZONE('UTC', 'Australia/Sydney', event_time)) > 19
  )
ORDER BY event_time DESC
LIMIT 20
"""

print("After-hours MCP call detection query (run in SQL cell or DBSQL):\n")
print(sql_after_hours)
print()
print("Integrate this query into a Databricks Job running every hour.")
print("Use Databricks SQL Alerts to send an email/Slack notification")
print("when the query returns any rows.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.7 — Create a Databricks SQL Alert for anomalous MCP activity (UI walkthrough)
# MAGIC
# MAGIC ```
# MAGIC Navigate: SQL Editor (left sidebar)
# MAGIC           → paste the after-hours query above
# MAGIC           → Run → verify it returns columns
# MAGIC           → [Save] → name: "AEMO Agent After-Hours Alert"
# MAGIC           → [+ Create Alert] button (top right of the query editor)
# MAGIC
# MAGIC Alert configuration:
# MAGIC ┌─── Create Alert ────────────────────────────────────────────────────────────┐
# MAGIC │  Name:        AEMO Agent MCP After-Hours Activity                           │
# MAGIC │  Query:       AEMO Agent After-Hours Alert (the query you just saved)       │
# MAGIC │                                                                             │
# MAGIC │  Condition:   [Column: count(*) ▼]  [>= ▼]  [Value: 1      ]              │
# MAGIC │               ↑ triggers if ANY after-hours calls appear                   │
# MAGIC │                                                                             │
# MAGIC │  Schedule:    Every [1] [hour ▼]                                           │
# MAGIC │                                                                             │
# MAGIC │  Notify:      ✉ aemo-security@company.com                                 │
# MAGIC │               📱 Slack: #aemo-ai-alerts                                    │
# MAGIC │                                                                             │
# MAGIC │  [Create Alert]                                                             │
# MAGIC └─────────────────────────────────────────────────────────────────────────────┘
# MAGIC
# MAGIC The alert will evaluate the query on schedule and notify if the condition is met.
# MAGIC Results are stored in system.access.audit — no extra data movement required.
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary — Lab 05
# MAGIC
# MAGIC | Control | What it gives you | Where to configure |
# MAGIC |---------|------------------|--------------------|
# MAGIC | AI Gateway metrics | Token usage, latency, error rate per endpoint | ML → Serving → endpoint → Metrics |
# MAGIC | AI Gateway inference table | Per-request log: who called, when, how many tokens | ML → Serving → endpoint → AI Gateway tab |
# MAGIC | AI Gateway rate limits | Budget caps per user / per service principal | ML → Serving → endpoint → AI Gateway → Rate limits |
# MAGIC | MLflow traces | Full agent reasoning + tool call tree with latencies | ML → Experiments → your experiment → Traces |
# MAGIC | `system.access.audit` | Every MCP tool call attributed to an identity | Catalog → system → access → audit |
# MAGIC | DBSQL Alert | Automated anomaly detection and notification | SQL Editor → Save query → Create Alert |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin-top: 16px;">
# MAGIC   <strong style="color: #00843D;">APRA CPS 234 audit readiness checklist</strong><br><br>
# MAGIC   After completing Labs 01–05, you can tick the following:
# MAGIC   <ul style="margin: 8px 0 0 0;">
# MAGIC     <li>✅ All LLM inference stays in AU East (PT endpoint + workspace-local MCP)</li>
# MAGIC     <li>✅ Every agent call attributed to a named identity in system.access.audit</li>
# MAGIC     <li>✅ UC function permissions control which tools the agent can call</li>
# MAGIC     <li>✅ AI Gateway rate limits prevent runaway cost and abuse</li>
# MAGIC     <li>✅ MLflow traces provide post-hoc review of agent reasoning</li>
# MAGIC     <li>✅ DBSQL alerts detect and notify on anomalous patterns</li>
# MAGIC     <li>✅ App permissions use SSO groups — onboarding/offboarding via AD</li>
# MAGIC   </ul>
# MAGIC </div>
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 14px 20px; border-radius: 6px; margin-top: 16px;">
# MAGIC   <strong style="color: #1B3A6B;">Workshop 2c complete</strong><br><br>
# MAGIC   You have built, deployed, and governed an MCP agent end to end:<br>
# MAGIC   <strong>Lab 01</strong> — Workspace setup and PT endpoint verification<br>
# MAGIC   <strong>Lab 02</strong> — UC Functions as MCP tools<br>
# MAGIC   <strong>Lab 03</strong> — Multi-MCP LangGraph agent with Genie + UC Functions<br>
# MAGIC   <strong>Lab 04</strong> — Deploy as a Databricks App with Gradio UI<br>
# MAGIC   <strong>Lab 05</strong> — Monitor, audit, and govern in production<br><br>
# MAGIC   The full stack runs in Australia East. Every call is attributable. Every tool
# MAGIC   is governed by Unity Catalog. Every session is authenticated by Databricks OAuth.
# MAGIC </div>
