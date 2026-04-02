from __future__ import annotations

import structlog

from agents.classifier import CONFIRMATION_PATTERNS, GREETING_PATTERNS, THANKS_PATTERNS
from agents.types import AgentResponse, MessageType
from prompts.faq_templates import get_faq_response

logger = structlog.get_logger()


class TypicalAgent:
    """Agent for handling simple messages without LLM.

    Processes greetings, thanks, and confirmations.
    Returns FAQ templates for greetings/thanks, silent for confirmations.
    """

    async def process(self, message: str) -> AgentResponse:
        """Process incoming message and return appropriate response.

        Args:
            message: User's incoming message text

        Returns:
            AgentResponse with FAQ text for greetings/thanks,
            or silent response for confirmations/unmatched messages
        """
        message_stripped = message.strip()

        if self._is_greeting(message_stripped):
            logger.info("typical_matched", pattern="greeting")
            faq_text = get_faq_response("greeting")
            return AgentResponse(
                text=faq_text or "",
                agent_type=MessageType.TYPICAL,
                should_send=True,
            )

        if self._is_thanks(message_stripped):
            logger.info("typical_matched", pattern="thanks")
            faq_text = get_faq_response("thanks")
            return AgentResponse(
                text=faq_text or "",
                agent_type=MessageType.TYPICAL,
                should_send=True,
            )

        if self._is_confirmation(message_stripped):
            logger.info("typical_matched", pattern="confirmation")
            return AgentResponse.silent()

        logger.info("typical_no_match")
        return AgentResponse.silent()

    def _is_greeting(self, message: str) -> bool:
        """Check if message is a greeting."""
        return bool(GREETING_PATTERNS.match(message))

    def _is_thanks(self, message: str) -> bool:
        """Check if message is thanks."""
        return bool(THANKS_PATTERNS.match(message))

    def _is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation."""
        return bool(CONFIRMATION_PATTERNS.match(message))
