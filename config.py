from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    OPENAI = "openai"
    YANDEX = "yandex"


class Settings(BaseSettings):
    """Application configuration with validation."""

    # LLM
    llm_provider: LLMProvider = LLMProvider.OPENAI
    openai_api_key: str = ""
    yandex_api_key: str = ""
    yandex_folder_id: str = ""

    # Bitrix24
    bitrix24_webhook_url: str = ""

    # Wappi
    wappi_api_token: str = ""
    wappi_profile_id: str = ""
    wappi_max_profile_id: str = ""  # Profile ID for MAX Messenger in Wappi

    # Database
    postgres_dsn: str = "postgresql://postgres:postgres@db:5432/eduflow"

    # Embeddings
    openai_embeddings_api_key: str = ""

    # Security
    wappi_webhook_token: str = ""
    bitrix24_webhook_token: str = ""
    admin_api_key: str = ""
    rate_limit_per_minute: int = 100

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
