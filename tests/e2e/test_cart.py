from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.domain.entities.cart import CartIdentity, StoredCartItem
from app.main import app


class FakeCartRepository:
    def __init__(self, items: list[StoredCartItem]) -> None:
        self.items = items
        self.identities: list[CartIdentity] = []

    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        self.identities.append(identity)
        return self.items


class StubB2BCartClient:
    def __init__(
        self,
        *,
        skus: dict[str, dict],
        products: list[dict],
    ) -> None:
        self.skus = skus
        self.products = products
        self.sku_calls: list[str] = []
        self.batch_calls: list[list[str]] = []

    async def get_public_sku(self, sku_id: str) -> dict:
        self.sku_calls.append(sku_id)
        return self.skus[sku_id]

    async def batch_public_products(self, product_ids: list[str]) -> list[dict]:
        self.batch_calls.append(product_ids)
        return [product for product in self.products if product["id"] in product_ids]


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_cart_enriched_with_b2b_data(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440001"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    repository = FakeCartRepository(
        [
            StoredCartItem(
                id="cart-item-1",
                sku_id=sku_id,
                quantity=2,
                updated_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
            )
        ]
    )
    b2b = StubB2BCartClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "256 GB Black",
                "price": 12999000,
                "discount": 500000,
                "active_quantity": 7,
                "article": "IPH15-BLK-256",
                "images": [
                    {
                        "id": "sku-image-1",
                        "url": "https://cdn.neomarket.ru/iphone15-black.jpg",
                        "ordering": 0,
                    }
                ],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "iPhone 15 Pro",
                "status": "MODERATED",
                "images": [],
            }
        ],
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/cart", headers={"X-Session-Id": "guest-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "guest-1"
    assert body["items_count"] == 2
    assert body["subtotal"] == 24998000
    assert body["is_valid"] is True
    assert body["items"][0] == {
        "sku_id": sku_id,
        "product_id": product_id,
        "name": "iPhone 15 Pro 256 GB Black",
        "sku_code": "IPH15-BLK-256",
        "quantity": 2,
        "unit_price": 12499000,
        "unit_price_at_add": None,
        "line_total": 24998000,
        "available_quantity": 7,
        "is_available": True,
        "image": {
            "id": "sku-image-1",
            "url": "https://cdn.neomarket.ru/iphone15-black.jpg",
            "alt": None,
            "ordering": 0,
            "is_main": True,
        },
        "unavailable_reason": None,
    }
    assert b2b.sku_calls == [sku_id]
    assert b2b.batch_calls == [[product_id]]


@pytest.mark.asyncio
async def test_unavailable_sku_shown_with_reason(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440002"
    product_id = "770e8400-e29b-41d4-a716-446655440002"
    repository = FakeCartRepository(
        [StoredCartItem(id="cart-item-2", sku_id=sku_id, quantity=1)]
    )
    b2b = StubB2BCartClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "42",
                "price": 799000,
                "discount": 0,
                "active_quantity": 0,
                "article": "SHOE-42",
                "images": [],
            }
        },
        products=[],
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/cart", headers={"X-Session-Id": "guest-2"})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["is_available"] is False
    assert item["available_quantity"] == 0
    assert item["line_total"] == 0
    assert item["unavailable_reason"] == "OUT_OF_STOCK"
    assert response.json()["subtotal"] == 0
    assert response.json()["is_valid"] is False
