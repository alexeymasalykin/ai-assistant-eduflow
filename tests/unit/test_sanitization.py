from __future__ import annotations

from utils.sanitize import sanitize_input


class TestSanitizeInput:
    def test_normal_text_unchanged(self) -> None:
        assert sanitize_input("Привет, когда мой курс?") == "Привет, когда мой курс?"

    def test_strips_whitespace(self) -> None:
        assert sanitize_input("  hello  ") == "hello"

    def test_removes_script_tags(self) -> None:
        result = sanitize_input("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result

    def test_removes_sql_injection_patterns(self) -> None:
        result = sanitize_input("'; DROP TABLE users; --")
        assert "DROP TABLE" not in result

    def test_truncates_long_messages(self) -> None:
        long_message = "a" * 5000
        result = sanitize_input(long_message)
        assert len(result) <= 4096

    def test_empty_string(self) -> None:
        assert sanitize_input("") == ""

    def test_removes_null_bytes(self) -> None:
        assert sanitize_input("hello\x00world") == "helloworld"
