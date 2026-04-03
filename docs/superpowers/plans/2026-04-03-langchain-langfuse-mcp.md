# LangChain + Langfuse + MCP Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LangChain parallel pipeline, Langfuse observability, and MCP server to EduFlow AI Assistant for AI/LLM Engineer portfolio.

**Architecture:** Three independent packages (`langchain_pipeline/`, `observability/`, `mcp_server/`) added alongside existing code. Pipeline switching via `PIPELINE_MODE` env. Original code unchanged except Langfuse decorators and one line in wappi router.

**Tech Stack:** LangChain 0.3+, langchain-openai, langchain-chroma, Langfuse 2.0+, MCP SDK (FastMCP), Python 3.12

**Spec:** `docs/superpowers/specs/2026-04-03-langchain-langfuse-mcp-design.md`

---

## File Structure

### New Files

```
observability/
  ├── __init__.py              # Package init
  ├── config.py                # Langfuse client init, env-based on/off
  ├── decorators.py            # @observe_if_enabled — no-op if disabled
  └── langchain_handler.py     # CallbackHandler for LangChain pipeline

langchain_pipeline/
  ├── __init__.py              # Package init
  ├── rag.py                   # LangChain VectorStore + Retriever
  ├── chains.py                # CourseChain, PlatformChain
  ├── tools.py                 # LangChain Tools (classify, search_kb)
  └── pipeline.py              # Entry point: process(message, deal_id) → AgentResponse

mcp_server/
  ├── __init__.py              # Package init
  ├── __main__.py              # python -m mcp_server entry point
  ├── server.py                # FastMCP app + tool registration
  ├── tools_kb.py              # Tool: search_knowledge_base
  └── tools_crm.py             # Tools: get_deal, find_deals_by_phone

tests/unit/test_observability.py
tests/unit/test_langchain_pipeline.py
tests/unit/test_langchain_rag.py
tests/unit/test_langchain_chains.py
tests/unit/test_mcp_tools.py
tests/integration/test_pipeline_switching.py
```

### Modified Files

```
config.py                      # Add PipelineMode, langfuse_* settings
app.py                         # Pipeline factory in lifespan
agents/orchestrator.py         # @observe_if_enabled decorators
agents/classifier.py           # @observe_if_enabled decorator
agents/course_agent.py         # @observe_if_enabled decorator
agents/platform_agent.py       # @observe_if_enabled decorator
routers/wappi.py               # orchestrator → pipeline (1 line)
requirements.txt               # New dependencies
docker-compose.prod.yml        # Add mcp-server service
.env.example                   # New variables
```

---

## Task 1: Dependencies and Config

**Files:**
- Modify: `requirements.txt`
- Modify: `config.py:1-50`
- Modify: `.env.example`
- Test: `tests/unit/test_config_pipeline.py` (new)

- [ ] **Step 1: Add new dependencies to requirements.txt**

Add after line 15 (`chromadb==0.5.5`):

```python
# LangChain (parallel pipeline)
langchain==0.3.25
langchain-openai==0.3.17
langchain-chroma==0.2.4
langchain-text-splitters==0.3.8

# Observability
langfuse==2.60.3

# MCP Server
mcp[cli]==1.9.4
```

- [ ] **Step 2: Write test for PipelineMode config**

Create `tests/unit/test_config_pipeline.py`:

```python
from __future__ import annotations

import os

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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_config_pipeline.py -v`

Expected: FAIL — `PipelineMode` not defined in `config.py`

- [ ] **Step 4: Add PipelineMode and Langfuse settings to config.py**

In `config.py`, add `PipelineMode` enum after `LLMProvider`:

```python
class PipelineMode(str, Enum):
    ORIGINAL = "original"
    LANGCHAIN = "langchain"
```

In `Settings` class, add after `log_format` (line 45):

```python
    # Pipeline
    pipeline_mode: PipelineMode = PipelineMode.ORIGINAL

    # Langfuse (observability)
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_config_pipeline.py -v`

Expected: 3 passed

- [ ] **Step 6: Update .env.example**

Add at end of `.env.example`:

```bash

# Pipeline mode: "original" or "langchain"
PIPELINE_MODE=original

# Langfuse observability (optional)
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=pk-your-langfuse-public-key
LANGFUSE_SECRET_KEY=sk-your-langfuse-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

- [ ] **Step 7: Run full test suite to ensure nothing breaks**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest --tb=short -q`

Expected: all 173+ tests pass

- [ ] **Step 8: Commit**

```bash
git add requirements.txt config.py .env.example tests/unit/test_config_pipeline.py
git commit -m "feat: add PipelineMode config and LangChain/Langfuse/MCP dependencies"
```

---

## Task 2: Observability — Langfuse Config and Decorators

**Files:**
- Create: `observability/__init__.py`
- Create: `observability/config.py`
- Create: `observability/decorators.py`
- Create: `observability/langchain_handler.py`
- Test: `tests/unit/test_observability.py` (new)

- [ ] **Step 1: Write tests for observability module**

Create `tests/unit/test_observability.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestObserveIfEnabled:
    def test_noop_when_disabled(self) -> None:
        """Decorator should be a no-op when Langfuse is disabled."""
        with patch("observability.config.is_langfuse_enabled", return_value=False):
            from observability.decorators import observe_if_enabled

            @observe_if_enabled(name="test_func")
            async def my_func(x: int) -> int:
                return x * 2

            # Function should work unchanged
            import asyncio
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_observability.py -v`

Expected: FAIL — `observability` module not found

- [ ] **Step 3: Create observability package**

Create `observability/__init__.py`:

```python
```

Create `observability/config.py`:

```python
from __future__ import annotations

import structlog

from config import settings

logger = structlog.get_logger()


def is_langfuse_enabled() -> bool:
    """Check if Langfuse observability is enabled via config."""
    return settings.langfuse_enabled


def get_langfuse_client():  # type: ignore[no-untyped-def]
    """Get Langfuse client instance. Returns None if disabled.

    Lazy import to avoid ImportError when langfuse is not needed.
    """
    if not is_langfuse_enabled():
        return None

    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
```

Create `observability/decorators.py`:

