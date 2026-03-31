from __future__ import annotations

import re

MAX_MESSAGE_LENGTH = 4096

_SCRIPT_TAG_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SQL_INJECTION_RE = re.compile(
    r"(\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC)\b\s+(TABLE|DATABASE|FROM|INTO))",
    re.IGNORECASE,
)
_NULL_BYTE_RE = re.compile(r"\x00")


def sanitize_llm_output(text: str) -> str:
    """Sanitize LLM response before sending to user.

    Removes potential system prompt leaks and instruction artifacts.
    """
    if not text:
        return ""
    lines = text.strip().splitlines()
    filtered = [
        line for line in lines
        if not line.strip().lower().startswith(("system:", "assistant:", "security:"))
    ]
    return "\n".join(filtered).strip()


def sanitize_input(text: str) -> str:
    """Sanitize user input: strip XSS, SQL injection patterns, null bytes, truncate."""
    text = text.strip()
    if not text:
        return ""

    text = _NULL_BYTE_RE.sub("", text)
    text = _SCRIPT_TAG_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _SQL_INJECTION_RE.sub("[FILTERED]", text)

    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]

    return text
