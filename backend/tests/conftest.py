from typing import AsyncGenerator, Dict

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rate_limiter import rate_limiter
from app.main import app
from app.repositories.document_repository import document_repository


# ------------------------------------------------------------------------------
# FIXTURE: HTTP Test Client
# ------------------------------------------------------------------------------

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an asynchronous in-memory HTTP client connected to FastAPI.
    
    raise_app_exceptions=False ensures that 500 errors are returned as HTTP 
    responses (just like in real production) instead of crashing the test runner.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


# ------------------------------------------------------------------------------
# FIXTURE: Mock Authenticated User
# ------------------------------------------------------------------------------

@pytest.fixture
def mock_user() -> Dict[str, str]:
    """Returns standard authenticated student user data."""
    return {
        "user_id": "test_student_123",
        "email": "student@university.edu",
        "name": "Test Student",
    }


# ------------------------------------------------------------------------------
# FIXTURE: Auth Headers
# ------------------------------------------------------------------------------

@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Returns valid Authorization headers for authenticated requests."""
    return {"Authorization": "Bearer test-valid-token"}


# ------------------------------------------------------------------------------
# FIXTURE: Clean State Before and After EVERY Test
# ------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """
    Automatically runs before and after EVERY test function.
    Guarantees total test isolation:
    - Clears in-memory document storage
    - Resets sliding window rate limiter counters
    """
    # Pre-test cleanup
    document_repository._storage.clear()
    rate_limiter._requests.clear()
    yield
    # Post-test cleanup
    document_repository._storage.clear()
    rate_limiter._requests.clear()