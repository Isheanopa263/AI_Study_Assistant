from typing import Optional
from fastapi import Depends, Header, HTTPException, status, Query
from app.schemas.chat import PaginationParams

def get_pagination(
    limit: int = Query(
        default=10, 
        ge=1, le=100, 
        description="Number of items to returned per page"
    ),
    
    page: int = Query(
        default=1, 
        ge=1, 
        description="Page number starting from 1"
    ),
)-> PaginationParams:
    """
    Extracts pagination parameters from the request query string
    Calculates the offset for database queries automatically
    """
    return PaginationParams(limit=limit, page=page)

def get_token_from_header(
    authorization: Optional[str] = Header(
    default=None, 
        description="Authorization token in the format 'Bearer <token>'"
    ),
)-> str:
    """
    Extracts the token from the Authorization header
    Raises an HTTPException (401) if the header is missing or malformed
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format, expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = authorization.split(" ")[1]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is empty",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    
    return token
    
def get_current_user(
    token : str = Depends(get_token_from_header)
)-> dict:
    """
    returns the cuurent authenticated user based on the provided token.
    currently it returns a stub user
    """
    return {
        "user_id": "stub_user_id",
        "name": "Study Student",
        "email": "student@example.com"
    }
    
def get_optional_user(
    authorization: Optional[str] = Header(default=None),
)->Optional[dict]:
    """
    Returns the current user if authenticated, otherwise returns None.
    Does not raise an exception for missing or invalid tokens.
    Useful for endpoints that can be accessed by both authenticated and anonymous users.
    """
    if authorization is None:
        return None
    if not authorization.startswith("Bearer "):
        return None
    
    return {
        "user_id": "stub_user_id",
        "name": "Study Student",
        "email": "student@example.com",
    }