from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger()


class AnalyticsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(self, agent_type: str, response_time_ms: int, success: bool) -> None:
        await self._pool.execute(
            "INSERT INTO analytics (agent_type, response_time_ms, success) VALUES ($1, $2, $3)",
            agent_type,
            response_time_ms,
            success,
        )

    async def get_stats(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            "SELECT agent_type, COUNT(*) as count, AVG(response_time_ms) as avg_time "
            "FROM analytics GROUP BY agent_type ORDER BY count DESC"
        )
        return [dict(row) for row in rows]
