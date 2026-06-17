# Architecture

Argus researches a target company and produces a structured sales briefing. A
user creates a *session*, kicks off a LangGraph *workflow* that runs as a
background task, watches it progress live over SSE, reads the generated
nine-section *report*, and then *chats* with that report as grounded context.

---

## 1. System overview

```
                       camelCase JSON (RTK Query / fetch + SSE)
   ┌─────────────────┐  ───────────────────────────────────▶  ┌──────────────────┐
   │    Frontend     │                                          │     Backend      │
   │  Next.js 16     │  ◀───────────────────────────────────   │   FastAPI        │
   │  App Router     │     SSE: run events + chat deltas        │   (Uvicorn)      │
   │  RTK Query      │                                          └────────┬─────────┘
   └─────────────────┘                                                   │
                                                          ┌──────────────┼───────────────┐
                                                          ▼              ▼               ▼
                                                  ┌──────────────┐ ┌───────────┐ ┌──────────────┐
                                                  │  LangGraph   │ │  MongoDB  │ │  OpenRouter  │
                                                  │  workflow    │ │  (Motor)  │ │  + Tavily    │
                                                  │  (6 nodes)   │ │           │ │  (LLM/search)│
                                                  └──────────────┘ └───────────┘ └──────────────┘
```

**Component responsibilities**

- **Frontend (`frontend/`)** — Next.js App Router UI. Server-renders shells;
  all data flows through RTK Query (cache + invalidation) over a camelCase API.
  Live updates (workflow progress, chat tokens) arrive via SSE, not polling.
- **Backend (`backend/app/`)** — FastAPI. Thin route handlers → service layer →
  repository layer → Mongo. Owns the workflow runner, the event bus, the chat
  stream manager, and the error/rate-limit/metrics middleware.
- **Workflow (`backend/app/workflow/`)** — a LangGraph `StateGraph` of six nodes
  sharing one typed state, checkpointed to Mongo after every super-step.
- **Persistence** — MongoDB via Motor (async). Collections for sessions, runs,
  reports, chat messages, and the LangGraph checkpointer.
- **External** — OpenRouter is the single LLM gateway; Tavily (falling back to
  DuckDuckGo) is web search. Both sit behind client *protocols* so the whole
  graph runs offline under pytest with fakes.

**Layering rule (backend):** `api → services → repositories → db`. Routes never
touch Mongo directly; repositories never raise HTTP. Domain errors raised in
services map to the wire contract in `app/api/errors.py`.

---

## 2. Request flows

### Create a session

```
Browser → POST /api/sessions {companyName, website, objective}
  sessions.py → session_service.create_session → session_repo.create → Mongo
  ← 201 SessionOut (camelCase)
```

### Run the workflow (background + SSE)

```
Browser → POST /api/sessions/{id}/run
  workflow_service.start_run:
    - guard: session exists, no active run
    - workflow_repo.create_run  (status=running)
    - session_repo.update_status(running)
    - BackgroundTasks.add_task(runner.execute)
  ← 202 { runId, status:"running" }       (returns immediately)

Browser → GET /api/sessions/{id}/runs/{runId}          (seed first paint)
Browser → GET /api/sessions/{id}/runs/{runId}/events?since_seq=N   (SSE)

Background: runner.execute
  bind RunContext (run_id, seq counter, event bus, cost cap)
  graph.ainvoke(initial, {thread_id: session_id})
    each node: emit node_started → node_output* → node_finished
      every emit() → append to workflow_runs.events  AND  event_bus.publish
  on success: mark_completed (+ persist raw_sources) → emit run_completed
  on error:   mark_failed → emit run_failed
```

The SSE handler subscribes to the bus, **backfills** stored events with
`seq > since_seq`, then tails live events — deduplicating by `seq`. A finished
run closes the stream right after backfill.

### Follow-up chat (grounded, streaming)

```
Browser → POST /api/sessions/{id}/chat {content}
  chat_service.post_message:
    - require report (else 409 chat_no_report)
    - load recent history (sliding window of 10)
    - persist user message (complete) + assistant message (streaming)
    - asyncio.create_task(_generate)         ← starts immediately
  ← 200 { messageId }

Browser → GET /api/sessions/{id}/chat/{messageId}/stream?since_seq=N  (SSE)

Background: _generate
  raw_sources ← latest completed run
  select_sources (BM25) → build messages (preamble + report md + source pack + history)
  llm.stream(messages) → publish each token delta to the stream manager
  on done: parse [i] citations → finalize_message → publish "done" frame
```

