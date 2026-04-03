from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.types import AgentResponse, MessageType
from langchain_pipeline.pipeline import LangChainPipeline


@pytest.fixture
def mock_deps():
    return {
        "llm": AsyncMock(),
        "retriever": MagicMock(),
        "bitrix_client": AsyncMock(),
        "langfuse_handler": None,
    }


@pytest.fixture
def pipeline(mock_deps):
    return LangChainPipeline(**mock_deps)


class TestLangChainPipeline:
    @pytest.mark.asyncio
    async def test_greeting_returns_typical_response(self, pipeline: LangChainPipeline) -> None:
        response = await pipeline.process("Привет!", deal_id=None)
        assert isinstance(response, AgentResponse)
        assert response.should_send is True
        assert response.agent_type == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_empty_message_returns_silent(self, pipeline: LangChainPipeline) -> None:
        response = await pipeline.process("", deal_id=None)
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_platform_question_routes_to_platform_chain(
        self, pipeline: LangChainPipeline, mock_deps: dict,
    ) -> None:
        mock_deps["retriever"].ainvoke = AsyncMock(return_value=[
            MagicMock(page_content="Нажмите 'Забыли пароль'."),
        ])
        mock_deps["llm"].generate.side_effect = [
            "platform",
            "Нажмите кнопку 'Забыли пароль'.",
        ]

        response = await pipeline.process("Как сбросить пароль?", deal_id=None)
        assert response.agent_type == MessageType.PLATFORM
        assert response.should_send is True

    @pytest.mark.asyncio
    async def test_escalate_returns_escalate(
        self, pipeline: LangChainPipeline, mock_deps: dict,
    ) -> None:
        mock_deps["llm"].generate.return_value = "escalate"
        response = await pipeline.process("Хочу вернуть деньги!", deal_id=None)
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_returns_agent_response_type(self, pipeline: LangChainPipeline) -> None:
        response = await pipeline.process("Привет", deal_id=None)
        assert isinstance(response, AgentResponse)
