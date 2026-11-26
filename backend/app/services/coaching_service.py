"""
Coaching Service
Location: backend/app/services/coaching_service.py

Orchestrates pedagogical coaching workflows, dynamic instruction formatting,
Gemini structured JSON generation, and multi-turn educational evaluations.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

from app.config import settings
from app.schemas.coaching import (
    CoachingMode,
    CoachingStage,
    CoachingEvaluation,
    CoachingTurnPayload,
    CoachingTurnRequest,
    CoachingTurnResponse,
)
from app.repositories.chat_repository import ChatRepository

logger = logging.getLogger(__name__)


class CoachingService:
    """Service dedicated to interactive educational coaching and multi-turn tutoring workflows."""

    def __init__(self, chat_repo: ChatRepository, client: Optional[genai.Client] = None):
        self.chat_repo = chat_repo
        if client is not None:
            self.client = client
        elif settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            self.client = None

    def build_pedagogical_system_instruction(
        self,
        topic: str,
        mode: CoachingMode,
        stage: CoachingStage,
        target_objectives: List[str],
    ) -> str:
        """Constructs dynamic pedagogical system instructions tailored to the mode and stage."""
        mode_instructions = {
            CoachingMode.SOCRATIC: (
                "PEDAGOGICAL MODE: SOCRATIC TUTOR\n"
                "- Do NOT reveal full answers or solutions directly.\n"
                "- Guide the student using leading questions, scaffolding, and intuitive hints.\n"
                "- If the student is wrong, gently expose the contradiction or misunderstanding."
            ),
            CoachingMode.EXPLANATORY: (
                "PEDAGOGICAL MODE: EXPLANATORY INSTRUCTOR\n"
                "- Deliver crystal-clear, structured explanations using rich analogies and step-by-step breakdowns.\n"
                "- Check for understanding at the end of each major concept."
            ),
            CoachingMode.QUIZ: (
                "PEDAGOGICAL MODE: ACTIVE RECALL QUIZ MASTER\n"
                "- Test the student's retrieval and precision with focused questions.\n"
                "- Grade answers rigorously, provide exact corrections, and follow up with a related question."
            ),
            CoachingMode.REVIEW: (
                "PEDAGOGICAL MODE: CODE & CONCEPT REVIEWER\n"
                "- Analyze the student's work for clarity, edge cases, efficiency, and common misconceptions.\n"
                "- Highlight strengths first, then provide actionable improvements."
            ),
        }

        stage_instructions = {
            CoachingStage.ASSESSMENT: "STAGE: Baseline Assessment. Gauge what the student already knows.",
            CoachingStage.EXPLANATION: "STAGE: Core Explanation. Focus on deep intuition and building mental models.",
            CoachingStage.PRACTICE: "STAGE: Active Practice. Have the student apply the concepts to concrete problems.",
            CoachingStage.SUMMARY: "STAGE: Synthesis & Review. Consolidate key takeaways and self-reflection.",
            CoachingStage.COMPLETED: "STAGE: Mastery Achieved. Celebrate progress and offer advanced exploration paths.",
        }

        objectives_formatted = (
            "\n".join(f"- {obj}" for obj in target_objectives)
            if target_objectives
            else "- Master core concepts and practical applications."
        )

        return (
            f"You are an expert, empathetic AI Study Coach.\n"
            f"TOPIC: {topic}\n\n"
            f"{mode_instructions.get(mode, mode_instructions[CoachingMode.SOCRATIC])}\n\n"
            f"{stage_instructions.get(stage, stage_instructions[CoachingStage.PRACTICE])}\n\n"
            f"LEARNING OBJECTIVES:\n{objectives_formatted}\n\n"
            f"CRITICAL OUTPUT FORMAT:\n"
            f"You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
            f"{{\n"
            f'  "assistant_message": "Conversational text addressing the student directly.",\n'
            f'  "evaluation": {{\n'
            f'    "understanding_score": <integer 1 to 5>,\n'
            f'    "concept_mastered": <boolean>,\n'
            f'    "feedback": "<concise constructive feedback>",\n'
            f'    "hints": ["<hint 1>", "<optional hint 2>"],\n'
            f'    "next_step": "<recommended pedagogical action>"\n'
            f'  }},\n'
            f'  "suggested_replies": ["<quick option 1>", "<quick option 2>", "<quick option 3>"]\n'
            f"}}"
        )

    async def conduct_coaching_turn(
        self,
        session_id: str,
        user_id: str,
        request: CoachingTurnRequest,
    ) -> CoachingTurnResponse:
        """Executes a multi-turn coaching step: fetches history, queries Gemini, parses evaluation, and persists turns."""
        if not self.client:
            raise RuntimeError("Gemini client is not initialized. Ensure GEMINI_API_KEY is configured.")

        # 1. Fetch recent history for multi-turn conversational context
        past_messages_dicts, _ = await self.chat_repo.get_messages(
            session_id=session_id,
            user_id=user_id,
            skip=0,
            limit=10,
        )

        gemini_contents: List[types.Content] = []
        for msg in past_messages_dicts:
            role = "user" if msg.get("role") == "user" else "model"
            content_text = msg.get("content", "")
            if content_text:
                gemini_contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=content_text)]
                    )
                )

        # Append current student message
        gemini_contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=request.message)]
            )
        )

        # 2. Build tailored system instruction
        system_instruction = self.build_pedagogical_system_instruction(
            topic=request.topic,
            mode=request.mode,
            stage=request.stage,
            target_objectives=request.target_objectives,
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
            response_mime_type="application/json",
        )

        # 3. Call Gemini
        try:
            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL or "gemini-2.5-flash",
                contents=gemini_contents,
                config=config,
            )
        except Exception as exc:
            logger.error(f"Error calling Gemini in CoachingService: {exc}")
            raise RuntimeError(f"AI Coaching generation failed: {str(exc)}")

        raw_text = response.text or "{}"
        tokens_used = (
            getattr(response.usage_metadata, "total_token_count", 0)
            if hasattr(response, "usage_metadata")
            else 0
        )

        # Clean markdown code markers if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        # 4. Parse structured JSON payload
        try:
            parsed_data = json.loads(clean_text)
            turn_payload = CoachingTurnPayload.model_validate(parsed_data)
        except Exception as parse_err:
            logger.warning(f"Failed to parse structured coaching JSON: {parse_err}. Raw text: {raw_text}")
            turn_payload = CoachingTurnPayload(
                assistant_message=clean_text if clean_text else "Let's continue reviewing this concept.",
                evaluation=CoachingEvaluation(
                    understanding_score=3,
                    concept_mastered=False,
                    feedback="Continuing review of the current topic.",
                    hints=[],
                    next_step="Proceed with next question.",
                ),
                suggested_replies=["I understand.", "Could you explain further?", "Let's try another problem."],
            )

        # 5. Persist student and coach turns in ChatRepository
        await self.chat_repo.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=request.message,
            tokens_used=0,
        )

        await self.chat_repo.add_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=turn_payload.assistant_message,
            tokens_used=tokens_used,
        )

        return CoachingTurnResponse(
            session_id=session_id,
            mode=request.mode,
            stage=request.stage,
            assistant_message=turn_payload.assistant_message,
            evaluation=turn_payload.evaluation,
            suggested_replies=turn_payload.suggested_replies,
            tokens_used=tokens_used,
        )