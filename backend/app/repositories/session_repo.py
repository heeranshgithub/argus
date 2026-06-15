"""Async CRUD for the ``sessions`` collection.

Functions take the ``AsyncIOMotorDatabase`` explicitly so they stay easy to test
against an in-memory Mongo. Documents are stored snake_case; conversion to the
camelCase wire model happens via ``to_session_out``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.db.collections import SESSIONS
from app.exceptions import InvalidObjectId
from app.models.mongo_base import to_session_out
from app.models.session import SessionCreate, SessionOut, SessionStatus

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


def _utcnow_ms() -> datetime:
    """Current UTC time truncated to millisecond precision.

    BSON datetimes only keep milliseconds, so truncating here means the value we
    return from a write matches exactly what a later read yields.
    """
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _to_object_id(session_id: str) -> ObjectId:
    """Parse a wire id into an ``ObjectId`` or raise :class:`InvalidObjectId`."""
    try:
        return ObjectId(session_id)
    except (InvalidId, TypeError) as exc:
        raise InvalidObjectId(session_id) from exc


async def create(db: AsyncIOMotorDatabase, data: SessionCreate) -> SessionOut:
    """Insert a new session and return it."""
    now = _utcnow_ms()
    doc = {
        "company_name": data.company_name,
        "website": str(data.website),
        "objective": data.objective,
        "status": SessionStatus.CREATED.value,
        "created_at": now,
        "updated_at": now,
    }
    result = await db[SESSIONS].insert_one(doc)
    doc["_id"] = result.inserted_id
    return to_session_out(doc)


async def list_sessions(
    db: AsyncIOMotorDatabase, *, limit: int, skip: int
) -> list[SessionOut]:
    """Return sessions newest-first, paginated by ``skip``/``limit``."""
    # Tiebreak on _id (monotonic with insertion) so same-millisecond
    # created_at values still return in a stable newest-first order.
    cursor = (
        db[SESSIONS]
        .find()
        .sort([("created_at", -1), ("_id", -1)])
        .skip(skip)
        .limit(limit)
    )
    return [to_session_out(doc) async for doc in cursor]


async def count(db: AsyncIOMotorDatabase) -> int:
    """Total number of sessions."""
    return await db[SESSIONS].count_documents({})


async def get(db: AsyncIOMotorDatabase, session_id: str) -> SessionOut | None:
    """Fetch one session by id, or ``None`` if it does not exist."""
    oid = _to_object_id(session_id)
    doc = await db[SESSIONS].find_one({"_id": oid})
    return to_session_out(doc) if doc is not None else None


async def update_status(
    db: AsyncIOMotorDatabase, session_id: str, status: SessionStatus
) -> SessionOut | None:
    """Update a session's status, returning the updated doc or ``None``."""
    oid = _to_object_id(session_id)
    doc = await db[SESSIONS].find_one_and_update(
        {"_id": oid},
        {"$set": {"status": status.value, "updated_at": _utcnow_ms()}},
        return_document=ReturnDocument.AFTER,
    )
    return to_session_out(doc) if doc is not None else None


async def mark_running_interrupted(db: AsyncIOMotorDatabase) -> int:
    """Flip every ``running`` session to ``interrupted`` (graceful shutdown).

    Returns the number of sessions updated. Used by the FastAPI lifespan on
    SIGTERM so in-flight runs land in a resumable terminal state (PLAN §2.1).
    """
    result = await db[SESSIONS].update_many(
        {"status": SessionStatus.RUNNING.value},
        {
            "$set": {
                "status": SessionStatus.INTERRUPTED.value,
                "updated_at": _utcnow_ms(),
            }
        },
    )
    return int(result.modified_count)


async def get_chat_suggestions(
    db: AsyncIOMotorDatabase, session_id: str
) -> list[str] | None:
    """Return cached chat starter prompts for a session, or ``None``."""
    oid = _to_object_id(session_id)
    doc = await db[SESSIONS].find_one(
        {"_id": oid}, projection={"chat_suggestions": 1}
    )
    if doc is None:
        return None
    cached = doc.get("chat_suggestions")
    return list(cached) if cached else None


async def set_chat_suggestions(
    db: AsyncIOMotorDatabase, session_id: str, suggestions: list[str]
) -> None:
    """Cache chat starter prompts on the session document."""
    oid = _to_object_id(session_id)
    await db[SESSIONS].update_one(
        {"_id": oid}, {"$set": {"chat_suggestions": suggestions}}
    )
