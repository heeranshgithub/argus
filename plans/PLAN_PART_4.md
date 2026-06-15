# PLAN — Part 4: Real-Time Progress & Report UI

**Goal:** Make the workflow visible. A user clicks "Run Research", watches each LangGraph node light up in real time with status, timings, and intermediate outputs, and ends up reading a beautifully rendered report with all 9 required sections. Failed runs can be retried or resumed from the last checkpoint.

This part is pure user-facing payoff. Part 3 already produces the data; Part 4 finishes the SSE plumbing on the backend and builds the frontend that consumes it.

**Exit criteria:**
- Clicking "Run Research" on a session opens a live progress view where every node transitions `pending → running → done/failed` without a refresh.
- Intermediate outputs (plan sub-questions, source URLs found, signals extracted, quality verdict) appear inline as nodes finish.
- The full report renders with all 9 sections and clickable sources after `run_completed`.
- Refreshing the page mid-run restores the exact same UI state via event backfill, then resumes the live stream seamlessly.
- A failed run shows a clear error state with "Retry" (new run) and "Resume" (from checkpoint) actions.
- Responsive from 360px → 1440px+; passes `eslint`, `tsc --noEmit`, basic a11y checks.

---

## 1. Architecture: How a Run Renders

```
   ┌─ first paint ──────────────────────────────────────────────┐
   │                                                             │
   │  GET /api/sessions/{id}/runs/{runId}                        │
   │   → seed UI from persisted events array (replay)            │
   │                                                             │
   │  GET (SSE) /api/sessions/{id}/runs/{runId}/events?sinceSeq= │
   │   → append live events with seq > last replayed seq         │
   │                                                             │
   │  on 'run_completed':                                        │
   │     GET /api/sessions/{id}/report → render full report      │
   │                                                             │
   └─────────────────────────────────────────────────────────────┘
```

The `sinceSeq` parameter is the keystone. It guarantees:
- No event is missed if SSE attaches a moment after a node finished.
- No event is duplicated if a replayed event also arrives on the stream.
- A page refresh during a long run rebuilds state in one round-trip then attaches live.

---

## 2. Backend: SSE Endpoint

### 2.1 Route
- `GET /api/sessions/{session_id}/runs/{run_id}/events?since_seq=<int>` (default 0).
- Content-Type: `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- Each frame: `event: <kind>\ndata: <json>\n\n` where `<json>` is the camelCase-serialized `WorkflowEvent`.
- Keep-alive comment line `: keep-alive\n\n` every 15s so proxies don't reap idle connections.
- Server-side close on `run_completed` or `run_failed` after flushing those terminal events.

### 2.2 Implementation (`backend/app/api/events.py`)
```python
@router.get("/sessions/{session_id}/runs/{run_id}/events")
async def stream_events(session_id, run_id, since_seq: int = 0, db = Depends(get_db)):
    async def gen():
        # 1) Backfill: pull events from workflow_runs where seq > since_seq, in order
        run = await workflow_repo.get_run(db, session_id, run_id)
        if not run: raise SessionNotFound(...)
        for ev in run["events"]:
            if ev["seq"] > since_seq:
                yield sse_frame(ev)
        # 2) If run already finished while we were paginating, terminal event is in the backfill — stop
        if run["status"] in ("completed", "failed"):
            return
        # 3) Otherwise attach to the live queue
        queue = event_bus.subscribe(run_id)
        try:
            last_keepalive = time.monotonic()
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15)
                    yield sse_frame(ev)
                    if ev["kind"] in ("run_completed", "run_failed"):
                        return
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
```

### 2.3 In-process event bus (`backend/app/workflow/event_bus.py`)
- Already partially implemented in Part 3 (per-session queue inside `events.emit`). Promote to a module-level `EventBus` with `subscribe(run_id) -> asyncio.Queue`, `publish(run_id, event)`, `unsubscribe(run_id, queue)`.
- Multiple subscribers per `run_id` allowed (two browser tabs both watching).
- A queue receives only events emitted *after* it subscribed — the SSE handler's backfill loop above fills the gap.
- Bounded queue (`maxsize=512`) with drop-oldest policy on overflow + a `dropped_events` counter logged via structlog.

### 2.4 Connection lifecycle
- Disconnect detection via `await request.is_disconnected()` checked on each yield — the handler exits cleanly.
- Idempotent: no side effects on subscribe/unsubscribe; the workflow keeps running regardless of client presence.

### 2.5 Tests (`backend/tests/test_events_sse.py`)
- Start a fake run that emits 3 events with a delay between them; assert client receives all 3 in order with the correct `event:` types.
- Subscribe with `since_seq=2`; assert only events with `seq > 2` are delivered (backfill correctness).
- Subscribe *after* run completes; assert backfill replays everything and the stream closes immediately.
- Two concurrent subscribers; assert both receive every event.
- Bounded queue: flood 1000 events at one slow consumer; assert no crash, `dropped_events` increments, structlog warning fired.

---

## 3. Frontend: Data Layer for Runs

### 3.1 New files
```
frontend/src/
  services/
    runs.ts                       # RTK Query endpoints for runs + report
  hooks/
    use-run-stream.ts             # SSE hook with backfill+live merging
    use-run-state.ts              # selector that derives node statuses + outputs from events
  types/
    workflow.ts                   # WorkflowEvent, WorkflowRun, NodeStatus
    report.ts                     # Report + nested types (mirrors backend ReportOut, camelCase)
  lib/
    sse.ts                        # tiny EventSource wrapper with auto-reconnect + sinceSeq
    workflow-graph.ts             # static node metadata (order, labels, icons, expected outputs)
