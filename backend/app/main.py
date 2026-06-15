"""FastAPI application factory and lifespan wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.api import health as health_routes
from app.api.errors import register_exception_handlers
from app.api.rate_limit import configure as configure_rate_limit
from app.api.rate_limit import limiter, rate_limit_handler
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.mongo import MongoManager, ensure_indexes, mongo_manager
from app.logging_config import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    configure_logging,
    get_logger,
)
from app.repositories import session_repo
from app.services.chat_service import stream_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect Mongo on startup; drain + mark interrupted on shutdown."""
    settings: Settings = app.state.settings
    manager: MongoManager = app.state.mongo
    log = get_logger("lifespan")

    manager.connect(settings)
    if await manager.ping():
        log.info("mongo_connected", db=settings.mongo_db_name)
        try:
            await ensure_indexes(manager.db)
        except Exception as exc:  # never block startup on indexing
            log.warning("mongo_index_creation_failed", error=str(exc))
    else:
        log.warning("mongo_unreachable", uri=settings.mongo_uri)

    try:
        yield
    finally:
        # Graceful shutdown (PLAN_PART_5 §2.1): cancel in-flight chat generation,
        # then flip any still-running sessions to ``interrupted`` so they remain
        # resumable from their last checkpoint.
        await stream_manager.shutdown()
        try:
            if await manager.ping():
                count = await session_repo.mark_running_interrupted(manager.db)
                if count:
                    log.info("sessions_marked_interrupted", count=count)
        except Exception as exc:
            log.warning("graceful_shutdown_failed", error=str(exc))
        await manager.disconnect()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, pretty=settings.env == "dev")

    app = FastAPI(
        title="Argus API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.mongo = mongo_manager

    # Rate limiting (slowapi): the limiter singleton is shared with the route
    # decorators; configure() disables it under env=test and syncs limits.
    configure_rate_limit(settings)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # Middleware added inner-to-outer: RequestID is added last so it sits
    # outermost — every log (incl. a 429) carries a request id and every
    # response gets the X-Request-ID header.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)

    # Health route depends on the live Mongo manager held on app.state.
    app.dependency_overrides[health_routes.get_mongo_manager] = lambda: app.state.mongo

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
