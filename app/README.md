# app/

Корневой пакет приложения. Точка входа — `app/main.py`, где создаётся экземпляр FastAPI, регистрируются роутеры и middleware.

## Что здесь находится

| Файл / директория | Назначение |
|---|---|
| `main.py` | Создание `FastAPI()`, подключение роутеров, lifespan-хуки (startup/shutdown) |
| `api/` | Слой представления: HTTP-роутеры, зависимости, middleware |
| `services/` | Слой приложения: use-cases, оркестрация бизнес-логики |
| `domain/` | Доменный слой: сущности, value objects, интерфейсы репозиториев |
| `infrastructure/` | Инфраструктурный слой: ORM-модели, конкретные репозитории, внешние клиенты |
| `schemas/` | Pydantic DTO: схемы запросов и ответов |
| `core/` | Конфиг, DI-контейнер, общие утилиты |

## Правило зависимостей

```
api → services → domain ← infrastructure
```

- `api` вызывает `services`
- `services` вызывают интерфейсы из `domain`
- `infrastructure` реализует интерфейсы `domain`
- `domain` не импортирует ничего из других слоёв

## Типичный файл main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.routers import orders, companies, users
from app.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown
    await engine.dispose()

app = FastAPI(title="NeoMarket B2C", lifespan=lifespan)
app.include_router(orders.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
```
