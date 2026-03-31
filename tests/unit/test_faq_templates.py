from __future__ import annotations

from prompts.faq_templates import FAQ_TEMPLATES, get_faq_response


class TestFaqTemplates:
    def test_all_templates_are_non_empty(self) -> None:
        for key, value in FAQ_TEMPLATES.items():
            assert len(value) > 0, f"Template '{key}' is empty"

    def test_get_existing_template(self) -> None:
        result = get_faq_response("working_hours")
        assert result is not None
        assert "EduFlow" in result

    def test_get_missing_template_returns_none(self) -> None:
        result = get_faq_response("nonexistent")
        assert result is None
