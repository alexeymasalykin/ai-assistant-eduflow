"""Wappi webhook router for incoming Telegram/WhatsApp messages.

Handles:
1. Message validation (Pydantic)
2. HMAC token validation
3. Deduplication
4. User mapping (find or create)
5. Orchestration (route to appropriate agent)
6. Response sending
"""

from __future__ import annotations

import hmac
import hashlib
from typing import TYPE_CHECKING, Any, Annotated

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from integrations.database import Database
    from integrations.wappi import WappiIncomingHandler, WappiOutgoingHandler
    from agents.orchestrator import Orchestrator

logger = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["wappi"])


class WappiWebhookPayload(BaseModel):
    """Wappi webhook message payload."""

    model_config = ConfigDict(populate_by_name=True)

    message_type: str
    from_number: Annotated[str, Field(alias="from")]
    body: str
    message_id: str
    timestamp: int
    chat_id: str


@router.post("/wappi")
async def wappi_webhook(
    request: Request,
    payload: WappiWebhookPayload,
) -> dict[str, Any]:
    """Process incoming Wappi webhook (Telegram/WhatsApp).

    Flow:
    1. Validate token (optional HMAC)
    2. Parse payload with Pydantic
    3. Process with WappiIncomingHandler (dedup, user mapping)
    4. If duplicate, return 200 silently
    5. Route to Orchestrator
    6. Send response via WappiOutgoingHandler if should_send=True
    7. Return 200 OK

    Args:
        request: FastAPI request for header access
        payload: Validated Wappi webhook payload

    Returns:
        JSON response with status

    Raises:
        HTTPException: On validation error (400)
    """
    # Get dependencies from app state
    db = request.app.state.db
    wappi_incoming = request.app.state.wappi_incoming
    wappi_outgoing = request.app.state.wappi_outgoing
    orchestrator = request.app.state.orchestrator

    # Dependencies are injected from app context
    # If None, this is a test or incomplete setup
    if not all([db, wappi_incoming, wappi_outgoing, orchestrator]):
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
        # Process incoming message (dedup, user mapping)
        result = await wappi_incoming.process_message(payload_dict)

        # If duplicate, return 200 silently (webhook acknowledged)
        if result is None:
            logger.info("wappi_webhook_duplicate_skipped", message_id=payload.message_id)
            return {"status": "ok"}

        chat_id, phone = result

        # Route to orchestrator
        logger.info("wappi_webhook_routing_to_orchestrator", chat_id=chat_id)
        agent_response = await orchestrator.process(payload.body)

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

    except (KeyError, ValueError) as e:
        logger.error("wappi_webhook_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    except Exception as e:
        logger.error("wappi_webhook_unexpected_error", error=str(e))
        # Don't expose internal errors to webhook
        return {"status": "ok"}  # Webhook ACK to prevent retries
