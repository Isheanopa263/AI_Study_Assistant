from typing import List
from pydantic import BaseModel, Field, computed_field

from app.utils.file_helpers import format_file_size


class DocumentBase(BaseModel):
    """Base schema containing shared document properties."""

    filename: str = Field(
        ...,
        description="Sanitized original filename of the document.",
        examples=["Computer_Architecture_Notes.pdf"],
    )
    file_type: str = Field(
        ...,
        description="Extension/type of the document (pdf, docx, txt).",
        examples=["pdf"],
    )
    size_bytes: int = Field(
        ...,
        description="Size of the document in bytes.",
        examples=[2048576],
    )


class DocumentResponse(DocumentBase):
    """Response schema returned to the client upon upload or retrieval."""

    document_id: str = Field(
        ...,
        description="Unique identifier for the document.",
        examples=["doc_9a8b7c6d5e"],
    )
    user_id: str = Field(
        ...,
        description="The ID of the user who owns this document.",
        examples=["stub-user-id"],
    )
    checksum: str = Field(
        ...,
        description="SHA-256 hash of the file content for deduplication and integrity.",
    )
    uploaded_at: str = Field(
        ...,
        description="ISO 8601 formatted timestamp of upload.",
        examples=["2025-01-15T10:00:00+00:00"],
    )

    @computed_field
    @property
    def human_size(self) -> str:
        """Calculates formatted human-readable size (e.g., '2.00 MB')."""
        return format_file_size(self.size_bytes)


class DocumentListResponse(BaseModel):
    """Envelope response schema for paginated document lists."""

    documents: List[DocumentResponse] = Field(
        default=[],
        description="List of document metadata items.",
    )
    total: int = Field(
        default=0,
        description="Total number of documents owned by the user.",
    )