"""Async MongoDB client lifecycle and FastAPI dependency."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from starlette.requests import Request

from app.config import Settings
from app.logging_config import get_logger

log = get_logger("db.mongo")

# Timeout (ms) for the connectivity ping so a down Mongo never hangs a request.
PING_TIMEOUT_MS = 1500


class MongoManager:
    """Owns the Motor client and exposes the configured database handle."""

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    def connect(self, settings: Settings) -> None:
        """Create the Motor client (lazy TCP — no I/O until first use)."""
        self._client = AsyncIOMotorClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=PING_TIMEOUT_MS,
            uuidRepresentation="standard",
        )
        self._db = self._client[settings.mongo_db_name]
        log.info("mongo_client_created", db=settings.mongo_db_name)

    async def disconnect(self) -> None:
        """Close the Motor client."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            log.info("mongo_client_closed")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Return the database handle, raising if not yet connected."""
        if self._db is None:
            raise RuntimeError("Mongo is not connected; call connect() first.")
        return self._db

    async def ping(self) -> bool:
        """Return True if the server answers an `ismaster` ping in time."""
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
        except Exception as exc:
            log.warning("mongo_ping_failed", error=str(exc))
            return False
        return True


# Single process-wide manager; the client itself is async-safe.
mongo_manager = MongoManager()


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """FastAPI dependency yielding the active database handle.

    Reads the manager off `app.state` so tests can swap in a mock.
    """
    manager: MongoManager = request.app.state.mongo
    return manager.db