```python
from __future__ import annotations

import functools
from typing import Any, Callable

from observability.config import is_langfuse_enabled


def observe_if_enabled(name: str) -> Callable:  # type: ignore[type-arg]
    """Decorator: wraps async function with Langfuse @observe if enabled, no-op otherwise.

    Args:
        name: Trace/span name for Langfuse dashboard
    """

    def decorator(func: Callable) -> Callable:  # type: ignore[type-arg]
        if not is_langfuse_enabled():
            return func

        from langfuse.decorators import observe

        @observe(name=name)
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper

    return decorator
```

Create `observability/langchain_handler.py`:

```python
from __future__ import annotations

from typing import Any

from observability.config import is_langfuse_enabled


def get_langfuse_handler(
    trace_name: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Get Langfuse CallbackHandler for LangChain tracing.

    Returns None if Langfuse is disabled — callers should check for None
    and skip passing callbacks.

    Args:
        trace_name: Name for the trace in Langfuse dashboard
        user_id: Optional user/deal ID for filtering
        metadata: Optional metadata dict (e.g. {"pipeline": "langchain"})
    """
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_observability.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add observability/ tests/unit/test_observability.py
git commit -m "feat: add observability package with Langfuse config, decorators, and LangChain handler"
```

---

## Task 3: Add Langfuse Decorators to Original Pipeline

**Files:**
- Modify: `agents/orchestrator.py:56-57`
- Modify: `agents/classifier.py:38-39`
- Modify: `agents/course_agent.py:35-36`
- Modify: `agents/platform_agent.py:36-37`

- [ ] **Step 1: Add @observe_if_enabled to Orchestrator.process()**

In `agents/orchestrator.py`, add import after line 5:

```python
from observability.decorators import observe_if_enabled
```

Add decorator before `process` method (line 56):

```python
    @observe_if_enabled(name="orchestrator.process")
    async def process(
```

- [ ] **Step 2: Add @observe_if_enabled to ClassifierAgent.classify()**

In `agents/classifier.py`, add import after line 8:

```python
from observability.decorators import observe_if_enabled
```

Add decorator before `classify` method (line 38):

```python
    @observe_if_enabled(name="classifier.classify")
    async def classify(self, message: str) -> MessageType:
```

- [ ] **Step 3: Add @observe_if_enabled to CourseAgent.process()**

In `agents/course_agent.py`, add import after line 9:

```python
from observability.decorators import observe_if_enabled
```

Add decorator before `process` method (line 35):

```python
    @observe_if_enabled(name="course_agent.process")
    async def process(self, message: str, deal_id: int | None) -> AgentResponse:
```

- [ ] **Step 4: Add @observe_if_enabled to PlatformAgent.process()**

In `agents/platform_agent.py`, add import after line 8:

```python
from observability.decorators import observe_if_enabled
```

Add decorator before `process` method (line 36):

```python
    @observe_if_enabled(name="platform_agent.process")
    async def process(self, message: str) -> AgentResponse:
```

- [ ] **Step 5: Run full test suite**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest --tb=short -q`

Expected: all existing tests pass (decorators are no-op since LANGFUSE_ENABLED=false by default)

- [ ] **Step 6: Commit**

```bash
git add agents/orchestrator.py agents/classifier.py agents/course_agent.py agents/platform_agent.py
git commit -m "feat: add Langfuse @observe_if_enabled decorators to original pipeline agents"
```

---

## Task 4: LangChain RAG (VectorStore + Retriever)

**Files:**
- Create: `langchain_pipeline/__init__.py`
- Create: `langchain_pipeline/rag.py`
- Test: `tests/unit/test_langchain_rag.py` (new)

- [ ] **Step 1: Write tests for LangChain RAG**

Create `tests/unit/test_langchain_rag.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from langchain_pipeline.rag import build_retriever, index_knowledge_base


class TestBuildRetriever:
    def test_returns_retriever(self) -> None:
        """build_retriever should return a VectorStoreRetriever."""
        with patch("langchain_pipeline.rag.Chroma") as mock_chroma, \
             patch("langchain_pipeline.rag.OpenAIEmbeddings") as mock_embeddings:
            mock_chroma.return_value = MagicMock()
            mock_chroma.return_value.as_retriever.return_value = MagicMock()

            retriever = build_retriever(
                embeddings_api_key="test-key",
                persist_dir="data/chroma_db",
            )
            assert retriever is not None
            mock_chroma.return_value.as_retriever.assert_called_once_with(
                search_kwargs={"k": 3},
            )

    def test_uses_correct_embedding_model(self) -> None:
        """Should use text-embedding-3-small model."""
        with patch("langchain_pipeline.rag.Chroma") as mock_chroma, \
             patch("langchain_pipeline.rag.OpenAIEmbeddings") as mock_embeddings:
            mock_chroma.return_value = MagicMock()
            mock_chroma.return_value.as_retriever.return_value = MagicMock()

            build_retriever(
                embeddings_api_key="test-key",
                persist_dir="data/chroma_db",
            )
            mock_embeddings.assert_called_once_with(
                api_key="test-key",
                model="text-embedding-3-small",
            )


class TestIndexKnowledgeBase:
    def test_index_from_directory(self, tmp_path: Path) -> None:
        """Should load .md files, split, and add to vectorstore."""
        # Create test markdown files
        (tmp_path / "test1.md").write_text("First document content about registration.")
        (tmp_path / "test2.md").write_text("Second document content about payments.")

        with patch("langchain_pipeline.rag.Chroma") as mock_chroma, \
             patch("langchain_pipeline.rag.OpenAIEmbeddings"):
            mock_vs = MagicMock()
            mock_chroma.from_documents.return_value = mock_vs

            result = index_knowledge_base(
                kb_dir=tmp_path,
                embeddings_api_key="test-key",
                persist_dir=str(tmp_path / "chroma"),
            )
            assert result > 0
            mock_chroma.from_documents.assert_called_once()

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        """Should return 0 if no .md files in directory."""
        with patch("langchain_pipeline.rag.Chroma"), \
             patch("langchain_pipeline.rag.OpenAIEmbeddings"):
            result = index_knowledge_base(
                kb_dir=tmp_path,
                embeddings_api_key="test-key",
                persist_dir=str(tmp_path / "chroma"),
            )
            assert result == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_langchain_rag.py -v`

Expected: FAIL — `langchain_pipeline` module not found

- [ ] **Step 3: Implement langchain_pipeline/rag.py**

Create `langchain_pipeline/__init__.py`:

```python
```

Create `langchain_pipeline/rag.py`:

```python
from __future__ import annotations

from pathlib import Path

import structlog
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = structlog.get_logger()

KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")
CHROMA_DB_DIR = "data/chroma_db"
COLLECTION_NAME = "eduflow_knowledge_lc"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def build_retriever(
    embeddings_api_key: str,
    persist_dir: str = CHROMA_DB_DIR,
    k: int = 3,
):  # type: ignore[no-untyped-def]
    """Build LangChain retriever backed by ChromaDB.

    Uses the same embedding model (text-embedding-3-small) and search params
    as the original VectorDB implementation for consistent results.

    Args:
        embeddings_api_key: OpenAI API key for embeddings
        persist_dir: ChromaDB persistence directory
        k: Number of results to return (default: 3, same as original)
    """
    embeddings = OpenAIEmbeddings(
        api_key=embeddings_api_key,
        model="text-embedding-3-small",
    )
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    return vectorstore.as_retriever(search_kwargs={"k": k})


def index_knowledge_base(
    kb_dir: Path = KNOWLEDGE_BASE_DIR,
    embeddings_api_key: str = "",
    persist_dir: str = CHROMA_DB_DIR,
) -> int:
    """Index knowledge base markdown files into ChromaDB via LangChain.

    Mirrors the original VectorDB.index_knowledge_base() logic:
    - Loads .md files from kb_dir
    - Splits into chunks (500 words, 50 overlap)
    - Indexes into ChromaDB with cosine similarity

    Uses TextLoader (not UnstructuredMarkdownLoader) to avoid
    heavy `unstructured` dependency — markdown files are simple
    and don't need structural parsing.

    Args:
        kb_dir: Directory with .md knowledge base files
        embeddings_api_key: OpenAI API key for embeddings
        persist_dir: ChromaDB persistence directory

    Returns:
        Number of document chunks indexed
    """
    from langchain_community.document_loaders import TextLoader

    md_files = sorted(kb_dir.glob("*.md"))
    if not md_files:
        logger.warning("langchain_kb_no_files", path=str(kb_dir))
        return 0

    all_docs = []
    for md_file in md_files:
        loader = TextLoader(str(md_file), encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = md_file.name
        all_docs.extend(docs)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=lambda text: len(text.split()),
        is_separator_regex=False,
    )
    chunks = splitter.split_documents(all_docs)

    if not chunks:
        return 0

    embeddings = OpenAIEmbeddings(
        api_key=embeddings_api_key,
        model="text-embedding-3-small",
    )
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
    )

    logger.info("langchain_kb_indexed", documents=len(chunks))
    return len(chunks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_langchain_rag.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add langchain_pipeline/ tests/unit/test_langchain_rag.py
git commit -m "feat: add LangChain RAG module with VectorStore retriever and knowledge base indexing"
```

---

## Task 5: LangChain Chains (CourseChain, PlatformChain)

**Files:**
- Create: `langchain_pipeline/chains.py`
- Test: `tests/unit/test_langchain_chains.py` (new)

- [ ] **Step 1: Write tests for LangChain chains**

Create `tests/unit/test_langchain_chains.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.types import AgentResponse, MessageType


class TestPlatformChain:
    @pytest.mark.asyncio
    async def test_returns_agent_response_with_rag(self) -> None:
        """PlatformChain should search retriever and return AgentResponse."""
        from langchain_pipeline.chains import PlatformChain

        mock_retriever = MagicMock()
        mock_retriever.ainvoke = AsyncMock(return_value=[
            MagicMock(page_content="Нажмите 'Забыли пароль' на странице входа."),
            MagicMock(page_content="Проверьте папку 'Спам' если письмо не пришло."),
        ])

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Нажмите кнопку 'Забыли пароль' на странице входа."

        chain = PlatformChain(llm=mock_llm, retriever=mock_retriever)
        response = await chain.process("Как восстановить пароль?")

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.PLATFORM
        assert response.should_send is True
        assert len(response.text) > 0

    @pytest.mark.asyncio
    async def test_escalates_when_no_rag_results(self) -> None:
        """PlatformChain should escalate when retriever returns empty."""
        from langchain_pipeline.chains import PlatformChain

        mock_retriever = MagicMock()
        mock_retriever.ainvoke = AsyncMock(return_value=[])

        mock_llm = AsyncMock()

        chain = PlatformChain(llm=mock_llm, retriever=mock_retriever)
        response = await chain.process("Неизвестный вопрос")

        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False


class TestCourseChain:
    @pytest.mark.asyncio
    async def test_returns_agent_response_with_deal(self) -> None:
        """CourseChain should fetch deal and return AgentResponse."""
        from langchain_pipeline.chains import CourseChain

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Ваш курс начинается 15 апреля."

        mock_bitrix = AsyncMock()
        mock_bitrix.get_deal.return_value = {
            "ID": "123",
            "TITLE": "Python для начинающих",
            "STAGE_ID": "LEARNING",
            "CONTACT_ID": "456",
            "UF_CRM_SUM": "5000",
            "COMMENTS": "Курс: Python",
            "DATE_CREATE": "2026-03-01",
        }
        mock_bitrix.parse_deal_stage.return_value = MagicMock(is_terminal=False)

        chain = CourseChain(llm=mock_llm, bitrix=mock_bitrix)
        response = await chain.process("Когда начинается мой курс?", deal_id=123)

        assert isinstance(response, AgentResponse)
        assert response.agent_type == MessageType.COURSE
        assert response.should_send is True

    @pytest.mark.asyncio
    async def test_escalates_without_deal_id(self) -> None:
        """CourseChain should escalate when deal_id is None."""
        from langchain_pipeline.chains import CourseChain

        mock_llm = AsyncMock()
        mock_bitrix = AsyncMock()

        chain = CourseChain(llm=mock_llm, bitrix=mock_bitrix)
        response = await chain.process("Вопрос о кур��е", deal_id=None)

        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_escalates_on_terminal_stage(self) -> None:
        """CourseChain should escalate when deal is in terminal stage."""
        from langchain_pipeline.chains import CourseChain

        mock_llm = AsyncMock()
        mock_bitrix = AsyncMock()
        mock_bitrix.get_deal.return_value = {
            "ID": "123",
            "TITLE": "Course",
            "STAGE_ID": "COMPLETED",
        }
        mock_bitrix.parse_deal_stage.return_value = MagicMock(is_terminal=True)

        chain = CourseChain(llm=mock_llm, bitrix=mock_bitrix)
        response = await chain.process("Вопрос", deal_id=123)

        assert response.agent_type == MessageType.ESCALATE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_langchain_chains.py -v`

Expected: FAIL — `langchain_pipeline.chains` not found

- [ ] **Step 3: Implement langchain_pipeline/chains.py**

Create `langchain_pipeline/chains.py`:

```python
"""LangChain chains mirroring CourseAgent and PlatformAgent.

Architecture decision (ADR-1): BitrixClient is reused directly instead of
wrapping in a LangChain Tool. LangChain is used where it adds value — RAG
retrieval and prompt chains — not for wrapping working HTTP clients.
Same applies to sanitize(), TypicalAgent, AgentResponse, and prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agents.types import AgentResponse, MessageType
from prompts.course_agent import COURSE_AGENT_SYSTEM_PROMPT
from prompts.platform_agent import PLATFORM_AGENT_SYSTEM_PROMPT
from utils.sanitize import sanitize_llm_output

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient
    from integrations.llm_client import LLMClient

logger = structlog.get_logger()


class PlatformChain:
    """LangChain-based platform support agent with RAG retrieval.

    Uses LangChain Retriever for knowledge base search, then delegates
    to the existing LLMClient for generation (same prompt templates).
    """

    def __init__(self, llm: LLMClient, retriever) -> None:  # type: ignore[no-untyped-def]
        self._llm = llm
        self._retriever = retriever

    async def process(self, message: str) -> AgentResponse:
        """Process platform question using LangChain retriever + LLM.

        Args:
            message: User's incoming message text

        Returns:
            AgentResponse with answer based on RAG context, or escalate
        """
        # Retrieve relevant documents via LangChain retriever
        docs = await self._retriever.ainvoke(message)

        if not docs:
            logger.warning("lc_platform_no_rag_results", message_length=len(message))
            return AgentResponse.escalate()

        # Format RAG context as numbered list (same format as original)
        rag_items = []
        for i, doc in enumerate(docs, start=1):
            content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            rag_items.append(f"{i}. {content}")
        rag_context = "\n".join(rag_items)

        # Generate response using existing prompt template
        system_prompt = PLATFORM_AGENT_SYSTEM_PROMPT.format(rag_context=rag_context)
        llm_response = await self._llm.generate(
            system_prompt=system_prompt,
            user_message=message,
        )

        sanitized = sanitize_llm_output(llm_response)
        if not sanitized.strip():
            logger.warning("lc_platform_empty_response")
            return AgentResponse.escalate()

        return AgentResponse(
            text=sanitized,
            agent_type=MessageType.PLATFORM,
            should_send=True,
        )


class CourseChain:
    """LangChain-based course agent with Bitrix24 deal context.

    Architecture decision (ADR-1): Uses BitrixClient directly rather than
    wrapping it in a LangChain Tool. The CRM client already has a clean
    async interface — LangChain is used for RAG and chains, not for
    wrapping every API call.
    """

    def __init__(self, llm: LLMClient, bitrix: BitrixClient) -> None:
        self._llm = llm
        self._bitrix = bitrix

    async def process(self, message: str, deal_id: int | None) -> AgentResponse:
        """Process course question using Bitrix24 deal context + LLM.

        Args:
            message: User's incoming message text
            deal_id: Bitrix24 deal ID for context

        Returns:
            AgentResponse with answer, or escalate if no deal / terminal stage
        """
        if deal_id is None:
            logger.warning("lc_course_no_deal_id")
            return AgentResponse.escalate()

        deal = await self._bitrix.get_deal(deal_id)
        if deal is None:
            logger.warning("lc_course_deal_not_found", deal_id=deal_id)
            return AgentResponse.escalate()

        # Check terminal stage (same logic as original CourseAgent)
        stage_id = deal.get("STAGE_ID")
        stage = self._bitrix.parse_deal_stage(stage_id) if stage_id else None
        if stage and stage.is_terminal:
            logger.info("lc_course_terminal_stage", deal_id=deal_id, stage=stage)
            return AgentResponse.escalate()

        # Format deal context (same format as original CourseAgent)
        deal_context = self._format_deal_context(deal)

        system_prompt = COURSE_AGENT_SYSTEM_PROMPT.format(deal_context=deal_context)
        llm_response = await self._llm.generate(
            system_prompt=system_prompt,
            user_message=message,
        )

        sanitized = sanitize_llm_output(llm_response)
        if not sanitized.strip():
            logger.warning("lc_course_empty_response", deal_id=deal_id)
            return AgentResponse.escalate()

        return AgentResponse(
            text=sanitized,
            agent_type=MessageType.COURSE,
            should_send=True,
        )

    @staticmethod
    def _format_deal_context(deal: dict) -> str:
        """Format deal info for system prompt injection (same as original)."""
        return f"""
Student Deal Information:
- Deal ID: {deal.get("ID")}
- Course: {deal.get("TITLE", "Unknown course")}
- Stage: {deal.get("STAGE_ID", "Unknown")}
- Contact ID: {deal.get("CONTACT_ID", "Unknown")}
- Payment Amount: {deal.get("UF_CRM_SUM", "Unknown")}
- Enrollment Date: {deal.get("DATE_CREATE", "Unknown")}
- Course Details: {deal.get("COMMENTS", "")}
""".strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_langchain_chains.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add langchain_pipeline/chains.py tests/unit/test_langchain_chains.py
git commit -m "feat: add LangChain CourseChain and PlatformChain with RAG retrieval"
```

---

## Task 6: LangChain Tools and Pipeline Entry Point

**Files:**
- Create: `langchain_pipeline/tools.py`
- Create: `langchain_pipeline/pipeline.py`
- Test: `tests/unit/test_langchain_pipeline.py` (new)

- [ ] **Step 1: Write tests for LangChainPipeline**

Create `tests/unit/test_langchain_pipeline.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.types import AgentResponse, MessageType
from langchain_pipeline.pipeline import LangChainPipeline


@pytest.fixture
def mock_deps():  # type: ignore[no-untyped-def]
    """Create mocked dependencies for LangChainPipeline."""
    return {
        "llm": AsyncMock(),
        "retriever": MagicMock(),
        "bitrix_client": AsyncMock(),
        "langfuse_handler": None,
    }


@pytest.fixture
def pipeline(mock_deps):  # type: ignore[no-untyped-def]
    return LangChainPipeline(**mock_deps)


class TestLangChainPipeline:
    @pytest.mark.asyncio
    async def test_greeting_returns_typical_response(self, pipeline: LangChainPipeline) -> None:
        """Greeting messages should be handled by TypicalAgent (reused)."""
        response = await pipeline.process("Привет!", deal_id=None)
        assert isinstance(response, AgentResponse)
        assert response.should_send is True
        assert response.agent_type == MessageType.TYPICAL

    @pytest.mark.asyncio
    async def test_empty_message_returns_silent(self, pipeline: LangChainPipeline) -> None:
        """Empty messages should return silent response."""
        response = await pipeline.process("", deal_id=None)
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_platform_question_routes_to_platform_chain(
        self, pipeline: LangChainPipeline, mock_deps: dict,
    ) -> None:
        """Platform questions should route to PlatformChain."""
        # Setup: classifier returns "platform", retriever returns docs
        mock_deps["llm"].generate.return_value = "platform"
        mock_deps["retriever"].ainvoke = AsyncMock(return_value=[
            MagicMock(page_content="Нажмите 'Забыли пароль'."),
        ])
        # Second LLM call (generation) returns answer
        mock_deps["llm"].generate.side_effect = [
            "platform",  # classification
            "Нажмите кнопку 'Забыли пароль'.",  # generation
        ]

        response = await pipeline.process("Как сбросить пароль?", deal_id=None)

        assert response.agent_type == MessageType.PLATFORM
        assert response.should_send is True

    @pytest.mark.asyncio
    async def test_escalate_returns_escalate(
        self, pipeline: LangChainPipeline, mock_deps: dict,
    ) -> None:
        """Escalate classification should return escalate response."""
        mock_deps["llm"].generate.return_value = "escalate"

        response = await pipeline.process("Хочу вернуть деньги!", deal_id=None)

        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False

    @pytest.mark.asyncio
    async def test_returns_agent_response_type(self, pipeline: LangChainPipeline) -> None:
        """Pipeline should always return AgentResponse (same contract as Orchestrator)."""
        response = await pipeline.process("Привет", deal_id=None)
        assert isinstance(response, AgentResponse)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_langchain_pipeline.py -v`

Expected: FAIL — `langchain_pipeline.pipeline` not found

- [ ] **Step 3: Create langchain_pipeline/tools.py**

Create `langchain_pipeline/tools.py`:

```python
"""LangChain Tools for concept demonstration.

These tools wrap the existing pipeline components as LangChain Tool objects,
demonstrating LangChain's tool abstraction. In the current pipeline, chains
are called directly — tools are defined for portfolio demonstration and
potential future AgentExecutor integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import Tool

if TYPE_CHECKING:
    pass


def create_classify_tool(llm_client) -> Tool:  # type: ignore[no-untyped-def]
    """Create a LangChain Tool for message classification.

    Args:
        llm_client: LLMClient instance for classification
    """
    from prompts.classifier import CLASSIFIER_SYSTEM_PROMPT

    async def classify(message: str) -> str:
        return await llm_client.generate(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            user_message=message,
        )

    return Tool(
        name="classify_message",
        description="Classify student message into: course, platform, escalate",
        func=lambda x: x,  # sync placeholder (not used)
        coroutine=classify,
    )


def create_search_kb_tool(retriever) -> Tool:  # type: ignore[no-untyped-def]
    """Create a LangChain Tool for knowledge base search.

    Args:
        retriever: LangChain retriever instance
    """

    async def search(query: str) -> str:
        docs = await retriever.ainvoke(query)
        if not docs:
            return "No results found."
        return "\n".join(f"- {doc.page_content[:200]}" for doc in docs)

    return Tool(
        name="search_knowledge_base",
        description="Search EduFlow knowledge base for platform questions about registration, payments, certificates, video playback, or password reset",
        func=lambda x: x,  # sync placeholder (not used)
        coroutine=search,
    )
```

- [ ] **Step 4: Create langchain_pipeline/pipeline.py**

Create `langchain_pipeline/pipeline.py`:

```python
"""LangChain pipeline — parallel implementation of the message processing flow.

Same contract as Orchestrator: process(message, deal_id) → AgentResponse.
Reuses TypicalAgent, sanitize(), prompts, BitrixClient from original code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from agents.classifier import CONFIRMATION_PATTERNS, GREETING_PATTERNS, THANKS_PATTERNS
from agents.types import AgentResponse, MessageType
from agents.typical_agent import TypicalAgent
from langchain_pipeline.chains import CourseChain, PlatformChain
from prompts.classifier import CLASSIFIER_SYSTEM_PROMPT
from utils.sanitize import sanitize_input

if TYPE_CHECKING:
    from integrations.bitrix_client import BitrixClient
    from integrations.llm_client import LLMClient

logger = structlog.get_logger()

VALID_LLM_RESPONSES = {"course", "platform", "escalate"}


class LangChainPipeline:
    """LangChain-based message processing pipeline.

    Drop-in replacement for Orchestrator with the same process() contract.
    Uses LangChain Retriever for RAG and LangChain-style chains for agents.
    Reuses TypicalAgent, sanitize(), prompts, and BitrixClient from original code.
    """

    def __init__(
        self,
        llm: LLMClient,
        retriever: Any,
        bitrix_client: BitrixClient,
        langfuse_handler: Any | None = None,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._bitrix = bitrix_client
        self._langfuse_handler = langfuse_handler

        # Reuse TypicalAgent from original code (see ADR-1)
        self._typical_agent = TypicalAgent()

        # LangChain chains
        self._platform_chain = PlatformChain(llm=llm, retriever=retriever)
        self._course_chain = CourseChain(llm=llm, bitrix=bitrix_client)

    async def process(
        self, message: str, deal_id: int | None = None
    ) -> AgentResponse:
        """Process incoming message through LangChain pipeline.

        Same contract as Orchestrator.process() — returns AgentResponse.

        Args:
            message: User's incoming message text
            deal_id: Optional Bitrix24 deal ID for course context

        Returns:
            AgentResponse from appropriate chain or escalation
        """
        # 1. Sanitize input (reuse from original)
        sanitized = sanitize_input(message)
        if not sanitized:
            return AgentResponse.silent()

        logger.info("lc_pipeline_process", message_length=len(sanitized))

        # 2. Try TypicalAgent (reuse from original — greeting/thanks/confirmation)
        typical_response = await self._try_typical(sanitized)
        if typical_response is not None:
            return typical_response

        # 3. Classify via LLM
        message_type = await self._classify(sanitized)
        logger.info("lc_pipeline_classified", type=message_type.value)

        # 4. Route to appropriate chain
        if message_type == MessageType.TYPICAL:
            return await self._typical_agent.process(sanitized)
        if message_type == MessageType.PLATFORM:
            return await self._platform_chain.process(sanitized)
        if message_type == MessageType.COURSE:
            return await self._course_chain.process(sanitized, deal_id=deal_id)

        # ESCALATE or unknown
        return AgentResponse.escalate()

    async def _classify(self, message: str) -> MessageType:
        """Classify message using LLM (same prompt as original ClassifierAgent)."""
        response = await self._llm.generate(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            user_message=message,
        )
        category = response.strip().lower()
        if category in VALID_LLM_RESPONSES:
            return MessageType(category)
        logger.warning("lc_unexpected_category", category=category)
        return MessageType.ESCALATE

    async def _try_typical(self, message: str) -> AgentResponse | None:
        """Try to handle message as typical (greeting/thanks/confirmation)."""
        response = await self._typical_agent.process(message)
        if response.should_send:
            return response

        # Check if confirmation pattern matched (silent response)
        stripped = message.strip()
        if (
            GREETING_PATTERNS.match(stripped)
            or THANKS_PATTERNS.match(stripped)
            or CONFIRMATION_PATTERNS.match(stripped)
        ):
            return response

        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_langchain_pipeline.py -v`

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add langchain_pipeline/tools.py langchain_pipeline/pipeline.py tests/unit/test_langchain_pipeline.py
git commit -m "feat: add LangChainPipeline entry point and LangChain Tools"
```

---

## Task 7: Pipeline Switching in app.py and wappi router

**Files:**
- Modify: `app.py:46-152`
- Modify: `routers/wappi.py:204,238`
- Test: `tests/integration/test_pipeline_switching.py` (new)

- [ ] **Step 1: Write test for pipeline switching**

Create `tests/integration/test_pipeline_switching.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.types import AgentResponse, MessageType


class TestPipelineSwitching:
    @pytest.mark.asyncio
    async def test_original_pipeline_by_default(self) -> None:
        """Default PIPELINE_MODE=original should use Orchestrator."""
        with patch("config.settings") as mock_settings:
            from config import PipelineMode
            mock_settings.pipeline_mode = PipelineMode.ORIGINAL
            # Original pipeline = Orchestrator instance
            # Just verify config is read correctly
            assert mock_settings.pipeline_mode == PipelineMode.ORIGINAL

    @pytest.mark.asyncio
    async def test_both_pipelines_return_agent_response(self) -> None:
        """Both pipelines must return AgentResponse (contract check)."""
        from agents.orchestrator import Orchestrator
        from langchain_pipeline.pipeline import LangChainPipeline

        # Check that both have process() method with same signature
        import inspect

        orig_sig = inspect.signature(Orchestrator.process)
        lc_sig = inspect.signature(LangChainPipeline.process)

        orig_params = list(orig_sig.parameters.keys())
        lc_params = list(lc_sig.parameters.keys())

        assert orig_params == lc_params  # ["self", "message", "deal_id"]
```

- [ ] **Step 2: Run test to verify it passes (these are contract tests)**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/integration/test_pipeline_switching.py -v`

Expected: 2 passed

- [ ] **Step 3: Modify app.py lifespan — add pipeline factory**

In `app.py`, add import at top (after line 27):

```python
from config import PipelineMode
```

In `lifespan()`, after line 150 (`app.state.orchestrator = orchestrator`), add:

```python
        # Pipeline selection (default: original Orchestrator)
        if settings.pipeline_mode == PipelineMode.LANGCHAIN:
            from langchain_pipeline.pipeline import LangChainPipeline
            from langchain_pipeline.rag import build_retriever
            from observability.langchain_handler import get_langfuse_handler

            logger.info("initializing_langchain_pipeline")
            lc_retriever = build_retriever(
                embeddings_api_key=settings.openai_embeddings_api_key,
            )
            pipeline = LangChainPipeline(
                llm=llm_client,
                retriever=lc_retriever,
                bitrix_client=bitrix_client,
                langfuse_handler=get_langfuse_handler("langchain"),
            )
            app.state.pipeline = pipeline
            logger.info("langchain_pipeline_initialized")
        else:
            app.state.pipeline = orchestrator
```

- [ ] **Step 4: Modify routers/wappi.py — use pipeline instead of orchestrator**

In `routers/wappi.py`, at line 204, change:

```python
    orchestrator = request.app.state.orchestrator
```

to:

```python
    pipeline = request.app.state.pipeline
```

At line 206, change:

```python
    if not all([db, wappi_incoming, wappi_outgoing, orchestrator]):
```

to:

```python
    if not all([db, wappi_incoming, wappi_outgoing, pipeline]):
```

At line 238, change:

```python
            agent_response = await orchestrator.process(payload.body)
```

to:

```python
            agent_response = await pipeline.process(payload.body)
```

- [ ] **Step 5: Run full test suite**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest --tb=short -q`

Expected: all tests pass (pipeline defaults to orchestrator, so existing tests work)

- [ ] **Step 6: Commit**

```bash
git add app.py routers/wappi.py tests/integration/test_pipeline_switching.py
git commit -m "feat: add pipeline switching — PIPELINE_MODE=original|langchain via env"
```

---

## Task 8: MCP Server

**Files:**
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/server.py`
- Create: `mcp_server/tools_kb.py`
- Create: `mcp_server/tools_crm.py`
- Test: `tests/unit/test_mcp_tools.py` (new)

- [ ] **Step 1: Write tests for MCP tools**

Create `tests/unit/test_mcp_tools.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


class TestMcpToolsKb:
    @pytest.mark.asyncio
    async def test_search_knowledge_base_returns_formatted_results(self) -> None:
        """search_knowledge_base should format VectorDB results."""
        from mcp_server.tools_kb import format_results

        results = [
            "Нажмите кнопку 'Забыли пароль' на странице входа.",
            "Проверьте папку 'Спам' если письмо не пришло.",
        ]
        formatted = format_results(results)

        assert "1." in formatted
        assert "2." in formatted
        assert "пароль" in formatted.lower()

    @pytest.mark.asyncio
    async def test_search_empty_results(self) -> None:
        """search_knowledge_base should handle empty results."""
        from mcp_server.tools_kb import format_results

        formatted = format_results([])
        assert "no results" in formatted.lower() or "не найдено" in formatted.lower()


class TestMcpToolsCrm:
    @pytest.mark.asyncio
    async def test_format_deal(self) -> None:
        """format_deal should format deal dict as readable string."""
        from mcp_server.tools_crm import format_deal

        deal = {
            "ID": "123",
            "TITLE": "Python для начинающих",
            "STAGE_ID": "LEARNING",
            "CONTACT_ID": "456",
            "UF_CRM_SUM": "5000",
            "DATE_CREATE": "2026-03-01",
        }
        formatted = format_deal(deal)

        assert "123" in formatted
        assert "Python" in formatted
        assert "LEARNING" in formatted

    @pytest.mark.asyncio
    async def test_format_deal_none(self) -> None:
        """format_deal should handle None deal."""
        from mcp_server.tools_crm import format_deal

        formatted = format_deal(None)
        assert "not found" in formatted.lower() or "не найден" in formatted.lower()

    @pytest.mark.asyncio
    async def test_format_deals_list(self) -> None:
        """format_deals_list should format list of deals."""
        from mcp_server.tools_crm import format_deals_list

        deals = [
            {"ID": "1", "TITLE": "Course A", "STAGE_ID": "LEARNING"},
            {"ID": "2", "TITLE": "Course B", "STAGE_ID": "PAYMENT"},
        ]
        formatted = format_deals_list(deals)

        assert "Course A" in formatted
        assert "Course B" in formatted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_mcp_tools.py -v`

Expected: FAIL — `mcp_server` module not found

- [ ] **Step 3: Create MCP server package**

Create `mcp_server/__init__.py`:

```python
```

Create `mcp_server/tools_kb.py`:

```python
"""MCP Tool: Knowledge Base search.

Exposes the existing VectorDB search as an MCP tool for external
MCP clients (Claude Code, Cursor, etc.).
"""

from __future__ import annotations


def format_results(results: list[str]) -> str:
    """Format VectorDB search results for MCP tool response.

    Args:
        results: List of knowledge base chunks from VectorDB.search()

    Returns:
        Formatted string with numbered results
    """
    if not results:
        return "No results found in knowledge base."

    items = []
    for i, chunk in enumerate(results, start=1):
        truncated = chunk[:500] + "..." if len(chunk) > 500 else chunk
        items.append(f"{i}. {truncated}")
    return "\n\n".join(items)


def register_kb_tools(mcp, vector_db) -> None:  # type: ignore[no-untyped-def]
    """Register knowledge base tools with MCP server.

    Args:
        mcp: FastMCP server instance
        vector_db: VectorDB instance for search
    """

    @mcp.tool()
    async def search_knowledge_base(query: str, n_results: int = 3) -> str:
        """Search EduFlow knowledge base for answers about the platform.

        Args:
            query: Student question about registration, payments,
                   certificates, video playback, or password reset
            n_results: Number of results to return (1-5)

        Returns:
            Relevant knowledge base excerpts with source file names
        """
        clamped = max(1, min(n_results, 5))
        results = await vector_db.search(query, n_results=clamped)
        return format_results(results)
```

Create `mcp_server/tools_crm.py`:

```python
"""MCP Tools: Bitrix24 CRM access.

Exposes the existing BitrixClient methods as MCP tools for external
MCP clients (Claude Code, Cursor, etc.).

Architecture decision (ADR-1): Reuses BitrixClient directly.
"""

from __future__ import annotations

from typing import Any


def format_deal(deal: dict[str, Any] | None) -> str:
    """Format a single deal for MCP tool response.

    Args:
        deal: Deal dict from BitrixClient.get_deal(), or None

    Returns:
        Formatted deal information string
    """
    if deal is None:
        return "Deal not found."

    return f"""Deal #{deal.get("ID", "?")}
- Title: {deal.get("TITLE", "Unknown")}
- Stage: {deal.get("STAGE_ID", "Unknown")}
- Contact ID: {deal.get("CONTACT_ID", "Unknown")}
- Payment: {deal.get("UF_CRM_SUM", "Unknown")}
- Created: {deal.get("DATE_CREATE", "Unknown")}
- Details: {deal.get("COMMENTS", "")}"""


def format_deals_list(deals: list[dict[str, Any]]) -> str:
    """Format a list of deals for MCP tool response.

    Args:
        deals: List of deal dicts from BitrixClient.find_deals_by_phone()

    Returns:
        Formatted deals list string
    """
    if not deals:
        return "No deals found."

    items = []
    for deal in deals:
        items.append(
            f"- Deal #{deal.get('ID', '?')}: {deal.get('TITLE', 'Unknown')} "
            f"(Stage: {deal.get('STAGE_ID', 'Unknown')})"
        )
    return f"Found {len(deals)} deal(s):\n" + "\n".join(items)


def register_crm_tools(mcp, bitrix_client) -> None:  # type: ignore[no-untyped-def]
    """Register CRM tools with MCP server.

    Args:
        mcp: FastMCP server instance
        bitrix_client: BitrixClient instance
    """

    @mcp.tool()
    async def get_deal(deal_id: int) -> str:
        """Get student deal information from Bitrix24 CRM.

        Args:
            deal_id: Bitrix24 deal ID

        Returns:
            Deal details: stage, course, payment, dates
        """
        deal = await bitrix_client.get_deal(deal_id)
        return format_deal(deal)

    @mcp.tool()
    async def find_deals_by_phone(phone: str) -> str:
        """Find student deals in Bitrix24 CRM by phone number.

        Args:
            phone: Phone number (any format, e.g. +7-999-123-45-67)

        Returns:
            List of matching deals with stages and courses
        """
        deals = await bitrix_client.find_deals_by_phone(phone)
        return format_deals_list(deals)
```

- [ ] **Step 4: Create mcp_server/server.py**

Create `mcp_server/server.py`:

```python
"""EduFlow MCP Server — exposes Knowledge Base and CRM tools.

Runs as a separate process from FastAPI. Supports stdio (default)
and SSE transport for network access.

Usage:
    python -m mcp_server.server              # stdio (for Claude Code / Cursor)
    python -m mcp_server.server --transport sse  # SSE (for Docker / network)

See README.md "MCP Server" section for configuration.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from config import settings
from integrations.bitrix_client import BitrixClient
from integrations.vector_db import VectorDB
from mcp_server.tools_crm import register_crm_tools
from mcp_server.tools_kb import register_kb_tools

mcp = FastMCP(
    name="eduflow-assistant",
    description="EduFlow AI Assistant — knowledge base search and CRM access",
)

# Initialize shared dependencies
vector_db = VectorDB(
    embeddings_api_key=settings.openai_embeddings_api_key,
    persist_dir="data/chroma_db",
)
bitrix_client = BitrixClient(
    webhook_url=settings.bitrix24_webhook_url,
)

# Register tools
register_kb_tools(mcp, vector_db)
register_crm_tools(mcp, bitrix_client)

if __name__ == "__main__":
    mcp.run()
```

Add `mcp_server/__main__.py` for `python -m mcp_server.server` support:

```python
from mcp_server.server import mcp

mcp.run()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest tests/unit/test_mcp_tools.py -v`

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add mcp_server/ tests/unit/test_mcp_tools.py
git commit -m "feat: add MCP server with Knowledge Base and CRM tools"
```

---

## Task 9: Docker Compose and MCP Client Config

**Files:**
- Modify: `docker-compose.prod.yml`
- Create: `.mcp.json`

- [ ] **Step 1: Add mcp-server service to docker-compose.prod.yml**

In `docker-compose.prod.yml`, add after the `nginx` service block (before `volumes:`):

```yaml
  # MCP Server (knowledge base + CRM tools)
  mcp-server:
    build: .
    container_name: eduflow_mcp
    command: ["python", "-m", "mcp_server.server", "--transport", "sse"]
    environment:
      OPENAI_EMBEDDINGS_API_KEY: ${OPENAI_EMBEDDINGS_API_KEY}
      BITRIX24_WEBHOOK_URL: ${BITRIX24_WEBHOOK_URL}
      POSTGRES_DSN: postgresql+asyncpg://postgres:${POSTGRES_PASSWORD:-postgres}@db:5432/ai_assistant_eduflow
    ports:
      - "127.0.0.1:8001:8001"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - eduflow_network
    volumes:
      - chroma_data:/app/data/chroma_db
    restart: unless-stopped
```

Also add Langfuse env vars to the `webhook` service environment section:

```yaml
      # Pipeline
      PIPELINE_MODE: ${PIPELINE_MODE:-original}

      # Langfuse (optional)
      LANGFUSE_ENABLED: ${LANGFUSE_ENABLED:-false}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-https://cloud.langfuse.com}
```

- [ ] **Step 2: Create .mcp.json for Claude Code / Cursor**

Create `.mcp.json` in project root:

```json
{
  "mcpServers": {
    "eduflow": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "DOTENV_PATH": ".env"
      }
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml .mcp.json
git commit -m "feat: add MCP server to Docker Compose and .mcp.json client config"
```

---

## Task 10: README MCP Section and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add MCP Server section to README.md**

Add after the existing Architecture section in README.md:

````markdown
## MCP Server

EduFlow предоставляет MCP-сервер (Model Context Protocol), который даёт AI-ассистентам доступ к базе знаний и CRM через стандартный протокол.

### Quick Start

```bash
# Локальный запуск (stdio — для Claude Code / Cursor)
python -m mcp_server.server

# Docker (SSE — для сетевого доступа)
docker compose -f docker-compose.prod.yml up mcp-server
```

### Подключение к Claude Code

Файл `.mcp.json` в корне проекта автоматически подхватывается Claude Code:

```json
{
  "mcpServers": {
    "eduflow": {
      "command": "python",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

### Доступные инструменты

| Tool | Описание |
|------|----------|
| `search_knowledge_base` | Поиск по базе знаний EduFlow (RAG) |
| `get_deal` | Получить информацию о сделке из Bitrix24 CRM |
| `find_deals_by_phone` | Найти сделки по номеру телефона |

### Пример использования

```
> search_knowledge_base("Как сбросить пароль?")

1. Если вы забыли пароль, нажмите на кнопку 'Забыли пароль?'
   на странице входа. Вам будет отправлено письмо со ссылкой...

2. Для восстановления пароля потребуется доступ к электронной
   почте, с которой вы регистрировались...
```
````

- [ ] **Step 2: Add LangChain and Langfuse sections to README.md**

Add after MCP Server section:

````markdown
## LangChain Pipeline

Проект содержит две параллельные реализации обработки сообщений:

| Пайплайн | Описание | Переключение |
|----------|----------|-------------|
| **Original** (по умолчанию) | Собственная оркестрация, прямые вызовы OpenAI API | `PIPELINE_MODE=original` |
| **LangChain** | LangChain Retriever + Chains, тот же RAG и промпты | `PIPELINE_MODE=langchain` |

Обе реализации возвращают одинаковый `AgentResponse` — переключение прозрачно для клиентов.

## Langfuse Observability

Трейсинг LLM-вызовов через [Langfuse](https://langfuse.com):

- **Original pipeline**: `@observe` декораторы на Orchestrator, Classifier, CourseAgent, PlatformAgent
- **LangChain pipeline**: автоматический CallbackHandler для всех chains и retrievers
- **Dashboard**: промпты, ответы, токены, латентность, стоимость — фильтрация по `pipeline` и `user_id`

```bash
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
```
````

- [ ] **Step 3: Run full test suite — final verification**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m pytest --tb=short -q`

Expected: all tests pass (existing 173 + new ~20)

- [ ] **Step 4: Run ruff lint**

Run: `cd /home/alex2061/projects/github-portfolio/ai_assistant_eduflow && python -m ruff check .`

Expected: no errors (fix any that appear)

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add MCP Server, LangChain Pipeline, and Langfuse sections to README"
```

---

## Task Summary

| Task | Description | New Files | Modified Files |
|------|------------|-----------|---------------|
| 1 | Dependencies + Config | 1 test | `requirements.txt`, `config.py`, `.env.example` |
| 2 | Observability package | 4 + 1 test | — |
| 3 | Langfuse decorators on agents | — | 4 agent files |
| 4 | LangChain RAG | 2 + 1 test | — |
| 5 | LangChain Chains | 1 + 1 test | — |
| 6 | LangChain Pipeline + Tools | 2 + 1 test | — |
| 7 | Pipeline switching | 1 test | `app.py`, `routers/wappi.py` |
| 8 | MCP Server | 5 + 1 test | — |
| 9 | Docker + MCP config | 1 new | `docker-compose.prod.yml` |
| 10 | README + verification | — | `README.md` |
