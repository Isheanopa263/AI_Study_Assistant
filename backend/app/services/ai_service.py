"""
AI Service layer interacting with Google Gemini API via google-genai SDK.
Hardened with Circuit Breaker, Exponential Backoff Retries, and Model Fallback.
"""
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from app.config import settings
from app.core.exceptions import AIServiceException
from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    retry_with_backoff,
)
from app.services.tools import REGISTERED_GEMINI_TOOLS, execute_registered_tool

logger = logging.getLogger(__name__)


class AIService:
    """Resilient Service wrapper for Google Gemini client operations."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.primary_model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self.fallback_model = getattr(settings, "GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")
        self._client: Optional[genai.Client] = None
        self.circuit_breaker = CircuitBreaker(
            name="GeminiClientCircuitBreaker",
            failure_threshold=3,
            recovery_timeout=30.0,
        )

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
        tools: Optional[List[Any]] = None,
    ) -> types.GenerateContentConfig:
        """Construct GenerateContentConfig with optional overrides and tools."""
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else settings.GEMINI_TEMPERATURE,
            max_output_tokens=max_output_tokens or settings.GEMINI_MAX_TOKENS,
            tools=tools,
        )

    def _translate_messages(
        self, messages: List[Union[Dict[str, Any], types.Content]]
    ) -> List[types.Content]:
        """Convert internal message dicts or Content objects into Gemini Content format."""
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

    async def _execute_generate_content(
        self,
        model_name: str,
        contents: List[types.Content],
        config: types.GenerateContentConfig,
    ) -> Any:
        """Low-level generation call executed inside Circuit Breaker and retry loops."""
        async def _call():
            return await self.client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )

        # Retry on transient ServerErrors (503) or rate limits (429)
        return await retry_with_backoff(
            coroutine_func=_call,
            retriable_exceptions=(ServerError,),
            max_retries=3,
            initial_delay=0.5,
            backoff_factor=2.0,
        )

    async def chat(
        self,
        messages: List[Union[Dict[str, Any], types.Content]],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enable_tools: bool = False,
    ) -> Union[str, Dict[str, Any]]:
        """Send chat messages to Gemini with circuit breaker, retries, and fallback model routing."""
        try:
            formatted_contents = self._translate_messages(messages)
            tools = REGISTERED_GEMINI_TOOLS if enable_tools else None
            config = self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=tools,
            )

            # Circuit-breaker protected execution with primary model
            active_model = self.primary_model
            try:
                response = await self.circuit_breaker.call(
                    self._execute_generate_content,
                    model_name=active_model,
                    contents=formatted_contents,
                    config=config,
                )
            except ClientError as client_err:
                # Quota / Rate limit exhausted -> Attempt fallback model
                if client_err.code == 429 or "RESOURCE_EXHAUSTED" in str(client_err):
                    logger.warning(
                        f"Primary model '{self.primary_model}' exhausted quota. Falling back to '{self.fallback_model}'."
                    )
                    active_model = self.fallback_model
                    response = await self.circuit_breaker.call(
                        self._execute_generate_content,
                        model_name=active_model,
                        contents=formatted_contents,
                        config=config,
                    )
                else:
                    raise client_err

            executed_tool_calls: List[Dict[str, Any]] = []

            # Process function calls if returned by Gemini
            if response.function_calls:
                for function_call in response.function_calls:
                    fn_name = function_call.name
                    fn_args = dict(function_call.args) if function_call.args else {}

                    result = execute_registered_tool(fn_name, fn_args)
                    executed_tool_calls.append(
                        {
                            "tool_name": fn_name,
                            "arguments": fn_args,
                            "result": result,
                        }
                    )

                    function_response_part = types.Part.from_function_response(
                        name=fn_name,
                        response={"result": result},
                    )

                    model_turn = types.Content(
                        role="model",
                        parts=[types.Part.from_function_call(name=fn_name, args=fn_args)],
                    )
                    tool_turn = types.Content(
                        role="user",
                        parts=[function_response_part],
                    )

                    formatted_contents.extend([model_turn, tool_turn])

                final_response = await self.circuit_breaker.call(
                    self._execute_generate_content,
                    model_name=active_model,
                    contents=formatted_contents,
                    config=config,
                )
                answer_text = final_response.text or ""
                return {
                    "answer": answer_text,
                    "tool_calls": executed_tool_calls,
                }

            answer_text = response.text or ""
            if enable_tools:
                return {
                    "answer": answer_text,
                    "tool_calls": executed_tool_calls,
                }
            return answer_text

        except CircuitBreakerOpenException as exc:
            logger.error(f"Circuit Breaker blocked call: {exc}")
            raise AIServiceException("AI Service is temporarily unavailable due to upstream outages. Please retry shortly.")
        except ClientError as exc:
            logger.error(f"Gemini client error (4xx): {exc}")
            if exc.code == 401 or "API_KEY_INVALID" in str(exc):
                raise AIServiceException("Invalid Gemini API Key. Please check configuration.")
            elif exc.code == 429 or "RESOURCE_EXHAUSTED" in str(exc):
                raise AIServiceException("AI service quota exceeded. Please try again later.")
            raise AIServiceException(
                f"AI client error: {exc.message if hasattr(exc, 'message') else str(exc)}"
            )
        except ServerError as exc:
            logger.error(f"Gemini server error (5xx): {exc}")
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
        """Stream chat responses chunk by chunk protected by the circuit breaker."""
        if self.circuit_breaker.state == CircuitBreaker.state.fget(self.circuit_breaker) == "OPEN":
            raise AIServiceException("AI Service is temporarily unavailable. Please retry shortly.")

        try:
            formatted_contents = self._translate_messages(messages)
            config = self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            response_stream = await self.client.aio.models.generate_content_stream(
                model=self.primary_model,
                contents=formatted_contents,
                config=config,
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
            self.circuit_breaker.record_success()
        except Exception as exc:
            self.circuit_breaker.record_failure(exc)
            logger.error(f"Streaming error in AIService: {exc}", exc_info=True)
            raise AIServiceException(f"Streaming error: {str(exc)}")

    def get_resilience_status(self) -> Dict[str, Any]:
        """Returns resilience health metrics and active circuit breaker state."""
        return {
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "circuit_breaker": self.circuit_breaker.get_status(),
        }