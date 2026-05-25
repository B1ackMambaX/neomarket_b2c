# app/domain/repositories/

Абстрактные интерфейсы репозиториев. Определяют контракт — **что** можно сделать с агрегатом, не указывая **как** это реализовано. Конкретные реализации живут в `app/infrastructure/database/repositories/`.

## Что сюда попадает

| Файл | Интерфейс |
|---|---|
| `order_repo.py` | `AbstractOrderRepository` |
| `company_repo.py` | `AbstractCompanyRepository` |
| `user_repo.py` | `AbstractUserRepository` |
| `product_repo.py` | `AbstractProductRepository` |

## Пример интерфейса

```python
# order_repo.py
from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.order import OrderEntity

class AbstractOrderRepository(ABC):

    @abstractmethod
    async def get_by_id(self, order_id: UUID) -> OrderEntity | None:
        ...

    @abstractmethod
    async def get_or_raise(self, order_id: UUID) -> OrderEntity:
        ...

    @abstractmethod
    async def list_by_company(
        self, company_id: UUID, limit: int, offset: int
    ) -> list[OrderEntity]:
        ...

    @abstractmethod
    async def save(self, order: OrderEntity) -> OrderEntity:
        ...

    @abstractmethod
    async def delete(self, order_id: UUID) -> None:
        ...
```

## Правила

- Методы принимают и возвращают **доменные сущности**, не ORM-модели и не словари.
- Интерфейс содержит только операции, реально нужные бизнес-логике (YAGNI).
- `get_or_raise` — конвенция: если объект не найден, бросает доменное исключение `NotFound`.
- Никаких SQLAlchemy, asyncpg или иных технических деталей в сигнатурах.
