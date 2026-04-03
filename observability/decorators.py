from __future__ import annotations

import functools
from typing import Any, Callable

from observability.config import is_langfuse_enabled


def observe_if_enabled(name: str) -> Callable:
    """Decorator: wraps async function with Langfuse @observe if enabled, no-op otherwise."""

    def decorator(func: Callable) -> Callable:
        if not is_langfuse_enabled():
            return func

        from langfuse.decorators import observe

        @observe(name=name)
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper

    return decorator
