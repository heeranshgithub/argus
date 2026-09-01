"""Translate raw exceptions into failures that are safe to show a user.

Provider SDKs raise exceptions whose text is written for the developer holding
the API key, not for the person waiting on a research report. Surfacing that text
verbatim is wrong three ways: it is meaningless or actively misleading to a user
(OpenRouter answers a bad key with ``User not found``, which reads as *their*
account being gone), it discloses internal infrastructure on a public endpoint,
and it renders as a raw Python repr in the UI.

So classification happens here, once, at the boundary. Everything the client sees
comes from :func:`classify`; the original exception text and traceback go to the
logs, which is where operators should be looking anyway.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.workflow.events import CostCapExceeded

#: Fallback for anything unrecognised. Deliberately vague — an unclassified
#: error is one we have not reasoned about, so it must not promise a cause.
GENERIC_CODE = "workflow_failed"
GENERIC_MESSAGE = (
    "Something went wrong while researching this company. "
    "You can start the run again."
)


@dataclass(frozen=True)
class Failure:
    """A user-facing failure.

    ``code`` is a stable slug for the *frontend*, not for display — it decides
    which actions to offer. ``retryable`` says whether running the same thing
    again could plausibly succeed, so the UI can avoid offering a Resume button
    that is guaranteed to fail.
    """

    code: str
    message: str
    retryable: bool


def _status_code(exc: Exception) -> int | None:
    """Best-effort HTTP status for an exception, across SDK shapes.

    The OpenAI SDK puts it on ``.status_code``; httpx raises
    ``HTTPStatusError`` carrying ``.response.status_code``. Duck-typing both
    avoids importing provider internals that shift between versions.
    """
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def classify(exc: Exception) -> Failure:
    """Map ``exc`` to a :class:`Failure` safe to serialize to a browser."""
    if isinstance(exc, CostCapExceeded):
        return Failure(
            code="cost_cap_exceeded",
            message=(
                "This run reached its spending limit before it could finish. "
                "Raise the limit or try a narrower objective."
            ),
            # Resuming would immediately re-trip the same cap.
            retryable=False,
        )

    status = _status_code(exc)
    if status in (401, 403):
        return Failure(
            code="llm_auth_failed",
            message=(
                "We couldn't authenticate with the research service. "
                "This is a configuration problem on our side, and retrying "
                "won't help until it's fixed."
            ),
            retryable=False,
        )
    if status == 429:
        return Failure(
            code="llm_rate_limited",
            message=(
                "The research service is rate-limiting us right now. "
                "Wait a few minutes and run it again."
            ),
            retryable=True,
        )
    if status is not None and status >= 500:
        return Failure(
            code="llm_unavailable",
            message=(
                "The research service is temporarily unavailable. "
                "This usually clears up on its own, so try again shortly."
            ),
            retryable=True,
        )

    # Transport-level trouble: no HTTP status because no response arrived.
    name = type(exc).__name__
    if isinstance(exc, TimeoutError) or "Timeout" in name:
        return Failure(
            code="llm_timeout",
            message=(
                "The research service took too long to respond. "
                "Try running it again."
            ),
            retryable=True,
        )
    if isinstance(exc, ConnectionError) or "Connect" in name:
        return Failure(
            code="network_error",
            message=(
                "We couldn't reach the research service. "
                "Check back in a few minutes."
            ),
            retryable=True,
        )

    return Failure(code=GENERIC_CODE, message=GENERIC_MESSAGE, retryable=True)
