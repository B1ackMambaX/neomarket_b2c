from dataclasses import replace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.events import get_product_event_repository
from app.core.config import settings
from app.domain.entities.cart import CartIdentity, StoredCartItem
from app.main import app
from tests.e2e.test_orders import make_order


class TrackingCartRepository:
    def __init__(self, items: list[StoredCartItem]) -> None:
        self.items = list(items)
        self.mark_calls: list[tuple[list[str], str]] = []

    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        return self.items

    async def get_item(
        self,
        identity: CartIdentity,
        sku_id: str,
    ) -> StoredCartItem | None:
        return next((item for item in self.items if item.sku_id == sku_id), None)

    async def add_item(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ) -> None:
        raise NotImplementedError

    async def update_item_quantity(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ) -> None:
        raise NotImplementedError

    async def delete_item(self, identity: CartIdentity, sku_id: str) -> None:
        raise NotImplementedError

    async def clear(self, identity: CartIdentity) -> None:
        raise NotImplementedError

    async def merge_guest_cart(
        self,
        user_identity: CartIdentity,
        guest_session_id: str,
    ) -> None:
        raise NotImplementedError

    async def mark_unavailable_by_sku_ids(
        self,
        sku_ids: list[str],
        unavailable_reason: str,
    ) -> int:
        self.mark_calls.append((list(sku_ids), unavailable_reason))
        updated = 0
        new_items: list[StoredCartItem] = []
        for item in self.items:
            if item.sku_id in sku_ids:
                new_items.append(
                    replace(item, unavailable_reason=unavailable_reason)
                )
                updated += 1
            else:
                new_items.append(item)
        self.items = new_items
        return updated


class FakeProductEventRepository:
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.register_calls: list[tuple[str, str]] = []

    async def register_idempotency_key(
        self,
        idempotency_key: str,
        event_type: str,
    ) -> bool:
        self.register_calls.append((idempotency_key, event_type))
        if idempotency_key in self.keys:
            return False
        self.keys.add(idempotency_key)
        return True


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def service_headers() -> dict[str, str]:
    return {"X-Service-Key": settings.B2B_TO_B2C_SERVICE_KEY}


def product_blocked_payload(
    *,
    idempotency_key: str = "d7e8f9a0-b1c2-3456-abcd-789012345678",
    sku_ids: list[str] | None = None,
) -> dict:
    return {
        "idempotency_key": idempotency_key,
        "event": "PRODUCT_BLOCKED",
        "product_id": "550e8400-e29b-41d4-a716-446655440000",
        "sku_ids": sku_ids
        or [
            "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "8a4e3f9c-1a2b-4c8d-9e5f-6b7a8c9d0e1f",
        ],
        "reason": "Описание не соответствует товару",
        "date": "2026-04-16T12:00:00Z",
    }


