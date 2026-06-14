"""``reporter`` node — produce and persist the final nine-section report.

The LLM emits a wire-shaped :class:`ReportDraft`. We then *deterministically*
rebuild the ``sources`` section from the gathered ``raw_sources`` ranked by how
often each was used as evidence — so section 9 is always grounded and present,
regardless of how the model populated it. Finally we persist the report to the
``reports`` collection so it's queryable independently of the graph state.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

from app.logging_config import get_logger
from app.models.report import ReportDraft, ReportSource
from app.repositories import report_repo
from app.workflow.deps import WorkflowDeps
from app.workflow.events import current_run_context, emit_node
from app.workflow.nodes._render import render_analysis, render_signals, render_sources
from app.workflow.prompts.reporter import REPORTER_SYSTEM, reporter_user
from app.workflow.state import GraphState, RawSource

log = get_logger("workflow.node.reporter")

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]


def _usage_counts(draft: ReportDraft) -> Counter[str]:
    """Count how often each URL appears as signal evidence in the draft."""
    counts: Counter[str] = Counter()
    for sig in draft.business_signals:
        for url in sig.evidence_urls:
            counts[url] += 1
    return counts


def _build_sources(
    raw_sources: list[RawSource], draft: ReportDraft
) -> list[ReportSource]:
    """Canonical, deduped sources from ``raw_sources`` ranked by evidence usage."""
    usage = _usage_counts(draft)
    # Stable ordering: most-cited first, then original discovery order.
    ordered = sorted(
        enumerate(raw_sources), key=lambda iv: (-usage[iv[1]["url"]], iv[0])
    )
    sources: list[ReportSource] = []
    seen: set[str] = set()
    for _, src in ordered:
        if src["url"] in seen:
            continue
        seen.add(src["url"])
        used_in = ["sources"]
        if usage[src["url"]]:
            used_in.insert(0, "businessSignals")
        sources.append(
            ReportSource(url=src["url"], title=src["title"], used_in=used_in)
        )
    return sources


def build_reporter(deps: WorkflowDeps) -> NodeFn:
    """Build the reporter node bound to ``deps``."""
    model = deps.settings.model_for_node("reporter")

    async def reporter(state: GraphState) -> dict[str, Any]:
        async with emit_node("reporter") as ev:
            sources = state.get("raw_sources") or []
            signals = state.get("extracted_signals") or []
            analysis = state.get("analysis")

            user = reporter_user(
                state["company_name"],
                state["objective"],
                render_analysis(analysis),
                render_signals(signals),
                render_sources(sources),
            )
            # Generous token budget: the report is the largest single output.
            draft = await deps.llm.complete(
                REPORTER_SYSTEM, user, response_model=ReportDraft, model=model, max_tokens=4000
            )

            # Ground section 9 in our actual sources, ranked by usage.
            draft.sources = _build_sources(sources, draft)

            # Persist independently of the graph state (queryable in Part 4).
            ctx = current_run_context()
            report = await report_repo.upsert_report(ctx.db, state["session_id"], draft)

            await ev.output({"report_id": report.id})
            ev.set_preview(
                {
                    "report_id": report.id,
                    "sections": 9,
                    "sources": len(draft.sources),
                }
            )
            log.info(
                "reporter_done",
                report_id=report.id,
                sources=len(draft.sources),
                signals=len(draft.business_signals),
            )
            return {"report": draft.model_dump()}

    return reporter
