from __future__ import annotations

import pytest

from agents.typical_agent import TypicalAgent
from agents.types import AgentResponse, MessageType


@pytest.fixture
def agent() -> TypicalAgent:
    return TypicalAgent()


class TestTypicalAgentGreeting:
    @pytest.mark.asyncio
    async def test_greeting_response(self, agent: TypicalAgent) -> None:
        """Test that greeting returns greeting FAQ response."""
        response = await agent.process("Привет")
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0
        assert "привет" in response.text.lower() or "добро" in response.text.lower()

    @pytest.mark.asyncio
    async def test_greeting_hello_english(self, agent: TypicalAgent) -> None:
        """Test English greeting."""
        response = await agent.process("Hello")
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0

    @pytest.mark.asyncio
    async def test_greeting_with_exclamation(self, agent: TypicalAgent) -> None:
        """Test greeting with punctuation."""
        response = await agent.process("Привет!")
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0


class TestTypicalAgentThanks:
    @pytest.mark.asyncio
    async def test_thanks_response(self, agent: TypicalAgent) -> None:
        """Test that thanks returns thanks FAQ response."""
        response = await agent.process("Спасибо")
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0
        assert "спасибо" in response.text.lower() or "благодар" in response.text.lower()

    @pytest.mark.asyncio
    async def test_thanks_english(self, agent: TypicalAgent) -> None:
        """Test English thanks."""
        response = await agent.process("Thanks")
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0

    @pytest.mark.asyncio
    async def test_thanks_with_punctuation(self, agent: TypicalAgent) -> None:
        """Test thanks with punctuation."""
        response = await agent.process("Спасибо!")
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0


class TestTypicalAgentConfirmation:
    @pytest.mark.asyncio
    async def test_confirmation_response(self, agent: TypicalAgent) -> None:
        """Test that confirmation returns empty/silent response."""
        response = await agent.process("Ок")
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_confirmation_ok_english(self, agent: TypicalAgent) -> None:
        """Test English OK."""
        response = await agent.process("OK")
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_confirmation_good(self, agent: TypicalAgent) -> None:
        """Test confirmation with 'хорошо'."""
        response = await agent.process("Хорошо")
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_confirmation_understood(self, agent: TypicalAgent) -> None:
        """Test confirmation with 'понял'."""
        response = await agent.process("Понял")
        assert response.should_send is False
        assert response.text == ""


class TestTypicalAgentEmptyResponse:
    @pytest.mark.asyncio
    async def test_question_returns_empty(self, agent: TypicalAgent) -> None:
        """Test that questions don't match typical patterns."""
        response = await agent.process("Когда начинается курс?")
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_long_message_returns_empty(self, agent: TypicalAgent) -> None:
        """Test that long messages return empty response."""
        response = await agent.process("Привет, я хочу узнать больше о курсах по Python")
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_unmatched_message_returns_empty(self, agent: TypicalAgent) -> None:
        """Test that unmatched messages return empty response."""
        response = await agent.process("Расскажи мне о курсах")
        assert response.should_send is False
        assert response.text == ""
