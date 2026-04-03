from __future__ import annotations

from typing import Any

from observability.config import is_langfuse_enabled


def get_langfuse_handler(
    trace_name: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Get Langfuse CallbackHandler for LangChain tracing. Returns None if disabled."""
    if not is_langfuse_enabled():
        return None

    from langfuse.callback import CallbackHandler

    handler_metadata = {"pipeline": "langchain"}
    if metadata:
        handler_metadata.update(metadata)

    return CallbackHandler(
        trace_name=trace_name,
        user_id=user_id,
        metadata=handler_metadata,
    )
