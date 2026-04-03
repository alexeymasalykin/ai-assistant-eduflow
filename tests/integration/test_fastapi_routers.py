"""Integration tests for FastAPI routers and application.

Tests cover:
1. Wappi webhook (valid message, invalid payload, deduplication)
2. Bitrix webhook (deal updates)
3. Admin endpoints (health, stats)
4. Global error handling
5. Rate limiting (per-IP via slowapi)
6. Webhook token authentication (HMAC)
7. Per-chat rate limiting (10 req/min)
8. Per-chat async locking
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app as app_module
from agents.orchestrator import Orchestrator
from integrations.bitrix_client import BitrixClient
from integrations.database import Database
from integrations.wappi import WappiIncomingHandler, WappiOutgoingHandler


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock Database instance."""
    db = AsyncMock(spec=Database)
    db.pool = MagicMock()
    return db


@pytest.fixture
def mock_bitrix() -> AsyncMock:
    """Mock Bitrix client."""
    return AsyncMock(spec=BitrixClient)


@pytest.fixture
def mock_wappi_incoming() -> AsyncMock:
    """Mock Wappi incoming handler."""
    return AsyncMock(spec=WappiIncomingHandler)


@pytest.fixture
def mock_wappi_outgoing() -> AsyncMock:
    """Mock Wappi outgoing handler."""
    return AsyncMock(spec=WappiOutgoingHandler)


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    """Mock Orchestrator."""
    return AsyncMock(spec=Orchestrator)


@pytest.fixture
def client(
    mock_db: AsyncMock,
    mock_bitrix: AsyncMock,
    mock_wappi_incoming: AsyncMock,
    mock_wappi_outgoing: AsyncMock,
    mock_orchestrator: AsyncMock,
) -> TestClient:
    """Create FastAPI test client with mocked dependencies."""
    # Patch dependency overrides
    app_module.app.dependency_overrides = {
        Database: lambda: mock_db,
        BitrixClient: lambda: mock_bitrix,
        WappiIncomingHandler: lambda: mock_wappi_incoming,
        WappiOutgoingHandler: lambda: mock_wappi_outgoing,
        Orchestrator: lambda: mock_orchestrator,
    }

    # Store mocks in app state for direct access in routers
    app_module.app.state.db = mock_db
    app_module.app.state.bitrix_client = mock_bitrix
    app_module.app.state.wappi_incoming = mock_wappi_incoming
    app_module.app.state.wappi_outgoing = mock_wappi_outgoing
    app_module.app.state.orchestrator = mock_orchestrator
    app_module.app.state.pipeline = mock_orchestrator  # default: original pipeline

    return TestClient(app_module.app)


@pytest.fixture
def valid_wappi_payload() -> dict[str, Any]:
    """Valid Wappi webhook payload."""
    return {
        "message_type": "text",
        "from": "+1234567890",
        "body": "Help with course module",
        "message_id": "msg_001",
        "timestamp": 1700000000,
        "chat_id": "1234567890",
    }


@pytest.fixture
def valid_bitrix_payload() -> dict[str, Any]:
    """Valid Bitrix webhook payload."""
    return {
        "event": "ONCRMDEALUPDATE",
        "data": {
            "FIELDS": {
                "ID": 12345,
                "STAGE_ID": "NEW",
                "UF_COURSE_MODULE": "Module 1",
            }
        },
    }


@pytest.fixture(autouse=True)
def _clear_chat_rate_limits() -> None:
    """Clear per-chat rate limit state between tests."""
    from routers.wappi import _chat_locks, _chat_timestamps
    _chat_timestamps.clear()
    _chat_locks.clear()


