"""
AI Service layer interacting with Google Gemini API via google-genai SDK.
Handles text generation, streaming, token counting, and error translation.
"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from app.config import settings
from app.core.exceptions import AIServiceException

logger = logging.getLogger(__name__)


class AIService:
    """Service wrapper for Google Gemini client operations."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL or "gemini-3.5-flash"
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Lazy initialization of google-genai client."""
        if self._client is None:
            if not self.api_key:
                logger.warning("GEMINI_API_KEY is empty. AI operations will fail.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_config(
        self,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> types.GenerateContentConfig:
        """Construct GenerateContentConfig with optional overrides."""
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else settings.GEMINI_TEMPERATURE,
            max_output_tokens=max_output_tokens or settings.GEMINI_MAX_TOKENS,
        )

    def _translate_messages(
        self, messages: List[Union[Dict[str, Any], types.Content]]
    ) -> List[types.Content]:
        """Convert list of internal message dicts or Content objects into Gemini Content format."""
        formatted: List[types.Content] = []
        for msg in messages:
            if isinstance(msg, types.Content):
                formatted.append(msg)
            elif isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                gemini_role = "model" if role == "assistant" else "user"
                formatted.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part(text=content)]
                    )
                )
        return formatted

    async def chat(
        self,
        messages: List[Union[Dict[str, Any], types.Content]],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send chat messages to Gemini and return text response."""
        try:
            formatted_contents = self._translate_messages(messages)
            config = self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=formatted_contents,
                config=config,
            )

            if not response.text:
                raise AIServiceException("Gemini returned empty response text.")

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                logger.info(
                    f"AI response generated. model={self.model_name} "
                    f"prompt_tokens={getattr(usage, 'prompt_token_count', 0)} "
                    f"completion_tokens={getattr(usage, 'candidates_token_count', 0)} "
                    f"total_tokens={getattr(usage, 'total_token_count', 0)}"
                )

            return response.text

        except ClientError as exc:
            logger.error(f"Gemini client error (4xx): {exc}")
            if exc.code == 401 or "API_KEY_INVALID" in str(exc):
                raise AIServiceException("Invalid Gemini API Key. Please check configuration.")
            elif exc.code == 429 or "RESOURCE_EXHAUSTED" in str(exc):
                raise AIServiceException("AI service quota exceeded. Please try again later.")
            raise AIServiceException(f"AI client error: {exc.message if hasattr(exc, 'message') else str(exc)}")

        except ServerError as exc:
            logger.error(f"Gemini server error: {exc}")
            raise AIServiceException("AI service is temporarily unavailable. Please try again.")

        except APIError as exc:
            logger.error(f"Gemini API error: {exc}")
            raise AIServiceException(f"AI service error: {str(exc)}")

        except AIServiceException:
            raise

        except Exception as exc:
            logger.error(f"Unexpected AI error: {exc}", exc_info=True)
            raise AIServiceException(f"AI service error: {str(exc)}")

    async def chat_stream(
        self,
        messages: List[Union[Dict[str, Any], types.Content]],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses chunk by chunk from Gemini."""
        try:
            formatted_contents = self._translate_messages(messages)
            config = self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            response_stream = await self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=formatted_contents,
                config=config,
            )

            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        except (ClientError, ServerError, APIError) as exc:
            logger.error(f"Error during Gemini response streaming: {exc}")
            raise AIServiceException(f"Streaming error: {str(exc)}")
        except Exception as exc:
            logger.error(f"Unexpected error in chat_stream: {exc}", exc_info=True)
            raise AIServiceException(f"Streaming error: {str(exc)}")