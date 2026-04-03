from __future__ import annotations

import pytest


class TestMcpToolsKb:
    def test_search_knowledge_base_returns_formatted_results(self) -> None:
        from mcp_server.tools_kb import format_results

        results = [
            "Нажмите кнопку 'Забыли пароль' на странице входа.",
            "Проверьте папку 'Спам' если письмо не пришло.",
        ]
        formatted = format_results(results)

        assert "1." in formatted
        assert "2." in formatted
        assert "пароль" in formatted.lower()

    def test_search_empty_results(self) -> None:
        from mcp_server.tools_kb import format_results

        formatted = format_results([])
        assert "no results" in formatted.lower()


class TestMcpToolsCrm:
    def test_format_deal(self) -> None:
        from mcp_server.tools_crm import format_deal

        deal = {
            "ID": "123",
            "TITLE": "Python для начинающих",
            "STAGE_ID": "LEARNING",
            "CONTACT_ID": "456",
            "UF_CRM_SUM": "5000",
            "DATE_CREATE": "2026-03-01",
        }
        formatted = format_deal(deal)

        assert "123" in formatted
        assert "Python" in formatted
        assert "LEARNING" in formatted

    def test_format_deal_none(self) -> None:
        from mcp_server.tools_crm import format_deal

        formatted = format_deal(None)
        assert "not found" in formatted.lower()

    def test_format_deals_list(self) -> None:
        from mcp_server.tools_crm import format_deals_list

        deals = [
            {"ID": "1", "TITLE": "Course A", "STAGE_ID": "LEARNING"},
            {"ID": "2", "TITLE": "Course B", "STAGE_ID": "PAYMENT"},
        ]
        formatted = format_deals_list(deals)

        assert "Course A" in formatted
        assert "Course B" in formatted
