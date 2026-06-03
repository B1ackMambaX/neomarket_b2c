from typing import Protocol

from app.domain.entities.favorite import StoredFavorite


class FavoriteRepository(Protocol):
    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[StoredFavorite]:
        raise NotImplementedError

    async def add(
        self,
        user_id: str,
        product_id: str,
    ) -> tuple[StoredFavorite, bool]:
        raise NotImplementedError

    async def delete(self, user_id: str, product_id: str) -> None:
        raise NotImplementedError
