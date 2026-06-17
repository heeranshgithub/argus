# PLAN — Part 3: LangGraph Workflow Engine

**Goal:** Build the heart of the product — a LangGraph workflow that takes a session (company, website, objective) and produces a structured research report. The workflow must have multiple meaningful nodes, shared state, conditional routing, intermediate outputs, failure handling, and recoverability via a Mongo-backed checkpointer. Every node's progress and output is persisted so Part 4 can stream it to the UI.

This is the highest-weighted slice of the rubric (LangGraph 25% + AI Engineering 15% = 40%). Treat it as the centerpiece.

**Exit criteria:**
- `POST /api/sessions/{id}/run` kicks off a workflow that runs to completion on a real session.
- The workflow has ≥5 distinct nodes, shared `GraphState`, at least one conditional edge, intermediate outputs visible in Mongo, retries on node failure, and resumes from the last checkpoint on restart.
- A `reports` document is created with all 9 required sections + sources.
- A `workflow_runs` document captures the full event timeline (node start/finish/error/output).
- The same workflow runs end-to-end against **mocked** LLM/search tools in pytest, and against the **real** providers from a local script.
- `ruff` + `pytest` green; ≥80% coverage on graph code.

---

## 1. Architectural Overview

```
                    ┌──────────────────────────────────────────────┐
                    │              GraphState (TypedDict)           │
                    │  session_id, inputs, plan, raw_sources,       │
                    │  extracted_signals, analysis, quality,        │
                    │  report, errors[], retry_counts{}             │
                    └──────────────────────────────────────────────┘
                                         │
                                         ▼
   ┌─────────┐    ┌──────────┐   ┌──────────────┐   ┌─────────┐   ┌──────────────┐   ┌──────────┐   ┌────────┐
   │ planner │ -> │ researcher│-> │signal_extract│-> │ analyst │-> │ quality_check│-> │ reporter │-> │  END   │
   └────┬────┘    └──────────┘   └──────────────┘   └─────────┘   └──────┬───────┘   └──────────┘   └────────┘
        ▲                                                                 │
        └─────────────────────[ if low confidence ]──────────────────────┘
                          (re-plans gaps as new questions; max 2 retries)
```

- **Checkpointer:** custom Mongo-backed `BaseCheckpointSaver` (or `langgraph.checkpoint.mongodb.MongoDBSaver` if available — verify version) keyed by `thread_id = session_id`. Allows a crashed run to resume from the last completed node.
- **Execution model:** workflow runs as a FastAPI `BackgroundTasks` coroutine (Part 3) — long-running but in-process. Part 5 may upgrade to a proper task queue if time allows; not required.
- **Event sink:** each node emits an event (`node_started`, `node_finished`, `node_errored`, `node_output`) that goes into both:
  1. `workflow_runs.events` (append) — for replay/audit + Part 4's SSE backfill.
  2. An in-memory `asyncio.Queue` per session — for Part 4's live SSE stream.
- **LLM provider:** **OpenRouter** as the single gateway — one OpenAI-compatible endpoint that proxies to hundreds of models (OpenAI, Anthropic, Google, Mistral, Meta, DeepSeek, Qwen, etc.). The `LLMClient` protocol stays so we *could* swap to direct providers, but in practice the model is just a config string (`openai/gpt-4o-mini`, `anthropic/claude-haiku-4.5`, `google/gemini-2.5-flash`, ...). Each node can even pin its own model (cheap/fast for planner & quality_check; stronger for analyst & reporter).
- **Search provider:** `SearchClient` protocol; default implementation uses Tavily (clean JSON API, no scraping headaches). Fallback to DuckDuckGo if no key.

---

## 2. New Backend Layout (additions to Part 1/2)

