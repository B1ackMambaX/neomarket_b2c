# tests/

Тесты проекта, разделённые по уровням изоляции. Запуск: `pytest`.

## Структура

```
tests/
├── unit/           # Юнит-тесты: сервисы и доменная логика (без БД и HTTP)
├── integration/    # Интеграционные тесты: репозитории с реальной тестовой БД
└── e2e/            # End-to-end тесты: HTTP-запросы через TestClient → реальная БД
```

## Конфигурация

| Файл | Назначение |
|---|---|
| `conftest.py` | Фикстуры верхнего уровня (тестовый клиент, тестовая БД, фикстуры данных) |
| `pytest.ini` / `pyproject.toml` | Настройки pytest, маркеры (`@pytest.mark.integration`) |

## Пример conftest.py

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine
from app.infrastructure.database.models.base import Base

@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

## Правила

- Юнит-тесты не касаются БД и HTTP — используют моки репозиториев.
- Интеграционные тесты используют отдельную тестовую БД (настраивается через `TEST_DATABASE_URL`).
- E2E-тесты проверяют полный цикл: запрос → бизнес-логика → персистентность.
- Каждый тест — независим: не зависит от порядка запуска и не оставляет побочных эффектов.
