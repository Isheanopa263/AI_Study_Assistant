from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# ------------------------------------------------------------------------------
# PAGINATION SCHEMA
# ------------------------------------------------------------------------------

class PaginationParams(BaseModel):
    """
    represent extracted and validated pagination parameters
    
    created by the get_pagination dependency
    injected into endpoints that support pagination
    """

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
        """
        Calculates the offset for database queries based on the current page and limit.
        """
        return (self.page - 1) * self.limit
    

# ------------------------------------------------------------------------------
# MESSAGE SCHEMAS
# ------------------------------------------------------------------------------


class MessageCreate(BaseModel):
    """
    Schema for creating a new chat message.

    This model validates the request body when a student sends a message.
    FastAPI uses this to automatically validate and parse the JSON body.
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The message content from the student. Cannot be empty.",
        examples=["Explain recursion in simple English."],
    )


class MessageResponse(BaseModel):
    """
    Schema for returning a single message in API responses.

    This model shapes the response the client receives.
    It ensures sensitive internal fields are never exposed.
    """

    message_id: str = Field(
        ...,
        description="Unique identifier for this message.",
    )
    session_id: str = Field(
        ...,
        description="The chat session this message belongs to.",
    )
    role: str = Field(
        ...,
        description="Who sent the message. Either 'user' or 'assistant'.",
    )
    content: str = Field(
        ...,
        description="The message content.",
    )
    created_at: str = Field(
        ...,
        description="Timestamp when the message was created.",
    )


# ------------------------------------------------------------------------------
# CHAT SESSION SCHEMAS
# ------------------------------------------------------------------------------


class ChatSessionCreate(BaseModel):
    """
    Schema for creating a new chat session.

    A chat session represents one conversation thread.
    The title is optional and can be auto-generated from the first message later.
    """

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Optional title for the chat session.",
        examples=["Study session: Data Structures"],
    )


class ChatSessionResponse(BaseModel):
    """
    Schema for returning a chat session in API responses.
    """

    session_id: str = Field(
        ...,
        description="Unique identifier for the chat session.",
    )
    title: Optional[str] = Field(
        default=None,
        description="Title of the chat session.",
    )
    created_at: str = Field(
        ...,
        description="Timestamp when the session was created.",
    )
    message_count: int = Field(
        default=0,
        description="Total number of messages in this session.",
    )


class ChatSessionListResponse(BaseModel):
    """
    Schema for returning a paginated list of chat sessions.

    Wraps a list of sessions with pagination metadata.
    This is a professional pattern called an envelope response.
    """

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
    """
    Schema for returning a paginated list of messages in a session.
    """

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
    """
    Schema for returning a session summary.

    Will be populated by AI in Phase 7.
    """

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