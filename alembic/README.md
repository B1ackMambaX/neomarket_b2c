# alembic/

Миграции базы данных. Управляются через Alembic — инструмент версионирования схемы PostgreSQL.

## Структура

```
alembic/
├── versions/       # Файлы миграций (генерируются автоматически)
├── env.py          # Конфигурация Alembic: подключение к БД, автоимпорт моделей
└── script.py.mako  # Шаблон для новых файлов миграций
```

## Основные команды

```bash
# Создать новую миграцию (автогенерация на основе изменений моделей)
alembic revision --autogenerate -m "add_orders_table"

# Применить все миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Показать текущую версию
alembic current

# История миграций
alembic history
```

## Настройка env.py

`env.py` должен импортировать все ORM-модели, чтобы автогенерация видела изменения:

```python
# alembic/env.py
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models import order, company, user, product  # noqa
from app.core.config import settings

target_metadata = Base.metadata
```

## Правила

- **Всегда** проверяйте автосгенерированную миграцию перед применением — Alembic не всегда корректно определяет изменения.
- Никогда не редактируйте уже применённые миграции — только создавайте новые.
- Каждая миграция должна иметь корректный `downgrade()` для возможности отката.
- Файлы миграций коммитятся в git.
