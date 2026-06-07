from typing import Any

import httpx

from app.domain.entities.cart import CartIdentity
from app.domain.entities.favorite import StoredFavorite
from app.domain.exceptions import (
    B2BUnavailableException,
    NotFoundException,
    UnauthorizedException,
)
from app.domain.repositories.favorite import FavoriteRepository
from app.schemas.catalog import CatalogProductCard
from app.schemas.favorite import FavoriteMutationResponse, FavoritesResponse
from app.services.catalog_service import CatalogService


class FavoriteProductResolver:
    def __init__(self, b2b_client: Any) -> None:
        self._b2b_client = b2b_client

    async def load(
        self,
        product_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not product_ids:
            return {}
        try:
            payload = await self._b2b_client.batch_public_products(product_ids)
        except httpx.HTTPError as exc:
            raise B2BUnavailableException("B2B unavailable") from exc

        raw_items = (
            payload.get("items", payload) if isinstance(payload, dict) else payload
        )
        return {
            item["id"]: item
            for item in raw_items
            if item.get("id") and item.get("status") == "MODERATED"
        }


class FavoriteService:
    def __init__(self, repository: FavoriteRepository, b2b_client: Any) -> None:
        self._repository = repository
        self._b2b_client = b2b_client
        self._product_resolver = FavoriteProductResolver(b2b_client)

    async def list_favorites(
        self,
        identity: CartIdentity,
        *,
        limit: int,
        offset: int,
    ) -> FavoritesResponse:
        user_id = self._require_user_id(identity)
        favorites = await self._repository.list_for_user(
            user_id,
            limit=limit,
            offset=offset,
        )
        product_ids = [favorite.product_id for favorite in favorites]
        products = await self._product_resolver.load(product_ids)

        items = [
            self._map_product(products[favorite.product_id])
            for favorite in favorites
            if favorite.product_id in products
        ]
        return FavoritesResponse(
            items=items,
            total_count=len(items),
            limit=limit,
            offset=offset,
        )

    async def add_favorite(
        self,
        identity: CartIdentity,
        product_id: str,
    ) -> tuple[FavoriteMutationResponse, bool]:
        user_id = self._require_user_id(identity)
        products = await self._product_resolver.load([product_id])
        if product_id not in products:
            raise NotFoundException("Product not found")

        favorite, created = await self._repository.add(user_id, product_id)
        return self._mutation_response(favorite), created

    async def delete_favorite(self, identity: CartIdentity, product_id: str) -> None:
        user_id = self._require_user_id(identity)
        await self._repository.delete(user_id, product_id)

    def _map_product(self, product: dict[str, Any]) -> CatalogProductCard:
        return CatalogService(self._b2b_client)._map_product(product)

    def _require_user_id(self, identity: CartIdentity) -> str:
        if not identity.is_authenticated or identity.user_id is None:
            raise UnauthorizedException("Authentication required")
        return identity.user_id

    def _mutation_response(
        self,
        favorite: StoredFavorite,
    ) -> FavoriteMutationResponse:
        return FavoriteMutationResponse(
            id=favorite.id,
            product_id=favorite.product_id,
            added_at=favorite.added_at,
        )
