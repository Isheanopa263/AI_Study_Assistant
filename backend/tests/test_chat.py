from typing import Dict

import pytest
from httpx import AsyncClient


# ==============================================================================
# 1. AUTHENTICATION & SECURITY TESTS
# ==============================================================================

async def test_get_sessions_unauthorized_without_token(client: AsyncClient):
    """Verify accessing chat sessions without Authorization header returns 401."""
    # Act
    response = await client.get("/api/chat-sessions")

    # Assert
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


async def test_get_sessions_with_malformed_auth_header(client: AsyncClient):
    """Verify invalid header format returns 401."""
    # Act
    response = await client.get(
        "/api/chat-sessions",
        headers={"Authorization": "InvalidFormatToken"},
    )

    # Assert
    assert response.status_code == 401
    assert "Bearer" in response.json()["message"]


# ==============================================================================
# 2. CHAT SESSION LIFECYCLE TESTS
# ==============================================================================

async def test_create_chat_session_success(client: AsyncClient, auth_headers: Dict[str, str]):
    """Verify creating a chat session with title returns 201 and valid schema."""
    # Arrange
    payload = {"title": "Data Structures & Algorithms"}

    # Act
    response = await client.post(
        "/api/chat-sessions",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert "session_id" in data
    assert data["message_count"] == 0


async def test_create_chat_session_without_title(client: AsyncClient, auth_headers: Dict[str, str]):
    """Verify title is optional on session creation."""
    # Act
    response = await client.post(
        "/api/chat-sessions",
        json={},
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 201
    assert response.json()["title"] is None


async def test_get_chat_sessions_pagination(client: AsyncClient, auth_headers: Dict[str, str]):
    """Verify pagination parameters are parsed and returned correctly."""
    # Act
    response = await client.get(
        "/api/chat-sessions?limit=5&page=2",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["page"] == 2
    assert "sessions" in data


async def test_get_chat_sessions_invalid_limit_fails_validation(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify limit > 100 triggers 422 validation error."""
    # Act
    response = await client.get(
        "/api/chat-sessions?limit=500",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "validation_error"


# ==============================================================================
# 3. EXERCISE 1 SOLUTION: SUMMARY FORMAT VALIDATION
# ==============================================================================

async def test_chat_summary_invalid_format_returns_422(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """
    [EXERCISE 1]
    Verify that providing an unsupported summary format string (e.g. format=invalid_format)
    fails Pydantic/FastAPI Literal validation and returns 422 with a structured error.
    """
    # Arrange
    session_id = "valid-session-123"

    # Act
    response = await client.get(
        f"/api/chat-sessions/{session_id}/summary?format=invalid_format",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "validation_error"
    assert "brief" in str(data["detail"]) or "detailed" in str(data["detail"])


# ==============================================================================
# 4. EXERCISE 2 SOLUTION: CONCURRENT FETCHING VERIFICATION
# ==============================================================================

async def test_full_session_concurrency(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """
    [EXERCISE 2]
    Verify that the /full endpoint executes three 500ms operations concurrently via
    asyncio.gather, returning a status 200 and total fetch duration well below
    the sequential execution threshold of 1500ms.
    """
    # Arrange
    session_id = "valid-session-123"

    # Act
    response = await client.get(
        f"/api/chat-sessions/{session_id}/full",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "session" in data
    assert "messages" in data
    assert "metadata" in data
    assert "fetch_duration_ms" in data

    # Concurrency Proof: Must complete under 1000ms (typically ~510ms)
    assert data["fetch_duration_ms"] < 1000.0, (
        f"Fetch took {data['fetch_duration_ms']}ms. Expected concurrent execution under 1000ms."
    )


# ==============================================================================
# 5. MESSAGE SENDING & VALIDATION
# ==============================================================================

async def test_send_message_success(client: AsyncClient, auth_headers: Dict[str, str]):
    """Verify sending a valid message returns 201 and assistant response placeholder."""
    # Arrange
    session_id = "test-session-001"
    payload = {"content": "Explain binary search trees step by step."}

    # Act
    response = await client.post(
        f"/api/chat-sessions/{session_id}/messages",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session_id
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0


async def test_send_empty_message_fails_validation(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify empty string message is rejected with 422."""
    # Arrange
    session_id = "test-session-001"
    payload = {"content": ""}

    # Act
    response = await client.post(
        f"/api/chat-sessions/{session_id}/messages",
        json=payload,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


async def test_delete_chat_session_returns_204(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify deleting a session returns 204 No Content."""
    # Act
    response = await client.delete(
        "/api/chat-sessions/test-session-001",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 204
    assert response.content == b""


# ==============================================================================
# 6. CHALLENGE EXERCISE SOLUTION: RATE LIMITER STRESS TEST
# ==============================================================================

async def test_rate_limiter_blocks_eleventh_message(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """
    [CHALLENGE EXERCISE]
    Verify sliding window rate limiting:
    - 10 rapid messages within 60 seconds are permitted (201 Created).
    - The 11th message is blocked immediately with 429 Too Many Requests.
    - Response headers contain Retry-After and rate limit metadata.
    """
    # Arrange
    session_id = "rate-limit-session-xyz"
    payload = {"content": "Rapid rate limit message"}

    # Act 1: Send 10 permitted messages in rapid succession
    for i in range(1, 11):
        res = await client.post(
            f"/api/chat-sessions/{session_id}/messages",
            json=payload,
            headers=auth_headers,
        )
        assert res.status_code == 201, f"Message {i} should have succeeded but got {res.status_code}"

    # Act 2: Send the 11th message (exceeding the limit of 10/minute)
    res_11 = await client.post(
        f"/api/chat-sessions/{session_id}/messages",
        json={"content": "Eleventh message exceeding quota"},
        headers=auth_headers,
    )

    # Assert
    assert res_11.status_code == 429
    data = res_11.json()
    assert data["error"] == "too_many_requests"
    assert "Too many requests" in data["message"]

    # Verify standard HTTP Rate Limiting Headers
    assert "retry-after" in res_11.headers
    assert res_11.headers["retry-after"] == "60"
    assert res_11.headers["x-ratelimit-limit"] == "10"
    assert res_11.headers["x-ratelimit-remaining"] == "0"