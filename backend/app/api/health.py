"""Health check and naming-bridge echo routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app import __version__
from app.db.mongo import MongoManager
from app.models.health import EchoRequest, EchoResponse, HealthResponse

router = APIRouter(tags=["health"])


def get_mongo_manager() -> MongoManager:
    """Dependency placeholder; overridden by the app to return app.state.mongo."""
    raise RuntimeError("get_mongo_manager dependency was not overridden")


@router.get("/health", response_model=HealthResponse)
async def health(
    manager: Annotated[MongoManager, Depends(get_mongo_manager)],
) -> HealthResponse:
    """Report process and Mongo connectivity."""
    mongo_ok = await manager.ping()
    return HealthResponse(
        status="ok",
        mongo="ok" if mongo_ok else "down",
        version=__version__,
    )


@router.post("/_echo", response_model=EchoResponse)
async def echo(payload: EchoRequest) -> EchoResponse:
    """Round-trip the payload to prove the camelCase ↔ snake_case bridge.

    The handler only ever touches snake_case attributes (`payload.full_name`,
    `payload.retry_count`); FastAPI serializes the response back to camelCase.
    """
    return EchoResponse(full_name=payload.full_name, retry_count=payload.retry_count)
