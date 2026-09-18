import asyncio
import logging

logger = logging.getLogger(__name__)


async def send_message_notification(
    user_id: str,
    session_id: str,
    message_preview: str,
) -> None:
    """
    Send a notification about a new message.

    Simulated implementation for now.
    In production this would send an email, push notification,
    or webhook depending on user preferences.

    This is designed to run as a background task so the client
    does not wait for the notification to complete.

    Args:
        user_id: The user to notify.
        session_id: The chat session ID.
        message_preview: First 100 chars of the message.
    """
    logger.info(
        "Sending notification. user_id=%s session_id=%s preview=%s",
        user_id,
        session_id,
        message_preview[:100],
    )

    # Simulate network delay for sending notification
    # In production this would be actual email/push service call
    await asyncio.sleep(0.5)

    logger.info(
        "Notification sent successfully. user_id=%s session_id=%s",
        user_id,
        session_id,
    )


async def update_analytics(
    user_id: str,
    event_type: str,
    metadata: dict,
) -> None:
    """
    Track user activity for analytics.

    Simulated implementation for now.
    In production this would send events to an analytics service
    like Segment, Mixpanel, or a custom analytics pipeline.

    Runs as a background task to avoid impacting response time.

    Args:
        user_id: The user performing the action.
        event_type: Type of event, e.g. 'message_sent'.
        metadata: Additional context about the event.
    """
    logger.info(
        "Recording analytics event. user_id=%s event=%s metadata=%s",
        user_id,
        event_type,
        metadata,
    )

    # Simulate analytics service call
    await asyncio.sleep(0.2)

    logger.info(
        "Analytics event recorded. user_id=%s event=%s",
        user_id,
        event_type,
    )