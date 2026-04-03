from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from agents.types import MessageType
from observability.decorators import observe_if_enabled
from prompts.classifier import CLASSIFIER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from integrations.llm_client import LLMClient

logger = structlog.get_logger()

MAX_TYPICAL_LENGTH = 60

GREETING_PATTERNS = re.compile(
    r"^(привет|здравствуй|добрый\s+(день|вечер|утро)|hi|hello|хай)\s*[!.]?$",
    re.IGNORECASE,
)
THANKS_PATTERNS = re.compile(
    r"^(спасибо|благодарю|спс|thanks|thank you)\s*[!.]?$",
    re.IGNORECASE,
)
CONFIRMATION_PATTERNS = re.compile(
    r"^(ок|ok|хорошо|понял|принял|ладно|ясно|понятно|да|ага|угу)\s*[!.]?$",
    re.IGNORECASE,
)

VALID_LLM_RESPONSES = {"course", "platform", "escalate"}


class ClassifierAgent:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    @observe_if_enabled(name="classifier.classify")
    async def classify(self, message: str) -> MessageType:
        message_stripped = message.strip()
        if self._is_typical(message_stripped):
            logger.info("classified", type="typical", method="rule_based")
            return MessageType.TYPICAL
        return await self._classify_with_llm(message_stripped)

    def _is_typical(self, message: str) -> bool:
        if "?" in message:
            return False
        if len(message) > MAX_TYPICAL_LENGTH:
            return False
        if GREETING_PATTERNS.match(message):
            return True
        if THANKS_PATTERNS.match(message):
            return True
        return bool(CONFIRMATION_PATTERNS.match(message))

    async def _classify_with_llm(self, message: str) -> MessageType:
        response = await self._llm_client.generate(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            user_message=message,
        )
        category = response.strip().lower()
        logger.info("classified", type=category, method="llm")
        if category in VALID_LLM_RESPONSES:
            return MessageType(category)
        logger.warning("llm_unexpected_category", category=category, fallback="escalate")
        return MessageType.ESCALATE
