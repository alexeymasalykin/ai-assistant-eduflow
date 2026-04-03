"""LangChain pipeline — parallel implementation of the message processing flow.

Same contract as Orchestrator: process(message, deal_id) → AgentResponse.
Reuses TypicalAgent, sanitize(), prompts, BitrixClient from original code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from agents.classifier import CONFIRMATION_PATTERNS, GREETING_PATTERNS, THANKS_PATTERNS
from agents.types import AgentResponse, MessageType
from agents.typical_agent import TypicalAgent
from langchain_pipeline.chains import CourseChain, PlatformChain
from prompts.classifier import CLASSIFIER_SYSTEM_PROMPT
from utils.sanitize import sanitize_input

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient
    from integrations.llm_client import LLMClient

logger = structlog.get_logger()

VALID_LLM_RESPONSES = {"course", "platform", "escalate"}


class LangChainPipeline:
    """LangChain-based message processing pipeline.

    Drop-in replacement for Orchestrator with the same process() contract.
    """

    def __init__(
        self,
        llm: LLMClient,
        retriever: Any,
        bitrix_client: BitrixClient,
        langfuse_handler: Any | None = None,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._bitrix = bitrix_client
        self._langfuse_handler = langfuse_handler

        self._typical_agent = TypicalAgent()
        self._platform_chain = PlatformChain(llm=llm, retriever=retriever)
        self._course_chain = CourseChain(llm=llm, bitrix=bitrix_client)

    async def process(self, message: str, deal_id: int | None = None) -> AgentResponse:
        sanitized = sanitize_input(message)
        if not sanitized:
            return AgentResponse.silent()

        logger.info("lc_pipeline_process", message_length=len(sanitized))

        typical_response = await self._try_typical(sanitized)
        if typical_response is not None:
            return typical_response

        message_type = await self._classify(sanitized)
        logger.info("lc_pipeline_classified", type=message_type.value)

        if message_type == MessageType.TYPICAL:
            return await self._typical_agent.process(sanitized)
        if message_type == MessageType.PLATFORM:
            return await self._platform_chain.process(sanitized)
        if message_type == MessageType.COURSE:
            return await self._course_chain.process(sanitized, deal_id=deal_id)

        return AgentResponse.escalate()

    async def _classify(self, message: str) -> MessageType:
        response = await self._llm.generate(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT, user_message=message,
        )
        category = response.strip().lower()
        if category in VALID_LLM_RESPONSES:
            return MessageType(category)
        logger.warning("lc_unexpected_category", category=category)
        return MessageType.ESCALATE

    async def _try_typical(self, message: str) -> AgentResponse | None:
        response = await self._typical_agent.process(message)
        if response.should_send:
            return response

        stripped = message.strip()
        if (
            GREETING_PATTERNS.match(stripped)
            or THANKS_PATTERNS.match(stripped)
            or CONFIRMATION_PATTERNS.match(stripped)
        ):
            return response

        return None
