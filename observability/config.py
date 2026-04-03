from __future__ import annotations

import structlog

from config import settings

logger = structlog.get_logger()


def is_langfuse_enabled() -> bool:
    """Check if Langfuse observability is enabled via config."""
    return settings.langfuse_enabled


def get_langfuse_client():
    """Get Langfuse client instance. Returns None if disabled."""
    if not is_langfuse_enabled():
        return None

    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