```
backend/app/
  workflow/
    __init__.py
    state.py                 # GraphState TypedDict + reducers
    graph.py                 # build_graph() — assembles nodes + edges
    checkpointer.py          # MongoCheckpointer (BaseCheckpointSaver impl)
    events.py                # WorkflowEvent model + emit() helper
    runner.py                # WorkflowRunner — orchestrates a run end-to-end
    prompts/
      __init__.py
      planner.py
      analyst.py
      reporter.py
      quality_check.py
    nodes/
      __init__.py
      planner.py
      researcher.py
      signal_extractor.py
      analyst.py
      quality_check.py
      reporter.py
    tools/
      __init__.py
      llm.py                 # LLMClient protocol + OpenAI/Anthropic impls
      search.py              # SearchClient protocol + Tavily/DDG impls
      fetch.py               # httpx-based page fetcher with timeouts + size cap
      text.py                # readability/cleanup helpers
  models/
    workflow.py              # WorkflowRunOut, WorkflowEventOut, NodeStatus
    report.py                # ReportOut + the 9 sections as nested models
  repositories/
    workflow_repo.py         # CRUD on workflow_runs + checkpoints collection
    report_repo.py           # CRUD on reports
  api/
    runs.py                  # /api/sessions/{id}/run + /runs/{run_id}
    reports.py               # /api/sessions/{id}/report
  services/
    workflow_service.py      # starts/resumes runs; bridges API ↔ runner
backend/tests/
  workflow/
    conftest.py              # fake LLMClient + SearchClient fixtures
    test_state.py
    test_planner_node.py
    test_researcher_node.py
    test_signal_extractor_node.py
    test_analyst_node.py
    test_quality_check_routing.py
    test_reporter_node.py
    test_checkpointer.py
    test_runner_end_to_end.py
    test_runs_api.py
```

---

## 3. GraphState (`workflow/state.py`)

```python
from typing import TypedDict, Annotated
from operator import add

class SubQuestion(TypedDict):
    id: str
    question: str
    rationale: str

class RawSource(TypedDict):
    url: str
    title: str
    snippet: str
    content: str           # cleaned text, capped at N chars
    fetched_at: str        # ISO

class BusinessSignal(TypedDict):
    category: str          # 'funding' | 'hiring' | 'product' | 'news' | 'partnership' | 'other'
    summary: str
    evidence_urls: list[str]
    confidence: float      # 0..1

class AnalysisBlock(TypedDict):
    overview: str
    products_services: list[str]
    target_customers: list[str]
    risks: list[str]
    unknowns: list[str]

class QualityVerdict(TypedDict):
    coverage_score: float        # 0..1
    confidence_score: float      # 0..1
    missing_areas: list[str]
    needs_more_research: bool

class GraphState(TypedDict, total=False):
    # inputs
    session_id: str
    company_name: str
    website: str
    objective: str

    # outputs accumulated per node
    plan: list[SubQuestion]
    raw_sources: Annotated[list[RawSource], add]      # appended across retries
    extracted_signals: list[BusinessSignal]
    analysis: AnalysisBlock
    quality: QualityVerdict
    report: dict                                       # final structured report

    # control
    retry_counts: dict[str, int]                       # node_name -> count
    errors: Annotated[list[dict], add]                 # append-only error log
    research_iteration: int                            # incremented per Research loop
```

The `Annotated[..., add]` reducers let LangGraph merge updates across iterations (especially important when Research re-runs after Quality fails).

---

## 4. Nodes — contract and responsibilities

Each node:
- Is an `async def node(state: GraphState) -> dict` returning a **partial** state update.
- Wraps its work in `with emit_node(state, "<name>") as ev:` (context manager from `events.py`) which writes `node_started` on enter, `node_finished` (with payload preview) on exit, `node_errored` on exception.
- Catches and re-raises after recording — letting LangGraph's retry policy take over.
- Has its own focused prompt (kept in `prompts/`) — no monolithic system prompts.

### 4.1 `planner`
- Input: `company_name`, `website`, `objective`.
- LLM call: produce 5–8 `SubQuestion`s tailored to the objective (e.g., "Are they hiring sales engineers?" if the objective is "expansion partnership").
- Output: `plan`.

### 4.2 `researcher`
- For each `SubQuestion` (parallelized with `asyncio.gather`, bounded by a semaphore of 4):
  - `SearchClient.search(query)` → top K (default 5) results.
  - `fetch(url)` for the top 3 with httpx (timeout 8s, 1 MB cap, follow redirects, respect robots when present — keep it simple).
  - Clean with `text.py` (readability-like: strip nav/script/style, collapse whitespace, truncate to 8k chars).
