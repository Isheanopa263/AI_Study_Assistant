# backend/app/repositories/base.py
from bson import ObjectId
from bson.errors import InvalidId

from app.core.exceptions import ValidationException


class BaseRepository:
    """Base class for all MongoDB repositories."""

    def __init__(self, db, collection_name: str):
        self.db = db
        self.collection = db[collection_name]

    @staticmethod
    def _to_object_id(id_string: str) -> ObjectId:
        """
        Safely convert a string to an ObjectId.

        Raises:
            ValidationException: If the string is not a valid 24-char hex ObjectId.
        """
        if not id_string or not isinstance(id_string, str):
            raise ValidationException(
                message="ID must be a non-empty string"
            )
        try:
            return ObjectId(id_string)
        except (InvalidId, TypeError):
            raise ValidationException(
                message=f"Invalid ID format: '{id_string}'. "
                        "Must be a 24-character hexadecimal string."
            )

    @staticmethod
    def _to_str_id(doc: dict | None, id_field: str = "id") -> dict | None:
        """
        Transform a MongoDB document for API use.

        Renames '_id' (ObjectId) to the given id_field name (string).
        Returns None if doc is None.

        Example:
            >>> doc = {"_id": ObjectId("..."), "title": "Notes"}
            >>> BaseRepository._to_str_id(doc, id_field="document_id")
            {"document_id": "664a...", "title": "Notes"}
        """
        if doc is None:
            return None
        doc[id_field] = str(doc.pop("_id"))
        return doc

    async def count(self, query: dict | None = None) -> int:
        """Count documents matching a query."""
        return await self.collection.count_documents(query or {})