from fastapi import APIRouter

router = APIRouter(
    prefix="/api",
    tags=["documents"]
)

@router.get("/documents")
def get_documents():
    '''
    Retrieve all documents for the user
    '''
    return {
        "documents": [],
        'message': 'This endpoint for retrieving documents. DB is not yet connected',
    }