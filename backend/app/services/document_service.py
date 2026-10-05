import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import UploadFile

from app.core.exceptions import DocumentProcessingException, NotFoundException
from app.repositories.document_repository import DocumentRepository, document_repository
from app.utils.file_helpers import get_file_extension, sanitize_filename

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
CHUNK_SIZE = 64 * 1024  # 64 KB chunks


class DocumentService:
    """Service layer for document processing and business rules."""

    def __init__(self, repo: DocumentRepository = document_repository):
        self.repo = repo

    async def process_and_save_upload(
        self,
        file: UploadFile,
        user_id: str,
    ) -> dict:
        """Validate, stream, hash, and store uploaded document metadata."""
        if not file.filename:
            raise DocumentProcessingException("No filename provided.")

        clean_filename = sanitize_filename(file.filename)
        extension = get_file_extension(clean_filename)

        # 1. Validate Extension
        if extension not in ALLOWED_EXTENSIONS:
            logger.warning(
                "Rejected file extension. filename=%s ext=%s",
                clean_filename,
                extension,
            )
            raise DocumentProcessingException(
                message=f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                detail={"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
            )

        # 2. Validate MIME Type
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            logger.warning(
                "Rejected MIME type. filename=%s mime=%s",
                clean_filename,
                content_type,
            )
            raise DocumentProcessingException(
                message=f"Invalid MIME type '{content_type}'.",
                detail={"allowed_mime_types": sorted(ALLOWED_MIME_TYPES)},
            )

        # 3. Stream File, Enforce Size & Compute SHA-256
        total_size = 0
        hasher = hashlib.sha256()

        try:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    logger.warning(
                        "File exceeded size limit. filename=%s size=%s",
                        clean_filename,
                        total_size,
                    )
                    raise DocumentProcessingException(
                        message=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
                        detail={"max_bytes": MAX_FILE_SIZE_BYTES, "received_bytes": total_size},
                    )

                hasher.update(chunk)
        finally:
            await file.close()

        if total_size == 0:
            raise DocumentProcessingException("Uploaded file is empty (0 bytes).")

        checksum = hasher.hexdigest()

        # ------------------------------------------------------------------
        # CHALLENGE SOLUTION: Duplicate Detection
        # ------------------------------------------------------------------
        existing_doc = await self.repo.get_by_checksum(user_id=user_id, checksum=checksum)
        if existing_doc:
            logger.info(
                "Duplicate document upload detected. user_id=%s doc_id=%s checksum=%s",
                user_id,
                existing_doc["document_id"],
                checksum,
            )
            return existing_doc

        # 4. Create Document Record
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        document_data = {
            "document_id": doc_id,
            "user_id": user_id,
            "filename": clean_filename,
            "file_type": extension.lstrip("."),
            "size_bytes": total_size,
            "checksum": checksum,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        saved_doc = await self.repo.create(document_data)
        logger.info(
            "Document uploaded successfully. doc_id=%s user_id=%s size=%s",
            doc_id,
            user_id,
            total_size,
        )

        return saved_doc

    async def get_document_by_id(self, document_id: str, user_id: str) -> dict:
        """Retrieve a specific document verifying user ownership."""
        doc = await self.repo.get_by_id(document_id)
        if not doc or doc.get("user_id") != user_id:
            raise NotFoundException(resource="Document", resource_id=document_id)
        return doc

    async def list_user_documents(self, user_id: str) -> List[dict]:
        """Fetch all documents belonging to a user."""
        return await self.repo.get_by_user_id(user_id)

    async def delete_document(self, document_id: str, user_id: str) -> None:
        """Delete a document verifying ownership."""
        # Verifies ownership via get_document_by_id first
        await self.get_document_by_id(document_id, user_id)
        await self.repo.delete(document_id)
        logger.info("Document deleted. doc_id=%s user_id=%s", document_id, user_id)


document_service = DocumentService()