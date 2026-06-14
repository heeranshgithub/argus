# PLAN — Part 1: Foundations & Scaffolding

**Goal:** Land a clean monorepo where both apps boot, talk to each other, talk to Mongo, share a naming bridge, and have lint/test/format in place. No product features yet — just the rails everything else rides on.

**Exit criteria:**
- `uv run uvicorn ...` boots the backend; `GET /api/health` returns `{ "status": "ok", "mongo": "ok" }`.
- `pnpm dev` boots the frontend; the home page calls the backend `/api/health` via RTK Query and renders the result.
- A round-trip of a sample payload proves camelCase ↔ snake_case mapping works automatically.
- `ruff check`, `pytest`, `eslint`, `tsc --noEmit` all pass green.
- `README.md` has a working "Quickstart" that a stranger can follow.

---

## 1. Repository Layout

```
argus/
  frontend/
  backend/
  docs/
    architecture.md            # stub
    engineering-decisions.md   # stub
    product-improvements.md    # stub
  scripts/
    dev.sh                     # boots both apps
  .gitignore
  .env.example                 # root-level shared example
  README.md
  PLAN.md
  PLAN_PART_1.md ... PLAN_PART_5.md
```

Move the existing `main.py` / `pyproject.toml` / `uv.lock` at the root into `backend/` (root-level Python scaffold gets dissolved).

---

## 2. Backend Scaffolding (`backend/`)

### 2.1 Tooling
- **UV** for dependency management. `pyproject.toml` with:
  - Runtime: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `motor`, `python-dotenv`, `httpx`, `structlog`
  - Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `httpx` (test client), `mongomock-motor`
- **Ruff** config in `pyproject.toml` (line length 100, target py312, enable `E,F,I,UP,B,SIM,RUF`).
- **pytest** config: `asyncio_mode = "auto"`, test dir `backend/tests`.

### 2.2 Directory layout
```
backend/
  app/
    __init__.py
    main.py                 # FastAPI factory + lifespan
    config.py               # Settings (pydantic-settings)
    logging_config.py       # structlog setup
    db/
      __init__.py
      mongo.py              # Motor client, get_db dependency
      collections.py        # collection name constants
    api/
      __init__.py
      router.py             # mounts all v1 routes under /api
      health.py             # /api/health
      errors.py             # exception handlers
    models/
      __init__.py
      base.py               # BaseModel with camelCase alias config
      health.py             # HealthResponse + EchoRequest/Response (for bridge test)
  tests/
    conftest.py
    test_health.py
    test_naming_bridge.py
  pyproject.toml
  .env.example
  .python-version
```

### 2.3 Settings (`app/config.py`)
- `pydantic-settings` `BaseSettings` reading from `.env`.
- Fields: `env` (`dev|prod|test`), `mongo_uri`, `mongo_db_name`, `cors_origins: list[str]`, `log_level`, `api_prefix="/api"`.
- Cached via `@lru_cache` `get_settings()`.

### 2.4 Naming bridge (`app/models/base.py`)
The single source of truth for camelCase ↔ snake_case:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
```

- Every request/response model inherits `ApiModel`.
- FastAPI route handlers always use `response_model=...` and `model.model_dump(by_alias=True)` is the default for responses (set via custom `JSONResponse` or just rely on FastAPI's auto-serialization with `response_model_by_alias=True` at app config — pick this; it's one line).
- Internal Python code stays snake_case. Mongo documents stay snake_case. Only the wire is camelCase.

### 2.5 Mongo (`app/db/mongo.py`)
- Async Motor client created in FastAPI `lifespan`.
- `get_db()` dependency yields the database handle.
- `collections.py` exports: `SESSIONS`, `WORKFLOW_RUNS`, `REPORTS`, `CHAT_MESSAGES` (used in later parts; declared now).
- On startup: ping the server; log success/failure.

### 2.6 Logging (`app/logging_config.py`)
- `structlog` JSON output in prod, pretty in dev.
- Middleware that attaches a `request_id` (uuid4) to each request's log context and to the `X-Request-ID` response header.

### 2.7 Error handling (`app/api/errors.py`)
- Register handlers for `RequestValidationError`, `HTTPException`, and a catch-all `Exception`.
- All responses follow:
  ```json
  { "error": { "code": "string", "message": "string", "details": {} } }
  ```
- These responses are also serialized through `ApiModel` so keys are camelCase.

### 2.8 Health route (`app/api/health.py`)
- `GET /api/health` returns `HealthResponse { status, mongo, version }`.
- Pings Mongo with a short timeout; reports `ok` or `down`.

### 2.9 Echo route (bridge sanity check)
- `POST /api/_echo` accepts `EchoRequest { fullName: str, retryCount: int }` (wire) which maps to `full_name`, `retry_count` server-side.
- Returns the same payload reversed back as camelCase.
- Backed by a test that asserts: send camelCase → handler sees snake_case → response is camelCase.

### 2.10 CORS
- `CORSMiddleware` reading `cors_origins` from settings. Default dev: `http://localhost:3000`.

### 2.11 Tests
- `test_health.py` — boots app with mocked Mongo, asserts 200 + shape.
- `test_naming_bridge.py` — POSTs camelCase, verifies internal model has snake_case attrs and response is camelCase.

---

## 3. Frontend Scaffolding (`frontend/`)

