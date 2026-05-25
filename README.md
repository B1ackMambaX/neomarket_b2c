# NeoMarket B2C — Backend

Бэкенд B2C-модуля платформы NeoMarket. Реализован на FastAPI с PostgreSQL, развёртывается через Docker Compose.

## Архитектура

Проект построен по принципу **слоистой архитектуры (Layered Architecture)** с элементами Domain-Driven Design. Зависимости направлены строго снизу вверх: внешние слои зависят от внутренних, но не наоборот.

```
┌─────────────────────────────────────┐
│         API Layer (app/api)         │  ← HTTP: роутеры, зависимости, middleware
├─────────────────────────────────────┤
│     Application Layer (app/services)│  ← Use-cases, оркестрация бизнес-логики
├─────────────────────────────────────┤
│      Domain Layer (app/domain)      │  ← Сущности, value objects, интерфейсы репозиториев
├─────────────────────────────────────┤
│  Infrastructure Layer               │  ← БД, внешние API, конкретные репозитории
│  (app/infrastructure)               │
└─────────────────────────────────────┘
```

## Структура проекта

```
neomarket_b2c/
├── app/
│   ├── api/                    # Слой представления (HTTP)
│   │   ├── v1/
│   │   │   ├── routers/        # Endpoint-роутеры по модулям
│   │   │   └── dependencies/   # FastAPI Depends (auth, pagination, и др.)
│   │   └── middleware/         # CORS, logging, error handling middleware
│   ├── services/               # Слой приложения: use-cases и бизнес-оркестрация
│   ├── domain/                 # Доменный слой
│   │   ├── entities/           # Доменные сущности (dataclasses / Pydantic BaseModel)
│   │   ├── repositories/       # Абстрактные интерфейсы репозиториев (ABC)
│   │   └── value_objects/      # Value objects (Email, Money, OrderStatus, и др.)
│   ├── infrastructure/         # Инфраструктурный слой
│   │   ├── database/
│   │   │   ├── models/         # SQLAlchemy ORM-модели
│   │   │   └── repositories/   # Конкретные реализации репозиториев
│   │   └── external/           # Клиенты внешних сервисов (платёжки, CRM, и др.)
│   ├── schemas/                # Pydantic-схемы запросов и ответов (DTO)
│   └── core/                   # Конфигурация, DI, утилиты
├── alembic/                    # Миграции базы данных
│   └── versions/
├── tests/
│   ├── unit/                   # Юнит-тесты (сервисы, domain)
│   ├── integration/            # Интеграционные тесты (репозитории + БД)
│   └── e2e/                    # End-to-end тесты (HTTP → БД)
├── docker/                     # Dockerfile-ы и вспомогательные конфиги
├── docker-compose.yml          # Полный стек (API + БД) — прод / CI
├── docker-compose.dev.yml      # Только инфраструктура (БД + pgadmin) — локальная разработка
├── Dockerfile
├── alembic.ini
├── pyproject.toml
└── requirements.txt
```

## Быстрый старт

### Локальная разработка (рекомендуется)

API запускается напрямую на хосте, в Docker — только БД. Горячая перезагрузка работает нативно.

```bash
# 1. Переменные окружения
cp .env.example .env          # DATABASE_URL уже настроен на localhost:5433

# 2. Поднять только инфраструктуру
docker compose -f docker-compose.dev.yml up -d

# 3. Виртуальное окружение и зависимости
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Применить миграции
alembic upgrade head

# 5. Запустить API
uvicorn app.main:app --reload

# Документация: http://localhost:8000/docs
# pgAdmin:       http://localhost:5050
```

### Полный стек в Docker

```bash
# Изменить DATABASE_URL в .env на: postgresql+asyncpg://postgres:postgres@db:5432/neomarket
docker compose up -d --build
docker compose exec api alembic upgrade head
# Документация: http://localhost:8000/docs
```

## Переменные окружения

| Переменная | Описание | Пример |
|---|---|---|
| `DATABASE_URL` | PostgreSQL DSN | `postgresql+asyncpg://postgres:postgres@localhost:5433/neomarket` |
| `SECRET_KEY` | JWT secret | `changeme` |
| `DEBUG` | Режим отладки | `false` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни JWT | `30` |

> CORS origins (`ALLOWED_ORIGINS`) задаются в коде — `app/core/config.py`. По умолчанию разрешены `localhost:3000` и `localhost:5173`.

## Стек

- **FastAPI** — HTTP-фреймворк
- **SQLAlchemy 2.x (async)** — ORM
- **Alembic** — миграции
- **PostgreSQL 16** — основная БД
- **Docker / Docker Compose** — развёртывание
- **pytest + httpx** — тесты

## Правила разработки

1. Доменный слой **не знает** ни про HTTP, ни про ORM, ни про конкретную БД.
2. Сервисы **не знают** про SQLAlchemy — работают только через интерфейсы репозиториев.
3. Все внешние зависимости (БД, Redis, внешние API) инициализируются в `app/core/` и прокидываются через FastAPI `Depends`.
4. Схемы (DTO) живут в `app/schemas/` и **не используются** внутри domain/services — только на границе API.
