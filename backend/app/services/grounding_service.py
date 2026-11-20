"""
Grounding Service for Retrieval-Augmented Generation (RAG).
Handles document retrieval, context formatting, and grounded prompt execution.
"""
import logging
from typing import List, Optional
from app.repositories.document_repository import DocumentRepository
from app.services.ai_service import AIService
from app.schemas.grounding import DocumentSnippet, Citation, GroundedChatResponse

logger = logging.getLogger(__name__)

STRICT_GROUNDING_PROMPT = (
    "You are an expert AI Study Assistant.\n"
    "Answer the student's question using ONLY the provided document sources below.\n"
    "If the answer cannot be determined from the sources, state clearly: "
    "\"I cannot find the answer to this question in your uploaded study documents.\"\n"
    "Do NOT use external knowledge when answering under strict grounding."
)

FLEXIBLE_GROUNDING_PROMPT = (
    "You are an expert AI Study Assistant.\n"
    "Answer the student's question primarily using the provided document sources below.\n"
    "You may supplement with external educational knowledge, but prioritize the provided sources and clearly cite them."
)


class GroundingService:
    """Service handling document context retrieval and grounded prompt assembly."""

    def __init__(self, doc_repo: DocumentRepository, ai_service: Optional[AIService] = None):
        self.doc_repo = doc_repo
        self.ai_service = ai_service or AIService()

    async def fetch_document_snippets(
        self, user_id: str, document_ids: List[str]
    ) -> List[DocumentSnippet]:
        """Fetch target document contents from database for a user."""
        snippets: List[DocumentSnippet] = []
        for doc_id in document_ids:
            try:
                doc = await self.doc_repo.get_by_id(document_id=doc_id, user_id=user_id)
                if doc:
                    snippets.append(
                        DocumentSnippet(
                            document_id=doc["document_id"],
                            title=doc.get("title", "Untitled Document"),
                            content=doc.get("content", ""),
                        )
                    )
            except Exception as e:
                logger.warning(f"Could not retrieve document {doc_id} for grounding: {e}")
                continue
        return snippets

    def build_grounded_instruction(
        self, snippets: List[DocumentSnippet], strict_mode: bool = True
    ) -> str:
        """Format document snippets into XML context blocks with instructions."""
        base_prompt = STRICT_GROUNDING_PROMPT if strict_mode else FLEXIBLE_GROUNDING_PROMPT

        if not snippets:
            return f"{base_prompt}\n\n<context_sources>\nNo documents provided.\n</context_sources>"

        formatted_sources = []
        for idx, snippet in enumerate(snippets, start=1):
            formatted_sources.append(
                f"--- SOURCE {idx}: {snippet.title} (ID: {snippet.document_id}) ---\n"
                f"{snippet.content}\n"
            )

        sources_text = "\n".join(formatted_sources)
        return f"{base_prompt}\n\n<context_sources>\n{sources_text}</context_sources>"

    async def generate_grounded_response(
        self,
        user_id: str,
        query: str,
        document_ids: List[str],
        strict_mode: bool = True,
    ) -> GroundedChatResponse:
        """Execute full RAG workflow: fetch docs, build instruction, invoke Gemini."""
        snippets = await self.fetch_document_snippets(user_id=user_id, document_ids=document_ids)
        system_instruction = self.build_grounded_instruction(
            snippets=snippets, strict_mode=strict_mode
        )

        messages = [
            {"role": "user", "content": query}
        ]

        answer = await self.ai_service.chat(
            messages=messages,
            system_instruction=system_instruction,
        )

        citations = [
            Citation(document_id=s.document_id, title=s.title)
            for s in snippets
        ]

        return GroundedChatResponse(
            answer=answer,
            citations=citations,
            grounded=len(snippets) > 0,
        )