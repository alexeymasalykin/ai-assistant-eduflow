from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from repositories.user_mapping import UserMappingRepository


@pytest.fixture
def mock_pool() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_pool: AsyncMock) -> UserMappingRepository:
    return UserMappingRepository(pool=mock_pool)


class TestUserMappingRepository:
    @pytest.mark.asyncio
    async def test_find_by_chat_id(self, repo: UserMappingRepository, mock_pool: AsyncMock) -> None:
        mock_pool.fetchrow.return_value = {
            "id": 1,
            "wappi_chat_id": "chat123",
            "bitrix_deal_id": 456,
            "channel": "telegram",
        }
        result = await repo.find_by_chat_id("chat123")
        assert result is not None
        assert result["bitrix_deal_id"] == 456

    @pytest.mark.asyncio
    async def test_find_by_chat_id_not_found(
        self, repo: UserMappingRepository, mock_pool: AsyncMock
    ) -> None:
        mock_pool.fetchrow.return_value = None
        result = await repo.find_by_chat_id("unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_mapping(
        self, repo: UserMappingRepository, mock_pool: AsyncMock
    ) -> None:
        mock_pool.fetchrow.return_value = {"id": 1}
        result = await repo.create(wappi_chat_id="chat123", bitrix_deal_id=456, channel="telegram")
        assert result is not None