```

### 3.2 Types (`types/workflow.ts`)
```ts
export type NodeName =
  | 'planner' | 'researcher' | 'signalExtractor'
  | 'analyst' | 'qualityCheck' | 'reporter';

export type NodeStatus = 'pending' | 'running' | 'done' | 'failed';

export type EventKind =
  | 'runStarted' | 'runCompleted' | 'runFailed'
  | 'nodeStarted' | 'nodeFinished' | 'nodeErrored' | 'nodeOutput';

export interface WorkflowEvent {
  runId: string;
  sessionId: string;
  node: NodeName | null;       // null for run-level events
  kind: EventKind;
  payload: Record<string, unknown>;
  ts: string;                   // ISO
  seq: number;
}

export interface WorkflowRun {
  id: string;
  sessionId: string;
  status: 'running' | 'completed' | 'failed';
  startedAt: string;
  finishedAt: string | null;
  events: WorkflowEvent[];
  error: { code: string; message: string } | null;
}
```

> Naming: backend uses `node_started`; frontend uses `nodeStarted`. The `ApiModel` `alias_generator=to_camel` from Part 1 handles this automatically — no manual mapping table.

### 3.3 RTK Query (`services/runs.ts`)
- `startRun: mutation<{ runId: string }, string /* sessionId */>` → `POST /sessions/{id}/run`. Invalidates `['Session', { type: 'Session', id }]`.
- `resumeRun: mutation<{ runId: string }, string>` → `POST /sessions/{id}/run/resume`.
- `getRun: query<WorkflowRun, { sessionId: string; runId: string }>` — used by the SSE hook to seed.
- `getLatestRun: query<WorkflowRun | null, string>` — convenience for the detail page.
- `getReport: query<Report, string>` — provides `[{ type: 'Report', id: sessionId }]`.

### 3.4 SSE wrapper (`lib/sse.ts`)
```ts
export function openEventStream(
  url: string,
  opts: { onEvent: (e: WorkflowEvent) => void; onError?: (err: unknown) => void; onClose?: () => void }
): () => void;
```
- Native `EventSource` if available; auto-reconnect with exp backoff (1s, 2s, 4s, cap 10s) on transient errors.
- Tracks the last seen `seq`; on reconnect, rewrites the URL `since_seq` query param so we never miss an event.
- Returns an `unsubscribe()` cleanup function.

### 3.5 `use-run-stream` hook
- Inputs: `sessionId`, `runId`.
- Steps:
  1. Fire `getRun` query → seed local state with persisted events.
  2. Call `openEventStream(.../events?since_seq=<lastSeenSeq>)` → push new events via dispatch into a small slice or via `useReducer`.
  3. On `runCompleted` → trigger `getReport` query refetch.
  4. On `runFailed` → expose `error` to caller.
  5. Cleanup on unmount.
- Output: `{ events, nodeStatuses, status, error, lastSeq, isStreaming }`.

### 3.6 `use-run-state` selector
- Pure function from `events[]` → derived view model:
  ```ts
  interface RunView {
    nodes: Record<NodeName, {
      status: NodeStatus;
      startedAt?: string;
      finishedAt?: string;
      durationMs?: number;
      output?: NodeOutputPreview;   // discriminated union by NodeName
      error?: { code: string; message: string };
    }>;
    overall: { status; startedAt; finishedAt; durationMs };
  }
  ```
- `NodeOutputPreview` is typed per node:
  - `planner` → `{ subQuestions: SubQuestion[] }`
  - `researcher` → `{ sourcesAdded: number; sampleUrls: string[]; iteration: number }`
  - `signalExtractor` → `{ signalCount: number; categories: string[] }`
  - `analyst` → `{ overviewPreview: string; risksCount: number }`
  - `qualityCheck` → `{ coverageScore: number; confidenceScore: number; needsMoreResearch: boolean; missingAreas: string[] }`
  - `reporter` → `{ reportId: string }`

---

## 4. Frontend: UI Components

### 4.1 Layout on `/sessions/[id]`
Two-column responsive grid (`lg:` breakpoint):
- **Left (sticky on desktop, top on mobile):** `SessionDetailHeader` + `RunControlPanel`.
- **Right:** tabbed area with `Progress`, `Report`, `Chat` (Part 5).
- Below `lg`, the tabs become the primary view; the header collapses to a compact card above them.

### 4.2 `RunControlPanel`
- States:
  - **No run yet:** "Run Research" primary button (calls `startRun`).
  - **Running:** disabled button "Running… (n of 6 nodes)" + small spinner. Shows overall elapsed time (ticking client-side).
  - **Completed:** "Re-run" button (creates a new run) + "View Report" tab cue.
  - **Failed:** error alert with `code`/`message`, two buttons: "Resume" (calls `resumeRun`) and "Start Over" (new run).

### 4.3 `WorkflowProgress` (the centerpiece)
File: `components/workflow/workflow-progress.tsx`. Renders a vertical timeline of all 6 nodes in canonical order from `workflow-graph.ts`.

Each node card has:
- Icon (Lucide: `compass` planner, `search` researcher, `signpost` signalExtractor, `brain-cog` analyst, `shield-check` qualityCheck, `file-text` reporter).
- Title + one-line description.
- Status pill (`StatusBadge` from Part 2 — reused).
- Duration ("1.4s") once finished; live elapsed once started.
- Expandable details (`<Collapsible>` shadcn) showing the node's typed `output` preview (see §3.6).
- Connector line between cards; the line animates (subtle pulse) while the *next* node is running.
- A small "iteration 2" badge appears on `researcher` if Quality Check looped back.

#### Animations
- Status transitions use `framer-motion` (single small dep) for color and pulse — keep it tasteful; no spinning logos.
- Respect `prefers-reduced-motion`.

### 4.4 Node-specific output panels
Each is a small, self-contained component, kept in `components/workflow/outputs/`:
- `planner-output.tsx` — bullet list of sub-questions with rationale tooltip.
- `researcher-output.tsx` — count + sample URL chips (favicon via `https://www.google.com/s2/favicons?domain=...`); "iteration N" tag.
- `signal-extractor-output.tsx` — grouped by category, each signal shows summary + evidence links.
- `analyst-output.tsx` — collapsed sections (overview, risks count) with "read more" → opens a side `Sheet`.
- `quality-check-output.tsx` — two horizontal progress bars (coverage, confidence), missing-areas chips, route-decision badge ("→ research again" or "→ finalize").
- `reporter-output.tsx` — single CTA: "View Report" → switches to the Report tab.

