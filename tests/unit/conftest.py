"""Unit test fixtures for mocking external services.

Fixtures:
- mock_llm_client: AsyncMock of OpenAI/YandexGPT LLM provider
- mock_bitrix_client: AsyncMock of Bitrix24 REST API client
- mock_vector_db: AsyncMock of ChromaDB vector database
- mock_database: AsyncMock of PostgreSQL database
- mock_http_client: AsyncMock of httpx.AsyncClient
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """Mock LLM client (OpenAI or YandexGPT).

    Returns a mock that responds to generate() calls with test responses.
    """
    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(
        return_value="Это тестовый ответ от LLM. Как дела?"
    )
    return mock_client


@pytest.fixture
def mock_bitrix_client() -> AsyncMock:
    """Mock Bitrix24 REST API client.

    Provides mocked methods:
    - get_deal() → returns deal details
    - get_contact() → returns contact details
    - find_deals_by_phone() → returns list of deals by phone
    - get_deal_stage() → returns stage info
    - log_dialog() → logs customer communication
    """
    mock_client = AsyncMock()

    # get_deal mock
    mock_client.get_deal = AsyncMock(
        return_value={
            "ID": "123",
            "TITLE": "Курс Python для начинающих",
            "STAGE_ID": "LEARNING",
            "DATE_CREATE": "2026-01-15",
            "CREATED_BY_ID": "1",
            "CONTACT_ID": "1",
            "UF_CRM_1234567890": "2500.00",  # sum field
        }
    )

    # get_contact mock
    mock_client.get_contact = AsyncMock(
        return_value={
            "ID": "1",
            "NAME": "Тестовый Пользователь",
            "PHONE": [{"VALUE": "+79991234567", "VALUE_TYPE": "MOBILE"}],
            "EMAIL": [{"VALUE": "test@example.com"}],
        }
    )

    # find_deals_by_phone mock
    mock_client.find_deals_by_phone = AsyncMock(return_value=[])

    # parse_deal_stage mock
    mock_client.parse_deal_stage = MagicMock(return_value="LEARNING")

    # log_dialog mock
    mock_client.log_dialog = AsyncMock()

    return mock_client


@pytest.fixture
def mock_vector_db() -> AsyncMock:
    """Mock vector database (ChromaDB).

    Provides mocked methods:
    - search() → returns similar documents from knowledge base
    - index_knowledge_base() → indexes documents
    """
    mock_db = AsyncMock()

    # search mock - returns list of similar documents
    mock_db.search = AsyncMock(
        return_value=[
            {
                "id": "doc_1",
                "text": "Знание статьи 1: информация об основах Python",
                "metadata": {"source": "python_basics.md"},
            },
            {
                "id": "doc_2",
                "text": "Знание статьи 2: переменные и типы данных",
                "metadata": {"source": "variables.md"},
            },
        ]
    )

    # index_knowledge_base mock
    mock_db.index_knowledge_base = AsyncMock()

    # query mock (alternative name)
    mock_db.query = AsyncMock(return_value=[{"text": "Test knowledge article"}])

    return mock_db


@pytest.fixture
def mock_database() -> AsyncMock:
    """Mock PostgreSQL database service.

    Provides mocked methods:
    - connect() → establishes connection
    - disconnect() → closes connection
    - pool property → returns connection pool
    """
    mock_db = AsyncMock()

    # Connection management
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()

    # Pool mock
    mock_pool = AsyncMock()
    mock_db.pool = mock_pool

    return mock_db


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Mock httpx.AsyncClient for HTTP requests.

    Provides mocked methods:
    - get() → HTTP GET requests
    - post() → HTTP POST requests
    - close() → cleanup
    """
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def sample_wappi_message() -> dict[str, Any]:
    """Sample Wappi incoming webhook message (WhatsApp/Telegram).

    Represents a customer message from WhatsApp channel.
    """
    return {
        "message_id": "msg_123456",
        "from": "+79991234567",
        "chat_id": "9991234567",
        "body": "Привет, мне нужна консультация",
        "type": "text",
        "timestamp": 1704067200,
        "profile_id": "test-profile-123",
    }


@pytest.fixture
def sample_deal_data() -> dict[str, Any]:
    """Sample deal data from Bitrix24."""
    return {
        "ID": "42",
        "TITLE": "JavaScript для фронтенда",
        "STAGE_ID": "PAYMENT",
        "DATE_CREATE": "2026-01-20",
        "CREATED_BY_ID": "1",
        "CONTACT_ID": "5",
        "UF_CRM_1234567890": "15000.00",
    }


@pytest.fixture
def sample_contact_data() -> dict[str, Any]:
    """Sample contact data from Bitrix24."""
    return {
        "ID": "5",
        "NAME": "Иван Сидоров",
        "PHONE": [
            {"VALUE": "+79991234567", "VALUE_TYPE": "MOBILE"},
            {"VALUE": "+79999876543", "VALUE_TYPE": "WORK"},
        ],
        "EMAIL": [{"VALUE": "ivan@example.com", "VALUE_TYPE": "WORK"}],
        "SOURCE_ID": "OTHER",
    }
