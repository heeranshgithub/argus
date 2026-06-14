"""Health and naming-bridge sanity-check models."""

from typing import Literal

from app.models.base import ApiModel


class HealthResponse(ApiModel):
    """Response for ``GET /api/health``."""

    status: Literal["ok", "down"]
    mongo: Literal["ok", "down"]
    version: str


class EchoRequest(ApiModel):
    """Request body for the naming-bridge echo endpoint.

    Arrives as camelCase (``fullName``, ``retryCount``) on the wire and is
    exposed to the handler as snake_case attributes.
    """

    full_name: str
    retry_count: int


class EchoResponse(ApiModel):
    """Echoes the request back; re-serialized as camelCase on the wire."""

    full_name: str
    retry_count: int
