# app/api/v1/dependencies/

FastAPI `Depends`-провайдеры — переиспользуемые функции для внедрения зависимостей в эндпоинты.

## Что сюда попадает

| Файл | Назначение |
|---|---|
| `auth.py` | `get_current_user` — декодирование JWT, проверка токена, возврат пользователя |
| `permissions.py` | Проверка ролей и прав (`require_role("admin")`, `require_company_member`) |
| `pagination.py` | `PaginationParams` — параметры `limit` / `offset` / `page` из query string |
| `database.py` | `get_db` — провайдер async-сессии SQLAlchemy |
| `services.py` | Фабрики сервисов с инжектированными репозиториями |

## Пример

```python
# auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from app.core.security import decode_jwt
from app.domain.entities.user import UserEntity

bearer = HTTPBearer()

async def get_current_user(token = Depends(bearer)) -> UserEntity:
    payload = decode_jwt(token.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return UserEntity(**payload)
```

## Правила

- Зависимость не должна содержать бизнес-логику — только инфраструктурные проверки (токен валиден, сессия открыта).
- Сложные цепочки зависимостей выносятся в отдельную функцию и переиспользуются.
- Зависимости, специфичные только для одного роутера, можно определить прямо в файле роутера.
