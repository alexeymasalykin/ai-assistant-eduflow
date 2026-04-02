# EduFlow AI Assistant

AI-ассистент для платформы онлайн-обучения EduFlow. Автоматически отвечает на вопросы студентов, предоставляет информацию о курсах, обрабатывает платежи, эскалирует сложные запросы к живым преподавателям.

![Tests](https://github.com/alex2061/ai_assistant_eduflow/actions/workflows/test.yml/badge.svg)
![Coverage](https://codecov.io/gh/alex2061/ai_assistant_eduflow/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**170 тестов** | **84% coverage** | **Production-Ready**

---

## Возможности

- Многоагентная система с классификацией запросов
- Поддержка OpenAI и YandexGPT (Protocol abstraction)
- RAG с ChromaDB для базы знаний (200+ статей)
- Интеграция с Bitrix24 CRM (статусы сделок, контакты, история)
- Мультиканальность: Telegram + MAX Messenger (через Wappi, различение по profile_id)
- Структурированное логирование JSON (маскирование PII)
- Защита от prompt injection, XSS, SQL injection
- Асинхронная архитектура (FastAPI + asyncpg + asyncio)
- Docker + nginx + PostgreSQL 15
- GitHub Actions CI/CD (тесты, security, Docker build)

---

## Архитектура

```mermaid
flowchart TD
    A["Входящее сообщение\n(Telegram / MAX Messenger)"] --> B["Wappi Webhook\nchannel detection, validation,\ndeduplication, user mapping"]
    B --> C["Orchestrator\nFAQ short-answer check"]
    C --> D["ClassifierAgent\nrule-based + LLM classification"]

    D -->|"~15%"| E["TypicalAgent\ngreeting / thanks / confirmations"]
    D -->|"~50%"| F["CourseAgent\ncourse info + deal status\nfrom Bitrix24"]
    D -->|"~5%"| G["PlatformAgent\ntechnical support\nRAG knowledge base"]
    D -->|"~30%"| H["ESCALATE\ncomplex queries\nlive instructor"]

    E --> I["Response via Wappi API"]
    F --> I
    G --> I
    H --> I
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

170 тестов, 84% coverage, TDD подход.

```bash
pytest tests/                          # все
pytest tests/unit/ -v                  # unit
pytest tests/integration/ -v           # integration
pytest tests/e2e/ -v                   # e2e (full pipeline)
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
├── tests/                # 170 tests (unit + integration + e2e)
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
