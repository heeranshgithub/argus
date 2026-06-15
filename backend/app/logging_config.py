"""structlog configuration and a request-id binding middleware."""

import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import metrics

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(log_level: str = "INFO", *, pretty: bool = False) -> None:
    """Configure structlog for either pretty (dev) or JSON (prod) output."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer() if pretty else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Bind a request id + route to the log context, time the request, and count it.

    Every log emitted during the request carries ``request_id``, ``route``, and
    ``method`` (PLAN_PART_5 §2.1); on completion a ``request_completed`` event
    records ``status`` and ``latency_ms`` and the request is tallied in
    :data:`app.metrics.metrics`.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            route=request.url.path,
            method=request.method,
        )
        log = get_logger("request")
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_failed")
            metrics.incr_request(request.method, request.url.path, 500)
            structlog.contextvars.clear_contextvars()
            raise
        # Prefer the matched route template (set during routing) so metric
        # cardinality stays bounded — e.g. ``/api/sessions/{session_id}``.
        route_obj = request.scope.get("route")
        route = getattr(route_obj, "path", request.url.path)
        latency_ms = int((time.monotonic() - started) * 1000)
        metrics.incr_request(request.method, route, response.status_code)
        log.info(
            "request_completed",
            status=response.status_code,
            latency_ms=latency_ms,
        )
        structlog.contextvars.clear_contextvars()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
