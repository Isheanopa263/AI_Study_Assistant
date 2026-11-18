"""
MongoDB Repository for Chat Operations.
Handles persistence for sessions, messages, and conversation summaries.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository
from app.core.exceptions import DatabaseException, NotFoundException

logger = logging.getLogger(__name__)


class ChatRepository(BaseRepository):
    """Repository handling CRUD operations for chat_sessions and messages collections."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "chat_sessions")
        self.sessions_collection = self.collection
        self.messages_collection = db["messages"]

    async def create_session(self, user_id: str, title: Optional[str] = None) -> Dict:
        """Create a new chat session for a user."""
        now = datetime.utcnow()
        doc = {
            "user_id": user_id,
            "title": title or "New Study Session",
            "summary": None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self.sessions_collection.insert_one(doc)
            doc["_id"] = result.inserted_id
            logger.info(f"Chat session created in DB: id={result.inserted_id} user={user_id}")
            return self._to_str_id(doc, id_field="session_id")
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}", exc_info=True)
            raise DatabaseException(f"Failed to create chat session: {str(e)}")

    async def get_session(self, session_id: str, user_id: str) -> Dict:
        """Retrieve a single chat session verifying user ownership."""
        oid = self._to_object_id(session_id)
        doc = await self.sessions_collection.find_one({"_id": oid, "user_id": user_id})

        if not doc:
            raise NotFoundException("ChatSession", session_id)

        return self._to_str_id(doc, id_field="session_id")

    async def list_sessions(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Dict], int]:
        """List chat sessions owned by user with pagination."""
        query = {"user_id": user_id}
        total = await self.sessions_collection.count_documents(query)

        cursor = (
            self.sessions_collection.find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        formatted = [self._to_str_id(doc, id_field="session_id") for doc in docs]
        return formatted, total

    async def update_summary(self, session_id: str, user_id: str, summary: str) -> Dict:
        """Persist a conversation summary onto a chat session document."""
        oid = self._to_object_id(session_id)
        now = datetime.utcnow()

        result = await self.sessions_collection.find_one_and_update(
            {"_id": oid, "user_id": user_id},
            {"$set": {"summary": summary, "updated_at": now}},
            return_document=True,
        )

        if not result:
            raise NotFoundException("ChatSession", session_id)

        logger.info(f"Session summary updated in DB: session={session_id}")
        return self._to_str_id(result, id_field="session_id")

    async def add_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        tokens_used: int = 0,
    ) -> Dict:
        """Add a message document and update parent session's updated_at timestamp."""
        sess_oid = self._to_object_id(session_id)
        session = await self.sessions_collection.find_one({"_id": sess_oid, "user_id": user_id})
        if not session:
            raise NotFoundException("ChatSession", session_id)

        now = datetime.utcnow()
        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "tokens_used": tokens_used,
            "created_at": now,
        }

        try:
            res = await self.messages_collection.insert_one(doc)
            doc["_id"] = res.inserted_id

            await self.sessions_collection.update_one(
                {"_id": sess_oid},
                {"$set": {"updated_at": now}}
            )

            return self._to_str_id(doc, id_field="message_id")
        except Exception as e:
            logger.error(f"Failed to add message: {e}", exc_info=True)
            raise DatabaseException(f"Failed to add message: {str(e)}")

    async def get_messages(
        self, session_id: str, user_id: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """Get messages for a session in chronological order."""
        await self.get_session(session_id, user_id)

        query = {"session_id": session_id, "user_id": user_id}
        total = await self.messages_collection.count_documents(query)

        cursor = (
            self.messages_collection.find(query)
            .sort("created_at", 1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        formatted = [self._to_str_id(doc, id_field="message_id") for doc in docs]
        return formatted, total

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete session and all associated messages."""
        oid = self._to_object_id(session_id)
        result = await self.sessions_collection.delete_one({"_id": oid, "user_id": user_id})

        if result.deleted_count == 0:
            raise NotFoundException("ChatSession", session_id)

        await self.messages_collection.delete_many({"session_id": session_id})
        logger.info(f"Deleted chat session and messages: session={session_id}")
        return True