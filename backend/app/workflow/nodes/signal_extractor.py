"""``signal_extractor`` node — sources → categorized business signals.

Runs a single LLM call over the rendered sources, keeping each signal grounded in
real ``evidence_urls`` drawn from those sources.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps
from app.workflow.events import emit_node
from app.workflow.nodes._render import render_sources
from app.workflow.prompts.signal_extractor import (
    SIGNAL_EXTRACTOR_SYSTEM,
    signal_extractor_user,
)
from app.workflow.schemas import SignalsResult
from app.workflow.state import BusinessSignal, GraphState

log = get_logger("workflow.node.signal_extractor")

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]


def build_signal_extractor(deps: WorkflowDeps) -> NodeFn:
    """Build the signal-extractor node bound to ``deps``."""
    model = deps.settings.model_for_node("signal_extractor")

    async def signal_extractor(state: GraphState) -> dict[str, Any]:
        async with emit_node("signal_extractor") as ev:
            sources = state.get("raw_sources") or []
            valid_urls = {src["url"] for src in sources}

            user = signal_extractor_user(state["objective"], render_sources(sources))
            result = await deps.llm.complete(
                SIGNAL_EXTRACTOR_SYSTEM,
                user,
                response_model=SignalsResult,
                model=model,
            )

            signals: list[BusinessSignal] = [
                BusinessSignal(
                    category=sig.category,
                    summary=sig.summary,
                    # Keep only evidence URLs that actually came from our sources.
                    evidence_urls=[u for u in sig.evidence_urls if u in valid_urls],
                    confidence=sig.confidence,
                )
                for sig in result.signals
            ]

            ev.set_preview({"signals": len(signals)})
            log.info("signal_extractor_done", signals=len(signals))
            return {"extracted_signals": signals}

    return signal_extractor
