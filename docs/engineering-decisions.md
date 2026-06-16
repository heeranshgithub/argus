# Engineering Decisions

## 1. Three major engineering decisions

### D1 — OpenRouter as the single LLM gateway

**Context.** The workflow runs six nodes with very different cost/quality needs
(cheap planning vs. strong synthesis), and the assignment must run against real
models without locking to one vendor.

**Decision.** Route *all* LLM calls through OpenRouter via the OpenAI-compatible
SDK. Models are config strings (`llm_model_<node>`), so each node pins an
appropriate model and a fallback chain handles provider outages.

**Alternatives considered.**
- *Direct OpenAI/Anthropic clients.* Best-in-class per provider, but two SDKs,
  two auth paths, and no single switch to swap models per node.
- *LiteLLM proxy.* Similar normalization, but adds a service to run/operate; for
  one engineer in a time-box, a hosted gateway is less to own.

**Consequences.** One API key, one client, per-node model tiering, and a built-in
fallback chain — at the cost of a hard dependency on OpenRouter's uptime
(accepted risk; partial mitigations in section 4) and slightly less control over
provider-specific features.
Structured output is handled defensively (native JSON-schema where supported,
otherwise JSON mode + schema-in-prompt + one repair retry).

### D2 — SSE with `sinceSeq` for live progress, not WebSocket

**Context.** Workflow progress and chat replies are one-way server→client streams
that must survive refreshes and dropped connections.

**Decision.** Server-Sent Events with a per-run monotonic `seq`. The durable
record is `workflow_runs.events` in Mongo; the stream backfills `seq > since_seq`
then tails live events, deduplicating by `seq`.

**Alternatives considered.**
- *WebSocket.* Bidirectional and powerful, but we have no client→server channel;
  it adds connection lifecycle, framing, and proxy complexity for no benefit.
- *Polling.* Simplest, but chatty and adds visible latency to a token stream.

**Consequences.** Plain HTTP, native browser reconnect, trivial proxying, and
exact resumability (no gaps, no dupes) on refresh/reconnect — at the cost of an
**in-process** event bus that doesn't span replicas (see section 3, item 4).

### D3 — Custom Mongo checkpointer (`BaseCheckpointSaver`)

**Context.** A run can span minutes and several LLM calls; it must resume from a
crash or a deploy, and we already run Mongo for everything else.

**Decision.** Implement LangGraph's `BaseCheckpointSaver` against Mongo
(`workflow_checkpoints` + blobs + writes), keyed by `thread_id == session_id`, so
state is snapshotted after every super-step and `resume` continues from the last
checkpoint.

**Alternatives considered.**
- *In-memory saver.* Zero setup, but loses everything on restart — defeats the
  recoverability requirement.
- *SQLite saver.* Durable, but a second datastore and an awkward fit for our
  async Motor stack.
- *Redis saver.* Great for ephemeral state, but another service to run and not
  the system of record.

**Consequences.** One datastore, durable resume, and checkpoints co-located with
the run record — at the cost of writing/maintaining the saver ourselves.

---

## 2. Tradeoffs made (what we chose, what we gave up)

- **Hosted gateway over direct SDKs** — vendor flexibility + simplicity; gave up
  some provider-specific control and added a single external dependency.
- **SSE over WebSocket** — simplicity + resumability; gave up bidirectional
  comms (not needed) and cross-replica fan-out (in-process bus).
- **BM25 over embeddings for chat retrieval** — zero extra deps, low latency,
  fully offline-testable; gave up semantic recall (fine at ≤50 sources).
- **In-process background tasks over a queue** — no infra, instant start; gave up
  horizontal scale and cross-process durability of the *bus* (state is still
  durable in Mongo).
- **Single-tenant** — no auth surface to build/secure; gave up multi-user.

---

## 3. Top technical debt

1. **Background tasks run in the FastAPI worker**, not a real queue. Fine for one
   user; breaks down past ~5 concurrent runs (event-loop contention, no
   backpressure).
2. **Single-tenant.** No auth, no per-user scoping; every session is global.
3. **BM25 retrieval** is good enough for ≤50 sources; at scale it should become
   embeddings (`openai/text-embedding-3-small`) + a reranker.
4. **In-process event bus + chat stream buffers** don't survive multi-replica
   deploys; needs Redis pub/sub. (Mongo durability means reconnect still works.)
5. **Manual prompt files, no eval harness** — prompt changes are unguarded by
   regression tests.
6. **Cost cap is a soft, per-run check** at node boundaries, not a hard
   pre-flight budget; a single runaway call can overshoot before the next check.

---

## 4. Biggest technical risk

**The OpenRouter gateway is a single point of dependency** for every LLM call
(workflow *and* chat). An outage or a breaking change stalls the core product.

**Mitigation (accepted risk).** A fallback model chain (`llm_fallback_models`)
routes around provider blips; transient errors get exponential-backoff retries;
the `/api/health` probe surfaces reachability. The `LLMClient` is a *protocol*,
so a direct-provider escape hatch is a drop-in replacement if we ever need to
leave OpenRouter. We accept the dependency for the simplicity it buys (D1).

---

## 5. What we'd improve with two more weeks

- **Auth + multi-tenant** — sessions scoped to users; API keys/OAuth.
- **Queue migration** — move background runs to a real worker (Celery/Arq/RQ)
  with backpressure and retries.
- **Embeddings + reranker** — replace BM25 for chat retrieval at scale.
- **Eval harness** — golden-set prompt regression tests in CI.
- **Redis pub/sub** — cross-replica event bus + chat streaming.
- **OpenTelemetry** — real tracing/metrics export (today: in-process counters at
  `/api/metrics`, documented as scrape-with-curl).
- **CI/CD + Docker Compose** — one-command stack and automated deploys.

---

## 6. Production-readiness summary (what's already in)

Implemented this part, so the debt above is honest rather than hand-wavy:
request-id propagation through every log + error response, structured JSON logs
with latency, per-IP rate limiting (slowapi) on the sensitive routes, a per-run
cost cap, graceful shutdown (running → `interrupted`, resumable), an
OpenRouter-aware health endpoint, an in-process metrics endpoint, and a
client-error sink. The frontend adds error/loading boundaries, an offline banner
with paused SSE retries, de-duplicated toasts, and a client-error reporter.
