# backend/app/services/ai_service.py
"""
AI service layer — the single point of contact with the Google Gemini API.

Phase 4, Lesson 4: Added streaming support via chat_stream().
"""

import logging
from typing import List, Dict, AsyncGenerator

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
        """Convert internal message format to Gemini format."""
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

    def _build_config(
        self,
        system_instruction: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> types.GenerateContentConfig:
        """Build the generation config from parameters."""
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else self.temperature,
            max_output_tokens=max_tokens if max_tokens is not None else self.max_tokens,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        few_shot_examples: List[Dict[str, str]] | None = None,
    ) -> str:
        """Send messages to the LLM and return the full response text."""
        system_instruction, contents = self._translate_messages(messages)

        if few_shot_examples:
            _, example_contents = self._translate_messages(few_shot_examples)
            contents = example_contents + contents

        config = self._build_config(system_instruction, temperature, max_tokens)

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

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream messages to the LLM, yielding text chunks as they arrive.

        This is an async generator — it yields partial text strings.
        The caller is responsible for accumulating the full response.

        Yields:
            Text chunks (e.g., "A ", "binary ", "search ", "tree ")

        Raises:
            AIServiceException: If the API call fails.
        """
        system_instruction, contents = self._translate_messages(messages)
        config = self._build_config(system_instruction, temperature, max_tokens)

        try:
            response_stream = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )

            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        except ClientError as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                logger.error("Gemini rate limit exceeded during stream.")
                raise AIServiceException(
                    message="AI service quota exceeded. Please try again later."
                )
            logger.error("Gemini client error during stream: %s", e)
            raise AIServiceException(
                message=f"AI service error: {e}"
            )

        except ServerError as e:
            logger.error("Gemini server error during stream: %s", e)
            raise AIServiceException(
                message="AI service is temporarily unavailable."
            )

        except Exception as e:
            logger.error("Unexpected error during stream: %s", e)
            raise AIServiceException(
                message="An unexpected error occurred during streaming."
            )