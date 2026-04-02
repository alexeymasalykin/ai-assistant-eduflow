from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.platform_agent import PlatformAgent
from agents.types import AgentResponse, MessageType
from integrations.llm_client import LLMClient
from integrations.vector_db import VectorDB


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM client."""
    return AsyncMock(spec=LLMClient)


@pytest.fixture
def mock_vector_db() -> AsyncMock:
    """Mock VectorDB client."""
    return AsyncMock(spec=VectorDB)


@pytest.fixture
def agent(mock_llm: AsyncMock, mock_vector_db: AsyncMock) -> PlatformAgent:
    """Create PlatformAgent with mocked dependencies."""
    return PlatformAgent(llm=mock_llm, vector_db=mock_vector_db)


@pytest.fixture
def rag_results() -> list[str]:
    """Realistic RAG results from knowledge base."""
    return [
        "Если вы забыли пароль, нажмите на кнопку 'Забыли пароль?' на странице входа. Вам будет отправлено письмо со ссылкой для сброса пароля на адрес электронной почты, привязанный к вашему аккаунту.",
        "Для восстановления пароля потребуется доступ к электронной почте, с которой вы регистрировались. Проверьте папку 'Спам', если письмо не пришло в течение 5 минут.",
        "Видео может не загружаться из-за медленного интернета. Попробуйте перезагрузить страницу или загрузить видео в более низком качестве через меню настроек.",
    ]


class TestPlatformAgentWithRagContext:
    @pytest.mark.asyncio
    async def test_with_rag_context(
        self, agent: PlatformAgent, mock_llm: AsyncMock, mock_vector_db: AsyncMock, rag_results: list[str]
    ) -> None:
        """Test PlatformAgent searches knowledge base and injects context into system prompt."""
        # Setup
        mock_vector_db.search.return_value = rag_results
        mock_llm.generate.return_value = "Нажмите на кнопку 'Забыли пароль?' на странице входа и следуйте инструкциям в письме."

        # Execute
        user_message = "Как восстановить пароль?"
        response = await agent.process(message=user_message)

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.PLATFORM
        assert response.should_send is True
        assert len(response.text) > 0
        assert "пароль" in response.text.lower() or "нажмите" in response.text.lower()

        # Verify that VectorDB was called
        mock_vector_db.search.assert_called_once_with(user_message)

        # Verify that LLM was called with RAG context
        mock_llm.generate.assert_called_once()
        call_kwargs = mock_llm.generate.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "rag_context" not in system_prompt  # Placeholder should be replaced
        assert "пароль" in system_prompt.lower() or "восстановление" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_rag_context_formatting(
        self, agent: PlatformAgent, mock_llm: AsyncMock, mock_vector_db: AsyncMock, rag_results: list[str]
    ) -> None:
        """Test that RAG results are formatted as numbered list in system prompt."""
        # Setup
        mock_vector_db.search.return_value = rag_results
        mock_llm.generate.return_value = "Ответ на вопрос"

        # Execute
        await agent.process(message="Как загружаются видео?")

        # Verify system prompt formatting
        call_kwargs = mock_llm.generate.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "1." in system_prompt  # RAG results should be numbered
        assert "2." in system_prompt
        assert "3." in system_prompt


class TestPlatformAgentWithoutRagContext:
    @pytest.mark.asyncio
    async def test_without_rag_context(
        self, agent: PlatformAgent, mock_vector_db: AsyncMock
    ) -> None:
        """Test PlatformAgent escalates when no RAG results found."""
        # Setup
        mock_vector_db.search.return_value = []  # Empty results

        # Execute
        response = await agent.process(message="Какой-то редкий технический вопрос?")

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
        assert response.text == ""

        # Verify VectorDB was called
        mock_vector_db.search.assert_called_once_with("Какой-то редкий технический вопрос?")


class TestPlatformAgentWithEmptyResponse:
    @pytest.mark.asyncio
    async def test_with_empty_response(
        self, agent: PlatformAgent, mock_llm: AsyncMock, mock_vector_db: AsyncMock, rag_results: list[str]
    ) -> None:
        """Test PlatformAgent escalates if LLM returns empty response."""
        # Setup
        mock_vector_db.search.return_value = rag_results
        mock_llm.generate.return_value = ""  # Empty response

        # Execute
        response = await agent.process(message="Вопрос о платформе")

        # Verify
        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_with_whitespace_response(
        self, agent: PlatformAgent, mock_llm: AsyncMock, mock_vector_db: AsyncMock, rag_results: list[str]
    ) -> None:
        """Test PlatformAgent escalates if LLM returns only whitespace."""
        # Setup
        mock_vector_db.search.return_value = rag_results
        mock_llm.generate.return_value = "   \n\t   "  # Only whitespace

        # Execute
        response = await agent.process(message="Техническая помощь?")

        # Verify
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
        assert response.text == ""
