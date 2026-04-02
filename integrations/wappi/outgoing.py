"""Send messages via Wappi API (Telegram and MAX Messenger).

Telegram uses /api/sync/message/send endpoint.
MAX Messenger uses /maxapi/async/message/send endpoint.
File/media sending for MAX uses /maxapi/async/message/file/url/send.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from integrations.wappi.channel import Channel

if TYPE_CHECKING:
    from config import Settings

logger = structlog.get_logger()

# API endpoint paths per channel
_ENDPOINTS: dict[Channel, dict[str, str]] = {
    Channel.TELEGRAM: {
        "send": "/api/sync/message/send",
        "file": "/api/sync/message/send",
        "read": "/api/sync/message/read",
    },
    Channel.MAX: {
        "send": "/maxapi/async/message/send",
        "file": "/maxapi/async/message/file/url/send",
        "read": "/maxapi/async/message/read",
    },
}


class WappiOutgoingHandler:
    """Send messages via Wappi API to Telegram or MAX Messenger."""

    def __init__(self, config: Settings, http_client: httpx.AsyncClient) -> None:
        self._config = config
        self._http_client = http_client
        self._base_url = "https://wappi.pro"
        self._timeout = 15.0

    def _build_headers(self, profile_id: str = "") -> dict[str, str]:
        """Build authorization headers for Wappi API.

        Args:
            profile_id: Wappi profile_id (uses default if empty).

        Returns:
            Dictionary with Authorization and profile_id headers.
        """
        headers = {
            "Authorization": self._config.wappi_api_token,
            "Content-Type": "application/json",
        }
        pid = profile_id or self._config.wappi_profile_id
        if pid:
            headers["profile_id"] = pid
        return headers

    def _get_profile_id(self, channel: Channel) -> str:
        """Get Wappi profile_id for the given channel.

        Args:
            channel: Target messaging channel.

        Returns:
            Profile ID string for the channel.
        """
        if channel == Channel.MAX:
            return self._config.wappi_max_profile_id
        return self._config.wappi_profile_id

    async def send_message(
        self,
        chat_id: str = "",
        text: str = "",
        phone: str | None = None,
        channel: Channel = Channel.TELEGRAM,
        **kwargs: Any,
    ) -> bool:
        """Send text message via Wappi API.

        Supports both Telegram and MAX Messenger. Channel determines
        which API endpoint and profile_id to use.

        Args:
            chat_id: Chat ID (numeric for both Telegram and MAX).
            text: Message body to send.
            phone: Phone number (fallback routing for Telegram/WhatsApp).
            channel: Target channel (TELEGRAM or MAX).
            **kwargs: Additional parameters (media_url, etc.).

        Returns:
            True if message sent successfully, False on error.
        """
        if not text:
            logger.warning("send_message_empty_text")
            return False

        if not chat_id and not phone:
            logger.warning("send_message_missing_routing_info")
            return False

        # Build payload — MAX uses dialog_id instead of chat_id
        payload: dict[str, Any] = {"body": text}

        if chat_id:
            payload["chat_id"] = chat_id
        elif phone:
            payload["recipient"] = phone

        if "media_url" in kwargs:
            payload["media_url"] = kwargs["media_url"]

        # Select endpoint and profile for channel
        profile_id = self._get_profile_id(channel)
        endpoint_key = "file" if "media_url" in kwargs else "send"
        endpoint = _ENDPOINTS[channel][endpoint_key]

        try:
            headers = self._build_headers(profile_id)
            response = await self._http_client.post(
                f"{self._base_url}{endpoint}",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()

            logger.info(
                "message_sent_successfully",
                chat_id=chat_id,
                channel=channel.value,
                response_status=response.status_code,
            )
            return True

        except httpx.HTTPError as e:
            logger.error(
                "message_send_failed",
                chat_id=chat_id,
                channel=channel.value,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "message_send_unexpected_error",
                chat_id=chat_id,
                channel=channel.value,
                error=str(e),
            )
            return False

    async def mark_as_read(
        self,
        message_id: str,
        channel: Channel = Channel.TELEGRAM,
    ) -> bool:
        """Mark message as read in Wappi.

        Note: MAX Messenger mark/read uses only message_id (no recipient).

        Args:
            message_id: Message ID to mark as read.
            channel: Source channel of the message.

        Returns:
            True if marked successfully, False on error.
        """
        try:
            payload: dict[str, str] = {"message_id": message_id}
            profile_id = self._get_profile_id(channel)
            headers = self._build_headers(profile_id)
            endpoint = _ENDPOINTS[channel]["read"]

            response = await self._http_client.post(
                f"{self._base_url}{endpoint}",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            logger.info(
                "message_marked_read",
                message_id=message_id,
                channel=channel.value,
            )
            return True

        except httpx.HTTPError as e:
            logger.error(
                "mark_read_failed",
                message_id=message_id,
                channel=channel.value,
                error=str(e),
            )
            return False
