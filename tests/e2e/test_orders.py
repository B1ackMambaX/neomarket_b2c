from datetime import datetime, timezone

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Request, Response
from jose import jwt

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.api.v1.dependencies.orders import get_order_repository
from app.core.config import settings
from app.domain.entities.cart import CartIdentity
from app.domain.entities.order import StoredOrder
from app.main import app


class FakeOrderRepository:
    def __init__(self) -> None:
        self.orders: list[StoredOrder] = []

    async def get_by_idempotency_key(self, idempotency_key: str) -> StoredOrder | None:
        return next(
            (
                order
                for order in self.orders
                if order.idempotency_key == idempotency_key
            ),
            None,
        )

    async def create_or_get_by_idempotency_key(
        self,
        order: StoredOrder,
    ) -> tuple[StoredOrder, bool]:
        existing = await self.get_by_idempotency_key(order.idempotency_key)
        if existing is not None:
            return existing, False
        self.orders.append(order)
        return order, True

    async def delete(self, order_id: str) -> None:
        self.orders = [order for order in self.orders if order.id != order_id]


class EmptyCartRepository:
    async def list_items(self, identity: CartIdentity):
        return []

    async def get_item(self, identity: CartIdentity, sku_id: str):
        return None

    async def add_item(self, identity: CartIdentity, sku_id: str, quantity: int):
        raise NotImplementedError

    async def update_item_quantity(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ):
        raise NotImplementedError

    async def delete_item(self, identity: CartIdentity, sku_id: str):
        raise NotImplementedError

    async def clear(self, identity: CartIdentity):
        raise NotImplementedError

    async def merge_guest_cart(
        self,
        user_identity: CartIdentity,
        guest_session_id: str,
    ):
        raise NotImplementedError


class StubB2BOrdersClient:
    def __init__(
        self,
        *,
        skus: dict[str, dict],
        products: list[dict],
        reserve_error: Exception | None = None,
    ) -> None:
        self.skus = skus
        self.products = products
        self.reserve_error = reserve_error
        self.reserve_calls: list[dict] = []

    async def get_public_sku(self, sku_id: str) -> dict:
        if sku_id not in self.skus:
            req = httpx.Request("GET", f"http://b2b/api/v1/public/skus/{sku_id}")
            raise httpx.HTTPStatusError(
                "Not Found",
                request=req,
                response=httpx.Response(404, request=req),
            )
        return self.skus[sku_id]

    async def batch_public_products(self, product_ids: list[str]) -> list[dict]:
        return [product for product in self.products if product["id"] in product_ids]

    async def reserve_inventory(
        self,
        *,
        idempotency_key: str,
        order_id: str,
        items: list[dict],
    ) -> dict:
        self.reserve_calls.append(
            {
                "idempotency_key": idempotency_key,
                "order_id": order_id,
                "items": items,
            }
        )
        if self.reserve_error:
            raise self.reserve_error
        return {
            "order_id": order_id,
            "status": "RESERVED",
            "reserved_at": datetime.now(timezone.utc).isoformat(),
        }


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(
    *,
    buyer_id: str = "11111111-1111-1111-1111-111111111111",
    idempotency_key: str = "22222222-2222-4222-8222-222222222222",
) -> dict[str, str]:
    token = jwt.encode({"sub": buyer_id}, settings.SECRET_KEY, algorithm="HS256")
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": idempotency_key,
    }


