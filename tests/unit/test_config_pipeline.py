from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from config import PipelineMode, Settings


class TestPipelineMode:
    def test_default_is_original(self) -> None:
        """Default pipeline mode should be 'original'."""
        s = Settings(
            _env_file=None,
            openai_api_key="test",
        )
        assert s.pipeline_mode == PipelineMode.ORIGINAL

    def test_langchain_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pipeline mode can be set to 'langchain'."""
        monkeypatch.setenv("PIPELINE_MODE", "langchain")
        s = Settings(
            _env_file=None,
            openai_api_key="test",
        )
        assert s.pipeline_mode == PipelineMode.LANGCHAIN

    def test_langfuse_disabled_by_default(self) -> None:
        """Langfuse should be disabled by default."""
        s = Settings(
            _env_file=None,
            openai_api_key="test",
        )
        assert s.langfuse_enabled is False
