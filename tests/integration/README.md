# tests/integration/

Интеграционные тесты для репозиториев. Проверяют реальную работу с PostgreSQL — правильность SQL-запросов, маппинг ORM → сущность, транзакции.

## Что тестируется

- Конкретные реализации репозиториев (`app/infrastructure/database/repositories/`)
- Целостность данных: каскады, уникальные ограничения, внешние ключи
- Корректность маппинга ORM-модели в доменную сущность

## Требования

Перед запуском нужна тестовая БД. Настраивается через переменную:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/neomarket_test pytest tests/integration/
```

Или поднимается через Docker Compose:

```bash
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/
```

## Структура

```
integration/
├── repositories/
│   ├── test_order_repo.py
│   ├── test_company_repo.py
│   └── test_user_repo.py
└── conftest.py  # Тестовая сессия БД, откат транзакции после каждого теста
```

## Пример

```python
# test_order_repo.py
async def test_save_and_get_order(db_session):
    repo = SQLAlchemyOrderRepository(db_session)
    order = OrderEntity.create(company_id=uuid4(), items=[])
    saved = await repo.save(order)
    found = await repo.get_by_id(saved.id)
    assert found is not None
    assert found.id == saved.id
```
