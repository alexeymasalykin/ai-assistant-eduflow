from __future__ import annotations

from enum import Enum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class DealStage(str, Enum):
    NEW_LEAD = "NEW_LEAD"
    CONSULTATION = "CONSULTATION"
    PAYMENT = "PAYMENT"
    ONBOARDING = "ONBOARDING"
    LEARNING = "LEARNING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    REFUND = "REFUND"

    @property
    def is_terminal(self) -> bool:
        return self in (DealStage.COMPLETED, DealStage.REJECTED, DealStage.REFUND)


class BitrixClient:
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url.rstrip("/")
        self._http_client = httpx.AsyncClient(timeout=15.0)

    @staticmethod
    async def _parse_json(response: Any) -> Any:
        """Call response.json(), awaiting if necessary (supports both real httpx and AsyncMock)."""
        result = response.json()
        if hasattr(result, "__await__"):
            result = await result
        return result

    async def get_deal(self, deal_id: int) -> dict[str, Any] | None:
        logger.info("bitrix_get_deal", deal_id=deal_id)
        response = await self._http_client.get(
            f"{self._webhook_url}/crm.deal.get",
            params={"ID": deal_id},
        )
        await response.raise_for_status()
        data = await self._parse_json(response)
        result = data.get("result")
        return result if result else None

    async def get_contact(self, contact_id: int) -> dict[str, Any] | None:
        response = await self._http_client.get(
            f"{self._webhook_url}/crm.contact.get",
            params={"ID": contact_id},
        )
        await response.raise_for_status()
        data = await self._parse_json(response)
        result = data.get("result")
        return result if result else None

    async def find_deals_by_phone(self, phone: str) -> list[dict[str, Any]]:
        response = await self._http_client.get(
            f"{self._webhook_url}/crm.contact.list",
            params={"filter[PHONE]": phone, "select[]": ["ID"]},
        )
        await response.raise_for_status()
        data = await self._parse_json(response)
        contacts = data.get("result", [])
        if not contacts:
            return []
        contact_id = contacts[0]["ID"]
        response = await self._http_client.get(
            f"{self._webhook_url}/crm.deal.list",
            params={"filter[CONTACT_ID]": contact_id},
        )
        await response.raise_for_status()
        data = await self._parse_json(response)
        return data.get("result", [])

    def parse_deal_stage(self, stage_id: str) -> DealStage | None:
        try:
            return DealStage(stage_id)
        except ValueError:
            logger.warning("unknown_deal_stage", stage_id=stage_id)
            return None
