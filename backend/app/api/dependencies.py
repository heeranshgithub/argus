"""Shared FastAPI dependencies for the workflow routes.

The workflow engine (real LLM/search clients) is expensive to build and needs an
API key, so we construct it lazily on first use and cache it on ``app.state``.
Tests override :func:`get_workflow_deps` with fakes. A construction failure
(e.g., missing ``OPENROUTER_API_KEY``) surfaces as :class:`WorkflowUnavailable`
(HTTP 503) only when a workflow route is actually hit — health/sessions stay up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

from app.exceptions import WorkflowUnavailable
from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps

if TYPE_CHECKING:
    from app.config import Settings

log = get_logger("api.dependencies")


def get_workflow_deps(request: Request) -> WorkflowDeps:
    """Return (and cache) the application's :class:`WorkflowDeps`."""
    cached = getattr(request.app.state, "workflow_deps", None)
    if cached is not None:
        return cached
    settings: Settings = request.app.state.settings
    try:
        deps = WorkflowDeps.from_settings(settings)
    except Exception as exc:  # missing key / bad config
        log.error("workflow_deps_unavailable", error=str(exc))
        raise WorkflowUnavailable(str(exc)) from exc
    request.app.state.workflow_deps = deps
    return deps
