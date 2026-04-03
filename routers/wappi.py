"""Wappi webhook router for incoming Telegram/WhatsApp messages.

Handles:
1. Message validation (Pydantic)
2. HMAC token validation (timing-safe)
3. Per-IP rate limiting (slowapi, 100/min)
4. Per-chat rate limiting (10 req/min)
5. Per-chat async locking (prevent race conditions)
6. Deduplication
7. User mapping (find or create)
8. Orchestration (route to appropriate agent)
9. Response sending
"""

from __future__ import annotations

import asyncio
import hmac
import time
from collections import defaultdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from config import settings
from rate_limiter import limiter  # noqa: F401 — used via app.state

logger = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["wappi"])

# ============================================================================
# Per-chat async locks (prevent race conditions on same chat)
# ============================================================================

_chat_locks: dict[str, asyncio.Lock] = {}

_MAX_CACHE_SIZE = 5000


def _cleanup_if_needed(cache: dict, max_size: int = _MAX_CACHE_SIZE) -> None:  # type: ignore[type-arg]
    """Evict oldest half of entries when cache exceeds max_size."""
    if len(cache) > max_size:
        keys_to_remove = list(cache.keys())[: max_size // 2]
        for k in keys_to_remove:
            del cache[k]


def get_chat_lock(chat_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for the given chat_id."""
    _cleanup_if_needed(_chat_locks)
    if chat_id not in _chat_locks:
        _chat_locks[chat_id] = asyncio.Lock()
    return _chat_locks[chat_id]


# ============================================================================
# Per-chat rate limiting (10 messages/minute per chat)
# ============================================================================

_CHAT_RATE_LIMIT = 10
_CHAT_RATE_WINDOW = 60.0  # seconds

_chat_timestamps: dict[str, list[float]] = defaultdict(list)


def check_chat_rate_limit(chat_id: str) -> bool:
    """Check if chat_id has exceeded per-chat rate limit.

    Returns True if allowed, False if rate-limited.
    Cleans up expired timestamps on each call.
    """
    _cleanup_if_needed(_chat_timestamps)
    now = time.monotonic()
    timestamps = _chat_timestamps[chat_id]

    # Remove expired timestamps
    _chat_timestamps[chat_id] = [
        ts for ts in timestamps if now - ts < _CHAT_RATE_WINDOW
    ]

    if len(_chat_timestamps[chat_id]) >= _CHAT_RATE_LIMIT:
        return False

    _chat_timestamps[chat_id].append(now)
    return True


# ============================================================================
# Per-chat daily LLM budget (50 calls / 24h rolling window)
# ============================================================================

_DAILY_LLM_LIMIT = 50
_DAILY_LLM_WINDOW = 86400.0  # 24 hours in seconds
_daily_llm_calls: dict[str, list[float]] = defaultdict(list)


def check_daily_llm_limit(chat_id: str) -> bool:
    """Check if chat_id has exceeded daily LLM call budget.

    Uses a rolling 24h window. Returns True if allowed, False if exceeded.
    """
    _cleanup_if_needed(_daily_llm_calls, max_size=10000)
    now = time.monotonic()
    calls = _daily_llm_calls[chat_id]
    _daily_llm_calls[chat_id] = [t for t in calls if now - t < _DAILY_LLM_WINDOW]

    if len(_daily_llm_calls[chat_id]) >= _DAILY_LLM_LIMIT:
        return False

    _daily_llm_calls[chat_id].append(now)
    return True


# ============================================================================
# Webhook token authentication (HMAC timing-safe)
# ============================================================================


async def verify_wappi_webhook_token(
    request: Request,
    x_webhook_token: str = Header(default=""),
) -> None:
    """Validate webhook token using timing-safe comparison.

    If WAPPI_WEBHOOK_TOKEN is not configured (empty), skip validation
    to allow dev/test environments without tokens.

    Raises:
        HTTPException: 403 if token is configured but doesn't match.
    """
    expected = settings.wappi_webhook_token
    if not expected:
        # Token not configured — skip auth (dev mode)
        return

    if not x_webhook_token or not hmac.compare_digest(x_webhook_token, expected):
        logger.warning("wappi_webhook_auth_failed", path=request.url.path)
        raise HTTPException(status_code=403, detail="Forbidden")


class WappiWebhookPayload(BaseModel):
    """Wappi webhook message payload."""

    model_config = ConfigDict(populate_by_name=True)

    message_type: str
    from_number: str = Field(alias="from")
    body: str
    message_id: str
    timestamp: int
    chat_id: str


@router.post("/wappi", dependencies=[Depends(verify_wappi_webhook_token)])
async def wappi_webhook(
    request: Request,
    payload: WappiWebhookPayload,
) -> dict[str, Any]:
    """Process incoming Wappi webhook (Telegram/WhatsApp).

    Flow:
    1. Validate token (HMAC, via dependency)
    2. Per-IP rate limit (slowapi decorator, 100/min)
    3. Per-chat rate limit (10 req/min)
    4. Parse payload with Pydantic
    5. Acquire per-chat lock
    6. Process with WappiIncomingHandler (dedup, user mapping)
    7. If duplicate, return 200 silently
    8. Route to Orchestrator
    9. Send response via WappiOutgoingHandler if should_send=True
    10. Return 200 OK
    """
    # Per-chat rate limit
    if not check_chat_rate_limit(payload.chat_id):
        logger.warning(
            "per_chat_rate_limit_exceeded",
            chat_id=payload.chat_id,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many messages from this chat",
            headers={"Retry-After": "60"},
        )

    # Per-chat daily LLM budget
    if not check_daily_llm_limit(payload.chat_id):
        logger.warning(
            "daily_llm_limit_exceeded",
            chat_id=payload.chat_id,
        )
        raise HTTPException(
            status_code=429,
            detail="Daily message limit exceeded",
            headers={"Retry-After": "3600"},
        )

    # Get dependencies from app state
    db = request.app.state.db
    wappi_incoming = request.app.state.wappi_incoming
    wappi_outgoing = request.app.state.wappi_outgoing
    pipeline = request.app.state.pipeline

    if not all([db, wappi_incoming, wappi_outgoing, pipeline]):
        logger.warning("wappi_webhook_missing_dependencies")
        raise HTTPException(status_code=503, detail="Service unavailable")

    # Convert alias from Pydantic model
    payload_dict = {
        "message_type": payload.message_type,
        "from": payload.from_number,
        "body": payload.body,
        "message_id": payload.message_id,
        "timestamp": payload.timestamp,
        "chat_id": payload.chat_id,
    }

    try:
        # Acquire per-chat lock to prevent race conditions
        async with get_chat_lock(payload.chat_id):
            # Process incoming message (dedup, user mapping)
            result = await wappi_incoming.process_message(payload_dict)

            # If duplicate, return 200 silently (webhook acknowledged)
            if result is None:
                logger.info(
                    "wappi_webhook_duplicate_skipped",
                    message_id=payload.message_id,
                )
                return {"status": "ok"}

            chat_id, phone, deal_id = result

            # Route to pipeline (original Orchestrator or LangChain)
            logger.info("wappi_webhook_routing_to_pipeline", chat_id=chat_id)
            agent_response = await pipeline.process(payload.body, deal_id=deal_id)

            # Send response if should_send=True
            if agent_response.should_send and agent_response.text:
                logger.info("wappi_webhook_sending_response", chat_id=chat_id)
                await wappi_outgoing.send_message(
                    chat_id=chat_id,
                    text=agent_response.text,
                )
            else:
                logger.info("wappi_webhook_silent_response", chat_id=chat_id)

        return {"status": "ok"}

    except HTTPException:
        raise  # Re-raise HTTP exceptions (rate limit, auth)

    except (KeyError, ValueError) as e:
        logger.error("wappi_webhook_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from None

    except Exception as e:
        logger.error("wappi_webhook_unexpected_error", error=str(e))
        # Don't expose internal errors to webhook
        return {"status": "ok"}  # Webhook ACK to prevent retries
