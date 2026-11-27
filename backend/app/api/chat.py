"""
API Router for Chat Sessions, Messaging, SSE Streaming, Grounded RAG, Tools, Coaching, and Resilience.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    MessageCreate,
    MessageResponse,
    PaginationParams,
    SummaryResponse,
)
from app.schemas.grounding import GroundedChatRequest, GroundedChatResponse
from app.schemas.tools import ToolChatRequest, ToolChatResponse, ToolCallDetail
from app.schemas.coaching import CoachingTurnRequest, CoachingTurnResponse
from app.repositories.chat_repository import ChatRepository
from app.repositories.document_repository import DocumentRepository
from app.services.ai_service import AIService
from app.services.context_manager import ContextManager
from app.services.grounding_service import GroundingService
from app.services.coaching_service import CoachingService
from app.services.prompts import TUTOR_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT
from app.core.dependencies import (
    get_chat_repo,
    get_document_repo,
    get_current_user,
    get_pagination,
)
from app.core.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Service singletons
ai_service = AIService()
context_manager = ContextManager()


def _extract_user_id(user: Any) -> str:
    """Helper to extract user_id string whether user is a dict or string."""
    if isinstance(user, dict):
        return user.get("user_id") or user.get("id") or "stub-user-id"
    return str(user)


def get_coaching_service(
    chat_repo: ChatRepository = Depends(get_chat_repo),
) -> CoachingService:
    """Dependency provider for CoachingService."""
    return CoachingService(chat_repo=chat_repo)


# ==========================================
# Resilience & Health Monitoring Endpoint
# ==========================================

@router.get(
    "/resilience/status",
    status_code=status.HTTP_200_OK,
    summary="Get AI Service Resilience & Circuit Breaker Health Status",
)
async def get_resilience_status() -> Dict[str, Any]:
    """Returns circuit breaker metrics, failure thresholds, and configured fallback models."""
    return ai_service.get_resilience_status()


# ==========================================
# Chat Session Management Endpoints
# ==========================================

@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_chat_session(
    payload: ChatSessionCreate,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Create a new chat session."""
    user_id = _extract_user_id(user)
    session = await repo.create_session(user_id=user_id, title=payload.title)
    return session