- Also crawls the company `website` root + `/about`, `/products`, `/pricing`, `/careers`, `/blog` (best-effort, ignore 404s).
- De-duplicate by URL.
- Output: appends to `raw_sources`. Increments `research_iteration`.
- Failure handling: per-URL errors are logged into `state.errors` but do **not** fail the node unless **all** sources fail.

### 4.3 `signal_extractor`
- LLM call(s) over `raw_sources` (chunked if needed) to pull `BusinessSignal`s grouped by category.
- Each signal carries `evidence_urls` referencing actual sources from `raw_sources`.
- Output: `extracted_signals`.

### 4.4 `analyst`
- LLM call: synthesize `AnalysisBlock` from `raw_sources` + `extracted_signals` + `objective`.
- Returns structured JSON (validated via Pydantic at the node boundary; on validation failure, retry once with a "your previous output failed schema X; fix it" prompt).
- Output: `analysis`.

### 4.5 `quality_check`
- LLM call evaluates: coverage of the 9 required report sections, contradiction detection, citation density, confidence per section.
- Returns `QualityVerdict`.
- **Conditional routing:**
  - If `needs_more_research and missing_areas and research_iteration < N` → route back to `planner`, which turns `missing_areas` into fresh gap-closing sub-questions appended to `plan` for the researcher to chase. (Routing straight to `researcher` would re-run it against the already-researched plan and gather nothing.)
  - Else → `reporter`. (Includes the case where `needs_more_research` is true but `missing_areas` is empty — no concrete gap to plan against.)
- This is the *required* conditional edge.

### 4.6 `reporter`
- LLM call: produce the final structured `ReportOut` matching the schema in §5. Strict JSON mode (response_format).
- Discovery questions and outreach strategy are generated here — they reference `objective` directly.
- `sources` deduped from `raw_sources`, ranked by usage (count of times referenced in evidence).
- Validates with Pydantic; on failure, retry once.
- Output: `report`.
- Also persists the report to `reports` collection at the end (via `report_repo`) so it's queryable independently of the graph state.

---

## 5. Report Schema (`models/report.py`)

Matches the assignment's 9 required sections exactly:

```python
class ReportSource(ApiModel):
    url: str
    title: str
    used_in: list[str]                  # which sections cited it

class DiscoveryQuestion(ApiModel):
    question: str
    rationale: str

class ReportOut(ApiModel):
    id: str
    session_id: str
    company_overview: str
    products_and_services: list[str]
    target_customers: list[str]
    business_signals: list[BusinessSignalOut]
    risks_and_challenges: list[str]
    suggested_discovery_questions: list[DiscoveryQuestion]
    suggested_outreach_strategy: str
    unknowns: list[str]
    sources: list[ReportSource]
    created_at: datetime
```

All on the wire as camelCase via the `ApiModel` base from Part 1. Stored snake_case in Mongo.

---

## 6. Checkpointer (`workflow/checkpointer.py`)

> **Implementation note (deviation from original single-collection sketch).**
> No `langgraph-checkpoint-mongodb` package exists for LangGraph 1.x, so the
> custom `BaseCheckpointSaver` is the default plan (as anticipated below). During
> implementation the storage was split across **three** collections instead of
> embedding `channel_values` / `pending_writes` inside one checkpoint document.
> Reason: LangGraph addresses channel **blobs** by `(thread, ns, channel,
> version)` *independently of any single checkpoint* — a later checkpoint reuses
> an earlier checkpoint's blob for any channel it didn't rewrite. Embedding blobs
> per-checkpoint would break that cross-step reuse (and bloat each snapshot), so
> blobs and writes get their own collections, mirroring LangGraph's own
> Postgres/SQLite savers.

Three Mongo collections:

```
# workflow_checkpoints — one doc per checkpoint (+ its metadata)
{ thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, ts,
  type, checkpoint: BinData, metadata_type, metadata: BinData }

# workflow_checkpoint_blobs — one doc per channel value, keyed by version
{ thread_id, checkpoint_ns, channel, version, type, blob: BinData }

# workflow_checkpoint_writes — pending writes (intermediate task outputs)
{ thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel,
  type, blob: BinData, task_path }
```

- Implements the `BaseCheckpointSaver` async interface: `aget_tuple`, `alist`,
  `aput`, `aput_writes` (plus `adelete_thread`). The sync methods raise — the
  graph runs async-only.
