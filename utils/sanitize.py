from __future__ import annotations

import re

MAX_MESSAGE_LENGTH = 4096

_SCRIPT_TAG_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_NULL_BYTE_RE = re.compile(r"\x00")


_PROMPT_LEAK_PATTERNS = [
    # English
    re.compile(
        r"(?i)^(my instructions|my prompt|i was told|i am instructed|system prompt)"
    ),
    re.compile(
        r"(?i)(here are my instructions|my rules are|i must follow)"
    ),
    # Russian
    re.compile(
        r"(?i)(мои инструкции|мой промпт|системный промпт|мне велено|мне приказано)"
    ),
    re.compile(
        r"(?i)^(мои правила|я должен следовать|вот мои инструкции)"
    ),
]


def sanitize_llm_output(text: str) -> str:
    """Sanitize LLM response before sending to user.

    Removes potential system prompt leaks and instruction artifacts.
    Truncates to MAX_MESSAGE_LENGTH.
    """
    if not text:
        return ""
    lines = text.strip().splitlines()
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith(("system:", "assistant:", "security:")):
            continue
        if any(p.search(line) for p in _PROMPT_LEAK_PATTERNS):
            continue
        filtered.append(line)
    result = "\n".join(filtered).strip()
    if len(result) > MAX_MESSAGE_LENGTH:
        result = result[:MAX_MESSAGE_LENGTH]
    return result


def sanitize_input(text: str) -> str:
    """Sanitize user input: strip XSS, null bytes, truncate."""
    text = text.strip()
    if not text:
        return ""

    text = _NULL_BYTE_RE.sub("", text)
    text = _SCRIPT_TAG_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)

    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]

    return text
