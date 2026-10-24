# app/core/database.py
"""
MongoDB connection management using Motor (async driver).

This module provides:
  - lifespan(): FastAPI lifespan context manager for startup/shutdown
  - get_db(): FastAPI dependency that injects the database instance
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

settings = get_settings()

# Module-level client reference (needed for shutdown)
_client: AsyncIOMotorClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage the MongoDB connection lifecycle.

    STARTUP:  Create Motor client, verify connection, store db in app.state.
    SHUTDOWN: Close the Motor client and release network resources.
    """
    global _client

    # ── STARTUP ──
    print(f"🔌 Connecting to MongoDB at {settings.MONGODB_URI}...")
    _client = AsyncIOMotorClient(settings.MONGODB_URI)

    # Verify the connection actually works (ping the server)
    try:
        await _client.admin.command("ping")
        print(f"✅ Connected to MongoDB! Database: {settings.MONGODB_DB_NAME}")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        # In development, we continue anyway so the app can start.
        # In production, you'd want to raise here and crash the app.
        if not settings.DEBUG:
            raise

    # Store the database object in app.state so endpoints can access it
    app.state.db = _client[settings.MONGODB_DB_NAME]

    yield  # ← App is running. Requests are being served.

    # ── SHUTDOWN ──
    print("🔌 Closing MongoDB connection...")
    if _client is not None:
        _client.close()
    print("✅ MongoDB connection closed.")


async def get_db(request: Request) -> AsyncIOMotorDatabase:
    """
    FastAPI dependency that returns the MongoDB database instance.

    Usage in endpoints:
        @router.get("/messages")
        async def get_messages(db: AsyncIOMotorDatabase = Depends(get_db)):
            messages = await db.messages.find().to_list(100)
    """
    return request.app.state.db