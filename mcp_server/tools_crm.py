"""MCP Tools: Bitrix24 CRM access.

Architecture decision (ADR-1): Reuses BitrixClient directly.
"""

from __future__ import annotations

from typing import Any


def format_deal(deal: dict[str, Any] | None) -> str:
    """Format a single deal for MCP tool response."""
    if deal is None:
        return "Deal not found."

    return f"""Deal #{deal.get("ID", "?")}
- Title: {deal.get("TITLE", "Unknown")}
- Stage: {deal.get("STAGE_ID", "Unknown")}
- Contact ID: {deal.get("CONTACT_ID", "Unknown")}
- Payment: {deal.get("UF_CRM_SUM", "Unknown")}
- Created: {deal.get("DATE_CREATE", "Unknown")}
- Details: {deal.get("COMMENTS", "")}"""


def format_deals_list(deals: list[dict[str, Any]]) -> str:
    """Format a list of deals for MCP tool response."""
    if not deals:
        return "No deals found."

    items = []
    for deal in deals:
        items.append(
            f"- Deal #{deal.get('ID', '?')}: {deal.get('TITLE', 'Unknown')} "
            f"(Stage: {deal.get('STAGE_ID', 'Unknown')})"
        )
    return f"Found {len(deals)} deal(s):\n" + "\n".join(items)


def register_crm_tools(mcp, bitrix_client) -> None:
    """Register CRM tools with MCP server."""

    @mcp.tool()
    async def get_deal(deal_id: int) -> str:
        """Get student deal information from Bitrix24 CRM.

        Args:
            deal_id: Bitrix24 deal ID

        Returns:
            Deal details: stage, course, payment, dates
        """
        deal = await bitrix_client.get_deal(deal_id)
        return format_deal(deal)

    @mcp.tool()
    async def find_deals_by_phone(phone: str) -> str:
        """Find student deals in Bitrix24 CRM by phone number.

        Args:
            phone: Phone number (any format, e.g. +7-999-123-45-67)

        Returns:
            List of matching deals with stages and courses
        """
        deals = await bitrix_client.find_deals_by_phone(phone)
        return format_deals_list(deals)
