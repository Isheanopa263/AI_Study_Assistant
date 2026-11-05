# backend/app/services/context_manager.py
"""
Context window management for AI conversations.
Phase 4, Lesson 5: Token-aware history selection and summarization.

Responsibilities:
  - Count tokens accurately using Gemini's API
  - Select the most recent messages that fit within a token budget
  - Summarize old messages when conversations grow too long
"""

import logging
from typing import List, Dict, Tuple

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context to fit within token budgets."""

    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL
        self.max_context_tokens = settings.GEMINI_MAX_CONTEXT_TOKENS
        self.summary_threshold = settings.GEMINI_SUMMARY_THRESHOLD

    async def count_tokens(
        self, messages: List[Dict[str, str]]
    ) -> int:
        """
        Count the total tokens for a list of messages using Gemini's API.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}

        Returns:
            Total token count. Returns 0 if counting fails.
        """
        if not messages:
            return 0

        # Convert to Gemini format for counting
        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg.get("content", ""))],
                )
            )

        try:
            response = await self.client.aio.models.count_tokens(
                model=self.model,
                contents=contents,
            )
            return response.total_tokens or 0
        except Exception as e:
            # Fallback: rough estimate (1 token ≈ 4 chars)
            logger.warning(
                "Token counting failed, using estimate: %s", e
            )
            total_chars = sum(len(m.get("content", "")) for m in messages)
            return total_chars // 4

    async def build_context(
        self,
        history: List[Dict[str, str]],
        system_prompt: str,
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Build the optimal context within the token budget.

        Uses a sliding window: starts from the most recent message and
        adds older messages until the token budget is exhausted.

        If the full history exceeds the summary threshold, old messages
        are summarized and injected into the system prompt.

        Args:
            history: All messages from MongoDB (chronological order).
            system_prompt: The base system instruction.

        Returns:
            A tuple of (selected_messages, enhanced_system_prompt).
        """
        if not history:
            return [], system_prompt

        # Count tokens for the full history
        total_tokens = await self.count_tokens(history)

        # If history fits within budget, use it all
        if total_tokens <= self.max_context_tokens:
            return history, system_prompt

        # History is too large — use sliding window
        logger.info(
            "History exceeds token budget (%d > %d). Applying sliding window.",
            total_tokens,
            self.max_context_tokens,
        )

        selected_messages, dropped_messages = await self._sliding_window(history)

        # If we dropped messages and they're substantial, summarize them
        enhanced_prompt = system_prompt
        if dropped_messages and len(dropped_messages) >= 4:
            summary = await self.summarize_old_messages(dropped_messages)
            if summary:
                enhanced_prompt = (
                    f"{system_prompt}\n\n"
                    f"## Earlier Conversation Summary\n"
                    f"The following is a summary of earlier messages in this "
                    f"conversation that were compressed to save context space:\n\n"
                    f"{summary}"
                )

        return selected_messages, enhanced_prompt

    async def _sliding_window(
        self, history: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Select the most recent messages that fit within the token budget.

        Works backwards from the newest message, adding older messages
        until the budget is full.

        Returns:
            A tuple of (selected_messages, dropped_messages).
        """
        selected = []
        running_tokens = 0

        # Walk backwards from newest to oldest
        for msg in reversed(history):
            msg_tokens = await self.count_tokens([msg])

            if running_tokens + msg_tokens > self.max_context_tokens:
                break

            selected.insert(0, msg)  # Insert at front to maintain order
            running_tokens += msg_tokens

        # Everything not selected was dropped
        selected_ids = set(id(m) for m in selected)
        dropped = [m for m in history if id(m) not in selected_ids]

        logger.info(
            "Sliding window: kept %d messages (%d tokens), "
            "dropped %d messages.",
            len(selected),
            running_tokens,
            len(dropped),
        )

        return selected, dropped

    async def summarize_old_messages(
        self, messages: List[Dict[str, str]]
    ) -> str:
        """
        Summarize a list of old messages into a concise paragraph.

        Uses a separate AI call with a summarization prompt.

        Args:
            messages: The old messages to summarize.

        Returns:
            A summary string, or empty string if summarization fails.
        """
        if not messages:
            return ""

        # Build a condensed version of the conversation for summarization
        conversation_text = "\n".join(
            f"{'Student' if m.get('role') == 'user' else 'Tutor'}: "
            f"{m.get('content', '')[:500]}"  # Truncate long messages
            for m in messages
        )

        summary_prompt = (
            "Summarize the following tutoring conversation in 2-4 sentences. "
            "Focus on: what topics were covered, what the student understood, "
            "and what they struggled with. Do not include specific code examples."
        )

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(
                        text=f"{summary_prompt}\n\n{conversation_text}"
                    )],
                )
            ]

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=200,
                ),
            )

            summary = response.text or ""
            logger.info(
                "Conversation summarized: %d messages → %d chars",
                len(messages),
                len(summary),
            )
            return summary

        except Exception as e:
            logger.warning("Summarization failed: %s", e)
            return ""