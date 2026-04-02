"""E2E tests: error and edge-case scenarios.

Tests negative paths: invalid input, deduplication, rate limiting, LLM failures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.e2e.conftest import WAPPI_AUTH_HEADER, E2EContext, make_wappi_payload

pytestmark = pytest.mark.e2e


async def test_invalid_payload_returns_error(e2e: E2EContext) -> None:
    """Missing required fields -> 422 validation error."""
    invalid_payload = {"message_type": "text"}  # Missing from, body, message_id, etc.

    response = await e2e.client.post(
        "/webhook/wappi", json=invalid_payload, headers=WAPPI_AUTH_HEADER
    )

    assert response.status_code == 422

    # No processing happened
    e2e.wappi_outgoing.send_message.assert_not_called()
    e2e.llm.generate.assert_not_called()


async def test_duplicate_message_processed_once(e2e: E2EContext) -> None:
    """Same message_id sent twice -> second request skipped (dedup)."""
    payload = make_wappi_payload(body="Привет!", message_id="msg_dup_001")

    # First request — processed normally
    resp1 = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )
    assert resp1.status_code == 200
    assert e2e.wappi_outgoing.send_message.call_count == 1

    # Second request with same message_id — skipped
    resp2 = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )
    assert resp2.status_code == 200

    # send_message still called only once (from first request)
    assert e2e.wappi_outgoing.send_message.call_count == 1


async def test_per_chat_rate_limit(e2e: E2EContext) -> None:
    """11 messages from same chat_id -> 11th returns 429."""
    for i in range(10):
        payload = make_wappi_payload(
            body="Привет!",
            message_id=f"msg_rate_{i:03d}",
            chat_id="rate_limit_chat",
        )
        resp = await e2e.client.post(
            "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
        )
        assert resp.status_code == 200, f"Request {i} failed with {resp.status_code}"

    # 11th message — rate limited
    payload_11 = make_wappi_payload(
        body="Привет!",
        message_id="msg_rate_010",
        chat_id="rate_limit_chat",
    )
    resp_11 = await e2e.client.post(
        "/webhook/wappi", json=payload_11, headers=WAPPI_AUTH_HEADER
    )
    assert resp_11.status_code == 429


async def test_llm_timeout_graceful_fallback(e2e: E2EContext) -> None:
    """LLM times out during classification -> graceful handling, no crash.

    When LLM generate raises TimeoutError, the classifier receives the exception.
    The webhook's exception handler catches it and returns 200 (ACK to prevent retries).
    No stack trace is leaked in the response.
    """
    e2e.llm.generate = AsyncMock(side_effect=TimeoutError("LLM timeout"))

    payload = make_wappi_payload(body="Расскажи про курс дизайна", message_id="msg_timeout_001")

    response = await e2e.client.post(
        "/webhook/wappi", json=payload, headers=WAPPI_AUTH_HEADER
    )

    # Webhook returns 200 — no crash, exception handled
    assert response.status_code == 200

    # Response body has no stack trace
    body = response.json()
    assert "traceback" not in str(body).lower()
    assert "error" not in str(body).lower() or body.get("status") == "ok"
