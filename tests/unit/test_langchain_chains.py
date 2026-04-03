from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.types import AgentResponse, MessageType


class TestPlatformChain:
    @pytest.mark.asyncio
    async def test_returns_agent_response_with_rag(self) -> None:
        from langchain_pipeline.chains import PlatformChain

        mock_retriever = MagicMock()
        mock_retriever.ainvoke = AsyncMock(return_value=[
            MagicMock(page_content="Нажмите 'Забыли пароль' на странице входа."),
            MagicMock(page_content="Проверьте папку 'Спам' если письмо не пришло."),
        ])
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Нажмите кнопку 'Забыли пароль' на странице входа."

        chain = PlatformChain(llm=mock_llm, retriever=mock_retriever)
        response = await chain.process("Как восстановить пароль?")

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.PLATFORM
        assert response.should_send is True
        assert len(response.text) > 0

    @pytest.mark.asyncio
    async def test_escalates_when_no_rag_results(self) -> None:
        from langchain_pipeline.chains import PlatformChain

        mock_retriever = MagicMock()
        mock_retriever.ainvoke = AsyncMock(return_value=[])
        mock_llm = AsyncMock()

        chain = PlatformChain(llm=mock_llm, retriever=mock_retriever)
        response = await chain.process("Неизвестный вопрос")

        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False


class TestCourseChain:
    @pytest.mark.asyncio
    async def test_returns_agent_response_with_deal(self) -> None:
        from langchain_pipeline.chains import CourseChain

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Ваш курс начинается 15 апреля."
        mock_bitrix = AsyncMock()
        mock_bitrix.get_deal.return_value = {
            "ID": "123", "TITLE": "Python для начинающих", "STAGE_ID": "LEARNING",
            "CONTACT_ID": "456", "UF_CRM_SUM": "5000", "COMMENTS": "Курс: Python",
            "DATE_CREATE": "2026-03-01",
        }
        # parse_deal_stage is a sync method on BitrixClient
        mock_bitrix.parse_deal_stage = MagicMock(return_value=MagicMock(is_terminal=False))

        chain = CourseChain(llm=mock_llm, bitrix=mock_bitrix)
        response = await chain.process("Когда начинается мой курс?", deal_id=123)

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.COURSE
        assert response.should_send is True

    @pytest.mark.asyncio
    async def test_escalates_without_deal_id(self) -> None:
        from langchain_pipeline.chains import CourseChain

        chain = CourseChain(llm=AsyncMock(), bitrix=AsyncMock())
        response = await chain.process("Вопрос о курсе", deal_id=None)

        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_escalates_on_terminal_stage(self) -> None:
        from langchain_pipeline.chains import CourseChain

        mock_bitrix = AsyncMock()
        mock_bitrix.get_deal.return_value = {"ID": "123", "TITLE": "Course", "STAGE_ID": "COMPLETED"}
        # parse_deal_stage is a sync method on BitrixClient
        mock_bitrix.parse_deal_stage = MagicMock(return_value=MagicMock(is_terminal=True))

        chain = CourseChain(llm=AsyncMock(), bitrix=mock_bitrix)
        response = await chain.process("Вопрос", deal_id=123)

        assert response.agent_type == MessageType.ESCALATE
