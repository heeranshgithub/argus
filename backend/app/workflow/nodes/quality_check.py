"""``quality_check`` node — gate report readiness and drive the conditional edge.

The node produces a :class:`QualityVerdict`; the *routing* decision lives in
``graph.route_after_quality`` so the edge logic is testable in isolation. The
loop is bounded by ``research_iteration`` (incremented by the researcher), which
this node also mirrors into ``retry_counts`` for audit visibility.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps
from app.workflow.events import emit_node
from app.workflow.nodes._render import render_analysis, render_signals
from app.workflow.prompts.quality_check import (
    QUALITY_CHECK_SYSTEM,
    quality_check_user,
)
from app.workflow.schemas import QualityResult
from app.workflow.state import GraphState, QualityVerdict

log = get_logger("workflow.node.quality_check")

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]


def build_quality_check(deps: WorkflowDeps) -> NodeFn:
    """Build the quality-check node bound to ``deps``."""
    model = deps.settings.model_for_node("quality_check")

    async def quality_check(state: GraphState) -> dict[str, Any]:
        async with emit_node("quality_check") as ev:
            iteration = state.get("research_iteration", 0)
            analysis = state.get("analysis")
            signals = state.get("extracted_signals") or []
            source_count = len(state.get("raw_sources") or [])

            user = quality_check_user(
                state["objective"],
                render_analysis(analysis),
                render_signals(signals),
                source_count,
                iteration,
            )
            result = await deps.llm.complete(
                QUALITY_CHECK_SYSTEM, user, response_model=QualityResult, model=model
            )

            verdict = QualityVerdict(
                coverage_score=result.coverage_score,
                confidence_score=result.confidence_score,
                missing_areas=result.missing_areas,
                needs_more_research=result.needs_more_research,
            )

            retry_counts = {**(state.get("retry_counts") or {}), "researcher": iteration}
            ev.set_preview(
                {
                    "coverage": result.coverage_score,
                    "confidence": result.confidence_score,
                    "needs_more_research": result.needs_more_research,
                }
            )
            log.info(
                "quality_check_done",
                coverage=result.coverage_score,
                confidence=result.confidence_score,
                needs_more_research=result.needs_more_research,
                iteration=iteration,
            )
            return {"quality": verdict, "retry_counts": retry_counts}

    return quality_check
