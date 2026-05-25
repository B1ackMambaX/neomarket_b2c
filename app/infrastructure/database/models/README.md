# app/infrastructure/database/models/

SQLAlchemy ORM-модели. Каждая модель описывает одну таблицу в PostgreSQL. Модели — это **техническая деталь** инфраструктурного слоя, они не передаются в сервисы или роутеры.

## Что сюда попадает

| Файл | Модель | Таблица |
|---|---|---|
| `base.py` | `Base`, `TimestampMixin` | — |
| `order.py` | `OrderModel` | `orders` |
| `order_item.py` | `OrderItemModel` | `order_items` |
| `company.py` | `CompanyModel` | `companies` |
| `user.py` | `UserModel` | `users` |
| `product.py` | `ProductModel` | `products` |
| `invoice.py` | `InvoiceModel` | `invoices` |

## Пример модели

```python
# order.py
from sqlalchemy import String, ForeignKey, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.models.base import Base, TimestampMixin
import uuid

class OrderModel(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    items: Mapped[list["OrderItemModel"]] = relationship(back_populates="order")
```

## Пример base.py

```python
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=func.now())
```

## Правила

- Модели импортируются **только** в репозиториях (`infrastructure/database/repositories/`).
- Название модели: `{Entity}Model` (чтобы не путать с доменной сущностью).
- Все внешние ключи, индексы и constraints определяются здесь же.
- Не добавляйте бизнес-методы в модели — для этого есть доменные сущности.
