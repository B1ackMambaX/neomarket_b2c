from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from app.api.v1.dependencies.catalog import (
    get_b2b_catalog_client,
)

from app.schemas.category import (
    BreadcrumbResponse,
    CategoryTreeResponse,
)

from app.services.catalog import CatalogService


router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)


@router.get(
    "",
    response_model=CategoryTreeResponse,
    summary="Get category tree",
)
async def get_categories(
    b2b_client: Any = Depends(
        get_b2b_catalog_client
    ),
) -> CategoryTreeResponse:

    service = CatalogService(
        b2b_client
    )

    result = (
        await service.get_categories_tree()
    )

    return CategoryTreeResponse(
        **result
    )


@router.get(
    "/{category_id}",
    summary="Get category details",
)
async def get_category(
    category_id: UUID,
    include_product_count: bool = Query(
        False,
    ),
    b2b_client: Any = Depends(
        get_b2b_catalog_client
    ),
):

    service = CatalogService(
        b2b_client
    )

    return await service.get_category(
        str(category_id),
        include_product_count=(
            include_product_count
        ),
    )


breadcrumbs_router = APIRouter(
    prefix="/breadcrumbs",
    tags=["Categories"],
)


@breadcrumbs_router.get(
    "",
    response_model=BreadcrumbResponse,
    summary="Get breadcrumbs",
)
async def get_breadcrumbs(
    category_id: UUID | None = Query(
        default=None,
    ),
    product_id: UUID | None = Query(
        default=None,
    ),
    b2b_client: Any = Depends(
        get_b2b_catalog_client
    ),
) -> BreadcrumbResponse:

    service = CatalogService(
        b2b_client
    )

    result = (
        await service.get_breadcrumbs(
            category_id=(
                str(category_id)
                if category_id
                else None
            ),
            product_id=(
                str(product_id)
                if product_id
                else None
            ),
        )
    )

    return BreadcrumbResponse(
        **result
    )