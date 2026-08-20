"""Tests for the OpenRouter credential probe.

The probe authenticates on purpose: an unauthenticated reachability check reports
``ok`` for a revoked key, which is how a dead key once went unnoticed while every
workflow run failed on a 401.
"""

import httpx
import pytest

from app.api import openrouter_health
from app.config import Settings


@pytest.fixture(autouse=True)
def _clear_cache():
    openrouter_health._cache.update({"ts": 0.0, "status": "unknown"})
    yield
    openrouter_health._cache.update({"ts": 0.0, "status": "unknown"})


def _settings(**kw) -> Settings:
    return Settings(env="prod", openrouter_api_key="sk-or-v1-test", **kw)


def _patch_response(monkeypatch, *, status_code=None, exc=None):
    """Stand in for httpx.AsyncClient.get, capturing the request headers."""
    seen: dict = {}

    async def fake_get(self, url, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs.get("headers") or {}
        if exc is not None:
            raise exc
        return httpx.Response(status_code, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return seen


async def test_valid_key_is_ok(monkeypatch) -> None:
    seen = _patch_response(monkeypatch, status_code=200)
    assert await openrouter_health.check_openrouter(_settings()) == "ok"
    # The whole point: the probe must send the credential.
    assert seen["headers"]["Authorization"] == "Bearer sk-or-v1-test"
    assert seen["url"].endswith("/key")


@pytest.mark.parametrize("code", [401, 403])
async def test_rejected_key_is_unauthorized(monkeypatch, code: int) -> None:
    """The regression: a dead key must not read as healthy."""
    _patch_response(monkeypatch, status_code=code)
    assert await openrouter_health.check_openrouter(_settings()) == "unauthorized"


async def test_server_error_is_down(monkeypatch) -> None:
    _patch_response(monkeypatch, status_code=503)
    assert await openrouter_health.check_openrouter(_settings()) == "down"


async def test_transport_error_is_down(monkeypatch) -> None:
    _patch_response(monkeypatch, exc=httpx.ConnectError("no route"))
    assert await openrouter_health.check_openrouter(_settings()) == "down"


async def test_no_key_is_unknown(monkeypatch) -> None:
    _patch_response(monkeypatch, status_code=200)
    settings = Settings(env="prod", openrouter_api_key=None)
    assert await openrouter_health.check_openrouter(settings) == "unknown"


async def test_test_env_never_calls_out(monkeypatch) -> None:
    async def boom(self, url, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("probe must not make a network call under tests")

    monkeypatch.setattr(httpx.AsyncClient, "get", boom)
    settings = Settings(env="test", openrouter_api_key="sk-or-v1-test")
    assert await openrouter_health.check_openrouter(settings) == "unknown"


async def test_result_is_cached(monkeypatch) -> None:
    calls = {"n": 0}

    async def counting_get(self, url, **kwargs):
        calls["n"] += 1
        return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", counting_get)
    s = _settings()
    assert await openrouter_health.check_openrouter(s) == "unauthorized"
    assert await openrouter_health.check_openrouter(s) == "unauthorized"
    assert calls["n"] == 1, "second call within the TTL should hit the cache"
