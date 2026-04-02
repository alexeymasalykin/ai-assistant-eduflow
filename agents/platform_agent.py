from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agents.types import AgentResponse, MessageType
from prompts.platform_agent import PLATFORM_AGENT_SYSTEM_PROMPT
from utils.sanitize import sanitize_llm_output

if TYPE_CHECKING:
    from integrations.llm_client import LLMClient
    from integrations.vector_db import VectorDB

logger = structlog.get_logger()


class PlatformAgent:
    """Agent for handling platform technical issues using RAG knowledge base.

    Processes questions about password reset, video playback, certificates, etc.
    using vector database search (RAG) to find relevant documentation, then
    generates response with injected context.
    """

    def __init__(self, llm: LLMClient, vector_db: VectorDB) -> None:
        """Initialize PlatformAgent with LLM and VectorDB clients.

        Args:
            llm: LLM client (OpenAI or YandexGPT)
            vector_db: Vector database for RAG knowledge base search
        """
        self.llm = llm
        self.vector_db = vector_db

    async def process(self, message: str) -> AgentResponse:
        """Process platform technical question using RAG knowledge base.

        Args:
            message: User's incoming message text

        Returns:
            AgentResponse with LLM-generated answer based on knowledge base,
            or escalate if no RAG results found or LLM returns empty response
        """
        # Search knowledge base via vector_db
        rag_results = await self.vector_db.search(message)

        # If no RAG results found, escalate
        if not rag_results:
            logger.warning("platform_agent_no_rag_results", message_length=len(message))
            return AgentResponse.escalate()

        # Format RAG context as numbered list
        rag_context = self._format_rag_context(rag_results)

        # Call LLM with RAG context injected into system prompt
        system_prompt = PLATFORM_AGENT_SYSTEM_PROMPT.format(rag_context=rag_context)
        llm_response = await self.llm.generate(system_prompt=system_prompt, user_message=message)

        # Sanitize and validate response
        sanitized_response = sanitize_llm_output(llm_response)
        if not sanitized_response.strip():
            logger.warning("platform_agent_empty_response", message_length=len(message))
            return AgentResponse.escalate()

        logger.info(
            "platform_agent_response_generated",
            message_length=len(message),
            response_length=len(sanitized_response),
            rag_hits=len(rag_results),
        )
        return AgentResponse(
            text=sanitized_response,
            agent_type=MessageType.PLATFORM,
            should_send=True,
        )

    def _format_rag_context(self, rag_results: list[str]) -> str:
        """Format RAG results as numbered list for injection into system prompt.

        Args:
            rag_results: List of relevant knowledge base chunks

        Returns:
            Formatted string with numbered RAG results
        """
        formatted_items: list[str] = []
        for i, chunk in enumerate(rag_results, start=1):
            # Truncate very long chunks to avoid token overflow
            truncated_chunk = chunk[:300] + "..." if len(chunk) > 300 else chunk
            formatted_items.append(f"{i}. {truncated_chunk}")

        return "\n".join(formatted_items)
