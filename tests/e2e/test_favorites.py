from datetime import datetime, timezone

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.api.v1.dependencies.catalog import get_b2b_catalog_client
from app.api.v1.dependencies.favorites import (
    get_favorites_repository,
    get_product_subscriptions_repository,
)
from app.core.config import settings
from app.domain.entities.favorite import StoredFavorite
from app.domain.entities.subscription import StoredProductSubscription
from app.main import app


class FakeFavoritesRepository:
    def __init__(self, favorites: list[StoredFavorite] | None = None) -> None:
        self.favorites = favorites or []
        self.list_calls: list[dict] = []
        self.add_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[StoredFavorite]:
        self.list_calls.append({"user_id": user_id, "limit": limit, "offset": offset})
        user_favorites = [
            favorite for favorite in self.favorites if favorite.user_id == user_id
        ]
        return user_favorites[offset : offset + limit]

    async def add(
        self,
        user_id: str,
        product_id: str,
    ) -> tuple[StoredFavorite, bool]:
        self.add_calls.append({"user_id": user_id, "product_id": product_id})
        existing = next(
            (
                favorite
                for favorite in self.favorites
                if favorite.user_id == user_id and favorite.product_id == product_id
            ),
            None,
        )
        if existing is not None:
            return existing, False

        favorite = StoredFavorite(
            id=f"favorite-{len(self.favorites) + 1}",
            user_id=user_id,
            product_id=product_id,
            added_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        )
        self.favorites.append(favorite)
        return favorite, True

    async def delete(self, user_id: str, product_id: str) -> None:
        self.delete_calls.append({"user_id": user_id, "product_id": product_id})
        self.favorites = [
            favorite
            for favorite in self.favorites
            if favorite.user_id != user_id or favorite.product_id != product_id
        ]


class StubB2BFavoritesClient:
    def __init__(self, products: list[dict]) -> None:
        self.products = products
        self.batch_calls: list[list[str]] = []

    async def batch_public_products(self, product_ids: list[str]) -> list[dict]:
        self.batch_calls.append(product_ids)
        return [product for product in self.products if product["id"] in product_ids]


class FakeProductSubscriptionsRepository:
    def __init__(
        self,
        subscriptions: list[StoredProductSubscription] | None = None,
    ) -> None:
        self.subscriptions = subscriptions or []
        self.add_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    async def get(
        self,
        user_id: str,
        product_id: str,
    ) -> StoredProductSubscription | None:
        self.get_calls.append({"user_id": user_id, "product_id": product_id})
        return next(
            (
                subscription
                for subscription in self.subscriptions
                if subscription.user_id == user_id
                and subscription.product_id == product_id
            ),
            None,
        )

    async def add(
        self,
        user_id: str,
        product_id: str,
        events: list[str],
    ) -> tuple[StoredProductSubscription, bool]:
        self.add_calls.append(
            {
                "user_id": user_id,
                "product_id": product_id,
                "events": events,
            }
        )
        existing = await self.get(user_id, product_id)
        if existing is not None:
            return existing, False

        subscription = StoredProductSubscription(
            id=f"subscription-{len(self.subscriptions) + 1}",
            user_id=user_id,
            product_id=product_id,
            events=tuple(events),
            created_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )
        self.subscriptions.append(subscription)
        return subscription, True

    async def delete(self, user_id: str, product_id: str) -> None:
        self.delete_calls.append({"user_id": user_id, "product_id": product_id})
        self.subscriptions = [
            subscription
            for subscription in self.subscriptions
            if subscription.user_id != user_id
            or subscription.product_id != product_id
        ]


class UnavailableB2BFavoritesClient:
    async def batch_public_products(self, product_ids: list[str]) -> list[dict]:
        raise httpx.ConnectError("B2B unavailable")


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(user_id: str = "11111111-1111-4111-8111-111111111111"):
    token = jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def product_payload(
    product_id: str = "770e8400-e29b-41d4-a716-446655440001",
    *,
    title: str = "iPhone 15 Pro",
) -> dict:
    return {
        "id": product_id,
        "title": title,
        "slug": "iphone-15-pro",
        "status": "MODERATED",
        "category_id": "123e4567-e89b-12d3-a456-426614174001",
        "min_price": 12999000,
        "cover_image": "https://cdn.neomarket.ru/iphone15.jpg",
        "has_stock": True,
    }


