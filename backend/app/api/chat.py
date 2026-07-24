from typing import Literal, Optional

from fastapi import APIRouter, Header, Path, Query

router = APIRouter(
    prefix="/api",
    tags=["Chat"],
)


# ------------------------------------------------------------------------------
# GET /api/chat-sessions
# ------------------------------------------------------------------------------

@router.get("/chat-sessions")
def get_chat_sessions(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of chat sessions to retrieve per page.",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Page number for pagination.",
    ),
    search: Optional[str] = Query(
        default=None,
        description="Optional search term to filter chat sessions by title or content.",
    ),
):
    """Retrieve all chat sessions for the current user with pagination and optional search."""
    return {
        "sessions": [],
        "limit": limit,
        "page": page,
        "search": search,
        "total_sessions": 0,
        "status": "Chat sessions endpoint ready. Database not yet connected.",
    }


# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}
# ------------------------------------------------------------------------------

@router.get("/chat-sessions/{session_id}")
def get_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session to retrieve.",
    ),
):
    """Retrieve a specific chat session by its ID."""
    return {
        "session_id": session_id,
        "messages": [],
        "status": "Single session endpoint ready. Database not yet connected.",
    }


# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}/messages
# ------------------------------------------------------------------------------

@router.get("/chat-sessions/{session_id}/messages")
def get_chat_session_messages(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=50,
        description="Number of messages to retrieve. Maximum is 50.",
    ),
):
    """Retrieve paginated messages for a specific chat session."""
    return {
        "session_id": session_id,
        "messages": [],
        "limit": limit,
        "total_messages": 0,
        "status": "Messages endpoint ready. Database not yet connected.",
    }


# ------------------------------------------------------------------------------
# POST /api/chat-sessions
# ------------------------------------------------------------------------------

@router.post("/chat-sessions", status_code=201)
def create_chat_session(
    authorization: Optional[str] = Header(
        default=None,
        description="Bearer token for authentication. Required in production.",
    ),
):
    """Create a new chat session for the current user."""
    return {
        "session_id": "placeholder-session-id",
        "created": True,
        "status": "Chat session created. Database not yet connected.",
    }


# ------------------------------------------------------------------------------
# POST /api/chat-sessions/{session_id}/messages
# ------------------------------------------------------------------------------

@router.post("/chat-sessions/{session_id}/messages", status_code=201)
def add_message_to_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session to add a message to.",
    ),
):
    """
    Add a new message to a specific chat session.
    """
    return {
        "message_id": "placeholder-message-id",
        "session_id": session_id,
        "role": "assistant",
        "content": "AI response coming soon.",
        "status": "Message endpoint ready. Request body and database coming in Lesson 3.",
    }


# ------------------------------------------------------------------------------
# DELETE /api/chat-sessions/{session_id}
# ------------------------------------------------------------------------------

@router.delete("/chat-sessions/{session_id}", status_code=204)
def delete_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session to delete.",
    ),
):
    """Delete a specific chat session by its ID. Returns 204 No Content."""
    return None


# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}/summary
# ------------------------------------------------------------------------------

@router.get("/chat-sessions/{session_id}/summary")
def get_chat_session_summary(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session to summarize.",
    ),
    summary_format: Literal["brief", "detailed"] = Query(
        default="brief",
        alias="format",
        description="The format of the summary. Allowed values: brief, detailed.",
    ),
):
    """
    Retrieve a summary of a specific chat session.
    """
    return {
        "session_id": session_id,
        "format": summary_format,
        "message_count": 0,
        "summary": "Summary generation coming in Phase 7.",
        "status": "Summary endpoint ready. AI integration coming in Phase 7.",
    }