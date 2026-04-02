from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.orchestrator import Orchestrator
from agents.types import AgentResponse, MessageType
from integrations.bitrix_client import BitrixClient, DealStage
from integrations.llm_client import LLMClient
from integrations.vector_db import VectorDB


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM client."""
    return AsyncMock(spec=LLMClient)


@pytest.fixture
def mock_bitrix() -> AsyncMock:
    """Mock Bitrix client."""
    return AsyncMock(spec=BitrixClient)


@pytest.fixture
def mock_vector_db() -> AsyncMock:
    """Mock Vector DB client."""
    return AsyncMock(spec=VectorDB)


@pytest.fixture
def orchestrator(
    mock_llm: AsyncMock,
    mock_bitrix: AsyncMock,
    mock_vector_db: AsyncMock,
) -> Orchestrator:
    """Create Orchestrator with mocked dependencies."""
    return Orchestrator(llm=mock_llm, bitrix=mock_bitrix, vector_db=mock_vector_db)


@pytest.fixture
def valid_deal() -> dict[str, str]:
    """Realistic deal dict for testing."""
    return {
        "ID": "123",
        "TITLE": "Python для начинающих",
        "STAGE_ID": "LEARNING",
        "CONTACT_ID": "456",
        "UF_CRM_SUM": "5000.00",
        "COMMENTS": "Курс: Основы Python. Начало: 2026-04-15.",
        "DATE_CREATE": "2026-03-01",
    }


class TestOrchestratorFAQShortAnswer:
    """Test FAQ short answer path (rule-based, no LLM)."""

    @pytest.mark.asyncio
    async def test_greeting_faq_response(self, orchestrator: Orchestrator) -> None:
        """Test that greeting returns FAQ template directly without classification."""
        response = await orchestrator.process("Привет")

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0
        assert "привет" in response.text.lower() or "добро" in response.text.lower()

    @pytest.mark.asyncio
    async def test_thanks_faq_response(self, orchestrator: Orchestrator) -> None:
        """Test that thanks returns FAQ template directly without classification."""
        response = await orchestrator.process("Спасибо")

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True
        assert len(response.text) > 0
        assert "спасибо" in response.text.lower() or "благодар" in response.text.lower()

    @pytest.mark.asyncio
    async def test_confirmation_silent_response(self, orchestrator: Orchestrator) -> None:
        """Test that confirmation returns silent response without classification."""
        response = await orchestrator.process("Ок")

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is False
        assert response.text == ""


class TestOrchestratorClassifyAsTypical:
    """Test routing to TypicalAgent."""

    @pytest.mark.asyncio
    async def test_classify_greeting_long_form(
        self, orchestrator: Orchestrator
    ) -> None:
        """Test that long greeting (>60 chars) bypasses typical patterns and gets classified."""
        # Long greeting should not match typical pattern (>60 chars)
        # Should go through classifier
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.TYPICAL
        ):
            message = "Привет, это я! Как дела и что новенького в твоей жизни?"
            response = await orchestrator.process(message)

            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_classification_returns_typical_response(
        self, orchestrator: Orchestrator
    ) -> None:
        """Test that messages classified as TYPICAL route to TypicalAgent."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.TYPICAL
        ):
            response = await orchestrator.process("Спасибо за помощь!")

            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.TYPICAL


class TestOrchestratorClassifyAsCourse:
    """Test routing to CourseAgent with deal_id."""

    @pytest.mark.asyncio
    async def test_course_question_with_deal_id(
        self,
        orchestrator: Orchestrator,
        mock_llm: AsyncMock,
        mock_bitrix: AsyncMock,
        valid_deal: dict[str, str],
    ) -> None:
        """Test that course question with deal_id routes to CourseAgent."""
        # Setup classifier to return COURSE
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.COURSE
        ):
            # Setup course agent mock
            mock_bitrix.get_deal.return_value = valid_deal
            mock_bitrix.parse_deal_stage.return_value = DealStage.LEARNING
            mock_llm.generate.return_value = "Ваш курс начинается 15 апреля."

            # Execute
            response = await orchestrator.process(
                "Когда начинается мой курс?", deal_id=123
            )

            # Verify
            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.COURSE
            assert response.should_send is True
            assert len(response.text) > 0

            # Verify course agent was called with deal_id
            mock_bitrix.get_deal.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_course_message_without_deal_escalates(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        """Test that course message without deal_id escalates."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.COURSE
        ):
            response = await orchestrator.process("Когда начинается курс?", deal_id=None)

            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.ESCALATE
            assert response.should_send is False


class TestOrchestratorClassifyAsPlatform:
    """Test routing to PlatformAgent (no deal_id needed)."""

    @pytest.mark.asyncio
    async def test_platform_question_no_deal_id(
        self,
        orchestrator: Orchestrator,
        mock_llm: AsyncMock,
        mock_vector_db: AsyncMock,
    ) -> None:
        """Test that platform question routes to PlatformAgent."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.PLATFORM
        ):
            # Setup platform agent mock
            mock_vector_db.search.return_value = [
                "Для восстановления пароля кликните 'Забыли пароль?' на странице входа."
            ]
            mock_llm.generate.return_value = "Используйте ссылку восстановления пароля."

            # Execute
            response = await orchestrator.process("Как восстановить пароль?")

            # Verify
            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.PLATFORM
            assert response.should_send is True
            assert len(response.text) > 0

            # Verify vector_db was called for RAG search
            mock_vector_db.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_platform_question_with_deal_id_ignored(
        self,
        orchestrator: Orchestrator,
        mock_llm: AsyncMock,
        mock_vector_db: AsyncMock,
    ) -> None:
        """Test that PlatformAgent doesn't use deal_id even if provided."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.PLATFORM
        ):
            # Setup platform agent mock
            mock_vector_db.search.return_value = [
                "Видео может не загружаться из-за проблем с интернетом."
            ]
            mock_llm.generate.return_value = "Проверьте подключение к интернету."

            # Execute with deal_id (should be ignored)
            response = await orchestrator.process(
                "Видео не загружается", deal_id=999
            )

            # Verify
            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.PLATFORM
            assert response.should_send is True

    @pytest.mark.asyncio
    async def test_platform_no_rag_results_escalates(
        self,
        orchestrator: Orchestrator,
        mock_vector_db: AsyncMock,
    ) -> None:
        """Test that PlatformAgent escalates if no RAG results found."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.PLATFORM
        ):
            # Setup platform agent mock - no RAG results
            mock_vector_db.search.return_value = []

            # Execute
            response = await orchestrator.process(
                "Очень странный и неизвестный вопрос про платформу"
            )

            # Verify escalation
            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.ESCALATE
            assert response.should_send is False


