# backend/app/schemas/base.py
"""
Base schema classes for MongoDB ↔ Pydantic integration.
"""

from datetime import datetime
from typing import Annotated, Any, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _convert_object_id(v: Any) -> str:
    """Convert an ObjectId (or string) to a plain string."""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        if ObjectId.is_valid(v):
            return v
        raise ValueError(f"Invalid ObjectId string: {v}")
    raise ValueError(f"Cannot convert {type(v).__name__} to ObjectId string")


# Reusable type for MongoDB ObjectId fields stored as strings
ObjectIdStr = Annotated[str, BeforeValidator(_convert_object_id)]


class MongoModel(BaseModel):
    """
    Base class for schemas that map to MongoDB documents.

    Provides:
    - from_mongo(): Convert raw MongoDB dict → Pydantic model
    - from_mongo_list(): Convert list of dicts → list of models
    - to_mongo(): Convert Pydantic model → MongoDB-compatible dict
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
    )

    @classmethod
    def from_mongo(cls, data: dict[str, Any]) -> Optional["MongoModel"]:
        """Convert a raw MongoDB document to a Pydantic model."""
        if data is None:
            return None
        data = dict(data)
        if "_id" in data:
            data["id"] = _convert_object_id(data.pop("_id"))
        return cls(**data)

    @classmethod
    def from_mongo_list(cls, data: list[dict[str, Any]]) -> list["MongoModel"]:
        """Convert a list of MongoDB documents to Pydantic models."""
        return [cls.from_mongo(doc) for doc in data if doc is not None]

    def to_mongo(self, exclude_none: bool = True) -> dict[str, Any]:
        """Convert this model to a MongoDB-compatible dict."""
        return self.model_dump(
            by_alias=True,
            exclude_none=exclude_none,
            exclude={"id", "document_id", "session_id", "message_id"},
        )