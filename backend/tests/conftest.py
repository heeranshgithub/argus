"""Shared test fixtures: an app wired to an in-memory Mongo stand-in."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.config import Settings
from app.db.mongo import MongoManager
from app.main import create_app


class FakeMongoManager(MongoManager):
    """A MongoManager backed by mongomock with a controllable ping result."""

    def __init__(self, *, reachable: bool = True) -> None:
        super().__init__()
        self._reachable = reachable

    def connect(self, settings: Settings) -> None:
        client = AsyncMongoMockClient()
        self._client = client
        self._db = client[settings.mongo_db_name]

    async def disconnect(self) -> None:
        self._client = None
        self._db = None

    async def ping(self) -> bool:
        return self._reachable


def _build_client(*, reachable: bool) -> TestClient:
    settings = Settings(env="test", mongo_db_name="argus_test")
    app = create_app(settings)
    # Swap the real manager for the fake before lifespan runs.
    app.state.mongo = FakeMongoManager(reachable=reachable)
    return TestClient(app)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient with Mongo reachable (runs lifespan via context manager)."""
    with _build_client(reachable=True) as test_client:
        yield test_client


@pytest.fixture
def client_mongo_down() -> Iterator[TestClient]:
    """A TestClient where Mongo is unreachable."""
    with _build_client(reachable=False) as test_client:
        yield test_client
