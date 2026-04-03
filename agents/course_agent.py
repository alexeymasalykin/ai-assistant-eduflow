from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agents.types import AgentResponse, MessageType
from observability.decorators import observe_if_enabled
from prompts.course_agent import COURSE_AGENT_SYSTEM_PROMPT
from utils.sanitize import sanitize_llm_output

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient
    from integrations.llm_client import LLMClient

logger = structlog.get_logger()


class CourseAgent:
    """Agent for handling course-related questions using Bitrix24 deal context.

    Processes questions about course enrollment, course info, and payment status
    using deal information from Bitrix24 CRM injected into the system prompt.
    """

    def __init__(self, llm: LLMClient, bitrix: BitrixClient) -> None:
        """Initialize CourseAgent with LLM and Bitrix clients.

        Args:
            llm: LLM client (OpenAI or YandexGPT)
            bitrix: Bitrix24 client for deal context retrieval
        """
        self.llm = llm
        self.bitrix = bitrix

    @observe_if_enabled(name="course_agent.process")
    async def process(self, message: str, deal_id: int | None) -> AgentResponse:
        """Process course-related message using deal context.

        Args:
            message: User's incoming message text
            deal_id: Bitrix24 deal ID for context

        Returns:
            AgentResponse with LLM-generated answer, or escalate if deal
            not found, in terminal stage, or LLM returns empty response
        """
        # CourseAgent requires deal_id
        if deal_id is None:
            logger.warning("course_agent_no_deal_id")
            return AgentResponse.escalate()

        # Fetch deal from Bitrix24
        deal = await self.bitrix.get_deal(deal_id)
        if deal is None:
            logger.warning("course_agent_deal_not_found", deal_id=deal_id)
            return AgentResponse.escalate()

        # Check if deal is in terminal stage
        stage_id = deal.get("STAGE_ID")
        stage = self.bitrix.parse_deal_stage(stage_id) if stage_id else None
        if stage and stage.is_terminal:
            logger.info("course_agent_terminal_stage", deal_id=deal_id, stage=stage)
            return AgentResponse.escalate()

        # Format deal context for LLM
        deal_context = self._format_deal_context(deal)

        # Call LLM with deal context injected
        system_prompt = COURSE_AGENT_SYSTEM_PROMPT.format(deal_context=deal_context)
        llm_response = await self.llm.generate(system_prompt=system_prompt, user_message=message)

        # Sanitize and validate response
        sanitized_response = sanitize_llm_output(llm_response)
        if not sanitized_response.strip():
            logger.warning("course_agent_empty_response", deal_id=deal_id)
            return AgentResponse.escalate()

        logger.info("course_agent_response_generated", deal_id=deal_id, length=len(sanitized_response))
        return AgentResponse(
            text=sanitized_response,
            agent_type=MessageType.COURSE,
            should_send=True,
        )

    def _format_deal_context(self, deal: dict) -> str:
        """Format deal information for injection into system prompt.

        Args:
            deal: Deal dict from Bitrix24

        Returns:
            Formatted string with deal context (title, stage, course info, etc.)
        """
        title = deal.get("TITLE", "Unknown course")
        stage_id = deal.get("STAGE_ID", "Unknown")
        contact_id = deal.get("CONTACT_ID", "Unknown")
        sum_amount = deal.get("UF_CRM_SUM", "Unknown")
        comments = deal.get("COMMENTS", "")
        date_create = deal.get("DATE_CREATE", "Unknown")

        context = f"""
Student Deal Information:
- Deal ID: {deal.get("ID")}
- Course: {title}
- Stage: {stage_id}
- Contact ID: {contact_id}
- Payment Amount: {sum_amount}
- Enrollment Date: {date_create}
- Course Details: {comments}
"""
        return context.strip()
