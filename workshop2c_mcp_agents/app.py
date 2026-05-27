# app.py — AEMO Operations Agent UI
# Databricks Apps entry point
# Deploy via: Apps → Create app → Custom → point to this folder

import gradio as gr
import asyncio
import os

from databricks_langchain import (
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
    ChatDatabricks,
)
from langgraph.prebuilt import create_react_agent
import mlflow

# ---------------------------------------------------------------------------
# Configuration — read from Databricks Apps environment variables
# ---------------------------------------------------------------------------
# These are set in app.yaml (env: block) or via the UI Resources/Environment tab.
# Local defaults below are only for testing outside Apps.

PT_ENDPOINT    = os.environ.get("PT_ENDPOINT",    "au_east_llm_inregion")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
WORKSPACE_URL  = os.environ.get("DATABRICKS_HOST",  "").rstrip("/")
CATALOG        = os.environ.get("CATALOG",        "workshop_au")
SCHEMA_AEMO    = os.environ.get("SCHEMA_AEMO",    "aemo")

# MLflow experiment for tracing — all agent calls will appear here
mlflow.set_experiment("/Apps/aemo-operations-agent")

# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------

async def build_agent():
    """
    Build a LangGraph ReAct agent backed by MCP servers.

    Called on each chat message in this workshop implementation.
    In production: call this once at module load and reuse the agent object.
    Pattern:  _agent = None  ->  initialise lazily in an async startup hook.
    """
    servers = [
        DatabricksMCPServer.from_uc_function(
            catalog=CATALOG,
            schema=SCHEMA_AEMO,
            name="aemo-uc-tools",
        ),
    ]

    # Add Genie Space MCP server only if a Space ID is configured
    if GENIE_SPACE_ID:
        servers.append(
            DatabricksMCPServer(
                name="aemo-genie",
                url=f"{WORKSPACE_URL}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            )
        )

    client = DatabricksMultiServerMCPClient(servers)
    tools  = await client.get_tools()
    llm    = ChatDatabricks(endpoint=PT_ENDPOINT)

    system_prompt = (
        "You are the AEMO NEM Operations Assistant. "
        "You help operations staff and analysts answer questions about "
        "NEM dispatch intervals, spot prices, market notices, settlements, "
        "and generation unit status. "
        "When you use a tool, briefly explain what you looked up before "
        "presenting results. "
        "All data is from Australia East — data residency is maintained."
    )

    return create_react_agent(
        llm,
        tools,
        state_modifier=system_prompt,
    )


# ---------------------------------------------------------------------------
# Gradio chat handler
# ---------------------------------------------------------------------------

def chat(message: str, history: list) -> str:
    """
    Synchronous wrapper around the async agent.
    Gradio's ChatInterface calls this function on every user message.

    history: list of [user_msg, assistant_msg] pairs (Gradio format)
    Returns:  assistant response as a plain string
    """

    async def run():
        agent  = await build_agent()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]}
        )
        return result["messages"][-1].content

    return asyncio.run(run())


# ---------------------------------------------------------------------------
# Gradio interface definition
# ---------------------------------------------------------------------------

demo = gr.ChatInterface(
    fn=chat,
    title="⚡ AEMO NEM Operations Assistant",
    description=(
        "Ask questions about NEM dispatch intervals, spot prices, market notices, "
        "settlements, and generation unit status. "
        "All data is processed in **Australia East** — SOCI Act / critical infrastructure data residency maintained."
    ),
    examples=[
        "What was the average spot price in VIC yesterday?",
        "Which generators dispatched the most in NSW last week?",
        "Were there any LOR1 or LOR2 events this week?",
        "Show me the five highest 5-minute dispatch prices across all regions this month.",
    ],
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="orange",
    ),
    retry_btn="Retry",
    undo_btn="Undo last turn",
    clear_btn="Clear conversation",
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Databricks Apps expects the server on port 8080
    # server_name="0.0.0.0" required so the Apps proxy can reach it
    demo.launch(
        server_name="0.0.0.0",
        server_port=8080,
        show_error=True,      # surface Python tracebacks in the UI during dev
    )