@pytest.mark.asyncio
async def test_checkout_creates_paid_order_with_fixed_prices(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440001"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    # B2B computed price: 12999000 - 500000 = 12499000.
    # Snapshot price is intentionally different to prove it takes precedence.
    snapshot_price = 11999000
    order_repository = FakeOrderRepository()
    b2b = StubB2BOrdersClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "256 GB Black",
                "price": 12999000,
                "discount": 500000,
                "active_quantity": 4,
                "article": "IPH15-BLK-256",
                "images": [{"url": "https://cdn.neomarket.local/iphone.jpg"}],
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
    app.dependency_overrides[get_order_repository] = lambda: order_repository
    app.dependency_overrides[get_cart_repository] = lambda: EmptyCartRepository()
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/orders",
        headers=auth_headers(),
        json={
            "address_id": "33333333-3333-4333-8333-333333333333",
            "payment_method_id": "44444444-4444-4444-8444-444444444444",
            "items_snapshot": [
                {"sku_id": sku_id, "quantity": 2, "unit_price": snapshot_price}
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PAID"
    assert body["items"][0]["unit_price"] == snapshot_price
    assert body["items"][0]["line_total"] == snapshot_price * 2
    assert body["subtotal"] == snapshot_price * 2
    assert body["total"] == snapshot_price * 2
    assert b2b.reserve_calls[0]["items"] == [{"sku_id": sku_id, "quantity": 2}]

    stored_item = order_repository.orders[0].items[0]
    assert stored_item.product_title == "iPhone 15 Pro"
    assert stored_item.sku_name == "256 GB Black"
    assert stored_item.unit_price == snapshot_price


@pytest.mark.asyncio
async def test_partial_reserve_failure_returns_409(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440002"
    product_id = "770e8400-e29b-41d4-a716-446655440002"
    failed_items = [
        {
            "sku_id": sku_id,
            "requested": 2,
            "available": 1,
            "reason": "INSUFFICIENT_STOCK",
        }
    ]
    request = Request("POST", "http://b2b/api/v1/inventory/reserve")
    reserve_response = Response(
        status_code=409,
        request=request,
        json={"details": {"failed_items": failed_items}},
    )
    order_repository = FakeOrderRepository()
    b2b = StubB2BOrdersClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "XL",
                "price": 100000,
                "discount": 0,
                "active_quantity": 2,
                "article": "HOODIE-XL",
                "images": [],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "Hoodie",
                "status": "MODERATED",
                "images": [],
            }
        ],
        reserve_error=httpx.HTTPStatusError(
            "reserve failed",
            request=request,
            response=reserve_response,
        ),
    )
    app.dependency_overrides[get_order_repository] = lambda: order_repository
    app.dependency_overrides[get_cart_repository] = lambda: EmptyCartRepository()
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/orders",
        headers=auth_headers(idempotency_key="22222222-2222-4222-8222-222222222223"),
        json={
            "address_id": "33333333-3333-4333-8333-333333333333",
            "payment_method_id": "44444444-4444-4444-8444-444444444444",
            "items_snapshot": [{"sku_id": sku_id, "quantity": 2, "unit_price": 100000}],
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "RESERVE_FAILED",
        "message": "Failed to reserve order items",
        "failed_items": failed_items,
    }
    assert order_repository.orders == []


@pytest.mark.asyncio
async def test_idempotency_returns_existing_order(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440003"
    product_id = "770e8400-e29b-41d4-a716-446655440003"
    order_repository = FakeOrderRepository()
    b2b = StubB2BOrdersClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "One size",
                "price": 50000,
                "discount": 0,
                "active_quantity": 5,
                "article": "CAP-OS",
                "images": [],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "Cap",
                "status": "MODERATED",
                "images": [],
            }
        ],
    )
    app.dependency_overrides[get_order_repository] = lambda: order_repository
    app.dependency_overrides[get_cart_repository] = lambda: EmptyCartRepository()
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b
    headers = auth_headers(idempotency_key="22222222-2222-4222-8222-222222222224")
    payload = {
        "address_id": "33333333-3333-4333-8333-333333333333",
        "payment_method_id": "44444444-4444-4444-8444-444444444444",
        "items_snapshot": [{"sku_id": sku_id, "quantity": 1, "unit_price": 50000}],
    }

    first = await client.post("/api/v1/orders", headers=headers, json=payload)
    second = await client.post("/api/v1/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert len(order_repository.orders) == 1
    assert len(b2b.reserve_calls) == 1


@pytest.mark.asyncio
async def test_b2b_unavailable_returns_503(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440004"
    product_id = "770e8400-e29b-41d4-a716-446655440004"
    order_repository = FakeOrderRepository()
    b2b = StubB2BOrdersClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "Red",
                "price": 120000,
                "discount": 20000,
                "active_quantity": 5,
                "article": "BELT-RED",
                "images": [],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "Belt",
                "status": "MODERATED",
                "images": [],
            }
        ],
        reserve_error=httpx.ConnectError("failed to connect"),
    )
    app.dependency_overrides[get_order_repository] = lambda: order_repository
    app.dependency_overrides[get_cart_repository] = lambda: EmptyCartRepository()
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/orders",
        headers=auth_headers(idempotency_key="22222222-2222-4222-8222-222222222225"),
        json={
            "address_id": "33333333-3333-4333-8333-333333333333",
            "payment_method_id": "44444444-4444-4444-8444-444444444444",
            "items_snapshot": [{"sku_id": sku_id, "quantity": 1, "unit_price": 100000}],
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "B2B_UNAVAILABLE",
        "message": "Product service is temporarily unavailable",
    }
    assert order_repository.orders == []


@pytest.mark.asyncio
async def test_missing_idempotency_key_returns_error_shape(client: AsyncClient):
    response = await client.post(
        "/api/v1/orders",
        headers={
            "Authorization": auth_headers()["Authorization"],
        },
        json={
            "address_id": "33333333-3333-4333-8333-333333333333",
            "payment_method_id": "44444444-4444-4444-8444-444444444444",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Invalid request"
