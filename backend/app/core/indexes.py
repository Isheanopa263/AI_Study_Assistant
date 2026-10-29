# backend/app/core/indexes.py
"""
MongoDB index definitions for all collections.

Indexes are created at application startup via the lifespan handler.
This function is idempotent — safe to call multiple times.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.operations import IndexModel

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create all required indexes for the application."""
    logger.info("Ensuring MongoDB indexes exist...")

    # --- Documents ---
    documents = db["documents"]
    await documents.create_indexes([
        IndexModel(
            [("user_id", ASCENDING)],
            name="idx_documents_user_id",
        ),
        IndexModel(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_documents_user_created",
        ),
        IndexModel(
            [("title", TEXT), ("content", TEXT)],
            name="idx_documents_text_search",
            default_language="english",
        ),
    ])
    logger.info("  ✓ documents indexes created")

    # --- Chat Sessions ---
    chat_sessions = db["chat_sessions"]
    await chat_sessions.create_indexes([
        IndexModel(
            [("user_id", ASCENDING)],
            name="idx_sessions_user_id",
        ),
        IndexModel(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)],
            name="idx_sessions_user_updated",
        ),
    ])
    logger.info("  ✓ chat_sessions indexes created")

    # --- Messages ---
    messages = db["messages"]
    await messages.create_indexes([
        IndexModel(
            [("session_id", ASCENDING), ("created_at", ASCENDING)],
            name="idx_messages_session_created",
        ),
    ])
    logger.info("  ✓ messages indexes created")

    logger.info("All indexes ensured successfully.")