# app/infrastructure/database/repositories/

Конкретные реализации абстрактных репозиториев из `app/domain/repositories/`. Здесь живут все SQL-запросы через SQLAlchemy async.

## Что сюда попадает

| Файл | Реализует |
|---|---|
| `order_repo.py` | `SQLAlchemyOrderRepository(AbstractOrderRepository)` |
| `company_repo.py` | `SQLAlchemyCompanyRepository(AbstractCompanyRepository)` |
| `user_repo.py` | `SQLAlchemyUserRepository(AbstractUserRepository)` |
| `product_repo.py` | `SQLAlchemyProductRepository(AbstractProductRepository)` |

## Пример реализации

```python
# order_repo.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.domain.entities.order import OrderEntity
from app.domain.repositories.order_repo import AbstractOrderRepository
from app.infrastructure.database.models.order import OrderModel

class SQLAlchemyOrderRepository(AbstractOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, order_id: UUID) -> OrderEntity | None:
        result = await self._session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, order: OrderEntity) -> OrderEntity:
        model = self._to_model(order)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    def _to_entity(self, model: OrderModel) -> OrderEntity:
        return OrderEntity(id=model.id, status=model.status, ...)

    def _to_model(self, entity: OrderEntity) -> OrderModel:
        return OrderModel(id=entity.id, status=entity.status.value, ...)
```

## Правила

- Репозиторий получает `AsyncSession` через конструктор — управление транзакцией снаружи (в сервисе или Unit of Work).
- Маперы `_to_entity` / `_to_model` — приватные методы самого репозитория.
- Не бросайте HTTP-исключения здесь — только `domain.exceptions`.
- Все запросы асинхронные (`await`).
