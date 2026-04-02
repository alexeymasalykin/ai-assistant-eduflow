"""Integration test fixtures for FastAPI application.

Fixtures:
- test_client: FastAPI TestClient for making HTTP requests
- mock_services: All mocked services wired into app context
- mock_database_service: Mocked database with connection pool
- mock_wappi_handler: Mocked Wappi incoming message handler
- mock_bitrix_handler: Mocked Bitrix webhook handler
- mock_orchestrator: Mocked orchestrator agent
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app as app_module
from agents.orchestrator import Orchestrator
from integrations.bitrix_client import BitrixClient
from integrations.database import Database
from integrations.llm_client import LLMClient
from integrations.vector_db import VectorDB
from integrations.wappi import WappiIncomingHandler, WappiOutgoingHandler


@pytest.fixture
def mock_database_service() -> AsyncMock:
    """Mock Database service with connection pool.

    Used for integration tests that need database mocking without
    running actual PostgreSQL.
    """
    db = AsyncMock(spec=Database)
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()

    # Mock asyncpg pool
    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock()
    mock_pool.close = AsyncMock()
    db.pool = mock_pool

    return db


@pytest.fixture
def mock_llm_service() -> AsyncMock:
    """Mock LLM client (OpenAI or YandexGPT)."""
    mock_client = AsyncMock(spec=LLMClient)
    mock_client.generate = AsyncMock(
        return_value="Это автоматический ответ от AI ассистента."
    )
    return mock_client


@pytest.fixture
def mock_bitrix_service() -> AsyncMock:
    """Mock Bitrix24 client."""
    mock_client = AsyncMock(spec=BitrixClient)

    mock_client.get_deal = AsyncMock(
        return_value={
            "ID": "999",
            "TITLE": "Интеграционный тест",
            "STAGE_ID": "LEARNING",
            "DATE_CREATE": "2026-04-01",
        }
    )

    mock_client.get_contact = AsyncMock(
        return_value={
            "ID": "100",
            "NAME": "Integration Test User",
            "PHONE": [{"VALUE": "+79991234567"}],
        }
    )

    mock_client.find_deals_by_phone = AsyncMock(return_value=[])
    mock_client.parse_deal_stage = MagicMock(return_value="LEARNING")
    mock_client.log_dialog = AsyncMock()

    return mock_client


@pytest.fixture
def mock_vector_db_service() -> AsyncMock:
    """Mock vector database service."""
    mock_db = AsyncMock(spec=VectorDB)

    mock_db.search = AsyncMock(
        return_value=[
            {
                "text": "Информация о курсе Python",
                "metadata": {"source": "courses.md"},
            }
        ]
    )

    mock_db.index_knowledge_base = AsyncMock()

    return mock_db


@pytest.fixture
def mock_wappi_incoming_handler() -> AsyncMock:
    """Mock Wappi incoming message handler.

    Processes incoming messages from WhatsApp/Telegram via Wappi.
    """
    mock_handler = AsyncMock(spec=WappiIncomingHandler)

    mock_handler.process_message = AsyncMock(
        return_value={
            "customer_id": "cust_123",
            "chat_id": "9991234567",
            "message": "Test message",
        }
    )

    mock_handler.mark_message_read = AsyncMock()

    return mock_handler


@pytest.fixture
def mock_wappi_outgoing_handler() -> AsyncMock:
    """Mock Wappi outgoing message handler."""
    mock_handler = AsyncMock(spec=WappiOutgoingHandler)
    mock_handler.send_message = AsyncMock(return_value=True)
    return mock_handler


@pytest.fixture
def mock_orchestrator_agent() -> AsyncMock:
    """Mock Orchestrator that processes messages through agents.

    Returns typical agent response with orchestration result.
    """
    mock_orchestrator = AsyncMock(spec=Orchestrator)

    mock_orchestrator.process = AsyncMock(
        return_value={
            "text": "Это ответ от оркестратора",
            "agent_type": "typical",
            "should_send": True,
            "context": {"customer_id": "cust_123"},
        }
    )

    return mock_orchestrator


@pytest.fixture
def app_with_mocks(
    mock_database_service: AsyncMock,
    mock_llm_service: AsyncMock,
    mock_bitrix_service: AsyncMock,
    mock_vector_db_service: AsyncMock,
    mock_wappi_incoming_handler: AsyncMock,
    mock_wappi_outgoing_handler: AsyncMock,
    mock_orchestrator_agent: AsyncMock,
) -> tuple[Any, dict[str, AsyncMock]]:
    """Wire mocked services into app context.

    Returns tuple of (app, mocks_dict) for easy access in tests.
    """
    mocks = {
        "db": mock_database_service,
        "llm": mock_llm_service,
        "bitrix": mock_bitrix_service,
        "vector_db": mock_vector_db_service,
        "wappi_incoming": mock_wappi_incoming_handler,
        "wappi_outgoing": mock_wappi_outgoing_handler,
        "orchestrator": mock_orchestrator_agent,
    }

    # Patch app module globals with mocks
    with patch.object(app_module, "db", mock_database_service), \
         patch.object(app_module, "llm_client", mock_llm_service), \
         patch.object(app_module, "bitrix_client", mock_bitrix_service), \
         patch.object(app_module, "vector_db", mock_vector_db_service), \
         patch.object(app_module, "wappi_incoming", mock_wappi_incoming_handler), \
         patch.object(app_module, "wappi_outgoing", mock_wappi_outgoing_handler), \
         patch.object(app_module, "orchestrator", mock_orchestrator_agent):

        yield app_module.app, mocks


@pytest.fixture
def test_client(app_with_mocks: tuple[Any, dict[str, AsyncMock]]) -> TestClient:
    """FastAPI TestClient with mocked services.

    Use this fixture to make HTTP requests to the application in tests.

    Example:
        def test_health_check(test_client):
            response = test_client.get("/health")
            assert response.status_code == 200
    """
    app, _ = app_with_mocks
    return TestClient(app)


@pytest.fixture
def mocked_services(
    app_with_mocks: tuple[Any, dict[str, AsyncMock]]
) -> dict[str, AsyncMock]:
    """Access all mocked services for assertions.

    Example:
        def test_orchestrator_called(test_client, mocked_services):
            test_client.post("/wappi", json={"message_id": "1", ...})
            mocked_services["orchestrator"].process.assert_called_once()
    """
    _, mocks = app_with_mocks
    return mocks


# Sample request/response payloads for integration tests


@pytest.fixture
def wappi_webhook_payload() -> dict[str, Any]:
    """Sample Wappi webhook payload (incoming message from WhatsApp)."""
    return {
        "message_id": "wappi_msg_123456",
        "from": "+79991234567",
        "chat_id": "9991234567",
        "body": "Привет! Мне нужна информация о курсах",
        "type": "text",
        "timestamp": 1704067200,
        "profile_id": "test-profile-123",
        "contact_name": "Ivan Sidorov",
    }


@pytest.fixture
def bitrix_webhook_payload() -> dict[str, Any]:
    """Sample Bitrix24 webhook payload (deal update)."""
    return {
        "event": "ONCRMDEALUPDATE",
        "data": {
            "FIELDS": {
                "ID": "123",
                "TITLE": "Test Deal",
                "STAGE_ID": "PAYMENT",
                "CONTACT_ID": "1",
            },
            "PREVIOUS": {
                "STAGE_ID": "LEARNING",
            },
        },
    }


@pytest.fixture
def wappi_invalid_payload() -> dict[str, Any]:
    """Sample invalid Wappi payload (missing required fields)."""
    return {
        "message_id": "invalid_msg_1",
        # missing 'from', 'chat_id', 'body'
        "type": "text",
    }