### 3.1 Bootstrap
- `pnpm create next-app@latest frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*"` (no Turbopack flag bikeshed; default is fine).
- Add: `@reduxjs/toolkit`, `react-redux`, `zod`, `lucide-react`, `sonner`, `clsx`, `tailwind-merge`, `class-variance-authority`.
- Init ShadCN: `pnpm dlx shadcn@latest init` → neutral base, CSS variables, `@/components/ui`.
- Install starter ShadCN primitives we'll definitely need: `button`, `input`, `label`, `card`, `dialog`, `toast`/sonner wrapper, `skeleton`.

### 3.2 Directory layout
```
frontend/
  src/
    app/
      layout.tsx              # wraps Providers, Toaster
      page.tsx                # health check demo
      providers.tsx           # Redux <Provider> + Sonner <Toaster>
    components/
      ui/                     # shadcn
      health-card.tsx         # consumes RTK Query
    lib/
      utils.ts                # cn()
      env.ts                  # zod-validated public env
    store/
      index.ts                # configureStore
      hooks.ts                # typed useAppDispatch/useAppSelector
    services/
      api.ts                  # RTK Query base + tagTypes
      health.ts               # healthApi.injectEndpoints
    types/
      api.ts                  # shared API types (camelCase only)
  .env.local.example
  eslint.config.mjs
  tsconfig.json
  package.json
```

### 3.3 RTK Query base (`src/services/api.ts`)
- `createApi` with `fetchBaseQuery({ baseUrl: env.NEXT_PUBLIC_API_BASE_URL })`.
- `tagTypes: ['Session', 'Report', 'Chat']` — declared now, used later.
- `endpoints: () => ({})` — endpoints injected per feature file (`injectEndpoints`).
- No camelCase ↔ snake_case transform needed; the backend already serves camelCase.

### 3.4 Env validation (`src/lib/env.ts`)
- Zod schema for `NEXT_PUBLIC_API_BASE_URL`.
- Throws at import time if missing → fail fast.

### 3.5 Health demo (`app/page.tsx`)
- `HealthCard` calls `useGetHealthQuery()`.
- Renders `status`, `mongo`, loading skeleton, error toast via Sonner.
- Proves the full chain: Next → RTK Query → FastAPI → Mongo.

### 3.6 ESLint / TS
- Keep Next's flat config, add `eslint-plugin-import` order rule.
- `tsconfig`: `"strict": true`, `"noUncheckedIndexedAccess": true`.

---

## 4. Shared Conventions

- **Wire format:** camelCase JSON, always. No snake_case ever crosses the network.
- **Internal Python:** snake_case (variables, fields, Mongo).
- **Internal TS:** camelCase (variables, fields).
- **IDs:** Mongo `_id` is mapped to `id` (camelCase on wire) via a base model field `id: str = Field(alias="_id")` pattern in a `MongoModel` base — declared in Part 1, used from Part 2 onward.
- **Timestamps:** stored as UTC `datetime` in Mongo; serialized as ISO-8601 strings on the wire.
- **Error contract:** `{ error: { code, message, details } }` — shared TS type in `frontend/src/types/api.ts`.

---

## 5. Dev Experience

- `scripts/dev.sh` — runs backend (`uv run uvicorn app.main:app --reload --port 8000`) and frontend (`pnpm --dir frontend dev`) concurrently (use `npx concurrently` or two `&` + `trap`).
- Root `.gitignore` covers Python, Node, `.env*`, `.venv`, `node_modules`, `.next`, `__pycache__`.
- `.env.example` at root documents every variable both apps need.

---

## 6. Documentation Stubs

- `README.md` — Quickstart (prereqs, install, env, run), repo map, link to `docs/`.
- `docs/architecture.md` — placeholder + system diagram outline.
- `docs/engineering-decisions.md` — placeholder with the 6 required sub-headings.
- `docs/product-improvements.md` — placeholder with the 10 required questions.

(Real content lands in Part 5; stubs exist now so links don't 404.)

---

## 7. Step-by-Step Execution Order

1. Reorganize repo: move root `main.py`/`pyproject.toml`/`uv.lock` into `backend/`. Add `frontend/`, `docs/`, `scripts/` dirs.
2. Backend: write `pyproject.toml`, `config.py`, `logging_config.py`, `models/base.py`, `db/mongo.py`, `api/errors.py`, `api/health.py`, `main.py`.
3. Backend: write `tests/test_health.py`, `tests/test_naming_bridge.py`. Run `ruff` + `pytest`.
4. Frontend: `create-next-app`, install deps, init ShadCN, wire Redux + RTK Query, write `env.ts`, `health.ts` endpoint, `health-card.tsx`, mount in `page.tsx`.
5. Run both apps via `scripts/dev.sh`; verify the page renders backend health.
6. Write README Quickstart. Commit.

---

## 8. Out of Scope for Part 1

- Sessions, workflows, chat, reports, LangGraph, LLM, search tools, auth, SSE, deployment configs. All handled in later parts.

## 9. Definition of Done — Part 1

- [ ] Backend boots, `/api/health` returns ok + Mongo reachable
- [ ] Echo round-trip test proves camelCase ↔ snake_case bridge
- [ ] Frontend home page renders live health from backend
- [ ] `ruff check`, `pytest`, `eslint`, `tsc --noEmit` all green
- [ ] README Quickstart works from a clean clone
- [ ] All four `docs/*.md` files exist (stubs)
