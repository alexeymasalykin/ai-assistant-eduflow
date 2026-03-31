from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from repositories.analytics import AnalyticsRepository


@pytest.fixture
def mock_pool() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_pool: AsyncMock) -> AnalyticsRepository:
    return AnalyticsRepository(pool=mock_pool)


class TestAnalyticsRepository:
    @pytest.mark.asyncio
    async def test_record_request(self, repo: AnalyticsRepository, mock_pool: AsyncMock) -> None:
        mock_pool.execute.return_value = None
        await repo.record(agent_type="course", response_time_ms=150, success=True)
        mock_pool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stats(self, repo: AnalyticsRepository, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = [
            {"agent_type": "course", "count": 50, "avg_time": 120.5},
            {"agent_type": "platform", "count": 15, "avg_time": 200.3},
        ]
        stats = await repo.get_stats()
        assert len(stats) == 2
        assert stats[0]["agent_type"] == "course"
