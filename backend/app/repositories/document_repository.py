# app/repositories/document_repository.py
"""
Document repository backed by MongoDB.

Manages the 'documents' collection.
Replaces the Phase 2 in-memory dict storage.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    """MongoDB-backed repository for document metadata."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collection_name="documents")

    async def create(self, document_data: dict) -> dict:
        """
        Insert a new document record.

        MongoDB auto-generates _id (ObjectId). We map it to 'document_id'
        to match the DocumentResponse schema.

        Returns the full saved document dict with document_id set.
        """
        result = await self.collection.insert_one(document_data)
        document_data["_id"] = result.inserted_id
        return self._to_str_id(document_data, id_field="document_id")

    async def get_by_id(self, document_id: str) -> dict | None:
        """Find a single document by its document_id."""
        try:
            object_id = self._to_object_id(document_id)
        except ValueError:
            return None
        document = await self.collection.find_one({"_id": object_id})
        return self._to_str_id(document, id_field="document_id")

    async def get_by_checksum(self, user_id: str, checksum: str) -> dict | None:
        """Find a document by user_id + checksum (for deduplication)."""
        document = await self.collection.find_one({
            "user_id": user_id,
            "checksum": checksum,
        })
        return self._to_str_id(document, id_field="document_id")

    async def get_by_user_id(self, user_id: str) -> list[dict]:
        """Fetch all documents belonging to a user."""
        cursor = self.collection.find({"user_id": user_id})
        documents = await cursor.to_list(length=500)
        return [
            self._to_str_id(doc, id_field="document_id") for doc in documents
        ]

    async def delete(self, document_id: str) -> bool:
        """Delete a document by ID. Returns True if deleted."""
        try:
            object_id = self._to_object_id(document_id)
        except ValueError:
            return False
        result = await self.collection.delete_one({"_id": object_id})
        return result.deleted_count > 0

    async def count(self) -> int:
        """Return the total number of documents."""
        return await self.collection.count_documents({})