# app/repositories/chat_repository.py
"""
Chat repository backed by MongoDB.

Manages two collections:
  - chat_sessions: One document per conversation
  - messages: One document per message, linked via session_id
"""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class ChatRepository:
    """
    MongoDB-backed repository for chat sessions and messages.

    Manages TWO collections, so it doesn't inherit from BaseRepository.
    Uses BaseRepository's static helpers directly.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.sessions = db["chat_sessions"]
        self.messages = db["messages"]

    # ── SESSIONS ──

    async def create_session(self, user_id: str, title: str | None) -> str:
        """Create a new chat session. Returns the session_id as a string."""
        now = datetime.now(timezone.utc).isoformat()
        session_data = {
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "message_count": 0,
        }
        result = await self.sessions.insert_one(session_data)
        return str(result.inserted_id)

    async def get_session(self, session_id: str) -> dict | None:
        """Get a single session by ID. Returns dict with 'session_id' field."""
        try:
            oid = BaseRepository._to_object_id(session_id)
        except ValueError:
            return None
        doc = await self.sessions.find_one({"_id": oid})
        return BaseRepository._to_str_id(doc, id_field="session_id")

    async def list_sessions(
        self, user_id: str, skip: int = 0, limit: int = 10
    ) -> list[dict]:
        """List sessions for a user, newest first."""
        cursor = (
            self.sessions.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [
            BaseRepository._to_str_id(doc, id_field="session_id") for doc in docs
        ]

    async def count_sessions(self, user_id: str) -> int:
        """Count total sessions for a user."""
        return await self.sessions.count_documents({"user_id": user_id})

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session AND all its messages."""
        try:
            oid = BaseRepository._to_object_id(session_id)
        except ValueError:
            return False

        # Delete messages first
        await self.messages.delete_many({"session_id": session_id})
        # Then delete the session
        result = await self.sessions.delete_one({"_id": oid})
        return result.deleted_count > 0

    # ── MESSAGES ──

    async def add_message(
        self, session_id: str, role: str, content: str
    ) -> dict:
        """
        Add a message to a session.
        Returns the full message dict with 'message_id' field.
        """
        now = datetime.now(timezone.utc).isoformat()
        message_data = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": now,
        }
        result = await self.messages.insert_one(message_data)

        # Update session metadata
        try:
            oid = BaseRepository._to_object_id(session_id)
            await self.sessions.update_one(
                {"_id": oid},
                {
                    "$inc": {"message_count": 1},
                },
            )
        except ValueError:
            pass

        message_data["_id"] = result.inserted_id
        return BaseRepository._to_str_id(message_data, id_field="message_id")

    async def get_messages(
        self, session_id: str, skip: int = 0, limit: int = 100
    ) -> list[dict]:
        """Get messages for a session, oldest first (chronological)."""
        cursor = (
            self.messages.find({"session_id": session_id})
            .sort("created_at", 1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [
            BaseRepository._to_str_id(doc, id_field="message_id") for doc in docs
        ]

    async def count_messages(self, session_id: str) -> int:
        """Count messages in a session."""
        return await self.messages.count_documents({"session_id": session_id})