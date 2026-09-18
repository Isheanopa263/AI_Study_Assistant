import logging
import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query
from app.services.audit import record_audit_log
from app.core.rate_limiter import check_rate_limit
from app.core.dependencies import get_current_user, get_pagination
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
from app.services.notification import send_message_notification, update_analytics

logger = logging.getLogger(__name__)

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
async def get_chat_sessions(
    pagination: PaginationParams = Depends(get_pagination),
    current_user: dict = Depends(get_current_user),
    search: Optional[str] = Query(
        default=None,
        description="Optional search term to filter sessions.",
    ),
):
    """
    Retrieve all chat sessions for the current user.

    Async because in Phase 3 this will call MongoDB via Motor.
    """
    logger.info(
        "Fetching chat sessions. user_id=%s page=%s limit=%s search=%s",
        current_user["user_id"],
        pagination.page,
        pagination.limit,
        search,
    )

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
async def get_chat_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve a specific chat session by its ID."""
    logger.info(
        "Fetching chat session. user_id=%s session_id=%s",
        current_user["user_id"],
        session_id,
    )

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
async def get_chat_session_messages(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    pagination: PaginationParams = Depends(get_pagination),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve paginated messages for a specific chat session."""
    logger.info(
        "Fetching messages. user_id=%s session_id=%s page=%s",
        current_user["user_id"],
        session_id,
        pagination.page,
    )

    return MessageListResponse(
        messages=[],
        total=0,
        session_id=session_id,
    )



@router.get(
    "/chat-sessions/{session_id}/full",
    summary="Get full session data concurrently",
)
async def get_full_session(
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve complete session data by fetching session info,
    messages, and metadata concurrently using asyncio.gather.

    Demonstrates how async concurrency reduces total wait time.
    Three 500ms operations complete in ~500ms total, not ~1500ms.
    """
    logger.info(
        "Fetching full session data. user_id=%s session_id=%s",
        current_user["user_id"],
        session_id,
    )

    start_time = asyncio.get_event_loop().time()

    # -----------------------------------------------------------------
    # Simulated async data sources
    # In production these would be real database and service calls:
    #   get_user_sessions → chat_repository.get_session()
    #   get_user_messages → chat_repository.get_messages()
    #   get_metadata      → analytics_service.get_session_metadata()
    # -----------------------------------------------------------------

    async def fake_get_session() -> dict:
        """Simulates fetching session details from MongoDB."""
        await asyncio.sleep(0.5)
        return {
            "session_id": session_id,
            "title": "Data Structures Study",
            "created_at": "2025-01-15T10:00:00",
        }

    async def fake_get_messages() -> list:
        """Simulates fetching messages from MongoDB."""
        await asyncio.sleep(0.5)
        return [
            {"role": "user", "content": "Explain recursion."},
            {"role": "assistant", "content": "Recursion is..."},
        ]

    async def fake_get_metadata() -> dict:
        """Simulates fetching analytics metadata."""
        await asyncio.sleep(0.5)
        return {
            "total_tokens_used": 1500,
            "ai_model": "gpt-4o-mini",
            "document_references": 2,
        }

    # -----------------------------------------------------------------
    # CONCURRENT EXECUTION
    # All three operations run at the same time.
    # Total time = max(0.5, 0.5, 0.5) = 0.5 seconds
    # NOT 0.5 + 0.5 + 0.5 = 1.5 seconds
    # -----------------------------------------------------------------

    session_data, messages, metadata = await asyncio.gather(
        fake_get_session(),
        fake_get_messages(),
        fake_get_metadata(),
    )

    # -----------------------------------------------------------------
    # Calculate total duration to prove concurrency
    # -----------------------------------------------------------------

    duration_ms = round(
        (asyncio.get_event_loop().time() - start_time) * 1000, 2
    )

    logger.info(
        "Full session data fetched. session_id=%s duration=%sms",
        session_id,
        duration_ms,
    )

    return {
        "session": session_data,
        "messages": messages,
        "metadata": metadata,
        "fetch_duration_ms": duration_ms,
        "concurrency_note": "Three 500ms operations completed concurrently.",
    }

# ------------------------------------------------------------------------------
# POST /api/chat-sessions
# ------------------------------------------------------------------------------

@router.post(
    "/chat-sessions",
    response_model=ChatSessionResponse,
    status_code=201,
    summary="Create a new chat session",
)
async def create_chat_session(
    body: ChatSessionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new chat session for the current user."""
    logger.info(
        "Creating chat session. user_id=%s title=%s",
        current_user["user_id"],
        body.title,
    )

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
async def add_message_to_chat_session(
    background_tasks: BackgroundTasks,
    _: bool = Depends(check_rate_limit),
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session.",
    ),
    body: MessageCreate = ...,
    current_user: dict = Depends(get_current_user),
):
    """
    Send a new message in a chat session.

    Rate limited to 10 messages per minute per user.
    Notifications and analytics run as background tasks.
    """
    logger.info(
        "Message received. user_id=%s session_id=%s length=%s",
        current_user["user_id"],
        session_id,
        len(body.content),
    )

    background_tasks.add_task(
        send_message_notification,
        user_id=current_user["user_id"],
        session_id=session_id,
        message_preview=body.content,
    )

    background_tasks.add_task(
        update_analytics,
        user_id=current_user["user_id"],
        event_type="message_sent",
        metadata={
            "session_id": session_id,
            "message_length": len(body.content),
        },
    )

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
async def delete_chat_session(
    background_tasks: BackgroundTasks,
    session_id: str = Path(
        ...,
        description="The unique identifier of the chat session to delete.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a specific chat session and all its messages.

    Records an audit log entry as a background task
    for security and compliance tracking.
    """
    logger.info(
        "Deleting chat session. user_id=%s session_id=%s",
        current_user["user_id"],
        session_id,
    )

    # In Phase 3, the actual deletion will happen here:
    #   await chat_repository.delete_session(session_id, current_user["user_id"])

    # Record the deletion in the audit log after response is sent
    background_tasks.add_task(
        record_audit_log,
        user_id=current_user["user_id"],
        action="chat_session_deleted",
        resource_type="chat_session",
        resource_id=session_id,
    )

    return None

# ------------------------------------------------------------------------------
# GET /api/chat-sessions/{session_id}/summary
# ------------------------------------------------------------------------------

@router.get(
    "/chat-sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    summary="Get a summary of a chat session",
)
async def get_chat_session_summary(
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
    """Retrieve an AI-generated summary of a chat session."""
    logger.info(
        "Fetching summary. user_id=%s session_id=%s format=%s",
        current_user["user_id"],
        session_id,
        summary_format,
    )

    return SessionSummaryResponse(
        session_id=session_id,
        summary_format=summary_format,
        summary="Summary generation coming in Phase 7.",
        message_count=0,
    )