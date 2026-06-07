from typing import Protocol

from app.domain.entities.subscription import StoredProductSubscription


class ProductSubscriptionRepository(Protocol):
    async def get(
        self,
        user_id: str,
        product_id: str,
    ) -> StoredProductSubscription | None:
        raise NotImplementedError

    async def add(
        self,
        user_id: str,
        product_id: str,
        events: list[str],
    ) -> tuple[StoredProductSubscription, bool]:
        raise NotImplementedError

    async def delete(self, user_id: str, product_id: str) -> None:
        raise NotImplementedError
