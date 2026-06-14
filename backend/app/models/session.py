"""Session models — the camelCase wire shapes for the sessions resource.

All inherit ``ApiModel`` so the JSON wire is camelCase while the Python
attributes stay snake_case. ``SessionOut`` exposes the Mongo ``_id`` as a plain
``id`` string; the ``_id`` → ``id`` conversion happens at the repo edge (see
``app.models.mongo_base``) so ``ObjectId`` never reaches Pydantic.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, HttpUrl

from app.models.base import ApiModel


class SessionStatus(StrEnum):
    """Lifecycle of a research session."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionCreate(ApiModel):
    """Request body for ``POST /api/sessions``."""

    company_name: str = Field(min_length=1, max_length=200)
    website: HttpUrl
    objective: str = Field(min_length=1, max_length=2000)


class SessionUpdate(ApiModel):
    """Partial update of a session (status only for now)."""

    status: SessionStatus | None = None


class SessionOut(ApiModel):
    """A session as returned on the wire."""

    id: str
    company_name: str
    website: str
    objective: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class SessionListResponse(ApiModel):
    """Paginated list envelope for ``GET /api/sessions``."""

    items: list[SessionOut]
    total: int
