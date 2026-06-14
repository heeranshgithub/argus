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
