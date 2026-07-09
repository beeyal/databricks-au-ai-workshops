# AEMO NEM Operations Agent — Databricks App

A polished React + TypeScript chat application for the AEMO Operations Agent
(Level-200 agent-building workshop). It replaces the earlier Gradio app. The
agent is a LangGraph ReAct agent backed by Databricks MCP servers (UC
Functions, optional Genie, Vector Search) and served through a FastAPI backend.

## Data residency (hard rule)

The model is **always** an in-region (Australia East) provisioned-throughput
(PT) serving endpoint — never pay-per-token / cross-geo. The UI shows an
"Australia East · in-region (PT endpoint)" badge and the backend reports
`region: australiaeast` on `/api/health`.

## Structure

```
session4_mcp_agents/app/
├── agent.py            # build_agent() + astream_answer() — importable agent module
├── server.py           # FastAPI: /api/chat (SSE), /api/health, static SPA serving
├── app.yaml            # Databricks App manifest (command, env, serving-endpoint resource)
├── requirements.txt    # Python deps
├── static/             # Built SPA (produced by `npm run build`) — served by server.py
└── frontend/           # React + TypeScript + Vite source
    ├── package.json
    ├── vite.config.ts  # build.outDir → ../static
    ├── index.html
    └── src/
        ├── App.tsx, main.tsx, useChat.ts, types.ts, styles.css
        └── components/  Header, MessageBubble, ToolIndicator, SourcesPanel, Examples
```

### Backend contract

- **`agent.py`**
  - `build_agent()` (async) — builds MCP servers (UC always; Genie only if
    `GENIE_SPACE_ID`; Vector Search) via `DatabricksMultiServerMCPClient`,
    discovers tools, and returns `create_react_agent(ChatDatabricks(PT_ENDPOINT), tools, ...)`.
  - `astream_answer(message, history)` (async generator) — yields structured
    events: `{"type":"tool_call","name":...}`, `{"type":"token","text":...}`,
    `{"type":"final","content":...,"sources":[...]}`. Sources are derived
    best-effort from Vector Search / Genie tool results.
  - MLflow tracing via `mlflow.langchain.autolog()` (guarded in try/except).
- **`server.py`**
  - `POST /api/chat` `{message, session_id}` → SSE stream of the agent events.
    Loads prior turns for the session from memory before invoking, persists the
    new turn after.
  - `GET /api/health` → `{status, pt_endpoint, region:"australiaeast", genie_enabled, lakebase_enabled}`.
  - Conversation memory in **Lakebase** (Postgres) via `psycopg`, with an
    in-memory dict fallback. All Postgres access is guarded; a Lakebase failure
    never breaks chat. Table: `app_memory.conversation_turns(session_id, turn_index, role, content, ts)`.
  - Serves the built SPA from `static/` with SPA fallback to `index.html`; if
    `static/` is missing it serves a placeholder telling you to build the frontend.
  - Listens on `DATABRICKS_APP_PORT` (default 8080), host `0.0.0.0`.

### Environment variables (defaults)

| Var | Default | Notes |
| --- | --- | --- |
| `PT_ENDPOINT` | `au_east_llm_inregion` | In-region PT serving endpoint |
| `CATALOG` | `workshop_au` | |
| `SCHEMA_AEMO` | `aemo` | |
| `VS_ENDPOINT` | `workshop_vs` | Vector Search endpoint name |
| `VS_INDEX` | `workshop_au.aemo.aemo_market_notices_index` | 3-part index name; overrides the constructed default |
| `GENIE_SPACE_ID` | *(empty)* | Optional; Genie MCP attached only when set |
| `DATABRICKS_HOST` | *(auto in Apps)* | Resolved via the SDK if unset |

## Build the frontend

> **IMPORTANT — `static/` is NOT committed / NOT built.** The build environment
> had no reachable npm registry (both `npm-proxy.cloud.databricks.com` and
> `registry.npmjs.org` timed out), so `npm install` / `npm run build` could not
> run here. You MUST run the build during integration to produce `static/`;
> until then `server.py` serves a placeholder page. The TypeScript source is
> complete and was reviewed for type-correctness by inspection (`tsc` was not
> runnable without dependencies).

Node/npm required.

```bash
cd session4_mcp_agents/app/frontend
npm install
npm run build          # type-checks, then writes the bundle to ../static/
```

This produces `session4_mcp_agents/app/static/index.html` and `static/assets/*`.
`server.py` serves that directory. If `static/` is absent, the server returns a
placeholder page.

## Run locally

```bash
cd session4_mcp_agents/app
pip install -r requirements.txt
python server.py       # http://localhost:8080
```

Auth resolves via the Databricks SDK: a CLI profile / token locally, the app
service principal (injected OAuth) in the Apps runtime.

## Deploy as a Databricks App

1. Build the frontend so `static/` exists (see above), commit it.
2. Create a Databricks App (Custom) and point it at `session4_mcp_agents/app/`.
   `app.yaml` declares `command: ["python","server.py"]`, the env block, and the
   `au_east_llm_inregion` serving endpoint with `CAN_QUERY`.
3. After deploy, set `GENIE_SPACE_ID` in the app's Environment tab if you want
   the Genie tool. Grant the app service principal `EXECUTE` on the UC schema
   and `CAN_QUERY` on the PT endpoint.
4. (Optional) To enable Lakebase-backed conversation memory, attach a Lakebase
   database and provide the connection via `PGHOST`/`PGPORT`/`PGDATABASE`/
   `PGUSER`/`PGPASSWORD` (or the `DATABRICKS_LAKEBASE_*` equivalents). Without
   these the app uses an in-memory store.

## Notes / things to verify during integration

- **Vector Search MCP URL**: built as
  `{HOST}/api/2.0/mcp/vector-search/{catalog}/{schema}/{index}` from `VS_INDEX`
  (default `workshop_au.aemo.aemo_market_notices_index`), matching the workshop
  labs. Confirm the actual index name and override `VS_INDEX` if it differs.
- **Lakebase connection specifics**: env-var names and the exact conninfo
  (sslmode, OAuth token vs password) may need adjusting for your Lakebase
  instance. The code degrades to in-memory automatically if it cannot connect.
- The existing root `session4_mcp_agents/app.py` / `app.yaml` (Gradio) are left
  in place for you to remove during integration.
