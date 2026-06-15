"""Async CRUD for ``workflow_runs`` (the run record + event timeline).

Stores documents snake_case; conversion to the camelCase wire models happens in
the ``to_*`` helpers. Functions take the ``AsyncIOMotorDatabase`` explicitly so
they stay trivial to test against an in-memory Mongo.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.collections import WORKFLOW_RUNS
from app.exceptions import InvalidObjectId
from app.models.workflow import (
    NODE_NAMES,
    NodeStatus,
    RunStatus,
    WorkflowError,
    WorkflowEventOut,
    WorkflowRunOut,
    WorkflowRunSummary,
)

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

    from app.workflow.events import WorkflowEvent


def _utcnow_ms() -> datetime:
    """Current UTC time truncated to millisecond precision (matches BSON)."""
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _to_object_id(run_id: str) -> ObjectId:
    """Parse a wire id into an ``ObjectId`` or raise :class:`InvalidObjectId`."""
    try:
        return ObjectId(run_id)
    except (InvalidId, TypeError) as exc:
        raise InvalidObjectId(run_id) from exc


def _initial_node_status() -> dict[str, str]:
    """All known nodes seeded to ``pending``."""
    return {name: NodeStatus.PENDING.value for name in NODE_NAMES}


async def create_run(db: AsyncIOMotorDatabase, session_id: str) -> str:
    """Insert a fresh run document (status ``running``) and return its id."""
    doc: dict[str, Any] = {
        "session_id": session_id,
        "status": RunStatus.RUNNING.value,
        "started_at": _utcnow_ms(),
        "finished_at": None,
        "node_status": _initial_node_status(),
        "events": [],
        "error": None,
        "final_state_keys": [],
    }
    result = await db[WORKFLOW_RUNS].insert_one(doc)
    return str(result.inserted_id)


async def append_event(
    db: AsyncIOMotorDatabase,
    run_id: str,
    event: WorkflowEvent,
    *,
    node_status: NodeStatus | None = None,
) -> None:
    """Append one event and (optionally) update a node's status, atomically."""
    update: dict[str, Any] = {"$push": {"events": dict(event)}}
    if node_status is not None and event["node"]:
        update["$set"] = {f"node_status.{event['node']}": node_status.value}
    await db[WORKFLOW_RUNS].update_one({"_id": _to_object_id(run_id)}, update)


async def mark_completed(
    db: AsyncIOMotorDatabase,
    run_id: str,
    *,
    final_state_keys: list[str],
    raw_sources: list[dict[str, Any]] | None = None,
) -> None:
    """Mark a run completed and stamp ``finished_at``.

    ``raw_sources`` (the fetched-and-cleaned source documents from the final
    graph state) are persisted onto the run so follow-up chat can rank over them
    (PLAN_PART_5 §1.3) without re-reading the LangGraph checkpoint blobs.
    """
    update: dict[str, Any] = {
        "status": RunStatus.COMPLETED.value,
        "finished_at": _utcnow_ms(),
        "final_state_keys": final_state_keys,
    }
    if raw_sources is not None:
        update["raw_sources"] = raw_sources
    await db[WORKFLOW_RUNS].update_one(
        {"_id": _to_object_id(run_id)}, {"$set": update}
    )


async def get_latest_raw_sources(
    db: AsyncIOMotorDatabase, session_id: str
) -> list[dict[str, Any]]:
    """Return ``raw_sources`` from the session's most recent completed run.

    Used by follow-up chat retrieval. Returns an empty list if no completed run
    has sources yet.
    """
    doc = await db[WORKFLOW_RUNS].find_one(
        {"session_id": session_id, "status": RunStatus.COMPLETED.value},
        projection={"raw_sources": 1},
        sort=[("finished_at", -1), ("_id", -1)],
    )
    if doc is None:
        return []
    return list(doc.get("raw_sources") or [])


async def mark_failed(
    db: AsyncIOMotorDatabase, run_id: str, *, error: WorkflowError
) -> None:
    """Mark a run failed, stamping ``finished_at`` and the error detail."""
    await db[WORKFLOW_RUNS].update_one(
        {"_id": _to_object_id(run_id)},
        {
            "$set": {
                "status": RunStatus.FAILED.value,
                "finished_at": _utcnow_ms(),
                "error": error.model_dump(),
            }
        },
    )


async def get_run(db: AsyncIOMotorDatabase, run_id: str) -> WorkflowRunOut | None:
    """Fetch a single run (with events), or ``None`` if absent."""
    doc = await db[WORKFLOW_RUNS].find_one({"_id": _to_object_id(run_id)})
    return to_workflow_run_out(doc) if doc is not None else None


async def list_runs(
    db: AsyncIOMotorDatabase, session_id: str, *, limit: int, skip: int
) -> list[WorkflowRunSummary]:
    """Return a session's runs newest-first, without their event lists."""
    cursor = (
        db[WORKFLOW_RUNS]
        .find({"session_id": session_id}, projection={"events": 0})
        .sort([("started_at", -1), ("_id", -1)])
        .skip(skip)
        .limit(limit)
    )
    return [to_workflow_run_summary(doc) async for doc in cursor]


async def count_runs(db: AsyncIOMotorDatabase, session_id: str) -> int:
    """Total number of runs for a session."""
    return await db[WORKFLOW_RUNS].count_documents({"session_id": session_id})


async def get_latest_run(
    db: AsyncIOMotorDatabase, session_id: str
) -> WorkflowRunOut | None:
    """Return the most recent run for a session, or ``None``."""
    doc = await db[WORKFLOW_RUNS].find_one(
        {"session_id": session_id}, sort=[("started_at", -1), ("_id", -1)]
    )
    return to_workflow_run_out(doc) if doc is not None else None


async def has_active_run(db: AsyncIOMotorDatabase, session_id: str) -> bool:
    """True if a run for this session is currently ``running``."""
    doc = await db[WORKFLOW_RUNS].find_one(
        {"session_id": session_id, "status": RunStatus.RUNNING.value},
        projection={"_id": 1},
    )
    return doc is not None


# --- converters ----------------------------------------------------------------


def _error_from_doc(raw: Mapping[str, Any] | None) -> WorkflowError | None:
    return WorkflowError.model_validate(raw) if raw else None


def to_workflow_run_summary(doc: Mapping[str, Any]) -> WorkflowRunSummary:
    """Convert a raw run document (no events) into a :class:`WorkflowRunSummary`."""
    data = dict(doc)
    raw_id = data.pop("_id", None)
    return WorkflowRunSummary(
        id=str(raw_id),
        session_id=data["session_id"],
        status=RunStatus(data["status"]),
        started_at=data["started_at"],
        finished_at=data.get("finished_at"),
        node_status={k: NodeStatus(v) for k, v in data.get("node_status", {}).items()},
        error=_error_from_doc(data.get("error")),
    )


def to_workflow_run_out(doc: Mapping[str, Any]) -> WorkflowRunOut:
    """Convert a raw run document (with events) into a :class:`WorkflowRunOut`."""
    data = dict(doc)
    raw_id = data.pop("_id", None)
    events = [WorkflowEventOut.model_validate(e) for e in data.get("events", [])]
    return WorkflowRunOut(
        id=str(raw_id),
        session_id=data["session_id"],
        status=RunStatus(data["status"]),
        started_at=data["started_at"],
        finished_at=data.get("finished_at"),
        node_status={k: NodeStatus(v) for k, v in data.get("node_status", {}).items()},
        events=events,
        error=_error_from_doc(data.get("error")),
        final_state_keys=data.get("final_state_keys", []),
    )
