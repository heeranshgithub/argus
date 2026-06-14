"""Tests for the event bus, RunContext binding, and emit_node bracketing."""

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.models.workflow import EventKind, NodeStatus
from app.repositories import workflow_repo
from app.workflow.events import (
    EventBus,
    RunContext,
    bind_run_context,
    current_run_context,
    emit,
    emit_node,
    event_bus,
)


def _db():
    return AsyncMongoMockClient(tz_aware=True)["argus_test"]


async def test_emit_requires_bound_context() -> None:
    with pytest.raises(RuntimeError):
        current_run_context()


async def test_emit_node_brackets_with_start_and_finish() -> None:
    db = _db()
    run_id = await workflow_repo.create_run(db, "s1")
    async with (
        bind_run_context(RunContext(db=db, run_id=run_id, session_id="s1")),
        emit_node("planner") as ev,
    ):
        ev.set_preview({"k": "v"})

    run = await workflow_repo.get_run(db, run_id)
    kinds = [e.kind for e in run.events]
    assert kinds == [EventKind.NODE_STARTED, EventKind.NODE_FINISHED]
    assert run.node_status["planner"] is NodeStatus.DONE
    assert run.events[-1].payload["k"] == "v"
    assert "duration_ms" in run.events[-1].payload
    # seq is monotonic.
    assert [e.seq for e in run.events] == [1, 2]


async def test_emit_node_records_error_and_reraises() -> None:
    db = _db()
    run_id = await workflow_repo.create_run(db, "s1")
    async with bind_run_context(RunContext(db=db, run_id=run_id, session_id="s1")):
        with pytest.raises(ValueError):
            async with emit_node("analyst"):
                raise ValueError("boom")

    run = await workflow_repo.get_run(db, run_id)
    kinds = [e.kind for e in run.events]
    assert EventKind.NODE_ERRORED in kinds
    assert run.node_status["analyst"] is NodeStatus.FAILED
    errored = next(e for e in run.events if e.kind is EventKind.NODE_ERRORED)
    assert errored.payload["error"] == "boom"


async def test_event_bus_publishes_to_subscribers() -> None:
    db = _db()
    run_id = await workflow_repo.create_run(db, "s-bus")
    bus = EventBus()
    queue = bus.subscribe("s-bus")
    assert bus.subscriber_count("s-bus") == 1

    async with bind_run_context(
        RunContext(db=db, run_id=run_id, session_id="s-bus", bus=bus)
    ):
        await emit(EventKind.RUN_STARTED, node="__run__")

    event = queue.get_nowait()
    assert event["kind"] == "run_started"
    bus.unsubscribe("s-bus", queue)
    assert bus.subscriber_count("s-bus") == 0


async def test_event_bus_no_subscriber_is_noop() -> None:
    # Publishing to a session with no subscribers must not raise.
    event_bus.publish("nobody", {"run_id": "r", "session_id": "nobody", "node": "n",
                                 "kind": "node_started", "payload": {}, "ts": None, "seq": 1})
