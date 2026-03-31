from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import asyncpg

logger = structlog.get_logger()


class UserMappingRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_by_chat_id(self, wappi_chat_id: str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM user_mappings WHERE wappi_chat_id = $1", wappi_chat_id
        )
        return dict(row) if row else None

    async def create(
        self,
        wappi_chat_id: str,
        bitrix_deal_id: int,
        channel: str,
        bitrix_contact_id: int | None = None,
        phone: str | None = None,
    ) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """INSERT INTO user_mappings (wappi_chat_id, bitrix_deal_id, bitrix_contact_id, channel, phone)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (wappi_chat_id) DO UPDATE SET bitrix_deal_id = EXCLUDED.bitrix_deal_id, updated_at = NOW()
               RETURNING *""",
            wappi_chat_id,
            bitrix_deal_id,
            bitrix_contact_id,
            channel,
            phone,
        )
        logger.info("user_mapping_created", chat_id=wappi_chat_id, deal_id=bitrix_deal_id)
        return dict(row) if row else None

    async def find_by_deal_id(self, bitrix_deal_id: int) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM user_mappings WHERE bitrix_deal_id = $1", bitrix_deal_id
        )
        return dict(row) if row else None