Same `since_seq` resumability as the workflow stream: a refresh mid-generation
replays buffered token deltas and tails the rest.

---

## 3. The LangGraph workflow

```
              ┌─────────┐   needs_more_research?  (loop, capped)
   START ───▶ │ planner │ ◀──────────── yes ───────────────┐
              └────┬────┘  turn missing_areas into          │
                   ▼       fresh gap-closing questions       │
            ┌────────────┐                                   │
            │ researcher │  search + fetch + clean → raw_sources
            └─────┬──────┘                                   │
                  ▼                                          │
        ┌──────────────────┐                                │
        │ signal_extractor │  pull funding/hiring/product/… signals
        └────────┬─────────┘                                │
                 ▼                                          │
            ┌──────────┐                                    │
            │ analyst  │  synthesize overview/products/customers/risks
            └────┬─────┘                                    │
                 ▼                                          │
         ┌───────────────┐                                 │
         │ quality_check │ ──────────── yes ───────────────┘
         └───────┬───────┘
                 │ no
                 ▼
            ┌──────────┐
            │ reporter │  emit the nine-section ReportDraft → reports
            └────┬─────┘
                 ▼
                END
```

- **Shared state** (`app/workflow/state.py`, `GraphState` TypedDict): inputs
  (`company_name`, `website`, `objective`), accumulated outputs (`plan`,
  `raw_sources`, `extracted_signals`, `analysis`, `quality`, `report`), and
  control (`retry_counts`, `errors`, `research_iteration`,
  `researched_question_ids`). Channels with reducers *accumulate* — e.g.
  `raw_sources` merges and de-dupes by URL across research loops; plain channels
  are last-write-wins.
- **Conditional routing:** `quality_check` returns `needs_more_research` plus
  `missing_areas`; the conditional edge loops back to `planner` — which converts
  those gaps into *new* sub-questions so the next research pass has something
  fresh to chase (looping straight to `researcher` would re-run it against the
  already-researched plan and gather nothing). Bounded by
  `workflow_max_research_iterations`, and only taken when `missing_areas` is
  non-empty; otherwise proceeds to `reporter`.
- **Intermediate outputs:** each node emits `node_output` events the UI renders
  live (sub-questions, sources found, signals, the analysis block, the verdict).
- **Failure handling:** per-node retry policy (`workflow_node_retry_limit`);
  an uncaught node error fails the run with a typed `WorkflowError`.
- **Capabilities, not clients:** nodes are closures over `WorkflowDeps`
  (`llm`, `search`, `fetcher`, `settings`) — protocols, so tests inject fakes.
  Deps never enter `GraphState` (which must stay serializable for checkpointing).

---

## 4. Persistence

MongoDB, accessed via Motor. Documents are snake_case; the wire is camelCase
(see §5). Indexes are created idempotently on startup (`ensure_indexes`).

### `sessions`
| field | type | notes |
|---|---|---|
| `_id` | ObjectId | wire `id` |
| `company_name`, `website`, `objective` | str | inputs |
| `status` | enum | `created`/`running`/`completed`/`failed`/`interrupted` |
| `chat_suggestions` | str[] \| absent | cached starter prompts |
| `created_at`, `updated_at` | datetime | ms precision |

Indexes: `created_at desc`, `status`.

### `workflow_runs`
| field | type | notes |
|---|---|---|
| `_id` | ObjectId | wire `id` (the runId) |
| `session_id` | str | |
| `status` | enum | `running`/`completed`/`failed` |
| `node_status` | map | node → `pending`/`running`/`done`/`failed` |
| `events` | obj[] | full timeline (append-only) |
| `raw_sources` | obj[] | fetched sources (persisted on completion; fuels chat) |
| `error` | obj \| null | `{code, message, traceback}` |
| `started_at`, `finished_at` | datetime | |

Indexes: `session_id`, `started_at desc`.

### `reports` (one per session)
The nine sections: `company_overview`, `products_and_services`,
`target_customers`, `business_signals[]`, `risks_and_challenges`,
`suggested_discovery_questions[]`, `suggested_outreach_strategy`, `unknowns`,
`sources[]`, plus `session_id`, `created_at`. Unique index on `session_id`.

### `chat_messages`
| field | type | notes |
|---|---|---|
| `_id` | ObjectId | wire `id` |
| `session_id`, `role`, `content` | | role ∈ user/assistant/system |
| `citations` | obj[] | `{source_index, url, title, snippet}` |
| `status` | enum | `streaming`/`complete`/`failed` |
| `model`, `tokens_in`, `tokens_out`, `cost_usd` | | analytics |
| `created_at`, `finished_at`, `error` | | |

Index: `(session_id, created_at)`.

### Checkpointer
`workflow_checkpoints`, `workflow_checkpoint_blobs`, `workflow_checkpoint_writes`
— a custom `BaseCheckpointSaver` implementation keyed by
`thread_id == session_id` (see §7).

---

## 5. Naming bridge

One rule: **camelCase on the wire, snake_case everywhere inside the backend and
Mongo.** The single source of truth is `app/models/base.py`:

```python
class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,   # snake_case attr → camelCase alias
        populate_by_name=True,      # accept either on input
        from_attributes=True,
    )
```

Every request/response model inherits `ApiModel`; routes serialize with
`response_model_by_alias=True`. Handlers only ever touch snake_case attributes.
Repositories convert `_id → id` at the edge so `ObjectId` never reaches Pydantic.

**Caveat (intentional):** the bridge renames *field keys* only. Wire *values*
that are enums or event payload keys stay snake_case — e.g. event `kind` is
`run_started`, node names are `signal_extractor`. The frontend treats those as
opaque string constants.

---

## 6. Event model — why SSE + `sinceSeq`

Both live feeds (workflow progress, chat tokens) are **one-way server→client**
streams, so Server-Sent Events fit better than WebSockets (no client→server
channel needed, native reconnect, plain HTTP, proxy-friendly). Polling was
rejected: it's chatty and adds latency to a token stream.

The keystone is a per-run monotonic **sequence number**. Every event carries a
`seq`; the durable record lives in `workflow_runs.events` (Mongo is the source of
truth). The stream endpoint takes `?since_seq=N` and:

1. **subscribes** to the in-process bus *before* reading backfill (closes the
   race where an event lands between snapshot and subscription),
2. **backfills** stored events with `seq > N`,
3. **tails** live events, dropping anything `≤ N` or already sent.

A dropped connection reconnects with the latest `seq`, so there's never a gap or
a duplicate. The chat stream mirrors this exactly with token-delta `seq`s.

> Trade-off: the event bus and chat stream buffers are **in-process**. They don't
> survive a multi-replica deploy — that needs Redis pub/sub (see
> `engineering-decisions.md`). Mongo durability means a reconnect still recovers.

---

## 7. Recoverability

State is checkpointed to Mongo after every LangGraph super-step via a custom
`MongoCheckpointer` (a `BaseCheckpointSaver`), keyed by
`thread_id == session_id`. Two recovery paths:

- **Resume after failure / interruption.** A failed run leaves the session
  `failed`; `POST /run/resume` re-invokes the graph with `None` input, so
  LangGraph continues from the last checkpoint instead of re-running completed
  nodes. **Graceful shutdown** (SIGTERM) flips any `running` session to
  `interrupted` (a resumable terminal status) and cancels in-flight chat
  generation, so a deploy/restart never strands a run.
- **Refresh / reconnect mid-run.** The UI seeds from the persisted run snapshot,
  then attaches the SSE stream at the last `seq` (§6). No work is lost or redone.

What's **not** guaranteed: exactly-once external side effects (a node that
crashed mid-LLM-call may re-issue that call on resume), and cross-replica live
streaming (in-process bus).

---

## 8. Deployment shape (illustrative)

```
              ┌──────────────┐        ┌──────────────────────┐      ┌─────────────┐
  Users ────▶ │ AWS Amplify  │ ─────▶ │  FastAPI (Uvicorn)   │ ───▶ │ Mongo Atlas │
              │ (Next.js)    │  HTTPS │  on AWS EC2 + nginx   │      └─────────────┘
              └──────────────┘        └──────────┬───────────┘
                                                 └────────▶ OpenRouter / Tavily
```

- **Frontend:** AWS Amplify (Next.js build; RTK Query points to the EC2 API base URL).
- **Backend:** a single Uvicorn instance on AWS EC2 behind nginx (reverse proxy + TLS termination).
- **DB:** MongoDB Atlas.
- **CI:** GitHub Actions runs `ruff`, `mypy`, `pytest`, `eslint`, `tsc`, `build`.

The current build is single-worker and single-tenant by design (see
`engineering-decisions.md` for the debt and the scale-out plan).