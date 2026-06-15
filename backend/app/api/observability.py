"""Observability routes: metrics scrape + client-side error sink (PLAN §2.3).

``GET /api/metrics`` exposes the in-process counter snapshot as JSON ("scrape
with curl/cron"); ``POST /api/client-errors`` records browser-side errors
server-side and replies 204 — it never echoes details back, so it can't be used
to probe internal state.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.logging_config import get_logger
from app.metrics import metrics
from app.models.health import ClientErrorReport

router = APIRouter(tags=["observability"])

log = get_logger("api.client_errors")


@router.get("/metrics")
async def get_metrics() -> dict[str, dict[str, int]]:
    """Return process-local counters (requests, runs, chat messages, tokens)."""
    return metrics.snapshot()


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
async def report_client_error(payload: ClientErrorReport) -> Response:
    """Log a browser-side error; reply 204 with no body (no detail leakage)."""
    log.warning(
        "client_error",
        message=payload.message,
        url=payload.url,
        client_request_id=payload.request_id,
        user_agent=payload.user_agent,
        stack=(payload.stack or "")[:2000],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
