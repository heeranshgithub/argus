"""Health and naming-bridge sanity-check models."""

from typing import Literal

from pydantic import Field

from app.models.base import ApiModel


class HealthResponse(ApiModel):
    """Response for ``GET /api/health``."""

    status: Literal["ok", "down"]
    mongo: Literal["ok", "down"]
    # OpenRouter reachability (HEAD on the API base, cached); ``unknown`` when no
    # key is configured or the probe hasn't run (PLAN_PART_5 §2.1).
    openrouter: Literal["ok", "down", "unknown"] = "unknown"
    version: str


class ClientErrorReport(ApiModel):
    """A browser-side error POSTed to ``/api/client-errors`` (PLAN_PART_5 §2.3)."""

    message: str = Field(max_length=2000)
    stack: str | None = Field(default=None, max_length=8000)
    url: str | None = Field(default=None, max_length=2000)
    user_agent: str | None = Field(default=None, max_length=1000)
    request_id: str | None = Field(default=None, max_length=200)


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
