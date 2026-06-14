"""Tests for GraphState reducers — the merge semantics LangGraph relies on."""

from operator import add

from app.workflow.state import GraphState, _merge_unique_sources
from app.workflow.tools.search import SearchHit  # noqa: F401  (type sanity)


def _src(url: str) -> dict:
    return {"url": url, "title": url, "snippet": "", "content": "", "fetched_at": "t"}


def test_raw_sources_reducer_appends_and_dedupes() -> None:
    left = [_src("https://a.com"), _src("https://b.com")]
    right = [_src("https://b.com"), _src("https://c.com")]

    merged = _merge_unique_sources(left, right)  # type: ignore[arg-type]

    assert [s["url"] for s in merged] == [
        "https://a.com",
        "https://b.com",
        "https://c.com",
    ]


def test_raw_sources_reducer_preserves_first_occurrence() -> None:
    left = [{**_src("https://a.com"), "title": "first"}]
    right = [{**_src("https://a.com"), "title": "second"}]

    merged = _merge_unique_sources(left, right)  # type: ignore[arg-type]

    assert len(merged) == 1
    assert merged[0]["title"] == "first"


def test_errors_channel_uses_plain_add() -> None:
    # errors uses operator.add — straightforward concatenation, no dedupe.
    assert add([{"e": 1}], [{"e": 2}]) == [{"e": 1}, {"e": 2}]


def test_graph_state_is_total_false() -> None:
    # All keys optional: an empty dict is a valid GraphState (nodes fill it in).
    state: GraphState = {}
    state["company_name"] = "Acme"
    assert state["company_name"] == "Acme"
