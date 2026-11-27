"""
Background task worker service for asynchronous AI and database jobs.
All functions in this module must handle internal exceptions gracefully
to avoid terminating the main ASGI worker process.
"""

import logging
from google import genai
from google.genai import types

from app.config import settings
from app.repositories.chat_repository import ChatRepository

logger = logging.getLogger("study_assistant.background")


async def generate_session_summary_task(
    session_id: str,
    user_id: str,
    chat_repo: ChatRepository,
) -> None:
    """
    Background worker function that compiles chat history, requests a structured
    pedagogical summary from Gemini, and stores it in the ChatRepository.
    """
    logger.info("Starting background summary for session: %s (user: %s)", session_id, user_id)

    try:
        # 1. Fetch the conversation messages from the repository
        messages, _ = await chat_repo.get_messages(
            session_id=session_id,
            user_id=user_id,
            skip=0,
            limit=100
        )

        if not messages:
            logger.warning("No messages found for session %s. Skipping summary.", session_id)
            return

        # 2. Format conversation into a clear dialogue transcript
        transcript_lines = []
        for msg in messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            transcript_lines.append(f"{role}: {content}")
        transcript = "\n".join(transcript_lines)

        # 3. Formulate the summarization prompt for the AI
        prompt = (
            "You are an expert pedagogical summarizer. Analyze the following study session transcript "
            "between a student and an AI tutor. Provide a concise, highly structured study summary.\n\n"
            "Include:\n"
            "1. Key Concepts Covered\n"
            "2. Student Strengths Identified\n"
            "3. Areas Needing Review\n\n"
            f"--- TRANSCRIPT ---\n{transcript}\n--- END TRANSCRIPT ---"
        )

        # 4. Invoke Google Gemini API asynchronously
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=500
            )
        )

        summary_text = response.text.strip() if response.text else "No summary generated."

        # 5. Persist the generated summary directly into MongoDB
        await chat_repo.update_summary(
            session_id=session_id,
            user_id=user_id,
            summary=summary_text
        )

        logger.info("Successfully completed and saved summary for session: %s", session_id)

    except Exception as exc:
        # Never re-raise raw exceptions in background tasks without logging.
        # Background exceptions do not return to the client; logging is mandatory.
        logger.error("Failed to generate background summary for session %s: %s", session_id, str(exc), exc_info=True)