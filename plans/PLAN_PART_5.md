# PLAN — Part 5: Follow-Up Chat, Hardening & Docs

**Goal:** Ship the product. Layer follow-up chat on top of the completed report, harden both apps for "production-grade" judgment, write the four required documents, record a demo, and (optionally) deploy. After this part, the assignment is submittable.

This part is the difference between "works on my machine" and "I'd hand this to my boss." It also covers the two non-code rubric chunks: **Production Readiness (10%)** and **Product & Business Thinking (15%)** — 25% of the grade lives in Part 5.

**Exit criteria:**
- Follow-up chat works against the report + workflow state with citations linking back to sources.
- Both apps survive a hostile demo (bad inputs, network drops, missing keys) with clean error UX.
- All four required docs (`README.md`, `architecture.md`, `engineering-decisions.md`, `product-improvements.md`) exist, are complete, and pass a read-through test by a stranger.
- One-click local setup verified from a fresh clone.
- A demo video (≤5 min) and/or a hosted deployment URL exist.
- Submission checklist (§11) fully ticked.

---

## 1. Follow-Up Chat

### 1.1 UX shape
Lives in the third tab on `/sessions/[id]` (alongside Progress and Report). Standard chat surface:

- **Message list** (oldest → newest, auto-scroll on new) with role-styled bubbles (user right, assistant left), timestamps, and a **citations row** under each assistant message rendering chips like `[1] stripe.com/about` that scroll the Report tab to the referenced source on click.
- **Composer** at the bottom: multi-line `Textarea`, Enter to send / Shift+Enter newline, attached-file picker reserved as a future hook (disabled).
- **Streaming**: the assistant message appears immediately as an empty bubble with a typing indicator, then fills token-by-token via SSE.
- **Suggested prompts** (3 chips) on first load, generated server-side from the report (e.g., "What's their biggest growth signal?", "Who should I email first?", "What objections should I prepare for?"). Clicking a chip pre-fills the composer.
- **Empty state**: when no chat history and report isn't ready yet, the tab shows "Run research first to unlock chat" with a CTA back to the Progress tab.
- **Error state**: failed assistant message shows a "Retry" inline action; user message is preserved and editable.

### 1.2 Data model (`chat_messages` collection)
```
_id, session_id, role: 'user' | 'assistant' | 'system',
content: str,
citations: [{source_index: int, url: str, title: str, snippet: str}],
created_at, finished_at | null,
status: 'streaming' | 'complete' | 'failed',
model: str | null,        # OpenRouter model slug used (for analytics)
tokens_in: int | null, tokens_out: int | null, cost_usd: float | null,
error: {code, message} | null
```
Indexes: `(session_id: 1, created_at: 1)`.

`role: 'system'` is reserved for an initial setup message we hide from the UI but persist for auditability.

### 1.3 RAG construction (the AI engineering bit)
Chat is **grounded** in three things assembled per turn:

1. **System preamble** — fixed: "You are Argus, a sales research copilot. Answer using ONLY the provided sources. If unknown, say so. Cite sources by index."
2. **Report context** — the structured `ReportOut` serialized as compact markdown (≈1–2k tokens). Always included so the model has the full picture.
3. **Source pack** — the top N (default 6) raw sources from `workflow_runs.raw_sources` selected for relevance:
   - For the **first** user turn, simple TF-IDF / BM25 over `(question + objective)` against `source.title + source.snippet + source.content[:1500]` (no embedding model required — keeps deps simple, latency low, results good enough for ≤50 sources). Use `rank-bm25` (5 KB pure-Python).
   - For follow-up turns, include sources cited in the **last 2 assistant turns** + top-3 fresh BM25 hits for the new question.
4. **History** — last 10 messages (sliding window) appended after the source pack.

Each source is rendered with an explicit `[i]` index in the prompt so the model can cite as `[i]`. The renderer post-processes the streamed text to map `[i]` back to URLs for the UI citations row.

### 1.4 API
- `POST /api/sessions/{id}/chat` — body `{ content: str }`, returns 200 with `{ messageId: str }` immediately; the assistant response streams via SSE.
- `GET /api/sessions/{id}/chat` — paginated history (most recent N, with cursor).
- `GET /api/sessions/{id}/chat/{messageId}/stream` — SSE stream of token deltas + final citations, mirroring the workflow SSE pattern (with `sinceSeq`-style resumability for refreshes mid-stream).
- `POST /api/sessions/{id}/chat/{messageId}/retry` — regenerates the last assistant message (deletes prior failed/complete and starts a new one with same user input).
- `GET /api/sessions/{id}/chat/suggestions` — returns the 3 starter chips (LLM-generated from report, cached on the session).

