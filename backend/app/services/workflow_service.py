"""Workflow orchestration above the runner.

Validates requests (session exists, not already running, resumable) and schedules
the background graph execution, keeping route handlers thin and the standard
domain errors here rather than leaking ``None``/conflicts into the API layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.exceptions import (
    ReportNotFound,
    RunNotFound,
    SessionAlreadyRunning,
    SessionNotResumable,
)
from app.models.report import ReportOut
from app.models.session import SessionStatus
from app.models.workflow import RunAccepted, RunStatus, WorkflowRunOut, WorkflowRunSummary
from app.repositories import report_repo, workflow_repo
from app.services import session_service
from app.workflow.runner import WorkflowRunner

if TYPE_CHECKING:
    from fastapi import BackgroundTasks
    from motor.motor_asyncio import AsyncIOMotorDatabase

    from app.workflow.deps import WorkflowDeps


async def start_run(
    db: AsyncIOMotorDatabase,
    deps: WorkflowDeps,
    session_id: str,
    background_tasks: BackgroundTasks,
) -> RunAccepted:
    """Validate, create a run, and schedule the graph in the background."""
    await session_service.get_session(db, session_id)  # raises SessionNotFound
    if await workflow_repo.has_active_run(db, session_id):
        raise SessionAlreadyRunning(session_id)

    runner = WorkflowRunner(db, deps)
    run_id = await runner.start(session_id)
    background_tasks.add_task(runner.execute, run_id, session_id)
    return RunAccepted(run_id=run_id, status=RunStatus.RUNNING)


async def resume_run(
    db: AsyncIOMotorDatabase,
    deps: WorkflowDeps,
    session_id: str,
    background_tasks: BackgroundTasks,
) -> RunAccepted:
    """Resume a failed session's workflow from its last checkpoint."""
    session = await session_service.get_session(db, session_id)
    if session.status is not SessionStatus.FAILED:
        raise SessionNotResumable(session_id, session.status.value)

    runner = WorkflowRunner(db, deps)
    run_id = await runner.resume(session_id)
    background_tasks.add_task(runner.execute, run_id, session_id, resume=True)
    return RunAccepted(run_id=run_id, status=RunStatus.RUNNING)


async def list_runs(
    db: AsyncIOMotorDatabase, session_id: str, *, limit: int, skip: int
) -> tuple[list[WorkflowRunSummary], int]:
    """List a session's runs (newest-first) plus the total count."""
    await session_service.get_session(db, session_id)  # raises SessionNotFound
    items = await workflow_repo.list_runs(db, session_id, limit=limit, skip=skip)
    total = await workflow_repo.count_runs(db, session_id)
    return items, total


async def get_run(
    db: AsyncIOMotorDatabase, session_id: str, run_id: str
) -> WorkflowRunOut:
    """Fetch one run (with events), enforcing it belongs to the session."""
    run = await workflow_repo.get_run(db, run_id)
    if run is None or run.session_id != session_id:
        raise RunNotFound(run_id)
    return run


async def get_report(db: AsyncIOMotorDatabase, session_id: str) -> ReportOut:
    """Fetch the session's report, raising :class:`ReportNotFound` if absent."""
    await session_service.get_session(db, session_id)  # raises SessionNotFound
    report = await report_repo.get_by_session(db, session_id)
    if report is None:
        raise ReportNotFound(session_id)
    return report
