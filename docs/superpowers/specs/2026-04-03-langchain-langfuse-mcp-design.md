# Design: LangChain + Langfuse + MCP Integration

**Date:** 2026-04-03
**Status:** Approved
**Goal:** Усилить проект для резюме AI/LLM Engineer — интегрировать LangChain, Langfuse, MCP

---

## Context

EduFlow AI Assistant — мультиагентный AI-ассистент с RAG (ChromaDB + OpenAI embeddings), оркестратором (router pattern) и интеграцией с Bitrix24 CRM. Текущая реализация: ~1,620 строк Python, 173 теста (19 файлов), 84% покрытие.

Задача — добавить три технологии, востребованные в вакансиях AI/LLM Engineer:
1. **LangChain** — параллельная реализация RAG + агентов
2. **Langfuse** — observability для LLM-вызовов обоих пайплайнов
3. **MCP** — сервер с инструментами для Knowledge Base и CRM

## Approach

**Подход 1: Отдельный пакет** — весь LangChain-код в новом пакете `langchain_pipeline/`, MCP-сервер в `mcp_server/`, observability в `observability/`. Оригинальный код не меняется (кроме Langfuse декораторов и одной строки в роутере).

Выбран за наглядность: рекрутер/техлид видит чёткую структуру на GitHub. Дублирование бизнес-логики — осознанное решение, демонстрирующее умение реализовать один пайплайн двумя способами.

## Architecture Decision Records

### ADR-1: Переиспользование BitrixClient вместо LangChain-обёртки

**Решение:** `CourseChain` (LangChain) использует существующий `BitrixClient` напрямую, без обёртки в LangChain Tool или BaseTool.

**Обоснование:** LangChain используется там, где он добавляет ценность — RAG (Retriever, VectorStore, text splitting) и chains (prompt templates, LLM orchestration). Оборачивать работающий HTTP-клиент Bitrix24 в LangChain абстракцию — overhead без пользы. `BitrixClient` уже имеет чистый async-интерфейс, протестирован и используется в нескольких местах.

**Это же относится к:** `sanitize()`, `TypicalAgent`, `AgentResponse`, промптам из `prompts/`.

### ADR-2: Параллельные пайплайны вместо замены

**Решение:** Оригинальный и LangChain пайплайны существуют параллельно, переключение через `PIPELINE_MODE` env.

**Обоснование:** Оригинальный код работает в продакшене. Параллельная реализация позволяет: (a) не ломать существующую функциональность, (b) демонстрировать владение LangChain, (c) сравнивать метрики через Langfuse.

### ADR-3: MCP-сервер как отдельный процесс

**Решение:** MCP-сервер запускается отдельно от FastAPI, а не встраивается в существующее приложение.

**Обоснование:** MCP работает по stdio/SSE, не по HTTP REST. Отдельный процесс = отдельный сервис в Docker Compose, подключаемый из Claude Code, Cursor или любого MCP-клиента независимо.

---

## File Structure

### New Packages

```
langchain_pipeline/          # LangChain-реализация RAG + агентов
  ├── __init__.py
  ├── rag.py                 # LangChain VectorStore + Retriever (ChromaDB)
  ├── chains.py              # CourseChain, PlatformChain (RetrievalQA)
  ├── tools.py               # LangChain Tools (classify, search_kb)
  └── pipeline.py            # Точка входа: process(message, deal_id) → AgentResponse

observability/               # Langfuse для обоих пайплайнов
  ├── __init__.py
  ├── config.py              # Langfuse client init, env-based on/off
  ├── decorators.py          # @observe_if_enabled — no-op если выключено
  └── langchain_handler.py   # CallbackHandler для LangChain пайплайна

mcp_server/                  # MCP-сервер (отдельный процесс)
  ├── __init__.py
  ├── server.py              # FastMCP app, регистрация tools
  ├── tools_kb.py            # Tool: search_knowledge_base(query) → results
  └── tools_crm.py           # Tools: get_deal(id), find_deals_by_phone(phone)
```

### Modified Files (minimal)

| File | Change |
|------|--------|
| `config.py` | Add `pipeline_mode`, `langfuse_*` settings |
| `app.py` | Pipeline factory in lifespan, DI for selected pipeline |
| `agents/orchestrator.py` | `@observe_if_enabled` decorators (logic unchanged) |
| `agents/classifier.py` | `@observe_if_enabled` decorator |
| `agents/course_agent.py` | `@observe_if_enabled` decorator |
| `agents/platform_agent.py` | `@observe_if_enabled` decorator |
| `routers/wappi.py` | One line: `orchestrator.process()` → `pipeline.process()` |
| `requirements.txt` | Add langchain, langfuse, mcp dependencies |
| `docker-compose.prod.yml` | Add mcp-server service |
| `.env.example` | New variables |
| `README.md` | MCP Server section with quick-start and usage example |

### Untouched

All contents of `integrations/`, `prompts/`, `repositories/`, `utils/`, `routers/bitrix.py`, `routers/admin.py` — remain as-is.

