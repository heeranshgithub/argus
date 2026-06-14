"""Shared rendering helpers — turn state collections into LLM-ready text blocks.

Kept tiny and deterministic so node prompts assemble the same way every run and
so tests can assert on rendered content without mocking an LLM.
"""

from __future__ import annotations

from app.workflow.state import AnalysisBlock, BusinessSignal, RawSource
from app.workflow.tools.text import truncate

# Per-source content budget inside a prompt block, so many sources still fit.
_SOURCE_CONTENT_CHARS = 1500


def render_sources(sources: list[RawSource], *, content_chars: int = _SOURCE_CONTENT_CHARS) -> str:
    """Render sources as a numbered block with URL, title, and capped content."""
    if not sources:
        return "(no sources gathered)"
    parts: list[str] = []
    for i, src in enumerate(sources, start=1):
        body = src.get("content") or src.get("snippet") or ""
        parts.append(
            f"[{i}] {src.get('title') or src['url']}\n"
            f"URL: {src['url']}\n"
            f"{truncate(body, content_chars)}"
        )
    return "\n\n".join(parts)


def render_signals(signals: list[BusinessSignal]) -> str:
    """Render extracted signals as a compact bulleted block."""
    if not signals:
        return "(no signals extracted)"
    lines: list[str] = []
    for sig in signals:
        urls = ", ".join(sig.get("evidence_urls", []))
        lines.append(
            f"- [{sig['category']}] {sig['summary']} "
            f"(confidence {sig.get('confidence', 0):.2f}; evidence: {urls or 'none'})"
        )
    return "\n".join(lines)


def render_analysis(analysis: AnalysisBlock | None) -> str:
    """Render the analysis block as labeled sections."""
    if not analysis:
        return "(no analysis yet)"

    def _list(items: list[str]) -> str:
        return "; ".join(items) if items else "(none)"

    return (
        f"Overview: {analysis.get('overview', '')}\n"
        f"Products/Services: {_list(analysis.get('products_services', []))}\n"
        f"Target customers: {_list(analysis.get('target_customers', []))}\n"
        f"Risks: {_list(analysis.get('risks', []))}\n"
        f"Unknowns: {_list(analysis.get('unknowns', []))}"
    )
