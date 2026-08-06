from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """
    Schema for returning an uploaded document's metadata.

    Full document processing will be implemented in Phase 6.
    """

    document_id: str = Field(
        ...,
        description="Unique identifier for the document.",
    )
    filename: str = Field(
        ...,
        description="Original filename of the uploaded document.",
    )
    file_type: str = Field(
        ...,
        description="Type of document. Supported: pdf, docx, txt.",
    )
    size_bytes: int = Field(
        ...,
        description="File size in bytes.",
    )
    uploaded_at: datetime = Field(
        ...,
        description="Timestamp when the document was uploaded.",
    )