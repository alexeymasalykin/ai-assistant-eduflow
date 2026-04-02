# EduFlow AI Assistant

AI-ассистент для платформы онлайн-обучения EduFlow. Автоматически отвечает на вопросы студентов, предоставляет информацию о курсах, обрабатывает платежи, эскалирует сложные запросы к живым преподавателям.

**Версия:** 1.0.0 | **Статус:** Production-Ready | **License:** MIT

---

## 🎯 Возможности

- ✅ Многоагентная система с классификацией запросов
- ✅ Поддержка OpenAI и YandexGPT (с абстракцией protokol)
- ✅ RAG с ChromaDB для базы знаний (200+ статей)
- ✅ Интеграция с Bitrix24 CRM (статусы сделок, контакты, история)
- ✅ Webhook для Telegram/WhatsApp (через Wappi Direct)
- ✅ Структурированное логирование JSON (маскирование PII)
- ✅ Защита от prompt injection + XSS + SQL injection
- ✅ Асинхронная архитектура (FastAPI + asyncpg + asyncio)
- ✅ Docker + nginx + PostgreSQL 15
- ✅ GitHub Actions CI/CD (тесты, security, Docker build)

---

## 🏗️ Архитектура

```
Входящее сообщение (Telegram/WhatsApp)
    ↓
[Wappi Webhook] → validation, deduplication, user mapping
    ↓
[Orchestrator] → FAQ short-answer check
    ↓
[ClassifierAgent] → rule-based + LLM classification
    ├─ TypicalAgent      (~15%) → greeting/thanks/confirmations
    ├─ CourseAgent       (~50%) → course info + deal status from Bitrix24
    ├─ PlatformAgent     (~5%)  → technical support (RAG knowledge base)
    └─ ESCALATE          (~30%) → complex queries → live instructor
    ↓
[Response] → via Wappi API → user
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

## 📋 Требования

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (для продакшена)
- API ключи: OpenAI, YandexGPT (опционально), Wappi, Bitrix24

---

## 🚀 Быстрый старт (локальная разработка)

### 1. Клонирование и подготовка

```bash
git clone https://github.com/your-org/ai_assistant_eduflow.git
cd ai_assistant_eduflow

# Virtual environment
python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate на Windows

# Зависимости
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
# Скопировать шаблон
cp deployment/.env.example .env

# Отредактировать .env:
# - OPENAI_API_KEY или YANDEX_API_KEY (обязательно)
# - POSTGRES_DSN (по умолчанию: postgresql+asyncpg://postgres:postgres@localhost:5432/ai_assistant_eduflow)
# - WAPPI_API_TOKEN (для Telegram/WhatsApp)
# - BITRIX24_WEBHOOK_URL (для CRM интеграции)
```

### 3. База данных

```bash
# PostgreSQL локально
createdb ai_assistant_eduflow

# Миграции
alembic upgrade head
```

### 4. Запуск

```bash
# Разработка (hot reload)
python -m uvicorn app:app --reload

# Доступно на http://localhost:8000
# Swagger UI: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

### 5. Тестирование

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ --cov=. --cov-report=html

# Только unit тесты
pytest tests/unit/ -v

# Только интеграционные
pytest tests/integration/ -v
```

---

## 🐳 Deployment (Docker)

### Production с Docker Compose

```bash
# Переименовать .env
mv .env .env.prod

# Запуск
docker-compose -f docker-compose.prod.yml up -d

# Проверка
curl http://localhost/health

# Логи
docker-compose -f docker-compose.prod.yml logs -f webhook

# Остановка
docker-compose -f docker-compose.prod.yml down
```

### Сервисы

| Сервис | Порт | Назначение |
|--------|------|-----------|
| **webhook** | 8000 | FastAPI приложение |
| **db** | 5432 | PostgreSQL (внутренний) |
| **nginx** | 80, 443 | Reverse proxy + SSL |

### Конфигурация SSL (Let's Encrypt)

```bash
# Сертификаты автоматически обновляются через certbot
# Путь: ./data/certbot/conf/
```

---

## 🔗 API Endpoints

### Webhook для Telegram/WhatsApp

**POST** `/webhook/wappi`

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

**Response:**
```json
{
  "success": true,
  "message_id": "msg_abc123xyz"
}
```

### Webhook для Bitrix24

**POST** `/webhook/bitrix`

Обработка событий:
- `ONCRMDEALUPDATE` — изменение сделки
- `ONCRMDEALSTAGECHANGE` — смена стадии
- `ONCRMLEADUPDATE` — обновление контакта

### Мониторинг

**GET** `/health`
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2025-04-02T10:30:00Z"
}
```

**GET** `/stats`
```json
{
  "total_messages": 1542,
  "total_escalations": 187,
  "today_messages": 42,
  "today_escalations": 5
}
```

---

## 🛡️ Безопасность

### Реализованные меры

- ✅ **HMAC webhook validation** — timing-safe token comparison
- ✅ **Rate limiting** — 100 req/min per IP (slowapi)
- ✅ **Input sanitization** — XSS, SQL injection, null bytes
- ✅ **No stack trace leaks** — global exception handler
- ✅ **PII masking** — логирование без номеров телефонов, user_id
- ✅ **Prompt injection protection** — security gates в prompts
- ✅ **Strict typing** — mypy/pyright (не используем `any`)
- ✅ **Supply chain** — pip-audit в CI

