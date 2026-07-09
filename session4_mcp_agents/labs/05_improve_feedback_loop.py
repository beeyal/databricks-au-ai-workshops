# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 05 — IMPROVE: Close the Human-in-the-Loop Feedback Cycle
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Session 4: Building AI Agents with MCP — Australian Energy Sector (Level 200)
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Lifecycle phase 5 of 5 &nbsp;•&nbsp; Build → Evaluate → Govern → Deploy → <strong>Improve</strong> ↺
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>30 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Labs 01-04 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>Judge = in-region PT ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Loops back to</strong><br>Lab 02 (EVALUATE)
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will do
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | Capture feedback | thumbs up/down + free-text from the app → `agent_feedback` table | 8 min |
# MAGIC | 2 | Negatives → golden rows | Convert down-voted answers into new evaluation cases | 8 min |
# MAGIC | 3 | Re-run the Lab 02 eval | Measure improvement vs the baseline | 8 min |
# MAGIC | 4 | Refine prompt / tools | What the feedback tells you to change | 6 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### The loop
# MAGIC ```
# MAGIC Deployed app → users thumbs up/down + corrections → agent_feedback table
# MAGIC       → negatives become NEW golden rows → re-run Lab 02 eval → compare to baseline
# MAGIC       → refine prompt/tools → redeploy → (back to the top)
# MAGIC ```
# MAGIC This is what makes the lifecycle a cycle rather than a line: IMPROVE feeds straight back into
# MAGIC EVALUATE.

# COMMAND ----------

# MAGIC %pip install -q databricks-langchain "langgraph>=1.2" "mlflow>=3.0" nest_asyncio
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC ### Configuration

# COMMAND ----------

dbutils.widgets.text("catalog",        "workshop_au",          "Catalog name")
dbutils.widgets.text("schema_aemo",    "aemo",                 "AEMO schema name")
dbutils.widgets.text("pt_endpoint",    "au_east_llm_inregion", "PT endpoint (agent + judge)")
dbutils.widgets.text("vs_endpoint",    "workshop_vs",          "Vector Search endpoint")
dbutils.widgets.text("genie_space_id", "",                     "Genie Space ID (optional)")
dbutils.widgets.text("mlflow_experiment",
                     "/Shared/session4-aemo-agent",            "MLflow experiment path")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA_AEMO    = dbutils.widgets.get("schema_aemo")
PT_ENDPOINT    = dbutils.widgets.get("pt_endpoint")
VS_ENDPOINT    = dbutils.widgets.get("vs_endpoint")
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id")
MLFLOW_EXPERIMENT = dbutils.widgets.get("mlflow_experiment")

JUDGE_MODEL = f"databricks:/{PT_ENDPOINT}"  # in-region PT judge, same as Lab 02

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

UC_MCP_URL    = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"
GENIE_MCP_URL = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}" if GENIE_SPACE_ID else None
VS_MCP_URL    = f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA_AEMO}/aemo_market_notices_index"

import mlflow
mlflow.set_experiment(MLFLOW_EXPERIMENT)
print(f"Judge model: {JUDGE_MODEL}  (in-region PT)")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — Capture feedback from the deployed app (8 min)
# MAGIC </div>
# MAGIC
# MAGIC The React app (Lab 04) renders thumbs-up / thumbs-down under each answer and a free-text box
# MAGIC for corrections. On click, the backend writes one row to `app_feedback.agent_feedback`. Here we
# MAGIC create that table and seed a few illustrative rows (in production these arrive from real users).

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 — Create the feedback table

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.app_feedback")
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.app_feedback.agent_feedback (
        feedback_id   STRING,
        session_id    STRING,
        question      STRING,
        agent_answer  STRING,
        rating        STRING,          -- 'up' or 'down'
        correction    STRING,          -- free-text correction (may be null)
        user_email    STRING,
        ts            TIMESTAMP
    )
    USING DELTA
