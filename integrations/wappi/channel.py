"""Channel detection for multi-messenger support.

Distinguishes between Telegram and MAX Messenger based on Wappi profile_id.
Both channels use numeric chat_id, so profile_id is the only reliable way
to determine the source channel.
"""

from __future__ import annotations

from enum import Enum


class Channel(str, Enum):
    """Supported messaging channels via Wappi."""

    TELEGRAM = "telegram"
    MAX = "max"

    @classmethod
    def from_profile_id(
        cls, profile_id: str, max_profile_id: str
    ) -> Channel:
        """Determine channel by comparing profile_id to MAX profile.

        Both Telegram and MAX use numeric chat_id in Wappi,
        so profile_id is the only way to distinguish them.

        Args:
            profile_id: Wappi profile_id from webhook payload.
            max_profile_id: WAPPI_MAX_PROFILE_ID from config.

        Returns:
            Channel.MAX if profile matches, Channel.TELEGRAM otherwise.
        """
        if max_profile_id and profile_id == max_profile_id:
            return cls.MAX
        return cls.TELEGRAM
