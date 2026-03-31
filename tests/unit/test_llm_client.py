from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.llm_client import LLMClient, OpenAIClient, YandexGPTClient, create_llm_client


class TestLLMClientProtocol:
    def test_openai_client_implements_protocol(self) -> None:
        client = OpenAIClient(api_key="test-key")
        assert isinstance(client, LLMClient)

    def test_yandex_client_implements_protocol(self) -> None:
        client = YandexGPTClient(api_key="test-key", folder_id="test-folder")
        assert isinstance(client, LLMClient)


class TestCreateLLMClient:
    def test_create_openai_client(self) -> None:
        client = create_llm_client(provider="openai", openai_api_key="sk-test")
        assert isinstance(client, OpenAIClient)

    def test_create_yandex_client(self) -> None:
        client = create_llm_client(
            provider="yandex", yandex_api_key="test", yandex_folder_id="folder"
        )
        assert isinstance(client, YandexGPTClient)

    def test_create_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_client(provider="unknown")


class TestOpenAIClient:
    @pytest.mark.asyncio
    async def test_generate_calls_api(self) -> None:
        from unittest.mock import MagicMock

        client = OpenAIClient(api_key="test-key")

        # Build a plain mock for the response (not AsyncMock — it's not awaited itself)
        mock_message = MagicMock()
        mock_message.content = "test response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # `create` must be an AsyncMock so it can be awaited
        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(client._client.chat.completions, "create", mock_create):
            result = await client.generate(
                system_prompt="You are helpful.", user_message="Hello"
            )

        assert result == "test response"
        mock_create.assert_called_once()
