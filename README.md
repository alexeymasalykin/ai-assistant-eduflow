# EduFlow AI Assistant

AI-ассистент для платформы онлайн-обучения EduFlow. Автоматически отвечает на вопросы студентов, предоставляет информацию о курсах, обрабатывает платежи, эскалирует сложные запросы к живым преподавателям.

**Версия:** 1.0.0 | **Статус:** Production-Ready | **License:** MIT

---

## Возможности

- Многоагентная система с классификацией запросов
- Поддержка OpenAI и YandexGPT (Protocol abstraction)
- RAG с ChromaDB для базы знаний (200+ статей)
- Интеграция с Bitrix24 CRM (статусы сделок, контакты, история)
- Webhook для Telegram/WhatsApp (через Wappi Direct)
- Структурированное логирование JSON (маскирование PII)
- Защита от prompt injection, XSS, SQL injection
- Асинхронная архитектура (FastAPI + asyncpg + asyncio)
- Docker + nginx + PostgreSQL 15
- GitHub Actions CI/CD (тесты, security, Docker build)

---

## Архитектура

```
Входящее сообщение (Telegram/WhatsApp)
    |
[Wappi Webhook] --> validation, deduplication, user mapping
    |
[Orchestrator] --> FAQ short-answer check
    |
[ClassifierAgent] --> rule-based + LLM classification
    |-- TypicalAgent      (~15%) --> greeting/thanks/confirmations
    |-- CourseAgent       (~50%) --> course info + deal status from Bitrix24
    |-- PlatformAgent     (~5%)  --> technical support (RAG knowledge base)
    \-- ESCALATE          (~30%) --> complex queries --> live instructor
    |
[Response] --> via Wappi API --> user
```

### Компоненты

| Компонент | Назначение |
|-----------|-----------|
| **Orchestrator** | Main message routing engine |
| **ClassifierAgent** | Message type detection (rule-based + LLM fallback) |
| **TypicalAgent** | FAQ templates, greetings, confirmations |
| **CourseAgent** | Course enrollment, payment status (Bitrix24) |
| **PlatformAgent** | Platform FAQ, technical help (RAG) |
| **LLMClient** | Protocol abstraction for OpenAI/YandexGPT |
| **VectorDB** | ChromaDB with OpenAI embeddings |
| **BitrixClient** | CRM integration (deals, contacts, stages) |
| **WappiIncomingHandler** | Webhook parsing + deduplication |
| **WappiOutgoingHandler** | Message sending via Wappi API |

---

## Требования

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (для продакшена)
- API ключи: OpenAI, YandexGPT (опционально), Wappi, Bitrix24

---

## Быстрый старт

### 1. Клонирование и подготовка

```bash
git clone https://github.com/your-org/ai_assistant_eduflow.git
cd ai_assistant_eduflow

python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate на Windows

pip install -r requirements.txt
```

### 2. Конфигурация

```bash
cp deployment/.env.example .env

# Отредактировать .env:
# - OPENAI_API_KEY или YANDEX_API_KEY (обязательно)
# - POSTGRES_DSN (по умолчанию: postgresql+asyncpg://postgres:postgres@localhost:5432/ai_assistant_eduflow)
# - WAPPI_API_TOKEN (для Telegram/WhatsApp)
# - BITRIX24_WEBHOOK_URL (для CRM интеграции)
```

### 3. База данных

```bash
createdb ai_assistant_eduflow
alembic upgrade head
```

### 4. Запуск

```bash
python -m uvicorn app:app --reload

# http://localhost:8000
# http://localhost:8000/docs   (Swagger UI)
# http://localhost:8000/health
```

### 5. Тесты

```bash
pytest tests/ -v
pytest tests/ --cov=. --cov-report=html
```

---

## Deployment (Docker)

```bash
docker-compose -f docker-compose.prod.yml up -d
curl http://localhost/health
```

### Сервисы

| Сервис | Порт | Назначение |
|--------|------|-----------|
| **webhook** | 8000 | FastAPI приложение |
| **db** | 5432 | PostgreSQL (внутренний) |
| **nginx** | 80, 443 | Reverse proxy + SSL |

---

## API Endpoints

### POST `/webhook/wappi` — Telegram/WhatsApp

```json
{
  "message_type": "text",
  "from": "+79991234567",
  "body": "Как начать изучать курс?",
  "message_id": "msg_abc123xyz",
  "timestamp": 1700000000,
  "chat_id": "1234567890"
}
```

### POST `/webhook/bitrix` — Bitrix24 CRM

События: `ONCRMDEALUPDATE`, `ONCRMDEALSTAGECHANGE`, `ONCRMLEADUPDATE`

### GET `/health`

```json
{"status": "ok", "database": "connected"}
```

### GET `/stats`

```json
{"total_messages": 1542, "total_escalations": 187}
```

---

## Безопасность

- **HMAC webhook validation** — timing-safe token comparison
- **Rate limiting** — 100 req/min per IP (slowapi)
- **Input sanitization** — XSS, SQL injection, null bytes
- **No stack trace leaks** — global exception handler
- **PII masking** — логирование без телефонов и user_id
- **Prompt injection protection** — security gates в system prompts
- **Strict typing** — pyright strict mode, zero `any`
- **Supply chain** — pip-audit + gitleaks в CI

### Переменные окружения

```bash
OPENAI_API_KEY=sk-...
YANDEX_API_KEY=...
BITRIX24_WEBHOOK_URL=https://...
WAPPI_API_TOKEN=...
POSTGRES_DSN=postgresql+asyncpg://...
```

---

## Тестирование

146 тестов, 100% pass rate, TDD подход.

```bash
pytest tests/                          # все
pytest tests/unit/ -v                  # unit
pytest tests/integration/ -v           # integration
pytest --cov=. --cov-report=term-missing  # coverage
```

---

## CI/CD

| Workflow | Триггер | Что делает |
|----------|---------|-----------|
| **test.yml** | Push/PR | pytest, coverage, pyright |
| **security.yml** | Push/PR | bandit, gitleaks, pip-audit |
| **docker-build.yml** | Push main | docker build + smoke test |

---

## Структура проекта

```
ai_assistant_eduflow/
├── agents/               # Multi-agent system
│   ├── orchestrator.py
│   ├── classifier.py
│   ├── typical_agent.py
│   ├── course_agent.py
│   └── platform_agent.py
├── integrations/         # External services
│   ├── llm_client.py
│   ├── bitrix_client.py
│   ├── vector_db.py
│   ├── database.py
│   ├── logging.py
│   └── wappi/
│       ├── incoming.py
│       ├── outgoing.py
│       └── templates.py
├── repositories/         # Database layer
│   ├── user_mapping.py
│   ├── dialog_log.py
│   └── analytics.py
├── routers/              # FastAPI routes
│   ├── wappi.py
│   ├── bitrix.py
│   └── admin.py
├── prompts/              # LLM prompts
├── utils/                # Sanitization, validation
├── tests/                # 146 tests
├── alembic/              # Database migrations
├── deployment/           # Docker, nginx, .env
├── app.py
├── config.py
├── Dockerfile
└── docker-compose.prod.yml
```

---

## Contributing

### Commit Convention

```
feat(agents): add TypicalAgent for greetings
fix(db): handle concurrent user mapping updates
refactor(orchestrator): simplify message routing
test(classifier): add edge case tests
chore(docker): update base image
```

### Workflow

1. `git checkout -b feature/my-feature`
2. Тесты первыми (TDD), код проходит все проверки
3. `pytest tests/ --cov=. && ruff check . && pyright .`
4. `git push origin feature/my-feature` + PR

---

## License

MIT