@pytest.mark.asyncio
async def test_product_blocked_marks_cart_items_unavailable(client: AsyncClient):
    sku_ids = [
        "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "8a4e3f9c-1a2b-4c8d-9e5f-6b7a8c9d0e1f",
    ]
    cart_repository = TrackingCartRepository(
        [
            StoredCartItem(id="cart-1", sku_id=sku_ids[0], quantity=2),
            StoredCartItem(id="cart-2", sku_id=sku_ids[1], quantity=1),
            StoredCartItem(
                id="cart-3",
                sku_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                quantity=1,
            ),
        ]
    )
    product_event_repository = FakeProductEventRepository()
    app.dependency_overrides[get_cart_repository] = lambda: cart_repository
    app.dependency_overrides[get_product_event_repository] = (
        lambda: product_event_repository
    )

    response = await client.post(
        "/api/v1/b2b/events",
        headers=service_headers(),
        json=product_blocked_payload(sku_ids=sku_ids),
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == [(sku_ids, "PRODUCT_BLOCKED")]
    assert cart_repository.items[0].unavailable_reason == "PRODUCT_BLOCKED"
    assert cart_repository.items[1].unavailable_reason == "PRODUCT_BLOCKED"
    assert cart_repository.items[2].unavailable_reason is None


@pytest.mark.asyncio
async def test_orders_not_affected_by_product_blocked(client: AsyncClient):
    sku_id = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    order_before = replace(
        make_order(status="PAID"),
        items=[replace(make_order().items[0], sku_id=sku_id)],
    )
    cart_repository = TrackingCartRepository(
        [StoredCartItem(id="cart-1", sku_id=sku_id, quantity=1)]
    )
    product_event_repository = FakeProductEventRepository()
    app.dependency_overrides[get_cart_repository] = lambda: cart_repository
    app.dependency_overrides[get_product_event_repository] = (
        lambda: product_event_repository
    )

    response = await client.post(
        "/api/v1/b2b/events",
        headers=service_headers(),
        json=product_blocked_payload(
            sku_ids=[sku_id],
            idempotency_key="e8f9a0b1-c2d3-4567-abcd-890123456789",
        ),
    )

    assert response.status_code == 202
    assert order_before.status == "PAID"
    assert order_before.items[0].sku_id == sku_id
    assert order_before.items[0].unit_price == 11999000
    assert cart_repository.items[0].unavailable_reason == "PRODUCT_BLOCKED"


@pytest.mark.asyncio
async def test_idempotent_event_no_side_effects(client: AsyncClient):
    sku_id = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    idempotency_key = "f9a0b1c2-d3e4-5678-abcd-901234567890"
    cart_repository = TrackingCartRepository(
        [StoredCartItem(id="cart-1", sku_id=sku_id, quantity=1)]
    )
    product_event_repository = FakeProductEventRepository()
    app.dependency_overrides[get_cart_repository] = lambda: cart_repository
    app.dependency_overrides[get_product_event_repository] = (
        lambda: product_event_repository
    )
    payload = product_blocked_payload(
        sku_ids=[sku_id],
        idempotency_key=idempotency_key,
    )

    first = await client.post(
        "/api/v1/b2b/events",
        headers=service_headers(),
        json=payload,
    )
    second = await client.post(
        "/api/v1/b2b/events",
        headers=service_headers(),
        json=payload,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json() == {"accepted": True}
    assert len(cart_repository.mark_calls) == 1
    assert len(product_event_repository.register_calls) == 2


@pytest.mark.asyncio
async def test_missing_service_key_returns_401(client: AsyncClient):
    response = await client.post(
        "/api/v1/b2b/events",
        json=product_blocked_payload(),
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_product_deleted_marks_cart_items_unavailable(client: AsyncClient):
    sku_id = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    cart_repository = TrackingCartRepository(
        [
            StoredCartItem(id="cart-1", sku_id=sku_id, quantity=1),
            StoredCartItem(
                id="cart-2",
                sku_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                quantity=2,
            ),
        ]
    )
    product_event_repository = FakeProductEventRepository()
    app.dependency_overrides[get_cart_repository] = lambda: cart_repository
    app.dependency_overrides[get_product_event_repository] = (
        lambda: product_event_repository
    )

    payload = {
        "idempotency_key": "e8f9a0b1-c2d3-4567-abcd-890123456789",
        "event": "PRODUCT_DELETED",
        "product_id": "550e8400-e29b-41d4-a716-446655440000",
        "sku_ids": [sku_id],
        "reason": None,
        "date": "2026-04-16T12:00:00Z",
    }

    response = await client.post(
        "/api/v1/b2b/events",
        headers=service_headers(),
        json=payload,
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == [([sku_id], "PRODUCT_DELETED")]
    assert cart_repository.items[0].unavailable_reason == "PRODUCT_DELETED"
    assert cart_repository.items[1].unavailable_reason is None


@pytest.mark.asyncio
async def test_sku_out_of_stock_marks_cart_items_unavailable(client: AsyncClient):
    sku_id = "8a4e3f9c-1a2b-4c8d-9e5f-6b7a8c9d0e1f"
    cart_repository = TrackingCartRepository(
        [
            StoredCartItem(id="cart-1", sku_id=sku_id, quantity=3),
            StoredCartItem(
                id="cart-2",
                sku_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                quantity=1,
            ),
        ]
    )
    product_event_repository = FakeProductEventRepository()
    app.dependency_overrides[get_cart_repository] = lambda: cart_repository
    app.dependency_overrides[get_product_event_repository] = (
        lambda: product_event_repository
    )

    payload = {
        "idempotency_key": "f9a0b1c2-d3e4-5678-abcd-901234567890",
        "event": "SKU_OUT_OF_STOCK",
        "product_id": "550e8400-e29b-41d4-a716-446655440000",
        "sku_ids": [sku_id],
        "reason": None,
        "date": "2026-04-16T12:30:00Z",
    }

    response = await client.post(
        "/api/v1/b2b/events",
        headers=service_headers(),
        json=payload,
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == [([sku_id], "OUT_OF_STOCK")]
    assert cart_repository.items[0].unavailable_reason == "OUT_OF_STOCK"
    assert cart_repository.items[1].unavailable_reason is None
