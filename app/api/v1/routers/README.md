# app/api/v1/routers/

Содержит `APIRouter`-файлы, каждый из которых соответствует одному бизнес-модулю. Роутеры регистрируются в `app/main.py`.

## Принцип организации

Один файл = один ресурс/модуль. Пример для B2B:

| Файл | Префикс | Описание |
|---|---|---|
| `orders.py` | `/orders` | Заказы: создание, статусы, история |
| `companies.py` | `/companies` | Компании-покупатели и поставщики |
| `users.py` | `/users` | Пользователи компании, роли |
| `catalog.py` | `/catalog` | Каталог товаров и категорий |
| `invoices.py` | `/invoices` | Счета и платёжные документы |
| `contracts.py` | `/contracts` | Договора между компаниями |

## Что находится в файле роутера

```python
from fastapi import APIRouter, Depends, status
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order_service import OrderService
from app.api.v1.dependencies.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    service: OrderService = Depends(),
    current_user = Depends(get_current_user),
):
    return await service.create_order(payload, current_user)
```

## Правила

- Функция эндпоинта содержит только: валидацию входа, вызов сервиса, возврат результата.
- Все HTTP-ошибки (`HTTPException`) бросаются здесь или в middleware — не в сервисах.
- Документация эндпоинта пишется через `summary`, `description`, `response_description` в декораторе.
