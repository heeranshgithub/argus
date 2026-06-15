"""Tests for Part 5 production hardening: cost cap, metrics, rate limit, errors."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.api.dependencies import get_workflow_deps
from app.api.rate_limit import configure as configure_rate_limit
from app.api.rate_limit import limiter
from app.config import Settings
from app.db.mongo import MongoManager
from app.main import create_app
from app.metrics import metrics
from app.models.session import SessionStatus
from app.repositories import session_repo
from app.workflow.deps import WorkflowDeps
from app.workflow.tools.llm import FakeLLMClient
from tests.workflow.conftest import (
    FakeFetcher,
    FakeSearchClient,
    make_analysis,
    make_plan,
    make_quality,
    make_report,
    make_signals,
)

SESSION_PAYLOAD = {
    "companyName": "Acme Corp",
    "website": "https://acme.example.com",
    "objective": "Explore an expansion partnership before the call.",
}


class _FakeMongoManager(MongoManager):
    def connect(self, settings: Settings) -> None:
        self._client = AsyncMongoMockClient(tz_aware=True)
        self._db = self._client[settings.mongo_db_name]

    async def disconnect(self) -> None:
        self._client = None
        self._db = None

    async def ping(self) -> bool:
        return True


def _scripted_llm(cost_per_call: float = 0.0) -> FakeLLMClient:
    return FakeLLMClient(
        {
            "PlanResult": [make_plan()],
            "SignalsResult": [make_signals()],
            "AnalysisResult": [make_analysis()],
            "QualityResult": [make_quality(needs_more=False)],
            "ReportDraft": [make_report()],
        },
        cost_per_call=cost_per_call,
    )


def _make_app(settings: Settings, llm: FakeLLMClient) -> tuple[object, object]:
    app = create_app(settings)
    manager = _FakeMongoManager()
    manager.connect(settings)
    app.state.mongo = manager
    deps = WorkflowDeps(
        llm=llm, search=FakeSearchClient(), fetcher=FakeFetcher(), settings=settings
    )
    app.dependency_overrides[get_workflow_deps] = lambda: deps
    return app, manager.db


async def _client(app: object) -> AsyncClient:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    return AsyncClient(transport=transport, base_url="http://test")


async def _create_session(client: AsyncClient) -> str:
    resp = await client.post("/api/sessions", json=SESSION_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _wait_for_run(client: AsyncClient, session_id: str, run_id: str) -> dict:
    for _ in range(80):
        body = (await client.get(f"/api/sessions/{session_id}/runs/{run_id}")).json()
        if body["status"] != "running":
            return body
    raise AssertionError("run did not finish in time")


async def test_cost_cap_fails_run_with_clear_code() -> None:
    settings = Settings(
        env="test", mongo_db_name="argus_test", workflow_max_cost_usd=0.5
    )
    app, _db = _make_app(settings, _scripted_llm(cost_per_call=0.6))
    async with await _client(app) as client:
        session_id = await _create_session(client)
        run_resp = await client.post(f"/api/sessions/{session_id}/run")
        run = await _wait_for_run(client, session_id, run_resp.json()["runId"])
        assert run["status"] == "failed"
        assert run["error"]["code"] == "cost_cap_exceeded"


async def test_metrics_endpoint_counts_requests() -> None:
    metrics.reset()
    settings = Settings(env="test", mongo_db_name="argus_test")
    app, _db = _make_app(settings, _scripted_llm())
    async with await _client(app) as client:
        await _create_session(client)
        resp = await client.get("/api/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert "requestsTotal" in body
        # The create-session POST was tallied under its route template.
        keys = " ".join(body["requestsTotal"].keys())
        assert "POST /api/sessions 201" in keys


async def test_client_error_endpoint_returns_204() -> None:
    settings = Settings(env="test", mongo_db_name="argus_test")
    app, _db = _make_app(settings, _scripted_llm())
    async with await _client(app) as client:
        resp = await client.post(
            "/api/client-errors",
            json={"message": "boom", "url": "http://x/y", "requestId": "abc"},
        )
        assert resp.status_code == 204
        assert resp.content == b""


async def test_error_responses_carry_request_id() -> None:
    settings = Settings(env="test", mongo_db_name="argus_test")
    app, _db = _make_app(settings, _scripted_llm())
    async with await _client(app) as client:
        resp = await client.get(f"/api/sessions/{'0' * 24}")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["details"]["requestId"]
        assert body["error"]["details"]["requestId"] == resp.headers["x-request-id"]


async def test_graceful_shutdown_marks_running_interrupted() -> None:
    settings = Settings(env="test", mongo_db_name="argus_test")
    app, db = _make_app(settings, _scripted_llm())
    async with await _client(app) as client:
        session_id = await _create_session(client)
        await session_repo.update_status(db, session_id, SessionStatus.RUNNING)

        count = await session_repo.mark_running_interrupted(db)
        assert count == 1
        session = await session_repo.get(db, session_id)
        assert session is not None
        assert session.status is SessionStatus.INTERRUPTED
        # An interrupted session is resumable.
        resume = await client.post(f"/api/sessions/{session_id}/run/resume")
        assert resume.status_code == 202


@pytest.fixture
async def _rate_limited_app() -> AsyncIterator[AsyncClient]:
    # env != "test" enables the limiter; reset storage so the window is clean.
    with contextlib.suppress(Exception):
        limiter.reset()
    settings = Settings(env="dev", mongo_db_name="argus_test")
    app, _db = _make_app(settings, _scripted_llm())
    try:
        async with await _client(app) as client:
            yield client
    finally:
        # Disable again + clear counters so later tests aren't throttled.
        configure_rate_limit(Settings(env="test"))
        with contextlib.suppress(Exception):
            limiter.reset()


async def test_rate_limit_returns_429_with_contract(_rate_limited_app) -> None:
    client = _rate_limited_app
    # create_session limit defaults to 30/min; the 31st should be throttled.
    last = None
    for _ in range(31):
        last = await client.post("/api/sessions", json=SESSION_PAYLOAD)
    assert last is not None
    assert last.status_code == 429
    body = last.json()
    assert body["error"]["code"] == "rate_limited"
    assert last.headers.get("Retry-After") == "60"
