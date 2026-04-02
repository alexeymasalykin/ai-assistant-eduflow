"""Root pytest configuration and shared fixtures.

Configures:
- pytest plugins (asyncio, cov)
- custom markers (unit, integration, database, slow)
- environment setup for tests
- global session fixtures
"""

from __future__ import annotations

import os
from typing import Generator

import pytest


# Pytest plugins configuration
pytest_plugins = [
    "pytest_asyncio",
    "pytest_cov",
]


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "database: mark test as database test")
    config.addinivalue_line("markers", "slow: mark test as slow (deselect with '-m \"not slow\"')")


@pytest.fixture(scope="session")
def env_setup() -> Generator[None, None, None]:
    """Set up environment variables for test session."""
    # Save original values
    original_values = {
        "LOG_LEVEL": os.environ.get("LOG_LEVEL"),
        "LOG_FORMAT": os.environ.get("LOG_FORMAT"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "YANDEX_API_KEY": os.environ.get("YANDEX_API_KEY"),
        "YANDEX_FOLDER_ID": os.environ.get("YANDEX_FOLDER_ID"),
        "BITRIX24_WEBHOOK_URL": os.environ.get("BITRIX24_WEBHOOK_URL"),
        "WAPPI_API_TOKEN": os.environ.get("WAPPI_API_TOKEN"),
        "WAPPI_PROFILE_ID": os.environ.get("WAPPI_PROFILE_ID"),
        "POSTGRES_DSN": os.environ.get("POSTGRES_DSN"),
        "WAPPI_WEBHOOK_TOKEN": os.environ.get("WAPPI_WEBHOOK_TOKEN"),
        "BITRIX24_WEBHOOK_TOKEN": os.environ.get("BITRIX24_WEBHOOK_TOKEN"),
    }

    # Set test environment variables
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["LOG_FORMAT"] = "console"
    os.environ["OPENAI_API_KEY"] = "test-openai-key-12345"
    os.environ["YANDEX_API_KEY"] = "test-yandex-key-12345"
    os.environ["YANDEX_FOLDER_ID"] = "test-folder-id"
    os.environ["BITRIX24_WEBHOOK_URL"] = "https://test.bitrix24.ru/rest/1/test-token/"
    os.environ["WAPPI_API_TOKEN"] = "test-wappi-token-12345"
    os.environ["WAPPI_PROFILE_ID"] = "test-profile-123"
    os.environ["POSTGRES_DSN"] = "postgresql://test:test@localhost:5432/test_db"
    os.environ["WAPPI_WEBHOOK_TOKEN"] = "test-webhook-token"
    os.environ["BITRIX24_WEBHOOK_TOKEN"] = "test-bitrix-webhook-token"

    yield

    # Restore original values
    for key, value in original_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
