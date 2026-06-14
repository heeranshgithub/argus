"""``GraphState`` — the shared state threaded through every node.

LangGraph merges each node's partial return into this dict. Channels annotated
with a reducer (``Annotated[list[...], add]``) *accumulate* across updates — this
is what lets the ``researcher`` node append new sources when ``quality_check``
loops back for another research iteration, instead of clobbering earlier work.
Plain channels are last-write-wins.

Everything here must be msgpack/JSON-serializable: the whole state is snapshotted
into the Mongo checkpointer after every super-step, so no live handles (db
clients, queues, …) may live in the state — those travel via ``events.RunContext``.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class SubQuestion(TypedDict):
    """One research sub-question produced by the planner."""

    id: str
    question: str
    rationale: str


class RawSource(TypedDict):
    """A fetched-and-cleaned source document."""

    url: str
    title: str
    snippet: str
    content: str  # cleaned text, capped at N chars
    fetched_at: str  # ISO 8601


class BusinessSignal(TypedDict):
    """A signal extracted from sources, grouped by category."""

    category: str  # 'funding' | 'hiring' | 'product' | 'news' | 'partnership' | 'other'
    summary: str
    evidence_urls: list[str]
    confidence: float  # 0..1


class AnalysisBlock(TypedDict):
    """The analyst's synthesis of the gathered material."""

    overview: str
    products_services: list[str]
    target_customers: list[str]
    risks: list[str]
    unknowns: list[str]


class QualityVerdict(TypedDict):
    """The quality gate's assessment, driving the conditional edge."""

    coverage_score: float  # 0..1
    confidence_score: float  # 0..1
    missing_areas: list[str]
    needs_more_research: bool


def _merge_unique_sources(
    left: list[RawSource], right: list[RawSource]
) -> list[RawSource]:
    """Reducer for ``raw_sources``: append new sources, de-duplicating by URL.

    A plain ``operator.add`` would let the same URL accumulate across research
    iterations; this keeps the first occurrence of each URL and drops repeats.
    """
    seen: set[str] = {src["url"] for src in left}
    merged = list(left)
    for src in right:
        if src["url"] in seen:
            continue
        seen.add(src["url"])
        merged.append(src)
    return merged


class GraphState(TypedDict, total=False):
    """The workflow's shared state (all keys optional; nodes fill them in)."""

    # --- inputs ----------------------------------------------------------------
    session_id: str
    run_id: str
    company_name: str
    website: str
    objective: str

    # --- outputs accumulated per node ------------------------------------------
    plan: list[SubQuestion]
    raw_sources: Annotated[list[RawSource], _merge_unique_sources]  # appended, deduped
    extracted_signals: list[BusinessSignal]
    analysis: AnalysisBlock
    quality: QualityVerdict
    report: dict[str, Any]  # final structured report (ReportDraft dump)

    # --- control ---------------------------------------------------------------
    retry_counts: dict[str, int]  # node_name -> count
    errors: Annotated[list[dict[str, Any]], add]  # append-only error log
    research_iteration: int  # incremented per research loop
    # Sub-question ids already researched, so a second research pass only chases
    # the new gap-closing questions instead of re-fetching everything.
    researched_question_ids: Annotated[list[str], add]
