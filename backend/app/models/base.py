"""Base models implementing the camelCase (wire) ↔ snake_case (internal) bridge."""

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base for every request/response model.

    Internal Python attributes stay snake_case; the JSON wire format is camelCase.
    `populate_by_name=True` means handlers can construct models with snake_case
    keyword arguments while still accepting camelCase input from the network.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


def _stringify_object_id(value: Any) -> Any:
    """Coerce a Mongo ``ObjectId`` (or anything) to ``str`` for the wire."""
    if value is None:
        return value
    return str(value)


# A Mongo `_id` exposed as a camelCase `id` string on the wire.
MongoId = Annotated[str, BeforeValidator(_stringify_object_id)]


class MongoModel(ApiModel):
    """Base for documents persisted in Mongo.

    Mongo stores the primary key as ``_id``; we surface it as ``id`` on the wire.
    Used from Part 2 onward; declared here so the bridge has a single home.
    """

    id: MongoId | None = Field(default=None, alias="_id")
