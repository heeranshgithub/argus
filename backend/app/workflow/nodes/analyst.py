"""``analyst`` node — synthesize sources + signals into a structured analysis.

The LLM client validates the output against :class:`AnalysisResult` at the node
boundary (with its own one-shot repair retry on schema failure), so this node
just maps the validated result into the ``AnalysisBlock`` state shape.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps
from app.workflow.events import emit_node
from app.workflow.nodes._render import render_signals, render_sources
from app.workflow.prompts.analyst import ANALYST_SYSTEM, analyst_user
from app.workflow.schemas import AnalysisResult
from app.workflow.state import AnalysisBlock, GraphState

log = get_logger("workflow.node.analyst")

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]


def build_analyst(deps: WorkflowDeps) -> NodeFn:
    """Build the analyst node bound to ``deps``."""
    model = deps.settings.model_for_node("analyst")

    async def analyst(state: GraphState) -> dict[str, Any]:
        async with emit_node("analyst") as ev:
            sources = state.get("raw_sources") or []
            signals = state.get("extracted_signals") or []

            user = analyst_user(
                state["company_name"],
                state["objective"],
                render_signals(signals),
                render_sources(sources),
            )
            result = await deps.llm.complete(
                ANALYST_SYSTEM, user, response_model=AnalysisResult, model=model, max_tokens=3000
            )

            analysis = AnalysisBlock(
                overview=result.overview,
                products_services=result.products_services,
                target_customers=result.target_customers,
                risks=result.risks,
                unknowns=result.unknowns,
            )

            ev.set_preview({"overview_chars": len(result.overview)})
            log.info(
                "analyst_done",
                products=len(result.products_services),
                risks=len(result.risks),
            )
            return {"analysis": analysis}

    return analyst
