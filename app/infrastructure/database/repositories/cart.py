from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.cart import CartIdentity, StoredCartItem
from app.infrastructure.database.models.cart import CartItemModel


class SQLAlchemyCartRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_items(self, identity: CartIdentity) -> list[StoredCartItem]:
        stmt = select(CartItemModel).order_by(CartItemModel.created_at)
        if identity.is_authenticated:
            stmt = stmt.where(CartItemModel.user_id == identity.user_id)
        else:
            stmt = stmt.where(CartItemModel.session_id == identity.session_id)

        result = await self._session.scalars(stmt)
        return [
            StoredCartItem(
                id=item.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                updated_at=item.updated_at,
                unavailable_reason=item.unavailable_reason,
            )
            for item in result.all()
        ]

    async def get_item(
        self,
        identity: CartIdentity,
        sku_id: str,
    ) -> StoredCartItem | None:
        stmt = self._identity_stmt(identity).where(CartItemModel.sku_id == sku_id)
        item = await self._session.scalar(stmt)
        if item is None:
            return None
        return StoredCartItem(
            id=item.id,
            sku_id=item.sku_id,
            quantity=item.quantity,
            updated_at=item.updated_at,
            unavailable_reason=item.unavailable_reason,
        )

    async def add_item(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ) -> None:
        stmt = self._identity_stmt(identity).where(CartItemModel.sku_id == sku_id)
        item = await self._session.scalar(stmt)
        if item is None:
            item = CartItemModel(
                user_id=identity.user_id,
                session_id=identity.session_id,
                sku_id=sku_id,
                quantity=quantity,
            )
            self._session.add(item)
        else:
            item.quantity += quantity
        await self._session.flush()

    async def update_item_quantity(
        self,
        identity: CartIdentity,
        sku_id: str,
        quantity: int,
    ) -> None:
        stmt = self._identity_stmt(identity).where(CartItemModel.sku_id == sku_id)
        item = await self._session.scalar(stmt)
        if item is None:
            return
        item.quantity = quantity
        await self._session.flush()

    async def delete_item(self, identity: CartIdentity, sku_id: str) -> None:
        stmt = (
            delete(CartItemModel)
            .where(self._identity_filter(identity))
            .where(CartItemModel.sku_id == sku_id)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def clear(self, identity: CartIdentity) -> None:
        stmt = delete(CartItemModel).where(self._identity_filter(identity))
        await self._session.execute(stmt)
        await self._session.flush()

    async def merge_guest_cart(
        self,
        user_identity: CartIdentity,
        guest_session_id: str,
    ) -> None:
        guest_items = (
            await self._session.scalars(
                select(CartItemModel).where(
                    CartItemModel.session_id == guest_session_id
                )
            )
        ).all()

        if not guest_items:
            return

        guest_sku_ids = [item.sku_id for item in guest_items]
        auth_items = (
            await self._session.scalars(
                select(CartItemModel).where(
                    CartItemModel.user_id == user_identity.user_id,
                    CartItemModel.sku_id.in_(guest_sku_ids),
                )
            )
        ).all()
        auth_by_sku = {item.sku_id: item for item in auth_items}

        for guest_item in guest_items:
            auth_item = auth_by_sku.get(guest_item.sku_id)
            if auth_item is None:
                guest_item.user_id = user_identity.user_id
                guest_item.session_id = None
                continue

            auth_item.quantity = max(auth_item.quantity, guest_item.quantity)
            await self._session.delete(guest_item)

        await self._session.flush()

    async def list_distinct_sku_ids(self) -> list[str]:
        result = await self._session.scalars(select(CartItemModel.sku_id).distinct())
        return list(result.all())

    async def mark_unavailable_by_sku_ids(
        self,
        sku_ids: list[str],
        unavailable_reason: str,
    ) -> int:
        if not sku_ids:
            return 0
        stmt = (
            update(CartItemModel)
            .where(CartItemModel.sku_id.in_(sku_ids))
            .values(unavailable_reason=unavailable_reason)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0

    def _identity_filter(self, identity: CartIdentity):
        if identity.is_authenticated:
            return CartItemModel.user_id == identity.user_id
        return CartItemModel.session_id == identity.session_id

    def _identity_stmt(self, identity: CartIdentity):
        return select(CartItemModel).where(self._identity_filter(identity))
