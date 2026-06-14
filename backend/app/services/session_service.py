"""Session orchestration above the repository.

Thin today — it exists so workflow wiring in later parts has a home that the API
layer already depends on, and so "not found" becomes a domain error here rather
than leaking ``None`` into route handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.exceptions import SessionNotFound
from app.models.session import SessionCreate, SessionOut
from app.repositories import session_repo

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


async def create_session(db: AsyncIOMotorDatabase, data: SessionCreate) -> SessionOut:
    """Create a new research session."""
    return await session_repo.create(db, data)


async def list_sessions(
    db: AsyncIOMotorDatabase, *, limit: int, skip: int
) -> tuple[list[SessionOut], int]:
    """Return a page of sessions plus the total count."""
    items = await session_repo.list_sessions(db, limit=limit, skip=skip)
    total = await session_repo.count(db)
    return items, total


async def get_session(db: AsyncIOMotorDatabase, session_id: str) -> SessionOut:
    """Fetch one session, raising :class:`SessionNotFound` if absent."""
    session = await session_repo.get(db, session_id)
    if session is None:
        raise SessionNotFound(session_id)
    return session
