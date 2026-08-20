"""Regression tests for the run-failure path.

A run that fails must always reach a terminal state. The failure handler is the
only thing standing between a crashed run and a session stuck on ``running``
forever, so it has to survive whatever the exception hands it.

What the resulting error *says* is covered in ``test_failure_classification``;
this file guards the weaker but more critical property — that building it can
never raise.
"""

import pytest

from app.models.workflow import WorkflowError
from app.workflow.runner import _detail_from, _error_from


class _IntCodeError(Exception):
    """Mirrors an OpenAI SDK APIStatusError, whose ``code`` is the raw body value.

    A live 401 from OpenRouter arrives as ``code == 401`` (an int), which used to
    blow up ``WorkflowError(code=...)`` inside the failure handler and strand the
    run as ``running``.
    """

    def __init__(self, message: str, code: object) -> None:
        super().__init__(message)
        self.code = code


def test_int_code_does_not_raise() -> None:
    """The original bug: an int ``code`` crashed the failure handler."""
    err = _error_from(_IntCodeError("Error code: 401 - User not found.", 401))
    assert isinstance(err, WorkflowError)
    assert isinstance(err.code, str)


@pytest.mark.parametrize(
    "code",
    [401, "cost_cap_exceeded", None, "", "   ", 503.0, True, object(), b"\xff"],
)
def test_never_raises_on_any_code(code: object) -> None:
    err = _error_from(_IntCodeError("boom", code))
    assert isinstance(err.code, str) and err.code
    assert isinstance(err.message, str) and err.message


def test_never_raises_on_hostile_code() -> None:
    """A ``code`` whose __str__ explodes must not take the failure handler down."""

    class Hostile:
        def __str__(self) -> str:
            raise ValueError("nope")

    err = _error_from(_IntCodeError("boom", Hostile()))
    assert isinstance(err.code, str) and err.code


def test_never_raises_on_hostile_message() -> None:
    """Likewise for an exception whose own __str__ explodes."""

    class HostileError(Exception):
        def __str__(self) -> str:
            raise ValueError("nope")

    err = _error_from(HostileError())
    assert isinstance(err.message, str) and err.message


def test_detail_never_raises_on_hostile_message() -> None:
    """Diagnostics are best-effort and must not break the handler either."""

    class HostileError(Exception):
        def __str__(self) -> str:
            raise ValueError("nope")

    assert _detail_from(HostileError()) == "HostileError"


def test_code_is_never_taken_from_the_exception() -> None:
    """Codes are our stable slugs, not whatever the provider happened to send."""
    err = _error_from(_IntCodeError("boom", "provider_specific_nonsense"))
    assert err.code != "provider_specific_nonsense"
