from dataclasses import replace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.catalog import (
    get_b2b_catalog_client,
    get_catalog_snapshot_repository,
)
from app.api.v1.dependencies.events import get_product_event_repository
from app.core.config import settings
from app.domain.entities.cart import CartIdentity, StoredCartItem
from app.main import app
from tests.e2e.test_orders import make_order

PRODUCT_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_PRODUCT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
EVENTS_URL = "/api/v1/b2b/events"


class StubB2BSkuClient:
    def __init__(
        self,
        sku_to_product: dict[str, str],
        products: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.sku_to_product = sku_to_product
        self.products = products or {}

    async def get_public_sku(self, sku_id: str) -> dict[str, Any]:
        return {
            "id": sku_id,
            "product_id": self.sku_to_product[sku_id],
        }

    async def get_public_product(self, product_id: str) -> dict[str, Any]:
        return self.products[product_id]


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

    async def list_distinct_sku_ids(self) -> list[str]:
        seen: set[str] = set()
        sku_ids: list[str] = []
        for item in self.items:
            if item.sku_id not in seen:
                seen.add(item.sku_id)
                sku_ids.append(item.sku_id)
        return sku_ids

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


class FakeCatalogSnapshotRepository:
    def __init__(self, snapshots: dict[str, dict[str, Any]] | None = None) -> None:
        self._snapshots: dict[str, dict[str, Any]] = snapshots or {}

    async def upsert(
        self, *, product_id, category_id, title, characteristics, min_price, has_stock
    ) -> None:
        self._snapshots[product_id] = dict(
            category_id=category_id,
            title=title,
            characteristics=characteristics,
            min_price=min_price,
            has_stock=has_stock,
            is_active=True,
        )

    async def deactivate(self, product_id: str) -> None:
        if product_id in self._snapshots:
            self._snapshots[product_id]["is_active"] = False

    async def set_stock(self, *, product_id: str, has_stock: bool) -> None:
        if product_id in self._snapshots:
            self._snapshots[product_id]["has_stock"] = has_stock

    async def set_min_price(self, *, product_id: str, min_price: int) -> None:
        if product_id in self._snapshots:
            self._snapshots[product_id]["min_price"] = min_price

    async def get_facets(self, *, category_id, filters) -> list[dict]:
        return []


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
    product_id: str = PRODUCT_ID,
    reason: str = "Описание не соответствует товару",
) -> dict:
    return {
        "idempotency_key": idempotency_key,
        "event_type": "PRODUCT_BLOCKED",
        "occurred_at": "2026-04-16T12:00:00Z",
        "payload": {
            "product_id": product_id,
            "reason": reason,
        },
    }


def setup_event_dependencies(
    *,
    cart_repository: TrackingCartRepository,
    product_event_repository: FakeProductEventRepository,
    sku_to_product: dict[str, str],
    catalog_snapshot_repository: FakeCatalogSnapshotRepository | None = None,
    product_payloads: dict[str, dict[str, Any]] | None = None,
) -> None:
    snapshot_repository = catalog_snapshot_repository or FakeCatalogSnapshotRepository()
    app.dependency_overrides[get_cart_repository] = lambda: cart_repository
    app.dependency_overrides[get_product_event_repository] = (
        lambda: product_event_repository
    )
    app.dependency_overrides[get_catalog_snapshot_repository] = (
        lambda: snapshot_repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = (
        lambda: StubB2BSkuClient(sku_to_product, products=product_payloads)
    )


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
                sku_id="cccccccc-dddd-eeee-ffff-000000000001",
                quantity=1,
            ),
        ]
    )
    product_event_repository = FakeProductEventRepository()
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={
            sku_ids[0]: PRODUCT_ID,
            sku_ids[1]: PRODUCT_ID,
            "cccccccc-dddd-eeee-ffff-000000000001": OTHER_PRODUCT_ID,
        },
    )

    response = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=product_blocked_payload(),
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == [(sku_ids, "PRODUCT_BLOCKED")]
    assert cart_repository.items[0].unavailable_reason == "PRODUCT_BLOCKED"
    assert cart_repository.items[1].unavailable_reason == "PRODUCT_BLOCKED"
    assert cart_repository.items[2].unavailable_reason is None


