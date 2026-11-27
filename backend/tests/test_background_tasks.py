"""
Tests for asynchronous background tasks and HTTP 202 Accepted endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient

from app.services.background_service import generate_session_summary_task

pytestmark = pytest.mark.asyncio


async def test_summarize_in_background_returns_202(
    client: AsyncClient,
    auth_headers: dict,
):
    """
    Verifies that calling the background summarization endpoint immediately
    returns HTTP 202 Accepted with a queued job payload.
    """
    # 1. Create a session
    create_res = await client.post(
        "/api/chat/sessions",
        headers=auth_headers,
        json={"title": "Background Task Test Session"},
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["session_id"]

    # 2. Add a message
    with patch("app.api.chat.ai_service.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Newton's second law is F=ma."
        await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            headers=auth_headers,
            json={"content": "Can you explain Newton's second law of motion?"},
        )

    # 3. Request background summarization
    with patch("app.services.background_service.genai.Client") as mock_genai:
        mock_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = "Key Concept: F=ma. Student explored acceleration."
        mock_model.generate_content.return_value = mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.aio.models = mock_model
        mock_genai.return_value = mock_client_instance

        bg_res = await client.post(
            f"/api/chat/sessions/{session_id}/summarize/background",
            headers=auth_headers,
        )

        assert bg_res.status_code == 202
        data = bg_res.json()
        assert data["session_id"] == session_id
        assert data["status"] == "queued"
        assert data["job_type"] == "session_summarization"


async def test_summarize_background_nonexistent_session_404(
    client: AsyncClient,
    auth_headers: dict,
):
    """
    Verifies that requesting a background task on a non-existent session
    returns HTTP 404 Not Found before queueing.
    """
    fake_id = "507f1f77bcf86cd799439011"
    res = await client.post(
        f"/api/chat/sessions/{fake_id}/summarize/background",
        headers=auth_headers,
    )
    assert res.status_code == 404


async def test_summary_status_endpoint_returns_state(
    client: AsyncClient,
    auth_headers: dict,
):
    """
    Verifies that the summary status polling endpoint accurately reports
    whether a summary exists on the session.
    """
    # Create session
    create_res = await client.post(
        "/api/chat/sessions",
        headers=auth_headers,
        json={"title": "Summary Status Check"},
    )
    session_id = create_res.json()["session_id"]

    # Check status before summary exists
    status_res = await client.get(
        f"/api/chat/sessions/{session_id}/summary/status",
        headers=auth_headers,
    )
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["session_id"] == session_id
    assert data["summary_available"] is False
    assert data["summary"] is None


async def test_background_service_worker_execution():
    """
    Direct unit test of the background worker function isolating AI and DB calls.
    """
    mock_chat_repo = AsyncMock()
    mock_chat_repo.get_messages.return_value = (
        [
            {"role": "user", "content": "What is Photosynthesis?"},
            {
                "role": "assistant",
                "content": "Photosynthesis converts sunlight into glucose.",
            },
        ],
        2,
    )
    mock_chat_repo.update_summary.return_value = True

    with patch("app.services.background_service.genai.Client") as mock_genai:
        mock_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = "Key Concept: Photosynthesis and energy conversion."
        mock_model.generate_content.return_value = mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.aio.models = mock_model
        mock_genai.return_value = mock_client_instance

        # Execute worker directly
        await generate_session_summary_task(
            session_id="test-session-123",
            user_id="test-user-456",
            chat_repo=mock_chat_repo,
        )

        mock_chat_repo.get_messages.assert_awaited_once_with(
            session_id="test-session-123",
            user_id="test-user-456",
            skip=0,
            limit=100,
        )
        mock_chat_repo.update_summary.assert_awaited_once_with(
            session_id="test-session-123",
            user_id="test-user-456",
            summary="Key Concept: Photosynthesis and energy conversion.",
        )