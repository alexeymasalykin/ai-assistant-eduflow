from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx
import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger()


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM providers."""

    async def generate(self, system_prompt: str, user_message: str) -> str: ...


LLM_TIMEOUT = 30.0
LLM_FALLBACK_RESPONSE = "Извините, не удалось обработать ваш запрос. Попробуйте позже."


class OpenAIClient:
    """OpenAI API client."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=LLM_TIMEOUT)
        self._model = model

    async def generate(self, system_prompt: str, user_message: str) -> str:
        logger.info("llm_request", provider="openai", model=self._model)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
        except TimeoutError:
            logger.error("llm_timeout", provider="openai")
            return LLM_FALLBACK_RESPONSE
        except Exception:
            logger.exception("llm_error", provider="openai")
            return LLM_FALLBACK_RESPONSE

        if not response.choices:
            logger.warning("llm_empty_response", provider="openai")
            return LLM_FALLBACK_RESPONSE

        content = response.choices[0].message.content or ""
        if not content.strip():
            logger.warning("llm_blank_content", provider="openai")
            return LLM_FALLBACK_RESPONSE

        logger.info("llm_response", provider="openai", length=len(content))
        return content


class YandexGPTClient:
    """YandexGPT API client."""

    YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def __init__(
        self,
        api_key: str,
        folder_id: str,
        model: str = "yandexgpt/latest",
    ) -> None:
        self._api_key = api_key
        self._folder_id = folder_id
        self._model = model
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def generate(self, system_prompt: str, user_message: str) -> str:
        logger.info("llm_request", provider="yandex", model=self._model)
        model_uri = f"gpt://{self._folder_id}/{self._model}"
        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 1024,
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_message},
            ],
        }
        headers = {
            "Authorization": f"Api-Key {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._http_client.post(
                self.YANDEX_GPT_URL, json=payload, headers=headers
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPStatusError):
            logger.exception("llm_error", provider="yandex")
            return LLM_FALLBACK_RESPONSE

        data = response.json()
        alternatives = data.get("result", {}).get("alternatives", [])
        if not alternatives:
            logger.warning("llm_empty_response", provider="yandex")
            return LLM_FALLBACK_RESPONSE

        content = alternatives[0].get("message", {}).get("text", "")
        if not content.strip():
            logger.warning("llm_blank_content", provider="yandex")
            return LLM_FALLBACK_RESPONSE

        logger.info("llm_response", provider="yandex", length=len(content))
        return content


def create_llm_client(
    provider: str,
    openai_api_key: str = "",
    yandex_api_key: str = "",
    yandex_folder_id: str = "",
) -> LLMClient:
    """Factory function to create LLM client based on provider."""
    if provider == "openai":
        return OpenAIClient(api_key=openai_api_key)
    if provider == "yandex":
        return YandexGPTClient(api_key=yandex_api_key, folder_id=yandex_folder_id)
    raise ValueError(f"Unknown LLM provider: {provider}")
