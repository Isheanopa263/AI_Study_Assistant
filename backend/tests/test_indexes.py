# backend/tests/test_indexes.py
"""Tests for MongoDB index creation and query optimization."""

import pytest
from pymongo import ASCENDING, DESCENDING

from app.core.indexes import ensure_indexes


async def get_query_stage(collection, query: dict) -> str:
    """
    Extract the primary query execution stage from explain().

    Returns 'IXSCAN' if an index was used, 'COLLSCAN' if not.
    """
    explanation = await collection.find(query).explain()
    plan = explanation["queryPlanner"]["winningPlan"]

    # The plan may be nested: FETCH → IXSCAN or just COLLSCAN
    if "inputStage" in plan:
        return plan["inputStage"]["stage"]
    return plan["stage"]


class TestEnsureIndexes:
    """Tests for the ensure_indexes() function."""

    async def test_documents_has_user_id_index(self, test_db_client):
        """documents collection should have an index on user_id."""
        db = test_db_client["study_assistant_test"]
        await ensure_indexes(db)

        indexes = await db["documents"].index_information()
        index_names = list(indexes.keys())

        assert "idx_documents_user_id" in index_names

    async def test_sessions_has_compound_index(self, test_db_client):
        """chat_sessions should have a compound index on user_id + updated_at."""
        db = test_db_client["study_assistant_test"]
        await ensure_indexes(db)

        indexes = await db["chat_sessions"].index_information()
        index_names = list(indexes.keys())

        assert "idx_sessions_user_updated" in index_names

        # Verify the compound index has the right fields
        compound_idx = indexes["idx_sessions_user_updated"]
        keys = compound_idx["key"]
        assert ("user_id", ASCENDING) in keys
        assert ("updated_at", DESCENDING) in keys

    async def test_messages_has_session_created_index(self, test_db_client):
        """messages should have a compound index on session_id + created_at."""
        db = test_db_client["study_assistant_test"]
        await ensure_indexes(db)

        indexes = await db["messages"].index_information()
        index_names = list(indexes.keys())

        assert "idx_messages_session_created" in index_names

    async def test_query_uses_index_not_collscan(self, test_db_client):
        """A query filtering by user_id should use IXSCAN, not COLLSCAN."""
        db = test_db_client["study_assistant_test"]
        await ensure_indexes(db)

        # Insert a test document so the query has something to find
        await db["documents"].insert_one({
            "user_id": "test-user-index",
            "title": "Test",
            "file_type": "pdf",
            "file_size": 100,
        })

        stage = await get_query_stage(
            db["documents"],
            {"user_id": "test-user-index"},
        )

        assert stage == "IXSCAN", (
            f"Expected IXSCAN (index used) but got {stage}. "
            "The query is doing a full collection scan!"
        )

    async def test_ensure_indexes_is_idempotent(self, test_db_client):
        """Calling ensure_indexes() twice should not raise an error."""
        db = test_db_client["study_assistant_test"]

        # Call twice — should not raise
        await ensure_indexes(db)
        await ensure_indexes(db)

        # Verify indexes still exist
        indexes = await db["documents"].index_information()
        assert "idx_documents_user_id" in indexes