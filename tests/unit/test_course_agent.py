from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.course_agent import CourseAgent
from agents.types import AgentResponse, MessageType
from integrations.bitrix_client import BitrixClient, DealStage
from integrations.llm_client import LLMClient


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM client."""
    return AsyncMock(spec=LLMClient)


@pytest.fixture
def mock_bitrix() -> AsyncMock:
    """Mock Bitrix client."""
    return AsyncMock(spec=BitrixClient)


@pytest.fixture
def agent(mock_llm: AsyncMock, mock_bitrix: AsyncMock) -> CourseAgent:
    """Create CourseAgent with mocked dependencies."""
    return CourseAgent(llm=mock_llm, bitrix=mock_bitrix)


@pytest.fixture
def valid_deal() -> dict:
    """Realistic deal dict with course enrollment info."""
    return {
        "ID": "123",
        "TITLE": "Python для начинающих",
        "STAGE_ID": "LEARNING",
        "CONTACT_ID": "456",
        "UF_CRM_SUM": "5000.00",
        "COMMENTS": "Курс: Основы Python. Начало: 2026-04-15. Доступ на 3 месяца.",
        "DATE_CREATE": "2026-03-01",
    }


class TestCourseAgentWithValidDeal:
    @pytest.mark.asyncio
    async def test_with_valid_deal(
        self, agent: CourseAgent, mock_llm: AsyncMock, mock_bitrix: AsyncMock, valid_deal: dict
    ) -> None:
        """Test CourseAgent with valid deal context injected into system prompt."""
        # Setup
        mock_bitrix.get_deal.return_value = valid_deal
        mock_bitrix.parse_deal_stage.return_value = DealStage.LEARNING
        mock_llm.generate.return_value = "Ваш курс начинается 15 апреля. Доступ на 3 месяца."

        # Execute
        user_message = "Когда начинается мой курс?"
        response = await agent.process(message=user_message, deal_id=123)

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.COURSE
        assert response.should_send is True
        assert len(response.text) > 0
        assert "начинается" in response.text or "апреля" in response.text

        # Verify that Bitrix was called
        mock_bitrix.get_deal.assert_called_once_with(123)

        # Verify that LLM was called with course context
        mock_llm.generate.assert_called_once()
        call_kwargs = mock_llm.generate.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "deal_context" not in system_prompt  # Placeholder should be replaced
        assert "Python" in system_prompt or "LEARNING" in system_prompt


class TestCourseAgentWithoutDeal:
    @pytest.mark.asyncio
    async def test_without_deal(
        self, agent: CourseAgent, mock_bitrix: AsyncMock
    ) -> None:
        """Test CourseAgent escalates when deal not found."""
        # Setup
        mock_bitrix.get_deal.return_value = None

        # Execute
        response = await agent.process(message="Когда начинается курс?", deal_id=999)

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
        assert response.text == ""

        # Verify Bitrix was called
        mock_bitrix.get_deal.assert_called_once_with(999)


class TestCourseAgentWithTerminalStage:
    @pytest.mark.asyncio
    async def test_with_terminal_stage(
        self, agent: CourseAgent, mock_bitrix: AsyncMock, valid_deal: dict
    ) -> None:
        """Test CourseAgent escalates if deal in terminal stage."""
        # Setup - modify deal to be in terminal stage
        completed_deal = {**valid_deal, "STAGE_ID": "COMPLETED"}
        mock_bitrix.get_deal.return_value = completed_deal
        mock_bitrix.parse_deal_stage.return_value = DealStage.COMPLETED

        # Execute
        response = await agent.process(message="Вопрос о курсе", deal_id=123)

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_with_rejected_stage(
        self, agent: CourseAgent, mock_bitrix: AsyncMock, valid_deal: dict
    ) -> None:
        """Test CourseAgent escalates when deal is rejected."""
        # Setup
        rejected_deal = {**valid_deal, "STAGE_ID": "REJECTED"}
        mock_bitrix.get_deal.return_value = rejected_deal
        mock_bitrix.parse_deal_stage.return_value = DealStage.REJECTED

        # Execute
        response = await agent.process(message="Вопрос о курсе", deal_id=123)

        # Verify
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_with_refund_stage(
        self, agent: CourseAgent, mock_bitrix: AsyncMock, valid_deal: dict
    ) -> None:
        """Test CourseAgent escalates when deal is in refund."""
        # Setup
        refund_deal = {**valid_deal, "STAGE_ID": "REFUND"}
        mock_bitrix.get_deal.return_value = refund_deal
        mock_bitrix.parse_deal_stage.return_value = DealStage.REFUND

        # Execute
        response = await agent.process(message="Вопрос о курсе", deal_id=123)

        # Verify
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False


class TestCourseAgentWithEmptyResponse:
    @pytest.mark.asyncio
    async def test_with_empty_response(
        self, agent: CourseAgent, mock_llm: AsyncMock, mock_bitrix: AsyncMock, valid_deal: dict
    ) -> None:
        """Test CourseAgent escalates if LLM returns empty response."""
        # Setup
        mock_bitrix.get_deal.return_value = valid_deal
        mock_bitrix.parse_deal_stage.return_value = DealStage.LEARNING
        mock_llm.generate.return_value = ""  # Empty response

        # Execute
        response = await agent.process(message="Какой-то вопрос", deal_id=123)

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_with_whitespace_only_response(
        self, agent: CourseAgent, mock_llm: AsyncMock, mock_bitrix: AsyncMock, valid_deal: dict
    ) -> None:
        """Test CourseAgent escalates if LLM returns only whitespace."""
        # Setup
        mock_bitrix.get_deal.return_value = valid_deal
        mock_bitrix.parse_deal_stage.return_value = DealStage.LEARNING
        mock_llm.generate.return_value = "   \n\t   "  # Only whitespace

        # Execute
        response = await agent.process(message="Какой-то вопрос", deal_id=123)

        # Verify
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
