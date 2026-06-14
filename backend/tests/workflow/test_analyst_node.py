"""Analyst node tests — structured synthesis into the AnalysisBlock shape."""

from app.workflow.nodes.analyst import build_analyst
from tests.workflow.conftest import base_state, invoke_node


async def test_analyst_produces_analysis_block(deps, db) -> None:
    node = build_analyst(deps)
    state = base_state(
        raw_sources=[
            {"url": "https://x", "title": "x", "snippet": "", "content": "c", "fetched_at": "t"}
        ],
        extracted_signals=[
            {
                "category": "funding",
                "summary": "Series B",
                "evidence_urls": ["https://x"],
                "confidence": 0.9,
            }
        ],
    )

    update, _ = await invoke_node(node, state, db)

    analysis = update["analysis"]
    assert set(analysis) == {
        "overview",
        "products_services",
        "target_customers",
        "risks",
        "unknowns",
    }
    assert analysis["overview"]
    assert analysis["products_services"] == ["Analytics platform"]
