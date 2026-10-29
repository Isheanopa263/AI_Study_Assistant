# backend/tests/test_schemas.py
"""Tests for Pydantic + MongoDB schema integration."""

import pytest
from bson import ObjectId
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.base import MongoModel, ObjectIdStr, _convert_object_id


# --- Test Models ---

class SampleDocument(MongoModel):
    """Test model mirroring DocumentResponse structure."""
    id: ObjectIdStr = ""
    user_id: str
    title: str
    file_type: str
    file_size: int
    content: str = ""
    chunk_count: int = 0
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime | None = None


class NestedChild(MongoModel):
    name: str
    value: int


class NestedParent(MongoModel):
    id: ObjectIdStr = ""
    title: str
    child: NestedChild


# --- Test Data ---

SAMPLE_DOCUMENT = {
    "_id": ObjectId("665a1f2e8c3d4b001234abcd"),
    "user_id": "user-123",
    "title": "Test Document",
    "file_type": "pdf",
    "file_size": 1024,
    "content": "Hello world",
    "chunk_count": 1,
    "tags": ["test"],
    "created_at": datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    "updated_at": None,
}


# --- Tests ---

class TestFromMongo:
    """Tests for MongoModel.from_mongo()."""

    def test_converts_object_id_to_string(self):
        """from_mongo() should convert _id (ObjectId) to id (string)."""
        result = SampleDocument.from_mongo(SAMPLE_DOCUMENT)

        assert result is not None
        assert result.id == "665a1f2e8c3d4b001234abcd"
        assert isinstance(result.id, str)

    def test_returns_none_for_none_input(self):
        """from_mongo() should return None when given None."""
        result = SampleDocument.from_mongo(None)
        assert result is None

    def test_handles_nested_documents(self):
        """from_mongo() should correctly parse nested embedded documents."""
        mongo_doc = {
            "_id": ObjectId("665a1f2e8c3d4b001234abcd"),
            "title": "Parent",
            "child": {"name": "child1", "value": 42},
        }
        result = NestedParent.from_mongo(mongo_doc)

        assert result is not None
        assert result.title == "Parent"
        assert result.child.name == "child1"
        assert result.child.value == 42

    def test_does_not_mutate_original_dict(self):
        """from_mongo() should not modify the input dict."""
        original = dict(SAMPLE_DOCUMENT)
        SampleDocument.from_mongo(SAMPLE_DOCUMENT)

        assert "_id" in SAMPLE_DOCUMENT
        assert "id" not in SAMPLE_DOCUMENT
        assert SAMPLE_DOCUMENT == original

    def test_preserves_all_fields(self):
        """from_mongo() should preserve all document fields."""
        result = SampleDocument.from_mongo(SAMPLE_DOCUMENT)

        assert result.user_id == "user-123"
        assert result.title == "Test Document"
        assert result.file_type == "pdf"
        assert result.file_size == 1024
        assert result.tags == ["test"]
        assert result.updated_at is None


class TestToMongo:
    """Tests for MongoModel.to_mongo()."""

    def test_excludes_none_values(self):
        """to_mongo() should omit fields with None values by default."""
        model = SampleDocument.from_mongo(SAMPLE_DOCUMENT)
        result = model.to_mongo()

        assert "updated_at" not in result
        assert "title" in result

    def test_excludes_id_fields(self):
        """to_mongo() should not include id/document_id/session_id fields."""
        model = SampleDocument.from_mongo(SAMPLE_DOCUMENT)
        result = model.to_mongo()

        assert "id" not in result
        assert "_id" not in result

    def test_includes_none_when_requested(self):
        """to_mongo(exclude_none=False) should include None values."""
        model = SampleDocument.from_mongo(SAMPLE_DOCUMENT)
        result = model.to_mongo(exclude_none=False)

        assert "updated_at" in result
        assert result["updated_at"] is None


class TestObjectIdStr:
    """Tests for the ObjectIdStr custom type."""

    def test_accepts_valid_object_id_string(self):
        """ObjectIdStr should accept a valid 24-char hex string."""
        model = SampleDocument(
            id="665a1f2e8c3d4b001234abcd",
            user_id="u1",
            title="T",
            file_type="pdf",
            file_size=1,
            created_at=datetime.now(timezone.utc),
        )
        assert model.id == "665a1f2e8c3d4b001234abcd"

    def test_accepts_object_id_instance(self):
        """ObjectIdStr should accept an actual ObjectId instance."""
        oid = ObjectId()
        model = SampleDocument(
            id=oid,
            user_id="u1",
            title="T",
            file_type="pdf",
            file_size=1,
            created_at=datetime.now(timezone.utc),
        )
        assert model.id == str(oid)

    def test_rejects_invalid_string(self):
        """ObjectIdStr should reject strings that aren't valid ObjectIds."""
        with pytest.raises(ValidationError):
            SampleDocument(
                id="not-a-valid-object-id",
                user_id="u1",
                title="T",
                file_type="pdf",
                file_size=1,
                created_at=datetime.now(timezone.utc),
            )


class TestRoundTrip:
    """Tests for MongoDB → Pydantic → MongoDB round-trip fidelity."""

    def test_round_trip_preserves_data(self):
        """Data should survive a full round-trip conversion."""
        # MongoDB → Pydantic
        model = SampleDocument.from_mongo(SAMPLE_DOCUMENT)

        # Pydantic → MongoDB
        mongo_dict = model.to_mongo()

        # Verify key fields survived
        assert mongo_dict["user_id"] == "user-123"
        assert mongo_dict["title"] == "Test Document"
        assert mongo_dict["file_type"] == "pdf"
        assert mongo_dict["file_size"] == 1024
        assert mongo_dict["tags"] == ["test"]
        assert mongo_dict["chunk_count"] == 1

    def test_from_mongo_list(self):
        """from_mongo_list() should convert multiple documents."""
        docs = [SAMPLE_DOCUMENT, SAMPLE_DOCUMENT, None]
        results = SampleDocument.from_mongo_list(docs)

        assert len(results) == 2  # None is filtered out
        assert all(isinstance(r, SampleDocument) for r in results)