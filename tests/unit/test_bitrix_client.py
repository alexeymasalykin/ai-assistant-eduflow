from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.bitrix_client import BitrixClient, DealStage


class TestDealStage:
    def test_terminal_stages(self) -> None:
        assert DealStage.COMPLETED.is_terminal is True
        assert DealStage.REJECTED.is_terminal is True
        assert DealStage.REFUND.is_terminal is True

    def test_active_stages(self) -> None:
        assert DealStage.NEW_LEAD.is_terminal is False
        assert DealStage.LEARNING.is_terminal is False
        assert DealStage.PAYMENT.is_terminal is False


class TestBitrixClient:
    @pytest.fixture
    def client(self) -> BitrixClient:
        return BitrixClient(webhook_url="https://test.bitrix24.ru/rest/1/token/")

    @pytest.mark.asyncio
    async def test_get_deal(self, client: BitrixClient) -> None:
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "result": {
                "ID": "123",
                "TITLE": "Python для начинающих",
                "STAGE_ID": "LEARNING",
                "DATE_CREATE": "2026-01-15",
            }
        }
        mock_response.raise_for_status = AsyncMock()
        with patch.object(client._http_client, "get", return_value=mock_response):
            deal = await client.get_deal(123)
        assert deal is not None
        assert deal["ID"] == "123"

    @pytest.mark.asyncio
    async def test_get_deal_not_found(self, client: BitrixClient) -> None:
        mock_response = AsyncMock()
        mock_response.json.return_value = {"result": None}
        mock_response.raise_for_status = AsyncMock()
        with patch.object(client._http_client, "get", return_value=mock_response):
            deal = await client.get_deal(999)
        assert deal is None

    @pytest.mark.asyncio
    async def test_get_deal_stage_from_deal(self, client: BitrixClient) -> None:
        stage = client.parse_deal_stage("LEARNING")
        assert stage == DealStage.LEARNING

    @pytest.mark.asyncio
    async def test_unknown_stage_returns_none(self, client: BitrixClient) -> None:
        stage = client.parse_deal_stage("UNKNOWN_STAGE")
        assert stage is None
