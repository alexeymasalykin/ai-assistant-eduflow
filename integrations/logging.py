from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from config import settings

_PHONE_RE = re.compile(r"(\+?7|8)\d{10}")
_CHAT_ID_SUFFIX = "@c.us"
PII_FIELDS = {"chat_id", "wappi_chat_id", "phone", "user_id"}


def mask_pii(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Mask PII fields in log output for production."""
    for field in PII_FIELDS:
        if field in event_dict and isinstance(event_dict[field], str):
            value = event_dict[field]
            if len(value) > 5:
                event_dict[field] = value[:5] + "***"
    # Mask phone numbers in any string field
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = _PHONE_RE.sub("7***MASKED***", value)
    return event_dict


def setup_logging() -> None:
    """Configure structlog for the application.

    JSON output in production, colored console in development.
    PII masking enabled in production mode.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # PII masking in production
    if settings.log_format == "json":
        shared_processors.append(mask_pii)

    if settings.log_format == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)
