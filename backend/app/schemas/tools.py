"""
Pydantic Schemas for Tool Execution and Function Calling Operations.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCallDetail(BaseModel):
    """Details of a tool call executed during an AI turn."""
    tool_name: str = Field(..., description="Name of the function called")
    arguments: Dict[str, Any] = Field(..., description="Arguments passed to the function")
    result: Dict[str, Any] = Field(..., description="Result returned by the backend tool")


class ToolChatRequest(BaseModel):
    """Payload for submitting a prompt to the tool-augmented AI model."""
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User query that may trigger function calls",
        examples=["I scored 18 out of 20 on my Biology quiz. What is my percentage and grade?"]
    )


class ToolChatResponse(BaseModel):
    """Response returned from a tool-augmented chat execution."""
    answer: str = Field(..., description="Final natural language answer from Gemini")
    tool_calls: List[ToolCallDetail] = Field(
        default_factory=list,
        description="List of backend tools executed to fulfill the request"
    )
    tokens_used: int = Field(default=0, description="Estimated token count")