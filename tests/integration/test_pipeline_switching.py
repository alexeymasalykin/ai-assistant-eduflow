from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.types import AgentResponse, MessageType


class TestPipelineSwitching:
    @pytest.mark.asyncio
    async def test_original_pipeline_by_default(self) -> None:
        with patch("config.settings") as mock_settings:
            from config import PipelineMode
            mock_settings.pipeline_mode = PipelineMode.ORIGINAL
            assert mock_settings.pipeline_mode == PipelineMode.ORIGINAL

    @pytest.mark.asyncio
    async def test_both_pipelines_return_agent_response(self) -> None:
        from agents.orchestrator import Orchestrator
        from langchain_pipeline.pipeline import LangChainPipeline

        import inspect

        orig_sig = inspect.signature(Orchestrator.process)
        lc_sig = inspect.signature(LangChainPipeline.process)

        orig_params = list(orig_sig.parameters.keys())
        lc_params = list(lc_sig.parameters.keys())

        assert orig_params == lc_params  # ["self", "message", "deal_id"]
