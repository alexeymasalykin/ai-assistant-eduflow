from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.classifier import ClassifierAgent
from agents.types import MessageType


@pytest.fixture
def mock_llm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def classifier(mock_llm: AsyncMock) -> ClassifierAgent:
    return ClassifierAgent(llm_client=mock_llm)


class TestClassifierRuleBased:
    @pytest.mark.asyncio
    async def test_greeting_is_typical(self, classifier: ClassifierAgent) -> None:
        result = await classifier.classify("Привет")
        assert result == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_thanks_is_typical(self, classifier: ClassifierAgent) -> None:
        result = await classifier.classify("Спасибо")
        assert result == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_ok_is_typical(self, classifier: ClassifierAgent) -> None:
        result = await classifier.classify("Ок")
        assert result == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_short_without_question_mark_is_typical(self, classifier: ClassifierAgent) -> None:
        result = await classifier.classify("Понял")
        assert result == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_short_with_question_mark_is_not_typical(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "course"
        result = await classifier.classify("Когда?")
        assert result != MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_long_message_goes_to_llm(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "course"
        result = await classifier.classify("Когда начинается мой курс по Python?")
        assert result == MessageType.COURSE
        mock_llm.generate.assert_called_once()


class TestClassifierLLMFallback:
    @pytest.mark.asyncio
    async def test_llm_returns_course(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "course"
        result = await classifier.classify("Какой статус моей оплаты за курс?")
        assert result == MessageType.COURSE

    @pytest.mark.asyncio
    async def test_llm_returns_platform(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "platform"
        result = await classifier.classify("Не могу войти в личный кабинет, что делать?")
        assert result == MessageType.PLATFORM

    @pytest.mark.asyncio
    async def test_llm_returns_escalate(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "escalate"
        result = await classifier.classify("Хочу вернуть деньги, курс ужасный!")
        assert result == MessageType.ESCALATE

    @pytest.mark.asyncio
    async def test_llm_returns_typical_maps_to_escalate(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "typical"
        result = await classifier.classify("Расскажите подробнее о курсе по аналитике")
        assert result == MessageType.ESCALATE

    @pytest.mark.asyncio
    async def test_llm_returns_unknown_maps_to_escalate(
        self, classifier: ClassifierAgent, mock_llm: AsyncMock
    ) -> None:
        mock_llm.generate.return_value = "something_unexpected"
        result = await classifier.classify("Непонятное сообщение среднего размера")
        assert result == MessageType.ESCALATE
