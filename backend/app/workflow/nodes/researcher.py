"""``researcher`` node — gather and clean web sources for the open questions.

The only node that does no LLM work. For each not-yet-researched sub-question it
runs a web search and fetches the top results; on the first iteration it also
crawls the company site (home + common pages). Fetches run concurrently under a
bounded semaphore. Per-URL failures are logged into ``state.errors`` and fall
back to the search snippet — the node only fails if it gathered nothing at all.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps
from app.workflow.events import emit_node
from app.workflow.state import GraphState, RawSource, SubQuestion
from app.workflow.tools.fetch import FetchError
from app.workflow.tools.search import SearchHit

log = get_logger("workflow.node.researcher")

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]

# Company-site pages worth a best-effort crawl on the first research pass.
_SITE_PATHS = ("", "/about", "/products", "/pricing", "/careers", "/blog")
# How many search results per question we actually fetch full pages for.
_FETCH_TOP_N = 3


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_researcher(deps: WorkflowDeps) -> NodeFn:
    """Build the researcher node bound to ``deps``."""
    settings = deps.settings
    semaphore = asyncio.Semaphore(settings.fetch_concurrency)

    async def _fetch_source(hit: SearchHit, errors: list[dict[str, Any]]) -> RawSource:
        """Fetch a page; fall back to the search snippet on failure."""
        async with semaphore:
            try:
                page = await deps.fetcher.fetch(hit["url"])
                content = page["text"] or hit["snippet"]
            except FetchError as exc:
                errors.append(
                    {"node": "researcher", "url": hit["url"], "error": str(exc)}
                )
                content = hit["snippet"]
        return RawSource(
            url=hit["url"],
            title=hit["title"],
            snippet=hit["snippet"],
            content=content,
            fetched_at=_now_iso(),
        )

    async def _research_question(
        q: SubQuestion, errors: list[dict[str, Any]]
    ) -> list[RawSource]:
        """Search one sub-question and fetch its top results."""
        try:
            hits = await deps.search.search(
                q["question"], k=settings.search_results_per_query
            )
        except Exception as exc:  # search failed entirely for this question
            errors.append(
                {"node": "researcher", "query": q["question"], "error": str(exc)}
            )
            return []
        tasks = [_fetch_source(hit, errors) for hit in hits[:_FETCH_TOP_N]]
        return list(await asyncio.gather(*tasks))

    async def _crawl_site(website: str, errors: list[dict[str, Any]]) -> list[RawSource]:
        """Best-effort crawl of common company-site pages."""
        async def _one(path: str) -> RawSource | None:
            url = urljoin(website, path) if path else website
            async with semaphore:
                try:
                    page = await deps.fetcher.fetch(url)
                except FetchError:
                    return None  # 404s/blocks are expected; ignore quietly
            if not page["text"]:
                return None
            return RawSource(
                url=page["url"],
                title=f"{website} {path or '(home)'}".strip(),
                snippet=page["text"][:280],
                content=page["text"],
                fetched_at=_now_iso(),
            )

        results = await asyncio.gather(*[_one(p) for p in _SITE_PATHS])
        return [r for r in results if r is not None]

    async def researcher(state: GraphState) -> dict[str, Any]:
        async with emit_node("researcher") as ev:
            plan = state.get("plan") or []
            already = set(state.get("researched_question_ids") or [])
            todo = [q for q in plan if q["id"] not in already]
            iteration = state.get("research_iteration", 0)

            errors: list[dict[str, Any]] = []
            collected: list[list[RawSource]] = await asyncio.gather(
                *[_research_question(q, errors) for q in todo]
            )
            sources: list[RawSource] = [s for batch in collected for s in batch]

            # Crawl the company site once, on the first research pass.
            if iteration == 0:
                sources.extend(await _crawl_site(state["website"], errors))

            # De-duplicate within this iteration (the state reducer dedupes across).
            deduped: list[RawSource] = []
            seen: set[str] = set()
            for src in sources:
                if src["url"] in seen:
                    continue
                seen.add(src["url"])
                deduped.append(src)

            # Fail the node only when a pass yielded literally nothing usable.
            if not deduped and not (state.get("raw_sources") or []):
                raise RuntimeError(
                    "Researcher gathered no sources (all searches/fetches failed)."
                )

            ev.set_preview(
                {
                    "new_sources": len(deduped),
                    "questions_researched": len(todo),
                    "errors": len(errors),
                }
            )
            log.info(
                "researcher_done",
                iteration=iteration,
                new_sources=len(deduped),
                questions=len(todo),
                errors=len(errors),
            )
            update: dict[str, Any] = {
                "raw_sources": deduped,
                "research_iteration": iteration + 1,
                "researched_question_ids": [q["id"] for q in todo],
            }
            if errors:
                update["errors"] = errors
            return update

    return researcher
