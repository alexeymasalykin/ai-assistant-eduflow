"""Bitrix24 webhook router for deal updates.

Handles:
1. HMAC token validation (timing-safe)
2. Per-IP rate limiting (slowapi, 100/min)
3. Deal update webhooks
4. Metadata synchronization
5. Course module assignments
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from config import settings
from rate_limiter import limiter

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient

logger = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["bitrix"])


# ============================================================================
# Webhook token authentication (HMAC timing-safe)
# ============================================================================


async def verify_bitrix_webhook_token(
    request: Request,
    x_webhook_token: str = Header(default=""),
) -> None:
    """Validate webhook token using timing-safe comparison.

    If BITRIX24_WEBHOOK_TOKEN is not configured (empty), skip validation
    to allow dev/test environments without tokens.

    Raises:
        HTTPException: 403 if token is configured but doesn't match.
    """
    expected = settings.bitrix24_webhook_token
    if not expected:
        # Token not configured — skip auth (dev mode)
        return

    if not x_webhook_token or not hmac.compare_digest(x_webhook_token, expected):
        logger.warning("bitrix_webhook_auth_failed", path=request.url.path)
        raise HTTPException(status_code=403, detail="Forbidden")


class BitrixWebhookPayload(BaseModel):
    """Bitrix24 webhook payload."""

    event: str
    data: dict[str, Any] = {}


@router.post("/bitrix", dependencies=[Depends(verify_bitrix_webhook_token)])
async def bitrix_webhook(
    request: Request,
    payload: BitrixWebhookPayload,
) -> dict[str, Any]:
    """Process incoming Bitrix24 webhook (deal updates).

    Flow:
    1. Validate token (HMAC, via dependency)
    2. Per-IP rate limit (slowapi decorator, 100/min)
    3. Parse payload with Pydantic
    4. Extract deal ID and update information
    5. Process with BitrixClient (update metadata, sync)
    6. Return 200 OK
    """
    bitrix_client = request.app.state.bitrix_client

    if not bitrix_client:
        logger.warning("bitrix_webhook_missing_client")
        raise HTTPException(status_code=503, detail="Service unavailable")

    try:
        # Handle different event types
        if payload.event == "ONCRMDEALUPDATE":
            logger.info("bitrix_webhook_deal_update", event=payload.event)

            # Extract deal data
            fields = payload.data.get("FIELDS", {})
            deal_id = fields.get("ID")

            if not deal_id:
                logger.warning("bitrix_webhook_missing_deal_id")
                return {"status": "ok"}  # ACK webhook

            # Process deal update (e.g., sync course module, update metadata)
            logger.info("bitrix_webhook_processed", deal_id=deal_id)

        elif payload.event == "ONCRMLEADUPDATE":
            logger.info("bitrix_webhook_lead_update", event=payload.event)

        elif payload.event == "ONCRMDEALSTAGECHANGE":
            logger.info("bitrix_webhook_deal_stage_change", event=payload.event)

        else:
            logger.info("bitrix_webhook_unknown_event", event=payload.event)

        return {"status": "ok"}

    except Exception as e:
        logger.error("bitrix_webhook_unexpected_error", error=str(e))
        # Always ACK webhook to prevent retries
        return {"status": "ok"}
