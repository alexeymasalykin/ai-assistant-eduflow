from __future__ import annotations

import pytest

from config import Settings


class TestProductionSecretsEnforcement:
    """Verify that production mode requires all security tokens."""

    def _prod_settings(self, **kwargs: str) -> Settings:
        """Helper: create Settings with log_format=json (production)."""
        return Settings(_env_file=None, log_format="json", **kwargs)

    def _dev_settings(self, **kwargs: str) -> Settings:
        """Helper: create Settings with log_format=console (development)."""
        return Settings(_env_file=None, log_format="console", **kwargs)

    # --- Production must reject empty tokens ---

    def test_production_requires_wappi_webhook_token(self) -> None:
        """Production raises ValueError when WAPPI_WEBHOOK_TOKEN is empty."""
        with pytest.raises(ValueError, match="wappi_webhook_token"):
            self._prod_settings(
                bitrix24_webhook_token="bx-secret",
                admin_api_key="admin-secret",
                wappi_webhook_token="",
            )

    def test_production_requires_bitrix24_webhook_token(self) -> None:
        """Production raises ValueError when BITRIX24_WEBHOOK_TOKEN is empty."""
        with pytest.raises(ValueError, match="bitrix24_webhook_token"):
            self._prod_settings(
                wappi_webhook_token="wappi-secret",
                admin_api_key="admin-secret",
                bitrix24_webhook_token="",
            )

    def test_production_requires_admin_api_key(self) -> None:
        """Production raises ValueError when ADMIN_API_KEY is empty."""
        with pytest.raises(ValueError, match="admin_api_key"):
            self._prod_settings(
                wappi_webhook_token="wappi-secret",
                bitrix24_webhook_token="bx-secret",
                admin_api_key="",
            )

    def test_production_reports_all_missing_tokens_at_once(self) -> None:
        """Production error lists all three missing vars in a single message."""
        with pytest.raises(ValueError) as exc_info:
            self._prod_settings(
                wappi_webhook_token="",
                bitrix24_webhook_token="",
                admin_api_key="",
            )
        message = str(exc_info.value)
        assert "wappi_webhook_token" in message
        assert "bitrix24_webhook_token" in message
        assert "admin_api_key" in message

    # --- Production succeeds when all tokens are present ---

    def test_production_succeeds_with_all_tokens(self) -> None:
        """Production starts normally when all required tokens are set."""
        s = self._prod_settings(
            wappi_webhook_token="wappi-secret",
            bitrix24_webhook_token="bx-secret",
            admin_api_key="admin-secret",
        )
        assert s.log_format == "json"
        assert s.wappi_webhook_token == "wappi-secret"
        assert s.bitrix24_webhook_token == "bx-secret"
        assert s.admin_api_key == "admin-secret"

    # --- Dev mode allows empty tokens ---

    def test_dev_allows_empty_tokens(self) -> None:
        """Dev mode (log_format=console) starts fine with all tokens empty."""
        s = self._dev_settings(
            wappi_webhook_token="",
            bitrix24_webhook_token="",
            admin_api_key="",
        )
        assert s.log_format == "console"

    def test_dev_allows_partial_tokens(self) -> None:
        """Dev mode accepts any combination of present/absent tokens."""
        s = self._dev_settings(
            wappi_webhook_token="wappi-secret",
            bitrix24_webhook_token="",
            admin_api_key="",
        )
        assert s.wappi_webhook_token == "wappi-secret"
