from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agents.classifier import ClassifierAgent
from agents.course_agent import CourseAgent
from agents.platform_agent import PlatformAgent
from agents.types import AgentResponse, MessageType
from agents.typical_agent import TypicalAgent
from utils.sanitize import sanitize_input

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient
    from integrations.llm_client import LLMClient
    from integrations.vector_db import VectorDB

logger = structlog.get_logger()


class Orchestrator:
    """Main orchestrator that routes messages to appropriate agents.

    Flow:
    1. Sanitize user input
    2. Check if message is FAQ short answer (typical: greeting/thanks/confirmation)
    3. Classify message type using ClassifierAgent (rule-based first, LLM fallback)
    4. Route to appropriate agent (TypicalAgent/CourseAgent/PlatformAgent/ESCALATE)
    5. Return final AgentResponse
    """

    def __init__(
        self,
        llm: LLMClient,
        bitrix: BitrixClient,
        vector_db: VectorDB,
    ) -> None:
        """Initialize Orchestrator with dependencies.

        Args:
            llm: LLM client for classification and generation
            bitrix: Bitrix24 client for deal context
            vector_db: Vector database for RAG knowledge base
        """
        self._llm = llm
        self._bitrix = bitrix
        self._vector_db = vector_db

        # Initialize agents as properties
        self.classifier = ClassifierAgent(llm)
        self.typical_agent = TypicalAgent()
        self.course_agent = CourseAgent(llm, bitrix)
        self.platform_agent = PlatformAgent(llm, vector_db)

    async def process(
        self, message: str, deal_id: int | None = None
    ) -> AgentResponse:
        """Process incoming message and route to appropriate agent.

        Args:
            message: User's incoming message text
            deal_id: Optional Bitrix24 deal ID for course context

        Returns:
            AgentResponse from appropriate agent or escalation response
        """
        # 1. Sanitize input
        sanitized_message = sanitize_input(message)
        if not sanitized_message:
            logger.warning("orchestrator_empty_message")
            return AgentResponse.silent()

        logger.info("orchestrator_process", message_length=len(sanitized_message))

        # 2. Check if FAQ short answer exists (typical: greeting/thanks/confirmation)
        # These are handled by TypicalAgent without classification
        faq_response = await self._try_typical_agent(sanitized_message)
        if faq_response is not None:
            logger.info("orchestrator_faq_short_answer")
            return faq_response

        # 3. Classify message type
        message_type = await self.classifier.classify(sanitized_message)
        logger.info("orchestrator_classified", type=message_type.value)

        # 4. Route to appropriate agent based on classification
        if message_type == MessageType.TYPICAL:
            response = await self.typical_agent.process(sanitized_message)
        elif message_type == MessageType.COURSE:
            response = await self.course_agent.process(
                message=sanitized_message, deal_id=deal_id
            )
        elif message_type == MessageType.PLATFORM:
            response = await self.platform_agent.process(sanitized_message)
        elif message_type == MessageType.ESCALATE:
            response = AgentResponse.escalate()
        else:
            # Fallback for unexpected message type
            logger.warning("orchestrator_unexpected_type", type=message_type.value)
            response = AgentResponse.escalate()

        logger.info(
            "orchestrator_response",
            agent_type=response.agent_type.value,
            should_send=response.should_send,
        )
        return response

    async def _try_typical_agent(self, message: str) -> AgentResponse | None:
        """Try to process message with TypicalAgent (greeting/thanks/confirmation).

        Returns None if message doesn't match typical patterns, indicating
        that classifier should be used.

        Args:
            message: Sanitized user message

        Returns:
            AgentResponse if message matches typical pattern, None otherwise
        """
        response = await self.typical_agent.process(message)

        # TypicalAgent returns silent response for messages that don't match patterns
        # We need to distinguish:
        # - Greeting/Thanks: should_send=True, text filled
        # - Confirmation: should_send=False, text empty (silent)
        # - No match: should_send=False, text empty (silent)
        #
        # So we return the response if it has text (greeting/thanks),
        # OR if the message matches typical patterns (confirmation).
        if response.should_send is True:
            # Has text (greeting/thanks FAQ template matched)
            return response

        # Check if this is a confirmation (silent response from TypicalAgent)
        # We need to check the internal patterns to know if it was matched
        message_stripped = message.strip()
        if self._is_typical_pattern(message_stripped):
            # Confirmation matched (silent)
            return response

        # No typical pattern matched - return None to trigger classification
        return None

    @staticmethod
    def _is_typical_pattern(message: str) -> bool:
        """Check if message matches any typical patterns (greeting/thanks/confirmation).

        Uses canonical patterns from ClassifierAgent.

        Args:
            message: Stripped message text

        Returns:
            True if message matches any typical pattern
        """
        from agents.classifier import (
            CONFIRMATION_PATTERNS,
            GREETING_PATTERNS,
            THANKS_PATTERNS,
        )

        if GREETING_PATTERNS.match(message):
            return True
        if THANKS_PATTERNS.match(message):
            return True
        return bool(CONFIRMATION_PATTERNS.match(message))
