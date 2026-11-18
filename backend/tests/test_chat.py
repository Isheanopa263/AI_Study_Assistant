"""
Integration Tests for Chat Endpoints.
Tests session creation, retrieval, messaging, rate limiting, SSE streaming, and summarization.
"""

import json
from typing import Dict
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_sessions_unauthorized_without_token(client: AsyncClient):
    """Verify requesting chat sessions without auth header returns 401."""
    response = await client.get("/api/chat/sessions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_sessions_with_malformed_auth_header(client: AsyncClient):
    """Verify requesting chat sessions with malformed auth header returns 401."""
    headers = {"Authorization": "InvalidScheme token"}
    response = await client.get("/api/chat/sessions", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_chat_session_success(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify creating a chat session with title returns 201 and valid schema."""
    payload = {"title": "Data Structures & Algorithms"}
    response = await client.post(
        "/api/chat/sessions",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["title"] == "Data Structures & Algorithms"


@pytest.mark.asyncio
async def test_create_chat_session_without_title(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify default title is applied if not supplied."""
    response = await client.post(
        "/api/chat/sessions",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["title"] == "New Study Session"


@pytest.mark.asyncio
async def test_get_chat_sessions_pagination(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify pagination parameters are parsed and list is returned."""
    response = await client.get(
        "/api/chat/sessions?limit=5&skip=0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_chat_sessions_invalid_limit_fails_validation(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify negative limit fails validation."""
    response = await client.get(
        "/api/chat/sessions?limit=-5",
        headers=auth_headers,
    )
    assert response.status_code in (422, 400)


@pytest.mark.asyncio
async def test_full_session_concurrency(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify the /full endpoint returns session + messages."""
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Full Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    response = await client.get(
        f"/api/chat/sessions/{session_id}/full",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "session" in data
    assert "messages" in data


@pytest.mark.asyncio
@patch("app.api.chat.ai_service.chat", new_callable=AsyncMock)
async def test_send_message_success(
    mock_chat, client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify sending a user message returns assistant response."""
    mock_chat.return_value = "Bubble sort has O(n^2) worst-case time complexity."

    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Algorithms"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    payload = {"content": "What is the time complexity of Bubble Sort?"}
    response = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "assistant"
    assert "Bubble sort" in data["content"]


@pytest.mark.asyncio
async def test_send_empty_message_fails_validation(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify empty message body returns validation error."""
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Validation Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    response = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": ""},
        headers=auth_headers,
    )
    assert response.status_code in (422, 400)


@pytest.mark.asyncio
async def test_delete_chat_session_returns_204(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify deleting a chat session returns 204."""
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "To Delete"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    del_resp = await client.delete(
        f"/api/chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
@patch("app.api.chat.ai_service.chat", new_callable=AsyncMock, return_value="Test response")
async def test_rate_limiter_blocks_eleventh_message(
    mock_chat, client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify sliding window rate limiting blocks 11th request."""
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Rate Limit Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]
    payload = {"content": "Rapid rate limit message"}

    for i in range(1, 11):
        res = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json=payload,
            headers=auth_headers,
        )
        assert res.status_code == 201

    res = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json=payload,
        headers=auth_headers,
    )
    assert res.status_code == 429


@pytest.mark.asyncio
@patch("app.api.chat.ai_service.chat_stream")
async def test_stream_message_success(
    mock_stream, client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify streaming AI response using SSE."""
    async def mock_async_gen(*args, **kwargs):
        yield "Hello "
        yield "World!"

    mock_stream.side_effect = mock_async_gen

    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Stream Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    response = await client.post(
        f"/api/chat/sessions/{session_id}/stream",
        json={"content": "Say hello world"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "data: " in response.text


@pytest.mark.asyncio
@patch("app.api.chat.ai_service.chat", new_callable=AsyncMock)
async def test_summarize_session_success(
    mock_chat, client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify manual summarization endpoint generates and stores summary."""
    mock_chat.return_value = "Summary: User is studying async Python event loops."

    create_res = await client.post(
        "/api/chat/sessions",
        json={"title": "Summary Test"},
        headers=auth_headers,
    )
    session_id = create_res.json()["session_id"]

    await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "I am studying async Python event loops."},
        headers=auth_headers,
    )

    sum_res = await client.post(
        f"/api/chat/sessions/{session_id}/summarize",
        headers=auth_headers,
    )

    assert sum_res.status_code == 200
    data = sum_res.json()
    assert data["session_id"] == session_id
    assert "User is studying async Python" in data["summary"]
    assert data["messages_summarized"] >= 1

    get_res = await client.get(
        f"/api/chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert get_res.json()["summary"] == "Summary: User is studying async Python event loops."


@pytest.mark.asyncio
async def test_summarize_empty_session(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify summarizing empty session returns early without errors."""
    create_res = await client.post(
        "/api/chat/sessions",
        json={"title": "Empty Summary Test"},
        headers=auth_headers,
    )
    session_id = create_res.json()["session_id"]

    sum_res = await client.post(
        f"/api/chat/sessions/{session_id}/summarize",
        headers=auth_headers,
    )

    assert sum_res.status_code == 200
    assert sum_res.json()["messages_summarized"] == 0
    assert sum_res.json()["summary"] == "No messages to summarize."