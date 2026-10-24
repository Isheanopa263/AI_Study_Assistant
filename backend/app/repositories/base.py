# app/repositories/base.py
"""
Base repository with shared MongoDB helpers.

All repositories inherit from this to get:
  - A reference to the MongoDB collection
  - ObjectId ↔ string conversion helpers
"""

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseRepository:
    """Base class for all MongoDB repositories."""

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection = db[collection_name]

    @staticmethod
    def _to_str_id(document: dict, id_field: str = "id") -> dict | None:
        """
        Convert MongoDB _id (ObjectId) to a named string field.

        Examples:
            _to_str_id(doc, "document_id")  → {"document_id": "abc123", ...}
            _to_str_id(doc, "session_id")   → {"session_id": "abc123", ...}
            _to_str_id(doc, "message_id")   → {"message_id": "abc123", ...}
        """
        if document is None:
            return None
        document[id_field] = str(document.pop("_id"))
        return document

    @staticmethod
    def _to_object_id(id_string: str) -> ObjectId:
        """Convert a string ID to ObjectId. Raises ValueError if invalid."""
        if not ObjectId.is_valid(id_string):
            raise ValueError(f"Invalid ObjectId: {id_string}")
        return ObjectId(id_string)