---

## Section 1: LangChain Pipeline

### `langchain_pipeline/rag.py`

Replaces logic of `integrations/vector_db.py` but uses the same ChromaDB and embeddings:

- **VectorStore:** `langchain_chroma.Chroma` with `persist_directory="data/chroma_db"`, collection `eduflow_knowledge`
- **Embeddings:** `langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")`
- **Text Splitter:** `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)` — mirrors current chunking logic
- **Retriever:** `vectorstore.as_retriever(search_kwargs={"k": 3})` — top-3, same as current

Method `index_knowledge_base()` loads `.md` files via `DirectoryLoader` + `TextLoader`, splits, indexes. Analog of current `VectorDB.index_knowledge_base()`. `TextLoader` chosen over `UnstructuredMarkdownLoader` to avoid heavy `unstructured` dependency — markdown files are simple and don't need structural parsing.

### `langchain_pipeline/chains.py`

Two chains mirroring `course_agent.py` and `platform_agent.py`:

**PlatformChain:**
- `RetrievalQA.from_chain_type(llm, retriever, chain_type="stuff")`
- System prompt from `prompts/platform_agent.py` — same prompts
- RAG context injected automatically via retriever

**CourseChain:**
- `LLMChain(llm, prompt_template)` with `{deal_context}` placeholder
- Fetches deal from `BitrixClient` (reused, see ADR-1)
- Terminal stage escalation logic — same as original

### `langchain_pipeline/tools.py`

```python
classify_tool = Tool(
    name="classify_message",
    description="Classify student message into: course, platform, escalate",
    func=classifier_chain.invoke,
)

search_kb_tool = Tool(
    name="search_knowledge_base",
    description="Search EduFlow knowledge base for platform questions",
    func=retriever.invoke,
)
```

Tools are defined for concept demonstration. Chains are called directly from pipeline.

### `langchain_pipeline/pipeline.py`

```python
class LangChainPipeline:
    def __init__(self, llm, retriever, bitrix_client, langfuse_handler):
        ...

    async def process(self, message: str, deal_id: int | None) -> AgentResponse:
        # 1. Sanitize (reuse utils/sanitize.py)
        # 2. Try TypicalAgent (reuse agents/typical_agent.py)
        # 3. Classify via LLMChain
        # 4. Route: PlatformChain | CourseChain | escalate
        # 5. Return AgentResponse (same dataclass)
```

**Key:** `LangChainPipeline.process()` returns the same `AgentResponse` as `Orchestrator.process()`. Same contract — router just delegates.

### Reused Components

| Component | Source | Why reuse |
|-----------|--------|-----------|
| `TypicalAgent` | `agents/typical_agent.py` | FAQ/greeting logic — no LangChain value |
| `BitrixClient` | `integrations/bitrix_client.py` | CRM client — see ADR-1 |
| `sanitize()` | `utils/sanitize.py` | Security — single source of truth |
| `AgentResponse` | `agents/types.py` | Unified response contract |
| Prompts | `prompts/*.py` | Same system prompts |

### Dependencies

```
langchain>=0.3
langchain-openai>=0.3
langchain-chroma>=0.2
```

---

## Section 2: Langfuse Observability

### `observability/config.py`

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)
```

If `LANGFUSE_ENABLED=false` — all decorators and handlers become no-op. Zero overhead for local dev and tests.

### `observability/langchain_handler.py` — Auto-tracing for LangChain

```python
from langfuse.callback import CallbackHandler

def get_langfuse_handler(trace_name: str) -> CallbackHandler | None:
    if not settings.langfuse_enabled:
        return None
    return CallbackHandler(
        trace_name=trace_name,
        metadata={"pipeline": "langchain"},
    )
```

Connected in LangChain pipeline:
```python
chain.invoke(input, config={"callbacks": [langfuse_handler]})
```

**Auto-captured:** every LLM call (prompt, completion, tokens, latency), retrieval (query, results, scores), chain execution (input/output per step).

### `observability/decorators.py` — Manual tracing for original pipeline

```python
from langfuse.decorators import observe, langfuse_context

def observe_if_enabled(name: str):
    """Decorator: @observe if Langfuse enabled, no-op otherwise."""
    ...
```

Decorators added to 4 points in original pipeline:

| Point | What is traced |
|-------|---------------|
| `Orchestrator.process()` | Full request trace (root span) |
| `ClassifierAgent.classify()` | LLM classification call (prompt, result, tokens) |
| `CourseAgent.process()` | LLM call + deal context |
| `PlatformAgent.process()` | RAG search + LLM call |

Decorators wrap existing methods without changing signatures or logic.

### Langfuse Dashboard Capabilities

- **Traces:** each student request — full path from input to response
- **Generations:** every LLM call with prompt/completion/tokens/cost/latency
- **Filter by `pipeline`:** compare `original` vs `langchain` metrics
- **Filter by `user_id`:** all interactions for a specific deal

### New Environment Variables

```bash
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Dependencies

