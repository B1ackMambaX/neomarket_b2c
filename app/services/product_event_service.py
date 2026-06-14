import asyncio
from typing import Any

from app.domain.repositories.cart import CartRepository
from app.domain.repositories.catalog_snapshot import CatalogSnapshotRepository
from app.domain.repositories.product_event import ProductEventRepository
from app.schemas.product_event import ProductEventRequest, ProductEventResponse

_EVENT_TO_UNAVAILABLE_REASON = {
    "PRODUCT_BLOCKED": "PRODUCT_BLOCKED",
    "PRODUCT_DELETED": "PRODUCT_DELETED",
    "SKU_OUT_OF_STOCK": "OUT_OF_STOCK",
}

_SNAPSHOT_DEACTIVATE_EVENTS = {"PRODUCT_BLOCKED", "PRODUCT_DELETED"}
_SNAPSHOT_UPSERT_EVENTS = {"PRODUCT_CREATED", "PRODUCT_UPDATED"}


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

        if request.event_type in _SNAPSHOT_UPSERT_EVENTS and request.product_data:
            await self._catalog_snapshot_repository.upsert(
                product_id=product_id,
                category_id=request.product_data.category_id,
                title=request.product_data.title,
                characteristics=request.product_data.characteristics,
                min_price=request.product_data.min_price,
                has_stock=request.product_data.has_stock,
            )
        elif request.event_type in _SNAPSHOT_DEACTIVATE_EVENTS:
            await self._catalog_snapshot_repository.deactivate(product_id)
        elif request.event_type == "SKU_OUT_OF_STOCK":
            await self._catalog_snapshot_repository.set_stock(
                product_id=product_id, has_stock=False
            )
        elif request.event_type == "SKU_BACK_IN_STOCK":
            await self._catalog_snapshot_repository.set_stock(
                product_id=product_id, has_stock=True
            )

        return ProductEventResponse(accepted=True)

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
