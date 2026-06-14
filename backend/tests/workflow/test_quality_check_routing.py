"""Quality-check node + the required conditional edge's routing logic."""

from app.workflow.graph import route_after_quality
from app.workflow.nodes.quality_check import build_quality_check
from app.workflow.schemas import QualityResult
from app.workflow.tools.llm import FakeLLMClient
from tests.workflow.conftest import base_state, invoke_node


async def test_quality_check_produces_verdict(deps, db) -> None:
    node = build_quality_check(deps)
    state = base_state(research_iteration=1, analysis={"overview": "o"})

    update, _ = await invoke_node(node, state, db)

    verdict = update["quality"]
    assert verdict["needs_more_research"] is False
    assert 0.0 <= verdict["coverage_score"] <= 1.0
    # retry_counts mirrors the research iteration for audit visibility.
    assert update["retry_counts"]["researcher"] == 1


def test_route_back_when_low_quality_and_under_cap() -> None:
    state = base_state(
        research_iteration=1,
        quality={
            "coverage_score": 0.3,
            "confidence_score": 0.3,
            "missing_areas": ["pricing"],
            "needs_more_research": True,
        },
    )
    assert route_after_quality(state, max_iterations=2) == "researcher"


def test_route_to_reporter_when_cap_reached() -> None:
    state = base_state(
        research_iteration=2,  # hit the cap
        quality={
            "coverage_score": 0.3,
            "confidence_score": 0.3,
            "missing_areas": ["pricing"],
            "needs_more_research": True,
        },
    )
    assert route_after_quality(state, max_iterations=2) == "reporter"


def test_route_to_reporter_when_quality_good() -> None:
    state = base_state(
        research_iteration=1,
        quality={
            "coverage_score": 0.9,
            "confidence_score": 0.9,
            "missing_areas": [],
            "needs_more_research": False,
        },
    )
    assert route_after_quality(state, max_iterations=2) == "reporter"


async def test_quality_check_low_then_high_routing(deps, db) -> None:
    """Scripted low verdict routes back; high verdict proceeds."""
    deps.llm = FakeLLMClient(
        {
            "QualityResult": [
                QualityResult(
                    coverage_score=0.3,
                    confidence_score=0.3,
                    missing_areas=["pricing"],
                    needs_more_research=True,
                ),
                QualityResult(
                    coverage_score=0.9,
                    confidence_score=0.9,
                    missing_areas=[],
                    needs_more_research=False,
                ),
            ]
        },
        repeat_last=False,
    )
    node = build_quality_check(deps)

    low_update, _ = await invoke_node(node, base_state(research_iteration=1), db)
    assert route_after_quality(
        {**base_state(research_iteration=1), **low_update}, max_iterations=2
    ) == "researcher"

    high_update, _ = await invoke_node(node, base_state(research_iteration=1), db)
    assert route_after_quality(
        {**base_state(research_iteration=1), **high_update}, max_iterations=2
    ) == "reporter"
