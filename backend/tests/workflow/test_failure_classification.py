"""Tests for exception -> user-facing failure classification.

The contract under test is as much about what is *absent* as what is present:
nothing derived from a provider's error text may reach the client.
"""

import httpx
import pytest

from app.models.workflow import WorkflowError
from app.workflow.events import CostCapExceeded
from app.workflow.failure import GENERIC_CODE, classify
from app.workflow.runner import _detail_from, _error_from


class _SdkError(Exception):
    """Mimics an OpenAI SDK APIStatusError (``.status_code`` on the exception)."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


# The exact string OpenRouter returns for a revoked key. It reads as though the
# *user's* account is missing, which is why it must never be shown.
OPENROUTER_401 = "Error code: 401 - {'error': {'message': 'User not found.', 'code': 401}}"


def test_auth_failure_is_classified_and_not_retryable() -> None:
    f = classify(_SdkError(OPENROUTER_401, 401))
    assert f.code == "llm_auth_failed"
    assert f.retryable is False


def test_auth_failure_message_leaks_nothing() -> None:
    """The regression this whole change exists for."""
    msg = classify(_SdkError(OPENROUTER_401, 401)).message
    for leak in ("User not found", "401", "{", "}", "'error'", "openrouter", "OpenRouter"):
        assert leak not in msg, f"{leak!r} leaked into the user-facing message"


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "llm_auth_failed", False),
        (403, "llm_auth_failed", False),
        (429, "llm_rate_limited", True),
        (500, "llm_unavailable", True),
        (503, "llm_unavailable", True),
    ],
)
def test_status_code_matrix(status: int, code: str, retryable: bool) -> None:
    f = classify(_SdkError("boom", status))
    assert (f.code, f.retryable) == (code, retryable)


def test_status_read_from_httpx_response_shape() -> None:
    """httpx puts the status on .response, not on the exception."""
    request = httpx.Request("POST", "https://example.test/v1/chat")
    exc = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=request,
        response=httpx.Response(429, request=request),
    )
    assert classify(exc).code == "llm_rate_limited"


def test_cost_cap_is_not_retryable() -> None:
    f = classify(CostCapExceeded(1.5, 1.0))
    assert f.code == "cost_cap_exceeded"
    assert f.retryable is False


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (TimeoutError("timed out"), "llm_timeout"),
        (ConnectionError("refused"), "network_error"),
        (httpx.ConnectTimeout("slow"), "llm_timeout"),
    ],
)
def test_transport_errors(exc: Exception, code: str) -> None:
    assert classify(exc).code == code


def test_unknown_exception_falls_back_without_promising_a_cause() -> None:
    secret = "postgres://admin:hunter2@10.0.0.5/db blew up"
    f = classify(RuntimeError(secret))
    assert f.code == GENERIC_CODE
    assert "hunter2" not in f.message
    assert "10.0.0.5" not in f.message


def test_wire_model_has_no_traceback_field() -> None:
    """``traceback`` must not be serializable to the client."""
    assert "traceback" not in WorkflowError.model_fields
    dumped = _error_from(_SdkError(OPENROUTER_401, 401)).model_dump()
    assert set(dumped) == {"code", "message", "retryable"}


def test_legacy_traceback_key_is_dropped_when_read() -> None:
    """Old records carry ``traceback``; reading one must not resurrect it."""
    legacy = {"code": "401", "message": OPENROUTER_401, "traceback": "File ...\n  raise"}
    err = WorkflowError.model_validate(legacy)
    assert "traceback" not in err.model_dump()


def test_detail_keeps_raw_text_for_operators() -> None:
    """The raw text still has to exist — just not on the wire."""
    detail = _detail_from(_SdkError(OPENROUTER_401, 401))
    assert "User not found" in detail
    assert "_SdkError" in detail
