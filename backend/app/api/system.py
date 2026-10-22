# app/api/system.py
"""System diagnostics endpoint — the Phase 2 capstone."""

import time
import logging
from fastapi import APIRouter, Depends

from app.config import get_settings, Settings
from app.schemas.system import SystemStatusResponse, SystemMetrics
from app.core.dependencies import get_current_user
from app.core.rate_limiter import rate_limiter
from app.repositories.document_repository import document_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System"])

# Capture startup time at module load
_start_time = time.time()


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="System health and diagnostics",
    description=(
        "Returns application metadata, runtime metrics, and overall health. "
        "Requires authentication. In DEBUG mode, external checks are skipped."
    ),
)
async def get_system_status(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> SystemStatusResponse:
    """
    Gather live metrics and return a full system status snapshot.

    Flow:
      1. Calculate uptime from module-level _start_time.
      2. Inspect the rate limiter's internal state.
      3. Count documents in the repository.
      4. Determine overall health based on DEBUG flag and metrics.
    """
    uptime = time.time() - _start_time

    # --- Gather metrics from live subsystems ---
    active_rate_limit_users = len(rate_limiter._requests)
    docs_count = len(document_repository._storage)

    metrics = SystemMetrics(
        uptime_seconds=round(uptime, 2),
        total_requests_served=0,  # Would come from middleware counter in production
        active_rate_limit_entries=active_rate_limit_users,
        documents_stored=docs_count,
    )

    # --- Determine health ---
    if settings.DEBUG:
        # In development, we're always "healthy" — no real DB to check
        status = "healthy"
        logger.debug("System status check (DEBUG mode) — returning healthy")
    else:
        # In production, you'd check MongoDB, Redis, etc. here.
        # For now, if uptime is suspiciously low, flag as degraded.
        status = "healthy" if uptime > 1.0 else "degraded"
        logger.info("System status check (PRODUCTION) — status=%s", status)

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        environment="development" if settings.DEBUG else "production",
        metrics=metrics,
        status=status,
    )