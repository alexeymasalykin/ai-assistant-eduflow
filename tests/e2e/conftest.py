"""E2E test fixtures.

Real Orchestrator + agents with mocked external dependencies.
No lifespan — app.state set manually. Rate limit state cleared between tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

import app as app_module
from agents.orchestrator import Orchestrator
from integrations.bitrix_client import BitrixClient
from integrations.database import Database
from integrations.vector_db import VectorDB
from integrations.wappi import WappiIncomingHandler, WappiOutgoingHandler


@dataclass
class E2EContext:
    """Holds test client and all mocks for assertions."""

    client: httpx.AsyncClient
    llm: AsyncMock
    bitrix: AsyncMock
    vector_db: AsyncMock
    wappi_outgoing: AsyncMock
    wappi_incoming: WappiIncomingHandler
    db_pool: AsyncMock


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    """Clear per-chat rate limit state between tests."""
    from routers.wappi import _chat_locks, _chat_timestamps, _daily_llm_calls

    _chat_timestamps.clear()
    _daily_llm_calls.clear()
    _chat_locks.clear()


@pytest.fixture
async def e2e(env_setup: None) -> E2EContext:
    """E2E test context with real Orchestrator and mocked externals.

    - Real: Orchestrator, ClassifierAgent, TypicalAgent, CourseAgent,
      PlatformAgent, WappiIncomingHandler, sanitization
    - Mocked: LLMClient (AsyncMock), BitrixClient (AsyncMock),
      VectorDB (AsyncMock), WappiOutgoingHandler (AsyncMock), DB pool (AsyncMock)
    """
    # --- Mock external dependencies ---
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="escalate")

    mock_bitrix = AsyncMock(spec=BitrixClient)
    mock_bitrix.find_deals_by_phone = AsyncMock(return_value=[])
    mock_bitrix.get_deal = AsyncMock(return_value=None)
    mock_bitrix.parse_deal_stage = MagicMock(return_value=None)

    mock_vector_db = AsyncMock(spec=VectorDB)
    mock_vector_db.search = AsyncMock(return_value=[])

    mock_db = AsyncMock(spec=Database)
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)  # No existing user mapping
    mock_pool.execute = AsyncMock()
    mock_db.pool = mock_pool

    # --- Real orchestrator with real agents ---
    orchestrator = Orchestrator(
        llm=mock_llm,
        bitrix=mock_bitrix,
        vector_db=mock_vector_db,
    )

    # --- Real incoming handler with mocked DB ---
    wappi_incoming = WappiIncomingHandler(
        db=mock_db,
        bitrix=mock_bitrix,
        max_profile_id="max-profile-test",
    )

    # --- Mock outgoing handler for send assertions ---
    mock_wappi_outgoing = AsyncMock(spec=WappiOutgoingHandler)
    mock_wappi_outgoing.send_message = AsyncMock(return_value=True)

    # --- Wire into app.state (no lifespan) ---
    app = app_module.app
    app.state.db = mock_db
    app.state.llm_client = mock_llm
    app.state.vector_db = mock_vector_db
    app.state.bitrix_client = mock_bitrix
    app.state.wappi_incoming = wappi_incoming
    app.state.wappi_outgoing = mock_wappi_outgoing
    app.state.orchestrator = orchestrator
    app.state.pipeline = orchestrator  # default: original pipeline
    app.state.http_client = AsyncMock()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield E2EContext(
            client=client,
            llm=mock_llm,
            bitrix=mock_bitrix,
            vector_db=mock_vector_db,
            wappi_outgoing=mock_wappi_outgoing,
            wappi_incoming=wappi_incoming,
            db_pool=mock_pool,
        )


def make_wappi_payload(
    body: str,
    message_id: str = "msg_e2e_001",
    chat_id: str = "e2e_chat_001",
    from_number: str = "+79990001122",
) -> dict[str, Any]:
    """Build a valid Wappi webhook payload."""
    return {
        "message_type": "text",
        "from": from_number,
        "body": body,
        "message_id": message_id,
        "timestamp": 1700000000,
        "chat_id": chat_id,
    }


WAPPI_AUTH_HEADER = {"X-Webhook-Token": "test-webhook-token"}
