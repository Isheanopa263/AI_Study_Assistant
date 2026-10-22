# app/schemas/system.py
"""Pydantic schemas for the system diagnostics endpoint."""

from pydantic import BaseModel, Field
from datetime import datetime


class SystemMetrics(BaseModel):
    """Runtime metrics snapshot."""

    uptime_seconds: float = Field(
        ...,
        ge=0,
        description="Seconds since the application started",
    )
    total_requests_served: int = Field(
        default=0,
        ge=0,
        description="Total HTTP requests processed since startup",
    )
    active_rate_limit_entries: int = Field(
        default=0,
        ge=0,
        description="Number of unique users currently tracked by the rate limiter",
    )
    documents_stored: int = Field(
        default=0,
        ge=0,
        description="Number of documents in the repository",
    )


class SystemStatusResponse(BaseModel):
    """Full system status payload returned by /api/system/status."""

    app_name: str = Field(..., description="Application name from config")
    version: str = Field(..., description="Semantic version string")
    debug: bool = Field(..., description="Whether DEBUG mode is active")
    environment: str = Field(
        default="development",
        description="Deployment environment (development/staging/production)",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC time the status was generated",
    )
    metrics: SystemMetrics = Field(
        ...,
        description="Live runtime metrics",
    )
    status: str = Field(
        default="healthy",
        pattern="^(healthy|degraded|unhealthy)$",
        description="Overall health: healthy, degraded, or unhealthy",
    )