import logging

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Documents"],
)


@router.get("/documents")
async def get_documents(
    current_user: dict = Depends(get_current_user),
):
    """
    List all documents uploaded by the current user.

    Async because in Phase 6 this will query MongoDB via Motor.
    """
    logger.info(
        "Fetching documents. user_id=%s",
        current_user["user_id"],
    )

    return {
        "documents": [],
        "total": 0,
        "message": "Documents endpoint ready. File upload coming in Phase 6.",
    }