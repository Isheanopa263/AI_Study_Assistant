# backend/app/repositories/document_repository.py
import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.exceptions import (
    DatabaseException,
    NotFoundException,
    ValidationException,
)
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository):
    """MongoDB repository for document operations."""

    def __init__(self, db):
        super().__init__(db, "documents")

    async def create(self, data: dict) -> dict:
        """Insert a new document. Returns the full doc with 'document_id'."""
        data["created_at"] = datetime.now(timezone.utc)
        try:
            result = await self.collection.insert_one(data)
            data["_id"] = result.inserted_id
            return self._to_str_id(data, id_field="document_id")
        except DuplicateKeyError:
            raise ValidationException(
                message=f"A document with title '{data.get('title')}' "
                        "already exists for this user"
            )
        except PyMongoError as e:
            logger.error(f"Failed to create document: {e}")
            raise DatabaseException(
                message="Failed to save document to database"
            ) from e

    async def get_by_id(self, document_id: str, user_id: str) -> Optional[dict]:
        """Find a document by ID and user. Returns doc with 'document_id'."""
        oid = self._to_object_id(document_id)

        try:
            doc = await self.collection.find_one({
                "_id": oid,
                "user_id": user_id,
            })
        except PyMongoError as e:
            logger.error(f"Failed to fetch document {document_id}: {e}")
            raise DatabaseException(
                message="Failed to retrieve document from database"
            ) from e

        if doc is None:
            raise NotFoundException(
                resource="Document",
                resource_id=document_id,
            )

        return self._to_str_id(doc, id_field="document_id")

    async def get_by_checksum(
        self, user_id: str, checksum: str
    ) -> Optional[dict]:
        """Find a document by user and SHA-256 checksum (duplicate detection)."""
        try:
            doc = await self.collection.find_one({
                "user_id": user_id,
                "checksum": checksum,
            })
        except PyMongoError as e:
            logger.error(
                f"Failed to check checksum for user {user_id}: {e}"
            )
            raise DatabaseException(
                message="Failed to check for duplicate document"
            ) from e

        if doc is None:
            return None
        return self._to_str_id(doc, id_field="document_id")

    async def list_by_user(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """List documents for a user. Returns (docs_with_document_id, total_count)."""
        query = {"user_id": user_id}
        try:
            total = await self.collection.count_documents(query)
            cursor = (
                self.collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            docs = await cursor.to_list(length=limit)
            return (
                [self._to_str_id(doc, id_field="document_id") for doc in docs],
                total,
            )
        except PyMongoError as e:
            logger.error(
                f"Failed to list documents for user {user_id}: {e}"
            )
            raise DatabaseException(
                message="Failed to retrieve documents from database"
            ) from e

    async def delete(self, document_id: str, user_id: str) -> bool:
        """Delete a document with ownership check."""
        oid = self._to_object_id(document_id)

        try:
            result = await self.collection.delete_one({
                "_id": oid,
                "user_id": user_id,
            })
        except PyMongoError as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise DatabaseException(
                message="Failed to delete document from database"
            ) from e

        if result.deleted_count == 0:
            raise NotFoundException(
                resource="Document",
                resource_id=document_id,
            )

        return True