@router.get(
    "/sessions",
    response_model=List[ChatSessionResponse],
    response_model_by_alias=False,
)
async def list_chat_sessions(
    pagination: PaginationParams = Depends(get_pagination),
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """List all chat sessions for the authenticated user."""
    user_id = _extract_user_id(user)
    sessions, _ = await repo.list_sessions(
        user_id=user_id, skip=pagination.skip, limit=pagination.limit
    )
    return sessions


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    response_model_by_alias=False,
)
async def get_chat_session(
    session_id: str,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Get session metadata including its conversation summary."""
    user_id = _extract_user_id(user)
    return await repo.get_session(session_id=session_id, user_id=user_id)


@router.get(
    "/sessions/{session_id}/full",
    status_code=status.HTTP_200_OK,
)
async def get_full_chat_session(
    session_id: str,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Get session metadata and all associated messages."""
    user_id = _extract_user_id(user)
    session = await repo.get_session(session_id=session_id, user_id=user_id)
    messages, total = await repo.get_messages(session_id=session_id, user_id=user_id, limit=1000)
    return {
        "session": session,
        "messages": messages,
        "total_messages": total,
    }


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def send_message(
    session_id: str,
    payload: MessageCreate,
    request: Request,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Send a user message, process with Gemini using session memory, and store response."""
    user_id = _extract_user_id(user)
    await check_rate_limit(user_id)
    session = await repo.get_session(session_id=session_id, user_id=user_id)
    user_msg = await repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=payload.content,
    )
    raw_messages, _ = await repo.get_messages(session_id=session_id, user_id=user_id, limit=50)
    system_instruction = context_manager.build_system_instruction(
        base_system_prompt=TUTOR_SYSTEM_PROMPT,
        summary=session.get("summary")
    )
    contents = context_manager.build_context(
        messages=raw_messages,
        system_prompt=TUTOR_SYSTEM_PROMPT,
        summary=session.get("summary"),
    )
    try:
        ai_text = await ai_service.chat(
            messages=contents,
            system_instruction=system_instruction,
        )
        if isinstance(ai_text, dict):
            ai_text = ai_text.get("answer", "")
    except Exception as exc:
        logger.warning(f"AI service unavailable, returning fallback: {exc}")
        return user_msg

    tokens_used = context_manager.estimate_tokens(ai_text)
    assistant_msg = await repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=ai_text,
        tokens_used=tokens_used,
    )
    return assistant_msg


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: str,
    payload: MessageCreate,
    request: Request,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Stream AI response using Server-Sent Events (SSE)."""
    user_id = _extract_user_id(user)
    await check_rate_limit(user_id)
    session = await repo.get_session(session_id=session_id, user_id=user_id)
    await repo.add_message(session_id=session_id, user_id=user_id, role="user", content=payload.content)
    raw_messages, _ = await repo.get_messages(session_id=session_id, user_id=user_id, limit=50)
    system_instruction = context_manager.build_system_instruction(
        base_system_prompt=TUTOR_SYSTEM_PROMPT,
        summary=session.get("summary")
    )
    contents = context_manager.build_context(
        messages=raw_messages,
        system_prompt=TUTOR_SYSTEM_PROMPT,
        summary=session.get("summary"),
    )

    async def event_generator():
        accumulated_text = []
        try:
            async for chunk in ai_service.chat_stream(messages=contents, system_instruction=system_instruction):
                accumulated_text.append(chunk)
                data = json.dumps({"chunk": chunk})
                yield f"data: {data}\n\n"
            full_response = "".join(accumulated_text)
            tokens_used = context_manager.estimate_tokens(full_response)
            await repo.add_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=full_response,
                tokens_used=tokens_used,
            )
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error(f"Error in stream_message SSE generator: {exc}")
            yield f"data: {json.dumps({'error': 'Streaming interrupted'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    "/sessions/{session_id}/summarize",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def summarize_chat_session(
    session_id: str,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Manually trigger conversation summarization using Gemini."""
    user_id = _extract_user_id(user)
    session = await repo.get_session(session_id=session_id, user_id=user_id)
    messages, total_count = await repo.get_messages(session_id=session_id, user_id=user_id, limit=100)
    if not messages:
        return SummaryResponse(
            session_id=session_id,
            summary="No messages to summarize.",
            messages_summarized=0,
        )
    formatted_transcript = "\n".join(
        [f"{m['role'].upper()}: {m['content']}" for m in messages]
    )
    if session.get("summary"):
        formatted_transcript = (
            f"PREVIOUS SUMMARY:\n{session['summary']}\n\n"
            f"NEW MESSAGES:\n{formatted_transcript}"
        )
    summary_content = [
        {"role": "user", "parts": [{"text": f"Summarize this study session:\n{formatted_transcript}"}]}
    ]
    summary_result = await ai_service.chat(
        messages=summary_content,
        system_instruction=SUMMARY_SYSTEM_PROMPT,
    )
    summary_text = summary_result.get("answer", "") if isinstance(summary_result, dict) else summary_result

    await repo.update_summary(session_id=session_id, user_id=user_id, summary=summary_text)
    return SummaryResponse(
        session_id=session_id,
        summary=summary_text,
        messages_summarized=total_count,
    )


@router.post(
    "/sessions/{session_id}/grounded",
    response_model=GroundedChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a grounded study query using uploaded documents as context",
)
async def grounded_chat(
    session_id: str,
    payload: GroundedChatRequest,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
    doc_repo: DocumentRepository = Depends(get_document_repo),
) -> GroundedChatResponse:
    """Execute a grounded study query against specific document context sources."""
    user_id = _extract_user_id(user)
    await check_rate_limit(user_id)
    await repo.get_session(session_id=session_id, user_id=user_id)
    await repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=payload.query,
    )

    grounding_service = GroundingService(doc_repo=doc_repo, ai_service=ai_service)
    response = await grounding_service.generate_grounded_response(
        user_id=user_id,
        query=payload.query,
        document_ids=payload.document_ids,
        strict_mode=payload.strict_mode,
    )

    tokens_used = context_manager.estimate_tokens(response.answer)
    await repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=response.answer,
        tokens_used=tokens_used,
    )

    return response


@router.post(
    "/sessions/{session_id}/tools",
    response_model=ToolChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a query using registered backend tools for calculation and schedule generation",
)
async def tool_augmented_chat(
    session_id: str,
    payload: ToolChatRequest,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
) -> ToolChatResponse:
    """Execute a query with Gemini Function Calling capabilities enabled."""
    user_id = _extract_user_id(user)
    await check_rate_limit(user_id)
    session = await repo.get_session(session_id=session_id, user_id=user_id)
    await repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=payload.prompt,
    )

    raw_messages, _ = await repo.get_messages(session_id=session_id, user_id=user_id, limit=20)
    contents = context_manager.build_context(
        messages=raw_messages,
        system_prompt=TUTOR_SYSTEM_PROMPT,
        summary=session.get("summary"),
    )

    ai_result = await ai_service.chat(
        messages=contents,
        system_instruction=TUTOR_SYSTEM_PROMPT,
        enable_tools=True,
    )

    if isinstance(ai_result, dict):
        answer_text = ai_result.get("answer", "")
        raw_tool_calls = ai_result.get("tool_calls", [])
    else:
        answer_text = str(ai_result)
        raw_tool_calls = []

    tool_details = [
        ToolCallDetail(
            tool_name=tc["tool_name"],
            arguments=tc["arguments"],
            result=tc["result"],
        )
        for tc in raw_tool_calls
    ]

    tokens_used = context_manager.estimate_tokens(answer_text)
    await repo.add_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=answer_text,
        tokens_used=tokens_used,
    )

    return ToolChatResponse(
        answer=answer_text,
        tool_calls=tool_details,
        tokens_used=tokens_used,
    )


@router.post(
    "/sessions/{session_id}/coaching",
    response_model=CoachingTurnResponse,
    status_code=status.HTTP_200_OK,
    summary="Conduct an interactive coaching turn with real-time diagnostic evaluation",
)
async def interactive_coaching(
    session_id: str,
    payload: CoachingTurnRequest,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
    coaching_service: CoachingService = Depends(get_coaching_service),
) -> CoachingTurnResponse:
    """Execute a multi-turn coaching turn in Socratic, Explanatory, Quiz, or Review mode."""
    user_id = _extract_user_id(user)
    await check_rate_limit(user_id)
    await repo.get_session(session_id=session_id, user_id=user_id)

    response = await coaching_service.conduct_coaching_turn(
        session_id=session_id,
        user_id=user_id,
        request=payload,
    )
    return response


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[MessageResponse],
    response_model_by_alias=False,
)
async def get_chat_messages(
    session_id: str,
    pagination: PaginationParams = Depends(get_pagination),
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Retrieve message history for a given chat session."""
    user_id = _extract_user_id(user)
    messages, _ = await repo.get_messages(
        session_id=session_id,
        user_id=user_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return messages


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chat_session(
    session_id: str,
    user: Any = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
):
    """Delete session and associated message history."""
    user_id = _extract_user_id(user)
    await repo.delete_session(session_id=session_id, user_id=user_id)
    return None