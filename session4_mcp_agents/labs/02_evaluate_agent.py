# Databricks notebook source

# MAGIC %md
# MAGIC <div style="background: linear-gradient(135deg, #1B3A6B 0%, #FF3621 100%); padding: 36px 40px; border-radius: 14px; margin-bottom: 8px;">
# MAGIC   <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2.3em; margin: 0 0 10px 0;">
# MAGIC     Lab 02 — EVALUATE: Measure Agent Quality with LLM Judges
# MAGIC   </h1>
# MAGIC   <p style="color: rgba(255,255,255,0.88); font-size: 1.15em; margin: 0 0 6px 0;">
# MAGIC     Session 4: Building AI Agents with MCP — Australian Energy Sector (Level 200)
# MAGIC   </p>
# MAGIC   <p style="color: rgba(255,255,255,0.70); font-size: 0.95em; margin: 0;">
# MAGIC     Lifecycle phase 2 of 5 &nbsp;•&nbsp; Build → <strong>Evaluate</strong> → Govern → Deploy → Improve
# MAGIC   </p>
# MAGIC </div>
# MAGIC
# MAGIC <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
# MAGIC   <div style="background: #f0f4ff; border-left: 4px solid #1B3A6B; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #1B3A6B;">Estimated time</strong><br>35 minutes
# MAGIC   </div>
# MAGIC   <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #FF3621;">Prerequisites</strong><br>Lab 01 complete
# MAGIC   </div>
# MAGIC   <div style="background: #f0fff4; border-left: 4px solid #00843D; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #00843D;">Data residency</strong><br>Judge = in-region PT ✅
# MAGIC   </div>
# MAGIC   <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; flex: 1; min-width: 160px;">
# MAGIC     <strong style="color: #e65100;">Golden set</strong><br>../eval/golden_questions.jsonl
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you will do
# MAGIC
# MAGIC | # | Section | Topic | Time |
# MAGIC |---|---------|-------|------|
# MAGIC | 1 | Load the golden dataset | Read `../eval/golden_questions.jsonl` into MLflow format | 6 min |
# MAGIC | 2 | Rebuild the agent as a `predict_fn` | Wrap the Lab 01 agent for evaluation | 8 min |
# MAGIC | 3 | Define LLM-judge scorers | Correctness, relevance, groundedness, no-hallucination | 8 min |
# MAGIC | 4 | Run `mlflow.genai.evaluate()` | LLM judges on the in-region PT endpoint | 8 min |
# MAGIC | 5 | Read results + per-question traces | Aggregate metrics and drill into failures | 5 min |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Why evaluate?
# MAGIC An agent that runs is not the same as an agent that is *correct*. Evaluation turns "it seemed
# MAGIC fine" into a number you can track across versions. We use **LLM-as-judge** scorers: a second
# MAGIC model grades each answer against a golden reference. That judge is itself an LLM call, so it
# MAGIC must obey the same residency rule as the agent.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #fff4f0; border-left: 4px solid #FF3621; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #FF3621;">Residency rule</strong><br>
# MAGIC   The judge model is an LLM call and MUST use the in-region <strong>PT endpoint</strong>
# MAGIC   (<code>au_east_llm_inregion</code>), referenced as <code>databricks:/au_east_llm_inregion</code>.
# MAGIC   Do NOT let the judge default to a pay-per-token / cross-geo model.
# MAGIC </div>

# COMMAND ----------

# MAGIC %pip install -q databricks-langchain langgraph "mlflow>=3.0"
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

# The judge model reference — same in-region PT endpoint the agent uses.
JUDGE_MODEL = f"databricks:/{PT_ENDPOINT}"

from databricks.sdk import WorkspaceClient
ws   = WorkspaceClient()
HOST = ws.config.host.rstrip("/")

UC_MCP_URL    = f"{HOST}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA_AEMO}"
GENIE_MCP_URL = f"{HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}" if GENIE_SPACE_ID else None
VS_MCP_URL    = f"{HOST}/api/2.0/mcp/vector-search/{CATALOG}/{SCHEMA_AEMO}/aemo_market_notices_index"

import mlflow
mlflow.set_experiment(MLFLOW_EXPERIMENT)

