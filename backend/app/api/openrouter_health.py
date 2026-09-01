"""Cached OpenRouter credential probe for the health endpoint (PLAN §2.1).

An authenticated ``GET {base}/key``, cached for 30s so health checks don't hammer
the gateway. Returns ``unknown`` when no key is configured (nothing to probe),
``unauthorized`` when the gateway rejects the key, and ``down`` on any timeout or
transport error.

This deliberately authenticates rather than probing reachability. An unauthorized
``HEAD`` on the API base returns a happy status code even when the configured key
is dead, so a revoked key used to surface as ``ok`` here while every workflow run
failed on a 401 — the failure stayed invisible until someone read the logs.
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
    """Return ``ok`` / ``unauthorized`` / ``down`` / ``unknown``, cached 30s.

    Never raises: the health endpoint must answer even when the gateway doesn't.
    Note the caller keeps overall ``status`` at ``ok`` regardless — this is a
    dependency report, and a bad LLM key must not make the container look
    unhealthy to the platform's health check and trigger a restart loop.
    """
    # Never make a real network call under tests.
    if settings.env == "test" or not settings.openrouter_api_key:
        return "unknown"
    now = time.monotonic()
    if now - float(_cache["ts"]) < _TTL_SECONDS and _cache["status"] != "unknown":
        return str(_cache["status"])

    status = "down"
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url.rstrip('/')}/key",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
        if resp.status_code in (401, 403):
            # The gateway is up and answering — the credential is the problem.
            status = "unauthorized"
            log.error("openrouter_key_rejected", status_code=resp.status_code)
        elif resp.status_code < 500:
            status = "ok"
        else:
            status = "down"
            log.warning("openrouter_probe_5xx", status_code=resp.status_code)
    except Exception as exc:
        log.warning("openrouter_probe_failed", error=str(exc))
        status = "down"

    _cache["ts"] = now
    _cache["status"] = status
    return status
