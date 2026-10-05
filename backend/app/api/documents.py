import logging

from fastapi import APIRouter, Depends, File, Path, UploadFile, status

from app.core.dependencies import get_current_user
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.document_service import DocumentService, document_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Documents"],
)


def get_document_service() -> DocumentService:
    """Dependency provider for DocumentService."""
    return document_service


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List all uploaded study documents",
)
async def get_documents(
    current_user: dict = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Retrieve all study documents uploaded by the authenticated student."""
    docs = await service.list_user_documents(user_id=current_user["user_id"])
    return DocumentListResponse(
        documents=docs,
        total=len(docs),
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details by ID",
)
async def get_document(
    document_id: str = Path(..., description="The unique ID of the document."),
    current_user: dict = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Retrieve metadata for a specific uploaded document."""
    return await service.get_document_by_id(
        document_id=document_id,
        user_id=current_user["user_id"],
    )


@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a study document (PDF, DOCX, TXT)",
)
async def upload_document(
    file: UploadFile = File(..., description="The study document file to upload."),
    current_user: dict = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Upload and validate a study document."""
    logger.info(
        "Upload request received. user_id=%s filename=%s",
        current_user["user_id"],
        file.filename,
    )

    created_doc = await service.process_and_save_upload(
        file=file,
        user_id=current_user["user_id"],
    )

    return created_doc


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded study document",
)
async def delete_document(
    document_id: str = Path(..., description="The unique ID of the document to delete."),
    current_user: dict = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Delete a specific document record."""
    await service.delete_document(
        document_id=document_id,
        user_id=current_user["user_id"],
    )
    return None