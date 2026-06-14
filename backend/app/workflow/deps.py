"""``WorkflowDeps`` — the external capabilities every node needs, bundled.

Nodes are built as closures over a single ``WorkflowDeps`` so they depend on
*protocols* (LLM, search, fetch), never on concrete clients. Production builds
real clients from settings; tests pass fakes. Keeping this out of ``GraphState``
matters: the state is checkpointed to Mongo, these handles must never be.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.workflow.tools.fetch import Fetcher, HttpxFetcher
from app.workflow.tools.llm import LLMClient, OpenRouterClient
from app.workflow.tools.search import SearchClient, build_search_client

if TYPE_CHECKING:
    from app.config import Settings


@dataclass
class WorkflowDeps:
    """The capabilities injected into the graph's nodes."""

    llm: LLMClient
    search: SearchClient
    fetcher: Fetcher
    settings: Settings

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkflowDeps:
        """Build production dependencies (real network clients) from settings."""
        return cls(
            llm=OpenRouterClient(settings),
            search=build_search_client(settings),
            fetcher=HttpxFetcher.from_settings(settings),
            settings=settings,
        )
