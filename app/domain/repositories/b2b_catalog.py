from typing import Any, Protocol


class B2BCatalogClientProtocol(Protocol):
    async def get_public_sku(self, sku_id: str) -> dict[str, Any]: ...

    async def batch_public_products(
        self, product_ids: list[str]
    ) -> list[dict[str, Any]]: ...

    async def reserve_inventory(
        self,
        *,
        idempotency_key: str,
        order_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def unreserve_inventory(
        self,
        *,
        order_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def fulfill_inventory(
        self,
        *,
        order_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]: ...
