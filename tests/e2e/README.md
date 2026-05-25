# tests/e2e/

End-to-end тесты. Проверяют полный HTTP-цикл: запрос через `AsyncClient` → FastAPI роутер → сервис → репозиторий → PostgreSQL → ответ.

## Что тестируется

- Правильность HTTP-статусов и структуры JSON-ответов
- Корректная авторизация (401, 403)
- Бизнес-сценарии от начала до конца: создание заказа, смена статуса, и т.д.
- Валидация входных данных (422 Unprocessable Entity)

## Структура

```
e2e/
├── test_orders.py
├── test_companies.py
├── test_auth.py
└── conftest.py  # Аутентифицированный клиент, фикстуры тестовых данных
```

## Пример

```python
# test_orders.py
async def test_create_order_success(auth_client, company_fixture):
    payload = {
        "items": [{"product_id": str(uuid4()), "quantity": 2, "price": "150.00"}],
        "delivery_address": "г. Москва, ул. Тверская, 1",
    }
    response = await auth_client.post("/api/v1/orders/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert "id" in data

async def test_create_order_unauthenticated(client):
    response = await client.post("/api/v1/orders/", json={})
    assert response.status_code == 401
```

## Правила

- E2E-тесты медленнее — не злоупотребляйте ими. Проверяйте критические user-пути, а не все ветки логики.
- Тестовые данные создаются через фикстуры, а не через прямые SQL-вставки.
- После каждого теста БД откатывается в исходное состояние.
