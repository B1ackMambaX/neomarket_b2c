from typing import Any

import httpx

from app.core.config import settings


class B2BCatalogClient:
    def __init__(
        self,
        base_url: str = settings.B2B_BASE_URL,
        service_key: str = settings.B2B_SERVICE_KEY,
        timeout: float = settings.B2B_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Service-Key": service_key}
        self._timeout = timeout

    async def list_public_products(self, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            response = await client.get("/api/v1/public/products", params=params)
            response.raise_for_status()
            return response.json()

    async def get_facets(
        self,
        *,
        category_id: str | None,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if category_id:
            params["category_id"] = category_id
        for name, value in filters.items():
            params[f"filters[{name}]"] = value
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            response = await client.get("/api/v1/public/facets", params=params)
            response.raise_for_status()
            return response.json()