@pytest.mark.asyncio
async def test_add_to_favorites_returns_201(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    repository = FakeFavoritesRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_favorites_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.put(
        f"/api/v1/favorites/{product_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    assert response.json()["product_id"] == product_id
    assert len(repository.favorites) == 1
    assert repository.favorites[0].user_id == user_id
    assert b2b.batch_calls == [[product_id]]


@pytest.mark.asyncio
async def test_repeat_add_returns_200_not_duplicate(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440002"
    repository = FakeFavoritesRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_favorites_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    first_response = await client.put(
        f"/api/v1/favorites/{product_id}",
        headers=auth_headers(),
    )
    repeat_response = await client.put(
        f"/api/v1/favorites/{product_id}",
        headers=auth_headers(),
    )

    assert first_response.status_code == 201
    assert repeat_response.status_code == 200
    assert len(repository.favorites) == 1
    assert repository.favorites[0].product_id == product_id


@pytest.mark.asyncio
async def test_get_favorites_enriched_from_b2b(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    product_id = "770e8400-e29b-41d4-a716-446655440003"
    repository = FakeFavoritesRepository(
        [
            StoredFavorite(
                id="favorite-1",
                user_id=user_id,
                product_id=product_id,
                added_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
            )
        ]
    )
    b2b = StubB2BFavoritesClient(
        [product_payload(product_id, title="Samsung Galaxy S24")]
    )
    app.dependency_overrides[get_favorites_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(
        "/api/v1/favorites",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    assert "total" not in body
    assert body["items"][0]["id"] == product_id
    assert body["items"][0]["title"] == "Samsung Galaxy S24"
    assert body["items"][0]["price"] == 12999000
    assert b2b.batch_calls == [[product_id]]


@pytest.mark.asyncio
async def test_blocked_product_excluded_from_list(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    visible_product_id = "770e8400-e29b-41d4-a716-446655440004"
    blocked_product_id = "770e8400-e29b-41d4-a716-446655440005"
    repository = FakeFavoritesRepository(
        [
            StoredFavorite(
                id="favorite-1",
                user_id=user_id,
                product_id=visible_product_id,
                added_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
            ),
            StoredFavorite(
                id="favorite-2",
                user_id=user_id,
                product_id=blocked_product_id,
                added_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
            ),
        ]
    )
    b2b = StubB2BFavoritesClient([product_payload(visible_product_id)])
    app.dependency_overrides[get_favorites_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(
        "/api/v1/favorites",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [visible_product_id]
    assert b2b.batch_calls == [[visible_product_id, blocked_product_id]]


@pytest.mark.asyncio
async def test_user_id_from_query_is_ignored(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    other_user_id = "22222222-2222-4222-8222-222222222222"
    product_id = "770e8400-e29b-41d4-a716-446655440006"
    repository = FakeFavoritesRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_favorites_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.put(
        f"/api/v1/favorites/{product_id}",
        params={"user_id": other_user_id},
        headers=auth_headers(user_id),
    )
    other_response = await client.get(
        "/api/v1/favorites",
        headers=auth_headers(other_user_id),
    )
    owner_response = await client.get(
        "/api/v1/favorites",
        params={"user_id": other_user_id},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    assert repository.add_calls == [{"user_id": user_id, "product_id": product_id}]
    assert other_response.json()["items"] == []
    assert owner_response.json()["items"][0]["id"] == product_id
    assert repository.list_calls[-1]["user_id"] == user_id
    assert repository.list_calls[-1]["user_id"] != other_user_id


@pytest.mark.asyncio
async def test_guest_cannot_use_favorites(client: AsyncClient):
    repository = FakeFavoritesRepository()
    b2b = StubB2BFavoritesClient([])
    app.dependency_overrides[get_favorites_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get(
        "/api/v1/favorites",
        headers={"X-Session-Id": "guest-session"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "UNAUTHORIZED",
        "message": "Authentication required",
    }
    assert repository.list_calls == []


@pytest.mark.asyncio
async def test_subscribe_returns_201_with_notify_on(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    product_id = "770e8400-e29b-41d4-a716-446655440011"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(user_id),
        json={"events": ["BACK_IN_STOCK", "PRICE_DROP"]},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert repository.subscriptions[0].events == (
        "BACK_IN_STOCK",
        "PRICE_DROP",
    )
    assert repository.add_calls == [
        {
            "user_id": user_id,
            "product_id": product_id,
            "events": ["BACK_IN_STOCK", "PRICE_DROP"],
        }
    ]
    assert b2b.batch_calls == [[product_id]]


@pytest.mark.asyncio
async def test_duplicate_subscription_returns_409(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440012"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    first_response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(),
        json={"events": ["BACK_IN_STOCK"]},
    )
    duplicate_response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(),
        json={"events": ["PRICE_DROP"]},
    )

    assert first_response.status_code == 204
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "code": "SUBSCRIPTION_ALREADY_EXISTS",
        "message": "Subscription already exists",
    }
    assert len(repository.subscriptions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("events", [[], ["UNKNOWN_EVENT"]])
async def test_invalid_notify_on_returns_400(
    client: AsyncClient,
    events: list[str],
):
    product_id = "770e8400-e29b-41d4-a716-446655440013"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(),
        json={"events": events},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_NOTIFY_ON",
        "message": "Invalid events",
    }
    assert repository.add_calls == []
    assert b2b.batch_calls == []


@pytest.mark.asyncio
async def test_subscribe_to_unknown_product_returns_404(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440014"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(),
        json={"events": ["BACK_IN_STOCK"]},
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Product not found",
    }
    assert repository.add_calls == []


@pytest.mark.asyncio
async def test_unsubscribe_returns_204(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    product_id = "770e8400-e29b-41d4-a716-446655440015"
    repository = FakeProductSubscriptionsRepository(
        [
            StoredProductSubscription(
                id="subscription-1",
                user_id=user_id,
                product_id=product_id,
                events=("PRICE_DROP",),
                created_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
            )
        ]
    )
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )

    first_response = await client.delete(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(user_id),
    )
    repeat_response = await client.delete(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(user_id),
    )

    assert first_response.status_code == 204
    assert repeat_response.status_code == 204
    assert repository.subscriptions == []
    assert repository.delete_calls == [
        {"user_id": user_id, "product_id": product_id},
        {"user_id": user_id, "product_id": product_id},
    ]


@pytest.mark.asyncio
async def test_user_id_from_query_is_ignored_for_subscription(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    other_user_id = "22222222-2222-4222-8222-222222222222"
    product_id = "770e8400-e29b-41d4-a716-446655440016"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        params={"user_id": other_user_id},
        headers=auth_headers(user_id),
        json={"events": ["BACK_IN_STOCK"], "user_id": other_user_id},
    )

    assert response.status_code == 204
    assert repository.add_calls[0]["user_id"] == user_id
    assert repository.add_calls[0]["user_id"] != other_user_id


@pytest.mark.asyncio
async def test_guest_cannot_subscribe(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440017"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers={"X-Session-Id": "guest-session"},
        json={"events": ["BACK_IN_STOCK"]},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "UNAUTHORIZED",
        "message": "Authentication required",
    }
    assert repository.add_calls == []
    assert b2b.batch_calls == []


@pytest.mark.asyncio
async def test_subscription_product_id_must_be_uuid(client: AsyncClient):
    repository = FakeProductSubscriptionsRepository()
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )

    response = await client.post(
        "/api/v1/favorites/not-a-uuid/subscribe",
        headers=auth_headers(),
        json={"events": ["BACK_IN_STOCK"]},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "Invalid request",
    }
    assert repository.add_calls == []


@pytest.mark.asyncio
async def test_b2b_unavailable_when_subscribing_returns_503(client: AsyncClient):
    product_id = "770e8400-e29b-41d4-a716-446655440018"
    repository = FakeProductSubscriptionsRepository()
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = (
        lambda: UnavailableB2BFavoritesClient()
    )

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(),
        json={"events": ["PRICE_DROP"]},
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "B2B_UNAVAILABLE",
        "message": "B2B unavailable",
    }
    assert repository.add_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {}])
async def test_subscribe_uses_default_events(
    client: AsyncClient,
    payload: dict | None,
):
    product_id = "770e8400-e29b-41d4-a716-446655440019"
    repository = FakeProductSubscriptionsRepository()
    b2b = StubB2BFavoritesClient([product_payload(product_id)])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    request_kwargs = {} if payload is None else {"json": payload}
    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(),
        **request_kwargs,
    )

    assert response.status_code == 204
    assert repository.add_calls[0]["events"] == [
        "BACK_IN_STOCK",
        "PRICE_DROP",
    ]


@pytest.mark.asyncio
async def test_duplicate_subscription_is_checked_before_b2b(client: AsyncClient):
    user_id = "11111111-1111-4111-8111-111111111111"
    product_id = "770e8400-e29b-41d4-a716-446655440020"
    repository = FakeProductSubscriptionsRepository(
        [
            StoredProductSubscription(
                id="subscription-1",
                user_id=user_id,
                product_id=product_id,
                events=("BACK_IN_STOCK",),
                created_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
            )
        ]
    )
    b2b = StubB2BFavoritesClient([])
    app.dependency_overrides[get_product_subscriptions_repository] = (
        lambda: repository
    )
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers=auth_headers(user_id),
        json={"events": ["PRICE_DROP"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "SUBSCRIPTION_ALREADY_EXISTS"
    assert b2b.batch_calls == []
    assert repository.add_calls == []
