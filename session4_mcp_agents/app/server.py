"""server.py — FastAPI backend for the AEMO NEM Operations Agent.

Responsibilities:
  * Serve the built React SPA from ./static (SPA fallback to index.html).
  * POST /api/chat  — SSE stream of agent events for one user turn.
  * GET  /api/health — status + config summary.
  * Conversation memory in Lakebase (Postgres) with an in-memory fallback.

Data residency: the LLM is a provisioned-throughput endpoint in Australia East.
Never pay-per-token / cross-geo.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent as agent_module

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")

PORT = int(os.environ.get("DATABRICKS_APP_PORT", "8080"))


# ---------------------------------------------------------------------------
# Lakebase (Postgres) conversation memory, with in-memory fallback.
# All Postgres access is guarded; a Lakebase failure NEVER breaks chat.
# ---------------------------------------------------------------------------
_MEM_TABLE = "app_memory.conversation_turns"
_INMEM: Dict[str, List[Dict[str, str]]] = {}

PG_ENABLED = False
_PG_CONNINFO = None


def _resolve_pg_conninfo():
    """Resolve a Postgres conninfo from Lakebase / standard PG env vars.

    Returns a conninfo string, or None if no connection is resolvable.
    """
    # Standard libpq vars.
    host = (
        os.environ.get("PGHOST")
        or os.environ.get("DATABRICKS_LAKEBASE_HOST")
        or os.environ.get("LAKEBASE_HOST")
    )
    if not host:
        return None
    port = os.environ.get("PGPORT") or os.environ.get("DATABRICKS_LAKEBASE_PORT") or "5432"
    dbname = (
        os.environ.get("PGDATABASE")
        or os.environ.get("DATABRICKS_LAKEBASE_DATABASE")
        or os.environ.get("LAKEBASE_DATABASE")
        or "databricks_postgres"
    )
    user = (
        os.environ.get("PGUSER")
        or os.environ.get("DATABRICKS_LAKEBASE_USER")
        or os.environ.get("LAKEBASE_USER")
    )
    password = (
        os.environ.get("PGPASSWORD")
        or os.environ.get("DATABRICKS_LAKEBASE_PASSWORD")
        or os.environ.get("LAKEBASE_PASSWORD")
    )
    parts = [f"host={host}", f"port={port}", f"dbname={dbname}", "sslmode=require"]
    if user:
        parts.append(f"user={user}")
    if password:
        parts.append(f"password={password}")
    return " ".join(parts)


def _pg_connect():
    import psycopg

    return psycopg.connect(_PG_CONNINFO, connect_timeout=5)


def _init_lakebase() -> None:
    """Probe Lakebase and create the memory table if reachable."""
    global PG_ENABLED, _PG_CONNINFO
    _PG_CONNINFO = _resolve_pg_conninfo()
    if not _PG_CONNINFO:
        PG_ENABLED = False
        return
    try:
        import psycopg  # noqa: F401

        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS app_memory")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {_MEM_TABLE} (
                        session_id  text,
                        turn_index  int,
                        role        text,
                        content     text,
                        ts          timestamptz
                    )
                    """
                )
            conn.commit()
        PG_ENABLED = True
    except Exception as exc:  # pragma: no cover - fall back silently
        print(f"[lakebase] disabled, using in-memory store: {exc}")
        PG_ENABLED = False


def load_history(session_id: str) -> List[Dict[str, str]]:
    """Return prior turns [{role, content}, ...] ordered by turn_index."""
    if PG_ENABLED:
        try:
            with _pg_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT role, content FROM {_MEM_TABLE} "
                        "WHERE session_id = %s ORDER BY turn_index ASC",
                        (session_id,),
                    )
                    return [{"role": r, "content": c} for (r, c) in cur.fetchall()]
        except Exception as exc:  # pragma: no cover
            print(f"[lakebase] load failed, using in-memory: {exc}")
    return list(_INMEM.get(session_id, []))


def save_turn(session_id: str, role: str, content: str) -> None:
    """Append one turn to the session's history."""
    existing = _INMEM.setdefault(session_id, [])
    turn_index = len(existing)
    existing.append({"role": role, "content": content})

    if PG_ENABLED:
        try:
            with _pg_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {_MEM_TABLE} "
                        "(session_id, turn_index, role, content, ts) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (
                            session_id,
                            turn_index,
                            role,
                            content,
                            datetime.now(timezone.utc),
                        ),
                    )
                conn.commit()
        except Exception as exc:  # pragma: no cover
            print(f"[lakebase] save failed (kept in-memory): {exc}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AEMO NEM Operations Agent")


@app.on_event("startup")
def _on_startup() -> None:
    _init_lakebase()


class ChatBody(BaseModel):
    message: str
    session_id: str = "default"


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.post("/api/chat")
async def chat(body: ChatBody):
    """Stream agent events for one user turn as Server-Sent Events."""
    session_id = body.session_id or "default"
    message = body.message or ""

    history = load_history(session_id)
    save_turn(session_id, "user", message)

    async def event_stream():
        final_content = ""
        try:
            async for ev in agent_module.astream_answer(message, history):
                if ev.get("type") == "final":
                    final_content = ev.get("content", "")
                yield _sse(ev)
        except Exception as exc:  # pragma: no cover
            yield _sse({"type": "token", "text": f"Server error: {exc}"})
            yield _sse({"type": "final", "content": f"Server error: {exc}", "sources": []})
        finally:
            if final_content:
                save_turn(session_id, "assistant", final_content)
            yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
def health():
    return JSONResponse(
        {
            "status": "ok",
            "pt_endpoint": agent_module.PT_ENDPOINT,
            "region": "australiaeast",
            "genie_enabled": agent_module.is_genie_enabled(),
            "lakebase_enabled": PG_ENABLED,
        }
    )


# ---------------------------------------------------------------------------
# Static SPA serving (mounted last so /api/* wins)
# ---------------------------------------------------------------------------
_PLACEHOLDER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>AEMO Operations Agent</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 640px; margin: 80px auto; padding: 0 24px; color: #1B3A6B;">
<h1>AEMO NEM Operations Agent</h1>
<p>The React frontend has not been built yet.</p>
<p>Build it with:</p>
<pre style="background:#f4f6fa; padding:16px; border-radius:8px;">cd session4_mcp_agents/app/frontend
npm install
npm run build</pre>
<p>This produces <code>session4_mcp_agents/app/static/index.html</code>, which this server will then serve.</p>
<p><em>Australia East · in-region (PT endpoint)</em></p>
</body></html>
"""


if os.path.isdir(STATIC_DIR) and os.path.isfile(INDEX_HTML):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def _index():
        return FileResponse(INDEX_HTML)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str):
        # Serve real static files if they exist, else fall back to index.html.
        candidate = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(INDEX_HTML)

else:

    @app.get("/", include_in_schema=False)
    def _placeholder():
        return HTMLResponse(_PLACEHOLDER_HTML)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