print("Configuration loaded.")
print(f"  PT endpoint (agent + judge): {PT_ENDPOINT}")
print(f"  Judge model reference      : {JUDGE_MODEL}")
print(f"  MLflow experiment          : {MLFLOW_EXPERIMENT}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 1 — Load the golden dataset (6 min)
# MAGIC </div>
# MAGIC
# MAGIC The golden set lives at `../eval/golden_questions.jsonl`. Each row has `inputs` (the question)
# MAGIC and `expectations` (`expected_facts` + a `reference` answer grounded in the sample tables).

# COMMAND ----------

import json
from pathlib import Path

# Resolve the eval file relative to this notebook (labs/ -> ../eval/).
_candidates = [
    Path("../eval/golden_questions.jsonl"),
    Path.cwd().parent / "eval" / "golden_questions.jsonl",
    Path("/Workspace") / "Repos",  # placeholder; falls through to the working candidate
]
golden_path = next((p for p in _candidates if p.exists()), _candidates[0])

eval_dataset = []
with open(golden_path) as f:
    for line in f:
        line = line.strip()
        if line:
            eval_dataset.append(json.loads(line))

print(f"Loaded {len(eval_dataset)} golden questions from {golden_path}\n")
for i, row in enumerate(eval_dataset[:3], 1):
    print(f"  Q{i}: {row['inputs']['question'][:70]}...")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 2 — Rebuild the agent as a predict_fn (8 min)
# MAGIC </div>
# MAGIC
# MAGIC `mlflow.genai.evaluate()` calls `predict_fn(**inputs)` per row. Our inputs key is `question`,
# MAGIC so the function signature is `predict_fn(question: str)`. It returns the agent's final answer.

# COMMAND ----------

import asyncio
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from databricks_langchain import (
    ChatDatabricks, DatabricksMCPServer, DatabricksMultiServerMCPClient,
)

mlflow.langchain.autolog()

# In-region PT endpoint ONLY.
llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=4096)

AEMO_SYSTEM_PROMPT = """You are the AEMO Operations Assistant for the National Electricity Market.
Use NEM region codes with the '1' suffix (NSW1, VIC1, QLD1, SA1, TAS1). Prices in $/MWh, generation
in MW, settlement in AUD. Market Price Cap = $15,300/MWh; floor = -$1,000/MWh. A price spike is
rrp > $300/MWh. LOR1/2/3 are Lack-Of-Reserve levels. Use Genie for aggregations, UC Functions for
deterministic calculations and lookups, Vector Search for market notices. Cite every claim and add
'Note: workshop dataset, not live NEM conditions.' Never invent numbers."""

uc_server = DatabricksMCPServer(name="aemo-uc-tools", url=UC_MCP_URL, timeout=30.0, handle_tool_error=True)
vs_server = DatabricksMCPServer(name="aemo-market-notices", url=VS_MCP_URL, timeout=30.0, handle_tool_error=True)
all_servers = [uc_server, vs_server]
if GENIE_MCP_URL:
    all_servers.append(DatabricksMCPServer(name="aemo-nem-genie", url=GENIE_MCP_URL, timeout=60.0, handle_tool_error=True))


async def _answer(question: str) -> str:
    async with DatabricksMultiServerMCPClient(all_servers) as client:
        tools = await client.get_tools()
        agent = create_react_agent(model=llm, tools=tools, prompt=AEMO_SYSTEM_PROMPT)
        result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content


@mlflow.trace
def predict_fn(question: str) -> str:
    """Evaluation entry point — one AEMO question in, final answer out."""
    return asyncio.run(_answer(question))


# Smoke-test one row before the full run.
print(predict_fn(eval_dataset[0]["inputs"]["question"]))

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 3 — Define LLM-judge scorers (8 min)
# MAGIC </div>
# MAGIC
# MAGIC | Scorer | What it checks | Needs |
# MAGIC |--------|----------------|-------|
# MAGIC | **Correctness** | Answer matches the golden `expected_facts` | `expectations.expected_facts` |
# MAGIC | **RelevanceToQuery** | Answer actually addresses the question (answer quality) | — |
# MAGIC | **RetrievalGroundedness** | Claims are grounded in retrieved tool output (not made up) | RETRIEVER/tool span |
# MAGIC | **no_hallucination** (Guidelines) | Faithfulness: no invented numbers, cites sources, adds the workshop disclaimer | — |
# MAGIC
# MAGIC Every scorer is an LLM call — each is pinned to the in-region PT endpoint via `model=JUDGE_MODEL`.

# COMMAND ----------

from mlflow.genai.scorers import (
    Correctness, RelevanceToQuery, RetrievalGroundedness, Guidelines,
)

correctness = Correctness(model=JUDGE_MODEL)
relevance   = RelevanceToQuery(model=JUDGE_MODEL)
groundedness = RetrievalGroundedness(model=JUDGE_MODEL)

# A faithfulness / no-hallucination judge expressed as natural-language guidelines.
no_hallucination = Guidelines(
    name="no_hallucination",
    guidelines=(
        "The response must NOT invent or estimate numeric values. Every quantitative claim "
        "(prices in $/MWh, demand in MW, settlement in AUD, interval counts) must be attributable "
        "to a tool result, and the response must cite its source. The response must use NEM region "
        "codes with the '1' suffix (e.g. VIC1, not VIC). If the response could not retrieve data, it "
        "must say so rather than fabricate an answer. The response should include the note that this "
        "reflects the workshop dataset and not live NEM conditions."
    ),
    model=JUDGE_MODEL,
)

