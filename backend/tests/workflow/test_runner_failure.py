"""Regression tests for the run-failure path.

A run that fails must always reach a terminal state. The failure handler is the
only thing standing between a crashed run and a session stuck on ``running``
forever, so it has to survive whatever the exception hands it.
"""

import pytest

from app.models.workflow import WorkflowError
from app.workflow.runner import _error_from


class _IntCodeError(Exception):
    """Mirrors an OpenAI SDK APIStatusError, whose ``code`` is the raw body value.

    A live 401 from OpenRouter arrives as ``code == 401`` (an int), which used to
    blow up ``WorkflowError(code=...)`` inside the failure handler and strand the
    run as ``running``.
    """

    def __init__(self, message: str, code: object) -> None:
        super().__init__(message)
        self.code = code


def test_int_code_is_coerced_not_raised() -> None:
    err = _error_from(_IntCodeError("Error code: 401 - User not found.", 401))
    assert isinstance(err, WorkflowError)
    assert err.code == "401"
    assert "User not found" in err.message


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (401, "401"),
        ("cost_cap_exceeded", "cost_cap_exceeded"),
        (None, "_IntCodeError"),  # absent -> class name
        ("", "_IntCodeError"),  # empty -> class name
        ("   ", "_IntCodeError"),  # whitespace-only -> class name
        (503.0, "503.0"),
        (True, "True"),
    ],
)
def test_code_coercion_matrix(code: object, expected: str) -> None:
    assert _error_from(_IntCodeError("boom", code)).code == expected


def test_plain_exception_uses_class_name() -> None:
    err = _error_from(RuntimeError("something broke"))
    assert err.code == "RuntimeError"
    assert err.message == "something broke"


def test_empty_message_falls_back_to_class_name() -> None:
    # str(exc) is "" for a bare raise; the UI needs *something* to render.
    assert _error_from(RuntimeError()).message == "RuntimeError"


def test_error_from_never_raises_on_hostile_code() -> None:
    """A ``code`` whose __str__ explodes must not take the failure handler down."""

    class Hostile:
        def __str__(self) -> str:
            raise ValueError("nope")

    err = _error_from(_IntCodeError("boom", Hostile()))
    assert err.code == "_IntCodeError"  # unusable code -> class name
    assert err.message == "boom"


def test_error_from_never_raises_on_hostile_message() -> None:
    """Likewise for an exception whose own __str__ explodes."""

    class HostileError(Exception):
        def __str__(self) -> str:
            raise ValueError("nope")

    err = _error_from(HostileError())
    assert err.code == "HostileError"
    assert err.message == "HostileError"
