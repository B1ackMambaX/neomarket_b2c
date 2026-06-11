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
    ) -> None:
        self._cart_repository = cart_repository
        self._product_event_repository = product_event_repository
        self._catalog_snapshot_repository = catalog_snapshot_repository

    async def handle_product_event(
        self,
        request: ProductEventRequest,
    ) -> ProductEventResponse:
        is_new = await self._product_event_repository.register_idempotency_key(
            idempotency_key=request.idempotency_key,
            event_type=request.event,
        )
        if not is_new:
            return ProductEventResponse(accepted=True)

        if request.event in _EVENT_TO_UNAVAILABLE_REASON and request.sku_ids:
            unavailable_reason = _EVENT_TO_UNAVAILABLE_REASON[request.event]
            await self._cart_repository.mark_unavailable_by_sku_ids(
                sku_ids=request.sku_ids,
                unavailable_reason=unavailable_reason,
            )

        if request.event in _SNAPSHOT_UPSERT_EVENTS and request.product_data:
            await self._catalog_snapshot_repository.upsert(
                product_id=request.product_id,
                category_id=request.product_data.category_id,
                title=request.product_data.title,
                characteristics=request.product_data.characteristics,
                min_price=request.product_data.min_price,
                has_stock=request.product_data.has_stock,
            )
        elif request.event in _SNAPSHOT_DEACTIVATE_EVENTS:
            await self._catalog_snapshot_repository.deactivate(request.product_id)
        elif request.event == "SKU_OUT_OF_STOCK":
            await self._catalog_snapshot_repository.set_stock(
                product_id=request.product_id, has_stock=False
            )
        elif request.event == "SKU_BACK_IN_STOCK":
            await self._catalog_snapshot_repository.set_stock(
                product_id=request.product_id, has_stock=True
            )

        return ProductEventResponse(accepted=True)
