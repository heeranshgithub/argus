"""Async CRUD for the ``reports`` collection.

One report per session (the ``session_id`` index is unique). The reporter node
hands us a :class:`ReportDraft` (sections only); we stamp ``session_id`` and
``created_at`` and upsert, so a re-run replaces the prior report in place.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pymongo import ReturnDocument

from app.db.collections import REPORTS
from app.models.report import ReportDraft, ReportOut

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


def _utcnow_ms() -> datetime:
    """Current UTC time truncated to millisecond precision (matches BSON)."""
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


async def upsert_report(
    db: AsyncIOMotorDatabase, session_id: str, draft: ReportDraft
) -> ReportOut:
    """Insert or replace the report for ``session_id`` and return it."""
    doc = draft.model_dump()  # snake_case section fields
    doc["session_id"] = session_id
    doc["created_at"] = _utcnow_ms()
    saved = await db[REPORTS].find_one_and_replace(
        {"session_id": session_id},
        doc,
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return to_report_out(saved)


async def get_by_session(
    db: AsyncIOMotorDatabase, session_id: str
) -> ReportOut | None:
    """Fetch the report for a session, or ``None`` if not yet generated."""
    doc = await db[REPORTS].find_one({"session_id": session_id})
    return to_report_out(doc) if doc is not None else None


def to_report_out(doc: Mapping[str, Any]) -> ReportOut:
    """Convert a raw ``reports`` document into a :class:`ReportOut`."""
    data = dict(doc)
    raw_id = data.pop("_id", None)
    data["id"] = str(raw_id)
    return ReportOut.model_validate(data)
