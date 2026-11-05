# backend/app/services/ai_service.py
"""
AI service layer — the single point of contact with the Google Gemini API.

Provider-independent design:
  - MongoDB stores messages as {"role": "user"|"assistant", "content": "..."}
  - This service translates to Gemini's {"role": "user"|"model", "parts": [...]}
  - If you switch providers later, only this file changes.

Phase 4, Lesson 2: Added few-shot example support.
"""

import logging
from typing import List, Dict

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from app.config import get_settings
from app.core.exceptions import AIServiceException

logger = logging.getLogger(__name__)


class AIService:
    """Wraps the Google Gemini client for chat completions."""

    def __init__(self):
        settings = get_settings()

        if not settings.GEMINI_API_KEY:
            logger.warning(
                "GEMINI_API_KEY is not set. AI features will not work."
            )

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL
        self.max_tokens = settings.GEMINI_MAX_TOKENS
        self.temperature = settings.GEMINI_TEMPERATURE

    @staticmethod
    def _translate_messages(
        messages: List[Dict[str, str]],
    ) -> tuple[str | None, list[types.Content]]:
        """
        Convert internal message format to Gemini format.

        Internal (MongoDB):  {"role": "user"|"assistant", "content": "..."}
        Gemini:              {"role": "user"|"model", "parts": [{"text": "..."}]}

        Returns:
            A tuple of (system_instruction, gemini_contents).
        """
        system_instruction = None
        gemini_contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content
            elif role == "assistant":
                gemini_contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=content)],
                    )
                )
            else:
                gemini_contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=content)],
                    )
                )

        return system_instruction, gemini_contents

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        few_shot_examples: List[Dict[str, str]] | None = None,
    ) -> str:
        """
        Send messages to the LLM and return the response text.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.
            few_shot_examples: Optional list of example Q&A pairs to prepend
                               after the system instruction. These teach the
                               model the desired response style by example.

        Returns:
            The model's response as a plain string.

        Raises:
            AIServiceException: If the API call fails.
        """
        system_instruction, contents = self._translate_messages(messages)

        # Insert few-shot examples at the beginning of the conversation
        if few_shot_examples:
            _, example_contents = self._translate_messages(few_shot_examples)
            contents = example_contents + contents

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else self.temperature,
            max_output_tokens=max_tokens if max_tokens is not None else self.max_tokens,
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )

            content_text = response.text or ""
            usage = response.usage_metadata

            logger.info(
                "AI response generated. model=%s prompt_tokens=%s "
                "completion_tokens=%s total_tokens=%s",
                self.model,
                usage.prompt_token_count if usage else "?",
                usage.candidates_token_count if usage else "?",
                usage.total_token_count if usage else "?",
            )

            return content_text

        except ClientError as e:
            error_msg = str(e)
            if "API_KEY_INVALID" in error_msg or "401" in error_msg:
                logger.error("Gemini API key is invalid or expired.")
                raise AIServiceException(
                    message="AI service authentication failed. Check your API key."
                )
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                logger.error("Gemini rate limit or quota exceeded.")
                raise AIServiceException(
                    message="AI service quota exceeded. Please try again later."
                )
            logger.error("Gemini client error: %s", e)
            raise AIServiceException(
                message=f"AI service request error: {e}"
            )

        except ServerError as e:
            logger.error("Gemini server error: %s", e)
            raise AIServiceException(
                message="AI service is temporarily unavailable. Please try again."
            )

        except APIError as e:
            logger.error("Gemini API error: %s", e)
            raise AIServiceException(
                message=f"AI service error: {e}"
            )

        except Exception as e:
            logger.error("Unexpected AI service error: %s", e)
            raise AIServiceException(
                message="An unexpected error occurred while contacting the AI service."
            )