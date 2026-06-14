"""Repository tests against an in-memory Mongo (mongomock-motor)."""

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

from app.db.collections import SESSIONS
from app.exceptions import InvalidObjectId
from app.models.session import SessionCreate, SessionStatus
from app.repositories import session_repo


@pytest.fixture
def db():
    """A fresh in-memory database per test."""
    return AsyncMongoMockClient(tz_aware=True)["argus_test"]


def _make(company: str = "Acme") -> SessionCreate:
    return SessionCreate(
        company_name=company,
        website="https://example.com",
        objective="Understand the buyer before the meeting.",
    )


async def test_create_sets_defaults_and_timestamps(db) -> None:
    out = await session_repo.create(db, _make())

    assert out.id
    assert out.company_name == "Acme"
    assert out.status is SessionStatus.CREATED
    assert out.created_at == out.updated_at

    # Stored document uses snake_case keys.
    doc = await db[SESSIONS].find_one({"_id": ObjectId(out.id)})
    assert doc is not None
    assert set(doc).issuperset(
        {"company_name", "website", "objective", "status", "created_at", "updated_at"}
    )


async def test_get_returns_none_for_missing(db) -> None:
    assert await session_repo.get(db, "0" * 24) is None


async def test_get_rejects_invalid_object_id(db) -> None:
    with pytest.raises(InvalidObjectId):
        await session_repo.get(db, "not-an-object-id")


async def test_get_roundtrips(db) -> None:
    created = await session_repo.create(db, _make())
    fetched = await session_repo.get(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.company_name == created.company_name


async def test_list_orders_newest_first(db) -> None:
    first = await session_repo.create(db, _make("First"))
    second = await session_repo.create(db, _make("Second"))
    third = await session_repo.create(db, _make("Third"))

    items = await session_repo.list_sessions(db, limit=20, skip=0)
    assert [s.id for s in items] == [third.id, second.id, first.id]


async def test_list_pagination(db) -> None:
    for i in range(5):
        await session_repo.create(db, _make(f"Co{i}"))

    page = await session_repo.list_sessions(db, limit=2, skip=2)
    assert len(page) == 2
    assert await session_repo.count(db) == 5


async def test_update_status(db) -> None:
    created = await session_repo.create(db, _make())
    updated = await session_repo.update_status(db, created.id, SessionStatus.RUNNING)
    assert updated is not None
    assert updated.status is SessionStatus.RUNNING
    assert updated.updated_at >= created.updated_at


async def test_update_status_missing_returns_none(db) -> None:
    assert await session_repo.update_status(db, "0" * 24, SessionStatus.RUNNING) is None