""")
print(f"Feedback table ready: {CATALOG}.app_feedback.agent_feedback")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 — What the app's backend writes (reference)
# MAGIC The endpoint the React thumbs control calls looks like this on the backend — one INSERT per
# MAGIC click. Do not run this here (it lives in the app); it is shown so you can trace the data flow.
# MAGIC ```python
# MAGIC # backend: POST /api/feedback
# MAGIC def record_feedback(payload):
# MAGIC     spark.sql(f'''INSERT INTO {CATALOG}.app_feedback.agent_feedback VALUES
# MAGIC       ('{uuid4()}', '{payload.session_id}', '{payload.question}',
# MAGIC        '{payload.answer}', '{payload.rating}', '{payload.correction}',
# MAGIC        '{payload.user_email}', current_timestamp())''')
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 — Seed illustrative feedback (stand-in for real app traffic)
# MAGIC The two down-votes below capture realistic Level-200 failure modes: a dropped region suffix and
# MAGIC a missing source citation.

# COMMAND ----------

import uuid
from pyspark.sql.functions import current_timestamp

seed_rows = [
    (str(uuid.uuid4()), "s-101", "What was the average spot price in VIC1 yesterday?",
     "The average price was about 90 dollars.", "down",
     "Wrong: must say VIC1 (with the '1'), give it in $/MWh, and cite the Genie source.",
     "analyst.a@example.com"),
    (str(uuid.uuid4()), "s-102", "Were there any LOR3 events?",
     "There were some reserve notices.", "down",
     "Too vague: should name LOR3 explicitly, summarise the notice, and cite market notices.",
     "analyst.b@example.com"),
    (str(uuid.uuid4()), "s-103", "Peak demand for QLD1?",
     "QLD1 peak demand was X MW (Source: calculate_peak_demand function).", "up",
     None, "analyst.c@example.com"),
]

cols = ["feedback_id", "session_id", "question", "agent_answer", "rating", "correction", "user_email"]
df = spark.createDataFrame(seed_rows, cols).withColumn("ts", current_timestamp())
df.write.mode("append").saveAsTable(f"{CATALOG}.app_feedback.agent_feedback")

print("Seeded feedback rows:")
display(spark.sql(
    f"SELECT rating, question, correction FROM {CATALOG}.app_feedback.agent_feedback ORDER BY ts DESC LIMIT 10"
))

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Turn negatives into new golden rows (8 min)
# MAGIC </div>
# MAGIC
# MAGIC Every thumbs-down with a correction is a question the agent got wrong and a human telling us the
# MAGIC right answer. That is exactly the shape of a golden-dataset row (`inputs` + `expectations`).

# COMMAND ----------

import json
from pathlib import Path

# Read existing golden set.
_candidates = [
    Path("../eval/golden_questions.jsonl"),
    Path.cwd().parent / "eval" / "golden_questions.jsonl",
]
try:  # resolve relative to this notebook's own workspace path (labs/ -> ../eval/)
    _nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    _candidates.append(Path("/Workspace" + _nb).parent.parent / "eval" / "golden_questions.jsonl")
except Exception:
    pass
golden_path = next((p for p in _candidates if p.is_file()), None)
if golden_path is None:
    raise FileNotFoundError(
        "golden_questions.jsonl not found — ensure the repo's eval/ folder sits next to labs/. "
        "Tried: " + ", ".join(str(p) for p in _candidates))
existing = [json.loads(l) for l in open(golden_path) if l.strip()]
print(f"Existing golden rows: {len(existing)}")

# Pull down-voted feedback with a correction and convert to golden rows.
neg = spark.sql(f"""
    SELECT question, correction
    FROM {CATALOG}.app_feedback.agent_feedback
    WHERE rating = 'down' AND correction IS NOT NULL
