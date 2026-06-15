"""Async CRUD for the ``chat_messages`` collection (PLAN_PART_5 §1.2).

Stores documents snake_case; conversion to the camelCase :class:`ChatMessageOut`
happens in :func:`to_chat_message_out`. Functions take the database explicitly so
they stay trivial to test against an in-memory Mongo. ``role='system'`` messages
are persisted but filtered out of history reads unless explicitly requested.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.collections import CHAT_MESSAGES
from app.exceptions import InvalidObjectId
from app.metrics import metrics
from app.models.chat import (
    ChatError,
    ChatMessageOut,
    ChatRole,
    ChatStatus,
    Citation,
)

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


def _utcnow_ms() -> datetime:
    """Current UTC time truncated to millisecond precision (matches BSON)."""
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _to_object_id(message_id: str) -> ObjectId:
    """Parse a wire id into an ``ObjectId`` or raise :class:`InvalidObjectId`."""
    try:
        return ObjectId(message_id)
    except (InvalidId, TypeError) as exc:
        raise InvalidObjectId(message_id) from exc


async def create_message(
    db: AsyncIOMotorDatabase,
    session_id: str,
    *,
    role: ChatRole,
    content: str,
    status: ChatStatus,
    citations: list[Citation] | None = None,
    model: str | None = None,
) -> str:
    """Insert a chat message and return its id."""
    now = _utcnow_ms()
    doc: dict[str, Any] = {
        "session_id": session_id,
        "role": role.value,
        "content": content,
        "citations": [c.model_dump() for c in (citations or [])],
        "created_at": now,
        "finished_at": now if status is ChatStatus.COMPLETE else None,
        "status": status.value,
        "model": model,
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "error": None,
    }
    result = await db[CHAT_MESSAGES].insert_one(doc)
    metrics.incr_chat_message(role.value)
    return str(result.inserted_id)


async def finalize_message(
    db: AsyncIOMotorDatabase,
    message_id: str,
    *,
    content: str,
    citations: list[Citation],
    model: str | None,
    tokens_in: int | None,
    tokens_out: int | None,
    cost_usd: float | None,
) -> None:
    """Mark a streaming assistant message ``complete`` with its final content."""
    await db[CHAT_MESSAGES].update_one(
        {"_id": _to_object_id(message_id)},
        {
            "$set": {
                "content": content,
                "citations": [c.model_dump() for c in citations],
                "status": ChatStatus.COMPLETE.value,
                "finished_at": _utcnow_ms(),
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_usd,
            }
        },
    )


async def fail_message(
    db: AsyncIOMotorDatabase, message_id: str, *, error: ChatError
) -> None:
    """Mark an assistant message ``failed`` with an error detail."""
    await db[CHAT_MESSAGES].update_one(
        {"_id": _to_object_id(message_id)},
        {
            "$set": {
                "status": ChatStatus.FAILED.value,
                "finished_at": _utcnow_ms(),
                "error": error.model_dump(),
            }
        },
    )


async def delete_message(db: AsyncIOMotorDatabase, message_id: str) -> None:
    """Delete a single chat message (used by retry)."""
    await db[CHAT_MESSAGES].delete_one({"_id": _to_object_id(message_id)})


async def get_message(
    db: AsyncIOMotorDatabase, session_id: str, message_id: str
) -> ChatMessageOut | None:
    """Fetch one chat message scoped to its session, or ``None``."""
    doc = await db[CHAT_MESSAGES].find_one(
        {"_id": _to_object_id(message_id), "session_id": session_id}
    )
    return to_chat_message_out(doc) if doc is not None else None


def _visible_filter(session_id: str, *, include_system: bool) -> dict[str, Any]:
    query: dict[str, Any] = {"session_id": session_id}
    if not include_system:
        query["role"] = {"$ne": ChatRole.SYSTEM.value}
    return query


async def list_messages(
    db: AsyncIOMotorDatabase,
    session_id: str,
    *,
    limit: int,
    skip: int,
    include_system: bool = False,
) -> list[ChatMessageOut]:
    """Return a session's chat history oldest-first (UI render order)."""
    cursor = (
        db[CHAT_MESSAGES]
        .find(_visible_filter(session_id, include_system=include_system))
        .sort([("created_at", 1), ("_id", 1)])
        .skip(skip)
        .limit(limit)
    )
    return [to_chat_message_out(doc) async for doc in cursor]


async def count_messages(
    db: AsyncIOMotorDatabase, session_id: str, *, include_system: bool = False
) -> int:
    """Total visible chat messages for a session."""
    return await db[CHAT_MESSAGES].count_documents(
        _visible_filter(session_id, include_system=include_system)
    )


async def recent_history(
    db: AsyncIOMotorDatabase, session_id: str, *, limit: int
) -> list[ChatMessageOut]:
    """Return the last ``limit`` non-system messages, oldest-first.

    Fetches newest-first then reverses, so a sliding window of the most recent
    turns is returned in conversational order for prompt assembly (PLAN §1.3.4).
    """
    cursor = (
        db[CHAT_MESSAGES]
        .find(_visible_filter(session_id, include_system=False))
        .sort([("created_at", -1), ("_id", -1)])
        .limit(limit)
    )
    items = [to_chat_message_out(doc) async for doc in cursor]
    items.reverse()
    return items


# --- converters ----------------------------------------------------------------


def _error_from_doc(raw: Mapping[str, Any] | None) -> ChatError | None:
    return ChatError.model_validate(raw) if raw else None


def to_chat_message_out(doc: Mapping[str, Any]) -> ChatMessageOut:
    """Convert a raw ``chat_messages`` document into a :class:`ChatMessageOut`."""
    data = dict(doc)
    raw_id = data.pop("_id", None)
    return ChatMessageOut(
        id=str(raw_id),
        session_id=data["session_id"],
        role=ChatRole(data["role"]),
        content=data.get("content", ""),
        citations=[Citation.model_validate(c) for c in data.get("citations", [])],
        created_at=data["created_at"],
        finished_at=data.get("finished_at"),
        status=ChatStatus(data["status"]),
        model=data.get("model"),
        tokens_in=data.get("tokens_in"),
        tokens_out=data.get("tokens_out"),
        cost_usd=data.get("cost_usd"),
        error=_error_from_doc(data.get("error")),
    )
