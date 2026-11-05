# backend/app/api/chat.py
"""
Chat session and message endpoints.
Phase 4, Lesson 4: Added SSE streaming endpoint.
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.core.dependencies import get_chat_repo, get_current_user, get_pagination
from app.core.exceptions import AIServiceException, NotFoundException
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
from app.services.ai_service import AIService
from app.services.context_manager import ContextManager
from app.services.prompts import TUTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ── HELPER ──


async def _build_ai_messages(
    repo: ChatRepository,
    session_id: str,
) -> list[dict]:
    """
    Load conversation history and build the full message list for the AI.
    Uses ContextManager for token-aware history selection.

    Returns:
        List of {"role": ..., "content": ...} dicts ready for AIService.
    """
    history = await repo.get_messages(
        session_id=session_id,
        skip=0,
        limit=100,  # Load more; context manager will trim
    )

    # Extract only role and content
    raw_messages = [
        {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        for msg in history
    ]

    # Use context manager to fit within token budget
    context_manager = ContextManager()
    selected_messages, enhanced_prompt = await context_manager.build_context(
        history=raw_messages,
        system_prompt=TUTOR_SYSTEM_PROMPT,
    )

    # Prepend system prompt (possibly enhanced with summary)
    ai_messages = [{"role": "system", "content": enhanced_prompt}]
    ai_messages.extend(selected_messages)

    return ai_messages

# ── SESSIONS ──


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    response_model_by_alias=False,
    status_code=201,
)
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
    return ChatSessionResponse.from_mongo(session)


@router.get(
    "/sessions",
    response_model=ChatSessionListResponse,
    response_model_by_alias=False,
)
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


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    response_model_by_alias=False,
)
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


# ── MESSAGES (non-streaming) ──


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    response_model_by_alias=False,
    status_code=201,
)
async def send_message(
    session_id: str,
    message_in: MessageCreate,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
    _: bool = Depends(check_rate_limit),
):
    """
    Send a message and get a complete AI response (non-streaming).
    Use /stream for real-time token-by-token responses.
    """
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)

    user_message = await repo.add_message(
        session_id=session_id,
        role="user",
        content=message_in.content,
    )
    logger.info("User message saved: session=%s", session_id)

    ai_messages = await _build_ai_messages(repo, session_id)

    try:
        ai = AIService()
        ai_response_text = await ai.chat(ai_messages)

        ai_message = await repo.add_message(
            session_id=session_id,
            role="assistant",
            content=ai_response_text,
        )
        logger.info("AI response saved: session=%s", session_id)
        return MessageResponse(**ai_message)

    except Exception as e:
        logger.warning(
            "AI unavailable, returning user message. session=%s error=%s",
            session_id, e,
        )
        return MessageResponse(**user_message)


# ── MESSAGES (streaming via SSE) ──


@router.post(
    "/sessions/{session_id}/stream",
    status_code=200,
)
async def stream_message(
    session_id: str,
    message_in: MessageCreate,
    user: dict = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
    _: bool = Depends(check_rate_limit),
):
    """
    Send a message and receive the AI response as a stream of SSE events.

    Each event is formatted as:
        data: {"chunk": "partial text"}

    The stream ends with:
        data: [DONE]

    The complete AI response is saved to MongoDB after streaming finishes.
    """
    # 1. Verify session exists
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundException(resource="ChatSession", resource_id=session_id)

    # 2. Save student's message
    await repo.add_message(
        session_id=session_id,
        role="user",
        content=message_in.content,
    )
    logger.info("User message saved (stream): session=%s", session_id)

    # 3. Build AI prompt
    ai_messages = await _build_ai_messages(repo, session_id)

    # 4. Create the SSE generator
    async def event_generator():
        """Yields SSE-formatted chunks and saves the full response at the end."""
        full_response_parts = []

        try:
            ai = AIService()
            async for chunk_text in ai.chat_stream(ai_messages):
                full_response_parts.append(chunk_text)

                # Format as SSE event
                event_data = json.dumps({"chunk": chunk_text})
                yield f"data: {event_data}\n\n"

            # Signal end of stream
            yield "data: [DONE]\n\n"

            # Save complete response to MongoDB
            complete_text = "".join(full_response_parts)
            if complete_text:
                await repo.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=complete_text,
                )
                logger.info(
                    "AI stream response saved: session=%s length=%d",
                    session_id, len(complete_text),
                )

        except AIServiceException as e:
            # Send error to client as an SSE event
            error_data = json.dumps({"error": e.message})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            logger.warning(
                "AI stream error: session=%s error=%s", session_id, e.message
            )

        except Exception as e:
            error_data = json.dumps({"error": "An unexpected error occurred."})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
            logger.error("Unexpected stream error: session=%s error=%s", session_id, e)

    # 5. Return streaming response
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if applicable
        },
    )


# ── MESSAGES (list) ──


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    response_model_by_alias=False,
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


@router.get(
    "/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    response_model_by_alias=False,
)
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


@router.get(
    "/sessions/{session_id}/full",
    response_model_by_alias=False,
)
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