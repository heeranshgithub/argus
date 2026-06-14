"""Aggregate v1 API router mounted under the configured API prefix."""

from fastapi import APIRouter

from app.api import health

api_router = APIRouter()
api_router.include_router(health.router)
