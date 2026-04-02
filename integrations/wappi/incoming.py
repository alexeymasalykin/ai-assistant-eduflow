from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import asyncpg

    from integrations.bitrix_client import BitrixClient
    from integrations.database import Database

logger = structlog.get_logger()


class WappiIncomingHandler:
    """Process incoming messages from Wappi webhook (Telegram/WhatsApp)."""

    def __init__(self, db: Database, bitrix: BitrixClient) -> None:
        self._pool: asyncpg.Pool = db.pool
        self._bitrix = bitrix
        self._dedup_cache: dict[str, datetime] = {}  # {message_id: timestamp}
        self._dedup_ttl_seconds = 60

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """Validate required fields in Wappi webhook payload.

        Raises:
            KeyError: If required field is missing.
            ValueError: If required field is empty.
        """
        required_fields = ["message_type", "from", "body", "message_id", "timestamp", "chat_id"]

        for field in required_fields:
            if field not in payload:
                raise KeyError(f"Missing required field: {field}")
            if payload[field] is None or (isinstance(payload[field], str) and not payload[field].strip()):
                raise ValueError(f"Required field cannot be empty: {field}")

    def _is_duplicate(self, message_id: str) -> bool:
        """Check if message_id is in dedup cache and not expired.

        Args:
            message_id: Unique message identifier from Wappi.

        Returns:
            True if duplicate (exists in cache and not expired), False otherwise.
        """
        if message_id not in self._dedup_cache:
            return False

        cached_time = self._dedup_cache[message_id]
        is_expired = datetime.now() - cached_time > timedelta(seconds=self._dedup_ttl_seconds)

        if is_expired:
            # Cleanup expired entry
            del self._dedup_cache[message_id]
            return False

        return True

    _DEDUP_MAX_SIZE = 10000

    def _cleanup_dedup_cache(self) -> None:
        """Evict oldest half of entries when cache exceeds max size."""
        if len(self._dedup_cache) > self._DEDUP_MAX_SIZE:
            keys_to_remove = list(self._dedup_cache.keys())[: self._DEDUP_MAX_SIZE // 2]
            for k in keys_to_remove:
                del self._dedup_cache[k]

    def _add_to_dedup_cache(self, message_id: str) -> None:
        """Add message_id to deduplication cache.

        Args:
            message_id: Unique message identifier to cache.
        """
        self._cleanup_dedup_cache()
        self._dedup_cache[message_id] = datetime.now()

    async def _find_or_create_user_mapping(
        self,
        chat_id: str,
        phone: str,
    ) -> tuple[str, str]:
        """Find existing user mapping or create new one.

        Strategy:
        1. Find by wappi_chat_id (existing user)
        2. Find by phone in Bitrix (existing deal)
        3. Create new mapping for new user

        Args:
            chat_id: Wappi chat_id (Telegram chat_id for telegram).
            phone: Sender phone number.

        Returns:
            Tuple of (user_id_or_chat_id, phone).
        """
        # 1. Find existing by chat_id
        existing = await self._pool.fetchrow(
            "SELECT * FROM user_mappings WHERE wappi_chat_id = $1",
            chat_id,
        )

        if existing:
            logger.info("user_mapping_found_by_chat_id", chat_id=chat_id)
            return (chat_id, phone)

        # 2. Find by phone in Bitrix
        deals = await self._bitrix.find_deals_by_phone(phone)

        if deals:
            deal = deals[0]
            deal_id = deal.get("ID")
            contact_id = deal.get("CONTACT_ID")

            # Create mapping for existing deal
            await self._pool.execute(
                """INSERT INTO user_mappings (wappi_chat_id, bitrix_deal_id, bitrix_contact_id, channel, phone)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (wappi_chat_id) DO UPDATE SET
                     bitrix_deal_id = EXCLUDED.bitrix_deal_id,
                     updated_at = NOW()""",
                chat_id,
                deal_id,
                contact_id,
                "telegram",
                phone,
            )
            logger.info("user_mapping_created_from_bitrix_deal", chat_id=chat_id, deal_id=deal_id)
            return (chat_id, phone)

        # 3. New user without a known deal — escalate (no mapping created)
        logger.info("user_mapping_no_deal_found", chat_id=chat_id, phone=phone)
        return (chat_id, phone)

    async def process_message(self, payload: dict[str, Any]) -> tuple[str, str] | None:
        """Process incoming Wappi webhook message.

        Args:
            payload: Webhook payload from Wappi.

        Returns:
            Tuple of (chat_id, phone) if processed successfully, None if duplicate.

        Raises:
            KeyError: If required field is missing.
            ValueError: If required field is invalid.
        """
        # Validate payload structure
        self._validate_payload(payload)

        message_id: str = payload["message_id"]
        chat_id: str = payload["chat_id"]
        phone: str = payload["from"]
        body: str = payload["body"]
        payload["timestamp"]
        message_type: str = payload["message_type"]

        # Check deduplication
        if self._is_duplicate(message_id):
            logger.info("message_skipped_duplicate", message_id=message_id, chat_id=chat_id)
            return None

        # Add to dedup cache
        self._add_to_dedup_cache(message_id)

        # Find or create user mapping
        chat_id_result, phone_result = await self._find_or_create_user_mapping(
            chat_id=chat_id,
            phone=phone,
        )

        # Log incoming message
        await self._pool.execute(
            """INSERT INTO dialog_logs (wappi_chat_id, role, message, agent_type)
               VALUES ($1, $2, $3, $4)""",
            chat_id_result,
            "user",
            body,
            None,
        )

        logger.info(
            "message_processed",
            message_id=message_id,
            chat_id=chat_id_result,
            message_type=message_type,
        )

        return (chat_id_result, phone_result)
