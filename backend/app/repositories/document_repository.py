import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentRepository:
    """
    Repository for document metadata persistence.

    Abstracts all database operations for documents.
    In Phase 3, this class will execute asynchronous queries against MongoDB.
    Currently uses in-memory storage that resets when the server restarts.
    """

    def __init__(self):
        # In-memory storage: { document_id: document_dict }
        self._storage: Dict[str, dict] = {}

    async def create(self, document_data: dict) -> dict:
        """
        Store a new document metadata record.

        Args:
            document_data: Dictionary containing validated document attributes.

        Returns:
            The saved document record.
        """
        doc_id = document_data["document_id"]
        self._storage[doc_id] = document_data
        logger.debug("Document saved to repository. document_id=%s", doc_id)
        return document_data

    async def get_by_id(self, document_id: str) -> Optional[dict]:
        """Retrieve a document record by its unique ID."""
        return self._storage.get(document_id)

    async def get_by_user_id(self, user_id: str) -> List[dict]:
        """Retrieve all documents belonging to a specific user."""
        return [
            doc for doc in self._storage.values()
            if doc.get("user_id") == user_id
        ]

    async def get_by_checksum(
        self,
        user_id: str,
        checksum: str,
    ) -> Optional[dict]:
        """
        Retrieve a document by its checksum for a specific user.
        Used to detect duplicate uploads.
        """
        for doc in self._storage.values():
            if doc.get("user_id") == user_id and doc.get("checksum") == checksum:
                return doc
        return None

    async def delete(self, document_id: str) -> bool:
        """
        Delete a document record by ID.

        Returns True if deleted, False if not found.
        """
        if document_id in self._storage:
            del self._storage[document_id]
            logger.debug("Document deleted from repository. document_id=%s", document_id)
            return True
        return False


# Global singleton instance for the application
document_repository = DocumentRepository()