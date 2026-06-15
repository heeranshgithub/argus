"""Workflow events — the audit trail and the live-stream feed.

Every node start/finish/error/output becomes a :class:`WorkflowEvent` that goes
to two sinks (see PLAN_PART_3 §7):

1. ``workflow_runs.events`` (append) — durable, for replay/audit and Part 4's
   SSE backfill on first paint.
2. A per-session :class:`asyncio.Queue` via :data:`event_bus` — for Part 4's
   live SSE stream. If nobody is subscribed the publish is a no-op; the event
   still lands in Mongo.

Run-scoped context (db handle, run id, the monotonic ``seq`` counter, the bus)
travels through a :class:`contextvars.ContextVar`, *not* through ``GraphState`` —
the state is checkpointed to Mongo after every step and must stay serializable.
``ainvoke`` copies the current context into each node task, so a context bound
just before invocation is visible to every node.
"""

from __future__ import annotations

import asyncio
import contextlib
import traceback as traceback_mod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict

from app.logging_config import get_logger
from app.models.workflow import EventKind, NodeStatus
from app.repositories import workflow_repo

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

log = get_logger("workflow.events")


class WorkflowEvent(TypedDict):
    """One entry in a run's timeline (also the SSE payload shape)."""

    run_id: str
    session_id: str
    node: str
    kind: str
    payload: dict[str, Any]
    ts: datetime
    seq: int


# Run-level events are not tied to a graph node; this sentinel marks them.
RUN_NODE = "__run__"


class CostCapExceeded(RuntimeError):
    """Raised mid-run when accumulated LLM spend crosses the per-run soft cap.

    Carries the stable error ``code`` the API/UI surface as a failed-run reason
    (PLAN_PART_5 §2.1).
    """

    code = "cost_cap_exceeded"

    def __init__(self, spent: float, cap: float) -> None:
        self.spent = spent
        self.cap = cap
        super().__init__(
            f"Run exceeded the cost cap: spent ${spent:.4f} of ${cap:.2f}."
        )


class EventBus:
    """In-process fan-out of run events to live SSE subscribers.

    Subscribers register a queue per session id; publishers push to every queue
    registered for that session. Queues are bounded (``max_queue``); a slow or
    stalled consumer never blocks the workflow — on overflow the *oldest* queued
    event is evicted to make room for the newest, ``dropped_events`` is bumped,
    and a structlog warning fires. The durable record in ``workflow_runs.events``
    is unaffected, so a reconnect with ``since_seq`` recovers anything dropped.
    """

    def __init__(self, *, max_queue: int = 512) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[WorkflowEvent]]] = {}
        self._max_queue = max_queue
        self.dropped_events = 0

    def subscribe(self, session_id: str) -> asyncio.Queue[WorkflowEvent]:
        """Register and return a new queue for ``session_id``."""
        queue: asyncio.Queue[WorkflowEvent] = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.setdefault(session_id, set()).add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[WorkflowEvent]) -> None:
        """Remove a previously-subscribed queue."""
        subs = self._subscribers.get(session_id)
        if not subs:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(session_id, None)

    def publish(self, session_id: str, event: WorkflowEvent) -> None:
        """Push ``event`` to every live subscriber for ``session_id``.

        Drop-oldest on overflow so live consumers always trend toward the newest
        events; dropped ones stay recoverable from Mongo via ``since_seq``.
        """
        for queue in self._subscribers.get(session_id, set()):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()  # evict the oldest to make room
                self.dropped_events += 1
                log.warning(
                    "event_queue_overflow",
                    session_id=session_id,
                    seq=event["seq"],
                    dropped_events=self.dropped_events,
                )
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - concurrent producers
                self.dropped_events += 1

    def subscriber_count(self, session_id: str) -> int:
        """Number of live subscribers for a session (used in tests)."""
        return len(self._subscribers.get(session_id, set()))


# Process-wide bus; the FastAPI app and the runner share this instance.
event_bus = EventBus()


