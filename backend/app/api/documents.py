"""
Document upload and management endpoints.
Phase 3: Uses MongoDB via DocumentService + DocumentRepository.
"""

import logging

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.dependencies import get_current_user, get_document_repo, get_pagination
from app.core.exceptions import NotFoundException
from app.repositories.document_repository import DocumentRepository
from app.schemas.chat import PaginationParams
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _get_document_service(
    repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentService:
    """Create a DocumentService with the injected repository."""
    return DocumentService(repo=repo)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    response_model_by_alias=False,
    status_code=201,
)
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    service: DocumentService = Depends(_get_document_service),
):
    """Upload a document and store its metadata in MongoDB."""
    result = await service.process_and_save_upload(file, user["user_id"])
    return DocumentResponse(**result)


@router.get(
    "/",
    response_model=DocumentListResponse,
    response_model_by_alias=False,
)
async def list_documents(
    pagination: PaginationParams = Depends(get_pagination),
    user: dict = Depends(get_current_user),
    service: DocumentService = Depends(_get_document_service),
):
    """List all uploaded documents for the current user."""
    docs, total = await service.list_user_documents(
        user["user_id"],
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return DocumentListResponse(
        documents=[DocumentResponse(**doc) for doc in docs],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    response_model_by_alias=False,
)
async def get_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    service: DocumentService = Depends(_get_document_service),
):
    """Get a single document by ID."""
    doc = await service.get_document_by_id(document_id, user["user_id"])
    return DocumentResponse(**doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    service: DocumentService = Depends(_get_document_service),
):
    """Delete a document by ID."""
    await service.delete_document(document_id, user["user_id"])