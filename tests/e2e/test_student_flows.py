"""E2E tests: student happy-path scenarios.

Each test sends an HTTP request to POST /webhook/wappi and verifies the full
pipeline: webhook parsing -> orchestrator routing -> agent processing -> response.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.e2e.conftest import WAPPI_AUTH_HEADER, E2EContext, make_wappi_payload

pytestmark = pytest.mark.e2e


async def test_greeting_returns_faq_response(e2e: E2EContext) -> None:
    """Student says 'Привет!' -> TypicalAgent -> FAQ greeting -> Wappi send."""
    payload = make_wappi_payload(body="Привет!", message_id="msg_greeting_001")

    response = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # TypicalAgent returns FAQ template — Wappi send called with greeting text
    e2e.wappi_outgoing.send_message.assert_called_once()
    sent_text = e2e.wappi_outgoing.send_message.call_args.kwargs.get(
        "text", e2e.wappi_outgoing.send_message.call_args[1].get("text", "")
    )
    assert "EduFlow" in sent_text  # FAQ greeting contains "EduFlow"

    # No LLM calls — greeting is rule-based
    e2e.llm.generate.assert_not_called()


async def test_platform_question_uses_rag_and_llm(e2e: E2EContext) -> None:
    """Student asks tech support -> ClassifierAgent(LLM) -> PlatformAgent -> RAG + LLM -> send."""
    # Configure mocks for platform flow
    e2e.llm.generate = AsyncMock(
        side_effect=[
            "platform",  # First call: classifier
            "Для входа в личный кабинет используйте email и пароль.",  # Second call: PlatformAgent
        ]
    )
    e2e.vector_db.search = AsyncMock(
        return_value=[
            "Для входа в личный кабинет перейдите на eduflow.ru/login",
            "Если забыли пароль, нажмите 'Забыли пароль' на странице входа",
            "Личный кабинет доступен 24/7 с любого устройства",
        ]
    )

    payload = make_wappi_payload(body="Не могу войти в личный кабинет", message_id="msg_platform_001")

    response = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )

    assert response.status_code == 200

    # VectorDB search was called
    e2e.vector_db.search.assert_called_once()

    # LLM called twice: classifier + PlatformAgent
    assert e2e.llm.generate.call_count == 2

    # Wappi send called with LLM response
    e2e.wappi_outgoing.send_message.assert_called_once()
    sent_text = e2e.wappi_outgoing.send_message.call_args.kwargs.get(
        "text", e2e.wappi_outgoing.send_message.call_args[1].get("text", "")
    )
    assert "личный кабинет" in sent_text.lower()


async def test_course_question_escalates_without_deal(e2e: E2EContext) -> None:
    """Course question -> ClassifierAgent(LLM:'course') -> CourseAgent(deal_id=None) -> escalate.

    NOTE: The webhook router calls orchestrator.process(body) without deal_id,
    so CourseAgent always receives deal_id=None and escalates. This is the
    actual production behavior — deal_id mapping is not yet wired into the
    webhook pipeline.
    """
    e2e.llm.generate = AsyncMock(return_value="course")

    payload = make_wappi_payload(body="Сколько стоит курс Python?", message_id="msg_course_001")

    response = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )

    assert response.status_code == 200

    # LLM called once for classification only (CourseAgent escalates before LLM)
    e2e.llm.generate.assert_called_once()

    # No message sent — escalation is silent
    e2e.wappi_outgoing.send_message.assert_not_called()


async def test_escalation_does_not_send_message(e2e: E2EContext) -> None:
    """Complex question -> ClassifierAgent(LLM:'escalate') -> ESCALATE -> no send."""
    e2e.llm.generate = AsyncMock(return_value="escalate")

    payload = make_wappi_payload(body="Хочу вернуть деньги за курс", message_id="msg_escalate_001")

    response = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )

    assert response.status_code == 200

    # LLM called once for classification
    e2e.llm.generate.assert_called_once()

    # No message sent — escalation to human
    e2e.wappi_outgoing.send_message.assert_not_called()


async def test_confirmation_is_silent(e2e: E2EContext) -> None:
    """Student says 'Ок' -> TypicalAgent -> silent (no send, no LLM)."""
    payload = make_wappi_payload(body="Ок", message_id="msg_confirm_001")

    response = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )

    assert response.status_code == 200

    # No message sent — confirmation acknowledged silently
    e2e.wappi_outgoing.send_message.assert_not_called()

    # No LLM calls — rule-based pattern match
    e2e.llm.generate.assert_not_called()
