# backend/app/core/database.py
import logging
from contextlib import asynccontextmanager
from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.core.indexes import ensure_indexes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Application lifespan: startup and shutdown."""
    # --- Startup ---
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    # Verify connection
    await client.admin.command("ping")
    logger.info("MongoDB connected successfully.")

    # Ensure indexes exist
    await ensure_indexes(db)

    app.state.db = db
    app.state.mongo_client = client

    yield

    # --- Shutdown ---
    logger.info("Closing MongoDB connection...")
    client.close()


async def get_db(request: Request):
    """FastAPI dependency to get the database instance."""
    return request.app.state.db