@pytest.mark.asyncio
async def test_product_hard_blocked_marks_cart_items_unavailable(client: AsyncClient):
    sku_id = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    cart_repository = TrackingCartRepository(
        [StoredCartItem(id="cart-1", sku_id=sku_id, quantity=1)]
    )
    product_event_repository = FakeProductEventRepository()
    snapshot_repository = FakeCatalogSnapshotRepository(
        {PRODUCT_ID: {"is_active": True, "min_price": 100000}}
    )
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={sku_id: PRODUCT_ID},
        catalog_snapshot_repository=snapshot_repository,
    )
    payload = product_blocked_payload(
        idempotency_key="d8e9f0a1-b2c3-4567-abcd-789012345678"
    )
    payload["event_type"] = "PRODUCT_HARD_BLOCKED"

    response = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=payload,
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == [([sku_id], "PRODUCT_BLOCKED")]
    assert cart_repository.items[0].unavailable_reason == "PRODUCT_BLOCKED"
    assert snapshot_repository._snapshots[PRODUCT_ID]["is_active"] is False


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
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={sku_id: PRODUCT_ID},
    )

    response = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=product_blocked_payload(
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
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={sku_id: PRODUCT_ID},
    )
    payload = product_blocked_payload(idempotency_key=idempotency_key)

    first = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=payload,
    )
    second = await client.post(
        EVENTS_URL,
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
        EVENTS_URL,
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
                sku_id="cccccccc-dddd-eeee-ffff-000000000001",
                quantity=2,
            ),
        ]
    )
    product_event_repository = FakeProductEventRepository()
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={
            sku_id: PRODUCT_ID,
            "cccccccc-dddd-eeee-ffff-000000000001": OTHER_PRODUCT_ID,
        },
    )

    payload = {
        "idempotency_key": "e8f9a0b1-c2d3-4567-abcd-890123456789",
        "event_type": "PRODUCT_DELETED",
        "occurred_at": "2026-04-16T12:00:00Z",
        "payload": {
            "product_id": PRODUCT_ID,
            "reason": None,
        },
    }

    response = await client.post(
        EVENTS_URL,
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
    same_product_sku_id = "9b5f4a0d-2b3c-4d9e-8f6a-7c8d9e0f1a2b"
    cart_repository = TrackingCartRepository(
        [
            StoredCartItem(id="cart-1", sku_id=sku_id, quantity=3),
            StoredCartItem(id="cart-2", sku_id=same_product_sku_id, quantity=1),
            StoredCartItem(
                id="cart-3",
                sku_id="cccccccc-dddd-eeee-ffff-000000000001",
                quantity=1,
            ),
        ]
    )
    product_event_repository = FakeProductEventRepository()
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={
            sku_id: PRODUCT_ID,
            same_product_sku_id: PRODUCT_ID,
            "cccccccc-dddd-eeee-ffff-000000000001": OTHER_PRODUCT_ID,
        },
    )

    payload = {
        "idempotency_key": "f9a0b1c2-d3e4-5678-abcd-901234567890",
        "event_type": "SKU_OUT_OF_STOCK",
        "occurred_at": "2026-04-16T12:30:00Z",
        "payload": {
            "product_id": PRODUCT_ID,
            "sku_id": sku_id,
            "available_quantity": 0,
        },
    }

    response = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=payload,
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == [([sku_id], "OUT_OF_STOCK")]
    assert cart_repository.items[0].unavailable_reason == "OUT_OF_STOCK"
    assert cart_repository.items[1].unavailable_reason is None
    assert cart_repository.items[2].unavailable_reason is None


@pytest.mark.asyncio
async def test_price_changed_refreshes_catalog_snapshot(client: AsyncClient):
    sku_id = "8a4e3f9c-1a2b-4c8d-9e5f-6b7a8c9d0e1f"
    cart_repository = TrackingCartRepository([])
    product_event_repository = FakeProductEventRepository()
    snapshot_repository = FakeCatalogSnapshotRepository()
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={sku_id: PRODUCT_ID},
        catalog_snapshot_repository=snapshot_repository,
        product_payloads={
            PRODUCT_ID: {
                "id": PRODUCT_ID,
                "title": "NeoPhone",
                "category_id": "category-1",
                "characteristics": [{"name": "brand", "value": "Neo"}],
                "min_price": 899000,
                "has_stock": True,
            }
        },
    )

    payload = {
        "idempotency_key": "a0b1c2d3-e4f5-6789-abcd-012345678901",
        "event_type": "PRICE_CHANGED",
        "occurred_at": "2026-04-16T12:45:00Z",
        "payload": {
            "product_id": PRODUCT_ID,
            "sku_id": sku_id,
            "old_price": 999000,
            "new_price": 899000,
        },
    }

    response = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=payload,
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert cart_repository.mark_calls == []
    assert snapshot_repository._snapshots[PRODUCT_ID] == {
        "category_id": "category-1",
        "title": "NeoPhone",
        "characteristics": [{"name": "brand", "value": "Neo"}],
        "min_price": 899000,
        "has_stock": True,
        "is_active": True,
    }


@pytest.mark.parametrize("event_type", ["PRODUCT_CREATED", "PRODUCT_UPDATED"])
@pytest.mark.asyncio
async def test_unsupported_product_event_type_returns_422(
    client: AsyncClient,
    event_type: str,
):
    cart_repository = TrackingCartRepository([])
    product_event_repository = FakeProductEventRepository()
    setup_event_dependencies(
        cart_repository=cart_repository,
        product_event_repository=product_event_repository,
        sku_to_product={},
    )
    payload = product_blocked_payload(
        idempotency_key="b1c2d3e4-f5a6-7890-abcd-123456789012"
    )
    payload["event_type"] = event_type

    response = await client.post(
        EVENTS_URL,
        headers=service_headers(),
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
