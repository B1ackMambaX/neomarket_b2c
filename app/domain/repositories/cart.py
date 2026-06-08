from typing import Protocol

from app.domain.entities.cart import CartIdentity, StoredCartItem


class CartRepository(Protocol):
    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        raise NotImplementedError

    async def get_item(
        self,
        identity: CartIdentity,
        sku_id: str,
    ) -> StoredCartItem | None:
        raise NotImplementedError

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
        raise NotImplementedError
