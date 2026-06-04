import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)

from app.api.v1.dependencies.catalog import (
    get_b2b_catalog_client,
)
from app.main import app


CATEGORY_ID = (
    "123e4567-e89b-12d3-a456-426614174003"
)


class StubB2BCatalogClient:

    def __init__(
        self,
        categories: list[dict],
    ) -> None:
        self.categories = categories

    async def get_categories(
        self,
    ) -> list[dict]:
        return self.categories

    async def get_category(
        self,
        category_id: str,
        **kwargs,
    ) -> dict | None:

        return next(
            (
                category
                for category in self.categories
                if category["id"]
                == category_id
            ),
            None,
        )

    async def get_category_by_product(
        self,
        product_id: str,
    ) -> dict | None:

        return (
            self.categories[-1]
            if self.categories
            else None
        )


@pytest.fixture
async def client():

    async with AsyncClient(
        transport=ASGITransport(
            app=app,
        ),
        base_url="http://test",
    ) as test_client:

        yield test_client

    app.dependency_overrides.clear()


def categories_payload():

    return [
        {
            "id":
            "123e4567-e89b-12d3-a456-426614174001",
            "name":
            "Электроника",
            "slug":
            "electronics",
            "parent_id":
            None,
        },
        {
            "id":
            CATEGORY_ID,
            "name":
            "Смартфоны",
            "slug":
            "smartphones",
            "parent_id":
            "123e4567-e89b-12d3-a456-426614174001",
        },
    ]


@pytest.mark.asyncio
async def test_category_tree_returns_nested_structure(
    client: AsyncClient,
):

    b2b = StubB2BCatalogClient(
        categories_payload()
    )

    app.dependency_overrides[
        get_b2b_catalog_client
    ] = lambda: b2b

    response = await client.get(
        "/api/v1/categories"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(
        body["items"]
    ) == 1

    assert (
        body["items"][0]
        ["children"][0]
        ["name"]
        ==
        "Смартфоны"
    )


@pytest.mark.asyncio
async def test_breadcrumbs_return_path_from_root(
    client: AsyncClient,
):

    b2b = StubB2BCatalogClient(
        categories_payload()
    )

    app.dependency_overrides[
        get_b2b_catalog_client
    ] = lambda: b2b

    response = await client.get(
        "/api/v1/breadcrumbs",
        params={
            "category_id":
            CATEGORY_ID
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()[
        "data"
    ]

    assert (
        data[0]["name"]
        ==
        "Электроника"
    )

    assert (
        data[0]["level"]
        == 0
    )

    assert (
        data[-1]
        ["is_current"]
        is True
    )


@pytest.mark.asyncio
async def test_ambiguous_params_returns_400(
    client: AsyncClient,
):

    response = await client.get(
        "/api/v1/breadcrumbs",
        params={
            "category_id":
            CATEGORY_ID,
            "product_id":
            CATEGORY_ID,
        },
    )

    assert (
        response.status_code
        == 400
    )


@pytest.mark.asyncio
async def test_orphan_node_returns_422(
    client: AsyncClient,
):

    b2b = StubB2BCatalogClient(
        [
            {
                "id":
                CATEGORY_ID,
                "name":
                "Смартфоны",
                "slug":
                "smartphones",
                "parent_id":
                "missing-parent",
            }
        ]
    )

    app.dependency_overrides[
        get_b2b_catalog_client
    ] = lambda: b2b

    response = await client.get(
        "/api/v1/categories"
    )

    assert (
        response.status_code
        == 422
    )


@pytest.mark.asyncio
async def test_unknown_category_returns_404(
    client: AsyncClient,
):

    b2b = StubB2BCatalogClient(
        []
    )

    app.dependency_overrides[
        get_b2b_catalog_client
    ] = lambda: b2b

    response = await client.get(
        "/api/v1/categories/"
        + CATEGORY_ID
    )

    assert (
        response.status_code
        == 404
    )