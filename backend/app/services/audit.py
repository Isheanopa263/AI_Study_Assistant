import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def record_audit_log(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
) -> None:
    """
    Record an audit log entry for a user action.

    Audit logs track all significant actions in the system
    for security, compliance, and debugging purposes.

    This runs as a background task so it does not slow down
    the user's response.

    In production, this would write to a dedicated audit
    collection in MongoDB or an external logging service.

    Args:
        user_id: The ID of the user performing the action.
        action: The action performed, e.g. 'chat_session_deleted'.
        resource_type: The type of resource affected, e.g. 'chat_session'.
        resource_id: The ID of the affected resource.
    """
    logger.info(
        "Audit log started. user_id=%s action=%s resource=%s/%s",
        user_id,
        action,
        resource_type,
        resource_id,
    )

    # Simulate writing to audit database
    # In Phase 3, this will be:
    #   await audit_repository.insert({
    #       "user_id": user_id,
    #       "action": action,
    #       "resource_type": resource_type,
    #       "resource_id": resource_id,
    #       "timestamp": datetime.now(timezone.utc),
    #   })
    await asyncio.sleep(0.1)

    logger.info(
        "Audit log recorded. user_id=%s action=%s resource=%s/%s",
        user_id,
        action,
        resource_type,
        resource_id,
    )