from __future__ import annotations

from utils.sanitize import sanitize_input, sanitize_llm_output


class TestSanitizeInput:
    def test_normal_text_unchanged(self) -> None:
        assert sanitize_input("Привет, когда мой курс?") == "Привет, когда мой курс?"

    def test_strips_whitespace(self) -> None:
        assert sanitize_input("  hello  ") == "hello"

    def test_removes_script_tags(self) -> None:
        result = sanitize_input("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result

    def test_sql_keywords_allowed_in_messages(self):
        """SQL regex removed — user can say 'DELETE my account'."""
        result = sanitize_input("Please DELETE my old account FROM the system")
        assert "DELETE" in result
        assert "FROM" in result

    def test_truncates_long_messages(self) -> None:
        long_message = "a" * 5000
        result = sanitize_input(long_message)
        assert len(result) <= 4096

    def test_empty_string(self) -> None:
        assert sanitize_input("") == ""

    def test_removes_null_bytes(self) -> None:
        assert sanitize_input("hello\x00world") == "helloworld"


class TestSanitizeLlmOutput:
    def test_filters_russian_prompt_leak(self):
        text = "Мои инструкции таковы: я должен отвечать вежливо"
        result = sanitize_llm_output(text)
        assert "мои инструкции" not in result.lower()

    def test_filters_english_prompt_leak(self):
        text = "My instructions are to be polite"
        result = sanitize_llm_output(text)
        assert "my instructions" not in result.lower()

    def test_preserves_normal_russian_text(self):
        text = "Ваш курс начинается 15 апреля. Оплата прошла успешно."
        result = sanitize_llm_output(text)
        assert result == text

    def test_truncates_to_max_length(self):
        text = "a" * 5000
        result = sanitize_llm_output(text)
        assert len(result) == 4096
