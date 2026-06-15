"""Cached OpenRouter reachability probe for the health endpoint (PLAN §2.1).

A HEAD on the API base, cached for 30s so health checks don't hammer the gateway.
Returns ``unknown`` when no key is configured (nothing to probe) and ``down`` on
any timeout/transport error.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.config import Settings

log = get_logger("api.openrouter_health")

_TTL_SECONDS = 30.0
_PROBE_TIMEOUT = 3.0
_cache: dict[str, float | str] = {"ts": 0.0, "status": "unknown"}


async def check_openrouter(settings: Settings) -> str:
    """Return ``ok`` / ``down`` / ``unknown`` for OpenRouter, cached 30s."""
    # Never make a real network call under tests.
    if settings.env == "test" or not settings.openrouter_api_key:
        return "unknown"
    now = time.monotonic()
    if now - float(_cache["ts"]) < _TTL_SECONDS and _cache["status"] != "unknown":
        return str(_cache["status"])

    status = "down"
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.head(settings.openrouter_base_url)
        # Any non-5xx (incl. 404/405 for a HEAD on the base) means reachable.
        status = "ok" if resp.status_code < 500 else "down"
    except Exception as exc:
        log.warning("openrouter_probe_failed", error=str(exc))
        status = "down"

    _cache["ts"] = now
    _cache["status"] = status
    return status
