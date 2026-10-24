# app/api/chat.py
"""
Chat session and message endpoints.
Phase 3: Uses MongoDB via ChatRepository.
"""

import logging

from fastapi import APIRouter, Depends

from app.core.dependencies import get_chat_repo, get_current_user, get_pagination
from app.core.exceptions import NotFoundException
from app.core.rate_limiter import check_rate_limit
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionListResponse,
    MessageCreate,
    MessageResponse,
    MessageListResponse,
    PaginationParams,
    SessionSummaryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ── SESSIONS ──


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    session_in: ChatSessionCreate,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Create a new chat session."""
    session_id = await repo.create_session(
        user_id=user["user_id"],
        title=session_in.title,
    )
    session = await repo.get_session(session_id)
    logger.info("Session created: id=%s user=%s", session_id, user["user_id"])
    return ChatSessionResponse(**session)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    pagination: PaginationParams = Depends(get_pagination),
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """List all chat sessions for the current user."""
    sessions = await repo.list_sessions(
        user_id=user["user_id"],
        skip=pagination.offset,
        limit=pagination.limit,
    )
    total = await repo.count_sessions(user["user_id"])
    return ChatSessionListResponse(
        sessions=[ChatSessionResponse(**s) for s in sessions],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Get a single chat session by ID."""
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)
    return ChatSessionResponse(**session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Delete a chat session and all its messages."""
    deleted = await repo.delete_session(session_id)
    if not deleted:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)
    logger.info("Session deleted: id=%s", session_id)


# ── MESSAGES ──


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
async def send_message(
    session_id: str,
    message_in: MessageCreate,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
    _: bool = Depends(check_rate_limit),
):
    """Send a message in a chat session."""
    # Verify session exists
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)

    # Save user message (role is always "user" from the student)
    message = await repo.add_message(
        session_id=session_id,
        role="user",
        content=message_in.content,
    )

    logger.info("Message sent: session=%s", session_id)
    return MessageResponse(**message)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
)
async def get_messages(
    session_id: str,
    pagination: PaginationParams = Depends(get_pagination),
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Get all messages in a chat session."""
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)

    messages = await repo.get_messages(
        session_id=session_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    total = await repo.count_messages(session_id)
    return MessageListResponse(
        messages=[MessageResponse(**m) for m in messages],
        total=total,
        session_id=session_id,
    )


# ── SUMMARY ──


@router.get("/sessions/{session_id}/summary", response_model=SessionSummaryResponse)
async def get_session_summary(
    session_id: str,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Get a summary of a chat session."""
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)

    count = await repo.count_messages(session_id)
    return SessionSummaryResponse(
        session_id=session_id,
        summary_format="brief",
        summary=f"Session '{session.get('title', 'Untitled')}' with {count} messages.",
        message_count=count,
    )

@router.get("/sessions/{session_id}/full")
async def get_full_conversation(
    session_id: str,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Get the full conversation (session + all messages)."""
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)

    messages = await repo.get_messages(session_id, limit=500)
    return {
        "session": ChatSessionResponse(**session),
        "messages": [MessageResponse(**m) for m in messages],
    }