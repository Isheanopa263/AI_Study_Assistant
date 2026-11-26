"""
Unit and Integration Tests for Interactive Multi-Turn Coaching Workflows.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient

from app.main import app
from app.repositories.chat_repository import ChatRepository
from app.services.coaching_service import CoachingService
from app.schemas.coaching import CoachingMode, CoachingStage, CoachingTurnRequest


def test_build_pedagogical_system_instruction_socratic():
    """Verify Socratic mode prompt enforces inquiry constraints."""
    service = CoachingService(chat_repo=AsyncMock(), client=MagicMock())
    instruction = service.build_pedagogical_system_instruction(
        topic="Dynamic Programming",
        mode=CoachingMode.SOCRATIC,
        stage=CoachingStage.PRACTICE,
        target_objectives=["Identify overlapping subproblems", "Define state transition equations"],
    )

    assert "TOPIC: Dynamic Programming" in instruction
    assert "PEDAGOGICAL MODE: SOCRATIC TUTOR" in instruction
    assert "Do NOT reveal full answers" in instruction
    assert "Identify overlapping subproblems" in instruction
    assert "CRITICAL OUTPUT FORMAT:" in instruction


def test_build_pedagogical_system_instruction_quiz_mode():
    """Verify Quiz mode prompt configures recall constraints."""
    service = CoachingService(chat_repo=AsyncMock(), client=MagicMock())
    instruction = service.build_pedagogical_system_instruction(
        topic="Mitochondrial Respiration",
        mode=CoachingMode.QUIZ,
        stage=CoachingStage.ASSESSMENT,
        target_objectives=["Explain the role of ATP synthase"],
    )

    assert "TOPIC: Mitochondrial Respiration" in instruction
    assert "PEDAGOGICAL MODE: ACTIVE RECALL QUIZ MASTER" in instruction
    assert "STAGE: Baseline Assessment" in instruction
    assert "Explain the role of ATP synthase" in instruction


@pytest.mark.asyncio
async def test_conduct_coaching_turn_service_logic():
    """Verify CoachingService parses structured JSON from Gemini."""
    mock_chat_repo = AsyncMock(spec=ChatRepository)
    mock_chat_repo.get_messages.return_value = ([], 0)
    mock_chat_repo.add_message.return_value = {"_id": "msg-123"}

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "assistant_message": "Excellent point! Why do we need a base case in recursive Fibonacci?",
        "evaluation": {
            "understanding_score": 4,
            "concept_mastered": False,
            "feedback": "Clear understanding of top-down division.",
            "hints": ["Think about infinite recursion."],
            "next_step": "Probe base case understanding."
        },
        "suggested_replies": [
            "To prevent infinite recursion and stack overflow.",
            "To speed up runtime.",
            "I'm not sure."
        ]
    })
    mock_response.usage_metadata = MagicMock(total_token_count=185)
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    service = CoachingService(chat_repo=mock_chat_repo, client=mock_client)
    request = CoachingTurnRequest(
        message="Recursion breaks problems into smaller identical subproblems.",
        topic="Recursion Fundamentals",
        mode=CoachingMode.SOCRATIC,
        stage=CoachingStage.PRACTICE,
        target_objectives=["Understand base cases and recursive steps"],
    )

    result = await service.conduct_coaching_turn(
        session_id="session-xyz",
        user_id="user-123",
        request=request,
    )

    assert result.session_id == "session-xyz"
    assert result.mode == CoachingMode.SOCRATIC
    assert result.stage == CoachingStage.PRACTICE
    assert "base case" in result.assistant_message
    assert result.evaluation.understanding_score == 4
    assert result.evaluation.concept_mastered is False
    assert len(result.suggested_replies) == 3
    assert result.tokens_used == 185
    assert mock_chat_repo.add_message.call_count == 2


@pytest.mark.asyncio
async def test_coaching_turn_endpoint_success(
    client: AsyncClient,
    auth_headers: dict,
    test_db_client,
):
    """Integration test: validates POST /api/chat/sessions/{session_id}/coaching flow."""
    test_db = test_db_client["study_assistant_test"]
    chat_repo = ChatRepository(db=test_db)

    # 1. Create a session
    sess_res = await client.post(
        "/api/chat/sessions",
        json={"title": "Coaching Test Session"},
        headers=auth_headers,
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 2. Mock Gemini client inside coaching service
    mock_gemini_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "assistant_message": "Spot on analysis of asymptotic limits! What happens when n approaches infinity?",
        "evaluation": {
            "understanding_score": 5,
            "concept_mastered": True,
            "feedback": "Mastery of Big-O upper bound definition demonstrated.",
            "hints": [],
            "next_step": "Advance to tight bound (Theta) analysis."
        },
        "suggested_replies": [
            "The lower-order terms become negligible.",
            "The constants dominate the computation.",
            "Can we review Theta notation next?"
        ]
    })
    mock_response.usage_metadata = MagicMock(total_token_count=210)
    mock_gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    from app.api import chat
    app.dependency_overrides[chat.get_coaching_service] = lambda: CoachingService(
        chat_repo=chat_repo,
        client=mock_gemini_client,
    )

    try:
        payload = {
            "message": "Big-O gives the upper bound on growth rate as input size scales.",
            "topic": "Computational Complexity",
            "mode": "socratic",
            "stage": "practice",
            "target_objectives": ["Define Big-O upper bound", "Compare polynomial vs exponential growth"],
        }
        res = await client.post(
            f"/api/chat/sessions/{session_id}/coaching",
            json=payload,
            headers=auth_headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == session_id
        assert data["mode"] == "socratic"
        assert data["stage"] == "practice"
        assert "Spot on analysis" in data["assistant_message"]
        assert data["evaluation"]["understanding_score"] == 5
        assert data["evaluation"]["concept_mastered"] is True
        assert len(data["suggested_replies"]) == 3
        assert data["tokens_used"] == 210

        # Verify messages persisted
        messages, count = await chat_repo.get_messages(
            session_id=session_id, user_id="stub-user-id"
        )
        assert count == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
    finally:
        app.dependency_overrides.pop(chat.get_coaching_service, None)