# app/api/system.py
"""System diagnostics endpoint."""

import time
import logging

from fastapi import APIRouter, Depends

from app.config import get_settings, Settings
from app.schemas.system import SystemStatusResponse, SystemMetrics
from app.core.dependencies import get_current_user, get_document_repo
from app.core.rate_limiter import rate_limiter
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System"])

_start_time = time.time()


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Return system health and diagnostics."""
    uptime = time.time() - _start_time

    active_rate_limit_users = len(rate_limiter._requests)
    docs_count = await repo.count()

    metrics = SystemMetrics(
        uptime_seconds=round(uptime, 2),
        total_requests_served=0,
        active_rate_limit_entries=active_rate_limit_users,
        documents_stored=docs_count,
    )

    if settings.DEBUG:
        status = "healthy"
    else:
        status = "healthy" if uptime > 1.0 else "degraded"

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        environment="development" if settings.DEBUG else "production",
        metrics=metrics,
        status=status,
    )