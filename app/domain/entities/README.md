# app/domain/entities/

Доменные сущности (Entity) — объекты, имеющие уникальный идентификатор и жизненный цикл. Содержат бизнес-правила и инварианты, специфичные для одной сущности.

## Что сюда попадает

| Файл | Сущность |
|---|---|
| `order.py` | `OrderEntity` — заказ, его статусы, позиции |
| `company.py` | `CompanyEntity` — компания (покупатель или поставщик) |
| `user.py` | `UserEntity` — пользователь компании |
| `product.py` | `ProductEntity` — товар в каталоге |
| `invoice.py` | `InvoiceEntity` — счёт на оплату |
| `contract.py` | `ContractEntity` — договор между компаниями |

## Пример сущности

```python
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from app.domain.value_objects.order_status import OrderStatus
from app.domain.exceptions import OrderCannotBeCancelledException

@dataclass
class OrderEntity:
    id: UUID = field(default_factory=uuid4)
    company_id: UUID = None
    status: OrderStatus = OrderStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    items: list = field(default_factory=list)

    @classmethod
    def create(cls, company_id: UUID, items: list) -> "OrderEntity":
        return cls(company_id=company_id, items=items)

    def cancel(self) -> None:
        if self.status not in (OrderStatus.DRAFT, OrderStatus.PENDING):
            raise OrderCannotBeCancelledException(
                f"Cannot cancel order in status {self.status}"
            )
        self.status = OrderStatus.CANCELLED
```

## Правила

- Сущность знает о своих инвариантах и защищает их через методы (не публичные поля).
- Фабричные методы (`create`, `from_dict`) используются вместо сложной логики в `__init__`.
- Сущность **не знает** про репозиторий, БД или HTTP.
- ID генерируется на уровне домена (UUID), не делегируется БД.
