# app/core/

Конфигурация приложения, инфраструктурные синглтоны и общие утилиты. Этот пакет не принадлежит ни одному бизнес-слою — он обслуживает всех.

## Что сюда попадает

| Файл | Назначение |
|---|---|
| `config.py` | `Settings` (pydantic-settings) — все переменные окружения |
| `database.py` | Создание async engine и `AsyncSessionFactory` |
| `security.py` | JWT: генерация и декодирование токенов, хэширование паролей |
| `dependencies.py` | Провайдеры сервисов через `Depends` (сборка репозиториев + сервисов) |
| `logging.py` | Настройка structlog / logging |
| `exceptions.py` | Базовые исключения приложения (не доменные) |

## Пример config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    DADATA_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

## Пример database.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)
```

## Пример dependencies.py

```python
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.core.database import AsyncSessionFactory
from app.infrastructure.database.repositories.order_repo import SQLAlchemyOrderRepository
from app.services.order_service import OrderService

async def get_db():
    async with AsyncSessionFactory() as session:
        yield session

def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    return OrderService(order_repo=SQLAlchemyOrderRepository(db))
```

## Правила

- `settings` — единственный экземпляр, импортируется по всему проекту.
- `core` не знает про конкретные роутеры или сервисы — только про инфраструктуру.
- Секреты (`SECRET_KEY`, API-ключи) **никогда** не хардкодятся — только через `.env`.
