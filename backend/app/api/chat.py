from typing import Literal, Optional

from fastapi import APIRouter, Header, Path, Query, Depends
from app.core.dependencies import get_pagination, get_current_user
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionResponse,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    PaginationParams,
    SessionSummaryResponse,
)

# ------------------------------------------------------------------------------
# Router Setup
# ------------------------------------------------------------------------------

router = APIRouter(
    prefix="/api",
    tags=["Chat"],
)


# ------------------------------------------------------------------------------
# GET /api/chat-sessions
# ------------------------------------------------------------------------------

@router.get(
    "/chat-sessions",
    response_model=ChatSessionListResponse,
    summary="List all chat sessions",
)
def get_chat_sessions(  
    pagination: PaginationParams = Depends(get_pagination),
    current_user: str = Depends(get_current_user),
    search: Optional[str] = Query(
        default=None,
        description="Optional search term to filter sessions.",
    ),
):
    """
    Retrieve all chat sessions for the current user.
    Requires authentication.
    Supports pagination and optional search filtering.
    """
    return ChatSessionListResponse(
        sessions=[],
        total=0,
        page=pagination.page,
        limit=pagination.limit,
    )


# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}
# ------------------------------------------------------------------------------

@router.get(
    "/chat-sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Get a single chat session",
)
def get_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve a specific chat session by its ID."""
    return ChatSessionResponse(
        session_id=session_id,
        title="Placeholder session",
        created_at="2025-01-15T10:00:00",
        message_count=0,
    )


# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}/messages
# ------------------------------------------------------------------------------

@router.get(
    "/chat-sessions/{session_id}/messages",
    response_model=MessageListResponse,
    summary="Get messages in a session",
)
def get_chat_session_messages(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    pagination: PaginationParams = Depends(get_pagination),
    current_user: dict = Depends(get_current_user),
    
):
    """Retrieve paginated messages for a specific chat session."""
    return MessageListResponse(
        messages=[],
        total=0,
        session_id=session_id,
    )


# ------------------------------------------------------------------------------
# POST /api/chat-sessions
# ------------------------------------------------------------------------------

@router.post(
    "/chat-sessions",
    response_model=ChatSessionResponse,
    status_code=201,
    summary="Create a new chat session",
)
def create_chat_session(
    body: ChatSessionCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new chat session.

    Accepts an optional title. If no title is provided,
    the session title will be auto-generated from the first message in Phase 9.
    """
    return ChatSessionResponse(
        session_id="placeholder-session-id",
        title=body.title,
        created_at="2025-01-15T10:00:00",
        message_count=0,
    )


# ------------------------------------------------------------------------------
# POST /api/chat-sessions/{session_id}/messages
# ------------------------------------------------------------------------------

@router.post(
    "/chat-sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    summary="Send a message in a chat session",
)
def add_message_to_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    body: MessageCreate = ...,
    current_user: dict = Depends(get_current_user),
):
    """
    Send a new message in a chat session and receive an AI response.

    The student's message is received in the request body.
    The role is always 'assistant' in this placeholder response.
    Full AI integration will be added in Phase 7.
    """
    return MessageResponse(
        message_id="placeholder-message-id",
        session_id=session_id,
        role="assistant",
        content="AI response coming in Phase 7.",
        created_at="2025-01-15T10:00:00",
    )


# ------------------------------------------------------------------------------
# DELETE /api/chat-sessions/{session_id}
# ------------------------------------------------------------------------------

@router.delete(
    "/chat-sessions/{session_id}",
    status_code=204,
    summary="Delete a chat session",
)
def delete_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session to delete.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Delete a specific chat session and all its messages."""
    return None


# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}/summary
# ------------------------------------------------------------------------------

@router.get(
    "/chat-sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    summary="Get a summary of a chat session",
)
def get_chat_session_summary(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    summary_format: Literal["brief", "detailed"] = Query(
        default="brief",
        alias="format",
        description="Summary format. Allowed values: brief, detailed.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve an AI-generated summary of a chat session.

    Summary generation will be implemented in Phase 7.
    """
    return SessionSummaryResponse(
        session_id=session_id,
        summary_format=summary_format,
        summary="Summary generation coming in Phase 7.",
        message_count=0,
    )