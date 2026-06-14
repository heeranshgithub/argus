# Argus — Master Plan

**Project:** AI Research Copilot for sales/business meeting prep
**Stack:** Next.js + FastAPI + LangGraph + MongoDB
**Delivery:** 5 sequential parts (`PLAN_PART_1.md` → `PLAN_PART_5.md`)

---

## 1. Product Summary

Argus helps a user prepare for a meeting by researching a target company and generating a structured briefing. The user creates a session (company name, website, objective), watches a LangGraph workflow execute in real time, reads the final report, and can chat with the report as context. All sessions, intermediate state, and chats persist.

---

## 2. Tech Stack

### Frontend (`frontend/`)
- **Framework:** Next.js (App Router) + TypeScript
- **State / Data:** Redux Toolkit + RTK Query
- **UI:** TailwindCSS, ShadCN, Lucide React icons, Sonner (toasts)
- **Validation:** Zod
- **Linting:** ESLint
- **Convention:** All code, variables, API payloads in **camelCase**

### Backend (`backend/`)
- **Framework:** FastAPI + Python 3.12
- **Validation:** Pydantic v2
- **Package mgmt:** UV
- **DB:** MongoDB (Motor async driver)
- **AI Workflow:** LangGraph (with checkpointer for recoverability)
- **Testing:** pytest
- **Linting:** Ruff
- **Convention:** All code, variables, MongoDB fields in **snake_case**

### Cross-cutting
- **Naming bridge:** A single Pydantic model layer at the API boundary uses field aliases (`snake_case` internally, `camelCase` on the wire) via `alias_generator=to_camel` + `populate_by_name=True`. The frontend never sees snake_case; the backend never sees camelCase. One config, one source of truth.
- **Env:** `.env` per app + a shared `.env.example` at root.
- **Repo layout:**
  ```
  argus/
    frontend/
    backend/
    docs/
      architecture.md
      engineering-decisions.md
      product-improvements.md
    README.md
  ```

---

## 3. LangGraph Workflow (high level)

Nodes (each writes to shared state, emits progress event, is independently retryable):

1. **Planner** — parses objective, decomposes into research sub-questions, picks tools.
2. **Web Research** — runs web search + page fetches for company + sub-questions.
3. **Signal Extractor** — pulls business signals (funding, hiring, news, product launches).
4. **Analyst** — synthesizes overview, products, customers, risks.
5. **Quality Check** — conditional routing: if confidence/coverage low → loop back to Research (max N retries); else proceed.
6. **Report Generator** — emits structured report matching the required schema.

State persisted via LangGraph checkpointer (Mongo-backed) so a session can resume after crash.

---

## 4. Data Model (Mongo collections)

- `sessions` — id, company_name, website, objective, status, created_at, updated_at
- `workflow_runs` — session_id, graph state snapshots, node events, errors
- `reports` — session_id, structured report (9 required sections), sources
- `chat_messages` — session_id, role, content, created_at, citations

---

## 5. API Surface (sketch)

- `POST /sessions` — create
- `GET /sessions` — list (history)
- `GET /sessions/{id}` — detail + report
- `POST /sessions/{id}/run` — start/resume workflow
- `GET /sessions/{id}/events` — SSE stream of node progress
- `POST /sessions/{id}/chat` — follow-up chat (RAG over report + state)
- `GET /sessions/{id}/chat` — chat history

---

## 6. Five-Part Breakdown

Each part is independently shippable and ends with a working checkpoint.

### PART 1 — Foundations & Scaffolding
- Monorepo layout, tooling (UV, ESLint, Ruff, pre-commit)
- FastAPI app skeleton, settings (Pydantic Settings), logging, error handlers
- Mongo connection + Motor client + collection bootstrap
- Next.js app skeleton, Tailwind + ShadCN init, Redux store, RTK Query base
- Shared naming bridge (camelCase ↔ snake_case alias config)
- `/health` route end-to-end
- Skeleton `README.md` + `docs/`

### PART 2 — Sessions CRUD & Persistence
- Pydantic models + Mongo repositories for `sessions`
- Session APIs: create, list, get
- Frontend: Create Session form (Zod validated), Session History list, Session Detail shell
- Loading / error / empty states wired with Sonner
- pytest for repos + API routes

### PART 3 — LangGraph Workflow
- Define `GraphState` (TypedDict)
- Implement nodes: Planner → Research → Signal Extractor → Analyst → Quality Check (conditional) → Report Generator
- Wire Mongo checkpointer for recoverability
- Persist `workflow_runs` + `reports`
- `POST /sessions/{id}/run` triggers execution as background task
- Node-level retry + structured error capture
- pytest with mocked LLM / search tools

### PART 4 — Real-time Progress & Report UI
- SSE endpoint streaming node start/finish/error events
- Frontend Workflow Progress UI (per-node status, timings, intermediate outputs)
- Report rendering with all 9 required sections + sources
- Resume / retry controls when a run fails

### PART 5 — Follow-up Chat, Polish & Docs
- Chat API (LLM grounded in report + selected workflow state, with citations)
- Frontend chat panel on session detail
- Responsive pass, accessibility pass, toast/error polish
- Production hardening: rate limiting, request IDs, structured logs
- Write `architecture.md`, `engineering-decisions.md`, `product-improvements.md`
- Final `README.md` (setup, run, env, demo)
- Demo video / deploy

---

## 7. Definition of Done (whole project)

- All 9 report sections render from a real workflow run
- Workflow has ≥5 meaningful nodes, shared state, conditional routing, intermediate outputs visible in UI, failure handling, and can resume from checkpoint
- Sessions, runs, reports, chats persist in Mongo across restarts
- Frontend is responsive, has loading + error states everywhere, passes ESLint + typecheck
- Backend passes Ruff + pytest
- All four required docs present and complete
- README explains setup in one read-through
