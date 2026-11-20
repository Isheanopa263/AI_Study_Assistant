"""
Pydantic Schemas for Grounded RAG Chat Operations.
"""
from typing import List
from pydantic import BaseModel, Field


class DocumentSnippet(BaseModel):
    """Retrieved document fragment used for prompt context."""
    document_id: str = Field(..., description="Unique document string ID")
    title: str = Field(..., description="Document file or display title")
    content: str = Field(..., description="Extracted textual content of the document")


class Citation(BaseModel):
    """Citation metadata returned in grounded responses."""
    document_id: str = Field(..., description="Referenced document ID")
    title: str = Field(..., description="Referenced document title")


class GroundedChatRequest(BaseModel):
    """Payload for submitting a grounded study query against uploaded documents."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The student's study query",
        examples=["What is the mechanism of action of action potentials?"]
    )
    document_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of document IDs to retrieve context from"
    )
    strict_mode: bool = Field(
        default=True,
        description="If True, AI answers ONLY from provided context. If False, allows general supplement."
    )


class GroundedChatResponse(BaseModel):
    """Response structure for grounded RAG query."""
    answer: str = Field(..., description="AI-generated grounded answer")
    citations: List[Citation] = Field(default_factory=list, description="Source documents cited")
    grounded: bool = Field(..., description="True if document context was successfully attached")