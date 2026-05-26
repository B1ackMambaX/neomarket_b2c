import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Request, Response

from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.main import app
from app.services import catalog_service


class StubB2BCatalogClient:
    def __init__(
        self,
        payload: dict | None = None,
        product_payload: dict | None = None,
        facets_payload: dict | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {}
        self.product_payload = product_payload or {}
        self.facets_payload = facets_payload or {}
        self.error = error
        self.calls: list[dict] = []
        self.product_calls: list[str] = []
        self.facets_calls: list[dict] = []

    async def list_public_products(self, params: dict) -> dict:
        self.calls.append(params)
        if self.error:
            raise self.error
        return self.payload

    async def get_public_product(self, product_id: str) -> dict:
        self.product_calls.append(product_id)
        if self.error:
            raise self.error
        return self.product_payload

    async def get_facets(self, *, category_id: str | None, filters: dict) -> dict:
        self.facets_calls.append({"category_id": category_id, "filters": filters})
        if self.error:
            raise self.error
        return self.facets_payload


@pytest.fixture(autouse=True)
def clear_facets_cache():
    catalog_service._facets_cache.clear()
    yield
    catalog_service._facets_cache.clear()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_catalog_returns_filtered_sorted_products(client: AsyncClient):
    b2b = StubB2BCatalogClient(
        payload={
            "items": [
                {
                    "id": "770e8400-e29b-41d4-a716-446655440003",
                    "title": "Samsung Galaxy S24",
                    "slug": "samsung-galaxy-s24",
                    "category_id": "123e4567-e89b-12d3-a456-426614174001",
                    "min_price": 8999000,
                    "cover_image": "https://cdn.neomarket.ru/images/s24.jpg",
                },
                {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "title": "iPhone 15 Pro Max",
                    "slug": "iphone-15-pro-max",
                    "category_id": "123e4567-e89b-12d3-a456-426614174001",
                    "min_price": 12999000,
                    "cover_image": "https://cdn.neomarket.ru/images/iphone15.jpg",
                },
            ],
            "total_count": 2,
            "limit": 2,
            "offset": 0,
        }
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(
        "/api/v1/catalog/products",
        params={
            "limit": "2",
            "offset": "0",
            "sort": "price_asc",
            "filter[category_id]": "123e4567-e89b-12d3-a456-426614174001",
            "filter[attributes][brand]": "Samsung",
        },
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Samsung Galaxy S24"
    assert response.json()["items"][0]["price"] == 8999000
    assert response.json()["total_count"] == 2
    assert b2b.calls == [
        {
            "limit": 2,
            "offset": 0,
            "sort": "price_asc",
            "category_id": "123e4567-e89b-12d3-a456-426614174001",
            "filters[brand]": "Samsung",
        }
    ]


@pytest.mark.asyncio
async def test_invalid_sort_returns_400(client: AsyncClient):
    response = await client.get(
        "/api/v1/catalog/products",
        params={"sort": "rating"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_REQUEST",
        "message": "Invalid sort parameter. Allowed: price_asc, price_desc, popularity, new",
    }


@pytest.mark.asyncio
async def test_b2b_unavailable_returns_502(client: AsyncClient):
    b2b = StubB2BCatalogClient(error=httpx.ConnectError("failed to connect"))
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/products")

    assert response.status_code == 502
    assert response.json() == {
        "code": "UPSTREAM_SERVICE_UNAVAILABLE",
        "message": "Catalog upstream unavailable",
    }


@pytest.mark.asyncio
async def test_b2b_category_not_found_returns_404(client: AsyncClient):
    request = Request("GET", "http://b2b/api/v1/public/products")
    upstream_response = Response(status_code=404, request=request)
    b2b = StubB2BCatalogClient(
        error=httpx.HTTPStatusError(
            "not found",
            request=request,
            response=upstream_response,
        )
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(
        "/api/v1/catalog/products",
        params={"filter[category_id]": "123e4567-e89b-12d3-a456-426614174099"},
    )

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Category not found"}


@pytest.mark.asyncio
async def test_product_card_returns_full_data_with_skus(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440002"
    b2b = StubB2BCatalogClient(product_payload=_product_card_payload(product_id))
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == product_id
    assert body["name"] == "iPhone 15 Pro Max"
    assert body["title"] == "iPhone 15 Pro Max"
    assert body["description"] == "Флагманский смартфон Apple 2024 года"
    assert body["images"][0]["url"] == "https://cdn.neomarket.ru/images/front.jpg"
    assert body["characteristics"] == [{"name": "Бренд", "value": "Apple"}]
    assert body["attributes"] == {"Бренд": "Apple"}
    assert body["min_price"] == 12499000
    assert body["old_price"] == 12999000
    assert body["has_stock"] is True
    assert len(body["skus"]) == 2
    assert body["skus"][0]["price"] == 12999000
    assert body["skus"][0]["discount"] == 500000
    assert body["skus"][0]["available_quantity"] == 10
    assert body["skus"][0]["active_quantity"] == 10
    assert body["skus"][0]["in_stock"] is True
    assert body["skus"][0]["image"] == "/s3/iphone15-black-256.jpg"
    assert b2b.product_calls == [product_id]


@pytest.mark.asyncio
async def test_cost_price_absent_in_response(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440002"
    b2b = StubB2BCatalogClient(product_payload=_product_card_payload(product_id))
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    sku = response.json()["skus"][0]
    assert "cost_price" not in sku
    assert "reserved_quantity" not in sku


@pytest.mark.asyncio
async def test_sku_without_stock_is_shown_as_unavailable(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440002"
    b2b = StubB2BCatalogClient(product_payload=_product_card_payload(product_id))
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 200
    sku_without_stock = response.json()["skus"][1]
    assert sku_without_stock["available_quantity"] == 0
    assert sku_without_stock["active_quantity"] == 0
    assert sku_without_stock["in_stock"] is False


@pytest.mark.asyncio
async def test_blocked_product_returns_404(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440099"
    request = Request("GET", f"http://b2b/api/v1/public/products/{product_id}")
    upstream_response = Response(status_code=404, request=request)
    b2b = StubB2BCatalogClient(
        error=httpx.HTTPStatusError(
            "not found",
            request=request,
            response=upstream_response,
        )
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Product not found"}


@pytest.mark.asyncio
async def test_facets_return_counts_per_filter_value(client: AsyncClient):
    b2b = StubB2BCatalogClient(
        facets_payload={
            "category_id": "123e4567-e89b-12d3-a456-426614174001",
            "facets": [
                {
                    "name": "brand",
                    "values": [
                        {"value": "Apple", "count": 124},
                        {"value": "Samsung", "count": 98},
                    ],
                },
                {
                    "name": "color",
                    "values": [
                        {"value": "черный", "count": 60},
                        {"value": "белый", "count": 45},
                    ],
                },
            ],
        }
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(
        "/api/v1/catalog/facets",
        params={
            "category_id": "123e4567-e89b-12d3-a456-426614174001",
            "filter[attributes][brand]": "Apple",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category_id"] == "123e4567-e89b-12d3-a456-426614174001"
    assert len(body["facets"]) == 2
    brand_facet = next(f for f in body["facets"] if f["name"] == "brand")
    assert brand_facet["values"][0] == {"value": "Apple", "count": 124}
    assert b2b.facets_calls == [
        {
            "category_id": "123e4567-e89b-12d3-a456-426614174001",
            "filters": {"brand": "Apple"},
        }
    ]


def _product_card_payload(product_id: str) -> dict:
    return {
        "id": product_id,
        "seller_id": "880e8400-e29b-41d4-a716-446655440001",
        "category_id": "123e4567-e89b-12d3-a456-426614174001",
        "title": "iPhone 15 Pro Max",
        "slug": "iphone-15-pro-max",
        "description": "Флагманский смартфон Apple 2024 года",
        "status": "MODERATED",
        "images": [
            {
                "id": "990e8400-e29b-41d4-a716-446655440001",
                "url": "https://cdn.neomarket.ru/images/front.jpg",
                "ordering": 0,
            },
        ],
        "characteristics": [{"name": "Бренд", "value": "Apple"}],
        "skus": [
            {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "product_id": product_id,
                "name": "256GB Black",
                "price": 12999000,
                "discount": 500000,
                "cost_price": 10000000,
                "stock_quantity": 12,
                "active_quantity": 10,
                "reserved_quantity": 2,
                "article": "IPH15PM-256-BLK",
                "images": [
                    {
                        "id": "990e8400-e29b-41d4-a716-446655440002",
                        "url": "/s3/iphone15-black-256.jpg",
                        "ordering": 0,
                    },
                ],
                "characteristics": [{"name": "Цвет", "value": "Черный"}],
            },
            {
                "id": "660e8400-e29b-41d4-a716-446655440002",
                "product_id": product_id,
                "name": "256GB White",
                "price": 12999000,
                "discount": 0,
                "cost_price": 10000000,
                "stock_quantity": 0,
                "active_quantity": 0,
                "reserved_quantity": 0,
                "article": "IPH15PM-256-WHT",
                "images": [],
                "characteristics": [{"name": "Цвет", "value": "Белый"}],
            },
        ],
    }
