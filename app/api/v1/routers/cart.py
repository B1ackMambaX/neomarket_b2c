from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.dependencies.cart import get_cart_repository, resolve_cart_identity
from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.domain.entities.cart import CartIdentity
from app.domain.repositories.cart import CartRepository
from app.schemas.cart import CartResponse
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
