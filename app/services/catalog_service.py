from typing import Any

import httpx

from app.domain.exceptions import NotFoundException, UpstreamServiceUnavailableException
from app.schemas.catalog import (
    CatalogProductCard,
    CategoryRef,
    ImageRef,
    PaginatedCatalogProducts,
    SellerRef,
)

B2C_ALLOWED_SORTS = ("price_asc", "price_desc", "popularity", "new")
B2B_SORT_MAP = {
    "price_asc": "price_asc",
    "price_desc": "price_desc",
    "popularity": "popular",
    "new": "created_desc",
}


class CatalogService:
    def __init__(self, b2b_client: Any) -> None:
        self._b2b_client = b2b_client

    async def list_products(
        self,
        *,
        limit: int,
        offset: int,
        q: str | None,
        sort: str,
        filters: dict[str, Any],
    ) -> PaginatedCatalogProducts:
        params = self._build_b2b_params(
            limit=limit,
            offset=offset,
            q=q,
            sort=sort,
            filters=filters,
        )
        try:
            payload = await self._b2b_client.list_public_products(params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise NotFoundException("Category not found") from exc
            raise UpstreamServiceUnavailableException("Catalog upstream failed") from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceUnavailableException("Catalog upstream unavailable") from exc

        return PaginatedCatalogProducts(
            items=[self._map_product(item) for item in payload.get("items", [])],
            total_count=payload.get("total_count", 0),
            limit=payload.get("limit", limit),
            offset=payload.get("offset", offset),
        )

    def _build_b2b_params(
        self,
        *,
        limit: int,
        offset: int,
        q: str | None,
        sort: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort": B2B_SORT_MAP[sort],
        }
        if q:
            params["search"] = q

        if category_id := filters.get("category_id"):
            params["category_id"] = category_id
        if (price_min := filters.get("price_min")) is not None:
            params["min_price"] = price_min
        if (price_max := filters.get("price_max")) is not None:
            params["max_price"] = price_max
        if seller_id := filters.get("seller_id"):
            params["seller_id"] = seller_id

        _reserved = frozenset({"category_id", "price_min", "price_max", "seller_id"})
        for name, value in filters.items():
            if name not in _reserved:
                params[f"filters[{name}]"] = value

        return params

    def _map_product(self, item: dict[str, Any]) -> CatalogProductCard:
        min_price = item.get("min_price", item.get("price", 0))
        image_url = item.get("cover_image") or item.get("image")
        images = []
        if image_url:
            images.append(
                ImageRef(
                    id=item.get("cover_image_id") or f"{item.get('id')}:cover",
                    url=image_url,
                    ordering=0,
                    is_main=True,
                )
            )

        category = None
        if item.get("category_id"):
            category = CategoryRef(id=item["category_id"])

        seller = None
        if item.get("seller_id") or item.get("seller"):
            seller_payload = item.get("seller") or {}
            seller = SellerRef(
                id=item.get("seller_id") or seller_payload.get("id"),
                display_name=seller_payload.get("display_name"),
            )

        has_stock = item.get("has_stock", item.get("in_stock", True))
        title = item.get("title") or item.get("name", "")

        return CatalogProductCard(
            id=item["id"],
            name=title,
            slug=item.get("slug"),
            category=category,
            min_price=min_price,
            old_price=item.get("old_price"),
            has_stock=has_stock,
            rating=item.get("rating"),
            reviews_count=item.get("reviews_count", 0),
            images=images,
            image=image_url,
            is_in_cart=item.get("is_in_cart", False),
            seller=seller,
        )
