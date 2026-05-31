from datetime import datetime, timezone

import pytest
from jose import jwt
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.cart import get_cart_repository
from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.core.config import settings
from app.domain.entities.cart import CartIdentity, StoredCartItem
from app.main import app


class FakeCartRepository:
    def __init__(self, items: list[StoredCartItem]) -> None:
        self.items = items
        self.identities: list[CartIdentity] = []

    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        self.identities.append(identity)
        return self.items

    async def get_item(
        self,
        identity: CartIdentity,
        sku_id: str,
    ) -> StoredCartItem | None:
        self.identities.append(identity)
        return next((item for item in self.items if item.sku_id == sku_id), None)

    async def add_item(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ) -> None:
        self.identities.append(identity)
        existing = next((item for item in self.items if item.sku_id == sku_id), None)
        if existing is None:
            self.items.append(
                StoredCartItem(
                    id="new-cart-item",
                    sku_id=sku_id,
                    quantity=quantity,
                )
            )
            return
        self.items = [
            StoredCartItem(
                id=item.id,
                sku_id=item.sku_id,
                quantity=(
                    item.quantity + quantity if item.sku_id == sku_id else item.quantity
                ),
                updated_at=item.updated_at,
            )
            for item in self.items
        ]

    async def update_item_quantity(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ) -> None:
        self.identities.append(identity)
        self.items = [
            StoredCartItem(
                id=item.id,
                sku_id=item.sku_id,
                quantity=quantity if item.sku_id == sku_id else item.quantity,
                updated_at=item.updated_at,
            )
            for item in self.items
        ]

    async def delete_item(self, identity: CartIdentity, sku_id: str) -> None:
        self.identities.append(identity)
        self.items = [item for item in self.items if item.sku_id != sku_id]

    async def clear(self, identity: CartIdentity) -> None:
        self.identities.append(identity)
        self.items = []


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


class FakeMergeCartRepository:
    def __init__(
        self,
        *,
        user_id: str,
        session_id: str,
        auth_items: list[StoredCartItem],
        guest_items: list[StoredCartItem],
    ) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.auth_items = auth_items
        self.guest_items = guest_items

    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        if identity.user_id == self.user_id:
            return self.auth_items
        if identity.session_id == self.session_id:
            return self.guest_items
        return []

    async def get_item(
        self,
        identity: CartIdentity,
        sku_id: str,
    ) -> StoredCartItem | None:
        items = await self.list_items(identity)
        return next((item for item in items if item.sku_id == sku_id), None)

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
        assert user_identity.user_id == self.user_id
        assert guest_session_id == self.session_id

        auth_by_sku = {item.sku_id: item for item in self.auth_items}
        merged_guest_items = []
        for guest_item in self.guest_items:
            auth_item = auth_by_sku.get(guest_item.sku_id)
            if auth_item is None:
                self.auth_items.append(guest_item)
                auth_by_sku[guest_item.sku_id] = guest_item
                merged_guest_items.append(guest_item)
                continue
            merged_guest_items.append(guest_item)
            auth_by_sku[guest_item.sku_id] = StoredCartItem(
                id=auth_item.id,
                sku_id=auth_item.sku_id,
                quantity=max(auth_item.quantity, guest_item.quantity),
                updated_at=auth_item.updated_at,
            )

        self.auth_items = [
            auth_by_sku.get(item.sku_id, item)
            for item in self.auth_items
            if item.sku_id in auth_by_sku
        ]
        self.guest_items = [
            item for item in self.guest_items if item not in merged_guest_items
        ]


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


