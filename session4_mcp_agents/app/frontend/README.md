# AEMO NEM Operations Agent — Frontend

React + TypeScript + Vite single-page app for the AEMO NEM Operations Agent.

## Build

```bash
cd session4_mcp_agents/app/frontend
npm install
npm run build
```

`npm run build` type-checks (`tsc`) then bundles with Vite, writing the output
to `../static/` (see `vite.config.ts` → `build.outDir`). The FastAPI backend
(`server.py`) serves that `static/` directory. **The `static/` directory must
exist for the deployed app to serve the UI** — if it is missing, the server
shows a placeholder page telling you to run `npm run build`.

## Local development

```bash
# Terminal 1 — backend
cd session4_mcp_agents/app
python server.py           # http://localhost:8080

# Terminal 2 — frontend with hot reload
cd session4_mcp_agents/app/frontend
npm run dev                # http://localhost:5173, proxies /api → :8080
```

## Type-check only

```bash
npm run typecheck          # tsc --noEmit
```

## Structure

- `src/App.tsx` — layout, composer, health probe, example wiring
- `src/useChat.ts` — POSTs to `/api/chat`, parses the SSE stream into events
- `src/types.ts` — shared types and the SSE `AgentEvent` union
- `src/components/` — `Header`, `MessageBubble`, `ToolIndicator`,
  `SourcesPanel`, `Examples`
