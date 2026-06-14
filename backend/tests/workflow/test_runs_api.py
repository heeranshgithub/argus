"""HTTP tests for the runs + report APIs, including the camelCase bridge."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.api.dependencies import get_workflow_deps
from app.config import Settings
from app.db.mongo import MongoManager
from app.main import create_app
from app.repositories import workflow_repo
from app.workflow.deps import WorkflowDeps
from tests.workflow.conftest import FakeFetcher, FakeSearchClient, happy_path_llm


class _FakeMongoManager(MongoManager):
    def connect(self, settings: Settings) -> None:
        self._client = AsyncMongoMockClient(tz_aware=True)
        self._db = self._client[settings.mongo_db_name]

    async def disconnect(self) -> None:
        self._client = None
        self._db = None

    async def ping(self) -> bool:
        return True


@pytest.fixture
async def api() -> AsyncIterator[tuple[AsyncClient, object]]:
    """AsyncClient wired to the app with fake workflow deps + mock Mongo."""
    settings = Settings(env="test", mongo_db_name="argus_test")
    app = create_app(settings)
    manager = _FakeMongoManager()
    manager.connect(settings)
    app.state.mongo = manager

    deps = WorkflowDeps(
        llm=happy_path_llm(),
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


async def _create_session(client: AsyncClient) -> str:
    resp = await client.post("/api/sessions", json=SESSION_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _wait_for_run(client: AsyncClient, session_id: str, run_id: str) -> dict:
    """Poll a run until it leaves the running state (background tasks finish)."""
    for _ in range(50):
        body = (await client.get(f"/api/sessions/{session_id}/runs/{run_id}")).json()
        if body["status"] != "running":
            return body
    raise AssertionError("run did not finish in time")


async def test_run_produces_report_end_to_end(api) -> None:
    client, _db = api
    session_id = await _create_session(client)

    resp = await client.post(f"/api/sessions/{session_id}/run")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    run_id = body["runId"]  # camelCase on the wire
    assert run_id

    run = await _wait_for_run(client, session_id, run_id)
    assert run["status"] == "completed"
    # camelCase bridge: nodeStatus + startedAt, never snake_case.
    assert "nodeStatus" in run and "startedAt" in run
    assert "node_status" not in run
    assert run["nodeStatus"]["reporter"] == "done"
    assert run["events"][0]["kind"] == "run_started"

    # Report is now available with all nine sections, camelCase.
    rep = await client.get(f"/api/sessions/{session_id}/report")
    assert rep.status_code == 200
    report = rep.json()
    for key in (
        "companyOverview",
        "productsAndServices",
        "targetCustomers",
        "businessSignals",
        "risksAndChallenges",
        "suggestedDiscoveryQuestions",
        "suggestedOutreachStrategy",
        "unknowns",
        "sources",
    ):
        assert key in report
    assert "company_overview" not in report
    assert report["suggestedDiscoveryQuestions"][0]["question"]


async def test_list_runs_after_run(api) -> None:
    client, _db = api
    session_id = await _create_session(client)
    resp = await client.post(f"/api/sessions/{session_id}/run")
    await _wait_for_run(client, session_id, resp.json()["runId"])

    listed = await client.get(f"/api/sessions/{session_id}/runs")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert "items" in body
    # Summaries omit the (potentially large) events list.
    assert "events" not in body["items"][0]


async def test_double_run_returns_409_conflict(api) -> None:
    client, db = api
    session_id = await _create_session(client)
    # Simulate an in-flight run so the conflict path is deterministic.
    await workflow_repo.create_run(db, session_id)

    resp = await client.post(f"/api/sessions/{session_id}/run")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "session_already_running"


async def test_run_missing_session_returns_404(api) -> None:
    client, _db = api
    resp = await client.post(f"/api/sessions/{'0' * 24}/run")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "session_not_found"


async def test_report_404_before_any_run(api) -> None:
    client, _db = api
    session_id = await _create_session(client)
    resp = await client.get(f"/api/sessions/{session_id}/report")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "report_not_found"


async def test_resume_non_failed_session_returns_409(api) -> None:
    client, _db = api
    session_id = await _create_session(client)  # status 'created'
    resp = await client.post(f"/api/sessions/{session_id}/run/resume")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "session_not_resumable"


async def test_sse_endpoint_streams_backfill(api) -> None:
    client, _db = api
    session_id = await _create_session(client)
    run_resp = await client.post(f"/api/sessions/{session_id}/run")
    run_id = run_resp.json()["runId"]
    await _wait_for_run(client, session_id, run_id)

    # Run already finished → the stream backfills and closes with a terminal kind.
    resp = await client.get(f"/api/sessions/{session_id}/runs/{run_id}/events")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: run_started" in resp.text
    assert "event: run_completed" in resp.text