### Переменные окружения (секреты)

```bash
# .env должен быть в .gitignore
OPENAI_API_KEY=sk-...
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
BITRIX24_WEBHOOK_URL=https://...
WAPPI_API_TOKEN=...
POSTGRES_DSN=postgresql+asyncpg://...
```

---

## 📊 Тестирование

### Статистика

- **146 тестов** (unit + integration)
- **100% pass rate** ✅
- **TDD подход** (тесты пишутся перед кодом)

### Запуск

```bash
# Все тесты
pytest tests/

# С маркерами
pytest -m unit      # только unit
pytest -m integration  # только интеграция

# С покрытием
pytest --cov=. --cov-report=term-missing

# Быстро (без медленных тестов)
pytest -m "not slow"
```

### Структура тестов

```
tests/
├── conftest.py              # Общие fixtures
├── unit/
│   ├── test_agents/         # Тесты агентов
│   ├── test_integrations/   # LLM, Bitrix, VectorDB
│   └── test_repositories/   # Database queries
├── integration/
│   ├── test_fastapi_routers.py    # Webhook endpoints
│   ├── test_wappi_integration.py  # Full message flow
│   └── test_migrations.py         # Database migrations
└── database/
    └── test_migrations.py   # Alembic migrations
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions

| Workflow | Триггер | Что делает |
|----------|---------|-----------|
| **test.yml** | Push/PR | pytest, coverage, pyright |
| **security.yml** | Push/PR | bandit, gitleaks, pip-audit |
| **docker-build.yml** | Push main | docker build, docker-compose test |

### Локальные проверки перед push

```bash
# Линтинг
ruff check .

# Типизация
pyright .

# Тесты
pytest tests/ --cov=.

# Security
bandit -r . --quiet
pip-audit
```

---

## 📝 Contributing

### Commit Convention

```
feat(agents): add new TypicalAgent for greetings
fix(db): handle concurrent user mapping updates
refactor(orchestrator): simplify message routing
docs(readme): clarify webhook structure
test(classifier): add edge case tests
chore(docker): update Python base image
```

**Types:**
- `feat` — новая фича
- `fix` — баг фикс
- `refactor` — рефакторинг (без изменения функциональности)
- `docs` — документация
- `test` — добавление/обновление тестов
- `chore` — техническое обслуживание

**Scopes:**
- agents, db, api, docker, ci, config, etc.

### Workflow

1. **Create branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Разработка:**
   - Тесты первыми (TDD)
   - Код должен проходить все проверки
   - Commit часто небольшими порциями

3. **Перед push:**
   ```bash
   pytest tests/ --cov=.
   ruff check .
   pyright .
   ```

4. **Push и PR:**
   ```bash
   git push origin feature/my-feature
   # Создать PR на GitHub
   ```

5. **Review:**
   - GitHub Actions автоматически проверит
   - Code review от team
   - Merge в main после approval

---

## 📚 Дополнительно

### Структура проекта

```
ai_assistant_eduflow/
├── agents/               # Multi-agent system
│   ├── orchestrator.py
│   ├── classifier.py
│   ├── typical_agent.py
│   ├── course_agent.py
│   └── platform_agent.py
├── integrations/         # External services
│   ├── llm_client.py     # OpenAI/YandexGPT abstraction
│   ├── bitrix_client.py
│   ├── vector_db.py
│   ├── database.py
│   ├── wappi/
│   │   ├── incoming.py
│   │   ├── outgoing.py
│   │   └── templates.py
│   └── logging.py        # Structured logging
├── repositories/         # Database layer
│   ├── user_mapping.py
│   ├── dialog_log.py
│   └── analytics.py
├── routers/             # FastAPI routes
│   ├── wappi.py
│   ├── bitrix.py
│   └── admin.py
├── prompts/             # LLM prompts
│   ├── classifier.py
│   ├── course_agent.py
│   ├── platform_agent.py
│   └── faq_templates.py
├── utils/               # Utilities
│   ├── sanitize.py
│   └── validators.py
├── tests/               # Test suite
├── deployment/          # Docker, nginx, .env
├── alembic/             # Database migrations
├── app.py               # FastAPI application
├── config.py            # Configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.prod.yml
└── README.md
```

### Полезные команды

```bash
# Миграции
alembic current           # Текущая версия
alembic upgrade head      # Применить все миграции
alembic downgrade base    # Откатить всё

# PostgreSQL (если локально)
psql -U postgres -d ai_assistant_eduflow
\dt                       # Список таблиц
\d user_mappings          # Структура таблицы

# Docker
docker-compose -f docker-compose.prod.yml logs -f webhook
docker exec -it <container> bash
docker-compose -f docker-compose.prod.yml down -v  # С удалением volumes
```

---

## 🤝 Support

Вопросы? Откройте Issue на GitHub или свяжитесь с team.

---

**Made with ❤️ for EduFlow learning platform**
