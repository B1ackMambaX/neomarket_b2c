from typing import Protocol

from app.domain.entities.order import StoredOrder


class OrderRepository(Protocol):
    async def get_by_idempotency_key(self, idempotency_key: str) -> StoredOrder | None:
        raise NotImplementedError

    async def get_by_id_for_buyer(
        self,
        order_id: str,
        buyer_id: str,
        *,
        for_update: bool = False,
    ) -> StoredOrder | None:
        raise NotImplementedError

    async def create_or_get_by_idempotency_key(
        self,
        order: StoredOrder,
    ) -> tuple[StoredOrder, bool]:
        raise NotImplementedError

    async def save(self, order: StoredOrder) -> StoredOrder:
        raise NotImplementedError

    async def delete(self, order_id: str) -> None:
        raise NotImplementedError
