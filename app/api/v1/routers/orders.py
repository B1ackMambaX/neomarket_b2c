from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, status

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.api.v1.dependencies.orders import get_order_repository, resolve_buyer_id
from app.domain.repositories.cart import CartRepository
from app.domain.repositories.order import OrderRepository
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order checkout",
)
async def create_order(
    request: OrderCreateRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    buyer_id: str = Depends(resolve_buyer_id),
    order_repository: OrderRepository = Depends(get_order_repository),
    cart_repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> OrderResponse:
    service = OrderService(order_repository, cart_repository, b2b_client)
    return await service.create_order(
        buyer_id=buyer_id,
        request=request,
        idempotency_key=idempotency_key,
    )
