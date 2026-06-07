from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.subscription import StoredProductSubscription
from app.infrastructure.database.models.subscription import (
    ProductSubscriptionModel,
)


class SQLAlchemyProductSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        user_id: str,
        product_id: str,
    ) -> StoredProductSubscription | None:
        subscription = await self._get_for_user_product(user_id, product_id)
        if subscription is None:
            return None
        return self._map_subscription(subscription)

    async def add(
        self,
        user_id: str,
        product_id: str,
        events: list[str],
    ) -> tuple[StoredProductSubscription, bool]:
        existing = await self._get_for_user_product(user_id, product_id)
        if existing is not None:
            return self._map_subscription(existing), False

        subscription = ProductSubscriptionModel(
            user_id=user_id,
            product_id=product_id,
            events=list(events),
        )
        self._session.add(subscription)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._get_for_user_product(user_id, product_id)
            if existing is None:
                raise
            return self._map_subscription(existing), False

        await self._session.refresh(subscription)
        return self._map_subscription(subscription), True

    async def delete(self, user_id: str, product_id: str) -> None:
        stmt = delete(ProductSubscriptionModel).where(
            ProductSubscriptionModel.user_id == user_id,
            ProductSubscriptionModel.product_id == product_id,
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def _get_for_user_product(
        self,
        user_id: str,
        product_id: str,
    ) -> ProductSubscriptionModel | None:
        stmt = select(ProductSubscriptionModel).where(
            ProductSubscriptionModel.user_id == user_id,
            ProductSubscriptionModel.product_id == product_id,
        )
        return await self._session.scalar(stmt)

    def _map_subscription(
        self,
        subscription: ProductSubscriptionModel,
    ) -> StoredProductSubscription:
        return StoredProductSubscription(
            id=subscription.id,
            user_id=subscription.user_id,
            product_id=subscription.product_id,
            events=tuple(subscription.events),
            created_at=subscription.created_at,
        )
