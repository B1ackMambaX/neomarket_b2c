# tests/unit/

Юнит-тесты для сервисов и доменной логики. Быстрые, изолированные — не требуют БД, HTTP или внешних сервисов.

## Что тестируется

- Методы сервисов (`app/services/`) с мок-репозиториями
- Бизнес-правила доменных сущностей (`app/domain/entities/`)
- Инварианты и исключения value objects (`app/domain/value_objects/`)

## Структура

```
unit/
├── services/
│   ├── test_order_service.py
│   ├── test_company_service.py
│   └── test_auth_service.py
└── domain/
    ├── test_order_entity.py
    └── test_money_value_object.py
```

## Пример теста сервиса

```python
# test_order_service.py
import pytest
from unittest.mock import AsyncMock
from app.services.order_service import OrderService
from app.domain.entities.order import OrderEntity

@pytest.fixture
def order_service():
    mock_order_repo = AsyncMock()
    mock_company_repo = AsyncMock()
    return OrderService(order_repo=mock_order_repo, company_repo=mock_company_repo)

async def test_create_order_returns_entity(order_service):
    order_service._order_repo.save.return_value = OrderEntity(company_id=..., items=[...])
    result = await order_service.create_order(buyer_id=..., items=[...])
    assert result.status.value == "draft"
```