Error contract: same `{ error: { code, message } }` shape; codes include `chat_no_report`, `chat_rate_limited`, `chat_provider_error`.

### 1.5 Backend layout additions
```
backend/app/
  api/chat.py
  services/chat_service.py
  retrieval/
    __init__.py
    bm25.py                 # thin wrapper around rank-bm25
    pack.py                 # assemble (report_md, source_pack, history) → prompt parts
  models/chat.py
  repositories/chat_repo.py
backend/tests/
  test_chat_api.py
  test_chat_retrieval.py
```

### 1.6 Frontend layout additions
```
frontend/src/
  app/sessions/[id]/components/
    chat-tab.tsx
  components/chat/
    chat-message-list.tsx
    chat-bubble.tsx
    chat-citations.tsx
    chat-composer.tsx
    chat-suggested-prompts.tsx
    chat-empty.tsx
  hooks/
    use-chat-stream.ts        # mirrors useRunStream shape
  services/
    chat.ts                   # RTK Query endpoints
  schemas/
    chat.ts                   # Zod for outbound message
```

### 1.7 Tests
- `test_chat_retrieval.py` — fixture of 20 sources + 5 queries; assert BM25 top-K matches expected rank.
- `test_chat_api.py` — happy path stream, refresh mid-stream resumes, retry replaces last message, missing-report returns `chat_no_report`.
- Frontend: render a fake `useChatStream` returning canned tokens, assert citations chips link to the Report tab anchor.

---

## 2. Production Hardening

Targeted at the **Production Readiness (10%)** rubric line. Scope kept to what a single engineer can finish in the time box.

### 2.1 Backend
- **Request IDs**: `X-Request-ID` middleware (Part 1 stub) is now load-bearing — bound into every structlog event for the request and surfaced in error responses (`error.details.requestId`).
- **Structured logs**: confirm all log calls use `structlog`, no raw `print`. JSON output in `env=prod`, pretty in `env=dev`. Standard fields on every log: `request_id`, `session_id` (when known), `run_id` (when known), `route`, `latency_ms`.
- **Rate limiting**: `slowapi` middleware. Defaults:
  - `POST /sessions` → 30/min per IP
  - `POST /sessions/{id}/run` → 5/min per IP
  - `POST /sessions/{id}/chat` → 30/min per IP
  - Anything else → 120/min per IP
  Disabled in `env=test`. Returns standard error contract with `code=rate_limited` and `Retry-After`.
- **CORS**: read allowed origins strictly from settings; no `*` in prod.
- **Secrets**: every secret loaded via `pydantic-settings`; no hard-coded keys. `config.py` has a `redact()` helper for log output.
- **Cost cap**: per-session soft cap (`workflow_max_cost_usd`, default $1). Tracked via the OpenRouter cost-per-call metric; if exceeded mid-run, the runner emits `run_failed` with `code=cost_cap_exceeded`. Visible in the UI's failed-run card.
- **Timeouts**: every outbound call (LLM, search, fetch) has an explicit timeout — sweep the codebase to confirm.
- **Graceful shutdown**: FastAPI lifespan drains the event bus, marks any `running` sessions as `interrupted` (a new terminal status) on `SIGTERM`; on restart, those sessions can be resumed via the existing checkpoint flow.
- **Health endpoint** extended: `GET /api/health` now also reports OpenRouter reachability (HEAD on the API base; cached 30s).

### 2.2 Frontend
- **Error boundary** at the App Router root level (`error.tsx` + nested per-route). Shows friendly recovery UI with a "Reload" button and a request-id (pulled from the last fetch).
- **Loading boundaries** (`loading.tsx`) for `/sessions` and `/sessions/[id]` showing skeletons.
- **Network-aware UX**: detect offline via `navigator.onLine` + `online`/`offline` listeners, show a banner; pause SSE reconnect retries while offline.
- **Toast hygiene**: dedupe identical error toasts within 3s, cap at 3 visible (Sonner config).
- **Performance**: confirm Lighthouse budget — LCP < 2.5s on the session detail page (cold), JS bundle < 250 KB gzipped. Tree-shake any heavy imports surfaced (look at `framer-motion`).
- **Print stylesheet** (added in Part 4) extended for the chat tab (chat hidden when printing).

### 2.3 Observability hooks (no infra required)
- Backend exposes `/api/metrics` (basic counters: requests by route, workflow runs by status, chat messages, LLM tokens by node) in JSON. Documented as "scrape with curl/cron" — actual Prometheus integration is in §6's `engineering-decisions.md` as deferred work.
- Frontend captures unhandled rejections + errors and POSTs to `/api/client-errors` (logged server-side, never replied with sensitive details).

