"""agent.py — AEMO NEM Operations Agent (importable module).

Builds a LangGraph ReAct agent backed by Databricks MCP servers:
  * UC Functions MCP   (always)
  * Genie MCP          (only if GENIE_SPACE_ID is configured)
  * Vector Search MCP  (market notices index)

The model is ALWAYS an in-region (Australia East) provisioned-throughput (PT)
serving endpoint — NEVER pay-per-token / cross-geo. This is a hard data
residency requirement for the AEMO workshop.

Auth:
  * In the Databricks Apps runtime the app authenticates as its service
    principal via the Databricks SDK (WorkspaceClient injects OAuth).
  * Locally, the SDK falls back to a Databricks CLI profile / token.
  * ChatDatabricks(endpoint=PT_ENDPOINT) and the MCP server classes pick up
    SDK auth automatically.
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration — read from Databricks Apps environment variables
# ---------------------------------------------------------------------------
PT_ENDPOINT = os.environ.get("PT_ENDPOINT", "au_east_llm_inregion")
CATALOG = os.environ.get("CATALOG", "workshop_au")
SCHEMA_AEMO = os.environ.get("SCHEMA_AEMO", "aemo")
VS_ENDPOINT = os.environ.get("VS_ENDPOINT", "workshop_vs")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "").strip()

# The Vector Search MCP URL is built from a 3-part index name
# (catalog.schema.index). By default we assume the workshop market-notices
# index; make it overridable via VS_INDEX in case the naming differs.
VS_INDEX = os.environ.get(
    "VS_INDEX", f"{CATALOG}.{SCHEMA_AEMO}.aemo_market_notices_index"
).strip()

# ---------------------------------------------------------------------------
# MLflow tracing — guarded so a missing/misconfigured MLflow never breaks chat
# ---------------------------------------------------------------------------
try:  # pragma: no cover - best effort
    import mlflow

    mlflow.langchain.autolog()
    _experiment = os.environ.get(
        "MLFLOW_EXPERIMENT", "/Shared/aemo-operations-agent"
    )
    try:
        mlflow.set_experiment(_experiment)
    except Exception:
        pass
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Host resolution (SDK auto-auth in Apps; CLI token locally)
# ---------------------------------------------------------------------------
def _resolve_host() -> str:
    host = os.environ.get("DATABRICKS_HOST", "").strip()
    if host:
        return host.rstrip("/")
    try:
        from databricks.sdk import WorkspaceClient

        return WorkspaceClient().config.host.rstrip("/")
    except Exception:
        return ""


AEMO_SYSTEM_PROMPT = """You are the AEMO NEM Operations Assistant, a technical AI agent for the \
National Electricity Market (NEM) operated by the Australian Energy Market Operator (AEMO).

Your users are NEM market participants (generators, retailers) and AEMO operations staff. \
You answer questions about NEM dispatch intervals, spot prices, market notices, settlements, \
and generation unit status.

## Domain rules
- Always use NEM region codes: NSW1, VIC1, QLD1, SA1, TAS1
- Express prices in $/MWh; generation in MW; energy in MWh
- Market Price Cap (MPC) = $14,000/MWh (hard ceiling on any dispatch interval)
- "Price spike" = spot price > $300/MWh
- LOR1/LOR2/LOR3 = Lack of Reserve conditions (LOR3 = load shedding imminent)
- "Yesterday" = the most recent complete day in the dataset

## Tool selection guidance
- Use the Genie tool for trends, averages, totals over a time window, and
  "how many / what was the average / show me all intervals where..." questions.
- Use the UC Function tools for specific region+date calculations and DUID lookups.
- Use Vector Search for market notices, LOR events, and AEMO bulletins.

## Behaviour
- Before presenting results, briefly explain which tool you used and why.
- Cite the source of every factual claim (Genie / the UC function name / the market notice ID).
- If a tool call fails, explain what you tried and why it failed. Never make up or estimate numbers.
- Refuse questions outside the NEM / AEMO operations domain and steer the user back to it.

