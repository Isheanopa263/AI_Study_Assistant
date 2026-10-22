import pytest
from httpx import AsyncClient


async def test_health_check_returns_200(client: AsyncClient):
    """Verify that the health check endpoint returns 200 OK and expected payload."""
    # Act
    response = await client.get("/api/health")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "running" in data["message"].lower()


async def test_info_endpoint_returns_metadata(client: AsyncClient):
    """Verify API metadata returns app title, version, and purpose."""
    # Act
    response = await client.get("/api/info")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data
    assert data["status"] == "operational"


async def test_unhandled_error_returns_safe_500(client: AsyncClient):
    """Verify that unexpected exceptions return a structured 500 error without leaking stack traces."""
    # Act
    response = await client.get("/api/test-error")

    # Assert
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "internal_server_error"
    assert "request_id" in data
    assert "traceback" not in data


async def test_custom_not_found_exception(client: AsyncClient):
    """Verify custom NotFoundException returns consistent 404 JSON format."""
    # Act
    response = await client.get("/api/test-not-found")

    # Assert
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "not_found"
    assert "abc123" in data["message"]
    assert "request_id" in data


async def test_non_existent_route_returns_404(client: AsyncClient):
    """Verify unknown routes return standard 404."""
    # Act
    response = await client.get("/api/unknown-endpoint-xyz")

    # Assert
    assert response.status_code == 404