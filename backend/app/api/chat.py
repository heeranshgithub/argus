"""Follow-up chat routes — post a question, stream the grounded reply, retry.

The POST returns immediately with a ``messageId``; the assistant reply is streamed
from ``GET /chat/{messageId}/stream`` (SSE) with the same ``sinceSeq`` resumability
as the workflow event stream (PLAN_PART_5 §1.4), so a refresh mid-generation
replays buffered token deltas and tails the rest without duplication.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.dependencies import get_workflow_deps
from app.api.rate_limit import chat_limit, limiter
from app.db.mongo import get_db
from app.models.chat import (
    ChatAccepted,
    ChatCreate,
    ChatListResponse,
    ChatMessageOut,
    ChatSuggestionsOut,
)
from app.services import chat_service
from app.services.chat_service import stream_manager
from app.workflow.deps import WorkflowDeps

router = APIRouter(prefix="/sessions", tags=["chat"])

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
DepsDep = Annotated[WorkflowDeps, Depends(get_workflow_deps)]

# How long to wait for a live delta before emitting an SSE heartbeat comment.
_SSE_HEARTBEAT_SECONDS = 15.0
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/{session_id}/chat", response_model=ChatAccepted, response_model_by_alias=True)
@limiter.limit(chat_limit)
async def post_chat(
    request: Request,
    session_id: str,
    payload: ChatCreate,
    db: DbDep,
    deps: DepsDep,
) -> ChatAccepted:
    """Accept a question and begin streaming the assistant reply (200 + messageId)."""
    return await chat_service.post_message(db, deps, session_id, payload.content)


@router.get(
    "/{session_id}/chat", response_model=ChatListResponse, response_model_by_alias=True
)
async def get_chat_history(
    session_id: str,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    skip: Annotated[int, Query(ge=0)] = 0,
) -> ChatListResponse:
    """Return the session's visible chat history, oldest-first."""
    return await chat_service.list_history(db, session_id, limit=limit, skip=skip)


@router.get(
    "/{session_id}/chat/suggestions",
    response_model=ChatSuggestionsOut,
    response_model_by_alias=True,
)
async def get_chat_suggestions(
    session_id: str, db: DbDep, deps: DepsDep
) -> ChatSuggestionsOut:
    """Return three starter prompts (LLM-generated, cached on the session)."""
    return await chat_service.get_suggestions(db, deps, session_id)


@router.post(
    "/{session_id}/chat/{message_id}/retry",
    response_model=ChatAccepted,
    response_model_by_alias=True,
)
async def retry_chat(
    session_id: str, message_id: str, db: DbDep, deps: DepsDep
) -> ChatAccepted:
    """Regenerate the last assistant reply from the same user question."""
    return await chat_service.retry_last(db, deps, session_id)


def _sse_delta(seq: int, text: str) -> str:
    data = json.dumps({"seq": seq, "text": text})
    return f"id: {seq}\nevent: delta\ndata: {data}\n\n"


def _sse_done(payload: dict[str, Any]) -> str:
    return f"event: done\ndata: {json.dumps(payload)}\n\n"


def _done_from_message(msg: ChatMessageOut) -> dict[str, Any]:
    return {
        "type": "done",
        "messageId": msg.id,
        "status": msg.status.value,
        "citations": [c.model_dump(by_alias=True) for c in msg.citations],
        "error": msg.error.model_dump(by_alias=True) if msg.error else None,
    }


@router.get("/{session_id}/chat/{message_id}/stream")
async def stream_chat(
    session_id: str,
    message_id: str,
    db: DbDep,
    request: Request,
    since_seq: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    """Stream an assistant reply via SSE: buffered deltas first, then live tail."""
    msg = await chat_service.get_message(db, session_id, message_id)  # 404 if absent

    async def generator() -> AsyncIterator[str]:
        state = stream_manager.get(message_id)
        # Subscribe before reading backfill to close the gap where a delta lands
        # between snapshot and subscription (mirrors the runs SSE).
        queue = (
            stream_manager.subscribe(message_id)
            if state is not None and not state.done
            else None
        )
        sent: set[int] = set()
        try:
            if state is not None:
                for seq, text in list(state.deltas):
                    if seq > since_seq:
                        sent.add(seq)
                        yield _sse_delta(seq, text)
                if state.done and state.final is not None:
                    yield _sse_done(state.final)
                    return
            else:
                # No live buffer in this process: replay the persisted message.
                if since_seq == 0 and msg.content:
                    yield _sse_delta(1, msg.content)
                yield _sse_done(_done_from_message(msg))
                return

            assert queue is not None
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=_SSE_HEARTBEAT_SECONDS
                    )
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if item["type"] == "delta":
                    if item["seq"] <= since_seq or item["seq"] in sent:
                        continue
                    sent.add(item["seq"])
                    yield _sse_delta(item["seq"], item["text"])
                elif item["type"] == "done":
                    yield _sse_done(item)
                    return
        finally:
            if queue is not None:
                stream_manager.unsubscribe(message_id, queue)

    return StreamingResponse(
        generator(), media_type="text/event-stream", headers=_SSE_HEADERS
    )
