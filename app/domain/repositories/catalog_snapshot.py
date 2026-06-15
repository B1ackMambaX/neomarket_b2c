from typing import Any, Protocol


class CatalogSnapshotRepository(Protocol):
    async def upsert(
        self,
        *,
        product_id: str,
        category_id: str | None,
        title: str,
        characteristics: list[dict[str, Any]],
        min_price: int,
        has_stock: bool,
    ) -> None: ...

    async def deactivate(self, product_id: str) -> None: ...

    async def set_stock(self, *, product_id: str, has_stock: bool) -> None: ...

    async def set_min_price(self, *, product_id: str, min_price: int) -> None: ...

    async def get_facets(
        self,
        *,
        category_id: str | None,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]: ...
