from datetime import date
from typing import Any

import httpx

from app.domain.exceptions import B2BUnavailableException
from app.domain.repositories.collection import CollectionRepository
from app.schemas.catalog import CatalogCollection, CollectionProductCard
from app.services.catalog_service import CatalogService

_B2B_BATCH_SIZE = 100


class CollectionService:
    def __init__(
        self,
        repository: CollectionRepository,
        b2b_client: Any,
    ) -> None:
        self._repository = repository
        self._b2b_client = b2b_client
        self._catalog_service = CatalogService(b2b_client)

    async def list_collections(self) -> list[CatalogCollection]:
        collections = await self._repository.list_active(as_of=date.today())
        product_ids = list(
            dict.fromkeys(
                product_id
                for collection in collections
                for product_id in collection.product_ids
            )
        )
        products = await self._load_products(product_ids)

        return [
            CatalogCollection(
                id=collection.id,
                name=collection.title,
                description=collection.description,
                products=[
                    self._map_product(products[product_id])
                    for product_id in collection.product_ids
                    if product_id in products
                ],
            )
            for collection in collections
        ]

    async def _load_products(
        self,
        product_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not product_ids:
            return {}

        products: dict[str, dict[str, Any]] = {}
        try:
            for offset in range(0, len(product_ids), _B2B_BATCH_SIZE):
                batch_ids = product_ids[offset : offset + _B2B_BATCH_SIZE]
                payload = await self._b2b_client.batch_public_products(batch_ids)
                raw_items = (
                    payload.get("items", [])
                    if isinstance(payload, dict)
                    else payload
                )
                products.update(
                    {
                        item["id"]: item
                        for item in raw_items
                        if item.get("id") in batch_ids
                        and self._is_available(item)
                    }
                )
        except httpx.HTTPError as exc:
            raise B2BUnavailableException("B2B unavailable") from exc

        return products

    def _map_product(self, product: dict[str, Any]) -> CollectionProductCard:
        card = self._catalog_service._map_product(product)
        category = card.category
        if category is not None and (
            category.name is None or category.level is None
        ):
            category = None

        return CollectionProductCard(
            id=card.id,
            name=card.name,
            slug=card.slug,
            category=category,
            min_price=card.min_price,
            old_price=card.old_price,
            has_stock=card.has_stock,
            rating=card.rating,
            reviews_count=card.reviews_count,
            images=card.images,
            seller=card.seller,
        )

    def _is_available(self, product: dict[str, Any]) -> bool:
        if product.get("status") not in (None, "MODERATED"):
            return False
        if product.get("deleted") is True:
            return False
        if product.get("has_stock") is False or product.get("in_stock") is False:
            return False

        skus = product.get("skus")
        if isinstance(skus, list):
            return any(
                sku.get("available_quantity", sku.get("active_quantity", 0)) > 0
                for sku in skus
            )
        return True
