"""
Unit and Integration Tests for Grounding Service & Grounded Endpoint.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from bson import ObjectId

from app.services.grounding_service import (
    GroundingService,
    STRICT_GROUNDING_PROMPT,
    FLEXIBLE_GROUNDING_PROMPT,
)
from app.schemas.grounding import DocumentSnippet


@pytest.mark.asyncio
async def test_build_grounded_instruction_formatting():
    """Verify system instruction string formatting with XML context tags."""
    mock_doc_repo = AsyncMock()
    service = GroundingService(doc_repo=mock_doc_repo)
    snippets = [
        DocumentSnippet(
            document_id="doc123",
            title="Python Fundamentals.pdf",
            content="Python uses indentation to define code blocks.",
        ),
        DocumentSnippet(
            document_id="doc456",
            title="Data Structures.txt",
            content="Arrays provide O(1) random access.",
        ),
    ]

    instruction = service.build_grounded_instruction(snippets, strict_mode=True)

    assert STRICT_GROUNDING_PROMPT in instruction
    assert "<context_sources>" in instruction
    assert "--- SOURCE 1: Python Fundamentals.pdf (ID: doc123) ---" in instruction
    assert "Python uses indentation to define code blocks." in instruction
    assert "--- SOURCE 2: Data Structures.txt (ID: doc456) ---" in instruction


@pytest.mark.asyncio
async def test_build_grounded_instruction_flexible_mode():
    """Verify flexible prompt is selected when strict_mode is False."""
    mock_doc_repo = AsyncMock()
    service = GroundingService(doc_repo=mock_doc_repo)
    snippets = [
        DocumentSnippet(
            document_id="doc1",
            title="Bio.pdf",
            content="Cells are the basic unit of life.",
        )
    ]

    instruction = service.build_grounded_instruction(snippets, strict_mode=False)
    assert FLEXIBLE_GROUNDING_PROMPT in instruction


@pytest.mark.asyncio
@patch("app.api.chat.ai_service.chat", new_callable=AsyncMock)
async def test_grounded_chat_endpoint_success(
    mock_ai_chat,
    client: AsyncClient,
    auth_headers: dict,
    test_db_client,
):
    """Verify POST /api/chat/sessions/{session_id}/grounded endpoint flow."""
    user_id = "stub-user-id"
    db = test_db_client["study_assistant_test"]

    # 1. Create a study session
    session_res = await client.post(
        "/api/chat/sessions",
        json={"title": "Grounded Physics Session"},
        headers=auth_headers,
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]

    # 2. Insert test document directly into DB
    doc_oid = ObjectId()
    doc_id = str(doc_oid)
    await db["documents"].insert_one(
        {
            "_id": doc_oid,
            "user_id": user_id,
            "title": "Quantum Physics Notes.pdf",
            "content": "Schrödinger's cat is a thought experiment in quantum mechanics.",
            "file_type": "pdf",
            "file_size": 1024,
        }
    )

    # 3. Mock AI chat output
    mock_ai_chat.return_value = (
        "According to your notes, Schrödinger's cat is a thought experiment."
    )

    payload = {
        "query": "What is Schrödinger's cat?",
        "document_ids": [doc_id],
        "strict_mode": True,
    }

    # 4. Invoke grounded chat endpoint
    response = await client.post(
        f"/api/chat/sessions/{session_id}/grounded",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert (
        data["answer"]
        == "According to your notes, Schrödinger's cat is a thought experiment."
    )
    assert len(data["citations"]) == 1
    assert data["citations"][0]["document_id"] == doc_id
    assert data["citations"][0]["title"] == "Quantum Physics Notes.pdf"
    assert data["grounded"] is True