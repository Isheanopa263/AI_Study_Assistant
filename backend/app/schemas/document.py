# backend/app/schemas/document.py
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import MongoModel, ObjectIdStr


class DocumentBase(MongoModel):
    """Base fields shared by all document schemas."""
    title: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(..., min_length=1, max_length=20)
    file_size: int = Field(..., ge=0)
    tags: list[str] = Field(default_factory=list)


class DocumentCreate(DocumentBase):
    """Schema for creating a new document (used internally)."""
    user_id: str
    content: str = ""
    chunk_count: int = 0


class DocumentResponse(MongoModel):
    """Schema for returning a document to the API client."""
    document_id: ObjectIdStr = Field(alias="id")
    user_id: str
    title: str
    file_type: str
    file_size: int
    content: str = ""
    chunk_count: int = 0
    tags: list[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = MongoModel.model_config | {
        "populate_by_name": True,
    }

    @classmethod
    def from_mongo(cls, data: dict) -> Optional["DocumentResponse"]:
        """Override to map _id → document_id instead of _id → id."""
        if data is None:
            return None
        data = dict(data)
        if "_id" in data:
            data["document_id"] = str(data.pop("_id"))
        return cls(**data)


class DocumentListResponse(MongoModel):
    """Schema for paginated document lists."""
    documents: list[DocumentResponse]
    total: int
    page: int
    limit: int