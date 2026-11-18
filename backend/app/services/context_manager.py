"""
Context Window & Conversation Memory Manager.
Handles token counting, sliding windows, and memory synthesis.
"""

import logging
from typing import Dict, List, Optional
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages chat context token budgeting, sliding window trimming, and memory injection."""

    def __init__(
        self,
        max_context_tokens: int = settings.GEMINI_MAX_CONTEXT_TOKENS,
        max_history_messages: int = settings.GEMINI_MAX_HISTORY_MESSAGES,
    ):
        self.max_context_tokens = max_context_tokens
        self.max_history_messages = max_history_messages

    def estimate_tokens(self, text: str) -> int:
        """Fast heuristic token estimator (~4 chars per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def estimate_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate total tokens across a list of message dicts."""
        return sum(self.estimate_tokens(m.get("content", "")) for m in messages)

    def build_context(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        summary: Optional[str] = None,
    ) -> List[types.Content]:
        """
        Build optimized context window from history messages and optional session summary.

        1. Injects session summary into system prompt/context if available.
        2. Applies sliding window trim based on message count and token limit constraints.
        3. Returns formatted list of google.genai types.Content objects.
        """
        # Trim history using sliding window
        trimmed_messages = self._sliding_window(messages)

        # Convert to Gemini Content models
        contents: List[types.Content] = []
        for msg in trimmed_messages:
            role = msg.get("role", "user")
            content_text = msg.get("content", "")

            # Translate internal "assistant" role to Gemini "model" role
            gemini_role = "model" if role == "assistant" else "user"

            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=content_text)]
                )
            )

        logger.debug(
            f"Built context window: original_messages={len(messages)} "
            f"included_messages={len(contents)} has_summary={bool(summary)}"
        )
        return contents

    def build_system_instruction(
        self,
        base_system_prompt: str,
        summary: Optional[str] = None
    ) -> str:
        """
        Combine system prompt with conversation summary context if present.
        """
        if not summary:
            return base_system_prompt

        augmented_prompt = (
            f"{base_system_prompt}\n\n"
            f"--- CONVERSATION HISTORY SUMMARY ---\n"
            f"The following is a condensed summary of prior interactions in this session:\n"
            f"{summary}\n"
            f"Use this context to maintain continuity while prioritizing recent user input."
        )
        return augmented_prompt

    def _sliding_window(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Apply message count limit and token threshold slicing."""
        if not messages:
            return []

        # Message count cap
        window = messages[-self.max_history_messages:]

        # Token cap budget trimming
        total_tokens = self.estimate_messages_tokens(window)
        while window and total_tokens > self.max_context_tokens:
            removed = window.pop(0)
            total_tokens -= self.estimate_tokens(removed.get("content", ""))

        return window

    def should_trigger_summarization(
        self,
        messages_count: int,
        threshold: int = 10
    ) -> bool:
        """Determine if conversation length warrants generating a new summary."""
        return messages_count >= threshold