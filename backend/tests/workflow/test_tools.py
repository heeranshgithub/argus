"""Unit tests for the tool layer: text cleanup, the fake LLM, and fetch fallback."""

import httpx
import pytest

from app.config import Settings
from app.workflow.schemas import PlanResult
from app.workflow.tools.fetch import FetchError, HttpxFetcher
from app.workflow.tools.llm import FakeLLMClient, LLMError, OpenRouterClient
from app.workflow.tools.search import build_search_client
from app.workflow.tools.text import clean_html, truncate


def test_clean_html_strips_chrome_and_collapses_whitespace() -> None:
    html = """
    <html><head><style>.x{}</style></head>
    <body><nav>menu</nav><script>1</script>
    <h1>Title</h1>
    <p>Hello    world</p>
    <footer>foot</footer></body></html>
    """
    text = clean_html(html)
    assert "Title" in text
    assert "Hello world" in text  # whitespace collapsed
    assert "menu" not in text and "foot" not in text  # chrome removed


def test_clean_html_truncates() -> None:
    long = "<p>" + ("word " * 5000) + "</p>"
    out = clean_html(long, max_chars=100)
    assert len(out) <= 101  # plus the ellipsis


def test_truncate_prefers_word_boundary() -> None:
    assert truncate("hello world foobar", 12).endswith("…")
    assert truncate("short", 100) == "short"


def test_clean_html_handles_empty() -> None:
    assert clean_html("") == ""
    assert clean_html("   ") == ""


async def test_fake_llm_scripts_by_response_model() -> None:
    plan = PlanResult(questions=[{"question": "q", "rationale": "r"}])
    llm = FakeLLMClient({"PlanResult": [plan]})
    result = await llm.complete("s", "u", response_model=PlanResult)
    assert isinstance(result, PlanResult)
    assert result.questions[0].question == "q"


async def test_fake_llm_validates_dict_payloads() -> None:
    llm = FakeLLMClient({"PlanResult": [{"questions": [{"question": "q", "rationale": "r"}]}]})
    result = await llm.complete("s", "u", response_model=PlanResult)
    assert isinstance(result, PlanResult)


async def test_fake_llm_raises_without_script() -> None:
    llm = FakeLLMClient({})
    with pytest.raises(LLMError):
        await llm.complete("s", "u", response_model=PlanResult)


def test_openrouter_client_requires_api_key() -> None:
    with pytest.raises(LLMError):
        OpenRouterClient(Settings(env="test", openrouter_api_key=None))


def test_build_search_client_falls_back_to_ddg_without_key() -> None:
    from app.workflow.tools.search import DuckDuckGoClient

    settings = Settings(env="test", search_provider="tavily", tavily_api_key=None)
    client = build_search_client(settings)
    assert isinstance(client, DuckDuckGoClient)


class _FakeStreamResp:
    def __init__(self, *, body: bytes, content_type: str, url: str) -> None:
        self._body = body
        self.headers = {"content-type": content_type}
        self.url = url
        self.status_code = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self) -> None: ...

    async def aiter_bytes(self):
        # Yield in small chunks to exercise the byte-cap loop.
        for i in range(0, len(self._body), 4):
            yield self._body[i : i + 4]


class _FakeStreamClient:
    def __init__(self, resp: _FakeStreamResp) -> None:
        self._resp = resp

    def __call__(self, *a, **k):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url):
        return self._resp


async def test_httpx_fetcher_success_cleans_html(monkeypatch) -> None:
    resp = _FakeStreamResp(
        body=b"<html><body><nav>nav</nav><p>Acme sells things</p></body></html>",
        content_type="text/html; charset=utf-8",
        url="https://example.com/final",
    )
    monkeypatch.setattr(httpx, "AsyncClient", _FakeStreamClient(resp))
    fetcher = HttpxFetcher(timeout_seconds=1, max_bytes=10_000, max_chars=500)

    page = await fetcher.fetch("https://example.com")
    assert page["status"] == 200
    assert page["url"] == "https://example.com/final"  # redirect-resolved url
    assert "Acme sells things" in page["text"]
    assert "nav" not in page["text"]  # chrome stripped


async def test_httpx_fetcher_skips_non_html(monkeypatch) -> None:
    resp = _FakeStreamResp(
        body=b"\x89PNG binary", content_type="image/png", url="https://example.com/x.png"
    )
    monkeypatch.setattr(httpx, "AsyncClient", _FakeStreamClient(resp))
    fetcher = HttpxFetcher(timeout_seconds=1, max_bytes=10_000)

    page = await fetcher.fetch("https://example.com/x.png")
    assert page["text"] == ""  # non-HTML yields no cleaned text


async def test_httpx_fetcher_wraps_errors(monkeypatch) -> None:
    fetcher = HttpxFetcher(timeout_seconds=1, max_bytes=1000)

    class _BoomClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        def stream(self, *a, **k):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _BoomClient)
    with pytest.raises(FetchError):
        await fetcher.fetch("https://example.com")
