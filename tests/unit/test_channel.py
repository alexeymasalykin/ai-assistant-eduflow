"""Tests for Channel detection (Telegram vs MAX Messenger)."""

from __future__ import annotations

from integrations.wappi.channel import Channel


class TestChannel:
    """Test Channel enum and detection logic."""

    def test_telegram_when_no_max_profile(self) -> None:
        result = Channel.from_profile_id("12345", "")
        assert result == Channel.TELEGRAM

    def test_telegram_when_profile_differs(self) -> None:
        result = Channel.from_profile_id("12345", "99999")
        assert result == Channel.TELEGRAM

    def test_max_when_profile_matches(self) -> None:
        result = Channel.from_profile_id("99999", "99999")
        assert result == Channel.MAX

    def test_channel_values(self) -> None:
        assert Channel.TELEGRAM.value == "telegram"
        assert Channel.MAX.value == "max"

    def test_telegram_is_default(self) -> None:
        """Empty profile_id defaults to Telegram."""
        result = Channel.from_profile_id("", "99999")
        assert result == Channel.TELEGRAM

    def test_max_detection_in_incoming_handler(self) -> None:
        """Simulate incoming payload with MAX profile_id."""
        from unittest.mock import MagicMock

        from integrations.wappi.incoming import WappiIncomingHandler

        db = MagicMock()
        db.pool = MagicMock()
        bitrix = MagicMock()

        handler = WappiIncomingHandler(
            db=db, bitrix=bitrix, max_profile_id="max-profile-123"
        )

        # Telegram payload (no profile_id match)
        tg_payload = {"profile_id": "tg-profile-456"}
        assert handler._detect_channel(tg_payload) == Channel.TELEGRAM

        # MAX payload (profile_id matches)
        max_payload = {"profile_id": "max-profile-123"}
        assert handler._detect_channel(max_payload) == Channel.MAX

        # Missing profile_id → Telegram
        empty_payload: dict[str, str] = {}
        assert handler._detect_channel(empty_payload) == Channel.TELEGRAM
