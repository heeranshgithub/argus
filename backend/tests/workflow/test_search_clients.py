"""Search client tests with mocked Tavily SDK and DuckDuckGo HTTP (no network)."""

import httpx
import tavily

from app.workflow.tools.search import DuckDuckGoClient, TavilyClient


async def test_tavily_client_maps_results(monkeypatch) -> None:
    class _FakeTavily:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        async def search(self, query: str, max_results: int = 5):
            return {
                "results": [
                    {"url": "https://a.com", "title": "A", "content": "snippet a"},
                    {"title": "no url"},  # dropped — no url
                ]
            }

    monkeypatch.setattr(tavily, "AsyncTavilyClient", _FakeTavily)
    client = TavilyClient("sk-tavily")
    hits = await client.search("acme funding", k=5)
    assert len(hits) == 1
    assert hits[0] == {"url": "https://a.com", "title": "A", "snippet": "snippet a"}


_DDG_HTML = """
<div class="result">
  <a class="result__a" href="https://x.com/a">Result A</a>
  <div class="result__snippet">Snippet A</div>
</div>
<div class="result">
  <a class="result__a" href="https://x.com/b">Result B</a>
  <div class="result__snippet">Snippet B</div>
</div>
"""


async def test_duckduckgo_client_parses_html(monkeypatch) -> None:
    class _Resp:
        text = _DDG_HTML

        def raise_for_status(self) -> None: ...

    class _FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, data=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    client = DuckDuckGoClient()
    hits = await client.search("acme", k=5)
    assert [h["url"] for h in hits] == ["https://x.com/a", "https://x.com/b"]
    assert hits[0]["title"] == "Result A"
    assert hits[0]["snippet"] == "Snippet A"
