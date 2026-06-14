# Argus — AI Research Copilot

> "Your sellers run the conversation. We do everything else."

Argus helps you prepare for a sales or business meeting by researching a target
company and generating a structured briefing. Create a research session, watch a
LangGraph workflow execute in real time, read the final report, and chat with the
report as context — all persisted.

**Stack:** Next.js (App Router) + FastAPI + LangGraph + MongoDB.

This repository is built in five sequential parts (`PLAN_PART_1.md` →
`PLAN_PART_5.md`). **Parts 1–3 are complete:**

- **Part 1** — foundations & scaffolding: both apps boot, talk to each other and
  to MongoDB, share a camelCase ↔ snake_case naming bridge, lint/test/typecheck.
- **Part 2** — sessions CRUD with Mongo persistence.
- **Part 3** — the LangGraph workflow engine: a six-node graph
  (`planner → researcher → signal_extractor → analyst → quality_check → reporter`)
  with shared state, a conditional research loop, per-node retries, a Mongo-backed
  checkpointer for resume-from-crash, an event timeline persisted per run, and a
  generated nine-section research report. Drives OpenRouter (LLM gateway) + Tavily
  (search) through swappable client protocols, so the whole graph runs offline
  under pytest and against live providers from a script.

### Part 3 workflow endpoints

| Method & path | Purpose |
|---|---|
| `POST /api/sessions/{id}/run` | Start a workflow run (202, background) |
| `POST /api/sessions/{id}/run/resume` | Resume a failed run from its last checkpoint |
| `GET /api/sessions/{id}/runs` | List runs (newest-first) |
| `GET /api/sessions/{id}/runs/{runId}` | One run with its full event timeline |
| `GET /api/sessions/{id}/runs/{runId}/events` | SSE event stream (backfill + live) |
| `GET /api/sessions/{id}/report` | The generated nine-section report |

Run the workflow against **live** providers (requires `OPENROUTER_API_KEY`, and
ideally `TAVILY_API_KEY`, in `backend/.env`):

```bash
cd backend
uv run python scripts/run_workflow.py \
    --company "Stripe" --website "https://stripe.com" \
    --objective "Explore a payments partnership"
```

---

## Quickstart

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| [uv](https://docs.astral.sh/uv/) | ≥ 0.5 | Python dependency manager |
| Python | ≥ 3.12 | `uv` can install it for you |
| [Node.js](https://nodejs.org) | ≥ 20 | |
| [pnpm](https://pnpm.io) | ≥ 9 | `corepack enable` |
| MongoDB | ≥ 7 | local install **or** Docker (below) |

### 1. Clone & configure environment

```bash
git clone <repo-url> argus
cd argus

# Backend env
cp backend/.env.example backend/.env

# Frontend env
cp frontend/.env.local.example frontend/.env.local
```

The root [`.env.example`](.env.example) documents every variable both apps use.

### 2. Start MongoDB

Local install, or via Docker:

```bash
docker run -d --name argus-mongo -p 27017:27017 mongo:7
```

### 3. Install dependencies

```bash
# Backend
cd backend && uv sync && cd ..

# Frontend
cd frontend && pnpm install && cd ..
```

### 4. Run both apps

```bash
./scripts/dev.sh
```

- Backend → http://localhost:8000 (`GET /api/health` → `{ "status": "ok", "mongo": "ok" }`)
- Frontend → http://localhost:3000 (home page renders live backend health)

Or run them separately:

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && pnpm dev
```

---

## Verify the toolchain

```bash
# Backend
cd backend
uv run ruff check .
uv run mypy app
uv run pytest

# Frontend
cd frontend
pnpm exec eslint .
pnpm exec tsc --noEmit
pnpm build
```

All should pass green.

---

## Repository Map

```
argus/
  backend/        FastAPI + Motor + (LangGraph, later parts)
    app/
      api/        routes, router, error handlers
      db/         Motor client, collection names
      models/     Pydantic models + naming bridge (ApiModel)
      config.py   pydantic-settings
      main.py     app factory + lifespan
    tests/        pytest (health + naming bridge)
  frontend/       Next.js (App Router) + Redux Toolkit + RTK Query + ShadCN
    src/
      app/        layout, page, providers
      components/ ui/ (shadcn), health-card
      services/   RTK Query base + injected endpoints
      store/      Redux store + typed hooks
      lib/        cn(), zod-validated env
      types/      shared API types (camelCase)
  docs/           architecture, engineering-decisions, product-improvements
  scripts/dev.sh  boots both apps together
```

## Conventions

- **Wire format:** camelCase JSON, always. snake_case never crosses the network.
- **Backend internals & Mongo:** snake_case.
- **Frontend internals:** camelCase.
- The single source of truth for the bridge is `backend/app/models/base.py`
  (`ApiModel` with `alias_generator=to_camel` + `populate_by_name=True`).
- **Error contract:** `{ "error": { "code", "message", "details" } }` (camelCase).

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/engineering-decisions.md`](docs/engineering-decisions.md)
- [`docs/product-improvements.md`](docs/product-improvements.md)

(Full content lands in Part 5; stubs exist now so links resolve.)
