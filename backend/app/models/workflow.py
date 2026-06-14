"""Workflow run + event models — the camelCase wire shapes for a graph run.

A *run* is one execution of the LangGraph workflow against a session. Each node
emits *events* (start/finish/error/output) that are appended to the run document
and streamed live in Part 4. These models inherit :class:`ApiModel`, so the wire
is camelCase while Mongo storage and Python attributes stay snake_case.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.models.base import ApiModel

# Canonical node names, in execution order. Kept here (not just in graph.py) so
# the API/repo layers can seed node_status without importing the graph.
NODE_NAMES: tuple[str, ...] = (
    "planner",
    "researcher",
    "signal_extractor",
    "analyst",
    "quality_check",
    "reporter",
)


class RunStatus(StrEnum):
    """Lifecycle of a single workflow run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeStatus(StrEnum):
    """Per-node progress within a run."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class EventKind(StrEnum):
    """The kinds of event a run can emit."""

    RUN_STARTED = "run_started"
    NODE_STARTED = "node_started"
    NODE_OUTPUT = "node_output"
    NODE_FINISHED = "node_finished"
    NODE_ERRORED = "node_errored"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class WorkflowError(ApiModel):
    """A captured run-level failure."""

    code: str
    message: str
    traceback: str | None = None


class WorkflowEventOut(ApiModel):
    """A single event in a run's timeline."""

    run_id: str
    session_id: str
    node: str
    kind: EventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime
    seq: int


class WorkflowRunOut(ApiModel):
    """A full run, including its event timeline (for first-paint backfill)."""

    id: str
    session_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    node_status: dict[str, NodeStatus] = Field(default_factory=dict)
    events: list[WorkflowEventOut] = Field(default_factory=list)
    error: WorkflowError | None = None
    final_state_keys: list[str] = Field(default_factory=list)


class WorkflowRunSummary(ApiModel):
    """A run without its (potentially large) event list, for list endpoints."""

    id: str
    session_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    node_status: dict[str, NodeStatus] = Field(default_factory=dict)
    error: WorkflowError | None = None


class RunListResponse(ApiModel):
    """List envelope for ``GET /api/sessions/{id}/runs``."""

    items: list[WorkflowRunSummary]
    total: int


class RunAccepted(ApiModel):
    """202 body for ``POST /api/sessions/{id}/run`` and ``.../run/resume``."""

    run_id: str
    status: RunStatus