scorers = [correctness, relevance, groundedness, no_hallucination]
print("Judge scorers ready (all pinned to in-region PT):")
for s in scorers:
    print(f"  {s.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 4 — Run the evaluation (8 min)
# MAGIC </div>
# MAGIC
# MAGIC `mlflow.genai.evaluate()` runs `predict_fn` on every golden row, traces each call, then applies
# MAGIC the judges. This produces one evaluation run with aggregate metrics + a per-question trace.

# COMMAND ----------

with mlflow.start_run(run_name="lab02_eval_baseline") as run:
    results = mlflow.genai.evaluate(
        data=eval_dataset,
        predict_fn=predict_fn,
        scorers=scorers,
    )

print("Evaluation complete.")
print(f"  Run ID : {results.run_id}")
print("\nAggregate metrics:")
for name, value in sorted(results.metrics.items()):
    print(f"  {name:45s} {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #fffbf0; border-left: 4px solid #f9a825; padding: 12px 18px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #e65100;">Note on the judge API</strong><br>
# MAGIC   This lab uses <code>mlflow.genai.evaluate()</code> with the built-in scorers from
# MAGIC   <code>mlflow.genai.scorers</code> (MLflow 3). If your workspace pins an older MLflow, the
# MAGIC   equivalent is <code>mlflow.evaluate(..., model_type="databricks-agent")</code>. Confirm the
# MAGIC   installed MLflow version and adjust imports during integration if needed.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background: #1B3A6B; color: white; padding: 10px 18px; border-radius: 6px; font-size: 1.05em; font-weight: bold; margin: 16px 0 4px 0;">
# MAGIC   Section 5 — Read results and per-question traces (5 min)
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.1 — Open the eval run in the UI
# MAGIC ```
# MAGIC Machine Learning → Experiments → /Shared/session4-aemo-agent
# MAGIC   → Runs tab → lab02_eval_baseline → Evaluation tab
# MAGIC ```
# MAGIC The Evaluation tab shows one row per golden question with each judge's score and rationale.
# MAGIC Click a row to open the full trace: the tool calls, the tool outputs, and the final answer the
# MAGIC judge graded.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.2 — Pull per-question results programmatically

# COMMAND ----------

eval_df = mlflow.search_traces(run_id=results.run_id)
print(f"Traces in this eval run: {len(eval_df)}\n")

# Surface the assessment (judge) columns per question.
assessment_cols = [c for c in eval_df.columns if "assessment" in c.lower() or c in ("request", "response")]
if assessment_cols:
    try:
        print(eval_df[assessment_cols].head(10).to_string())
    except Exception:
        print(eval_df.head(10).to_string())
else:
    print(eval_df.head(10).to_string())

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.3 — Find the lowest-scoring questions to fix later
# MAGIC These become the raw material for Lab 05 (IMPROVE) — negatives get turned into new golden rows.

# COMMAND ----------

# The correctness assessment column name is typically 'assessments.correctness' or similar;
# search flexibly so this works across MLflow point releases.
corr_col = next((c for c in eval_df.columns if "correctness" in c.lower()), None)

if corr_col:
    try:
        weakest = eval_df.sort_values(corr_col).head(3)
        print(f"Lowest-correctness questions (by {corr_col}):\n")
        for _, r in weakest.iterrows():
            req = r.get("request", "")
            print(f"  score={r[corr_col]}  |  {str(req)[:70]}")
    except Exception as e:
        print(f"Could not rank (schema varies by version): {e}")
        print("Inspect the Evaluation tab in the UI instead.")
else:
    print("Correctness column not found in this MLflow version — use the Evaluation tab UI.")
    print("Available columns:", list(eval_df.columns))

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC <div style="background: #e8f5e9; border-left: 4px solid #00843D; padding: 14px 20px; border-radius: 6px; margin: 8px 0;">
# MAGIC   <strong style="color: #00843D;">Lab 02 complete — EVALUATE ✅</strong><br>
# MAGIC   You scored the agent against a golden dataset with four LLM-judge metrics — correctness,
# MAGIC   relevance, groundedness, and a no-hallucination faithfulness check — all judged by the
# MAGIC   in-region PT endpoint. You captured a baseline (<code>lab02_eval_baseline</code>) to compare
# MAGIC   against later.
# MAGIC   <br><br>
# MAGIC   <strong>Next — Lab 03 (GOVERN):</strong> put guardrails, rate limits, access controls, and an
# MAGIC   audit trail around the agent before anyone else can use it.
# MAGIC </div>
