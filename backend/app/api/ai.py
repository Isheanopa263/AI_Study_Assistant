# backend/app/api/ai.py
"""
AI test endpoint with improved tutor persona.
Phase 4, Lesson 2: Prompt engineering — system prompt + few-shot examples.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.services.ai_service import AIService
from app.services.prompts import TUTOR_SYSTEM_PROMPT, TUTOR_FEW_SHOT_EXAMPLES
from app.services.prompts import QUIZ_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI (Test)"])


class AITestRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1, 
        max_length=2000)
    use_chain_of_thought: bool = False


class AITestResponse(BaseModel):
    question: str
    answer: str
    model: str

class QuizRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    num_questions: int = Field(default=3, ge=1, le=5)
    difficulty: str = Field(default="intermediate")

class QuizResponse(BaseModel):
    topic: str
    quiz_text: str
    model: str

@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz(
    req: QuizRequest,
    user: dict = Depends(get_current_user),
):
    ai = AIService()
    system_prompt = QUIZ_SYSTEM_PROMPT.format(
        num_questions=req.num_questions,
        difficulty=req.difficulty,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate a quiz about: {req.topic}"},
    ]
    quiz_text = await ai.chat(messages, temperature=0.5)
    return QuizResponse(
        topic=req.topic,
        quiz_text=quiz_text,
        model=ai.model,
    )
    
    
@router.post("/test", response_model=AITestResponse)
async def test_ai(
    req: AITestRequest,
    user: dict = Depends(get_current_user),
):
    """Send a question to the AI tutor. For testing only."""
    ai = AIService()
    user_content = req.question
    if req.use_chain_of_thought:
        user_content += "\n\nThink step by step before answering."

    messages = [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    answer = await ai.chat(
        messages,
        few_shot_examples=TUTOR_FEW_SHOT_EXAMPLES,
    )

    return AITestResponse(
        question=req.question,
        answer=answer,
        model=ai.model,
    )