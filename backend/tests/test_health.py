"""Tests for the /api/health route."""

from fastapi.testclient import TestClient

from app.logging_config import REQUEST_ID_HEADER


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "status": "ok",
        "mongo": "ok",
        "openrouter": "unknown",
        "version": body["version"],
    }
    assert body["version"]


def test_health_reports_mongo_down(client_mongo_down: TestClient) -> None:
    resp = client_mongo_down.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mongo"] == "down"


def test_request_id_header_present(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.headers.get(REQUEST_ID_HEADER)
