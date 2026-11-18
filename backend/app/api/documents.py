"""
API Router for Document Operations (Upload, List, Get, Delete).
"""

import logging
from typing import Any
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.schemas.document import DocumentResponse, DocumentListResponse
from app.schemas.chat import PaginationParams
from app.services.document_service import DocumentService
from app.repositories.document_repository import DocumentRepository
from app.core.dependencies import get_current_user, get_document_repo, get_pagination

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _extract_user_id(user: Any) -> str:
    if isinstance(user, dict):
        return user.get("user_id") or user.get("id") or "stub-user-id"
    return str(user)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def upload_document(
    file: UploadFile = File(...),
    user: Any = Depends(get_current_user),
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Upload and process a document (PDF, TXT, MD)."""
    user_id = _extract_user_id(user)
    service = DocumentService(repo)
    doc = await service.process_and_save_upload(file=file, user_id=user_id)
    return doc


@router.get(
    "/",
    response_model=DocumentListResponse,
    response_model_by_alias=False,
)
async def list_documents(
    pagination: PaginationParams = Depends(get_pagination),
    user: Any = Depends(get_current_user),
    repo: DocumentRepository = Depends(get_document_repo),
):
    """List documents uploaded by authenticated user."""
    user_id = _extract_user_id(user)
    service = DocumentService(repo)
    docs, total = await service.list_user_documents(
        user_id=user_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    page = (pagination.skip // pagination.limit) + 1 if pagination.limit > 0 else 1
    return DocumentListResponse(
        documents=docs,
        total=total,
        page=page,
        limit=pagination.limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    response_model_by_alias=False,
)
async def get_document(
    document_id: str,
    user: Any = Depends(get_current_user),
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Retrieve document metadata by ID."""
    user_id = _extract_user_id(user)
    service = DocumentService(repo)
    return await service.get_document_by_id(document_id=document_id, user_id=user_id)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    user: Any = Depends(get_current_user),
    repo: DocumentRepository = Depends(get_document_repo),
):
    """Delete document by ID."""
    user_id = _extract_user_id(user)
    service = DocumentService(repo)
    await service.delete_document(document_id=document_id, user_id=user_id)
    return None