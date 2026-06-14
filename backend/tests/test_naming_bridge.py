"""Tests proving the camelCase ↔ snake_case naming bridge end to end."""

from fastapi.testclient import TestClient

from app.models.health import EchoRequest


def test_echo_roundtrips_camelcase(client: TestClient) -> None:
    """camelCase in → camelCase out, with no snake_case leaking onto the wire."""
    resp = client.post("/api/_echo", json={"fullName": "Ada Lovelace", "retryCount": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"fullName": "Ada Lovelace", "retryCount": 3}
    # The internal snake_case keys must never appear on the wire.
    assert "full_name" not in body
    assert "retry_count" not in body


def test_model_exposes_snake_case_internally() -> None:
    """The handler sees snake_case attributes even when given camelCase input."""
    model = EchoRequest.model_validate({"fullName": "Grace Hopper", "retryCount": 7})
    assert model.full_name == "Grace Hopper"
    assert model.retry_count == 7
    # And serializes back to camelCase for the wire.
    assert model.model_dump(by_alias=True) == {"fullName": "Grace Hopper", "retryCount": 7}


def test_validation_error_uses_error_envelope(client: TestClient) -> None:
    """A bad payload returns the standard camelCase error envelope."""
    resp = client.post("/api/_echo", json={"fullName": "x", "retryCount": "not-an-int"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert "message" in body["error"]
    assert "details" in body["error"]
