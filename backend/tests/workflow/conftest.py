"""Shared fixtures for workflow tests: in-memory Mongo + deterministic fakes.

Every node test runs fully offline: a :class:`FakeLLMClient` scripted by response
model, a fake search client, and a fake fetcher. Helpers here build a minimal
``GraphState`` and a bound :class:`RunContext` so ``emit_node`` has somewhere to
write events.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.config import Settings
from app.models.report import ReportDraft
from app.repositories import workflow_repo
from app.workflow.deps import WorkflowDeps
from app.workflow.events import RunContext, bind_run_context
from app.workflow.schemas import (
    AnalysisResult,
    PlanResult,
    QualityResult,
    SignalsResult,
)
from app.workflow.state import GraphState
from app.workflow.tools.fetch import FetchedPage
from app.workflow.tools.llm import FakeLLMClient
from app.workflow.tools.search import SearchHit

SESSION_ID = "sess-test"


# --- fake clients --------------------------------------------------------------


class FakeSearchClient:
    """Deterministic search: returns configured hits (or a generic default)."""

    def __init__(self, by_query: dict[str, list[SearchHit]] | None = None) -> None:
        self._by_query = by_query or {}
        self.calls: list[str] = []

    async def search(self, query: str, k: int = 5) -> list[SearchHit]:
        self.calls.append(query)
        if query in self._by_query:
            return self._by_query[query][:k]
        return [
            SearchHit(
                url="https://example.com/news",
                title="Acme raises Series B",
                snippet="Acme announced a $40M Series B to expand its platform.",
            ),
            SearchHit(
                url="https://example.com/product",
                title="Acme Product",
                snippet="Acme builds analytics tooling for retailers.",
            ),
        ][:k]


class FakeFetcher:
    """Deterministic fetcher: returns configured pages (or a generic default)."""

    def __init__(self, by_url: dict[str, FetchedPage] | None = None) -> None:
        self._by_url = by_url or {}
        self.calls: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url in self._by_url:
            return self._by_url[url]
        return FetchedPage(
            url=url,
            status=200,
            content_type="text/html",
            html="<p>content</p>",
            text=f"Cleaned content for {url}. Acme sells analytics to retailers.",
        )


# --- scripted LLM happy path ---------------------------------------------------


def make_plan(n: int = 5) -> PlanResult:
    return PlanResult(
        questions=[
            {"question": f"Question {i}?", "rationale": f"Rationale {i}"}
            for i in range(n)
        ]
    )


def make_signals() -> SignalsResult:
    return SignalsResult(
        signals=[
            {
                "category": "funding",
                "summary": "Acme raised a $40M Series B.",
                "evidence_urls": ["https://example.com/news"],
                "confidence": 0.9,
            }
        ]
    )


def make_analysis() -> AnalysisResult:
    return AnalysisResult(
        overview="Acme builds analytics tooling for retailers.",
        products_services=["Analytics platform"],
        target_customers=["Mid-market retailers"],
        risks=["Crowded analytics market"],
        unknowns=["Pricing tiers"],
    )


def make_quality(*, needs_more: bool = False, missing: list[str] | None = None) -> QualityResult:
    return QualityResult(
        coverage_score=0.6 if needs_more else 0.9,
        confidence_score=0.6 if needs_more else 0.9,
        missing_areas=missing or ([] if not needs_more else ["pricing"]),
        needs_more_research=needs_more,
    )


def make_report() -> ReportDraft:
    return ReportDraft(
        company_overview="Acme is an analytics company.",
        products_and_services=["Analytics platform"],
        target_customers=["Mid-market retailers"],
        business_signals=[
            {
                "category": "funding",
                "summary": "Acme raised a $40M Series B.",
                "evidenceUrls": ["https://example.com/news"],
                "confidence": 0.9,
            }
        ],
        risks_and_challenges=["Crowded market"],
        suggested_discovery_questions=[
            {"question": "What is your expansion plan?", "rationale": "Ties to objective"}
        ],
        suggested_outreach_strategy="Lead with the Series B momentum.",
        unknowns=["Pricing"],
        sources=[],
    )


def happy_path_llm() -> FakeLLMClient:
    """A FakeLLMClient scripted for a clean single-pass run."""
    return FakeLLMClient(
        {
            "PlanResult": [make_plan()],
            "SignalsResult": [make_signals()],
            "AnalysisResult": [make_analysis()],
            "QualityResult": [make_quality(needs_more=False)],
            "ReportDraft": [make_report()],
        }
    )


# --- fixtures ------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    return Settings(env="test", mongo_db_name="argus_test")


@pytest.fixture
def db() -> Any:
    return AsyncMongoMockClient(tz_aware=True)["argus_test"]


@pytest.fixture
def fake_search() -> FakeSearchClient:
    return FakeSearchClient()


@pytest.fixture
def fake_fetcher() -> FakeFetcher:
    return FakeFetcher()


@pytest.fixture
def deps(
    settings: Settings, fake_search: FakeSearchClient, fake_fetcher: FakeFetcher
) -> WorkflowDeps:
    """Workflow deps with a happy-path LLM and fake search/fetch."""
    return WorkflowDeps(
        llm=happy_path_llm(),
        search=fake_search,
        fetcher=fake_fetcher,
        settings=settings,
    )


@pytest.fixture
async def ctx(db: Any) -> AsyncIterator[RunContext]:
    """A bound RunContext (with a real run document) for node-level emits."""
    run_id = await workflow_repo.create_run(db, SESSION_ID)
    async with bind_run_context(
        RunContext(db=db, run_id=run_id, session_id=SESSION_ID)
    ) as bound:
        yield bound


def base_state(**overrides: Any) -> GraphState:
    """Minimal valid GraphState for node tests."""
    state: GraphState = {
        "session_id": SESSION_ID,
        "run_id": "run-test",
        "company_name": "Acme",
        "website": "https://example.com",
        "objective": "Explore an expansion partnership.",
        "research_iteration": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


async def invoke_node(
    node_fn: Any, state: GraphState, db: Any, *, session_id: str = SESSION_ID
) -> tuple[dict[str, Any], str]:
    """Run a node inside a fresh bound RunContext; return ``(update, run_id)``.

    Binding explicitly (rather than via a fixture) keeps the contextvar in the
    same task as the node call, so ``emit_node`` reliably finds the context.
    """
    run_id = await workflow_repo.create_run(db, session_id)
    async with bind_run_context(
        RunContext(db=db, run_id=run_id, session_id=session_id)
    ):
        update = await node_fn(state)
    return update, run_id
