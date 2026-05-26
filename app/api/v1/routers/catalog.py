from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.schemas.catalog import (
    CatalogProductDetail,
    FacetsResponse,
    PaginatedCatalogProducts,
)
from app.services.catalog_service import B2C_ALLOWED_SORTS, CatalogService

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get(
    "/products",
    response_model=PaginatedCatalogProducts,
    summary="Публичный листинг товаров с фильтрами",
)
async def list_catalog_products(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="popularity"),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> PaginatedCatalogProducts | JSONResponse:
    if sort not in B2C_ALLOWED_SORTS:
        allowed = ", ".join(B2C_ALLOWED_SORTS)
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_REQUEST",
                "message": f"Invalid sort parameter. Allowed: {allowed}",
            },
        )

    service = CatalogService(b2b_client)
    return await service.list_products(
        limit=limit,
        offset=offset,
        q=q,
        sort=sort,
        filters=_parse_filter_query(request),
    )


@router.get(
    "/products/{product_id}",
    response_model=CatalogProductDetail,
    summary="Карточка товара (публичная)",
)
async def get_catalog_product(
    product_id: str,
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> CatalogProductDetail:
    service = CatalogService(b2b_client)
    return await service.get_product(product_id)


@router.get(
    "/facets",
    response_model=FacetsResponse,
    summary="Фасеты (фильтры) для каталога",
)
async def get_catalog_facets(
    request: Request,
    category_id: str | None = Query(default=None),
    b2b_client: Any = Depends(get_b2b_catalog_client),
) -> FacetsResponse:
    service = CatalogService(b2b_client)
    filters = _parse_filter_query(request)
    filters.pop("category_id", None)  # category_id is a dedicated param, not a filter
    return await service.get_facets(category_id=category_id, filters=filters)


_ATTR_PREFIX = "filter[attributes]["


def _parse_filter_query(request: Request) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith(_ATTR_PREFIX) and key.endswith("]"):
            # filter[attributes][brand]=Apple  →  dynamic attribute "brand"
            name = key[len(_ATTR_PREFIX) : -1]
        elif key.startswith("filter[") and key.endswith("]"):
            inner = key[7:-1]
            if "[" in inner:
                continue  # skip malformed nested keys
            name = inner
        else:
            continue
        existing = filters.get(name)
        if existing is None:
            filters[name] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            filters[name] = [existing, value]
    return filters