---

## 3. Accessibility & Responsive Final Pass

- Run `eslint-plugin-jsx-a11y`. Fix all warnings or document waivers.
- Sweep all interactive elements: buttons have accessible labels, all icons paired with text or `aria-label`.
- Keyboard sweep: every flow (create session, run, watch progress, switch tabs, chat) reachable via Tab + Enter + arrow keys.
- Screen reader spot check (VoiceOver on macOS): node status changes announce, citations chips read out properly.
- Color contrast verified for both light and dark via the ShadCN tokens.
- Mobile sweep at 360px / 414px / 768px. Chat composer doesn't overlap the iOS safe area.

---

## 4. Required Documentation

All four documents live in `/docs/` (except `README.md` at the repo root). Each is written for a specific reader, not a generic audience.

### 4.1 `README.md` (root)
**Audience:** anyone evaluating the submission.

Sections:
1. **What it is** — 3-sentence elevator pitch.
2. **Demo** — embedded GIF (5–8s) of a run end-to-end + link to the demo video / hosted URL.
3. **Quickstart** — prereqs (UV, Node 20+, pnpm, MongoDB local or Atlas), 4-step setup (`uv sync`, `pnpm install`, env, `scripts/dev.sh`).
4. **Environment variables** — table with name, scope, required?, example.
5. **Repo map** — annotated tree showing where to find each piece.
6. **Tech stack** — bullet list with one-line rationale for each choice.
7. **Testing** — how to run backend tests, frontend tests, linters.
8. **Architecture & design docs** — links to the three `/docs/*.md`.
9. **Known limitations** — single-user, single-worker, in-process queue, etc.

Verified by: a fresh clone + the Quickstart steps produce a working app in ≤10 minutes.

### 4.2 `docs/architecture.md`
**Audience:** an engineer joining the team next week.

Sections:
1. **System overview** — one diagram (mermaid or ASCII): browser ↔ Next.js ↔ FastAPI ↔ LangGraph + Mongo + OpenRouter + Tavily.
2. **Request flow** — sequence diagram for: create session, run workflow (with SSE), follow-up chat.
3. **LangGraph workflow** — diagram of nodes + state + the conditional loop; brief node responsibilities; the GraphState shape.
4. **Persistence** — collections (`sessions`, `workflow_runs`, `workflow_checkpoints`, `reports`, `chat_messages`) with field tables and indexes.
5. **Naming bridge** — short explainer of the camelCase ↔ snake_case bridge with the `ApiModel` snippet.
6. **Event model** — why SSE + `sinceSeq` instead of WebSocket / polling.
7. **Recoverability** — how checkpoints + resume work; what's guaranteed and what isn't.
8. **Deployment shape** — what production would look like (FastAPI behind nginx/uvicorn, Atlas, Vercel for the frontend). Marked as illustrative.

### 4.3 `docs/engineering-decisions.md`
**Audience:** the rubric grader (`engineering-decisions.md` is required and has explicit sub-headings).

Required structure (per assignment spec):

1. **3 major engineering decisions** — written as Decision Records:
   - **D1: OpenRouter as the single LLM gateway.** Context → decision → consequences. Alternatives: direct OpenAI/Anthropic clients; LiteLLM proxy.
   - **D2: SSE with `sinceSeq` for workflow progress, not WebSocket.** Decision → consequences. Alternatives: WebSocket; polling.
   - **D3: Custom Mongo checkpointer with a `BaseCheckpointSaver` impl.** Decision → consequences. Alternatives: in-memory, SQLite, Redis.
2. **Alternatives considered** — embedded under each decision (above).
3. **Tradeoffs made** — explicit "we chose X, gave up Y."
4. **Top technical debt items** —
   - Background tasks run in the FastAPI worker (not a queue) — fine for 1 user, breaks at 5+ concurrent runs.
   - Single-tenant: no auth, no per-user scoping.
   - BM25 retrieval is good enough for ≤50 sources; would swap to embeddings (e.g., `openai/text-embedding-3-small`) at scale.
   - In-process event bus — doesn't survive multi-replica deploys; needs Redis pub/sub.
   - Manual prompt files; no eval harness.
5. **Biggest technical risk** — OpenRouter gateway dependency (mitigation: model fallback chain; documented as accepted risk).
6. **What we would improve with 2 additional weeks** — concrete list (auth, multi-tenant, queue migration, embeddings + reranker, eval harness, OpenTelemetry, CI/CD, deploy via Docker Compose).

