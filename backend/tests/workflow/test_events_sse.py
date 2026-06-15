"""SSE streaming tests: since_seq backfill, headers, multi-subscriber, overflow.

The happy-path end-to-end stream is covered in ``test_runs_api.py``; this module
focuses on Part 4's reconnect keystone (``since_seq``), the proxy-friendly
headers, and the :class:`EventBus` fan-out / overflow behaviour in isolation.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.api.dependencies import get_workflow_deps
from app.config import Settings
from app.db.mongo import MongoManager
from app.main import create_app
from app.workflow.deps import WorkflowDeps
from app.workflow.events import EventBus, WorkflowEvent
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
async def api() -> AsyncIterator[AsyncClient]:
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
        yield client


SESSION_PAYLOAD = {
    "companyName": "Acme Corp",
    "website": "https://acme.example.com",
    "objective": "Explore an expansion partnership before the call.",
}


async def _run_to_completion(client: AsyncClient) -> tuple[str, str]:
    """Create a session, run it to completion, return (session_id, run_id)."""
    created = await client.post("/api/sessions", json=SESSION_PAYLOAD)
    session_id = created.json()["id"]
    run_id = (await client.post(f"/api/sessions/{session_id}/run")).json()["runId"]
    for _ in range(50):
        body = (await client.get(f"/api/sessions/{session_id}/runs/{run_id}")).json()
        if body["status"] != "running":
            break
    else:  # pragma: no cover - safety net
        raise AssertionError("run did not finish in time")
    return session_id, run_id


def _parse_frames(text: str) -> list[tuple[int, str]]:
    """Parse an SSE response body into ``(seq, kind)`` tuples in order."""
    frames: list[tuple[int, str]] = []
    for block in text.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue  # keep-alive comment
        seq: int | None = None
        kind: str | None = None
        for line in block.splitlines():
            if line.startswith("id:"):
                seq = int(line[3:].strip())
            elif line.startswith("event:"):
                kind = line[6:].strip()
        if seq is not None and kind is not None:
            frames.append((seq, kind))
    return frames


async def test_sse_sets_proxy_friendly_headers(api: AsyncClient) -> None:
    session_id, run_id = await _run_to_completion(api)
    resp = await api.get(f"/api/sessions/{session_id}/runs/{run_id}/events")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"


async def test_sse_backfill_replays_everything_and_closes(api: AsyncClient) -> None:
    """Subscribing after completion replays the full timeline and closes."""
    session_id, run_id = await _run_to_completion(api)
    resp = await api.get(f"/api/sessions/{session_id}/runs/{run_id}/events")
    frames = _parse_frames(resp.text)

    assert frames[0][1] == "run_started"
    assert frames[-1][1] == "run_completed"
    # seq is monotonic and gap-free across the replay.
    seqs = [seq for seq, _ in frames]
    assert seqs == sorted(seqs)
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))


async def test_sse_since_seq_skips_already_seen_events(api: AsyncClient) -> None:
    """``since_seq=N`` replays only events with seq > N (backfill correctness)."""
    session_id, run_id = await _run_to_completion(api)
    full = _parse_frames(
        (await api.get(f"/api/sessions/{session_id}/runs/{run_id}/events")).text
    )
    cutoff = full[len(full) // 2][0]

    resp = await api.get(
        f"/api/sessions/{session_id}/runs/{run_id}/events",
        params={"since_seq": cutoff},
    )
    frames = _parse_frames(resp.text)
    assert frames, "expected the tail of the timeline"
    assert all(seq > cutoff for seq, _ in frames)
    assert frames[-1][1] == "run_completed"


async def test_sse_since_seq_past_terminal_yields_no_frames(api: AsyncClient) -> None:
    """A client fully caught up gets an immediate, empty close — no hang."""
    session_id, run_id = await _run_to_completion(api)
    full = _parse_frames(
        (await api.get(f"/api/sessions/{session_id}/runs/{run_id}/events")).text
    )
    last_seq = full[-1][0]

    resp = await api.get(
        f"/api/sessions/{session_id}/runs/{run_id}/events",
        params={"since_seq": last_seq},
    )
    assert resp.status_code == 200
    assert _parse_frames(resp.text) == []


async def test_sse_unknown_run_returns_404(api: AsyncClient) -> None:
    created = await api.post("/api/sessions", json=SESSION_PAYLOAD)
    session_id = created.json()["id"]
    resp = await api.get(f"/api/sessions/{session_id}/runs/{'0' * 24}/events")
    assert resp.status_code == 404


# --- EventBus unit tests -------------------------------------------------------


def _event(seq: int, *, session_id: str = "s1", kind: str = "node_output") -> WorkflowEvent:
    return {
        "run_id": "r1",
        "session_id": session_id,
        "node": "researcher",
        "kind": kind,
        "payload": {},
        "ts": None,  # type: ignore[typeddict-item]  # not serialized in this test
        "seq": seq,
    }


async def test_event_bus_fans_out_to_multiple_subscribers() -> None:
    bus = EventBus()
    q1 = bus.subscribe("s1")
    q2 = bus.subscribe("s1")
    assert bus.subscriber_count("s1") == 2

    for seq in (1, 2, 3):
        bus.publish("s1", _event(seq))

    assert [q1.get_nowait()["seq"] for _ in range(3)] == [1, 2, 3]
    assert [q2.get_nowait()["seq"] for _ in range(3)] == [1, 2, 3]

    bus.unsubscribe("s1", q1)
    bus.unsubscribe("s1", q2)
    assert bus.subscriber_count("s1") == 0


async def test_event_bus_drops_oldest_on_overflow() -> None:
    """Flooding a slow consumer drops the oldest, counts it, and never raises."""
    bus = EventBus(max_queue=4)
    queue = bus.subscribe("s1")

    for seq in range(1, 1001):  # far beyond capacity; consumer never drains
        bus.publish("s1", _event(seq))

    assert bus.dropped_events == 1000 - 4
    drained = [queue.get_nowait()["seq"] for _ in range(queue.qsize())]
    assert len(drained) == 4
    # Drop-oldest means the survivors are the most recent four, in order.
    assert drained == [997, 998, 999, 1000]
    assert drained == sorted(drained)
