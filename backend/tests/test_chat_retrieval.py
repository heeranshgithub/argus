"""Unit tests for chat retrieval: BM25 ranking + prompt pack assembly."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.report import (
    BusinessSignalOut,
    DiscoveryQuestion,
    ReportOut,
    ReportSource,
)
from app.retrieval.bm25 import Bm25Index, tokenize
from app.retrieval.pack import (
    SelectedSource,
    build_messages,
    parse_citations,
    report_to_markdown,
    select_sources,
)

# A 20-document corpus, each clearly "about" a distinct topic keyword.
_TOPICS = [
    "funding series investment venture capital raised",
    "hiring engineers recruiting talent headcount growth",
    "product launch feature release roadmap shipping",
    "partnership integration alliance ecosystem collaboration",
    "acquisition merger acquired buyout consolidation",
    "revenue earnings profit financials quarterly results",
    "customers enterprise clients adoption logos retention",
    "competition rivals market share competitors landscape",
    "security compliance soc2 encryption privacy audit",
    "pricing plans subscription tiers cost billing",
    "leadership executive ceo founder management team",
    "expansion international global europe asia markets",
    "research ai machine learning models innovation",
    "support documentation onboarding success training",
    "marketing campaign brand awareness demand generation",
    "infrastructure cloud scaling reliability uptime",
    "open source community contributors github developers",
    "regulation legal policy government lawsuit risk",
    "sustainability climate carbon environmental esg",
    "mobile app ios android downloads users",
]


def _corpus_sources() -> list[dict[str, str]]:
    return [
        {
            "url": f"https://example.com/{i}",
            "title": f"Article {i}",
            "snippet": topic,
            "content": topic + " " + topic,
        }
        for i, topic in enumerate(_TOPICS)
    ]


def test_tokenize_lowercases_and_splits() -> None:
    assert tokenize("Series-A Funding, $10M!") == ["series", "a", "funding", "10m"]


def test_bm25_top_k_ranks_matching_document_first() -> None:
    index = Bm25Index(_TOPICS)
    # Each query targets exactly one topic; that topic must rank first.
    cases = {
        "venture capital funding round": 0,
        "recruiting engineers headcount": 1,
        "product feature roadmap release": 2,
        "soc2 compliance encryption audit": 8,
        "international expansion europe asia": 11,
    }
    for query, expected_index in cases.items():
        ranked = index.top_k(query, 3)
        assert ranked[0] == expected_index, (query, ranked)


def test_bm25_empty_corpus_is_safe() -> None:
    index = Bm25Index([])
    assert index.top_k("anything", 5) == []


def test_select_sources_first_turn_ranks_by_question_and_objective() -> None:
    sources = _corpus_sources()
    selected = select_sources(
        sources,
        question="Tell me about their latest funding round",
        objective="Assess financial health before the call",
        top_k=6,
    )
    assert len(selected) == 6
    # Indices are 1-based and contiguous for the prompt.
    assert [s.index for s in selected] == [1, 2, 3, 4, 5, 6]
    # The funding doc (corpus index 0) should be the top pick.
    assert selected[0].url == "https://example.com/0"


def test_select_sources_follow_up_carries_prior_citations() -> None:
    sources = _corpus_sources()
    prior = {"https://example.com/17"}  # the "regulation/legal" doc
    selected = select_sources(
        sources,
        question="What new products did they launch?",
        objective="",
        prior_citation_urls=prior,
        top_k=4,
    )
    urls = {s.url for s in selected}
    # Carried forward even though it's irrelevant to the new question...
    assert "https://example.com/17" in urls
    # ...alongside the fresh product hit.
    assert "https://example.com/2" in urls


def test_select_sources_empty_returns_empty() -> None:
    assert select_sources([], question="q", objective="o") == []


def _report() -> ReportOut:
    return ReportOut(
        id="r1",
        session_id="s1",
        company_overview="Acme builds developer tools.",
        products_and_services=["CLI", "SaaS dashboard"],
        target_customers=["Engineering teams"],
        business_signals=[
            BusinessSignalOut(
                category="funding",
                summary="Raised $20M Series B",
                evidence_urls=["https://example.com/0"],
                confidence=0.8,
            )
        ],
        risks_and_challenges=["Crowded market"],
        suggested_discovery_questions=[
            DiscoveryQuestion(question="What's your stack?", rationale="Qualify fit")
        ],
        suggested_outreach_strategy="Lead with the funding signal.",
        unknowns=["Pricing not public"],
        sources=[ReportSource(url="https://example.com/0", title="Funding", used_in=["signals"])],
        created_at=datetime.now(UTC),
    )


def test_report_to_markdown_includes_all_populated_sections() -> None:
    md = report_to_markdown(_report())
    assert "### Company Overview" in md
    assert "Acme builds developer tools." in md
    assert "- CLI" in md
    assert "[funding] Raised $20M Series B" in md
    assert "### Outreach Strategy" in md


def test_build_messages_orders_system_history_then_question() -> None:
    selected = [
        SelectedSource(index=1, url="u", title="t", snippet="snip", content="body")
    ]
    messages = build_messages(
        report_md="REPORT_MD",
        selected=selected,
        history=[],
        question="What's the latest?",
    )
    assert messages[0]["role"] == "system"
    assert "REPORT_MD" in messages[0]["content"]
    assert "[1] t — u" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "What's the latest?"}


def test_parse_citations_maps_indices_and_suppresses_out_of_range() -> None:
    selected = [
        SelectedSource(index=1, url="https://a", title="A", snippet="sa", content=""),
        SelectedSource(index=2, url="https://b", title="B", snippet="sb", content=""),
    ]
    text = "Growth is strong [1] and hiring is up [2], but [9] is unknown."
    citations = parse_citations(text, selected)
    assert [c.source_index for c in citations] == [1, 2]  # [9] dropped
    assert citations[0].url == "https://a"
    assert citations[1].title == "B"
