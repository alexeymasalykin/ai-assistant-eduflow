from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from config import Settings

logger = structlog.get_logger()


class WappiOutgoingHandler:
    """Send messages via Wappi API."""

    def __init__(self, config: Settings, http_client: httpx.AsyncClient) -> None:
        self._config = config
        self._http_client = http_client
        self._base_url = "https://api.wappi.com.br/api"  # Wappi API base URL
        self._timeout = 15.0

    def _build_headers(self) -> dict[str, str]:
        """Build authorization headers for Wappi API.

        Returns:
            Dictionary with Authorization header using Bearer token.
        """
        return {
            "Authorization": f"Bearer {self._config.wappi_api_token}",
            "Content-Type": "application/json",
        }

    async def send_message(
        self,
        chat_id: str = "",
        text: str = "",
        phone: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """Send message via Wappi API.

        Supports both chat_id (Telegram) and phone (fallback) routing.

        Args:
            chat_id: Chat ID from Telegram (preferred for routing).
            text: Message body to send.
            phone: Phone number (fallback if chat_id unavailable).
            **kwargs: Additional parameters (media_url, etc.).

        Returns:
            True if message sent successfully, False on error.
        """
        # Validate input
        if not text:
            logger.warning("send_message_empty_text")
            return False

        if not chat_id and not phone:
            logger.warning("send_message_missing_routing_info")
            return False

        # Build payload
        payload: dict[str, Any] = {"body": text}

        # Use chat_id if available (Telegram), fallback to phone (WhatsApp)
        if chat_id:
            payload["chat_id"] = chat_id
        else:
            payload["recipient"] = phone

        # Add optional parameters
        if "media_url" in kwargs:
            payload["media_url"] = kwargs["media_url"]

        # Send via API
        try:
            headers = self._build_headers()
            response = await self._http_client.post(
                f"{self._base_url}/send",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )

            response.raise_for_status()
            _ = response.json()

            logger.info(
                "message_sent_successfully",
                chat_id=chat_id,
                phone=phone,
                response_status=response.status_code,
            )

            return True

        except httpx.HTTPError as e:
            logger.error(
                "message_send_failed",
                chat_id=chat_id,
                phone=phone,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "message_send_unexpected_error",
                chat_id=chat_id,
                phone=phone,
                error=str(e),
            )
            return False

    async def mark_as_read(self, message_id: str) -> bool:
        """Mark message as read in Wappi.

        Args:
            message_id: Message ID to mark as read.

        Returns:
            True if marked successfully, False on error.
        """
        try:
            payload = {"message_id": message_id}
            headers = self._build_headers()
            response = await self._http_client.post(
                f"{self._base_url}/mark/read",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )

            response.raise_for_status()
            logger.info("message_marked_read", message_id=message_id)
            return True

        except httpx.HTTPError as e:
            logger.error("mark_read_failed", message_id=message_id, error=str(e))
            return False
