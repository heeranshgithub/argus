"""Web search abstraction: ``SearchClient`` protocol + Tavily/DDG/fake impls.

Tavily is the primary provider (clean JSON, no scraping). DuckDuckGo is a
best-effort, key-free fallback. The concrete client is chosen at startup by
:func:`build_search_client` based on which credentials/provider are configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict, runtime_checkable

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.config import Settings

log = get_logger("workflow.search")


class SearchHit(TypedDict):
    """A single search result."""

    url: str
    title: str
    snippet: str


@runtime_checkable
class SearchClient(Protocol):
    """Runs a web search and returns the top ``k`` hits."""

    async def search(self, query: str, k: int = 5) -> list[SearchHit]: ...


# Retry transient search failures twice (3 attempts total) with backoff.
_search_retry = retry(
    retry=retry_if_exception_type((httpx.HTTPError, ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)


class TavilyClient:
    """Search via the Tavily API (``AsyncTavilyClient``)."""

    def __init__(self, api_key: str) -> None:
        # Imported lazily so the dependency is only required when actually used.
        from tavily import AsyncTavilyClient

        self._client = AsyncTavilyClient(api_key=api_key)

    @_search_retry
    async def search(self, query: str, k: int = 5) -> list[SearchHit]:
        resp = await self._client.search(query, max_results=k)
        hits: list[SearchHit] = []
        for item in resp.get("results", []):
            url = item.get("url")
            if not url:
                continue
            hits.append(
                SearchHit(
                    url=url,
                    title=item.get("title") or url,
                    snippet=item.get("content") or "",
                )
            )
        return hits


class DuckDuckGoClient:
    """Key-free fallback search by scraping DuckDuckGo's HTML endpoint."""

    _ENDPOINT = "https://html.duckduckgo.com/html/"

    def __init__(self, *, timeout_seconds: float = 8.0) -> None:
        self._timeout = timeout_seconds

    @_search_retry
    async def search(self, query: str, k: int = 5) -> list[SearchHit]:
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0 (compatible; ArgusResearchBot/1.0)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.post(self._ENDPOINT, data={"q": query})
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        hits: list[SearchHit] = []
        for result in soup.select(".result")[:k]:
            link = result.select_one(".result__a")
            if link is None or not link.get("href"):
                continue
            snippet_el = result.select_one(".result__snippet")
            hits.append(
                SearchHit(
                    url=str(link["href"]),
                    title=link.get_text(strip=True),
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                )
            )
        return hits


def build_search_client(settings: Settings) -> SearchClient:
    """Pick a search client from settings (Tavily if keyed, else DuckDuckGo)."""
    if settings.search_provider == "tavily" and settings.tavily_api_key:
        log.info("search_provider_selected", provider="tavily")
        return TavilyClient(settings.tavily_api_key)
    log.info("search_provider_selected", provider="ddg")
    return DuckDuckGoClient(timeout_seconds=settings.fetch_timeout_seconds)