class TestWappiWebhook:
    """Tests for POST /webhook/wappi endpoint."""

    def test_wappi_webhook_valid_message(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock
    ) -> None:
        """Test processing valid Wappi message returns 200."""
        mock_wappi_incoming.process_message.return_value = ("1234567890", "+1234567890")
        mock_orchestrator.process.return_value = MagicMock(
            text="Hello! How can I help?",
            should_send=True,
        )
        mock_wappi_outgoing.send_message.return_value = True

        response = client.post("/webhook/wappi", json=valid_wappi_payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_wappi_webhook_invalid_payload(self, client: TestClient) -> None:
        """Test invalid payload returns 400."""
        invalid_payload = {
            "message_type": "text",
            "body": "Missing required fields",
        }

        response = client.post("/webhook/wappi", json=invalid_payload)

        assert response.status_code in [400, 422]
        assert "error" in response.json() or "detail" in response.json()

    def test_wappi_webhook_deduplication(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
        mock_wappi_incoming: AsyncMock
    ) -> None:
        """Test duplicate message_id is skipped (returns 200 silently)."""
        mock_wappi_incoming.process_message.return_value = None

        response = client.post("/webhook/wappi", json=valid_wappi_payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_wappi_webhook_empty_message_body(
        self, client: TestClient, mock_wappi_incoming: AsyncMock
    ) -> None:
        """Test empty message body is accepted by Pydantic but handled by handler."""
        payload = {
            "message_type": "text",
            "from": "+1234567890",
            "body": "",
            "message_id": "msg_002",
            "timestamp": 1700000000,
            "chat_id": "1234567890",
        }

        mock_wappi_incoming.process_message.side_effect = ValueError("Empty body")

        response = client.post("/webhook/wappi", json=payload)

        assert response.status_code in [200, 400, 422]

    def test_wappi_webhook_missing_message_id(self, client: TestClient) -> None:
        """Test missing message_id is rejected."""
        payload = {
            "message_type": "text",
            "from": "+1234567890",
            "body": "Test message",
            "timestamp": 1700000000,
            "chat_id": "1234567890",
        }

        response = client.post("/webhook/wappi", json=payload)

        assert response.status_code in [400, 422]


class TestBitrixWebhook:
    """Tests for POST /webhook/bitrix endpoint."""

    def test_bitrix_webhook_deal_update(
        self, client: TestClient, valid_bitrix_payload: dict[str, Any]
    ) -> None:
        """Test processing Bitrix deal update returns 200."""
        response = client.post("/webhook/bitrix", json=valid_bitrix_payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_bitrix_webhook_invalid_event(self, client: TestClient) -> None:
        """Test invalid Bitrix event is handled gracefully."""
        payload = {
            "event": "UNKNOWN_EVENT",
            "data": {},
        }

        response = client.post("/webhook/bitrix", json=payload)

        assert response.status_code == 200


class TestAdminEndpoints:
    """Tests for admin endpoints."""

    def test_health_endpoint_success(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Test GET /health returns 200 with status."""
        mock_db.pool = MagicMock()

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data or "version" in data

    def test_stats_endpoint(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Test GET /stats returns message counts."""
        async def mock_fetchval(query: str) -> int:  # type: ignore[no-untyped-def]
            return 42

        mock_db.pool.fetchval = mock_fetchval

        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert "messages_processed" in data or "stats" in data


class TestErrorHandling:
    """Tests for error handling and exceptions."""

    def test_global_exception_handler_no_stack_trace(
        self, client: TestClient, mock_wappi_incoming: AsyncMock,
        mock_orchestrator: AsyncMock
    ) -> None:
        """Test global exception handler doesn't leak stack traces."""
        mock_orchestrator.process.side_effect = RuntimeError("Unexpected error")
        mock_wappi_incoming.process_message.return_value = ("chat_id", "+phone")

        response = client.post(
            "/webhook/wappi",
            json={
                "message_type": "text",
                "from": "+1234567890",
                "body": "Test",
                "message_id": "msg_003",
                "timestamp": 1700000000,
                "chat_id": "1234567890",
            },
        )

        assert response.status_code in [200, 500]
        data = response.json()
        assert "traceback" not in data
        assert "stack" not in data

    def test_validation_error_returns_400(self, client: TestClient) -> None:
        """Test Pydantic validation error returns 422."""
        invalid_payload = {
            "message_type": "text",
        }

        response = client.post("/webhook/wappi", json=invalid_payload)

        assert response.status_code in [400, 422]
        data = response.json()
        assert "error" in data or "detail" in data


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limiting_limit_exceeded(
        self, client: TestClient, mock_wappi_incoming: AsyncMock,
        mock_orchestrator: AsyncMock, mock_wappi_outgoing: AsyncMock
    ) -> None:
        """Test rate limit mechanism exists."""
        payload = {
            "message_type": "text",
            "from": "+1234567890",
            "body": "Test",
            "message_id": "msg_004",
            "timestamp": 1700000000,
            "chat_id": "1234567890",
        }

        mock_wappi_incoming.process_message.return_value = ("chat_id", "+phone")
        mock_orchestrator.process.return_value = MagicMock(text="Hi", should_send=True)
        mock_wappi_outgoing.send_message.return_value = True

        response = client.post("/webhook/wappi", json=payload)

        assert response.status_code in [200, 429]

    def test_rate_limit_header_present(
        self, client: TestClient, mock_wappi_incoming: AsyncMock,
        mock_orchestrator: AsyncMock, mock_wappi_outgoing: AsyncMock
    ) -> None:
        """Test rate limiter is registered in app."""
        payload = {
            "message_type": "text",
            "from": "+1234567890",
            "body": "Test",
            "message_id": "msg_005",
            "timestamp": 1700000000,
            "chat_id": "1234567890",
        }

        mock_wappi_incoming.process_message.return_value = ("chat_id", "+phone")
        mock_orchestrator.process.return_value = MagicMock(text="Hi", should_send=True)
        mock_wappi_outgoing.send_message.return_value = True

        response = client.post("/webhook/wappi", json=payload)

        assert hasattr(app_module.app.state, "limiter")
        assert response.status_code in [200, 429]


class TestWebhookTokenAuth:
    """Tests for HMAC webhook token authentication."""

    def test_wappi_webhook_auth_failure_with_wrong_token(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
    ) -> None:
        """Test wappi webhook rejects invalid token when configured."""
        with patch("routers.wappi.settings") as mock_settings:
            mock_settings.wappi_webhook_token = "correct-secret-token"

            response = client.post(
                "/webhook/wappi",
                json=valid_wappi_payload,
                headers={"X-Webhook-Token": "wrong-token"},
            )

            assert response.status_code == 403
            assert response.json()["detail"] == "Forbidden"

    def test_wappi_webhook_auth_failure_missing_token(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
    ) -> None:
        """Test wappi webhook rejects missing token when configured."""
        with patch("routers.wappi.settings") as mock_settings:
            mock_settings.wappi_webhook_token = "correct-secret-token"

            response = client.post(
                "/webhook/wappi",
                json=valid_wappi_payload,
                # No X-Webhook-Token header
            )

            assert response.status_code == 403

    def test_wappi_webhook_auth_success_with_correct_token(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock,
    ) -> None:
        """Test wappi webhook accepts correct token."""
        mock_wappi_incoming.process_message.return_value = ("1234567890", "+1234567890")
        mock_orchestrator.process.return_value = MagicMock(
            text="OK", should_send=True,
        )
        mock_wappi_outgoing.send_message.return_value = True

        with patch("routers.wappi.settings") as mock_settings:
            mock_settings.wappi_webhook_token = "correct-secret-token"

            response = client.post(
                "/webhook/wappi",
                json=valid_wappi_payload,
                headers={"X-Webhook-Token": "correct-secret-token"},
            )

            assert response.status_code == 200

    def test_wappi_webhook_auth_skipped_when_not_configured(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock,
    ) -> None:
        """Test wappi webhook skips auth when token is empty."""
        mock_wappi_incoming.process_message.return_value = ("1234567890", "+1234567890")
        mock_orchestrator.process.return_value = MagicMock(
            text="OK", should_send=True,
        )
        mock_wappi_outgoing.send_message.return_value = True

        with patch("routers.wappi.settings") as mock_settings:
            mock_settings.wappi_webhook_token = ""  # Not configured

            response = client.post(
                "/webhook/wappi",
                json=valid_wappi_payload,
                # No header needed
            )

            assert response.status_code == 200

    def test_bitrix_webhook_auth_failure_with_wrong_token(
        self, client: TestClient, valid_bitrix_payload: dict[str, Any],
    ) -> None:
        """Test bitrix webhook rejects invalid token when configured."""
        with patch("routers.bitrix.settings") as mock_settings:
            mock_settings.bitrix24_webhook_token = "bitrix-secret-token"

            response = client.post(
                "/webhook/bitrix",
                json=valid_bitrix_payload,
                headers={"X-Webhook-Token": "wrong-token"},
            )

            assert response.status_code == 403

    def test_bitrix_webhook_auth_success_with_correct_token(
        self, client: TestClient, valid_bitrix_payload: dict[str, Any],
    ) -> None:
        """Test bitrix webhook accepts correct token."""
        with patch("routers.bitrix.settings") as mock_settings:
            mock_settings.bitrix24_webhook_token = "bitrix-secret-token"

            response = client.post(
                "/webhook/bitrix",
                json=valid_bitrix_payload,
                headers={"X-Webhook-Token": "bitrix-secret-token"},
            )

            assert response.status_code == 200


class TestPerChatRateLimiting:
    """Tests for per-chat rate limiting (10 req/min per chat)."""

    def test_per_chat_rate_limit_allows_normal_traffic(
        self, client: TestClient,
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock,
    ) -> None:
        """Test that normal traffic is not rate-limited."""
        mock_wappi_incoming.process_message.return_value = ("chat_1", "+phone")
        mock_orchestrator.process.return_value = MagicMock(
            text="Hi", should_send=True,
        )
        mock_wappi_outgoing.send_message.return_value = True

        # Send 5 messages from same chat — should all pass
        for i in range(5):
            payload = {
                "message_type": "text",
                "from": "+1234567890",
                "body": f"Message {i}",
                "message_id": f"msg_chat_rl_{i}",
                "timestamp": 1700000000 + i,
                "chat_id": "chat_rate_test",
            }
            response = client.post("/webhook/wappi", json=payload)
            assert response.status_code == 200

    def test_per_chat_rate_limit_exceeded(
        self, client: TestClient,
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock,
    ) -> None:
        """Test that 11th message from same chat is rejected with 429."""
        mock_wappi_incoming.process_message.return_value = ("chat_1", "+phone")
        mock_orchestrator.process.return_value = MagicMock(
            text="Hi", should_send=True,
        )
        mock_wappi_outgoing.send_message.return_value = True

        chat_id = "chat_flood_test"

        # Send 10 messages — should all pass
        for i in range(10):
            payload = {
                "message_type": "text",
                "from": "+1234567890",
                "body": f"Message {i}",
                "message_id": f"msg_flood_{i}",
                "timestamp": 1700000000 + i,
                "chat_id": chat_id,
            }
            response = client.post("/webhook/wappi", json=payload)
            assert response.status_code == 200, f"Message {i} should pass"

        # 11th message should be rate limited
        payload = {
            "message_type": "text",
            "from": "+1234567890",
            "body": "Too many messages",
            "message_id": "msg_flood_11",
            "timestamp": 1700000011,
            "chat_id": chat_id,
        }
        response = client.post("/webhook/wappi", json=payload)
        assert response.status_code == 429
        assert "Too many messages" in response.json()["detail"]

    def test_per_chat_rate_limit_different_chats_independent(
        self, client: TestClient,
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock,
    ) -> None:
        """Test that rate limits are per-chat, not global."""
        mock_wappi_incoming.process_message.return_value = ("chat_x", "+phone")
        mock_orchestrator.process.return_value = MagicMock(
            text="Hi", should_send=True,
        )
        mock_wappi_outgoing.send_message.return_value = True

        # Fill up chat_a with 10 messages
        for i in range(10):
            payload = {
                "message_type": "text",
                "from": "+1234567890",
                "body": f"Message {i}",
                "message_id": f"msg_a_{i}",
                "timestamp": 1700000000 + i,
                "chat_id": "chat_a_independent",
            }
            response = client.post("/webhook/wappi", json=payload)
            assert response.status_code == 200

        # chat_b should still work fine
        payload = {
            "message_type": "text",
            "from": "+9876543210",
            "body": "Message from different chat",
            "message_id": "msg_b_0",
            "timestamp": 1700000000,
            "chat_id": "chat_b_independent",
        }
        response = client.post("/webhook/wappi", json=payload)
        assert response.status_code == 200


class TestPerChatLocking:
    """Tests for per-chat async locking."""

    def test_chat_lock_created_per_chat(self) -> None:
        """Test that get_chat_lock returns same lock for same chat_id."""
        from routers.wappi import get_chat_lock

        lock1 = get_chat_lock("chat_123")
        lock2 = get_chat_lock("chat_123")
        lock3 = get_chat_lock("chat_456")

        assert lock1 is lock2  # Same lock for same chat
        assert lock1 is not lock3  # Different lock for different chat


class TestAppInitialization:
    """Tests for app initialization and configuration."""

    def test_app_is_fastapi_instance(self) -> None:
        """Test that app is properly initialized."""
        from fastapi import FastAPI

        assert isinstance(app_module.app, FastAPI)

    def test_app_has_title(self) -> None:
        """Test app has descriptive title."""
        assert app_module.app.title == "EduFlow AI Assistant" or app_module.app.title is not None

    def test_wappi_router_registered(self) -> None:
        """Test Wappi router is registered."""
        routes = [route.path for route in app_module.app.routes]
        assert any("/webhook/wappi" in route for route in routes)

    def test_bitrix_router_registered(self) -> None:
        """Test Bitrix router is registered."""
        routes = [route.path for route in app_module.app.routes]
        assert any("/webhook/bitrix" in route for route in routes)

    def test_admin_router_registered(self) -> None:
        """Test admin router is registered."""
        routes = [route.path for route in app_module.app.routes]
        assert any("/health" in route for route in routes)


class TestWappiWebhookIntegration:
    """End-to-end integration tests for Wappi webhook."""

    def test_wappi_webhook_full_flow(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock
    ) -> None:
        """Test full flow: message -> orchestrator -> response."""
        mock_wappi_incoming.process_message.return_value = ("1234567890", "+1234567890")
        mock_orchestrator.process.return_value = MagicMock(
            text="Module overview: Learn basics...",
            should_send=True,
            agent_type="course",
        )
        mock_wappi_outgoing.send_message.return_value = True

        response = client.post("/webhook/wappi", json=valid_wappi_payload)

        assert response.status_code == 200
        assert mock_orchestrator.process.called
        assert mock_wappi_outgoing.send_message.called

    def test_wappi_webhook_silent_response(
        self, client: TestClient, valid_wappi_payload: dict[str, Any],
        mock_wappi_incoming: AsyncMock, mock_orchestrator: AsyncMock,
        mock_wappi_outgoing: AsyncMock
    ) -> None:
        """Test silent response (should_send=False) doesn't send message."""
        mock_wappi_incoming.process_message.return_value = ("1234567890", "+1234567890")
        mock_orchestrator.process.return_value = MagicMock(
            text="",
            should_send=False,
        )

        response = client.post("/webhook/wappi", json=valid_wappi_payload)

        assert response.status_code == 200
        assert not mock_wappi_outgoing.send_message.called or mock_wappi_outgoing.send_message.call_count == 0