@pytest.mark.asyncio
async def test_add_sku_increments_quantity_if_already_in_cart(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440003"
    product_id = "770e8400-e29b-41d4-a716-446655440003"
    repository = FakeCartRepository(
        [StoredCartItem(id="cart-item-3", sku_id=sku_id, quantity=2)]
    )
    b2b = StubB2BCartClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "M",
                "price": 300000,
                "discount": 0,
                "active_quantity": 5,
                "article": "TSHIRT-M",
                "images": [],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "T-Shirt",
                "status": "MODERATED",
                "images": [],
            }
        ],
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/cart/items",
        headers={"X-Session-Id": "guest-3"},
        json={"sku_id": sku_id, "quantity": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["quantity"] == 4
    assert body["items_count"] == 4
    assert body["subtotal"] == 1200000


@pytest.mark.asyncio
async def test_patch_cart_item_quantity(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440004"
    product_id = "770e8400-e29b-41d4-a716-446655440004"
    repository = FakeCartRepository(
        [StoredCartItem(id="cart-item-4", sku_id=sku_id, quantity=2)]
    )
    b2b = StubB2BCartClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "XL",
                "price": 400000,
                "discount": 50000,
                "active_quantity": 8,
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
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.patch(
        f"/api/v1/cart/items/{sku_id}",
        headers={"X-Session-Id": "guest-4"},
        json={"quantity": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["quantity"] == 3
    assert body["items_count"] == 3
    assert body["subtotal"] == 1050000


@pytest.mark.asyncio
async def test_patch_cart_item_quantity_rejects_insufficient_stock(
    client: AsyncClient,
):
    sku_id = "660e8400-e29b-41d4-a716-446655440005"
    product_id = "770e8400-e29b-41d4-a716-446655440005"
    repository = FakeCartRepository(
        [StoredCartItem(id="cart-item-5", sku_id=sku_id, quantity=1)]
    )
    b2b = StubB2BCartClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "One size",
                "price": 150000,
                "discount": 0,
                "active_quantity": 2,
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
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.patch(
        f"/api/v1/cart/items/{sku_id}",
        headers={"X-Session-Id": "guest-5"},
        json={"quantity": 3},
    )

    assert response.status_code == 409
    assert response.json() == {"code": "CONFLICT", "message": "Insufficient stock"}
    assert repository.items[0].quantity == 1


@pytest.mark.asyncio
async def test_delete_cart_item_returns_updated_cart(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440006"
    kept_sku_id = "660e8400-e29b-41d4-a716-446655440007"
    product_id = "770e8400-e29b-41d4-a716-446655440006"
    repository = FakeCartRepository(
        [
            StoredCartItem(id="cart-item-6", sku_id=sku_id, quantity=1),
            StoredCartItem(id="cart-item-7", sku_id=kept_sku_id, quantity=2),
        ]
    )
    b2b = StubB2BCartClient(
        skus={
            kept_sku_id: {
                "id": kept_sku_id,
                "product_id": product_id,
                "name": "Blue",
                "price": 250000,
                "discount": 0,
                "active_quantity": 4,
                "article": "BAG-BLUE",
                "images": [],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "Bag",
                "status": "MODERATED",
                "images": [],
            }
        ],
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.delete(
        f"/api/v1/cart/items/{sku_id}",
        headers={"X-Session-Id": "guest-6"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["sku_id"] for item in body["items"]] == [kept_sku_id]
    assert body["items_count"] == 2
    assert body["subtotal"] == 500000


@pytest.mark.asyncio
async def test_delete_missing_cart_item_returns_404(client: AsyncClient):
    repository = FakeCartRepository([])
    b2b = StubB2BCartClient(skus={}, products=[])
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.delete(
        "/api/v1/cart/items/660e8400-e29b-41d4-a716-446655440099",
        headers={"X-Session-Id": "guest-7"},
    )

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Cart item not found"}


@pytest.mark.asyncio
async def test_clear_cart_returns_204(client: AsyncClient):
    repository = FakeCartRepository(
        [
            StoredCartItem(
                id="cart-item-8",
                sku_id="660e8400-e29b-41d4-a716-446655440008",
                quantity=1,
            )
        ]
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository

    response = await client.delete(
        "/api/v1/cart",
        headers={"X-Session-Id": "guest-8"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert repository.items == []


@pytest.mark.asyncio
async def test_validate_cart_returns_issues(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440009"
    product_id = "770e8400-e29b-41d4-a716-446655440009"
    repository = FakeCartRepository(
        [StoredCartItem(id="cart-item-9", sku_id=sku_id, quantity=3)]
    )
    b2b = StubB2BCartClient(
        skus={
            sku_id: {
                "id": sku_id,
                "product_id": product_id,
                "name": "Green",
                "price": 90000,
                "discount": 0,
                "active_quantity": 2,
                "article": "SOCKS-GREEN",
                "images": [],
            }
        },
        products=[
            {
                "id": product_id,
                "title": "Socks",
                "status": "MODERATED",
                "images": [],
            }
        ],
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/cart/validate",
        headers={"X-Session-Id": "guest-9"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert body["cart"]["is_valid"] is False
    assert body["issues"] == [
        {
            "sku_id": sku_id,
            "type": "QUANTITY_REDUCED",
            "message": "Requested quantity exceeds available stock",
            "old_value": 3,
            "new_value": 2,
        }
    ]


@pytest.mark.asyncio
async def test_validate_cart_returns_valid_empty_issues(client: AsyncClient):
    sku_id = "660e8400-e29b-41d4-a716-446655440010"
    product_id = "770e8400-e29b-41d4-a716-446655440010"
    repository = FakeCartRepository(
        [StoredCartItem(id="cart-item-10", sku_id=sku_id, quantity=1)]
    )
    b2b = StubB2BCartClient(
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
    )
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/cart/validate",
        headers={"X-Session-Id": "guest-10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["cart"]["subtotal"] == 100000
    assert body["issues"] == []


@pytest.mark.asyncio
async def test_guest_cart_merged_on_login(client: AsyncClient):
    user_id = "11111111-1111-1111-1111-111111111111"
    session_id = "guest-merge-1"
    shared_sku_id = "660e8400-e29b-41d4-a716-446655440011"
    guest_only_sku_id = "660e8400-e29b-41d4-a716-446655440012"
    product_id = "770e8400-e29b-41d4-a716-446655440011"
    repository = FakeMergeCartRepository(
        user_id=user_id,
        session_id=session_id,
        auth_items=[
            StoredCartItem(id="auth-cart-item-1", sku_id=shared_sku_id, quantity=2)
        ],
        guest_items=[
            StoredCartItem(id="guest-cart-item-1", sku_id=shared_sku_id, quantity=5),
            StoredCartItem(id="guest-cart-item-2", sku_id=guest_only_sku_id, quantity=3),
        ],
    )
    b2b = StubB2BCartClient(
        skus={
            shared_sku_id: {
                "id": shared_sku_id,
                "product_id": product_id,
                "name": "Black",
                "price": 100000,
                "discount": 0,
                "active_quantity": 10,
                "article": "MUG-BLACK",
                "images": [],
            },
            guest_only_sku_id: {
                "id": guest_only_sku_id,
                "product_id": product_id,
                "name": "White",
                "price": 120000,
                "discount": 0,
                "active_quantity": 10,
                "article": "MUG-WHITE",
                "images": [],
            },
        },
        products=[
            {
                "id": product_id,
                "title": "Mug",
                "status": "MODERATED",
                "images": [],
            }
        ],
    )
    token = jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm="HS256")
    app.dependency_overrides[get_cart_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        "/api/v1/cart/merge",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Session-Id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    quantities = {item["sku_id"]: item["quantity"] for item in body["items"]}
    assert quantities == {shared_sku_id: 5, guest_only_sku_id: 3}
    assert body["items_count"] == 8
    assert body["subtotal"] == 860000
    assert repository.guest_items == []
