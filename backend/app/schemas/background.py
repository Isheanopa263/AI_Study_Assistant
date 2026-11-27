"""
Pydantic schemas for asynchronous background jobs.
Complies with RFC 9110 HTTP 202 Accepted status contracts.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BackgroundJobResponse(BaseModel):
    """
    Standard response returned immediately when a background task is enqueued.
    """
    session_id: str = Field(..., description="ID of the chat session being processed.")
    job_type: str = Field(..., description="Type of background job scheduled.")
    status: str = Field(default="queued", description="Initial status of the task.")
    message: str = Field(..., description="Human-readable acknowledgement message.")
    queued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the job was accepted into the queue."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "60d5ec49f1b2c8b1f8e4e1a1",
                "job_type": "session_summarization",
                "status": "queued",
                "message": "Session summarization task has been queued successfully.",
                "queued_at": "2025-01-01T12:00:00Z"
            }
        }
    )


class BackgroundJobStatus(BaseModel):
    """
    Schema for inspecting the status or result of a background job.
    """
    session_id: str
    summary_available: bool
    summary: Optional[str] = None
    last_updated: Optional[datetime] = None