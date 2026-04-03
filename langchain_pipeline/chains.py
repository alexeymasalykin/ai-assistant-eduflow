"""LangChain chains mirroring CourseAgent and PlatformAgent.

Architecture decision (ADR-1): BitrixClient is reused directly instead of
wrapping in a LangChain Tool. LangChain is used where it adds value — RAG
retrieval and prompt chains — not for wrapping working HTTP clients.
Same applies to sanitize(), TypicalAgent, AgentResponse, and prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agents.types import AgentResponse, MessageType
from prompts.course_agent import COURSE_AGENT_SYSTEM_PROMPT
from prompts.platform_agent import PLATFORM_AGENT_SYSTEM_PROMPT
from utils.sanitize import sanitize_llm_output

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient
    from integrations.llm_client import LLMClient

logger = structlog.get_logger()


class PlatformChain:
    """LangChain-based platform support agent with RAG retrieval."""

    def __init__(self, llm: LLMClient, retriever) -> None:
        self._llm = llm
        self._retriever = retriever

    async def process(self, message: str) -> AgentResponse:
        """Process platform question using LangChain retriever + LLM.

        Args:
            message: User's incoming message text

        Returns:
            AgentResponse with answer based on RAG context, or escalate
        """
        docs = await self._retriever.ainvoke(message)

        if not docs:
            logger.warning("lc_platform_no_rag_results", message_length=len(message))
            return AgentResponse.escalate()

        rag_items = []
        for i, doc in enumerate(docs, start=1):
            content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            rag_items.append(f"{i}. {content}")
        rag_context = "\n".join(rag_items)

        system_prompt = PLATFORM_AGENT_SYSTEM_PROMPT.format(rag_context=rag_context)
        llm_response = await self._llm.generate(system_prompt=system_prompt, user_message=message)

        sanitized = sanitize_llm_output(llm_response)
        if not sanitized.strip():
            logger.warning("lc_platform_empty_response")
            return AgentResponse.escalate()

        return AgentResponse(text=sanitized, agent_type=MessageType.PLATFORM, should_send=True)


class CourseChain:
    """LangChain-based course agent with Bitrix24 deal context.

    Architecture decision (ADR-1): Uses BitrixClient directly rather than
    wrapping it in a LangChain Tool.
    """

    def __init__(self, llm: LLMClient, bitrix: BitrixClient) -> None:
        self._llm = llm
        self._bitrix = bitrix

    async def process(self, message: str, deal_id: int | None) -> AgentResponse:
        """Process course question using Bitrix24 deal context + LLM.

        Args:
            message: User's incoming message text
            deal_id: Bitrix24 deal ID for context

        Returns:
            AgentResponse with answer, or escalate if no deal / terminal stage
        """
        if deal_id is None:
            logger.warning("lc_course_no_deal_id")
            return AgentResponse.escalate()

        deal = await self._bitrix.get_deal(deal_id)
        if deal is None:
            logger.warning("lc_course_deal_not_found", deal_id=deal_id)
            return AgentResponse.escalate()

        stage_id = deal.get("STAGE_ID")
        stage = self._bitrix.parse_deal_stage(stage_id) if stage_id else None
        if stage and stage.is_terminal:
            logger.info("lc_course_terminal_stage", deal_id=deal_id, stage=stage)
            return AgentResponse.escalate()

        deal_context = self._format_deal_context(deal)

        system_prompt = COURSE_AGENT_SYSTEM_PROMPT.format(deal_context=deal_context)
        llm_response = await self._llm.generate(system_prompt=system_prompt, user_message=message)

        sanitized = sanitize_llm_output(llm_response)
        if not sanitized.strip():
            logger.warning("lc_course_empty_response", deal_id=deal_id)
            return AgentResponse.escalate()

        return AgentResponse(text=sanitized, agent_type=MessageType.COURSE, should_send=True)

    @staticmethod
    def _format_deal_context(deal: dict) -> str:
        return f"""
Student Deal Information:
- Deal ID: {deal.get("ID")}
- Course: {deal.get("TITLE", "Unknown course")}
- Stage: {deal.get("STAGE_ID", "Unknown")}
- Contact ID: {deal.get("CONTACT_ID", "Unknown")}
- Payment Amount: {deal.get("UF_CRM_SUM", "Unknown")}
- Enrollment Date: {deal.get("DATE_CREATE", "Unknown")}
- Course Details: {deal.get("COMMENTS", "")}
""".strip()
