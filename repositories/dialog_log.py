from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger()


class DialogLogRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(
        self,
        wappi_chat_id: str,
        role: str,
        message: str,
        agent_type: str | None = None,
    ) -> None:
        await self._pool.execute(
            "INSERT INTO dialog_logs (wappi_chat_id, role, message, agent_type) VALUES ($1, $2, $3, $4)",
            wappi_chat_id,
            role,
            message,
            agent_type,
        )
        logger.debug("dialog_saved", chat_id=wappi_chat_id, role=role)

    async def get_history(self, wappi_chat_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            "SELECT role, message, agent_type, created_at FROM dialog_logs "
            "WHERE wappi_chat_id = $1 ORDER BY created_at DESC LIMIT $2",
            wappi_chat_id,
            limit,
        )
        return [dict(row) for row in rows]
