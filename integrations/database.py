from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger()


class Database:
    """Async PostgreSQL connection pool manager."""

    def __init__(self, dsn: str, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size
        )
        logger.info("database_connected", dsn=self._dsn.split("@")[-1])

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("database_disconnected")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool
