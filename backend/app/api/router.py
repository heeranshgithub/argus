"""Aggregate v1 API router mounted under the configured API prefix."""

from fastapi import APIRouter

from app.api import health, reports, runs, sessions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(runs.router)
api_router.include_router(reports.router)