""").collect()

new_rows = []
for r in neg:
    # The correction text becomes the expectation. Keep expected_facts directional.
    new_rows.append({
        "inputs": {"question": r["question"]},
        "expectations": {
            "expected_facts": [r["correction"]],
            "reference": r["correction"],
        },
    })

print(f"New golden rows from negative feedback: {len(new_rows)}")
for nr in new_rows:
    print(f"  + {nr['inputs']['question'][:60]}")

# Augmented dataset used for the improvement eval (does not overwrite the source file here;
# during integration, append these to ../eval/golden_questions.jsonl once reviewed by an SME).
augmented = existing + new_rows
print(f"\nAugmented dataset size: {len(augmented)}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #e65100;">Human in the loop</strong><br>
# MAGIC   New golden rows come from a human correction, but a second human should review them before
# MAGIC   they become permanent regression cases — a bad correction poisons the eval. Here we use them
# MAGIC   in-memory to demonstrate the loop; commit to <code>../eval/golden_questions.jsonl</code> after
# MAGIC   review.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Re-run the Lab 02 evaluation and compare (8 min)
# MAGIC </div>
# MAGIC
# MAGIC Same agent, same judges (in-region PT), now against the augmented golden set. Compare the new
# MAGIC run to the <code>lab02_eval_baseline</code> run to see whether prompt/tool changes moved the
# MAGIC needle.

# COMMAND ----------

import asyncio
import nest_asyncio
nest_asyncio.apply()  # allow asyncio.run() inside the notebook's running event loop
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import (
    ChatDatabricks, DatabricksMCPServer, DatabricksMultiServerMCPClient,
)

mlflow.langchain.autolog()
llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=4096)

# Refined system prompt (see Section 4 for the rationale behind each added line).
AEMO_SYSTEM_PROMPT = """You are the AEMO Operations Assistant for the National Electricity Market.
Use NEM region codes WITH the '1' suffix (NSW1, VIC1, QLD1, SA1, TAS1) — never drop the '1'.
Prices in $/MWh, generation in MW, settlement in AUD. Market Price Cap = $15,300/MWh; floor =
-$1,000/MWh. A price spike is rrp > $300/MWh. LOR1/2/3 are Lack-Of-Reserve levels; name the exact
level. Use Genie for aggregations, UC Functions for deterministic calculations/lookups, Vector
Search for market notices. You MUST cite every factual claim with its source and MUST add
'Note: workshop dataset, not live NEM conditions.' Never invent numbers; if a tool returns nothing,
say so."""

uc_server = DatabricksMCPServer(name="aemo-uc-tools", url=UC_MCP_URL, timeout=30.0, handle_tool_error=True)
vs_server = DatabricksMCPServer(name="aemo-market-notices", url=VS_MCP_URL, timeout=30.0, handle_tool_error=True)
all_servers = [uc_server, vs_server]
if GENIE_MCP_URL:
    all_servers.append(DatabricksMCPServer(name="aemo-nem-genie", url=GENIE_MCP_URL, timeout=60.0, handle_tool_error=True))


async def _answer(question: str) -> str:
    # langchain-mcp-adapters >=0.1.0 removed context-manager support on the client.
    client = DatabricksMultiServerMCPClient(all_servers)
    tools = await client.get_tools()
    agent = create_react_agent(model=llm, tools=tools, prompt=AEMO_SYSTEM_PROMPT)
    result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content


@mlflow.trace
def predict_fn(question: str) -> str:
    return asyncio.run(_answer(question))


print("Refined agent ready for re-evaluation.")

# COMMAND ----------

from mlflow.genai.scorers import (
    Correctness, RelevanceToQuery, RetrievalGroundedness, Guidelines,
)

scorers = [
    Correctness(model=JUDGE_MODEL),
    RelevanceToQuery(model=JUDGE_MODEL),
    RetrievalGroundedness(model=JUDGE_MODEL),
    Guidelines(
        name="no_hallucination",
        guidelines=(
            "The response must not invent numbers, must cite sources, must use NEM region codes with "
            "the '1' suffix, and must include the workshop-dataset note."
        ),
        model=JUDGE_MODEL,
    ),
]

with mlflow.start_run(run_name="lab05_eval_improved") as run:
    results = mlflow.genai.evaluate(
        data=augmented,
        predict_fn=predict_fn,
        scorers=scorers,
    )

print("Improved-run metrics:")
for name, value in sorted(results.metrics.items()):
    print(f"  {name:45s} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 — Compare against the baseline

# COMMAND ----------

def metrics_for(run_name: str) -> dict:
    exp = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)
    if not exp:
        return {}
    runs = mlflow.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string=f"tags.mlflow.runName = '{run_name}'",
        order_by=["start_time DESC"], max_results=1,
    )
    if runs.empty:
        return {}
    row = runs.iloc[0]
    return {c.replace("metrics.", ""): row[c] for c in runs.columns if c.startswith("metrics.")}

baseline = metrics_for("lab02_eval_baseline")
improved = metrics_for("lab05_eval_improved")

if baseline and improved:
    print(f"{'Metric':45s} {'baseline':>12} {'improved':>12} {'delta':>10}")
    print("-" * 82)
    for k in sorted(set(baseline) & set(improved)):
        b, i = baseline[k], improved[k]
        try:
            print(f"{k:45s} {b:>12.3f} {i:>12.3f} {i - b:>+10.3f}")
        except (TypeError, ValueError):
            print(f"{k:45s} {str(b):>12} {str(i):>12}")
else:
    print("Baseline or improved metrics not found. Run Lab 02 (baseline) first, then this lab.")
    print(f"  baseline keys: {list(baseline)[:5]}")
    print(f"  improved keys: {list(improved)[:5]}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Refine the prompt and tools (6 min)
# MAGIC </div>
# MAGIC
# MAGIC The feedback pointed at concrete, fixable gaps. What each correction changed:
# MAGIC
# MAGIC | Feedback signal | Change made | Where |
# MAGIC |-----------------|-------------|-------|
# MAGIC | Dropped the region '1' suffix | Prompt: "never drop the '1'" | System prompt |
# MAGIC | Missing source citation | Prompt: "MUST cite every factual claim" (was "should") | System prompt |
# MAGIC | Vague LOR answer | Prompt: "name the exact LOR level" | System prompt |
# MAGIC | Missing units ($/MWh, MW) | Prompt reinforces units + directs deterministic calcs to UC functions | System prompt + tool routing |
# MAGIC
# MAGIC **When to change tools instead of the prompt.** If the eval shows the agent routing an
# MAGIC aggregation to a UC function (or vice versa), the fix is a clearer tool **description** in Unity
# MAGIC Catalog or Genie — the description is the LLM's decision surface. Prompt tweaks handle wording
# MAGIC and format; tool-description tweaks handle *which tool fires*.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Closing the loop
# MAGIC ```
# MAGIC  Build → Evaluate → Govern → Deploy → Improve
# MAGIC    ▲                                     │
# MAGIC    └──────────  you are here  ───────────┘
# MAGIC ```
# MAGIC After a prompt/tool change: commit the reviewed golden rows to
# MAGIC `../eval/golden_questions.jsonl`, re-run Lab 02 as the new baseline, redeploy the app (Lab 04),
# MAGIC and keep collecting feedback. The dataset grows with every real failure the app encounters, so
# MAGIC the agent measurably improves over time instead of silently drifting.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 05 complete — IMPROVE ✅ &nbsp;(loop closed)</strong><br>
# MAGIC   You captured thumbs-up/down + corrections into <code>app_feedback.agent_feedback</code>,
# MAGIC   converted negatives into new golden rows, re-ran the Lab 02 evaluation with the in-region PT
# MAGIC   judge to measure the delta, and refined the prompt/tool descriptions. The lifecycle is now a
# MAGIC   cycle: <strong>Build → Evaluate → Govern → Deploy → Improve → Evaluate → ...</strong>
# MAGIC </div>
# MAGIC
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #00843D 100%); color: white; padding: 24px 28px; border-radius: 12px; margin-top: 16px;">
# MAGIC   <h3 style="color: white; margin: 0 0 10px 0;">Session 4 complete — what you built</h3>
# MAGIC   <ul style="color: rgba(255,255,255,0.9); margin: 0; padding-left: 20px; font-size: 0.95em;">
# MAGIC     <li><strong>Build</strong> — LangGraph ReAct agent, 3 MCP servers, Lakebase memory</li>
# MAGIC     <li><strong>Evaluate</strong> — LLM-judge scorers vs a golden dataset (in-region PT judge)</li>
# MAGIC     <li><strong>Govern</strong> — residency block, AI Gateway, guardrails, UC access, audit</li>
# MAGIC     <li><strong>Deploy</strong> — React app in Databricks Apps, SSO + service principal, AU East</li>
# MAGIC     <li><strong>Improve</strong> — feedback → new golden rows → re-eval → refine → redeploy</li>
# MAGIC   </ul>
# MAGIC   <p style="color: rgba(255,255,255,0.85); margin: 12px 0 0 0; font-size: 0.9em;">
# MAGIC     Everything ran in Azure Australia East on an in-region PT endpoint. No cross-geo inference.
# MAGIC   </p>
# MAGIC </div>
