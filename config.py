from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    OPENAI = "openai"
    YANDEX = "yandex"


class PipelineMode(str, Enum):
    ORIGINAL = "original"
    LANGCHAIN = "langchain"


class Settings(BaseSettings):
    """Application configuration with validation."""

    # LLM
    llm_provider: LLMProvider = LLMProvider.OPENAI
    openai_api_key: SecretStr = SecretStr("")
    yandex_api_key: SecretStr = SecretStr("")
    yandex_folder_id: str = ""

    # Bitrix24
    bitrix24_webhook_url: str = ""

    # Wappi
    wappi_api_token: SecretStr = SecretStr("")
    wappi_profile_id: str = ""
    wappi_max_profile_id: str = ""  # Profile ID for MAX Messenger in Wappi

    # Database
    postgres_dsn: str = ""

    # Embeddings
    openai_embeddings_api_key: SecretStr = SecretStr("")

    # Security
    wappi_webhook_token: str = ""
    bitrix24_webhook_token: str = ""
    admin_api_key: str = ""
    rate_limit_per_minute: int = 100

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Pipeline
    pipeline_mode: PipelineMode = PipelineMode.ORIGINAL

    # Langfuse (observability)
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        """Require all security tokens when running in production (log_format=json).

        Crashes on startup if any token is missing, preventing silent auth bypass.
        """
        if self.log_format != "json":
            return self

        required: dict[str, str] = {
            "wappi_webhook_token": self.wappi_webhook_token,
            "bitrix24_webhook_token": self.bitrix24_webhook_token,
            "admin_api_key": self.admin_api_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Production requires non-empty values for: {', '.join(missing)}"
            )
        return self


settings = Settings()