## Data residency
All data is served from Australia East, in-region, via a provisioned-throughput endpoint. \
Data residency is maintained (AU East). Add: "Note: This data reflects the workshop dataset \
and may not represent live NEM conditions."
"""


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------
async def build_agent():
    """Construct MCP servers and return a compiled LangGraph ReAct agent.

    UC Functions MCP is always attached. Genie MCP is attached only when
    GENIE_SPACE_ID is set. Vector Search MCP is attached for the market
    notices index.
    """
    from databricks_langchain import (
        ChatDatabricks,
        DatabricksMCPServer,
        DatabricksMultiServerMCPClient,
    )
    from langgraph.prebuilt import create_react_agent

    host = _resolve_host()

    uc_server = DatabricksMCPServer.from_uc_function(
        catalog=CATALOG,
        schema=SCHEMA_AEMO,
        name="aemo-uc-tools",
    )

    servers = [uc_server]

    if GENIE_SPACE_ID:
        servers.append(
            DatabricksMCPServer(
                name="aemo-nem-genie",
                url=f"{host}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
            )
        )

    vs_parts = VS_INDEX.split(".")
    vs_url = f"{host}/api/2.0/mcp/vector-search/{'/'.join(vs_parts)}"
    servers.append(
        DatabricksMCPServer(
            name="aemo-market-notices",
            url=vs_url,
        )
    )

    client = DatabricksMultiServerMCPClient(servers)
    tools = await client.get_tools()

    llm = ChatDatabricks(endpoint=PT_ENDPOINT, temperature=0.0, max_tokens=4096)

    agent = create_react_agent(model=llm, tools=tools, prompt=AEMO_SYSTEM_PROMPT)
    # Keep the client handle alive alongside the agent so MCP connections
    # persist for the lifetime of the agent (Apps reuses one agent instance).
    agent._mcp_client = client  # type: ignore[attr-defined]
    return agent


def is_genie_enabled() -> bool:
    return bool(GENIE_SPACE_ID)


# ---------------------------------------------------------------------------
# Helpers for streaming
# ---------------------------------------------------------------------------
_SOURCE_TOOL_HINTS = ("search", "vector", "genie", "notice")


def _looks_like_source_tool(name: str) -> bool:
    lname = (name or "").lower()
    return any(hint in lname for hint in _SOURCE_TOOL_HINTS)


def _extract_sources(tool_name: str, content: Any) -> List[Dict[str, str]]:
    """Best-effort extraction of citation-style sources from a tool result.

    Vector Search / Genie tool payloads vary; we try JSON first, then fall
    back to treating the raw text as a single source snippet.
    """
    sources: List[Dict[str, str]] = []
    text = content if isinstance(content, str) else str(content)

    parsed: Any = None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None

    def _add(title: str, snippet: str) -> None:
        snippet = (snippet or "").strip()
        if not snippet:
            return
        sources.append(
            {
                "tool": tool_name,
                "title": (title or tool_name)[:200],
                "snippet": snippet[:500],
            }
        )

    if isinstance(parsed, dict):
        rows = (
            parsed.get("result")
            or parsed.get("results")
            or parsed.get("data")
            or parsed.get("rows")
        )
        if isinstance(rows, list):
            for row in rows[:5]:
                if isinstance(row, dict):
                    title = str(
                        row.get("notice_id")
                        or row.get("id")
                        or row.get("title")
                        or tool_name
                    )
                    snippet = str(
                        row.get("text")
                        or row.get("content")
                        or row.get("notice_text")
                        or json.dumps(row)
                    )
                    _add(title, snippet)
                else:
                    _add(tool_name, str(row))
        else:
            _add(tool_name, text)
    elif isinstance(parsed, list):
        for row in parsed[:5]:
            _add(tool_name, json.dumps(row) if not isinstance(row, str) else row)
    else:
        _add(tool_name, text)

    return sources


def _message_text(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


def _history_to_messages(history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = []
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    return msgs


# ---------------------------------------------------------------------------
# Streaming answer generator
# ---------------------------------------------------------------------------
async def astream_answer(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield structured streaming events for a single user turn.

    Event shapes:
      {"type": "tool_call", "name": <str>}
      {"type": "token", "text": <str>}
      {"type": "final", "content": <str>, "sources": [ {tool,title,snippet} ]}

    Sources are derived best-effort from Vector Search / Genie tool results.
    """
    agent = await build_agent()

    input_messages = _history_to_messages(history)
    input_messages.append({"role": "user", "content": message})

    sources: List[Dict[str, str]] = []
    final_text = ""
    streamed_any_token = False
    announced_tools: set = set()

    try:
        # stream_mode "messages" yields (message_chunk, metadata) tuples with
        # token-level deltas; "updates" yields node outputs (tool results).
        async for stream_mode, chunk in agent.astream(
            {"messages": input_messages},
            stream_mode=["messages", "updates"],
        ):
            if stream_mode == "messages":
                msg_chunk, _meta = chunk
                # Announce tool calls as they are decided by the model.
                tool_calls = getattr(msg_chunk, "tool_calls", None) or []
                for tc in tool_calls:
                    name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if name and name not in announced_tools:
                        announced_tools.add(name)
                        yield {"type": "tool_call", "name": name}

                text = _message_text(msg_chunk)
                # Only stream assistant text (skip tool messages).
                msg_type = getattr(msg_chunk, "type", "")
                if text and msg_type in ("ai", "AIMessageChunk", ""):
                    streamed_any_token = True
                    final_text += text
                    yield {"type": "token", "text": text}

            elif stream_mode == "updates":
                for node_name, node_out in (chunk or {}).items():
                    msgs = (node_out or {}).get("messages", []) if isinstance(node_out, dict) else []
                    for m in msgs:
                        m_type = getattr(m, "type", "")
                        name = getattr(m, "name", "") or node_name
                        # Tool result messages carry retrieval payloads.
                        if m_type == "tool" or node_name == "tools":
                            if name and name not in announced_tools:
                                announced_tools.add(name)
                                yield {"type": "tool_call", "name": name}
                            if _looks_like_source_tool(name):
                                sources.extend(_extract_sources(name, getattr(m, "content", "")))
                        # Final assistant message (fallback if no token stream).
                        elif m_type == "ai":
                            txt = _message_text(m)
                            if txt:
                                final_text = txt
    except Exception as exc:  # pragma: no cover - surfaced to the client
        err = f"The agent hit an error while answering: {exc}"
        if not streamed_any_token:
            yield {"type": "token", "text": err}
            final_text = err
        else:
            final_text += f"\n\n{err}"

    # De-duplicate sources by (title, snippet).
    seen = set()
    deduped: List[Dict[str, str]] = []
    for s in sources:
        key = (s.get("title"), s.get("snippet"))
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    yield {"type": "final", "content": final_text, "sources": deduped}
