# app/schemas/

**DTO (Data Transfer Objects)** — Pydantic-модели для валидации и сериализации данных на HTTP-границе. Схемы описывают, что приходит в запросе и что уходит в ответе.

## Что сюда попадает

Для каждого модуля — отдельный файл со схемами запроса и ответа:

| Файл | Схемы |
|---|---|
| `order.py` | `OrderCreate`, `OrderUpdate`, `OrderResponse`, `OrderListResponse` |
| `company.py` | `CompanyCreate`, `CompanyResponse`, `CompanyUpdate` |
| `user.py` | `UserCreate`, `UserResponse`, `UserLogin` |
| `product.py` | `ProductResponse`, `ProductFilter` |
| `invoice.py` | `InvoiceResponse` |
| `common.py` | `PaginatedResponse`, `ErrorResponse`, `SuccessResponse` |

## Пример

```python
# order.py
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    price: Decimal = Field(ge=0)

class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1)
    delivery_address: str
    comment: str | None = None

class OrderResponse(BaseModel):
    id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
```

## Правила

- Схемы живут **только** в слое API: роутеры принимают схемы и конвертируют в доменные объекты перед вызовом сервиса.
- Схема ответа (`Response`) может строиться `from_attributes=True` из доменной сущности или ORM-модели — на выбор команды, но консистентно.
- Разделяйте схемы создания (`Create`), обновления (`Update`) и чтения (`Response`) — у них разные поля.
- Не добавляйте бизнес-логику в схемы. Валидаторы (`@field_validator`) — только для форматирования входных данных (trim, lowercase, и т.п.).
