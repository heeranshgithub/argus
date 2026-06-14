"""Reporter node tests — nine sections, grounded sources, persistence."""

from app.models.report import ReportOut
from app.repositories import report_repo
from app.workflow.nodes.reporter import build_reporter
from tests.workflow.conftest import base_state, invoke_node

_NINE_SECTIONS = {
    "company_overview",
    "products_and_services",
    "target_customers",
    "business_signals",
    "risks_and_challenges",
    "suggested_discovery_questions",
    "suggested_outreach_strategy",
    "unknowns",
    "sources",
}


def _report_state():
    return base_state(
        raw_sources=[
            {
                "url": "https://example.com/news",
                "title": "News",
                "snippet": "",
                "content": "Series B",
                "fetched_at": "t",
            },
            {
                "url": "https://example.com/other",
                "title": "Other",
                "snippet": "",
                "content": "misc",
                "fetched_at": "t",
            },
        ],
        extracted_signals=[
            {
                "category": "funding",
                "summary": "Series B",
                "evidence_urls": ["https://example.com/news"],
                "confidence": 0.9,
            }
        ],
        analysis={
            "overview": "o",
            "products_services": [],
            "target_customers": [],
            "risks": [],
            "unknowns": [],
        },
    )


async def test_reporter_persists_nine_section_report(deps, db) -> None:
    node = build_reporter(deps)
    update, _ = await invoke_node(node, _report_state(), db)

    report = update["report"]
    assert set(report) >= _NINE_SECTIONS

    # Persisted independently and validates as a ReportOut.
    stored = await report_repo.get_by_session(db, "sess-test")
    assert isinstance(stored, ReportOut)
    assert stored.company_overview
    assert len(stored.suggested_discovery_questions) >= 1


async def test_reporter_sources_grounded_and_ranked_by_usage(deps, db) -> None:
    node = build_reporter(deps)
    update, _ = await invoke_node(node, _report_state(), db)

    sources = update["report"]["sources"]
    urls = [s["url"] for s in sources]
    # Both raw sources present, the evidence-cited one ranked first.
    assert set(urls) == {"https://example.com/news", "https://example.com/other"}
    assert urls[0] == "https://example.com/news"
    assert "businessSignals" in sources[0]["used_in"]
