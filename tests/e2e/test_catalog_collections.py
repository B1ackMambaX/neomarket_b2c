from datetime import date, timedelta

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.catalog import (
    get_b2b_catalog_client,
    get_collections_repository,
)
from app.domain.entities.collection import StoredCollection
from app.main import app


class FakeCollectionRepository:
    def __init__(self, collections: list[StoredCollection]) -> None:
        self.collections = collections
        self.calls: list[date] = []

    async def list_active(self, *, as_of: date) -> list[StoredCollection]:
        self.calls.append(as_of)
        visible = [
            collection
            for collection in self.collections
            if collection.is_active
            and (
                collection.start_date is None
                or collection.start_date <= as_of
            )
        ]
        return sorted(
            visible,
            key=lambda collection: (collection.priority, collection.id),
        )


class StubB2BCollectionsClient:
    def __init__(
        self,
        products: list[dict] | None = None,
        error: httpx.HTTPError | None = None,
    ) -> None:
        self.products = products or []
        self.error = error
        self.batch_calls: list[list[str]] = []

    async def batch_public_products(self, product_ids: list[str]) -> list[dict]:
        self.batch_calls.append(product_ids)
        if self.error is not None:
            raise self.error
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
async def test_catalog_collections_returns_collections_with_products(
    client: AsyncClient,
):
    first_product_id = _uuid(101)
    second_product_id = _uuid(102)
    repository = FakeCollectionRepository(
        [
            _collection(
                1,
                title="Хиты недели",
                description="Самые популярные товары",
                product_ids=(second_product_id, first_product_id),
            )
        ]
    )
    b2b = StubB2BCollectionsClient(
        [
            _product(first_product_id, title="Первый товар"),
            _product(second_product_id, title="Второй товар"),
        ]
    )
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == _uuid(1)
    assert body[0]["name"] == "Хиты недели"
    assert body[0]["description"] == "Самые популярные товары"
    assert [product["id"] for product in body[0]["products"]] == [
        second_product_id,
        first_product_id,
    ]
    assert "title" not in body[0]
    assert "priority" not in body[0]
    assert "target_url" not in body[0]
    assert "cover_image_url" not in body[0]
    assert "unavailable_ids" not in body[0]
    assert "title" not in body[0]["products"][0]
    assert "price" not in body[0]["products"][0]
    assert "in_stock" not in body[0]["products"][0]


@pytest.mark.asyncio
async def test_collection_products_enriched_from_b2b(client: AsyncClient):
    product_id = _uuid(201)
    repository = FakeCollectionRepository(
        [_collection(2, title="Новинки", product_ids=(product_id,))]
    )
    b2b = StubB2BCollectionsClient(
        [
            _product(
                product_id,
                title="Смартфон",
                price=12_999_000,
                discount=500_000,
            )
        ]
    )
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 200
    product = response.json()[0]["products"][0]
    assert product["id"] == product_id
    assert product["name"] == "Смартфон"
    assert product["min_price"] == 12_499_000
    assert product["old_price"] == 12_999_000
    assert product["has_stock"] is True
    assert product["images"][0]["url"] == "https://cdn.neomarket.test/product.jpg"
    assert b2b.batch_calls == [[product_id]]


@pytest.mark.asyncio
async def test_unavailable_products_excluded_from_products(client: AsyncClient):
    available_id = _uuid(301)
    missing_id = _uuid(302)
    blocked_id = _uuid(303)
    repository = FakeCollectionRepository(
        [
            _collection(
                3,
                title="Подборка",
                product_ids=(available_id, missing_id, blocked_id),
            )
        ]
    )
    blocked_product = _product(blocked_id, title="Заблокированный")
    blocked_product["status"] = "BLOCKED"
    b2b = StubB2BCollectionsClient(
        [
            _product(available_id, title="Доступный"),
            blocked_product,
        ]
    )
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()[0]["products"]] == [
        available_id
    ]


@pytest.mark.asyncio
async def test_inactive_and_future_collections_are_hidden(client: AsyncClient):
    today = date.today()
    repository = FakeCollectionRepository(
        [
            _collection(4, title="Активная", start_date=today),
            _collection(5, title="Без даты", start_date=None),
            _collection(6, title="Неактивная", is_active=False),
            _collection(
                7,
                title="Будущая",
                start_date=today + timedelta(days=1),
            ),
        ]
    )
    b2b = StubB2BCollectionsClient()
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 200
    assert [collection["name"] for collection in response.json()] == [
        "Активная",
        "Без даты",
    ]
    assert repository.calls == [today]


@pytest.mark.asyncio
async def test_collections_sorted_by_priority(client: AsyncClient):
    repository = FakeCollectionRepository(
        [
            _collection(8, title="Позже", priority=20),
            _collection(9, title="Раньше", priority=5),
        ]
    )
    b2b = StubB2BCollectionsClient()
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 200
    assert [collection["name"] for collection in response.json()] == [
        "Раньше",
        "Позже",
    ]


@pytest.mark.asyncio
async def test_empty_collection_does_not_call_b2b(client: AsyncClient):
    repository = FakeCollectionRepository(
        [_collection(10, title="Пустая подборка")]
    )
    b2b = StubB2BCollectionsClient()
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 200
    assert response.json()[0]["products"] == []
    assert b2b.batch_calls == []


@pytest.mark.asyncio
async def test_b2b_unavailable_returns_503(client: AsyncClient):
    product_id = _uuid(401)
    repository = FakeCollectionRepository(
        [_collection(11, title="Подборка", product_ids=(product_id,))]
    )
    b2b = StubB2BCollectionsClient(
        error=httpx.ConnectError("B2B unavailable")
    )
    app.dependency_overrides[get_collections_repository] = lambda: repository
    app.dependency_overrides[get_b2b_catalog_client] = lambda: b2b

    response = await client.get("/api/v1/catalog/collections")

    assert response.status_code == 503
    assert response.json() == {
        "code": "B2B_UNAVAILABLE",
        "message": "B2B unavailable",
    }


def _collection(
    value: int,
    *,
    title: str,
    description: str | None = None,
    priority: int = 0,
    is_active: bool = True,
    start_date: date | None = None,
    product_ids: tuple[str, ...] = (),
) -> StoredCollection:
    return StoredCollection(
        id=_uuid(value),
        title=title,
        description=description,
        cover_image_url="https://cdn.neomarket.test/collection.jpg",
        target_url="/catalog",
        priority=priority,
        is_active=is_active,
        start_date=start_date,
        product_ids=product_ids,
    )


def _product(
    product_id: str,
    *,
    title: str,
    price: int = 1_000_000,
    discount: int = 0,
) -> dict:
    return {
        "id": product_id,
        "seller_id": _uuid(900),
        "category_id": _uuid(901),
        "title": title,
        "slug": title.lower().replace(" ", "-"),
        "description": f"Описание: {title}",
        "status": "MODERATED",
        "images": [
            {
                "id": _uuid(902),
                "url": "https://cdn.neomarket.test/product.jpg",
                "ordering": 0,
            }
        ],
        "characteristics": [],
        "skus": [
            {
                "id": _uuid(903),
                "product_id": product_id,
                "name": "Основной",
                "price": price,
                "discount": discount,
                "active_quantity": 5,
                "article": "SKU-1",
                "images": [],
                "characteristics": [],
            }
        ],
    }


def _uuid(value: int) -> str:
    return f"00000000-0000-4000-8000-{value:012d}"
