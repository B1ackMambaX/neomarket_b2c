# app/domain/

**Доменный слой (Domain Layer).** Сердце архитектуры. Содержит бизнес-сущности, правила домена и абстрактные интерфейсы репозиториев. Этот слой **не зависит** ни от одного другого слоя проекта — никаких импортов из `api`, `services`, `infrastructure`.

## Структура

```
domain/
├── entities/        # Доменные сущности
├── repositories/    # Абстрактные интерфейсы репозиториев (ABC)
├── value_objects/   # Value objects
└── exceptions.py   # Доменные исключения
```

## Правило: нулевые внешние зависимости

В `domain/` допускаются только:
- Стандартная библиотека Python (`dataclasses`, `abc`, `datetime`, `uuid`, `enum`)
- `pydantic` (только для определения моделей — без HTTP/ORM-зависимостей)

Запрещено импортировать: `sqlalchemy`, `fastapi`, `httpx`, любые пакеты из других слоёв.

## Доменные исключения (exceptions.py)

Здесь определяются бизнес-ошибки, которые бросает доменная логика:

```python
class DomainException(Exception):
    code: str = "DOMAIN_ERROR"

class OrderCannotBeCancelledException(DomainException):
    code = "ORDER_CANNOT_BE_CANCELLED"

class CompanyNotVerifiedException(DomainException):
    code = "COMPANY_NOT_VERIFIED"
```

Слой API перехватывает их и преобразует в HTTP 4xx-ответы.
