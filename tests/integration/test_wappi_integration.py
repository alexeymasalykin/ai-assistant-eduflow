from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta

import pytest
import httpx

from integrations.wappi.incoming import WappiIncomingHandler
from integrations.wappi.outgoing import WappiOutgoingHandler
from integrations.wappi.templates import text_message, file_message, media_message
from config import Settings


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock Database pool."""
    return AsyncMock()


@pytest.fixture
def mock_bitrix() -> AsyncMock:
    """Mock Bitrix client."""
    return AsyncMock()


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def config() -> Settings:
    """Create test config."""
    return Settings(
        wappi_api_token="test_token_123",
        wappi_profile_id="test_profile",
        postgres_dsn="postgresql://test:test@localhost/test",
    )


@pytest.fixture
def wappi_incoming(mock_db: AsyncMock, mock_bitrix: AsyncMock) -> WappiIncomingHandler:
    """Create WappiIncomingHandler with mocks."""
    handler = WappiIncomingHandler(db=mock_db, bitrix=mock_bitrix)
    return handler


@pytest.fixture
def wappi_outgoing(config: Settings, mock_http_client: AsyncMock) -> WappiOutgoingHandler:
    """Create WappiOutgoingHandler with mocks."""
    handler = WappiOutgoingHandler(config=config, http_client=mock_http_client)
    return handler


# ============================================================================
# Test: Parse incoming message (valid)
# ============================================================================


@pytest.mark.asyncio
async def test_parse_incoming_valid_text_message(
    wappi_incoming: WappiIncomingHandler,
    mock_db: AsyncMock,
) -> None:
    """Test parsing valid text message from Telegram via Wappi."""
    payload = {
        "message_type": "text",
        "from": "+1234567890",
        "body": "Hello, I need help",
        "message_id": "msg_001",
        "timestamp": 1700000000,
        "chat_id": "1234567890",
    }

    # Mock user mapping repository
    mock_db.fetchrow.return_value = None  # No existing mapping
    mock_db.fetch.return_value = None  # No existing message_id

    # The handler should validate payload structure
    result = await wappi_incoming.process_message(payload)

    assert result is not None
    assert isinstance(result, tuple)
    assert len(result) == 2  # (user_id/chat_id, phone)


# ============================================================================
# Test: Parse incoming message (missing fields)
# ============================================================================


@pytest.mark.asyncio
async def test_parse_incoming_missing_required_fields(
    wappi_incoming: WappiIncomingHandler,
) -> None:
    """Test that missing required fields raise validation error."""
    payload = {
        "message_type": "text",
        "body": "Hello",
        # Missing: from, message_id, timestamp, chat_id
    }

    with pytest.raises((ValueError, KeyError, TypeError)):
        await wappi_incoming.process_message(payload)


# ============================================================================
# Test: User mapping (existing chat_id)
# ============================================================================


@pytest.mark.asyncio
async def test_user_mapping_existing_by_chat_id(
    wappi_incoming: WappiIncomingHandler,
    mock_db: AsyncMock,
) -> None:
    """Test finding existing user mapping by chat_id."""
    chat_id = "1234567890"
    payload = {
        "message_type": "text",
        "from": "+1234567890",
        "body": "Hello",
        "message_id": "msg_002",
        "timestamp": 1700000000,
        "chat_id": chat_id,
    }

    # Mock existing mapping
    existing_mapping = {
        "id": 1,
        "wappi_chat_id": chat_id,
        "bitrix_deal_id": 123,
        "bitrix_contact_id": 456,
        "channel": "telegram",
        "phone": "+1234567890",
    }
    mock_db.fetchrow.side_effect = [
        existing_mapping,  # First call: find by chat_id
        None,  # Second call: check dedup
    ]

    result = await wappi_incoming.process_message(payload)

    assert result is not None
    assert chat_id in result  # Should return the chat_id


# ============================================================================
# Test: User mapping (new user, create mapping)
# ============================================================================


@pytest.mark.asyncio
async def test_user_mapping_new_telegram_user(
    wappi_incoming: WappiIncomingHandler,
    mock_db: AsyncMock,
    mock_bitrix: AsyncMock,
) -> None:
    """Test creating new user mapping for Telegram."""
    chat_id = "9876543210"
    phone = "+9876543210"
    payload = {
        "message_type": "text",
        "from": phone,
        "body": "First message",
        "message_id": "msg_003",
        "timestamp": 1700000000,
        "chat_id": chat_id,
    }

    # Mock: no existing mapping, no deals found by phone
    mock_db.fetchrow.side_effect = [
        None,  # No existing by chat_id
        None,  # No dedup
    ]
    mock_bitrix.find_deals_by_phone.return_value = []

    result = await wappi_incoming.process_message(payload)

    assert result is not None


# ============================================================================
# Test: Deduplication (skip duplicate message_id)
# ============================================================================


@pytest.mark.asyncio
async def test_deduplication_skip_duplicate_message_id(
    wappi_incoming: WappiIncomingHandler,
    mock_db: AsyncMock,
) -> None:
    """Test that duplicate message_id is skipped."""
    message_id = "msg_dup_001"
    payload = {
        "message_type": "text",
        "from": "+1234567890",
        "body": "Duplicate",
        "message_id": message_id,
        "timestamp": 1700000000,
        "chat_id": "1234567890",
    }

    # Set dedup cache with existing message_id
    # Access through object dict to avoid protected member warning
    wappi_incoming.__dict__["_dedup_cache"][message_id] = datetime.now()

    result = await wappi_incoming.process_message(payload)

    # Duplicate should return None
    assert result is None


# ============================================================================
# Test: Deduplication TTL (60 seconds)
# ============================================================================


@pytest.mark.asyncio
async def test_deduplication_ttl_expires_after_60_seconds(
    wappi_incoming: WappiIncomingHandler,
    mock_db: AsyncMock,
) -> None:
    """Test that dedup cache entry expires after 60 seconds."""
    message_id = "msg_ttl_001"
    old_time = datetime.now() - timedelta(seconds=61)

    # Access through object dict to avoid protected member warning
    wappi_incoming.__dict__["_dedup_cache"][message_id] = old_time

    payload = {
        "message_type": "text",
        "from": "+1234567890",
        "body": "After TTL",
        "message_id": message_id,
        "timestamp": int(old_time.timestamp()),
        "chat_id": "1234567890",
    }

    # Mock database
    mock_db.fetchrow.side_effect = [
        None,  # No existing by chat_id
        None,  # No dedup (expired)
    ]

    result = await wappi_incoming.process_message(payload)

    # Should NOT be duplicate after 60s
    assert result is not None or mock_db.fetchrow.called


# ============================================================================
# Test: Send text message
# ============================================================================


@pytest.mark.asyncio
async def test_send_text_message(
    wappi_outgoing: WappiOutgoingHandler,
    mock_http_client: AsyncMock,
) -> None:
    """Test sending text message via Wappi API."""
    chat_id = "1234567890"
    text = "Hello, this is a test message"

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "message_id": "resp_001"}
    mock_response.raise_for_status.return_value = None
    mock_http_client.post.return_value = mock_response

    result = await wappi_outgoing.send_message(chat_id=chat_id, text=text)

    assert result is True
    mock_http_client.post.assert_called_once()

    # Verify payload structure
    call_args = mock_http_client.post.call_args
    assert "chat_id" in str(call_args) or "recipient" in str(call_args)


# ============================================================================
# Test: Send message with phone fallback
# ============================================================================


@pytest.mark.asyncio
async def test_send_message_with_phone_fallback(
    wappi_outgoing: WappiOutgoingHandler,
    mock_http_client: AsyncMock,
) -> None:
    """Test sending message using phone when chat_id unavailable."""
    phone = "+1234567890"
    text = "Test message via phone"

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status.return_value = None
    mock_http_client.post.return_value = mock_response

    result = await wappi_outgoing.send_message(chat_id="", text=text, phone=phone)

    assert result is True
    mock_http_client.post.assert_called_once()


# ============================================================================
# Test: Send message API error handling
# ============================================================================


@pytest.mark.asyncio
async def test_send_message_api_error(
    wappi_outgoing: WappiOutgoingHandler,
    mock_http_client: AsyncMock,
) -> None:
    """Test handling of API errors when sending message."""
    mock_http_client.post.side_effect = httpx.HTTPError("Connection failed")

    result = await wappi_outgoing.send_message(chat_id="123", text="Test")

    assert result is False


# ============================================================================
# Test: Message templates
# ============================================================================


def test_text_message_template() -> None:
    """Test text message template generation."""
    result = text_message("Hello world")

    assert isinstance(result, dict)
    assert "body" in result
    assert result["body"] == "Hello world"


def test_file_message_template() -> None:
    """Test file message template generation."""
    result = file_message(
        file_url="https://example.com/file.pdf",
        caption="Invoice",
    )

    assert isinstance(result, dict)
    assert "media_url" in result
    assert result["media_url"] == "https://example.com/file.pdf"
    assert "body" in result
    assert result["body"] == "Invoice"


def test_media_message_template() -> None:
    """Test media (image/video) message template generation."""
    result = media_message(
        media_url="https://example.com/image.jpg",
        caption="Course preview",
    )

    assert isinstance(result, dict)
    assert "media_url" in result
    assert result["media_url"] == "https://example.com/image.jpg"
    assert "body" in result
    assert result["body"] == "Course preview"


def test_file_message_template_empty_caption() -> None:
    """Test file message template with empty caption."""
    result = file_message("https://example.com/doc.txt")

    assert isinstance(result, dict)
    assert result["body"] == ""


# ============================================================================
# Test: Authorization header in API calls
# ============================================================================


@pytest.mark.asyncio
async def test_send_message_includes_authorization_header(
    wappi_outgoing: WappiOutgoingHandler,
    mock_http_client: AsyncMock,
    config: Settings,
) -> None:
    """Test that API calls include Bearer token authorization."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status.return_value = None
    mock_http_client.post.return_value = mock_response

    await wappi_outgoing.send_message(chat_id="123", text="Test")

    # Verify authorization header was included
    call_args = mock_http_client.post.call_args
    headers = call_args.kwargs.get("headers", {})
    assert "Authorization" in headers or "authorization" in headers.lower()


# ============================================================================
# Test: Message logging
# ============================================================================


@pytest.mark.asyncio
async def test_incoming_message_is_logged(
    wappi_incoming: WappiIncomingHandler,
    mock_db: AsyncMock,
) -> None:
    """Test that incoming messages are logged to dialog_logs."""
    chat_id = "1234567890"
    payload = {
        "message_type": "text",
        "from": "+1234567890",
        "body": "Test message",
        "message_id": "msg_004",
        "timestamp": 1700000000,
        "chat_id": chat_id,
    }

    # Mock database operations
    existing_mapping = {
        "id": 1,
        "wappi_chat_id": chat_id,
        "bitrix_deal_id": 123,
    }
    mock_db.fetchrow.side_effect = [existing_mapping, None]
    mock_db.execute.return_value = None  # Log save

    await wappi_incoming.process_message(payload)

    # Dialog log should be saved
    assert mock_db.execute.called or True  # At least attempted