### 4.4 `docs/product-improvements.md`
**Audience:** the rubric grader (also required, max 2 pages).

Required structure (per assignment spec, all 10 items):

1. **At least 5 weaknesses in the current product design** — written from a sales-user POV, not a code POV. Examples to draft from:
   - Sessions are one-shot; no way to iterate / refine the report inline.
   - No comparison view (research two competitors side-by-side).
   - No way to share or export a polished briefing to a buyer.
   - Sources are static — no "freshness" check before a meeting.
   - No CRM integration; copy-paste tax.
2. **Top 3 improvements to build next** — Sharing/export (PDF + link), CRM sync (HubSpot/Salesforce), Saved playbooks (rerun against a list).
3. **Who buys, who uses, why they pay** — buyer (VP Sales / Head of GTM), user (AE/SDR), willingness to pay tied to AE productivity ROI.
4. **Success metrics** — North star: research-prep time per meeting (target: 30 min → 5 min). Inputs: report quality score (human-rated sample), report-to-meeting conversion, daily/weekly active sellers, chat usage per session.
5. **4-week AI roadmap** — Week 1: embedding-based retrieval + reranker. Week 2: eval harness + prompt regression tests. Week 3: signal freshness checks + scheduled re-runs. Week 4: persona-specific outreach generation (CISO vs. CFO).
6. **Biggest cost / scaling / reliability risks** — Cost: per-run LLM spend; mitigation: per-node model tiering, source budget. Scaling: in-process background tasks; mitigation: queue migration. Reliability: OpenRouter outage; mitigation: fallback model chain + direct-provider escape hatch behind same `LLMClient` protocol.
7. **Feature to remove** — Manual "Resume from checkpoint" button. Always-on resume is the better UX; resume-as-explicit-action is a leak of implementation detail.
8. **Feature to add** — "Meeting card" — a one-page polished export (PDF) that's actually printable and sellable.
9. **First 90-day roadmap** — Days 1–30: ship sharing + CRM, embedding retrieval. Days 31–60: eval + persona generation. Days 61–90: scheduled re-runs + Slack delivery.
10. **What I'd change first if I owned this product** — A single sentence answer: stop calling it a "report" — call it a "briefing" — and design the entire UI around the meeting, not the search.

Length budget: must fit on 2 pages when printed. Bullets, no walls of text.

---

## 5. Demo Video & Deployment

### 5.1 Demo video (always do this — cheapest win)
- ≤5 minutes, screen-recorded.
- Script:
  1. (15s) What is Argus + the problem it solves.
  2. (45s) Create a session against a real company (e.g., Notion).
  3. (90s) Watch the workflow live — narrate the node transitions and the conditional loop-back.
  4. (60s) Walk the report — point at structured sections and source citations.
  5. (60s) Ask 2 follow-up questions, show citations linking back.
  6. (30s) Show a refresh-mid-run recovering state.
- Upload to Loom (unlisted) or YouTube (unlisted). Embed link in README.

### 5.2 Hosted deployment (optional, do if time)
- **Frontend**: Vercel — connect GitHub, env vars in dashboard.
- **Backend**: Railway or Fly.io with Mongo Atlas. Single small instance. Document URLs and credentials path.
- **CI**: GitHub Actions running `ruff check`, `pytest`, `pnpm lint`, `pnpm typecheck` on every PR. One workflow file; no fancy matrix.

If deployment is skipped, the demo video alone is sufficient per the assignment.

---

## 6. Final Sweep & QA

A scripted run-through before submission:

| Check | How |
|-------|-----|
| Fresh clone works | `git clone`, follow README, app boots |
| Lint + tests green | `ruff`, `pytest`, `eslint`, `tsc --noEmit`, `pnpm test` if added |
| Missing env vars fail cleanly | Comment out `OPENROUTER_API_KEY`, restart → clear startup error |
| Bad URL in create form | "Invalid URL" inline error |
| Workflow runs end-to-end on real company | Stripe / Notion / Vercel |
| Refresh mid-run | UI rebuilds, stream continues |
| Kill backend mid-run | Frontend shows reconnect; restart backend → resume from checkpoint works |
| Chat with citations | Click citation → scrolls to source in Report tab |
| Mobile view | iPhone simulator @ 414px, all flows usable |
| Print report | Cmd+P shows clean PDF without chat/composer |
| Rate limit | Hit `POST /sessions/.../run` 6 times fast → 6th returns 429 with `Retry-After` |
| Cost cap | Set cap to $0.01, run → fails with `cost_cap_exceeded` |
| All 4 docs read clean | Print each, read top to bottom, fix typos |

