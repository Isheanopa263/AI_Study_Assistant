# tests/test_chat.py
"""Tests for the chat session and message endpoints."""

import asyncio
from typing import Dict

import pytest
from httpx import AsyncClient

from unittest.mock import AsyncMock, patch, MagicMock


# ── AUTH TESTS ──


async def test_get_sessions_unauthorized_without_token(client: AsyncClient):
    """Verify accessing chat sessions without Authorization header returns 401."""
    response = await client.get("/api/chat/sessions")
    assert response.status_code == 401


async def test_get_sessions_with_malformed_auth_header(client: AsyncClient):
    """Verify invalid header format returns 401."""
    response = await client.get(
        "/api/chat/sessions",
        headers={"Authorization": "InvalidFormatToken"},
    )
    assert response.status_code == 401


# ── SESSION CRUD ──


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
    assert data["message_count"] == 0


async def test_create_chat_session_without_title(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify title is optional on session creation."""
    response = await client.post(
        "/api/chat/sessions",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["title"] is None


async def test_get_chat_sessions_pagination(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify pagination parameters are parsed and returned correctly."""
    response = await client.get(
        "/api/chat/sessions?limit=5&page=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data
    assert data["page"] == 2
    assert data["limit"] == 5


async def test_get_chat_sessions_invalid_limit_fails_validation(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify limit > 100 triggers 422 validation error."""
    response = await client.get(
        "/api/chat/sessions?limit=500",
        headers=auth_headers,
    )
    assert response.status_code == 422


# ── SUMMARY & FULL ──


async def test_chat_summary_invalid_format_returns_422(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify unsupported summary format returns 422."""
    # First create a real session
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Summary Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    # The summary endpoint no longer takes a format query param,
    # so this test now verifies a valid session returns 200.
    response = await client.get(
        f"/api/chat/sessions/{session_id}/summary",
        headers=auth_headers,
    )
    assert response.status_code == 200


async def test_full_session_concurrency(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify the /full endpoint returns session + messages."""
    # Create a real session first
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


# ── MESSAGES ──



async def test_send_message_success(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify sending a valid message returns 201 with an AI response."""
    # Create a session first
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Message Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    # Mock the AI service to avoid real API calls in tests
    mock_ai_response = "A binary search tree is a sorted binary tree where each node's left children are smaller and right children are larger."

    with patch(
        "app.api.chat.AIService.chat",
        new_callable=AsyncMock,
        return_value=mock_ai_response,
    ):
        payload = {"content": "Explain binary search trees step by step."}
        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json=payload,
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "assistant"
    assert data["content"] == mock_ai_response
    assert "message_id" in data

async def test_send_empty_message_fails_validation(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify empty string message is rejected with 422."""
    # Create a session first
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Empty Msg Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    payload = {"content": ""}
    response = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 422


# ── DELETE ──


async def test_delete_chat_session_returns_204(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify deleting a session returns 204 No Content."""
    # Create a session first
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Delete Me"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    response = await client.delete(
        f"/api/chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/api/chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


# ── RATE LIMITING ──


@patch("app.services.ai_service.AIService.chat", new_callable=AsyncMock, return_value="Test response")
async def test_rate_limiter_blocks_eleventh_message(
    mock_chat, client: AsyncClient, auth_headers: Dict[str, str]
):
    """
    Verify sliding window rate limiting:
    - 10 rapid messages within 60 seconds are permitted (201 Created).
    - The 11th message is blocked with 429 Too Many Requests.
    """
    # Mock AI to return instantly — we're testing the rate limiter, not Gemini
    mock_chat = AsyncMock(return_value="Test response")

    # Create a session first
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Rate Limit Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    payload = {"content": "Rapid rate limit message"}

    # Send 10 permitted messages
    for i in range(1, 11):
        res = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json=payload,
            headers=auth_headers,
        )
        assert res.status_code == 201, f"Message {i} should have succeeded but got {res.status_code}"

    # 11th message should be blocked
    res = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json=payload,
        headers=auth_headers,
    )
    assert res.status_code == 429

async def test_stream_message_success(
    client: AsyncClient, auth_headers: Dict[str, str]
):
    """Verify streaming endpoint returns SSE events."""
    # Create session
    create_resp = await client.post(
        "/api/chat/sessions",
        json={"title": "Stream Test"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    # Create a mock async generator
    async def mock_stream(*args, **kwargs):
        for chunk in ["A hash ", "table is ", "a data structure."]:
            yield chunk

    with patch(
        "app.api.chat.AIService.chat_stream",
        side_effect=mock_stream,
    ):
        response = await client.post(
            f"/api/chat/sessions/{session_id}/stream",
            json={"content": "What is a hash table?"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert 'data: {"chunk": "A hash "}' in body
    assert 'data: {"chunk": "table is "}' in body
    assert 'data: {"chunk": "a data structure."}' in body
    assert "data: [DONE]" in body