### 4.5 `ReportView`
File: `components/report/report-view.tsx`. Renders the 9 sections in a fixed order with anchored navigation:

```
┌────────────────────────────────┐
│  Company Overview              │ ← anchor: #overview
├────────────────────────────────┤
│  Products & Services           │
├────────────────────────────────┤
│  Target Customers              │
├────────────────────────────────┤
│  Business Signals (grouped)    │
├────────────────────────────────┤
│  Risks & Challenges            │
├────────────────────────────────┤
│  Discovery Questions           │
├────────────────────────────────┤
│  Outreach Strategy             │
├────────────────────────────────┤
│  Unknowns                      │
├────────────────────────────────┤
│  Sources (with usedIn chips)   │
└────────────────────────────────┘
```

Components:
- `report-section.tsx` — generic section wrapper with anchor + copy-link button.
- `report-toc.tsx` — sticky right rail on `xl:` with smooth-scroll links.
- `business-signals-list.tsx` — collapsible cards per category, badge for `confidence`, evidence URLs.
- `discovery-questions-list.tsx` — numbered list, each with rationale.
- `source-card.tsx` — favicon, title, url (host highlighted), chips of section names it was cited in.
- `report-empty.tsx` — placeholder when no report yet ("Run research to generate a report").
- `report-loading.tsx` — skeleton matching the section layout.

