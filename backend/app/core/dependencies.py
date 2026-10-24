# app/core/dependencies.py
"""
FastAPI dependencies for authentication, pagination, and repository injection.

Phase 2: get_current_user, get_pagination, get_token_from_header, get_optional_user
Phase 3: get_document_repo, get_chat_repo, get_document_service
"""

from fastapi import Depends, Header, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.repositories.document_repository import DocumentRepository
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import PaginationParams


# ──────────────────────────────────────────────
# AUTHENTICATION (Phase 2 — unchanged)
# ──────────────────────────────────────────────

async def get_token_from_header(
    authorization: str | None = Header(default=None),
) -> str:
    """Extract the Bearer token from the Authorization header."""
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme")
    token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")
    return token


async def get_current_user(
    token: str = Depends(get_token_from_header),
) -> dict:
    """
    Validate the token and return the current user.

    STUB: accepts any non-empty Bearer token.
    Will be replaced with JWT verification in Phase 5.
    """
    return {
        "user_id": "stub-user-id",
        "email": "student@example.com",
        "name": "Test Student",
    }


async def get_optional_user(
    authorization: str | None = Header(default=None),
) -> dict | None:
    """Return the current user if a token is provided, else None."""
    if authorization is None:
        return None
    try:
        token = await get_token_from_header(authorization)
        return await get_current_user(token)
    except HTTPException:
        return None


# ──────────────────────────────────────────────
# PAGINATION (Phase 2 — unchanged)
# ──────────────────────────────────────────────

async def get_pagination(
    limit: int = Query(default=10, ge=1, le=100, description="Items per page"),
    page: int = Query(default=1, ge=1, description="Page number (starts at 1)"),
) -> PaginationParams:
    """Parse and validate pagination query parameters."""
    return PaginationParams(limit=limit, page=page)


# ──────────────────────────────────────────────
# REPOSITORIES (Phase 3 — NEW)
# ──────────────────────────────────────────────

async def get_document_repo(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> DocumentRepository:
    """Dependency that provides a DocumentRepository instance."""
    return DocumentRepository(db)


async def get_chat_repo(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ChatRepository:
    """Dependency that provides a ChatRepository instance."""
    return ChatRepository(db)