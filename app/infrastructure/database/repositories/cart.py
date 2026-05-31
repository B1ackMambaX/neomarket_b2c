from sqlalchemy import select
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
            )
            for item in result.all()
        ]
