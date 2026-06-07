from typing import Protocol

from app.domain.entities.category import Category


class CategoryRepository(Protocol):

    async def list(self) -> list[Category]:
        raise NotImplementedError

    async def get_by_id(
        self,
        category_id: str,
    ) -> Category | None:
        raise NotImplementedError

    async def get_category_by_product(
        self,
        product_id: str,
    ) -> Category | None:
        raise NotImplementedError

    async def count_products(
        self,
        category_id: str,
    ) -> int:
        raise NotImplementedError