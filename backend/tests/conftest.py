# tests/conftest.py
"""
Shared test fixtures for the AI Study Assistant test suite.
Phase 3: Uses a separate MongoDB test database.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient

from app.main import app
from app.core.rate_limiter import rate_limiter

TEST_MONGODB_URI = "mongodb://localhost:27017"
TEST_DB_NAME = "study_assistant_test"


@pytest.fixture
async def test_db_client():
    """Motor client for the test database. Created per-test to avoid scope issues."""
    client = AsyncIOMotorClient(TEST_MONGODB_URI)
    await client.admin.command("ping")
    yield client
    client.close()


@pytest.fixture(autouse=True)
async def clean_test_database(test_db_client):
    """Wipe the test database before and after every test."""
    db = test_db_client[TEST_DB_NAME]

    for name in await db.list_collection_names():
        await db[name].delete_many({})
    rate_limiter._requests.clear()

    yield

    for name in await db.list_collection_names():
        await db[name].delete_many({})
    rate_limiter._requests.clear()


@pytest.fixture
async def client(test_db_client):
    """HTTP client that uses the test database."""
    app.state.db = test_db_client[TEST_DB_NAME]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """Authentication headers for protected endpoints."""
    return {"Authorization": "Bearer test-token-123"}