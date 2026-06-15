"""Per-IP rate limiting via slowapi (PLAN_PART_5 §2.1).

A module-level :data:`limiter` singleton is shared between the route decorators
(imported at module load) and the app wiring. :func:`configure` adjusts it from
settings at app-creation time — disabling enforcement under ``env=test`` and
pulling the per-route limits from config — and :func:`rate_limit_handler` renders
``RateLimitExceeded`` into the app's standard error contract with ``Retry-After``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.errors import error_json

if TYPE_CHECKING:
    from app.config import Settings

# Defaults mirror config; configure() overrides them from settings.
_DEFAULT = "120/minute"
_limits = {
    "default": _DEFAULT,
    "create_session": "30/minute",
    "run": "5/minute",
    "chat": "30/minute",
}

# headers_enabled stays off: slowapi's header injection requires every limited
# route to declare a ``response: Response`` param. We set ``Retry-After``
# ourselves in :func:`rate_limit_handler` instead.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_DEFAULT],
)


def configure(settings: Settings) -> None:
    """Enable/disable enforcement and sync per-route limits from settings."""
    limiter.enabled = settings.env != "test"
    _limits["default"] = settings.rate_limit_default
    _limits["create_session"] = settings.rate_limit_create_session
    _limits["run"] = settings.rate_limit_run
    _limits["chat"] = settings.rate_limit_chat


# Callables so decorators (evaluated at import) read the configured value at
# request time rather than capturing the pre-configure default.
def create_session_limit() -> str:
    return _limits["create_session"]


def run_limit() -> str:
    return _limits["run"]


def chat_limit() -> str:
    return _limits["chat"]


def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render a 429 in the standard error contract with a ``Retry-After`` header."""
    detail = getattr(exc, "detail", "rate limit exceeded")
    response = error_json(
        429,
        code="rate_limited",
        message="Too many requests; please slow down and retry shortly.",
        details={"limit": str(detail)},
    )
    response.headers["Retry-After"] = "60"
    return response
