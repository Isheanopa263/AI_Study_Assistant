# backend/app/api/ai.py
"""
Temporary AI test endpoint.
Phase 4, Lesson 1: Verify Gemini integration works.
Will be replaced by the full chat integration in Lesson 3.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI (Test)"])


class AITestRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        examples=["Explain recursion in simple terms."],
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

class AITestResponse(BaseModel):
    question: str
    answer: str
    model: str


@router.post("/test", response_model=AITestResponse)
async def test_ai(
    req: AITestRequest,
    user: dict = Depends(get_current_user),
):
    """Send a question to the AI and get an answer. For testing only."""
    ai = AIService()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a friendly and patient study tutor. "
                "Explain concepts clearly using simple language and examples. "
                "Keep your answers concise — under 150 words unless the student "
                "asks for more detail."
            ),
        },
        {"role": "user", "content": req.question},
    ]

    answer = await ai.chat(messages)

    return AITestResponse(
        question=req.question,
        answer=answer,
        model=ai.model,
    )