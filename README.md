# Argus — AI Research Copilot

> "Your sellers run the conversation. We do everything else."

**What it is.** Argus researches a target company and turns the result into a
structured sales briefing. You create a research session, watch a six-node
LangGraph workflow execute live, read a nine-section report with cited sources,
and then chat with that report as grounded context — every answer cites the
sources it used. Built on Next.js + FastAPI + LangGraph + MongoDB.

## Live demo

**Deployed app:** [https://main.dnpq3ypn7esgf.amplifyapp.com](https://main.dnpq3ypn7esgf.amplifyapp.com)

The flow end-to-end: **New session → Run → live Progress → Report → Chat.**

---

## Quickstart

A fresh clone reaches a working app in well under 10 minutes.

### Prerequisites


| Tool                             | Version | Notes                                                  |
| -------------------------------- | ------- | ------------------------------------------------------ |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.5   | Python dependency manager (can install Python for you) |
| Python                           | ≥ 3.12  |                                                        |
| [Node.js](https://nodejs.org)    | ≥ 20    |                                                        |
| [pnpm](https://pnpm.io)          | ≥ 10    | `corepack enable`                                      |
| MongoDB                          | ≥ 7     | local **or** Docker (below) — or a free Atlas cluster  |


### 1. Clone & configure

```bash
git clone https://github.com/heeranshgithub/argus argus && cd argus
cp backend/.env.example backend/.env          
cp frontend/.env.local.example frontend/.env.local
```

### 2. Start MongoDB

```bash
docker run -d --name argus-mongo -p 27017:27017 mongo:7
```

Or connect to a free [MongoDB Atlas](https://www.mongodb.com/atlas) cluster — set `MONGO_URI` in `backend/.env` to your Atlas connection string.

### 3. Install dependencies

```bash
cd backend && uv sync && cd ..
cd frontend && pnpm install && cd ..
```

### 4. Run both apps

```bash
# Terminal 1 — backend
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 — frontend
cd frontend
pnpm dev --port 3000
```

- Backend → [http://localhost:8000](http://localhost:8000) — `GET /api/health` → `{ "status": "ok", "mongo": "ok", "openrouter": "…" }`
- Frontend → [http://localhost:3000](http://localhost:3000)

---

## API surface


| Method & path                                    | Purpose                                            |
| ------------------------------------------------ | -------------------------------------------------- |
| `GET /api/health`                                | process + Mongo + OpenRouter reachability          |
| `GET /api/metrics`                               | in-process counters (requests, runs, chat, tokens) |
| `POST /api/sessions`                             | create a session                                   |
| `GET /api/sessions` · `GET /api/sessions/{id}`   | list / fetch                                       |
| `POST /api/sessions/{id}/run` · `/run/resume`    | start / resume a workflow run                      |
| `GET /api/sessions/{id}/runs/{runId}/events`     | SSE run progress (backfill + live)                 |
| `GET /api/sessions/{id}/report`                  | the nine-section report                            |
| `POST /api/sessions/{id}/chat`                   | ask a question (streams the reply)                 |
| `GET /api/sessions/{id}/chat/{messageId}/stream` | SSE chat token stream                              |
| `POST /api/sessions/{id}/chat/{messageId}/retry` | regenerate the last reply                          |
| `GET /api/sessions/{id}/chat/suggestions`        | starter prompts                                    |


Error contract everywhere: `{ "error": { "code", "message", "details": { "requestId" } } }`.

---

## Repository map

```
argus/
  backend/                     FastAPI + Motor + LangGraph
    app/
      api/        routes, router, error contract, rate limiting, metrics, chat
      db/         Motor client, collection names, indexes
      models/     Pydantic models + camelCase bridge (ApiModel)
      repositories/  async Mongo CRUD (sessions, runs, reports, chat)
      services/   orchestration above repos (session, workflow, chat)
      retrieval/  BM25 + prompt pack for grounded chat
      workflow/   LangGraph graph, nodes, prompts, runner, checkpointer, events
      config.py   pydantic-settings (+ redact())   metrics.py   logging_config.py
      main.py     app factory + lifespan (graceful shutdown)
    tests/        pytest — node, API, retrieval, hardening, end-to-end
  frontend/                    Next.js App Router + RTK Query + ShadCN
    src/
      app/        layout, providers, error.tsx / loading.tsx boundaries, routes
      components/ chat/ report/ workflow/ sessions/ ui/  + error/offline helpers
      hooks/      use-run-stream, use-chat-stream
      lib/        sse (run + chat), citations, request-id, toast, api-error
      services/   RTK Query base + injected endpoints
      store/      Redux store + typed hooks
      schemas/    zod schemas for API payloads
      types/      shared TypeScript types
  docs/           architecture.md · engineering-decisions.md · product-improvements.md
  scripts/dev.sh  boots both apps together
```

---

## Tech stack (and why)

- **FastAPI + Uvicorn** — async, typed, first-class Pydantic; fits a streaming API.
- **MongoDB + Motor** — flexible documents for evolving report/event shapes; async.
- **LangGraph** — explicit stateful graph with conditional routing + checkpointing.
- **OpenRouter** — one gateway, many models, per-node tiering.
- **Tavily** — quality search API.
- **Next.js App Router + RTK Query** — server shells + a cache/invalidation layer;
SSE for live updates.
- **Tailwind + ShadCN** — fast, consistent, accessible UI primitives.
- **slowapi / structlog / rank-free BM25** — rate limiting, structured logs, and a
dependency-free retriever for grounded chat.

---

## Testing

```bash
# Backend
cd backend
uv run ruff check . && uv run mypy app && uv run pytest

# Frontend
cd frontend
pnpm lint && pnpm typecheck && pnpm build
```

---

## Architecture & design docs

- `[docs/architecture.md](docs/architecture.md)` — system overview, request
flows, the LangGraph workflow, persistence, naming bridge, event model,
recoverability, deployment shape.
- `[docs/engineering-decisions.md](docs/engineering-decisions.md)` — the three
major decisions, tradeoffs, technical debt, biggest risk, the two-week plan.
- `[docs/product-improvements.md](docs/product-improvements.md)` — weaknesses,
what to build next, who pays, metrics, roadmap.

