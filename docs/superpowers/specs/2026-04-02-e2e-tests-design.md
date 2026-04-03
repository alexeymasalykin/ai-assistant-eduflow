# E2E Tests Design

## Goal

End-to-end tests that verify the full message pipeline: HTTP request on webhook -> internal routing -> agent processing -> outgoing response. External HTTP APIs mocked with `respx`, internal logic runs for real.

## Approach

- **Variant A**: mock only external HTTP APIs (OpenAI, Bitrix24, Wappi), everything internal is real
- **User scenario-based**: each test tells a story ("student asks about a course")
- **No real DB**: asyncpg mocked, PostgreSQL already tested in CI via services

## File Structure

```
tests/e2e/
  __init__.py
  conftest.py              # Fixtures: app with respx mocks, payloads, auth headers
  test_student_flows.py    # Happy path scenarios (5 tests)
  test_error_flows.py      # Negative scenarios (4 tests)
```

## Mock Layer

| External Service   | Mock Tool              | Returns                                        |
|--------------------|------------------------|------------------------------------------------|
| OpenAI (classifier)| `respx`                | `"course"`, `"platform"`, `"escalate"` per test|
| OpenAI (agent LLM) | `respx`                | Realistic Russian response text                |
| Bitrix24 API       | `respx`                | Deal JSON with appropriate `STAGE_ID`          |
| Wappi send API     | `respx`                | `{"status": "ok"}`, assert called with body    |
| PostgreSQL         | `AsyncMock`            | user_mapping, dialog_log stubs                 |
| ChromaDB           | `unittest.mock.patch`  | Return 3 knowledge base documents              |

## Fixture: `e2e_client` (conftest.py)

1. Create real `Orchestrator` with real `ClassifierAgent`, `TypicalAgent`, `CourseAgent`, `PlatformAgent`
2. Inject mock dependencies into agents:
   - `LLMClient` — real class but `respx` intercepts outgoing HTTP to OpenAI
   - `BitrixClient` — real class but `respx` intercepts outgoing HTTP to Bitrix24
   - `VectorDB` — mocked via `unittest.mock.patch` (ChromaDB is local, not HTTP)
3. Override FastAPI dependencies via `app.dependency_overrides`:
   - `get_database` -> AsyncMock with pool stub
   - `get_orchestrator` -> real orchestrator from step 1
   - `get_wappi_incoming` -> real `WappiIncomingHandler` with mocked DB pool + mocked bitrix
   - `get_wappi_outgoing` -> real `WappiOutgoingHandler` with `respx` intercepting Wappi API
   - `get_bitrix_client` -> real `BitrixClient` with `respx` intercepting Bitrix API
4. `httpx.AsyncClient(transport=ASGITransport(app=app))` as test client
5. Auth header: `X-Wappi-Token: test-token-123` matching `WAPPI_WEBHOOK_TOKEN` env var

## Test Scenarios

### test_student_flows.py — Happy Path

#### 1. test_greeting_returns_faq_response

- **Input**: POST `/webhook/wappi` with body `"Привет!"`
- **Path**: Wappi webhook -> Orchestrator -> TypicalAgent (pattern match) -> FAQ template -> Wappi send
- **Asserts**:
  - HTTP 200 with `{"status": "ok"}`
  - Wappi send API called once
  - Wappi send body contains FAQ greeting text
  - No LLM calls made (rule-based, no classification needed)

#### 2. test_course_question_uses_bitrix_and_llm

- **Input**: POST `/webhook/wappi` with body `"Сколько стоит курс Python?"`
- **respx setup**:
  - OpenAI classifier returns `"course"`
  - Bitrix `crm.deal.get` returns deal with `STAGE_ID: "CONSULTATION"`
  - OpenAI agent LLM returns `"Курс Python стоит 15 000 руб..."`
  - Wappi send returns ok
- **Path**: -> ClassifierAgent (LLM) -> CourseAgent -> Bitrix deal context + LLM -> Wappi send
- **Asserts**:
  - HTTP 200
  - OpenAI called twice (classifier + agent)
  - Bitrix API called (get_deal)
  - Wappi send called with response text
  - Response contains course-related content

#### 3. test_platform_question_uses_rag_and_llm

- **Input**: POST `/webhook/wappi` with body `"Не могу войти в личный кабинет"`
- **respx setup**:
  - OpenAI classifier returns `"platform"`
  - VectorDB.search returns 3 knowledge base docs (mocked)
  - OpenAI agent LLM returns `"Для входа в личный кабинет..."`
  - Wappi send returns ok
- **Path**: -> ClassifierAgent (LLM) -> PlatformAgent -> RAG + LLM -> Wappi send
- **Asserts**:
  - HTTP 200
  - VectorDB.search called with user message
  - OpenAI called twice (classifier + agent)
  - Wappi send called with response text

#### 4. test_escalation_does_not_send_message

- **Input**: POST `/webhook/wappi` with body `"Хочу вернуть деньги за курс"`
- **respx setup**:
  - OpenAI classifier returns `"escalate"`
- **Path**: -> ClassifierAgent (LLM) -> ESCALATE -> no outgoing message
- **Asserts**:
  - HTTP 200
  - Wappi send API **NOT** called
  - OpenAI called once (classifier only)

#### 5. test_confirmation_is_silent

- **Input**: POST `/webhook/wappi` with body `"Ок"`
- **Path**: -> Orchestrator -> TypicalAgent (pattern match, confirmation) -> silent
- **Asserts**:
  - HTTP 200
  - Wappi send API **NOT** called
  - No LLM calls (rule-based)

### test_error_flows.py — Negative Scenarios

#### 6. test_invalid_payload_returns_error

- **Input**: POST `/webhook/wappi` with `{"message_type": "text"}` (missing required fields)
- **Asserts**:
  - HTTP 400 or 422
  - Wappi send **NOT** called
  - No LLM calls

#### 7. test_duplicate_message_processed_once

- **Input**: POST `/webhook/wappi` twice with same `message_id`
- **Asserts**:
  - First request: 200, Wappi send called
  - Second request: 200, Wappi send **NOT** called again
  - LLM called only once

#### 8. test_per_chat_rate_limit

- **Input**: 11 POST `/webhook/wappi` requests from same `chat_id`
- **Asserts**:
  - First 10: HTTP 200
  - 11th: HTTP 429

#### 9. test_llm_timeout_graceful_fallback

- **Input**: POST `/webhook/wappi` with body `"Расскажи про курс"`
- **respx setup**:
  - OpenAI classifier returns `"course"`
  - OpenAI agent LLM raises `httpx.ConnectTimeout`
- **Asserts**:
  - HTTP 200 (no crash)
  - Response is graceful fallback or escalation
  - No stack trace in response body

## Dependencies

- `respx==0.21.1` — already in requirements.txt
- `httpx` — already in requirements.txt (used by FastAPI TestClient)
- `pytest-asyncio` — already in requirements.txt

## pytest marker

```python
# pytest.ini
markers =
    e2e: end-to-end tests
```

## Run

```bash
pytest tests/e2e/ -v              # E2E only
pytest tests/ -v                  # all tests
pytest tests/e2e/ -v -m e2e      # explicit marker
```
