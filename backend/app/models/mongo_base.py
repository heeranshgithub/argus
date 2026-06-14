"""Helpers for turning raw Mongo documents into API models.

Mongo stores the primary key as ``_id`` (an ``ObjectId``); the wire wants a
plain ``id`` string. We convert here, at the repository edge, so ``ObjectId``
never leaks into Pydantic models or onto the wire.
"""

from collections.abc import Mapping
from typing import Any

from app.models.session import SessionOut


def to_session_out(doc: Mapping[str, Any]) -> SessionOut:
    """Convert a raw ``sessions`` document into a :class:`SessionOut`."""
    data = dict(doc)
    raw_id = data.pop("_id", None)
    if raw_id is not None:
        data["id"] = str(raw_id)
    return SessionOut.model_validate(data)
