"""Report route — fetch the generated report for a session."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.models.report import ReportOut
from app.services import workflow_service

router = APIRouter(prefix="/sessions", tags=["reports"])

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


@router.get("/{session_id}/report", response_model=ReportOut, response_model_by_alias=True)
async def get_report(session_id: str, db: DbDep) -> ReportOut:
    """Return the session's report, or 404 if it hasn't been generated yet."""
    return await workflow_service.get_report(db, session_id)
