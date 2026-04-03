from __future__ import annotations

import asyncio
from unittest.mock import patch


class TestObserveIfEnabled:
    def test_noop_when_disabled(self) -> None:
        """Decorator should be a no-op when Langfuse is disabled."""
        with patch("observability.config.is_langfuse_enabled", return_value=False):
            from observability.decorators import observe_if_enabled

            @observe_if_enabled(name="test_func")
            async def my_func(x: int) -> int:
                return x * 2

            result = asyncio.get_event_loop().run_until_complete(my_func(5))
            assert result == 10

    def test_preserves_function_signature(self) -> None:
        """Decorated function should preserve its name."""
        with patch("observability.config.is_langfuse_enabled", return_value=False):
            from observability.decorators import observe_if_enabled

            @observe_if_enabled(name="test_func")
            async def my_func(x: int) -> int:
                return x * 2

            assert my_func.__name__ == "my_func"


class TestGetLangfuseHandler:
    def test_returns_none_when_disabled(self) -> None:
        """Handler should return None when Langfuse is disabled."""
        with patch("observability.config.is_langfuse_enabled", return_value=False):
            from observability.langchain_handler import get_langfuse_handler

            handler = get_langfuse_handler(trace_name="test")
            assert handler is None
