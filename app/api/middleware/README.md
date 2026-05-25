# app/api/middleware/

Middleware-компоненты, применяемые ко всем запросам. Регистрируются в `app/main.py` через `app.add_middleware(...)`.

## Что сюда попадает

| Файл | Назначение |
|---|---|
| `cors.py` | Настройка CORS (`CORSMiddleware`) |
| `logging.py` | Структурированное логирование каждого запроса/ответа (метод, путь, статус, время) |
| `error_handler.py` | Глобальный обработчик исключений → единый формат JSON-ошибок |
| `request_id.py` | Генерация и прокидывание `X-Request-ID` через весь цикл запроса |
| `timing.py` | Добавление заголовка `X-Process-Time` в ответ |

## Пример error_handler.py

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from app.domain.exceptions import DomainException

async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": str(exc)},
    )
```

## Правила

- Middleware не знает про бизнес-логику — только сквозные технические аспекты.
- Обработчики исключений (`exception_handler`) регистрируются отдельно от Starlette-middleware, но хранятся здесь же.
- Порядок регистрации middleware важен: middleware выполняются в порядке, обратном регистрации.