- Indexes: unique `(thread_id, checkpoint_ns, checkpoint_id)`,
  `(thread_id, ts desc)`, unique blob/write keys (see `ensure_indexes`).
- BSON-safe serialization via LangGraph's own `serde` (msgpack → `bytes`) stored
  as BSON `Binary`; `ObjectId`/Pydantic never enter the checkpoint path.

If `langgraph-checkpoint-mongodb` exists for our LangGraph version, use it instead and skip writing this from scratch — but verify it actually works async and supports our state types. Decide at implementation time. *(Resolved: it does not exist for 1.x; custom saver shipped.)*

---

## 7. Events (`workflow/events.py`)

```python
class WorkflowEvent(TypedDict):
    run_id: str
    session_id: str
    node: str
    kind: str               # 'node_started' | 'node_finished' | 'node_errored' | 'node_output' | 'run_started' | 'run_completed' | 'run_failed'
    payload: dict           # small preview; full output is in checkpoint
    ts: datetime
    seq: int                # monotonically increasing per run
```

- `events.py` exports `emit_node(state, name)` (async context manager) and `emit(event)`.
- `emit` does two things atomically (best-effort):
  1. `$push` to `workflow_runs.events`.
  2. `put_nowait` on the per-session asyncio queue (so Part 4's SSE can read live).
- If no consumer queue is registered, the put is a no-op — events still land in Mongo for backfill.

---

## 8. Runner (`workflow/runner.py`)

```python
class WorkflowRunner:
    def __init__(self, db, llm, search, settings): ...

    async def start(self, session_id: str) -> str:
        """Create workflow_run, mark session 'running', launch graph in background."""

    async def resume(self, session_id: str) -> str:
        """Reload from checkpoint, continue execution."""

    async def _execute(self, run_id: str, session_id: str) -> None:
        """Graph invocation + final status update on session."""
```

- Uses `graph.ainvoke({...}, config={"configurable": {"thread_id": session_id}, "recursion_limit": 30})`.
- Wraps in try/except: on uncaught failure → mark session `failed`, emit `run_failed`, persist error to `workflow_runs.error`.
- On success → mark session `completed`, emit `run_completed`.

---

## 9. New Mongo collections

### `workflow_runs`
```
_id, session_id, status, started_at, finished_at,
events: [WorkflowEvent...], error: {code, message, traceback} | null,
node_status: {planner: 'pending'|'running'|'done'|'failed', ...},
final_state_keys: [str]      # for debugging without dumping full state
```
Indexes: `session_id: 1`, `started_at: -1`.

### `workflow_checkpoints` (+ `workflow_checkpoint_blobs`, `workflow_checkpoint_writes`)
Checkpointer storage — three collections, not one. See §6 for the schema and the
rationale for splitting blobs/writes out of the checkpoint document.

### `reports`
```
_id, session_id, created_at, ...all sections from §5...
```
Indexes: `session_id: 1` (unique — one report per session for now).

---

## 10. APIs (`api/runs.py`, `api/reports.py`)

- `POST /api/sessions/{id}/run` → 202, `{ runId, status: 'running' }`. Validates session exists + is not already running. Launches `runner.start()` as a background task.
- `POST /api/sessions/{id}/run/resume` → 202, resumes from last checkpoint if session is `failed`.
- `GET /api/sessions/{id}/runs` → list of runs for that session (most recent first).
- `GET /api/sessions/{id}/runs/{run_id}` → full `WorkflowRunOut` including events (so a refreshing UI can rebuild state on first paint before SSE attaches).
- `GET /api/sessions/{id}/report` → `ReportOut` or 404.

All error responses follow the standard `{ error: { code, message, details } }` contract.

SSE endpoint (`/api/sessions/{id}/runs/{run_id}/events`) is **scaffolded but not consumed** in Part 3 — the contract is fixed here so Part 4 only wires the frontend.

---

## 11. LLM & Search abstractions

### `tools/llm.py`
```python
class LLMClient(Protocol):
    async def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,            # override default; e.g. 'anthropic/claude-haiku-4.5'
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        fallback_models: list[str] | None = None,   # OpenRouter `models` array
    ) -> str | BaseModel: ...
```

**`OpenRouterClient`** — the only real implementation. Uses the official OpenAI SDK pointed at `https://openrouter.ai/api/v1` with the OpenRouter API key. This gives us:
- One API key, one client, hundreds of models.
- Model selection by config string (`openai/gpt-4o-mini`, `anthropic/claude-sonnet-4.6`, `google/gemini-2.5-flash`, `meta-llama/llama-3.3-70b`, ...).
- Built-in provider fallback: pass `models=[primary, fallback1, fallback2]` and OpenRouter routes around outages automatically.
- Per-node model overrides — `planner` and `quality_check` use a cheap/fast model; `analyst` and `reporter` use a stronger one. Defaults live in `config.py`, overridable per call.
- Optional `HTTP-Referer` and `X-Title` headers (OpenRouter convention) set to identify Argus in their dashboard.

**Structured output handling.** Not all models behind OpenRouter support `response_format={"type": "json_schema"}`. The client tries in this order:
1. If the model is known to support strict JSON schema (slug prefix `openai/` or `google/gemini`) → use **native** structured output: `response_format={"type":"json_schema","json_schema":{...,"strict":True}}`. Pydantic's schema is hardened for OpenAI strict mode first (`_to_strict_schema`): every object gets `additionalProperties: false` and all properties marked `required`, and `default` keys are stripped, recursively through `$defs`.
2. Otherwise (e.g. `anthropic/*`) → `response_format={"type":"json_object"}` **plus** the JSON Schema embedded in the system prompt, then parse + Pydantic-validate.
3. On parse/validation failure (either path) → one repair retry with the error message included in the prompt ("Your previous response failed validation: …. Return ONLY corrected JSON that is an instance of the schema.").

> **Implementation note (this design was forced by the live smoke run, not the unit tests).** The first cut used only path 2 (JSON mode + schema-in-prompt) for *all* models. Mocked tests passed, but the live run exposed two failures the fakes couldn't:
> - **`gpt-4o-mini` echoed the schema** (returned `{"description": ..., "properties": {...}}`) instead of an instance, even under JSON mode, and the repair retry didn't recover it. → Fixed by adding the native strict-schema path (step 1), which enforces the exact shape server-side.
> - **The reporter's output was truncated** mid-JSON because the full report (with ~26 sources) exceeded the 2000-token default → invalid JSON. → Fixed by (a) raising `max_tokens` for the heavy nodes (`reporter` 4000, `analyst` 3000) and (b) instructing the reporter to return an empty `sources` array — the node rebuilds `sources` deterministically from `raw_sources` ranked by evidence usage anyway, so the model never needs to emit them.
>
> Lesson captured for later parts: **structured-output adherence and token budgets must be validated against real providers**, not just `FakeLLMClient`.

**Retry & metrics.** 3 attempts with exp backoff (1s, 2s, 4s) on 429/5xx/timeout. Every call emits a structlog event with `model`, `prompt_tokens`, `completion_tokens`, `cost_usd` (OpenRouter returns it in the response), `latency_ms`, `node`, `session_id`, `run_id`.

**`FakeLLMClient`** — used in all unit tests; deterministic scripted responses keyed by node name + call index. Never hits the network.

### `tools/search.py`
```python
class SearchClient(Protocol):
    async def search(self, query: str, k: int = 5) -> list[SearchHit]: ...

class SearchHit(TypedDict):
    url: str
    title: str
    snippet: str
```
- `TavilyClient` primary; `DuckDuckGoClient` fallback. Choice at startup based on which env var is set.

### `tools/fetch.py`
- `async def fetch(url: str) -> FetchedPage`
- `httpx.AsyncClient` with 8s timeout, 1 MB cap, follow redirects, common UA.
- Returns `{ url, status, content_type, html, text }` where `text` is readability-cleaned.

---

## 12. Configuration additions (`config.py`)

```
# OpenRouter — single LLM gateway
openrouter_api_key: str | None = None        # optional at Settings level; see note below
openrouter_base_url: str = 'https://openrouter.ai/api/v1'
openrouter_app_title: str = 'Argus Research Copilot'
openrouter_app_url: str | None = None       # sent as HTTP-Referer

# Per-node default models (all OpenRouter model slugs; freely changeable)
llm_model_default: str = 'openai/gpt-4o-mini'
llm_model_planner: str | None = None        # falls back to default
llm_model_researcher: str | None = None     # researcher does no LLM work; reserved
llm_model_signal_extractor: str | None = None
llm_model_analyst: str = 'anthropic/claude-sonnet-4.6'
llm_model_quality_check: str | None = None
llm_model_reporter: str = 'anthropic/claude-sonnet-4.6'
llm_fallback_models: list[str] = ['openai/gpt-4o-mini', 'google/gemini-2.5-flash']

# Search
tavily_api_key: str | None = None
search_provider: Literal['tavily', 'ddg'] = 'tavily'

# Workflow control
workflow_max_research_iterations: int = 2
workflow_node_retry_limit: int = 2
workflow_recursion_limit: int = 30
fetch_timeout_seconds: float = 8.0
fetch_max_bytes: int = 1_000_000
```

All read from env. Model slugs are validated lazily on first use (OpenRouter returns a clear 404 for unknown models).

> **Implementation note (deviation: where "fail fast" lives).** The original plan declared `openrouter_api_key: str` (required) and said a missing key "fails fast at startup." In practice the key is **optional on the `Settings` model** (`str | None = None`) and the fail-fast moved *down* to `OpenRouterClient` construction, which raises `LLMError` with a clear message when the key is absent. Rationale:
> - A required field would make `Settings()` itself throw, breaking the **test suite** (which never sets a real key) and the unrelated **health/sessions** routes, which don't need an LLM.
> - Construction is **lazy** anyway: `get_workflow_deps` builds the real client on the first workflow request and caches it on `app.state`; a missing key surfaces there as a domain `WorkflowUnavailable` → **HTTP 503** with the standard error envelope, only on workflow routes.
>
> Net effect matches the plan's intent ("clear error when misconfigured") while keeping the rest of the app and the offline test suite runnable without any provider credentials.

---

## 13. Testing strategy

### 13.1 Unit tests per node
- `conftest.py` provides:
  - `FakeLLMClient` — returns scripted Pydantic objects keyed by prompt fingerprint or call count.
  - `FakeSearchClient` — returns fixture hits from `tests/workflow/fixtures/search/*.json`.
  - `FakeFetcher` — returns fixture HTML from `tests/workflow/fixtures/pages/*.html`.
- Each node test feeds a minimal `GraphState`, asserts the partial-state diff matches expectation, and asserts events were emitted.

### 13.2 Routing test
- `test_quality_check_routing.py` — runs `quality_check` with two scripted verdicts (low/high) and asserts the next node decision.

### 13.3 Checkpoint test
- Run graph to mid-flight, simulate crash (raise from `analyst`), call `runner.resume()` with a new runner instance, assert it picks up from `signal_extractor`'s output without re-running earlier nodes.

### 13.4 End-to-end test
- `test_runner_end_to_end.py` — runs the full graph with all fakes against a real Mongo (testcontainers or local), asserts:
  - `workflow_runs` has events for all nodes in order.
  - `reports` document has all 9 sections populated.
  - `sessions.status` transitions `created → running → completed`.

### 13.5 API tests
- `test_runs_api.py` — POST run, poll GET run, eventually see `completed`; GET report returns full structure; double-POST returns 409 conflict.

### 13.6 Live smoke script
- `scripts/run_workflow.py` — CLI that creates a session and runs the workflow against **real** LLM + search (using local env). Not a test; used for manual verification before Part 4.

---

## 14. Observability

- Every node logs structured events: `node`, `session_id`, `run_id`, `duration_ms`, `tokens_in`, `tokens_out`, `llm_model`, `retry_attempt`.
- LLM client wraps each call in a `with log.bind(...)` block.
- A `GET /api/sessions/{id}/runs/{run_id}/timeline` debug endpoint (dev-only, gated by `settings.env == 'dev'`) returns the full event list with payloads for quick eyeballing.

---

## 15. Error & retry policy

| Layer | Strategy |
|-------|----------|
| LLM call | 3 retries, exponential backoff (1s, 2s, 4s), only on 429/5xx/timeout |
| Search call | 2 retries, same backoff |
| Page fetch | No retries (search has many results; move on) |
| Node | LangGraph's per-node retry: max 2, only for transient exceptions; persistent errors short-circuit to a `node_errored` event and the run continues if non-critical (e.g., one page fetch failed) or fails the run if critical (planner, reporter) |
| Run | On uncaught failure, session status = `failed`. `resume` is allowed. |

---

## 16. Step-by-Step Execution Order

1. **Skeleton:** create `workflow/` tree with empty modules; wire `runner.py` stub into `services/workflow_service.py`; add empty API endpoints returning 501.
2. **State + events:** implement `GraphState`, `events.py`, `WorkflowEvent` model, repo for `workflow_runs`.
3. **Tool abstractions:** `LLMClient`/`SearchClient` protocols + fake implementations + real implementations. Unit tests with fakes only.
4. **Nodes (bottom-up):**
   1. `reporter` (easiest to test — fixed-output transform).
   2. `analyst`, `signal_extractor`.
   3. `researcher` (heaviest — exercises fetch + search).
   4. `planner`.
   5. `quality_check` + conditional routing.
5. **Graph assembly:** `graph.py` wiring all nodes + conditional edge + entry/finish points.
6. **Checkpointer:** implement (or adopt) Mongo checkpointer. Verify with mid-run crash simulation.
7. **Runner + API:** `WorkflowRunner.start/resume`, `runs.py` endpoints, `reports.py` endpoint, session status transitions.
8. **End-to-end test:** full mocked run through API; assert DB state.
9. **Live smoke:** run `scripts/run_workflow.py` against a real session (e.g., "Stripe", "https://stripe.com", "explore payments partnership"). Tune prompts.
10. **Polish:** structlog fields, error contract consistency, prompt files split + commented with intent.

---

## 17. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| LangGraph's Mongo checkpointer for our version doesn't exist / is buggy | Custom `BaseCheckpointSaver` impl is in scope as the default plan |
| Real LLM calls flaky / expensive in dev loop | All node tests use FakeLLMClient; live runs gated behind a script |
| OpenRouter gateway outage = total LLM outage | OpenRouter's own `models` fallback array routes around individual provider failures; gateway-level downtime is accepted risk, documented in `engineering-decisions.md` |
| Structured-output support varies across models behind OpenRouter | `OpenRouterClient` detects model capability and falls back to prompt-based JSON + Pydantic validation + 1 retry |
| Web scraping yields noisy data | Readability-style cleanup; cap source length; rely on search snippets as backup when fetch fails |
| Long runs block FastAPI worker | BackgroundTasks is fine for a 30–90s run; if it stretches, document as known limitation; future upgrade to ARQ/Celery in `engineering-decisions.md` |
| Token cost on retries | Strict structured output + single retry on schema failure; bounded research iterations |

---

## 18. Out of Scope for Part 3

- Streaming progress to the **frontend** (Part 4 — endpoint contract is fixed here, just not consumed).
- Frontend rendering of the report (Part 4).
- Follow-up chat (Part 5).
- Multi-user, auth, rate limits (Part 5 hardening).
- Background worker / queue infrastructure (BackgroundTasks is enough).

---

## 19. Definition of Done — Part 3

- [ ] `workflow/state.py` defines `GraphState` with reducers; tests cover merging semantics
- [ ] All 6 nodes implemented with focused prompts and unit tests using FakeLLM/FakeSearch
- [ ] `graph.py` assembles nodes + conditional edge from `quality_check`
- [ ] Mongo checkpointer round-trips a state snapshot; mid-run crash test passes
- [ ] `runner.start()` runs full workflow against fakes end-to-end inside pytest
- [ ] `runner.resume()` continues from last checkpoint after simulated failure
- [ ] `POST /api/sessions/{id}/run`, `GET /runs`, `GET /runs/{id}`, `GET /report` all behave per spec
- [ ] Events written to `workflow_runs.events` for every node start/finish/error
- [ ] Report doc has all 9 sections populated and validates against `ReportOut`
- [ ] `scripts/run_workflow.py` produces a real report against live providers
- [ ] `ruff check`, `pytest`, ≥80% line coverage on `app/workflow/`
- [ ] Standard error contract honored on all new routes
- [ ] camelCase ↔ snake_case bridge respected for all new models (asserted by at least one test)
