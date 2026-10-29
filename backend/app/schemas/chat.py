from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field
from app.schemas.base import MongoModel, ObjectIdStr

# ------------------------------------------------------------------------------
# PAGINATION SCHEMA
# ------------------------------------------------------------------------------

class PaginationParams(BaseModel):
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of items to return per page.",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number starting from 1.",
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


# ------------------------------------------------------------------------------
# MESSAGE SCHEMAS
# ------------------------------------------------------------------------------


class MessageCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The message content from the student. Cannot be empty.",
        examples=["Explain recursion in simple English."],
    )


class MessageResponse(MongoModel):
    message_id: ObjectIdStr = Field(alias="id")
    content: str
    role: str = "user"
    created_at: datetime

    @classmethod
    def from_mongo(cls, data: dict) -> Optional["MessageResponse"]:
        if data is None:
            return None
        data = dict(data)
        if "_id" in data:
            data["message_id"] = str(data.pop("_id"))
        return cls(**data)


# ------------------------------------------------------------------------------
# CHAT SESSION SCHEMAS
# ------------------------------------------------------------------------------


class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Optional title for the chat session.",
        examples=["Study session: Data Structures"],
    )


class ChatSessionResponse(MongoModel):
    session_id: ObjectIdStr = Field(alias="id")
    user_id: str
    title: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    @classmethod
    def from_mongo(cls, data: dict) -> Optional["ChatSessionResponse"]:
        if data is None:
            return None
        data = dict(data)
        if "_id" in data:
            data["session_id"] = str(data.pop("_id"))
        return cls(**data)


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse] = Field(
        default=[],
        description="List of chat sessions for the current page.",
    )
    total: int = Field(
        default=0,
        description="Total number of sessions across all pages.",
    )
    page: int = Field(
        default=1,
        description="Current page number.",
    )
    limit: int = Field(
        default=10,
        description="Number of sessions per page.",
    )


# ------------------------------------------------------------------------------
# MESSAGE LIST SCHEMA
# ------------------------------------------------------------------------------


class MessageListResponse(BaseModel):
    messages: List[MessageResponse] = Field(
        default=[],
        description="List of messages for the current page.",
    )
    total: int = Field(
        default=0,
        description="Total number of messages in this session.",
    )
    session_id: str = Field(
        ...,
        description="The session these messages belong to.",
    )


# ------------------------------------------------------------------------------
# SUMMARY SCHEMA
# ------------------------------------------------------------------------------


class SessionSummaryResponse(BaseModel):
    session_id: str = Field(
        ...,
        description="The session being summarized.",
    )
    summary_format: str = Field(
        ...,
        description="The requested format: brief or detailed.",
    )
    summary: str = Field(
        ...,
        description="The generated summary content.",
    )
    message_count: int = Field(
        default=0,
        description="Number of messages included in the summary.",
    )