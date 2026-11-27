"""
Chat and AI Interaction Router.
Provides endpoints for standard messaging, streaming, grounded RAG,
tool-augmented execution, multi-turn pedagogical coaching,
resilience status, and asynchronous background tasks.
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.dependencies import (
    get_chat_repo,
    get_current_user,
    get_document_repo,
    get_pagination,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.background import BackgroundJobResponse, BackgroundJobStatus
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    MessageCreate,
    MessageResponse,
    PaginationParams,
    SummaryResponse,
)
from app.schemas.coaching import CoachingTurnRequest, CoachingTurnResponse
from app.schemas.grounding import GroundedChatRequest, GroundedChatResponse
from app.schemas.tools import ToolChatRequest, ToolChatResponse
from app.services.ai_service import AIService
from app.services.background_service import generate_session_summary_task
from app.services.coaching_service import CoachingService
from app.services.grounding_service import GroundingService

# Optional Rate Limiter import
try:
    from app.core.rate_limiter import check_rate_limit
except ImportError:
    async def check_rate_limit(user_id: str):
        pass

logger = logging.getLogger("study_assistant.chat")

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Shared singleton for resilient AI calls
ai_service = AIService()


def _get_user_id(current_user: dict) -> str:
    """Safely extract user ID whether stored as 'user_id' or '_id'."""
    return str(current_user.get("user_id") or current_user.get("_id", "anonymous"))


def _resolve_pagination(pagination: PaginationParams) -> tuple[int, int]:
    """Resolves skip and limit across differing PaginationParams structures."""
    limit = getattr(pagination, "limit", 20)
    skip = getattr(pagination, "skip", None)
    if skip is None:
        page = getattr(pagination, "page", 1)
        skip = (page - 1) * limit
    return skip, limit


def get_coaching_service(
    chat_repo: ChatRepository = Depends(get_chat_repo),
) -> CoachingService:
    """FastAPI dependency providing CoachingService instance (overrideable in tests)."""
    return CoachingService(chat_repo=chat_repo)


# ============================================================================
# Session Management Endpoints
# ============================================================================

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: ChatSessionCreate,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Create a new chat session for the authenticated student."""
    user_id = _get_user_id(current_user)
    # await check_rate_limit(user_id)

    session = await chat_repo.create_session(
        user_id=user_id,
        title=session_data.title,
    )
    return session


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """List all chat sessions belonging to the authenticated student."""
    user_id = _get_user_id(current_user)
    skip, limit = _resolve_pagination(pagination)

    result = await chat_repo.list_sessions(user_id=user_id, skip=skip, limit=limit)
    sessions = result[0] if isinstance(result, tuple) else result
    return sessions


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Retrieve details for a single chat session."""
    user_id = _get_user_id(current_user)
    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return session


@router.get("/sessions/{session_id}/full")
async def get_session_full(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Retrieve full details of a session together with all its messages."""
    user_id = _get_user_id(current_user)
    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    result = await chat_repo.get_messages(session_id=session_id, user_id=user_id, skip=0, limit=100)
    messages = result[0] if isinstance(result, tuple) else result
    return {"session": session, "messages": messages}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Delete a chat session and all its associated messages."""
    user_id = _get_user_id(current_user)
    deleted = await chat_repo.delete_session(session_id=session_id, user_id=user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return None


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Retrieve historical messages for a specific chat session."""
    user_id = _get_user_id(current_user)
    skip, limit = _resolve_pagination(pagination)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    result = await chat_repo.get_messages(
        session_id=session_id, user_id=user_id, skip=skip, limit=limit
    )
    messages = result[0] if isinstance(result, tuple) else result
    return messages


# ============================================================================
# Messaging & AI Interaction Endpoints
# ============================================================================

@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: str,
    msg_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Send a message to the AI assistant using resilient fallbacks and retries."""
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Save student message
    await chat_repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=msg_data.content,
    )

    # Fetch recent conversation history
    history_data = await chat_repo.get_messages(
        session_id=session_id, user_id=user_id, skip=0, limit=20
    )
    history = history_data[0] if isinstance(history_data, tuple) else history_data

    system_instruction = (
        "You are an encouraging, precise, and world-class AI Study Assistant. "
        "Help the student understand concepts deeply through step-by-step explanations."
    )

    ai_response = await ai_service.chat(
        messages=history,
        system_instruction=system_instruction,
    )

    response_text = ai_response if isinstance(ai_response, str) else ai_response.get("answer", "")

    # Save assistant message
    saved_assistant_message = await chat_repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=response_text,
    )

    return saved_assistant_message


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: str,
    msg_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Stream AI response chunks using Server-Sent Events (SSE)."""
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    await chat_repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=msg_data.content,
    )

    history_data = await chat_repo.get_messages(
        session_id=session_id, user_id=user_id, skip=0, limit=20
    )
    history = history_data[0] if isinstance(history_data, tuple) else history_data

    async def event_generator():
        accumulated_chunks = []
        try:
            async for chunk in ai_service.chat_stream(
                messages=history,
                system_instruction="You are an expert AI Study Assistant. Stream your pedagogical explanation clearly.",
            ):
                accumulated_chunks.append(chunk)
                payload = json.dumps({"chunk": chunk})
                yield f"data: {payload}\n\n"

            full_text = "".join(accumulated_chunks)
            await chat_repo.add_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=full_text,
            )
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as exc:
            logger.error("Error in streaming response: %s", str(exc), exc_info=True)
            yield f"data: {json.dumps({'error': 'Streaming interrupted'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# Synchronous Summarization Endpoint (Phase 2/3 compatibility)
