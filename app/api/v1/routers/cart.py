from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.v1.dependencies.cart import get_cart_repository, resolve_cart_identity
from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.domain.entities.cart import CartIdentity
from app.domain.repositories.cart import CartRepository
from app.schemas.cart import (
    CartItemAddRequest,
    CartItemQuantityUpdateRequest,
    CartResponse,
    CartValidationResponse,
)
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartResponse, summary="Get cart")
async def get_cart(
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CartResponse:
    service = CartService(repository, b2b_client)
    return await service.get_cart(identity)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Clear cart")
async def clear_cart(
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
) -> Response:
    service = CartService(repository, b2b_client=None)
    await service.clear(identity)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/validate",
    response_model=CartValidationResponse,
    summary="Validate cart before checkout",
)
async def validate_cart(
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CartValidationResponse:
    service = CartService(repository, b2b_client)
    return await service.validate(identity)


@router.post(
    "/merge",
    response_model=CartResponse,
    summary="Merge guest cart into user cart",
)
async def merge_cart(
    guest_session_id: Annotated[str, Header(alias="X-Session-Id")],
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CartResponse:
    service = CartService(repository, b2b_client)
    return await service.merge_guest_cart(identity, guest_session_id)


@router.post("/items", response_model=CartResponse, summary="Add SKU to cart")
async def add_cart_item(
    request: CartItemAddRequest,
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CartResponse:
    service = CartService(repository, b2b_client)
    return await service.add_item(identity, request)


@router.patch(
    "/items/{sku_id}",
    response_model=CartResponse,
    summary="Update SKU quantity in cart",
)
async def update_cart_item_quantity(
    sku_id: str,
    request: CartItemQuantityUpdateRequest,
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CartResponse:
    service = CartService(repository, b2b_client)
    return await service.update_item_quantity(identity, sku_id, request)


@router.delete(
    "/items/{sku_id}",
    response_model=CartResponse,
    summary="Delete SKU from cart",
)
async def delete_cart_item(
    sku_id: str,
    identity: CartIdentity = Depends(resolve_cart_identity),
    repository: CartRepository = Depends(get_cart_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CartResponse:
    service = CartService(repository, b2b_client)
    return await service.delete_item(identity, sku_id)
