import asyncio
from typing import Any

from app.domain.repositories.cart import CartRepository
from app.domain.repositories.catalog_snapshot import CatalogSnapshotRepository
from app.domain.repositories.product_event import ProductEventRepository
from app.schemas.product_event import ProductEventRequest, ProductEventResponse

_EVENT_TO_UNAVAILABLE_REASON = {
    "PRODUCT_BLOCKED": "PRODUCT_BLOCKED",
    "PRODUCT_HARD_BLOCKED": "PRODUCT_BLOCKED",
    "PRODUCT_DELETED": "PRODUCT_DELETED",
}

_SNAPSHOT_DEACTIVATE_EVENTS = {
    "PRODUCT_BLOCKED",
    "PRODUCT_HARD_BLOCKED",
    "PRODUCT_DELETED",
}


class ProductEventService:
    def __init__(
        self,
        cart_repository: CartRepository,
        product_event_repository: ProductEventRepository,
        catalog_snapshot_repository: CatalogSnapshotRepository,
        b2b_client: Any,
    ) -> None:
        self._cart_repository = cart_repository
        self._product_event_repository = product_event_repository
        self._catalog_snapshot_repository = catalog_snapshot_repository
        self._b2b_client = b2b_client

    async def handle_product_event(
        self,
        request: ProductEventRequest,
    ) -> ProductEventResponse:
        is_new = await self._product_event_repository.register_idempotency_key(
            idempotency_key=request.idempotency_key,
            event_type=request.event_type,
        )
        if not is_new:
            return ProductEventResponse(accepted=True)

        product_id = request.payload.product_id

        if request.event_type in _EVENT_TO_UNAVAILABLE_REASON:
            sku_ids = await self._cart_sku_ids_for_product(product_id)
            if sku_ids:
                unavailable_reason = _EVENT_TO_UNAVAILABLE_REASON[request.event_type]
                await self._cart_repository.mark_unavailable_by_sku_ids(
                    sku_ids=sku_ids,
                    unavailable_reason=unavailable_reason,
                )
        elif request.event_type == "SKU_OUT_OF_STOCK" and request.payload.sku_id:
            await self._cart_repository.mark_unavailable_by_sku_ids(
                sku_ids=[request.payload.sku_id],
                unavailable_reason="OUT_OF_STOCK",
            )

        if request.event_type in _SNAPSHOT_DEACTIVATE_EVENTS:
            await self._catalog_snapshot_repository.deactivate(product_id)
        elif request.event_type == "SKU_OUT_OF_STOCK":
            await self._catalog_snapshot_repository.set_stock(
                product_id=product_id, has_stock=False
            )
        elif request.event_type == "SKU_BACK_IN_STOCK":
            await self._catalog_snapshot_repository.set_stock(
                product_id=product_id, has_stock=True
            )
        elif request.event_type == "PRICE_CHANGED":
            await self._refresh_catalog_snapshot(
                product_id=product_id,
                fallback_min_price=request.payload.new_price,
            )

        return ProductEventResponse(accepted=True)

    async def _refresh_catalog_snapshot(
        self,
        *,
        product_id: str,
        fallback_min_price: int | None,
    ) -> None:
        try:
            product = await self._b2b_client.get_public_product(product_id)
        except Exception:
            if fallback_min_price is not None:
                await self._catalog_snapshot_repository.set_min_price(
                    product_id=product_id,
                    min_price=fallback_min_price,
                )
            return

        await self._catalog_snapshot_repository.upsert(
            product_id=product_id,
            category_id=self._category_id(product),
            title=product.get("title") or product.get("name") or product_id,
            characteristics=product.get("characteristics") or [],
            min_price=self._min_price(product, fallback_min_price),
            has_stock=self._has_stock(product),
        )

    async def _cart_sku_ids_for_product(self, product_id: str) -> list[str]:
        cart_sku_ids = await self._cart_repository.list_distinct_sku_ids()
        if not cart_sku_ids:
            return []

        async def _match(sku_id: str) -> str | None:
            try:
                sku = await self._b2b_client.get_public_sku(sku_id)
            except Exception:
                return None
            if sku.get("product_id") == product_id:
                return sku_id
            return None

        results = await asyncio.gather(*[_match(sku_id) for sku_id in cart_sku_ids])
        return [sku_id for sku_id in results if sku_id is not None]

    def _category_id(self, product: dict[str, Any]) -> str | None:
        category = product.get("category") or {}
        return product.get("category_id") or category.get("id")

    def _min_price(
        self,
        product: dict[str, Any],
        fallback_min_price: int | None,
    ) -> int:
        min_price = product.get("min_price")
        if min_price is not None:
            return int(min_price)
        price = product.get("price")
        if price is not None:
            return int(price)

        sku_prices = [
            max(int(sku.get("price") or 0) - int(sku.get("discount") or 0), 0)
            for sku in product.get("skus", [])
            if int(sku.get("active_quantity") or 0) > 0
        ]
        if sku_prices:
            return min(sku_prices)
        return fallback_min_price or 0

    def _has_stock(self, product: dict[str, Any]) -> bool:
        has_stock = product.get("has_stock")
        if has_stock is not None:
            return bool(has_stock)
        in_stock = product.get("in_stock")
        if in_stock is not None:
            return bool(in_stock)
        return any(
            int(sku.get("active_quantity") or 0) > 0
            for sku in product.get("skus", [])
        )