```
langfuse>=2.0
```

---

## Section 3: MCP Server

### `mcp_server/server.py`

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="eduflow-assistant",
    description="EduFlow AI Assistant — knowledge base search and CRM access",
)
```

Launch: `python -m mcp_server.server` (stdio) or via SSE for network access.

### `mcp_server/tools_kb.py` — Knowledge Base Tool

```python
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
    results = await vector_db.search(query, n_results=n_results)
    return format_results(results)
```

### `mcp_server/tools_crm.py` — CRM Tools

```python
@mcp.tool()
async def get_deal(deal_id: int) -> str:
    """Get student deal information from Bitrix24 CRM."""
    deal = await bitrix_client.get_deal(deal_id)
    return format_deal(deal)

@mcp.tool()
async def find_deals_by_phone(phone: str) -> str:
    """Find student deals in Bitrix24 CRM by phone number."""
    deals = await bitrix_client.find_deals_by_phone(phone)
    return format_deals_list(deals)
```

### Reused Components (see ADR-1)

| Component | Source |
|-----------|--------|
| `VectorDB` | `integrations/vector_db.py` |
| `BitrixClient` | `integrations/bitrix_client.py` |
| `Settings` | `config.py` |

### Docker Compose

```yaml
mcp-server:
  build:
    context: .
    dockerfile: Dockerfile
  command: ["python", "-m", "mcp_server.server", "--transport", "sse"]
  ports:
    - "8001:8001"
  env_file: .env
  depends_on:
    - db
```

### MCP Client Configuration

`.mcp.json` in project root for Claude Code / Cursor auto-discovery:

```json
{
  "mcpServers": {
    "eduflow": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": { "DOTENV_PATH": ".env" }
    }
  }
}
```

### Dependencies

```
mcp[cli]>=1.0
```

---

## Section 4: Pipeline Switching

### `config.py`

```python
class PipelineMode(str, Enum):
    ORIGINAL = "original"
    LANGCHAIN = "langchain"

class Settings(BaseSettings):
    # ... existing ...
    pipeline_mode: PipelineMode = PipelineMode.ORIGINAL
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
```

Default: `original` pipeline, Langfuse disabled. Zero breakage for current deployments.

### `app.py` — Factory in lifespan

```python
async def lifespan(app: FastAPI):
    # ... existing init (db, vector_db, bitrix_client) ...

    if settings.pipeline_mode == PipelineMode.LANGCHAIN:
        from langchain_pipeline.pipeline import LangChainPipeline
        pipeline = LangChainPipeline(
            retriever=build_retriever(settings),
            bitrix_client=bitrix_client,
            langfuse_handler=get_langfuse_handler("langchain"),
        )
    else:
        pipeline = orchestrator

    app.state.pipeline = pipeline
```

### `routers/wappi.py` — Single line change

```python
# Before:
response = await orchestrator.process(message, deal_id)

# After:
pipeline = request.app.state.pipeline
response = await pipeline.process(message, deal_id)
```

### Pipeline Contract

Both pipelines guarantee:
```python
async def process(self, message: str, deal_id: int | None) -> AgentResponse
```

`AgentResponse` — same frozen dataclass from `agents/types.py`.

---

## Section 5: Testing Strategy

- **Existing 173 tests pass unchanged** (pipeline_mode=original by default)
- **New unit tests for `langchain_pipeline/`:** chains, retriever, pipeline routing
- **New unit tests for `mcp_server/`:** tool invocation, error handling, response formatting
- **Langfuse tests:** mock callback handler, verify traces are created
- **Integration test:** pipeline switching via env, both modes return valid `AgentResponse`

---

## Section 6: README Updates

### MCP Server Section (in README.md)

Must include:
1. What the MCP server provides (2 sentences)
2. Quick-start: how to run locally (`python -m mcp_server.server`)
3. Claude Code config: `.mcp.json` contents
4. Usage example: sample MCP tool call and response
5. Docker: `docker compose up mcp-server`

---

## New Environment Variables Summary

```bash
# Pipeline mode: "original" or "langchain"
PIPELINE_MODE=original

# Langfuse observability (optional)
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## New Dependencies Summary

```
# LangChain
langchain>=0.3
langchain-openai>=0.3
langchain-chroma>=0.2

# Observability
langfuse>=2.0

# MCP
mcp[cli]>=1.0
```

## Impact Summary

| Category | New Files | Modified Files |
|----------|-----------|---------------|
| LangChain Pipeline | 5 in `langchain_pipeline/` | — |
| Langfuse | 3 in `observability/` | `orchestrator.py`, agents (decorators) |
| MCP Server | 4 in `mcp_server/` | `docker-compose.prod.yml` |
| Integration | — | `config.py`, `app.py`, `routers/wappi.py` |
| Documentation | — | `README.md`, `.env.example` |
| Tests | ~8-10 new test files | — |

**Original code:** logic unchanged, only `@observe_if_enabled` decorators added and one line in wappi router.