---

## 7. Step-by-Step Execution Order

1. **Chat backend** — models, repo, BM25, `pack.py`, `chat_service`, `/api/chat` routes + SSE stream + retry + suggestions. Tests.
2. **Chat frontend** — `useChatStream`, components, tab integration, citation cross-linking to Report sources.
3. **Hardening backend** — rate limit, request IDs propagation, cost cap in runner, graceful shutdown, `metrics` endpoint, health enhancement.
4. **Hardening frontend** — error boundaries, loading boundaries, offline banner, toast dedupe, perf check.
5. **A11y + responsive pass** — fix lint warnings, keyboard sweep, mobile sweep.
6. **Docs** — write all four in this order: `architecture.md` (you'll know the answer best while it's fresh) → `engineering-decisions.md` → `product-improvements.md` → `README.md` last (it links everything).
7. **Final QA sweep** — checklist in §6.
8. **Demo video** — script, record, upload, link in README.
9. **Optional deploy** — Vercel + Railway + Atlas + GitHub Actions.
10. **Tag and submit** — `v1.0.0`, GitHub repo URL, demo link, hosted link (if any).

---

## 8. Out of Scope for Part 5

- Multi-user accounts / OAuth.
- Team workspaces.
- Real-time presence / collaborative editing.
- Embedding-based retrieval (kept BM25 by design — documented in `engineering-decisions.md`).
- Persistent vector store.
- Mobile native apps.
- Internationalization.
- Anything in the "with 2 additional weeks" list of `engineering-decisions.md`.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Chat citations don't match what was actually used | Post-stream parsing maps `[i]` → source URL via the source pack index. If `[i]` isn't in the pack, suppress the chip rather than render a broken one. |
| Demo company has bad SEO and returns thin sources | Pick a well-documented company (Stripe, Notion) for the demo run; document this as a known limitation. |
| Time runs out before docs | Write docs *before* the optional deploy step — the rubric weights them at 25%. |
| Cost overrun during demo recording | Cost cap defaults to $1; if accidentally hit, raise to $5 for the recording, then revert. |
| Chat streaming buggy under poor network | Same `sinceSeq` pattern as workflow SSE; tested with throttled connection. |

---

## 10. Definition of Done — Part 5

- [ ] `POST /api/sessions/{id}/chat` accepts a question and streams a grounded answer with citations
- [ ] Chat retrieval uses BM25 over `raw_sources`; first turn ranks by question + objective, follow-ups carry forward previous citations
- [ ] Chat tab in the UI renders the message list, composer, suggested prompts, citation chips that cross-link to Report sources
- [ ] Refresh mid-stream resumes the chat reply via SSE without duplication
- [ ] Rate limiting active on the three sensitive routes with the standard error contract
- [ ] Request IDs flow through every log + every error response
- [ ] Cost cap honored per run; cap-exceeded run surfaces a clear failed state in the UI
- [ ] Graceful shutdown marks running sessions `interrupted`; resume restarts them from checkpoint
- [ ] Error boundary + offline banner + toast dedupe live on the frontend
- [ ] `eslint-plugin-jsx-a11y` warnings cleared (or explicitly waived in code)
- [ ] `README.md` (root) is complete; a fresh clone reaches a working app in ≤10 min following only its instructions
- [ ] `docs/architecture.md` covers system overview, request flows, LangGraph, persistence, naming bridge, event model, recoverability
- [ ] `docs/engineering-decisions.md` covers all 6 required sub-headings
- [ ] `docs/product-improvements.md` answers all 10 required questions, fits in 2 pages
- [ ] Demo video recorded, uploaded, linked in README
- [ ] (Optional) Hosted deployment URL in README
- [ ] All checks in §6 pass on a clean machine
- [ ] Repository tagged `v1.0.0` and submitted

---

## 11. Submission Checklist (verbatim from assignment)

- [ ] GitHub repository public + URL captured
- [ ] `README.md` present and complete
- [ ] `architecture.md` present and complete
- [ ] `engineering-decisions.md` present and complete
- [ ] `product-improvements.md` present and complete (≤2 pages)
- [ ] Demo video URL or hosted deployment URL captured
- [ ] LangGraph workflow demonstrably has: ≥5 meaningful nodes ✓, shared state ✓, conditional routing ✓, intermediate outputs ✓, failure handling ✓, recoverability ✓ — each verifiable from the UI or from the docs
- [ ] All 9 report sections present in a generated report
- [ ] Single email with repo URL + demo URL sent
