from typing import Dict

import pytest
from httpx import AsyncClient


async def test_list_documents_empty_initially(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify documents list is empty on fresh state."""
    # Act
    response = await client.get("/api/documents/", headers=auth_headers)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["documents"] == []


async def test_upload_valid_txt_file(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify uploading a valid .txt file succeeds with 201 and generates metadata."""
    # Arrange
    file_content = b"Introduction to Graph Theory: Vertices and Edges."
    files = {
        "file": ("graph_theory.txt", file_content, "text/plain"),
    }

    # Act
    response = await client.post(
        "/api/documents/upload",
        files=files,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "graph_theory.txt"
    assert data["file_type"] == "txt"
    assert data["file_size"] == len(file_content)
    assert "created_at" in data
    assert "document_id" in data
    assert data["file_size"] == len(file_content)


async def test_upload_invalid_extension_rejected(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify uploading an executable or script file is rejected with 422."""
    # Arrange
    files = {
        "file": ("malicious_script.py", b"import os; os.system('ls')", "text/plain"),
    }

    # Act
    response = await client.post(
        "/api/documents/upload",
        files=files,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "document_processing_error"
    assert "Unsupported file type" in data["message"]


async def test_upload_invalid_mime_type_rejected(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify invalid MIME type is rejected even with a .txt extension."""
    # Arrange
    files = {
        "file": ("data.txt", b'{"key": "value"}', "application/json"),
    }

    # Act
    response = await client.post(
        "/api/documents/upload",
        files=files,
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "Invalid MIME type" in data["message"]


async def test_duplicate_file_upload_returns_existing_record(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify uploading identical content twice returns the existing document record."""
    # Arrange
    file_bytes = b"Identical study notes content for duplicate test."
    files_1 = {"file": ("notes_v1.txt", file_bytes, "text/plain")}
    files_2 = {"file": ("notes_v2.txt", file_bytes, "text/plain")}

    # Act 1: First upload
    res1 = await client.post("/api/documents/upload", files=files_1, headers=auth_headers)
    assert res1.status_code == 201
    doc1 = res1.json()

    # Act 2: Second upload (Identical bytes, different name)
    res2 = await client.post("/api/documents/upload", files=files_2, headers=auth_headers)
    assert res2.status_code == 201
    doc2 = res2.json()

    # Assert: Should return same document ID and checksum
    assert doc1["document_id"] == doc2["document_id"]
    assert doc1["file_type"] == doc2["file_type"]


async def test_get_document_by_id_success(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify retrieving a specific document by its ID."""
    # Arrange: Upload first
    files = {"file": ("discrete_math.txt", b"Sets, Relations, Functions", "text/plain")}
    upload_res = await client.post("/api/documents/upload", files=files, headers=auth_headers)
    doc_id = upload_res.json()["document_id"]

    # Act: Retrieve by ID
    get_res = await client.get(f"/api/documents/{doc_id}", headers=auth_headers)

    # Assert
    assert get_res.status_code == 200
    assert get_res.json()["document_id"] == doc_id
    assert get_res.json()["title"] == "discrete_math.txt"


async def test_get_document_by_id_not_found(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify requesting non-existent document ID returns 404."""
    # Act
    response = await client.get("/api/documents/000000000000000000000000", headers=auth_headers)

    # Assert
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


async def test_delete_document_success(
    client: AsyncClient,
    auth_headers: Dict[str, str],
):
    """Verify deleting an uploaded document returns 204 and removes it from listing."""
    # Arrange: Upload
    files = {"file": ("temp_notes.txt", b"Temporary study notes", "text/plain")}
    upload_res = await client.post("/api/documents/upload", files=files, headers=auth_headers)
    doc_id = upload_res.json()["document_id"]

    # Act: Delete
    del_res = await client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # Assert: Verify it no longer exists
    get_res = await client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert get_res.status_code == 404