"""Domain exceptions, mapped to the standard error contract in ``api.errors``."""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, handled application errors."""


class SessionNotFound(AppError):
    """Raised when a session id resolves to no document."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id!r} was not found.")


class InvalidObjectId(AppError):
    """Raised when a path id is not a valid Mongo ``ObjectId``."""

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f"{value!r} is not a valid id.")


class SessionAlreadyRunning(AppError):
    """Raised when a workflow run is requested for an already-running session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id!r} already has a run in progress.")


class SessionNotResumable(AppError):
    """Raised when resume is requested for a session that is not ``failed``."""

    def __init__(self, session_id: str, status: str) -> None:
        self.session_id = session_id
        self.status = status
        super().__init__(
            f"Session {session_id!r} is {status!r}; only failed sessions can resume."
        )


class RunNotFound(AppError):
    """Raised when a run id resolves to no document for the session."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run {run_id!r} was not found.")


class ReportNotFound(AppError):
    """Raised when a session has no generated report yet."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"No report exists for session {session_id!r}.")


class WorkflowUnavailable(AppError):
    """Raised when the workflow engine cannot be constructed (e.g., no API key)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Workflow engine unavailable: {reason}")
