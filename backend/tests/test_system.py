# tests/test_system.py
"""Tests for the /api/system/status endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_system_status_authenticated(client: AsyncClient, auth_headers: dict):
    """Authenticated user gets a 200 with all expected fields."""
    response = await client.get("/api/system/status", headers=auth_headers)

    assert response.status_code == 200

    data = response.json()

    # --- Top-level fields ---
    assert "app_name" in data
    assert "version" in data
    assert "debug" in data
    assert "timestamp" in data
    assert "status" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")

    # --- Nested metrics ---
    metrics = data["metrics"]
    assert "uptime_seconds" in metrics
    assert metrics["uptime_seconds"] >= 0
    assert "documents_stored" in metrics
    assert metrics["documents_stored"] >= 0
    assert "active_rate_limit_entries" in metrics


@pytest.mark.asyncio
async def test_system_status_unauthenticated(client: AsyncClient):
    """Unauthenticated request is rejected with 401."""
    response = await client.get("/api/system/status")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_system_status_reflects_document_count(
    client: AsyncClient, auth_headers: dict
):
    """After uploading a document, the status endpoint reflects the new count."""
    # Upload a file first
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    await client.post("/api/documents/upload", files=files, headers=auth_headers)

    # Now check system status
    response = await client.get("/api/system/status", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["metrics"]["documents_stored"] >= 1