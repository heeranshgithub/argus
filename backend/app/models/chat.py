"""Chat models — the camelCase wire shape for follow-up chat (PLAN_PART_5 §1.2).

A chat message is grounded in the session's report + raw sources. Assistant
replies stream in (``status='streaming'``) and are finalized with citations and
usage analytics. ``role='system'`` messages are persisted for auditability but
hidden from the UI. All inherit :class:`ApiModel`, so the wire is camelCase while
the Python attributes — and the Mongo document — stay snake_case.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.models.base import ApiModel


class ChatRole(StrEnum):
    """Author of a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatStatus(StrEnum):
    """Lifecycle of an assistant message (user messages are born ``complete``)."""

    STREAMING = "streaming"
    COMPLETE = "complete"
    FAILED = "failed"


class Citation(ApiModel):
    """A source the assistant cited, keyed by its ``[i]`` index in the prompt."""

    source_index: int
    url: str
    title: str
    snippet: str


class ChatError(ApiModel):
    """Why an assistant message failed to generate."""

    code: str
    message: str


class ChatMessageOut(ApiModel):
    """A single chat message as returned on the wire."""

    id: str
    session_id: str
    role: ChatRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime
    finished_at: datetime | None = None
    status: ChatStatus
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    error: ChatError | None = None


class ChatCreate(ApiModel):
    """Inbound body for ``POST /sessions/{id}/chat``."""

    content: str = Field(min_length=1, max_length=4000)


class ChatAccepted(ApiModel):
    """Returned immediately from ``POST`` — the assistant reply streams via SSE."""

    message_id: str


class ChatListResponse(ApiModel):
    """Paginated chat history (oldest-first), excluding ``system`` messages."""

    items: list[ChatMessageOut]
    total: int


class ChatSuggestionsOut(ApiModel):
    """The three starter prompts shown on an empty chat (LLM-generated, cached)."""

    suggestions: list[str] = Field(default_factory=list)
