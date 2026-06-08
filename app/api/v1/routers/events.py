from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.events import (
    get_product_event_repository,
    verify_b2b_service_key,
)
from app.domain.repositories.cart import CartRepository
from app.domain.repositories.product_event import ProductEventRepository
from app.schemas.product_event import ProductEventRequest, ProductEventResponse
from app.services.product_event_service import ProductEventService

router = APIRouter(prefix="/b2b/events", tags=["B2B Events"])


@router.post(
    "",
    response_model=ProductEventResponse,
    status_code=202,
    summary="Handle product events from B2B",
)
async def handle_product_event(
    request: ProductEventRequest,
    _: Annotated[None, Depends(verify_b2b_service_key)],
    cart_repository: CartRepository = Depends(get_cart_repository),
    product_event_repository: ProductEventRepository = Depends(
        get_product_event_repository
    ),
) -> ProductEventResponse:
    service = ProductEventService(cart_repository, product_event_repository)
    return await service.handle_product_event(request)
