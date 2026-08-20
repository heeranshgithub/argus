"""``WorkflowRunner`` — orchestrate one graph run end-to-end.

Bridges the API/service layer and the LangGraph graph: it creates the run
record, flips session status, binds the per-run :class:`RunContext` (so nodes can
emit events), invokes the graph with the Mongo checkpointer, and records the
terminal outcome. ``start`` does the synchronous prep and returns a ``run_id``;
``execute`` is the (background) coroutine that actually runs the graph.
"""

from __future__ import annotations

import contextlib
import traceback as traceback_mod
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.metrics import metrics
from app.models.session import SessionStatus
from app.models.workflow import WorkflowError
from app.repositories import session_repo, workflow_repo
from app.workflow.checkpointer import MongoCheckpointer
from app.workflow.events import (
    RUN_NODE,
    EventKind,
    RunContext,
    bind_run_context,
    emit,
    event_bus,
)
from app.workflow.failure import classify
from app.workflow.graph import build_graph
from app.workflow.tools import llm as llm_tool

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

    from app.workflow.deps import WorkflowDeps

log = get_logger("workflow.runner")


def _error_from(exc: Exception) -> WorkflowError:
    """Build the sanitized, client-visible :class:`WorkflowError` for ``exc``.

    Classification lives in :mod:`app.workflow.failure`; nothing derived from the
    exception's own text reaches this model. It cannot raise — it is called from
    the failure handler, and a raise there would strand the run as ``running``,
    which is the exact bug this path once had.
    """
    failure = classify(exc)
    return WorkflowError(
        code=failure.code, message=failure.message, retryable=failure.retryable
    )


def _detail_from(exc: Exception) -> str:
    """Raw exception text + traceback, for logs and ``error_detail`` only."""
    try:
        return (
            f"{type(exc).__name__}: {exc}\n{traceback_mod.format_exc(limit=12)}"
        )
    except Exception:
        return type(exc).__name__


class WorkflowRunner:
    """Runs (and resumes) the research workflow for a session."""

    def __init__(self, db: AsyncIOMotorDatabase, deps: WorkflowDeps) -> None:
        self.db = db
        self.deps = deps
        self.settings = deps.settings

    async def start(self, session_id: str) -> str:
        """Create a run record and mark the session running; return the run id.

        Synchronous prep only — the caller schedules :meth:`execute` to actually
        run the graph (e.g., via FastAPI ``BackgroundTasks``).
        """
        run_id = await workflow_repo.create_run(self.db, session_id)
        await session_repo.update_status(self.db, session_id, SessionStatus.RUNNING)
        log.info("run_started", run_id=run_id, session_id=session_id)
        return run_id

    async def resume(self, session_id: str) -> str:
        """Create a fresh run record for a resume attempt; return the run id.

        Reuses ``thread_id == session_id`` so the checkpointer continues from the
        last completed node instead of re-running earlier work.
        """
        run_id = await workflow_repo.create_run(self.db, session_id)
        await session_repo.update_status(self.db, session_id, SessionStatus.RUNNING)
        log.info("run_resuming", run_id=run_id, session_id=session_id)
        return run_id

    async def execute(self, run_id: str, session_id: str, *, resume: bool = False) -> None:
        """Run the graph to completion, recording success/failure.

        Binds the run context, invokes the graph with the Mongo checkpointer, and
        on any uncaught error marks the run + session ``failed`` (a later resume is
        allowed). On success marks both ``completed``.
        """
        ctx = RunContext(
            db=self.db,
            run_id=run_id,
            session_id=session_id,
            bus=event_bus,
            cost_cap_usd=self.settings.workflow_max_cost_usd,
        )
        # Route every LLM call's cost into this run's accumulator so the soft cap
        # can be enforced at node boundaries (PLAN_PART_5 §2.1).
        cost_token = llm_tool.set_cost_reporter(ctx.record_cost)
        async with bind_run_context(ctx):
            await emit(EventKind.RUN_STARTED, node=RUN_NODE, payload={"resume": resume})
            try:
                final_state = await self._invoke(run_id, session_id, resume=resume)
            except Exception as exc:
                await self._fail(run_id, session_id, exc)
                return
            finally:
                llm_tool.reset_cost_reporter(cost_token)
            await self._complete(run_id, session_id, final_state)

    async def _invoke(
        self, run_id: str, session_id: str, *, resume: bool
    ) -> dict[str, Any]:
        """Build the graph and invoke it, returning the final state."""
        checkpointer = MongoCheckpointer(self.db)
        graph = build_graph(self.deps, checkpointer=checkpointer)
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": self.settings.workflow_recursion_limit,
        }

        if resume:
            # Pass None so LangGraph resumes from the last checkpoint.
            return await graph.ainvoke(None, config=config)

        session = await session_repo.get(self.db, session_id)
        if session is None:  # pragma: no cover - guarded by the service/API layer
            raise RuntimeError(f"Session {session_id!r} disappeared before run.")
        initial: dict[str, Any] = {
            "session_id": session_id,
            "run_id": run_id,
            "company_name": session.company_name,
            "website": session.website,
            "objective": session.objective,
            "research_iteration": 0,
        }
        return await graph.ainvoke(initial, config=config)

    async def _complete(
        self, run_id: str, session_id: str, final_state: dict[str, Any]
    ) -> None:
        """Mark a run + session completed and emit ``run_completed``."""
        raw_sources = final_state.get("raw_sources") or []
        await workflow_repo.mark_completed(
            self.db,
            run_id,
            final_state_keys=sorted(final_state.keys()),
            raw_sources=raw_sources,
        )
        await session_repo.update_status(self.db, session_id, SessionStatus.COMPLETED)
        metrics.incr_workflow_run("completed")
        await emit(
            EventKind.RUN_COMPLETED,
            node=RUN_NODE,
            payload={"final_state_keys": sorted(final_state.keys())},
        )
        log.info("run_completed", run_id=run_id, session_id=session_id)

    async def _fail(self, run_id: str, session_id: str, exc: Exception) -> None:
        """Mark a run + session failed and emit ``run_failed``.

        This is the last line of defence for a run: if it raises, the run is left
        ``running`` forever and the UI streams an event that never arrives. So it
        must not be able to fail on malformed inputs — every step below is either
        total or guarded.
        """
        error = _error_from(exc)
        detail = _detail_from(exc)
        try:
            await workflow_repo.mark_failed(
                self.db, run_id, error=error, detail=detail
            )
            await session_repo.update_status(self.db, session_id, SessionStatus.FAILED)
        finally:
            # Even if persistence failed, still tell the log and any live listener
            # — a stream that ends badly beats one that hangs.
            metrics.incr_workflow_run("failed")
            with contextlib.suppress(Exception):
                await emit(
                    EventKind.RUN_FAILED,
                    node=RUN_NODE,
                    payload={"code": error.code, "message": error.message},
                )
            # The raw text lives here and nowhere the client can reach.
            log.error(
                "run_failed",
                run_id=run_id,
                session_id=session_id,
                code=error.code,
                retryable=error.retryable,
                detail=detail,
            )