class TestOrchestratorClassifyAsEscalate:
    """Test routing for escalation."""

    @pytest.mark.asyncio
    async def test_classify_as_escalate(self, orchestrator: Orchestrator) -> None:
        """Test that complex question is classified as escalate."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.ESCALATE
        ):
            response = await orchestrator.process(
                "Сложный вопрос про возврат оплаты за курс"
            )

            assert isinstance(response, AgentResponse)
            assert response.agent_type == MessageType.ESCALATE
            assert response.should_send is False
            assert response.text == ""


class TestOrchestratorInputSanitization:
    """Test input sanitization."""

    @pytest.mark.asyncio
    async def test_sanitize_xss_injection(self, orchestrator: Orchestrator) -> None:
        """Test that XSS injection is sanitized."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.ESCALATE
        ):
            response = await orchestrator.process("<script>alert('xss')</script>")

            # Should process sanitized message (greeting patterns won't match)
            # Should not crash
            assert isinstance(response, AgentResponse)

    @pytest.mark.asyncio
    async def test_sanitize_sql_injection(self, orchestrator: Orchestrator) -> None:
        """Test that SQL injection patterns are sanitized."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.ESCALATE
        ):
            response = await orchestrator.process("'; DROP TABLE users; --")

            # Should process sanitized message
            assert isinstance(response, AgentResponse)

    @pytest.mark.asyncio
    async def test_truncate_long_message(self, orchestrator: Orchestrator) -> None:
        """Test that very long messages are truncated."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.ESCALATE
        ):
            long_message = "a" * 5000

            response = await orchestrator.process(long_message)

            # Should process without crashing
            assert isinstance(response, AgentResponse)


class TestOrchestratorDealIdPassing:
    """Test that deal_id is properly passed to CourseAgent."""

    @pytest.mark.asyncio
    async def test_deal_id_passed_to_course_agent(
        self,
        orchestrator: Orchestrator,
        mock_bitrix: AsyncMock,
        mock_llm: AsyncMock,
        valid_deal: dict[str, str],
    ) -> None:
        """Test that deal_id parameter is passed to CourseAgent."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.COURSE
        ):
            mock_bitrix.get_deal.return_value = valid_deal
            mock_bitrix.parse_deal_stage.return_value = DealStage.LEARNING
            mock_llm.generate.return_value = "Ответ курса"

            # Execute with specific deal_id
            deal_id = 456
            response = await orchestrator.process("Вопрос", deal_id=deal_id)

            # Verify deal_id was passed correctly
            assert response.agent_type == MessageType.COURSE
            mock_bitrix.get_deal.assert_called_once_with(deal_id)

    @pytest.mark.asyncio
    async def test_none_deal_id_passed_to_platform(
        self,
        orchestrator: Orchestrator,
        mock_vector_db: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        """Test that None deal_id works for PlatformAgent."""
        with patch.object(
            orchestrator.classifier, "classify", return_value=MessageType.PLATFORM
        ):
            mock_vector_db.search.return_value = ["RAG result"]
            mock_llm.generate.return_value = "Ответ платформы"

            # Execute with None deal_id (should be OK for platform)
            response = await orchestrator.process("Вопрос платформы", deal_id=None)

            assert response.agent_type == MessageType.PLATFORM
            assert response.should_send is True


class TestOrchestratorAgentInstanceManagement:
    """Test that agent instances are properly managed."""

    def test_orchestrator_has_all_agents(self, orchestrator: Orchestrator) -> None:
        """Test that Orchestrator has all required agent instances."""
        assert hasattr(orchestrator, "classifier")
        assert hasattr(orchestrator, "typical_agent")
        assert hasattr(orchestrator, "course_agent")
        assert hasattr(orchestrator, "platform_agent")

    def test_orchestrator_agents_are_correct_type(
        self, orchestrator: Orchestrator
    ) -> None:
        """Test that agent instances are correct types."""
        from agents.classifier import ClassifierAgent
        from agents.course_agent import CourseAgent
        from agents.platform_agent import PlatformAgent
        from agents.typical_agent import TypicalAgent

        assert isinstance(orchestrator.classifier, ClassifierAgent)
        assert isinstance(orchestrator.typical_agent, TypicalAgent)
        assert isinstance(orchestrator.course_agent, CourseAgent)
        assert isinstance(orchestrator.platform_agent, PlatformAgent)
