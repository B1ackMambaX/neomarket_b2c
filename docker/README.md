# docker/

Вспомогательные Docker-файлы и конфиги для сборки образов.

## Что сюда попадает

| Файл | Назначение |
|---|---|
| `Dockerfile.prod` | Многоэтапная сборка для продакшена (минимальный образ) |
| `nginx.conf` | Конфиг Nginx для продакшен-прокси (если используется) |
| `entrypoint.sh` | Скрипт запуска: применение миграций + старт приложения |
| `healthcheck.sh` | Скрипт для Docker healthcheck |

## Основной Dockerfile

Основной `Dockerfile` для локальной разработки находится в корне проекта. Пример:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

## docker-compose.yml (в корне)

Сервисы:

| Сервис | Образ | Назначение |
|---|---|---|
| `api` | Локальный Dockerfile | FastAPI приложение |
| `db` | `postgres:16-alpine` | PostgreSQL |
| `pgadmin` | `dpage/pgadmin4` | Веб-интерфейс для БД (только dev) |

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/neomarket
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: neomarket
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
      retries: 5

volumes:
  postgres_data:
```