Markdown formatting: keep it plain — the report fields are strings/lists from a typed schema, not free-form markdown. If `companyOverview` happens to contain newlines, render with `whitespace-pre-wrap`. No markdown parser needed.

Actions:
- **Copy as Markdown** button: client-side stringifier — no backend round-trip.
- **Print / Save as PDF** uses native `window.print()` with a print-friendly stylesheet (`@media print`).

### 4.6 Error states
- Network/SSE error: Sonner toast + inline "Connection lost — retrying…" pill at the top of the progress timeline. The auto-reconnect handles it; user takes no action.
- Run failed: a `RunFailedCard` at the top of the progress timeline, plus the failed node card shows its `error.message` expanded by default.
- Missing report when status is `completed` (shouldn't happen): show "Report not found — please re-run" with the rerun action.

### 4.7 Tabs
ShadCN `Tabs`. URL-synced via the App Router (`?tab=progress|report|chat`) so refreshes preserve the active tab and links are shareable.

---

## 5. State Reconstruction & Edge Cases

| Scenario | Behavior |
|----------|----------|
| User runs research, never refreshes | Pure live stream after initial empty `getRun` (backfill is empty) |
| User refreshes mid-run | `getRun` backfill restores all node statuses + outputs to the second, SSE resumes from `lastSeq` |
| User refreshes after completion | `getRun` returns `completed` + full events; SSE handler closes immediately; report fetched via `getReport` |
| Two tabs open | Both subscribe; both update independently (no cross-tab coordination needed) |
| Run fails on node X | Node X card shows error; downstream cards stay `pending`; `RunControlPanel` switches to resume/retry |
| User clicks Resume | `POST /run/resume` returns same `runId`; UI clears the failure card and reattaches to the stream |
| User clicks Re-run | `POST /run` returns new `runId`; UI swaps to the new run; old run remains accessible via `getRun` (history) |
| Connection drops | `sse.ts` reconnects with `since_seq=lastSeq`; user sees a small pill briefly |
| Slow network: SSE buffered | Backend keep-alive every 15s prevents proxies from killing the stream |

---

## 6. Responsive & Accessibility

- Breakpoints: mobile 360+, tablet 768+, desktop 1024+, wide 1440+.
- Sticky elements (toc, control panel) become inline at `< lg`.
- All status changes announce via `aria-live="polite"` region (one per node, throttled to one announcement per status change).
- Color isn't the only signal: every status pill also has an icon (`Loader2`, `Check`, `X`, `Clock`).
- Keyboard navigation: tabs, collapsibles, anchors all reachable via Tab/Enter.
- Focus ring visible (Tailwind `focus-visible:` utilities).
- Contrast verified for status colors against both light and dark themes.

---

## 7. Step-by-Step Execution Order

1. **Backend SSE** — implement `event_bus.py` upgrades, `events.py` route, tests. Verify with `curl -N`.
2. **Frontend data layer** — `services/runs.ts`, `types/workflow.ts`, `lib/sse.ts`, `hooks/use-run-stream.ts`, `hooks/use-run-state.ts`. Unit-test the selectors with synthetic event arrays.
3. **`RunControlPanel`** — start / resume / re-run wiring with the four state branches.
4. **`WorkflowProgress` shell** — static rendering of all 6 node cards from `workflow-graph.ts`, no live data yet.
5. **Wire live data** — connect `useRunStream` to the progress component; verify mid-run refresh, two-tab, and reconnect cases manually.
6. **Node output panels** — one component per node, plugged into the expandable region.
7. **`ReportView`** — sections, TOC, sources, copy/print actions.
8. **Tabs + URL sync** — `?tab=` query param, default tab logic (progress while running, report after completion).
9. **Responsive + a11y pass** — resize sweep, keyboard sweep, screen-reader spot check.
10. **Manual smoke** — run end-to-end against the live LangGraph workflow from Part 3 with OpenRouter; iterate on copy/spacing only.

---

## 8. Out of Scope for Part 4

- Follow-up chat (Part 5).
- Editing or deleting runs/reports (not required).
- Server-Sent Events authentication (single-user demo; CORS handles it).
- Real-time collaboration / presence indicators.
- Internationalization.

---

## 9. Definition of Done — Part 4

- [ ] `GET /api/sessions/{id}/runs/{runId}/events` streams `text/event-stream`, supports `since_seq`, sends keep-alives, closes on terminal events
- [ ] Backend tests cover backfill correctness, multi-subscriber, post-completion subscribe, queue overflow
- [ ] `lib/sse.ts` reconnects with `since_seq` after transient errors
- [ ] `useRunStream` seeds from `getRun`, attaches live, merges without duplicates, surfaces error
- [ ] `WorkflowProgress` shows live status, durations, and node-specific outputs for all 6 nodes
- [ ] Conditional loop-back from `qualityCheck` to `researcher` renders correctly (iteration badge, second activation)
- [ ] `RunControlPanel` handles all four states (idle / running / completed / failed) with correct actions
- [ ] `ReportView` renders all 9 sections with sources cross-referenced and copy/print actions
- [ ] Page refresh mid-run rebuilds identical UI state via backfill, then continues live with no missed/dup events
- [ ] Layout responsive 360px → 1440px; passes basic keyboard and `aria-live` checks
- [ ] `eslint`, `tsc --noEmit`, `pytest`, `ruff check` all green
- [ ] Manual demo: cold start → create session → run → watch progress → read report works end-to-end with the real OpenRouter-backed workflow

---

## 10. Implementation Notes & Deviations

Recorded during implementation — where the build differs from the plan above, and why.

### 10.1 Wire format is snake_case for *values*, not just camelCase fields
§3.2 sketched event `kind`/`node` values and `nodeStatus`/`payload` keys as camelCase (e.g. `nodeStarted`, `signalExtractor`) and assumed the `ApiModel` `alias_generator` would produce them. It won't: Pydantic's alias generator renames **model field names only** — not enum string *values*, not `dict[str, …]` *keys*, and not free-form `payload` contents.

So object fields are camelCase as expected (`runId`, `sessionId`, `nodeStatus`, `startedAt`), but these stay snake_case on the wire:
- `kind` value → `"node_started"`, `"run_completed"`, … (EventKind values)
- `node` value → `"signal_extractor"`, `"quality_check"`, `"__run__"`
- `nodeStatus` keys → `planner`, `signal_extractor`, `quality_check`, … (dict keys)
- `payload` keys → `new_questions`, `new_sources`, `needs_more_research`, `report_id`, `duration_ms`, … (set via each node's `ev.set_preview(...)`)

The frontend types (`frontend/src/types/workflow.ts`) keep camelCase interface fields and use snake_case only in the string-literal unions (`NodeName`, `EventKind`) and when indexing the dynamic dicts. The backend was **not** changed: Part 3's `test_runs_api.py` locks in `event: run_started` and `nodeStatus.reporter == "done"`, so the camelCase-everything approach would have broken existing tests for no gain.

### 10.2 Node output panels render the metrics the nodes actually emit
§3.6 / §4.4 sketched richer per-node previews (planner sub-question text, researcher sample URLs + favicons, signal categories, analyst overview text, quality-check missing-areas chips). The Part 3 nodes only emit compact counters via `set_preview`, so the panels render what's actually available rather than inventing empty fields:
- `planner` → `new_questions`, `total`
- `researcher` → `new_sources`, `questions_researched`, `errors` (+ iteration note when looped)
- `signal_extractor` → `signals`
- `analyst` → `overview_chars`
- `quality_check` → `coverage`, `confidence` bars + route-decision badge (from `needs_more_research`)
- `reporter` → `report_id`, `sections`, `sources` + "View report" CTA

The full sub-question text, source URLs, signals, and analysis all appear in the **report** (§4.5) once the run completes — that's where the rich data lives. If richer live previews are wanted later, the change is on the backend (`ev.set_preview(...)` / `ev.output(...)`), and these panels read it for free.

### 10.3 Animations use CSS/Tailwind, not framer-motion
§4.3 named `framer-motion`. To avoid a new dependency, status pulses and transitions use Tailwind utilities + `tw-animate-css` (already installed), with `motion-reduce:` variants for `prefers-reduced-motion`.

### 10.4 UI primitives use the `radix-ui` umbrella package
`tabs`, `collapsible`, `tooltip`, `progress` are built on the already-installed `radix-ui` umbrella (re-exports every primitive); `sheet` reuses `@radix-ui/react-dialog`. No new Radix packages were added.

### 10.5 Status — not yet done
- **DoD item 10 (manual end-to-end smoke against the live OpenRouter workflow)** is NOT done: it needs a running Mongo + an OpenRouter API key, which weren't available in this environment. Everything else is green (`pytest` 90 passed, `ruff`, `tsc --noEmit`, `eslint`, `next build`).
- Work is on the `dev` branch, **uncommitted**.
