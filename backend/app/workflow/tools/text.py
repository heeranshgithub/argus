"""HTML → clean text helpers (readability-lite, no heavy dependencies).

We strip script/style/nav/footer chrome, collapse whitespace, and truncate to a
character cap so a single bloated page can't blow up the token budget downstream.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Tags whose text content is never useful research material.
_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
)

_WHITESPACE_RE = re.compile(r"[ \t\xa0]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")

DEFAULT_MAX_CHARS = 8000


def clean_html(html: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Extract readable text from an HTML document.

    Removes obvious chrome/boilerplate tags, normalizes whitespace, and truncates
    to ``max_chars`` (on a word boundary where possible). Returns ``""`` for empty
    or unparseable input rather than raising.
    """
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(list(_NOISE_TAGS)):
        tag.decompose()

    text = soup.get_text(separator="\n")
    return _normalize(text, max_chars=max_chars)


def _normalize(text: str, *, max_chars: int) -> str:
    """Collapse whitespace and truncate to ``max_chars``."""
    lines = (_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    collapsed = "\n".join(line for line in lines if line)
    collapsed = _BLANKLINES_RE.sub("\n\n", collapsed).strip()
    return truncate(collapsed, max_chars)


def truncate(text: str, max_chars: int) -> str:
    """Truncate ``text`` to ``max_chars``, preferring the last whitespace break."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars * 0.8:  # only trim to a word boundary if it's close
        cut = cut[:last_space]
    return cut.rstrip() + "…"
