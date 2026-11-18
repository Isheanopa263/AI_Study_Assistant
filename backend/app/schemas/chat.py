"""
Pydantic Schemas for Chat Operations.
Includes session creation, message schemas, and summary models.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")


class MessageCreate(BaseModel):
    """Payload for creating a new user message."""
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The message text from the user",
        examples=["Explain quantum entanglement in simple terms."]
    )


class MessageResponse(BaseModel):
    """Response model for a single chat message."""
    message_id: str = Field(..., description="Unique message string ID")
    session_id: str = Field(..., description="Parent session ID")
    user_id: str = Field(..., description="Owner user ID")
    role: str = Field(..., description="Message author role (user/assistant/system)")
    content: str = Field(..., description="Text content of the message")
    tokens_used: Optional[int] = Field(default=0, description="Token count consumed")
    created_at: datetime = Field(..., description="ISO creation timestamp")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ChatSessionCreate(BaseModel):
    """Payload for creating a new chat session."""
    title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional title for the study session"
    )


class ChatSessionResponse(BaseModel):
    """Response model representing a chat session."""
    session_id: str = Field(..., description="Unique chat session ID")
    user_id: str = Field(..., description="Owner user ID")
    title: Optional[str] = Field(default="New Study Session", description="Session title")
    summary: Optional[str] = Field(default=None, description="Condensed conversation memory summary")
    message_count: int = Field(default=0, description="Total messages in session")
    created_at: datetime = Field(..., description="ISO creation timestamp")
    updated_at: datetime = Field(..., description="ISO last updated timestamp")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SummaryResponse(BaseModel):
    """Response returned after manually triggering a session summary."""
    session_id: str = Field(..., description="Target session ID")
    summary: str = Field(..., description="Generated conversation summary")
    messages_summarized: int = Field(..., description="Count of historical messages processed")
    created_at: datetime = Field(default_factory=datetime.utcnow)