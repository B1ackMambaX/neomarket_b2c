# app/infrastructure/external/

Клиенты внешних HTTP-сервисов и интеграций. Каждый файл — отдельный адаптер для одного внешнего сервиса.

## Что сюда попадает

| Файл | Внешний сервис |
|---|---|
| `payment_client.py` | Платёжный шлюз (ЮKassa, Tinkoff, и др.) |
| `crm_client.py` | CRM-система (Bitrix24, AmoCRM) |
| `email_client.py` | Email-рассылки (SendGrid, Postmark) |
| `sms_client.py` | SMS-уведомления |
| `dadata_client.py` | DaData — проверка ИНН, ОГРН, адресов |
| `s3_client.py` | Хранилище файлов (S3-совместимое) |

## Пример клиента

```python
# dadata_client.py
import httpx
from app.core.config import settings

class DaDataClient:
    BASE_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs"

    def __init__(self):
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Token {settings.DADATA_API_KEY}"},
            timeout=5.0,
        )

    async def suggest_company(self, query: str) -> dict:
        resp = await self._client.post(
            f"{self.BASE_URL}/suggest/party",
            json={"query": query, "count": 5},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
```

## Правила

- Каждый клиент изолирован: не знает про другие сервисы, про домен, про HTTP-слой.
- Клиент не бросает доменные исключения — только технические (`httpx.HTTPError`). Преобразование в доменные исключения делает вызывающий сервис.
- Timeouts обязательны для всех внешних запросов.
- Аутентификационные данные (API-ключи) берутся из `app/core/config.py`, а не хардкодятся.
- Инстансы клиентов создаются один раз (singleton) через DI в `app/core/`.
