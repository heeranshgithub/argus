"""HTTP tests for the follow-up chat API: post/stream, retry, history, errors."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.api.dependencies import get_workflow_deps
from app.config import Settings
from app.db.collections import WORKFLOW_RUNS
from app.db.mongo import MongoManager
from app.main import create_app
from app.models.report import ReportDraft, ReportSource
from app.repositories import report_repo
from app.workflow.deps import WorkflowDeps
from app.workflow.tools.llm import FakeLLMClient
from tests.workflow.conftest import FakeFetcher, FakeSearchClient


class _FakeMongoManager(MongoManager):
    def connect(self, settings: Settings) -> None:
        self._client = AsyncMongoMockClient(tz_aware=True)
        self._db = self._client[settings.mongo_db_name]

    async def disconnect(self) -> None:
        self._client = None
        self._db = None

    async def ping(self) -> bool:
        return True


_STREAM_ANSWER = (
    "Their biggest signal is the recent funding round [1], and hiring is "
    "accelerating [2]. I'd lead with that."
)


def _chat_llm() -> FakeLLMClient:
    return FakeLLMClient(
        by_model={"_Suggestions": [{"suggestions": ["Q1?", "Q2?", "Q3?"]}]},
        stream_texts=[_STREAM_ANSWER],
        repeat_last=True,
    )


@pytest.fixture
async def api() -> AsyncIterator[tuple[AsyncClient, object]]:
    settings = Settings(env="test", mongo_db_name="argus_test")
    app = create_app(settings)
    manager = _FakeMongoManager()
    manager.connect(settings)
    app.state.mongo = manager

    deps = WorkflowDeps(
        llm=_chat_llm(),
        search=FakeSearchClient(),
        fetcher=FakeFetcher(),
        settings=settings,
    )
    app.dependency_overrides[get_workflow_deps] = lambda: deps

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, manager.db


SESSION_PAYLOAD = {
    "companyName": "Acme Corp",
    "website": "https://acme.example.com",
    "objective": "Explore an expansion partnership before the call.",
}

_RAW_SOURCES = [
    {
        "url": "https://acme.example.com/funding",
        "title": "Acme raises Series B",
        "snippet": "Acme raised a $20M Series B funding round led by investors.",
        "content": "Acme raised a $20M Series B funding round to fuel growth.",
        "fetched_at": "2026-06-01T00:00:00Z",
    },
    {
        "url": "https://acme.example.com/careers",
        "title": "Acme is hiring",
        "snippet": "Acme is hiring engineers across many teams, growing headcount.",
        "content": "Acme is hiring engineers and recruiting talent rapidly.",
        "fetched_at": "2026-06-01T00:00:00Z",
    },
    {
        "url": "https://acme.example.com/product",
        "title": "Acme product launch",
        "snippet": "Acme launched a new analytics product feature.",
        "content": "Acme shipped a new analytics product with a fresh roadmap.",
        "fetched_at": "2026-06-01T00:00:00Z",
    },
]


async def _seed_session_with_report(client: AsyncClient, db: object) -> str:
    """Create a session, a completed run with raw_sources, and a report."""
    resp = await client.post("/api/sessions", json=SESSION_PAYLOAD)
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    await db[WORKFLOW_RUNS].insert_one(
        {
            "session_id": session_id,
            "status": "completed",
            "started_at": datetime.now(UTC),
            "finished_at": datetime.now(UTC),
            "node_status": {},
            "events": [],
            "error": None,
            "final_state_keys": [],
            "raw_sources": _RAW_SOURCES,
        }
    )

    draft = ReportDraft(
        company_overview="Acme builds developer tooling.",
        products_and_services=["CLI", "Dashboard"],
        target_customers=["Engineering teams"],
        business_signals=[],
        risks_and_challenges=["Crowded market"],
        suggested_discovery_questions=[],
        suggested_outreach_strategy="Lead with the funding signal.",
        unknowns=["Pricing"],
        sources=[
            ReportSource(
                url="https://acme.example.com/funding",
                title="Acme raises Series B",
                used_in=["signals"],
            )
        ],
    )
    await report_repo.upsert_report(db, session_id, draft)  # type: ignore[arg-type]
    return session_id


async def _drain_stream(
    client: AsyncClient, session_id: str, message_id: str, *, since_seq: int = 0
) -> str:
    resp = await client.get(
        f"/api/sessions/{session_id}/chat/{message_id}/stream",
        params={"since_seq": since_seq},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    return resp.text


async def test_post_chat_streams_grounded_reply_with_citations(api) -> None:
    client, db = api
    session_id = await _seed_session_with_report(client, db)

    resp = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"content": "What's their biggest growth signal?"},
    )
    assert resp.status_code == 200
    message_id = resp.json()["messageId"]
    assert message_id

    # Let the background generation task run to completion.
    for _ in range(50):
        msg = await client.get(f"/api/sessions/{session_id}/chat")
        items = msg.json()["items"]
        assistant = [m for m in items if m["role"] == "assistant"]
        if assistant and assistant[-1]["status"] == "complete":
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("assistant reply did not complete")

    body = msg.json()
    roles = [m["role"] for m in body["items"]]
    assert roles == ["user", "assistant"]
    reply = body["items"][1]
    assert "funding round" in reply["content"]
    # Citations parsed from [1]/[2] and mapped to source URLs (camelCase wire).
    citation_indices = [c["sourceIndex"] for c in reply["citations"]]
    assert citation_indices == [1, 2]
    assert reply["citations"][0]["url"].startswith("https://acme.example.com/")


async def test_stream_endpoint_replays_completed_reply(api) -> None:
    client, db = api
    session_id = await _seed_session_with_report(client, db)
    resp = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"content": "Summarize the company."},
    )
    message_id = resp.json()["messageId"]

    # Drain twice: even after completion the stream replays the persisted reply
    # and closes with a done event (refresh-after-complete resumability).
    text = await _drain_stream(client, session_id, message_id)
    assert "event: done" in text
    again = await _drain_stream(client, session_id, message_id)
    assert "event: done" in again


async def test_chat_without_report_returns_409(api) -> None:
    client, _db = api
    resp = await client.post("/api/sessions", json=SESSION_PAYLOAD)
    session_id = resp.json()["id"]

    chat = await client.post(
        f"/api/sessions/{session_id}/chat", json={"content": "hi"}
    )
    assert chat.status_code == 409
    assert chat.json()["error"]["code"] == "chat_no_report"


async def test_chat_missing_session_returns_404(api) -> None:
    client, _db = api
    resp = await client.post(
        f"/api/sessions/{'0' * 24}/chat", json={"content": "hi"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "session_not_found"


async def test_suggestions_returns_three_and_caches(api) -> None:
    client, db = api
    session_id = await _seed_session_with_report(client, db)

    resp = await client.get(f"/api/sessions/{session_id}/chat/suggestions")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 3

    # Cached on the session document.
    again = await client.get(f"/api/sessions/{session_id}/chat/suggestions")
    assert again.json()["suggestions"] == suggestions


async def test_retry_replaces_last_assistant_message(api) -> None:
    client, db = api
    session_id = await _seed_session_with_report(client, db)
    first = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"content": "What's their biggest growth signal?"},
    )
    first_message_id = first.json()["messageId"]

    async def _wait_complete() -> None:
        for _ in range(50):
            items = (await client.get(f"/api/sessions/{session_id}/chat")).json()[
                "items"
            ]
            assistant = [m for m in items if m["role"] == "assistant"]
            if assistant and assistant[-1]["status"] == "complete":
                return
            await asyncio.sleep(0.01)
        raise AssertionError("reply did not complete")

    await _wait_complete()

    retry = await client.post(
        f"/api/sessions/{session_id}/chat/{first_message_id}/retry"
    )
    assert retry.status_code == 200
    new_message_id = retry.json()["messageId"]
    assert new_message_id != first_message_id
    await _wait_complete()

    items = (await client.get(f"/api/sessions/{session_id}/chat")).json()["items"]
    # Still exactly one user + one assistant (the old assistant was replaced).
    assert [m["role"] for m in items] == ["user", "assistant"]
    assert items[1]["id"] == new_message_id
