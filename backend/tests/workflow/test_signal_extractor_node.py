"""Signal extractor node tests — categorized, evidence-grounded signals."""

from app.workflow.nodes.signal_extractor import build_signal_extractor
from app.workflow.schemas import SignalsResult
from app.workflow.tools.llm import FakeLLMClient
from tests.workflow.conftest import base_state, invoke_node


def _state_with_sources():
    return base_state(
        raw_sources=[
            {
                "url": "https://example.com/news",
                "title": "News",
                "snippet": "Series B",
                "content": "Acme raised a $40M Series B.",
                "fetched_at": "t",
            }
        ]
    )


async def test_signal_extractor_maps_signals(deps, db) -> None:
    node = build_signal_extractor(deps)
    update, _ = await invoke_node(node, _state_with_sources(), db)

    signals = update["extracted_signals"]
    assert len(signals) == 1
    assert signals[0]["category"] == "funding"
    assert signals[0]["evidence_urls"] == ["https://example.com/news"]


async def test_signal_extractor_drops_hallucinated_evidence_urls(deps, db) -> None:
    # The model cites a URL not present in raw_sources; the node strips it.
    deps.llm = FakeLLMClient(
        {
            "SignalsResult": [
                SignalsResult(
                    signals=[
                        {
                            "category": "news",
                            "summary": "Something",
                            "evidence_urls": [
                                "https://example.com/news",  # real
                                "https://hallucinated.example/x",  # not in sources
                            ],
                            "confidence": 0.5,
                        }
                    ]
                )
            ]
        }
    )
    node = build_signal_extractor(deps)
    update, _ = await invoke_node(node, _state_with_sources(), db)

    assert update["extracted_signals"][0]["evidence_urls"] == [
        "https://example.com/news"
    ]
