# app/services/

**Слой приложения (Application Layer).** Содержит use-cases — сценарии использования системы. Сервисы оркестрируют доменные объекты и вызовы репозиториев, не зная ни про HTTP, ни про конкретную СУБД.

## Принцип организации

Один файл = один сервис для одного модуля. Сервис — это класс с методами, каждый из которых соответствует одному use-case.

| Файл | Use-cases |
|---|---|
| `order_service.py` | `create_order`, `cancel_order`, `get_order_history` |
| `company_service.py` | `register_company`, `update_requisites`, `invite_user` |
| `catalog_service.py` | `search_products`, `get_product_detail`, `update_price` |
| `invoice_service.py` | `generate_invoice`, `mark_paid`, `get_overdue` |
| `auth_service.py` | `login`, `refresh_token`, `logout` |

## Что сюда попадает

- Бизнес-логика, которая не принадлежит одной сущности (оркестрация нескольких доменных объектов)
- Вызовы репозиториев через абстрактные интерфейсы (`domain/repositories/`)
- Управление транзакциями (unit of work)
- Вызовы внешних сервисов через интерфейсы (`infrastructure/external/`)
- Доменные события и их публикация

## Чего сюда НЕ попадает

- HTTP-специфика (`Request`, `Response`, `HTTPException`)
- Прямые SQL-запросы или SQLAlchemy-вызовы
- Pydantic-схемы запросов/ответов из `app/schemas/` (сервис принимает и возвращает доменные объекты)

## Пример

```python
# order_service.py
from app.domain.repositories.order_repo import AbstractOrderRepository
from app.domain.repositories.company_repo import AbstractCompanyRepository
from app.domain.entities.order import OrderEntity

class OrderService:
    def __init__(
        self,
        order_repo: AbstractOrderRepository,
        company_repo: AbstractCompanyRepository,
    ):
        self._order_repo = order_repo
        self._company_repo = company_repo

    async def create_order(self, buyer_id: int, items: list) -> OrderEntity:
        company = await self._company_repo.get_or_raise(buyer_id)
        company.ensure_can_place_order()  # доменная проверка
        order = OrderEntity.create(company=company, items=items)
        return await self._order_repo.save(order)
```

## Правила

- Сервисы получают зависимости через конструктор (DI) — тестируются без реальной БД.
- Один метод = один use-case. Методы не вызывают друг друга внутри одного сервиса.
- Если логика требует нескольких шагов с возможным откатом — используется паттерн Unit of Work.