@dataclass
class RunContext:
    """Run-scoped handles + counters, carried via :data:`_run_ctx`."""

    db: AsyncIOMotorDatabase
    run_id: str
    session_id: str
    bus: EventBus | None = None
    cost_cap_usd: float | None = None
    cost_usd: float = 0.0
    cost_exceeded: bool = False
    _seq: int = field(default=0)

    def next_seq(self) -> int:
        """Return the next monotonic sequence number for this run."""
        self._seq += 1
        return self._seq

    def record_cost(self, amount: float | None) -> None:
        """Accumulate an LLM call's cost and flag if the soft cap is crossed.

        Deliberately does *not* raise — it's called from inside the (retrying)
        LLM client, where an exception would trigger pointless re-calls. The cap
        is enforced at the node boundary in :func:`emit_node` instead.
        """
        if not amount:
            return
        self.cost_usd += amount
        if self.cost_cap_usd is not None and self.cost_usd > self.cost_cap_usd:
            self.cost_exceeded = True


_run_ctx: ContextVar[RunContext | None] = ContextVar("argus_run_ctx", default=None)


def current_run_context() -> RunContext:
    """Return the active :class:`RunContext`, raising if none is bound."""
    ctx = _run_ctx.get()
    if ctx is None:
        raise RuntimeError(
            "No RunContext is bound; emit() must run inside bind_run_context()."
        )
    return ctx


@asynccontextmanager
async def bind_run_context(ctx: RunContext) -> AsyncIterator[RunContext]:
    """Bind ``ctx`` for the duration of the block (resets on exit)."""
    token = _run_ctx.set(ctx)
    try:
        yield ctx
    finally:
        _run_ctx.reset(token)


def _now() -> datetime:
    """UTC now truncated to milliseconds (BSON datetime precision)."""
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


async def emit(
    kind: EventKind | str,
    *,
    node: str = RUN_NODE,
    payload: dict[str, Any] | None = None,
    node_status: NodeStatus | None = None,
) -> WorkflowEvent:
    """Build, persist, and publish a single event.

    Persists to ``workflow_runs.events`` (and optionally updates the run's
    ``node_status`` map) then publishes to any live SSE subscribers. Mongo is the
    source of truth; a failed publish never affects the durable record.
    """
    ctx = current_run_context()
    event: WorkflowEvent = {
        "run_id": ctx.run_id,
        "session_id": ctx.session_id,
        "node": node,
        "kind": str(kind),
        "payload": payload or {},
        "ts": _now(),
        "seq": ctx.next_seq(),
    }
    await workflow_repo.append_event(ctx.db, ctx.run_id, event, node_status=node_status)
    if ctx.bus is not None:
        ctx.bus.publish(ctx.session_id, event)
    return event


class NodeEmitter:
    """Handle yielded by :func:`emit_node` for attaching output to a node run."""

    def __init__(self, node: str) -> None:
        self.node = node
        self._preview: dict[str, Any] = {}

    def set_preview(self, preview: dict[str, Any]) -> None:
        """Attach a small preview emitted with the ``node_finished`` event."""
        self._preview = preview

    async def output(self, payload: dict[str, Any]) -> None:
        """Emit an intermediate ``node_output`` event for this node."""
        await emit(EventKind.NODE_OUTPUT, node=self.node, payload=payload)

    @property
    def preview(self) -> dict[str, Any]:
        return self._preview


@asynccontextmanager
async def emit_node(node: str) -> AsyncIterator[NodeEmitter]:
    """Bracket a node's work with start/finish/error events.

    Emits ``node_started`` on entry and ``node_finished`` on clean exit (carrying
    any preview set via the yielded handle and a ``duration_ms``). On exception it
    emits ``node_errored`` with the error details and re-raises, letting
    LangGraph's retry policy take over.
    """
    emitter = NodeEmitter(node)
    started = _now()
    await emit(EventKind.NODE_STARTED, node=node, node_status=NodeStatus.RUNNING)
    try:
        yield emitter
    except Exception as exc:
        await emit(
            EventKind.NODE_ERRORED,
            node=node,
            payload={
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback_mod.format_exc(limit=8),
            },
            node_status=NodeStatus.FAILED,
        )
        raise
    else:
        duration_ms = int((_now() - started).total_seconds() * 1000)
        await emit(
            EventKind.NODE_FINISHED,
            node=node,
            payload={**emitter.preview, "duration_ms": duration_ms},
            node_status=NodeStatus.DONE,
        )
        # Enforce the per-run cost cap at the node boundary (PLAN_PART_5 §2.1).
        # Checked here (not inside the retrying LLM client) so the run fails
        # cleanly after the over-budget node rather than re-calling the model.
        ctx = current_run_context()
        if ctx.cost_exceeded:
            raise CostCapExceeded(ctx.cost_usd, ctx.cost_cap_usd or 0.0)
