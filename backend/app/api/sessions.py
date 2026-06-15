"""Sessions resource routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.rate_limit import create_session_limit, limiter
from app.db.mongo import get_db
from app.models.session import SessionCreate, SessionListResponse, SessionOut
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


@router.post(
    "",
    response_model=SessionOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(create_session_limit)
async def create_session(
    request: Request, payload: SessionCreate, db: DbDep
) -> SessionOut:
    """Create a research session."""
    return await session_service.create_session(db, payload)


@router.get("", response_model=SessionListResponse, response_model_by_alias=True)
async def list_sessions(
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    skip: Annotated[int, Query(ge=0)] = 0,
) -> SessionListResponse:
    """List sessions newest-first."""
    items, total = await session_service.list_sessions(db, limit=limit, skip=skip)
    return SessionListResponse(items=items, total=total)


@router.get("/{session_id}", response_model=SessionOut, response_model_by_alias=True)
async def get_session(session_id: str, db: DbDep) -> SessionOut:
    """Fetch a single session, or 404 if it does not exist."""
    return await session_service.get_session(db, session_id)
