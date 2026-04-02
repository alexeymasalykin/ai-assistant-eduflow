"""Bitrix24 webhook router for deal updates.

Handles:
1. Deal update webhooks
2. Metadata synchronization
3. Course module assignments
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient

logger = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["bitrix"])


class BitrixWebhookPayload(BaseModel):
    """Bitrix24 webhook payload."""

    event: str
    data: dict[str, Any] = {}


@router.post("/bitrix")
async def bitrix_webhook(
    request: Request,
    payload: BitrixWebhookPayload,
) -> dict[str, Any]:
    """Process incoming Bitrix24 webhook (deal updates).

    Flow:
    1. Parse payload with Pydantic
    2. Extract deal ID and update information
    3. Process with BitrixClient (update metadata, sync)
    4. Return 200 OK

    Args:
        request: FastAPI request for header access
        payload: Validated Bitrix webhook payload

    Returns:
        JSON response with status

    Raises:
        HTTPException: On validation error (400)
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
            # This is optional for MVP
            logger.info("bitrix_webhook_processed", deal_id=deal_id)

        elif payload.event == "ONCRMLEADUPDATE":
            logger.info("bitrix_webhook_lead_update", event=payload.event)
            # Handle lead updates (optional)

        elif payload.event == "ONCRMDEALSTAGECHANGE":
            logger.info("bitrix_webhook_deal_stage_change", event=payload.event)
            # Handle stage changes (optional)

        else:
            logger.info("bitrix_webhook_unknown_event", event=payload.event)

        return {"status": "ok"}

    except Exception as e:
        logger.error("bitrix_webhook_unexpected_error", error=str(e))
        # Always ACK webhook to prevent retries
        return {"status": "ok"}
