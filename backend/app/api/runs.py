"""Workflow run routes — start/resume runs, inspect timelines, stream events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.dependencies import get_workflow_deps
from app.db.mongo import get_db
from app.exceptions import RunNotFound
from app.models.workflow import (
    RunAccepted,
    RunListResponse,
    RunStatus,
    WorkflowRunOut,
)
from app.services import workflow_service
from app.workflow.deps import WorkflowDeps
from app.workflow.events import EventKind, WorkflowEvent, event_bus

router = APIRouter(prefix="/sessions", tags=["runs"])

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
DepsDep = Annotated[WorkflowDeps, Depends(get_workflow_deps)]

# Kinds that terminate an SSE stream.
_TERMINAL_KINDS = {EventKind.RUN_COMPLETED.value, EventKind.RUN_FAILED.value}
# Run statuses that mean the timeline is already complete in the backfill.
_TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED}
# How long to wait for a live event before emitting an SSE heartbeat comment.
_SSE_HEARTBEAT_SECONDS = 15.0
# Headers that keep SSE flowing through proxies (disable buffering + caching).
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post(
    "/{session_id}/run",
    response_model=RunAccepted,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    session_id: str,
    db: DbDep,
    deps: DepsDep,
    background_tasks: BackgroundTasks,
) -> RunAccepted:
    """Kick off a workflow run for a session (202; runs in the background)."""
    return await workflow_service.start_run(db, deps, session_id, background_tasks)


@router.post(
    "/{session_id}/run/resume",
    response_model=RunAccepted,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_run(
    session_id: str,
    db: DbDep,
    deps: DepsDep,
    background_tasks: BackgroundTasks,
) -> RunAccepted:
    """Resume a failed session's workflow from its last checkpoint (202)."""
    return await workflow_service.resume_run(db, deps, session_id, background_tasks)


@router.get(
    "/{session_id}/runs",
    response_model=RunListResponse,
    response_model_by_alias=True,
)
async def list_runs(
    session_id: str,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    skip: Annotated[int, Query(ge=0)] = 0,
) -> RunListResponse:
    """List a session's runs, newest-first (summaries, without events)."""
    items, total = await workflow_service.list_runs(db, session_id, limit=limit, skip=skip)
    return RunListResponse(items=items, total=total)


@router.get(
    "/{session_id}/runs/{run_id}",
    response_model=WorkflowRunOut,
    response_model_by_alias=True,
)
async def get_run(session_id: str, run_id: str, db: DbDep) -> WorkflowRunOut:
    """Fetch a single run including its full event timeline (for first paint)."""
    return await workflow_service.get_run(db, session_id, run_id)


@router.get("/{session_id}/runs/{run_id}/timeline", response_model=WorkflowRunOut)
async def run_timeline(
    session_id: str, run_id: str, db: DbDep, request: Request
) -> WorkflowRunOut:
    """Dev-only debug view of a run's full event list with payloads."""
    settings = request.app.state.settings
    if settings.env != "dev":
        raise RunNotFound(run_id)  # hide the endpoint outside dev
    return await workflow_service.get_run(db, session_id, run_id)


def _sse_format(event: WorkflowEvent) -> str:
    """Render a workflow event as a Server-Sent-Events frame (camelCase JSON)."""
    from app.models.workflow import WorkflowEventOut

    data = WorkflowEventOut.model_validate(event).model_dump(by_alias=True, mode="json")
    return f"id: {event['seq']}\nevent: {event['kind']}\ndata: {json.dumps(data)}\n\n"


@router.get("/{session_id}/runs/{run_id}/events")
async def stream_run_events(
    session_id: str,
    run_id: str,
    db: DbDep,
    request: Request,
    since_seq: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    """Stream a run's events via SSE: stored backfill first, then live updates.

    ``since_seq`` is the keystone for refresh + reconnect (PLAN_PART_4 §1): the
    backfill replays only events with ``seq > since_seq``, and the live loop
    drops anything at-or-below it. Subscribing *before* reading backfill (and
    de-duplicating by ``seq``) closes the race where an event lands between the
    snapshot and the subscription. The handler also exits cleanly when the
    client disconnects, so an abandoned stream doesn't leak a subscriber.
    """
    run = await workflow_service.get_run(db, session_id, run_id)  # 404 if absent

    async def generator() -> AsyncIterator[str]:
        queue = event_bus.subscribe(session_id)
        sent: set[int] = set()
        try:
            # Backfill events the client hasn't seen yet (seq > since_seq).
            for event in run.events:
                if event.seq <= since_seq:
                    continue
                sent.add(event.seq)
                frame: WorkflowEvent = {
                    "run_id": event.run_id,
                    "session_id": event.session_id,
                    "node": event.node,
                    "kind": event.kind.value,
                    "payload": event.payload,
                    "ts": event.ts,
                    "seq": event.seq,
                }
                yield _sse_format(frame)

            # If the run already finished, its terminal event is in the backfill
            # (or was below since_seq) — close now instead of waiting on a queue
            # that will never receive anything.
            if run.status in _TERMINAL_STATUSES:
                return

            # Otherwise stream live events for this run until it terminates.
            while True:
                if await request.is_disconnected():
                    return
                try:
                    live = await asyncio.wait_for(
                        queue.get(), timeout=_SSE_HEARTBEAT_SECONDS
                    )
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if (
                    live["run_id"] != run_id
                    or live["seq"] <= since_seq
                    or live["seq"] in sent
                ):
                    continue
                sent.add(live["seq"])
                yield _sse_format(live)
                if live["kind"] in _TERMINAL_KINDS:
                    return
        finally:
            event_bus.unsubscribe(session_id, queue)

    return StreamingResponse(
        generator(), media_type="text/event-stream", headers=_SSE_HEADERS
    )
