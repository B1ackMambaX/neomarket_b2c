# app/domain/value_objects/

Value Objects — объекты без идентификатора, определяемые своими атрибутами. Неизменяемы (immutable), равны друг другу по значению, а не по ссылке. Инкапсулируют правила валидации и форматирования примитивов.

## Что сюда попадает

| Файл | Value Object | Пример значений |
|---|---|---|
| `order_status.py` | `OrderStatus` | `DRAFT`, `PENDING`, `CONFIRMED`, `SHIPPED`, `CANCELLED` |
| `money.py` | `Money` | `Money(amount=1500.00, currency="RUB")` |
| `email.py` | `Email` | `Email("buyer@company.ru")` |
| `inn.py` | `INN` | `INN("7707083893")` — с валидацией контрольной суммы |
| `address.py` | `Address` | Адрес доставки с валидацией полей |
| `phone.py` | `PhoneNumber` | Нормализованный номер телефона |
| `quantity.py` | `Quantity` | Положительное количество товара |

## Пример

```python
# money.py
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
```

## Правила

- `frozen=True` для `dataclass` или `model_config = ConfigDict(frozen=True)` для Pydantic — объект неизменяем.
- Вся валидация находится в `__post_init__` или валидаторах Pydantic.
- Value objects сравниваются по значению (`==`), не по `id`.
- Не содержат бизнес-методов, влияющих на внешнее состояние — только вычисления и преобразования.
