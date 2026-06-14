"""FastAPI application factory and lifespan wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health as health_routes
from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.mongo import MongoManager, mongo_manager
from app.logging_config import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    configure_logging,
    get_logger,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect Mongo on startup, ping it, and disconnect on shutdown."""
    settings: Settings = app.state.settings
    manager: MongoManager = app.state.mongo
    log = get_logger("lifespan")

    manager.connect(settings)
    if await manager.ping():
        log.info("mongo_connected", db=settings.mongo_db_name)
    else:
        log.warning("mongo_unreachable", uri=settings.mongo_uri)

    try:
        yield
    finally:
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

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    register_exception_handlers(app)

    # Health route depends on the live Mongo manager held on app.state.
    app.dependency_overrides[health_routes.get_mongo_manager] = lambda: app.state.mongo

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
