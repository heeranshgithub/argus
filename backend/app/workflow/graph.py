"""Graph assembly — wire the six nodes, the conditional edge, and retry policy.

Linear backbone with one loop:

    planner → researcher → signal_extractor → analyst → quality_check
                  ▲                                         │
                  └──────── [needs_more_research] ──────────┘
                                                            │
                                                       reporter → END

``quality_check`` is the required conditional edge: it routes back to
``researcher`` while coverage is weak (bounded by ``research_iteration``), else
forward to ``reporter``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

import httpx
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps
from app.workflow.nodes.analyst import build_analyst
from app.workflow.nodes.planner import build_planner
from app.workflow.nodes.quality_check import build_quality_check
from app.workflow.nodes.reporter import build_reporter
from app.workflow.nodes.researcher import build_researcher
from app.workflow.nodes.signal_extractor import build_signal_extractor
from app.workflow.state import GraphState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

log = get_logger("workflow.graph")

# Exceptions worth a node-level retry — transient transport hiccups only.
# Deterministic failures (schema/validation/empty-source) won't fix on retry.
_TRANSIENT = (httpx.HTTPError, ConnectionError, TimeoutError, asyncio.TimeoutError)


def _retry_on(exc: Exception) -> bool:
    return isinstance(exc, _TRANSIENT)


def route_after_quality(
    state: GraphState, *, max_iterations: int
) -> Literal["researcher", "reporter"]:
    """Decide whether to loop back for more research or finalize the report.

    Loops to ``researcher`` only while the quality gate asks for more *and* we
    haven't hit the research-iteration cap — otherwise proceeds to ``reporter``.
    """
    quality = state.get("quality")
    iteration = state.get("research_iteration", 0)
    if quality and quality.get("needs_more_research") and iteration < max_iterations:
        log.info("route_back_to_researcher", iteration=iteration)
        return "researcher"
    log.info("route_to_reporter", iteration=iteration)
    return "reporter"


def build_graph(
    deps: WorkflowDeps,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Assemble and compile the workflow graph.

    Args:
        deps: External capabilities (LLM, search, fetch) injected into nodes.
        checkpointer: Optional Mongo-backed saver enabling resume-from-crash.

    Returns:
        A compiled LangGraph ready for ``ainvoke``.
    """
    retry = RetryPolicy(
        max_attempts=deps.settings.workflow_node_retry_limit, retry_on=_retry_on
    )
    builder: StateGraph = StateGraph(GraphState)

    nodes = {
        "planner": build_planner(deps),
        "researcher": build_researcher(deps),
        "signal_extractor": build_signal_extractor(deps),
        "analyst": build_analyst(deps),
        "quality_check": build_quality_check(deps),
        "reporter": build_reporter(deps),
    }
    for name, fn in nodes.items():
        # langgraph's add_node overloads don't recognize a plain async callable
        # returning a partial-state dict; the runtime contract is correct.
        builder.add_node(name, fn, retry_policy=retry)  # type: ignore[call-overload]

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "signal_extractor")
    builder.add_edge("signal_extractor", "analyst")
    builder.add_edge("analyst", "quality_check")

    max_iterations = deps.settings.workflow_max_research_iterations
    builder.add_conditional_edges(
        "quality_check",
        lambda state: route_after_quality(state, max_iterations=max_iterations),
        {"researcher": "researcher", "reporter": "reporter"},
    )
    builder.add_edge("reporter", END)

    return builder.compile(checkpointer=checkpointer)
