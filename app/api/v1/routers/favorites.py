from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Response, status

from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.api.v1.dependencies.favorites import (
    get_favorites_repository,
    get_product_subscriptions_repository,
    resolve_favorites_identity,
)
from app.domain.entities.cart import CartIdentity
from app.domain.repositories.favorite import FavoriteRepository
from app.domain.repositories.subscription import ProductSubscriptionRepository
from app.schemas.favorite import FavoriteMutationResponse, FavoritesResponse
from app.schemas.subscription import (
    DEFAULT_SUBSCRIPTION_EVENTS,
    ProductSubscriptionRequest,
)
from app.services.favorite_service import FavoriteService
from app.services.subscription_service import ProductSubscriptionService

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("", response_model=FavoritesResponse, summary="Get favorites")
async def get_favorites(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    identity: CartIdentity = Depends(resolve_favorites_identity),
    repository: FavoriteRepository = Depends(get_favorites_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> FavoritesResponse:
    service = FavoriteService(repository, b2b_client)
    return await service.list_favorites(identity, limit=limit, offset=offset)


@router.put(
    "/{product_id}",
    response_model=FavoriteMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add product to favorites",
)
async def add_favorite(
    product_id: UUID,
    response: Response,
    identity: CartIdentity = Depends(resolve_favorites_identity),
    repository: FavoriteRepository = Depends(get_favorites_repository),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> FavoriteMutationResponse:
    service = FavoriteService(repository, b2b_client)
    result, created = await service.add_favorite(identity, str(product_id))
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return result


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product from favorites",
)
async def delete_favorite(
    product_id: UUID,
    identity: CartIdentity = Depends(resolve_favorites_identity),
    repository: FavoriteRepository = Depends(get_favorites_repository),
) -> Response:
    service = FavoriteService(repository, b2b_client=None)
    await service.delete_favorite(identity, str(product_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{product_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Subscribe to product changes",
)
async def subscribe_to_product(
    product_id: UUID,
    request: Annotated[ProductSubscriptionRequest | None, Body()] = None,
    identity: CartIdentity = Depends(resolve_favorites_identity),
    repository: ProductSubscriptionRepository = Depends(
        get_product_subscriptions_repository
    ),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> Response:
    service = ProductSubscriptionService(repository, b2b_client)
    events = (
        request.events
        if request is not None
        else list(DEFAULT_SUBSCRIPTION_EVENTS)
    )
    await service.subscribe(identity, str(product_id), events)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{product_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsubscribe from product changes",
)
async def unsubscribe_from_product(
    product_id: UUID,
    identity: CartIdentity = Depends(resolve_favorites_identity),
    repository: ProductSubscriptionRepository = Depends(
        get_product_subscriptions_repository
    ),
) -> Response:
    service = ProductSubscriptionService(repository, b2b_client=None)
    await service.unsubscribe(identity, str(product_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
