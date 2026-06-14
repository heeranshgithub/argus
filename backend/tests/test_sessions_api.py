"""Full HTTP tests for the sessions API, including the camelCase ↔ snake_case
naming bridge proven against the real stored document."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.config import Settings
from app.db.collections import SESSIONS
from app.db.mongo import MongoManager
from app.main import create_app


class _FakeMongoManager(MongoManager):
    """MongoManager backed by mongomock; exposes its db for direct assertions."""

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
    """An AsyncClient wired to the app, plus the live (mock) db handle."""
    settings = Settings(env="test", mongo_db_name="argus_test")
    app = create_app(settings)
    manager = _FakeMongoManager()
    manager.connect(settings)
    app.state.mongo = manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, manager.db


VALID_PAYLOAD = {
    "companyName": "Acme Corp",
    "website": "https://acme.example.com",
    "objective": "Understand their procurement priorities before the call.",
}


async def test_create_returns_camelcase_201(api) -> None:
    client, _db = api
    resp = await client.post("/api/sessions", json=VALID_PAYLOAD)
    assert resp.status_code == 201

    body = resp.json()
    assert body["companyName"] == "Acme Corp"
    assert body["status"] == "created"
    assert body["id"]
    assert "createdAt" in body and "updatedAt" in body
    # No snake_case leaks onto the wire.
    assert "company_name" not in body
    assert "created_at" not in body


async def test_stored_document_is_snake_case(api) -> None:
    client, db = api
    resp = await client.post("/api/sessions", json=VALID_PAYLOAD)
    assert resp.status_code == 201

    doc = await db[SESSIONS].find_one({})
    assert doc is not None
    # Mongo stores snake_case keys, never camelCase.
    assert doc["company_name"] == "Acme Corp"
    assert "created_at" in doc and "updated_at" in doc
    assert "companyName" not in doc
    assert "createdAt" not in doc


async def test_list_returns_newest_first(api) -> None:
    client, _db = api
    await client.post("/api/sessions", json={**VALID_PAYLOAD, "companyName": "First"})
    await client.post("/api/sessions", json={**VALID_PAYLOAD, "companyName": "Second"})

    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [item["companyName"] for item in body["items"]] == ["Second", "First"]


async def test_get_existing_session(api) -> None:
    client, _db = api
    created = (await client.post("/api/sessions", json=VALID_PAYLOAD)).json()

    resp = await client.get(f"/api/sessions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_missing_session_returns_404_contract(api) -> None:
    client, _db = api
    resp = await client.get(f"/api/sessions/{'0' * 24}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "session_not_found"
    assert "message" in body["error"]


async def test_get_invalid_id_returns_400(api) -> None:
    client, _db = api
    resp = await client.get("/api/sessions/not-a-valid-id")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_id"


@pytest.mark.parametrize(
    "payload",
    [
        {"website": "https://acme.example.com", "objective": "x"},  # missing companyName
        {**VALID_PAYLOAD, "website": "not-a-url"},  # invalid URL
        {**VALID_PAYLOAD, "companyName": ""},  # empty company name
        {**VALID_PAYLOAD, "companyName": "x" * 201},  # oversized company name
        {**VALID_PAYLOAD, "objective": "x" * 2001},  # oversized objective
    ],
)
async def test_create_validation_errors(api, payload) -> None:
    client, _db = api
    resp = await client.post("/api/sessions", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
