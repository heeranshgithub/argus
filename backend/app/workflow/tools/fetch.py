"""HTTP page fetcher — bounded, timeout-guarded, readability-cleaned.

The researcher node pulls candidate pages through a :class:`Fetcher`. The real
implementation uses ``httpx`` with a short timeout, a byte cap (so a giant page
can't exhaust memory), and redirect-following. Failures raise :class:`FetchError`
so the caller can log-and-skip a single bad URL without failing the node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict, runtime_checkable

import httpx

from app.logging_config import get_logger
from app.workflow.tools.text import clean_html

if TYPE_CHECKING:
    from app.config import Settings

log = get_logger("workflow.fetch")

# A browser-ish UA; some sites 403 the default httpx agent.
_USER_AGENT = (
    "Mozilla/5.0 (compatible; ArgusResearchBot/1.0; +https://github.com/argus)"
)


class FetchedPage(TypedDict):
    """The result of fetching and cleaning a single URL."""

    url: str
    status: int
    content_type: str
    html: str
    text: str  # readability-cleaned plain text


class FetchError(Exception):
    """Raised when a page cannot be fetched (network, timeout, HTTP error)."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to fetch {url!r}: {reason}")


@runtime_checkable
class Fetcher(Protocol):
    """Fetches and cleans a web page."""

    async def fetch(self, url: str) -> FetchedPage: ...


class HttpxFetcher:
    """Real fetcher backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        max_bytes: int = 1_000_000,
        max_chars: int = 8000,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._max_chars = max_chars

    @classmethod
    def from_settings(cls, settings: Settings) -> HttpxFetcher:
        """Build a fetcher from application settings."""
        return cls(
            timeout_seconds=settings.fetch_timeout_seconds,
            max_bytes=settings.fetch_max_bytes,
        )

    async def fetch(self, url: str) -> FetchedPage:
        """Fetch ``url`` and return cleaned text; raise :class:`FetchError`."""
        headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=True, headers=headers
            ) as client, client.stream("GET", url) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                body = await self._read_capped(resp)
        except httpx.HTTPStatusError as exc:
            raise FetchError(url, f"HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise FetchError(url, type(exc).__name__) from exc

        is_html = "html" in content_type or "xml" in content_type or not content_type
        html = body.decode("utf-8", errors="replace") if is_html else ""
        text = clean_html(html, max_chars=self._max_chars) if html else ""
        return FetchedPage(
            url=str(resp.url),
            status=resp.status_code,
            content_type=content_type,
            html=html,
            text=text,
        )

    async def _read_capped(self, resp: httpx.Response) -> bytes:
        """Read response bytes up to the configured cap."""
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total >= self._max_bytes:
                break
        return b"".join(chunks)[: self._max_bytes]