# ============================================================================

@router.post("/sessions/{session_id}/summarize", response_model=SummaryResponse)
async def summarize_session_sync(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Synchronously summarize session history and update database."""
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    messages_data = await chat_repo.get_messages(
        session_id=session_id, user_id=user_id, skip=0, limit=100
    )
    messages = messages_data[0] if isinstance(messages_data, tuple) else messages_data

    if not messages:
        return SummaryResponse(
            session_id=session_id,
            summary="No messages to summarize.",
            messages_summarized=0,
        )

    ai_result = await ai_service.chat(
        messages=messages,
        system_instruction="Summarize the key study concepts covered in this conversation concisely.",
    )
    summary_text = ai_result if isinstance(ai_result, str) else ai_result.get("answer", "")

    await chat_repo.update_summary(
        session_id=session_id,
        user_id=user_id,
        summary=summary_text,
    )

    return SummaryResponse(
        session_id=session_id,
        summary=summary_text,
        messages_summarized=len(messages),
    )


# ============================================================================
# Advanced Pedagogical & Tool Endpoints
# ============================================================================

@router.post("/sessions/{session_id}/grounded", response_model=GroundedChatResponse)
async def grounded_chat_endpoint(
    session_id: str,
    request: GroundedChatRequest,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
    doc_repo: DocumentRepository = Depends(get_document_repo),
):
    """Answer student queries grounded strictly in uploaded study documents."""
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    grounding_service = GroundingService(doc_repo=doc_repo, ai_service=ai_service)
    return await grounding_service.generate_grounded_response(
        user_id=user_id,
        query=request.query,
        document_ids=request.document_ids,
        strict_mode=request.strict_mode,
    )


@router.post("/sessions/{session_id}/tools", response_model=ToolChatResponse)
async def tools_chat_endpoint(
    session_id: str,
    request: ToolChatRequest,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Execute AI interaction with tool assistance (calculator, dictionary, study timer)."""
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    messages = [{"role": "user", "content": request.prompt}]
    result = await ai_service.chat(messages=messages, enable_tools=True)

    if isinstance(result, dict):
        return ToolChatResponse(
            answer=result.get("answer", ""),
            tool_calls=result.get("tool_calls", []),
            tokens_used=0,
        )

    return ToolChatResponse(answer=str(result), tool_calls=[], tokens_used=0)


@router.post("/sessions/{session_id}/coaching", response_model=CoachingTurnResponse)
async def coaching_chat_endpoint(
    session_id: str,
    request: CoachingTurnRequest,
    current_user: dict = Depends(get_current_user),
    coaching_service: CoachingService = Depends(get_coaching_service),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Conduct an interactive pedagogical coaching turn."""
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    return await coaching_service.conduct_coaching_turn(
        session_id=session_id,
        user_id=user_id,
        request=request,
    )


@router.get("/resilience/status")
async def get_resilience_status():
    """Inspect the live health and circuit-breaker state of the AI service (Public probe)."""
    return ai_service.get_resilience_status()


# ============================================================================
# Background Processing Endpoints
# ============================================================================

@router.post(
    "/sessions/{session_id}/summarize/background",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def summarize_session_in_background(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """
    Queue a background AI job to summarize the study session.
    Returns HTTP 202 Accepted immediately without blocking the client.
    """
    user_id = _get_user_id(current_user)
    await check_rate_limit(user_id)

    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    background_tasks.add_task(
        generate_session_summary_task,
        session_id=session_id,
        user_id=user_id,
        chat_repo=chat_repo,
    )

    return BackgroundJobResponse(
        session_id=session_id,
        job_type="session_summarization",
        status="queued",
        message="Session summarization has been queued and is processing in the background.",
    )


@router.get(
    "/sessions/{session_id}/summary/status",
    response_model=BackgroundJobStatus,
)
async def get_session_summary_status(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Check if the background summary has been completed and saved in MongoDB."""
    user_id = _get_user_id(current_user)
    session = await chat_repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    summary = session.get("summary")
    return BackgroundJobStatus(
        session_id=session_id,
        summary_available=bool(summary),
        summary=summary,
        last_updated=session.get("updated_at"),
    )