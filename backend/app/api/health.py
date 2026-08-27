from fastapi import APIRouter

from app.config import settings
from app.core.exceptions import NotFoundException

# ------------------------------------------------------------------------------
# Router Setup
# ------------------------------------------------------------------------------

router = APIRouter(prefix="/api", tags=["Health"])


# ------------------------------------------------------------------------------
# GET /api/health
# ------------------------------------------------------------------------------

@router.get("/health")
def health_check():
    """Returns basic health status of the API."""
    return {
        "status": "ok",
        "message": "AI Study Assistant is running.",
    }


# ------------------------------------------------------------------------------
# GET /api/info
# ------------------------------------------------------------------------------

@router.get("/info")
def get_api_info():
    """Returns basic API information."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "purpose": "Conversational learning platform for students",
        "status": "operational",
    }


# ------------------------------------------------------------------------------
# TEMPORARY TEST ENDPOINTS
# Remove these before production deployment
# ------------------------------------------------------------------------------

@router.get("/test-error")
def test_error():
    """
    Temporary endpoint to test the unhandled exception handler.
    Remove before production.
    """
    raise ValueError("Deliberate unhandled error for testing.")


@router.get("/test-not-found")
def test_not_found():
    """
    Temporary endpoint to test the NotFoundException handler.
    Remove before production.
    """
    raise NotFoundException("Chat Session", "abc123")