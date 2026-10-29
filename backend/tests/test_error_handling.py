# backend/tests/test_error_handling.py
"""Tests for MongoDB error handling and data validation."""

import pytest
from bson import ObjectId
from unittest.mock import AsyncMock, patch
from pymongo.errors import ServerSelectionTimeoutError, DuplicateKeyError

from app.repositories.base import BaseRepository
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    DatabaseException,
)


# ============================================================
# REPOSITORY-LEVEL TESTS (test the actual validation logic)
# ============================================================

class TestObjectIdValidation:
    """Tests for ObjectId validation in BaseRepository._to_object_id()."""

    def test_valid_object_id_converts(self, test_db_client):
        """A valid 24-char hex string should convert to an ObjectId."""
        db = test_db_client["study_assistant_test"]
        repo = BaseRepository(db, "test")

        result = repo._to_object_id("665a1f2e8c3d4b001234abcd")

        assert isinstance(result, ObjectId)
        assert str(result) == "665a1f2e8c3d4b001234abcd"

    def test_garbage_string_raises_validation(self, test_db_client):
        """A non-hex string should raise ValidationException."""
        db = test_db_client["study_assistant_test"]
        repo = BaseRepository(db, "test")

        with pytest.raises(ValidationException) as exc_info:
            repo._to_object_id("not-a-valid-id")

        assert "Invalid ID format" in str(exc_info.value)

    def test_too_short_hex_raises_validation(self, test_db_client):
        """A 12-char hex string is too short for an ObjectId."""
        db = test_db_client["study_assistant_test"]
        repo = BaseRepository(db, "test")

        with pytest.raises(ValidationException):
            repo._to_object_id("abcdef123456")

    def test_empty_string_raises_validation(self, test_db_client):
        """An empty string should raise ValidationException."""
        db = test_db_client["study_assistant_test"]
        repo = BaseRepository(db, "test")

        with pytest.raises(ValidationException):
            repo._to_object_id("")

    def test_none_raises_validation(self, test_db_client):
        """None should raise ValidationException."""
        db = test_db_client["study_assistant_test"]
        repo = BaseRepository(db, "test")

        with pytest.raises(ValidationException):
            repo._to_object_id(None)

    def test_integer_raises_validation(self, test_db_client):
        """A numeric ID should raise ValidationException."""
        db = test_db_client["study_assistant_test"]
        repo = BaseRepository(db, "test")

        with pytest.raises(ValidationException):
            repo._to_object_id(12345)


class TestDocumentRepositoryErrors:
    """Tests for error handling in DocumentRepository."""

    async def test_get_nonexistent_raises_not_found(self, test_db_client):
        """Getting a valid but non-existent ID should raise NotFoundException."""
        from app.repositories.document_repository import DocumentRepository

        db = test_db_client["study_assistant_test"]
        repo = DocumentRepository(db)

        with pytest.raises(NotFoundException):
            await repo.get_by_id("000000000000000000000000", "test-user")

    async def test_get_with_garbage_id_raises_validation(self, test_db_client):
        """Getting a document with a malformed ID should raise ValidationException."""
        from app.repositories.document_repository import DocumentRepository

        db = test_db_client["study_assistant_test"]
        repo = DocumentRepository(db)

        with pytest.raises(ValidationException) as exc_info:
            await repo.get_by_id("garbage-id", "test-user")

        assert "Invalid ID format" in str(exc_info.value)

    async def test_delete_nonexistent_raises_not_found(self, test_db_client):
        """Deleting a non-existent document should raise NotFoundException."""
        from app.repositories.document_repository import DocumentRepository

        db = test_db_client["study_assistant_test"]
        repo = DocumentRepository(db)

        with pytest.raises(NotFoundException):
            await repo.delete("000000000000000000000000", "test-user")

    async def test_delete_with_garbage_id_raises_validation(self, test_db_client):
        """Deleting with a malformed ID should raise ValidationException."""
        from app.repositories.document_repository import DocumentRepository

        db = test_db_client["study_assistant_test"]
        repo = DocumentRepository(db)

        with pytest.raises(ValidationException):
            await repo.delete("not-valid", "test-user")

    async def test_duplicate_key_raises_validation(self, test_db_client):
        """Inserting a duplicate (unique index violation) should raise ValidationException."""
        from app.repositories.document_repository import DocumentRepository

        db = test_db_client["study_assistant_test"]
        repo = DocumentRepository(db)

        # Create a unique index for this test
        await repo.collection.create_index(
            [("user_id", 1), ("title", 1)],
            unique=True,
            name="idx_test_unique_dup",
        )

        doc = {
            "user_id": "test-user-dup",
            "title": "Duplicate Test",
            "file_type": "pdf",
            "file_size": 100,
        }

        # First insert succeeds
        await repo.create(doc)

        # Second insert should raise ValidationException
        with pytest.raises(ValidationException) as exc_info:
            await repo.create(doc)
        assert "already exists" in str(exc_info.value).lower()

        # Cleanup
        await repo.collection.drop_index("idx_test_unique_dup")


# ============================================================
# HTTP-LEVEL TESTS (test the full request → response chain)
# ============================================================

class TestHTTPErrors:
    """
    Integration tests for HTTP error responses.

    Note: These tests verify that errors return clean 4xx responses
    without leaking internal details. The exact status code (400 vs 422)
    depends on where in the dependency chain the validation occurs.
    """

    async def test_invalid_id_does_not_return_500(self, client, auth_headers):
        """A garbage ID should return a client error (4xx), never a 500."""
        response = await client.get(
            "/api/documents/not-a-valid-id",
            headers=auth_headers,
        )

        # Must be a client error, not a server crash
        assert 400 <= response.status_code < 500
        data = response.json()
        assert "detail" in data

    async def test_error_response_does_not_leak_internals(self, client, auth_headers):
        """Error responses should not expose MongoDB internals."""
        response = await client.get(
            "/api/documents/not-a-valid-id",
            headers=auth_headers,
        )

        data = response.json()
        # detail can be a string OR a list (FastAPI 422 returns a list)
        detail = str(data.get("detail", ""))

        # Should NOT contain raw MongoDB/PyMongo details
        assert "E11000" not in detail
        assert "pymongo" not in detail.lower()
        assert "traceback" not in detail.lower()
        assert "bson.errors" not in detail.lower()
    async def test_nonexistent_valid_id_returns_error(self, client, auth_headers):
        """A valid-format but non-existent ObjectId should return 4xx."""
        response = await client.get(
            "/api/documents/000000000000000000000000",
            headers=auth_headers,
        )

        assert 400 <= response.status_code < 500

    async def test_chat_invalid_id_returns_error(self, client, auth_headers):
        """Invalid chat session ID should return 4xx, not 500."""
        response = await client.get(
            "/api/chat/sessions/garbage-string",
            headers=auth_headers,
        )

        assert 400 <= response.status_code < 500