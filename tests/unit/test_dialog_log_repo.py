from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from repositories.dialog_log import DialogLogRepository


@pytest.fixture
def mock_pool() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_pool: AsyncMock) -> DialogLogRepository:
    return DialogLogRepository(pool=mock_pool)


class TestDialogLogRepository:
    @pytest.mark.asyncio
    async def test_save_message(self, repo: DialogLogRepository, mock_pool: AsyncMock) -> None:
        mock_pool.execute.return_value = None
        await repo.save(
            wappi_chat_id="chat123", role="user", message="Когда мой курс?", agent_type="course"
        )
        mock_pool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_history(self, repo: DialogLogRepository, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = [
            {"role": "user", "message": "Привет", "agent_type": None},
            {"role": "assistant", "message": "Здравствуйте!", "agent_type": "typical"},
        ]
        history = await repo.get_history("chat123", limit=10)
        assert len(history) == 2
        assert history[0]["role"] == "user"
