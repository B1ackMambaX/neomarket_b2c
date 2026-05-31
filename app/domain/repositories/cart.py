from typing import Protocol

from app.domain.entities.cart import CartIdentity, StoredCartItem


class CartRepository(Protocol):
    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        raise NotImplementedError
