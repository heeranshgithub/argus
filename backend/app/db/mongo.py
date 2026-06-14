"""Async MongoDB client lifecycle and FastAPI dependency."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from starlette.requests import Request

from app.config import Settings
from app.db.collections import (
    ALL_COLLECTIONS,
    REPORTS,
    SESSIONS,
    WORKFLOW_CHECKPOINT_BLOBS,
    WORKFLOW_CHECKPOINT_WRITES,
    WORKFLOW_CHECKPOINTS,
    WORKFLOW_RUNS,
)
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
            tz_aware=True,
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


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create the indexes the app relies on. Idempotent — safe to call on every
    startup; Mongo no-ops when an index already exists."""
    await db[SESSIONS].create_index([("created_at", -1)], name="created_at_desc")
    await db[SESSIONS].create_index([("status", 1)], name="status_asc")

    # Workflow runs: list-by-session, newest-first.
    await db[WORKFLOW_RUNS].create_index([("session_id", 1)], name="session_id_asc")
    await db[WORKFLOW_RUNS].create_index([("started_at", -1)], name="started_at_desc")

    # Reports: one per session for now.
    await db[REPORTS].create_index([("session_id", 1)], name="session_id_unique", unique=True)

    # Checkpointer collections (see app.workflow.checkpointer).
    await db[WORKFLOW_CHECKPOINTS].create_index(
        [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", 1)],
        name="checkpoint_pk",
        unique=True,
    )
    await db[WORKFLOW_CHECKPOINTS].create_index(
        [("thread_id", 1), ("ts", -1)], name="thread_ts_desc"
    )
    await db[WORKFLOW_CHECKPOINT_BLOBS].create_index(
        [("thread_id", 1), ("checkpoint_ns", 1), ("channel", 1), ("version", 1)],
        name="blob_pk",
        unique=True,
    )
    await db[WORKFLOW_CHECKPOINT_WRITES].create_index(
        [
            ("thread_id", 1),
            ("checkpoint_ns", 1),
            ("checkpoint_id", 1),
            ("task_id", 1),
            ("idx", 1),
        ],
        name="write_pk",
        unique=True,
    )
    log.info("mongo_indexes_ensured", collections=len(ALL_COLLECTIONS))


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """FastAPI dependency yielding the active database handle.

    Reads the manager off `app.state` so tests can swap in a mock.
    """
    manager: MongoManager = request.app.state.mongo
    return manager.db
