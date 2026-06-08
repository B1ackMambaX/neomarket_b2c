from app.domain.repositories.cart import CartRepository
from app.domain.repositories.product_event import ProductEventRepository
from app.schemas.product_event import ProductEventRequest, ProductEventResponse

_EVENT_TO_UNAVAILABLE_REASON = {
    "PRODUCT_BLOCKED": "PRODUCT_BLOCKED",
    "PRODUCT_DELETED": "PRODUCT_DELETED",
    "SKU_OUT_OF_STOCK": "OUT_OF_STOCK",
}


class ProductEventService:
    def __init__(
        self,
        cart_repository: CartRepository,
        product_event_repository: ProductEventRepository,
    ) -> None:
        self._cart_repository = cart_repository
        self._product_event_repository = product_event_repository

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

        unavailable_reason = _EVENT_TO_UNAVAILABLE_REASON[request.event]
        await self._cart_repository.mark_unavailable_by_sku_ids(
            sku_ids=request.sku_ids,
            unavailable_reason=unavailable_reason,
        )
        return ProductEventResponse(accepted=True)
