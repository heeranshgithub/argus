"""Assemble the grounded chat prompt (PLAN_PART_5 §1.3).

Three things ground every turn: a fixed system preamble, the structured report
serialized as compact markdown, and a relevance-ranked pack of raw sources, each
tagged with an explicit ``[i]`` index so the model can cite it. History (a sliding
window of recent turns) is appended as real chat messages. After streaming, the
text is post-processed to map each ``[i]`` back to a source URL for the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.chat import ChatMessageOut, ChatRole, Citation
from app.models.report import ReportOut
from app.retrieval.bm25 import Bm25Index

SYSTEM_PREAMBLE = (
    "You are Argus, a sales research copilot. Answer the user's question about the "
    "company using ONLY the provided report context and sources. If the answer is "
    "not supported by them, say you don't know rather than guessing. Be concise and "
    "practical for a salesperson preparing for a meeting. Cite sources inline by "
    "their bracketed index, e.g. [1] or [2][3], placing the citation right after the "
    "claim it supports. Only cite indices that appear in the Sources list."
)

# How much of a source's cleaned body to inline into the prompt.
_SOURCE_BODY_CHARS = 1500
# How much of each source goes into the BM25 match field.
_MATCH_BODY_CHARS = 1500


@dataclass
class SelectedSource:
    """A source chosen for the pack, carrying its 1-based prompt index."""

    index: int
    url: str
    title: str
    snippet: str
    content: str


def report_to_markdown(report: ReportOut) -> str:
    """Serialize a report to compact markdown for the chat context (~1-2k tokens)."""
    lines: list[str] = []

    def bullets(heading: str, items: list[str]) -> None:
        if not items:
            return
        lines.append(f"### {heading}")
        lines.extend(f"- {item}" for item in items)

    lines.append("### Company Overview")
    lines.append(report.company_overview or "(none)")
    bullets("Products & Services", report.products_and_services)
    bullets("Target Customers", report.target_customers)
    if report.business_signals:
        lines.append("### Business Signals")
        for sig in report.business_signals:
            lines.append(
                f"- [{sig.category}] {sig.summary} "
                f"(confidence {sig.confidence:.0%})"
            )
    bullets("Risks & Challenges", report.risks_and_challenges)
    if report.suggested_discovery_questions:
        lines.append("### Suggested Discovery Questions")
        lines.extend(
            f"- {q.question} — {q.rationale}"
            for q in report.suggested_discovery_questions
        )
    if report.suggested_outreach_strategy:
        lines.append("### Outreach Strategy")
        lines.append(report.suggested_outreach_strategy)
    bullets("Unknowns", report.unknowns)
    return "\n".join(lines)


def _match_text(source: dict[str, Any]) -> str:
    """The text a source is BM25-ranked on: title + snippet + body excerpt."""
    return " ".join(
        [
            source.get("title", ""),
            source.get("snippet", ""),
            (source.get("content", "") or "")[:_MATCH_BODY_CHARS],
        ]
    )


def select_sources(
    sources: list[dict[str, Any]],
    *,
    question: str,
    objective: str,
    prior_citation_urls: set[str] | None = None,
    top_k: int = 6,
) -> list[SelectedSource]:
    """Pick the most relevant sources for this turn (PLAN §1.3.3).

    First turn (no prior citations): rank all sources by BM25 over
    ``question + objective`` and take the top ``top_k``. Follow-up turns: carry
    forward sources cited in recent assistant turns, then top up with fresh BM25
    hits for the new question, deduped by URL and capped at ``top_k``.
    """
    if not sources:
        return []
    prior = prior_citation_urls or set()
    index = Bm25Index([_match_text(s) for s in sources])

    chosen: list[int] = []
    seen_urls: set[str] = set()

    def take(i: int) -> None:
        url = sources[i].get("url", "")
        if url in seen_urls:
            return
        seen_urls.add(url)
        chosen.append(i)

    if prior:
        # Carry forward previously-cited sources first (stable context).
        for i, src in enumerate(sources):
            if src.get("url", "") in prior:
                take(i)
        # Then top up with fresh hits for the new question.
        for i in index.top_k(question, top_k):
            if len(chosen) >= top_k:
                break
            take(i)
    else:
        query = f"{question} {objective}".strip()
        for i in index.top_k(query, top_k):
            take(i)

    return [
        SelectedSource(
            index=rank + 1,
            url=sources[i].get("url", ""),
            title=sources[i].get("title", "") or sources[i].get("url", ""),
            snippet=sources[i].get("snippet", ""),
            content=sources[i].get("content", "") or "",
        )
        for rank, i in enumerate(chosen[:top_k])
    ]


def _render_source_pack(selected: list[SelectedSource]) -> str:
    if not selected:
        return "(no sources available)"
    blocks: list[str] = []
    for src in selected:
        body = (src.content or src.snippet or "").strip()[:_SOURCE_BODY_CHARS]
        blocks.append(f"[{src.index}] {src.title} — {src.url}\n{body}")
    return "\n\n".join(blocks)


def build_messages(
    *,
    report_md: str,
    selected: list[SelectedSource],
    history: list[ChatMessageOut],
    question: str,
) -> list[dict[str, str]]:
    """Build the OpenAI-style messages list for a chat turn."""
    system = (
        f"{SYSTEM_PREAMBLE}\n\n"
        f"# Report context\n{report_md}\n\n"
        f"# Sources\n{_render_source_pack(selected)}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for msg in history:
        if msg.role is ChatRole.SYSTEM:
            continue
        messages.append({"role": msg.role.value, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def parse_citations(text: str, selected: list[SelectedSource]) -> list[Citation]:
    """Map ``[i]`` markers in ``text`` back to cited sources (PLAN §9, §1.3).

    Only indices present in the source pack become citations — out-of-range
    markers are silently dropped so the UI never renders a broken chip. Returned
    in ascending index order, de-duplicated.
    """
    import re

    by_index = {s.index: s for s in selected}
    found: list[int] = []
    seen: set[int] = set()
    for match in re.findall(r"\[(\d{1,3})\]", text):
        idx = int(match)
        if idx in by_index and idx not in seen:
            seen.add(idx)
            found.append(idx)
    found.sort()
    return [
        Citation(
            source_index=idx,
            url=by_index[idx].url,
            title=by_index[idx].title,
            snippet=(by_index[idx].snippet or by_index[idx].content[:200]),
        )
        for idx in found
    ]
