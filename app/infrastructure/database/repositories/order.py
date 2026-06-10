from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.order import StoredOrder, StoredOrderItem
from app.infrastructure.database.models.order import OrderItemModel, OrderModel


class SQLAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(self, idempotency_key: str) -> StoredOrder | None:
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(OrderModel.idempotency_key == idempotency_key)
        )
        order = await self._session.scalar(stmt)
        if order is None:
            return None
        return self._map_order(order)

    async def get_by_id(
        self,
        order_id: str,
        *,
        for_update: bool = False,
    ) -> StoredOrder | None:

        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(OrderModel.id == order_id)
        )

        if for_update:
            stmt = stmt.with_for_update()

        order = await self._session.scalar(stmt)

        if order is None:
            return None

        return self._map_order(order)

    async def get_by_id_for_buyer(
        self,
        order_id: str,
        buyer_id: str,
        *,
        for_update: bool = False,
    ) -> StoredOrder | None:
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(OrderModel.id == order_id, OrderModel.buyer_id == buyer_id)
        )
        if for_update:
            stmt = stmt.with_for_update()
        order = await self._session.scalar(stmt)
        if order is None:
            return None
        return self._map_order(order)

    async def create_or_get_by_idempotency_key(
        self,
        order: StoredOrder,
    ) -> tuple[StoredOrder, bool]:
        model = OrderModel(
            id=order.id,
            number=order.number,
            buyer_id=order.buyer_id,
            idempotency_key=order.idempotency_key,
            request_hash=order.request_hash,
            status=order.status,
            subtotal=order.subtotal,
            delivery_cost=order.delivery_cost,
            total=order.total,
            address_id=order.address_id,
            payment_method_id=order.payment_method_id,
            comment=order.comment,
            cancel_reason=order.cancel_reason,
            status_history=order.status_history,
            paid_at=order.paid_at,
            delivered_at=order.delivered_at,
            items=[
                OrderItemModel(
                    id=item.id,
                    sku_id=item.sku_id,
                    product_id=item.product_id,
                    name=item.name,
                    sku_code=item.sku_code,
                    product_title=item.product_title,
                    sku_name=item.sku_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    image_url=item.image_url,
                )
                for item in order.items
            ],
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_idempotency_key(order.idempotency_key)
            if existing is None:
                raise
            return existing, False
        await self._session.refresh(model, attribute_names=["items"])
        return self._map_order(model), True

    async def save(self, order: StoredOrder) -> StoredOrder:
        model = await self._session.get(
            OrderModel,
            order.id,
            options=[selectinload(OrderModel.items)],
        )
        if model is None:
            raise ValueError(f"Order {order.id} not found")

        model.status = order.status
        model.cancel_reason = order.cancel_reason
        model.status_history = order.status_history
        model.paid_at = order.paid_at
        model.delivered_at = order.delivered_at
        await self._session.flush()
        await self._session.refresh(model, attribute_names=["items"])
        return self._map_order(model)

    async def delete(self, order_id: str) -> None:
        await self._session.execute(delete(OrderModel).where(OrderModel.id == order_id))
        await self._session.flush()

    def _map_order(self, order: OrderModel) -> StoredOrder:
        return StoredOrder(
            id=order.id,
            number=order.number,
            buyer_id=order.buyer_id,
            idempotency_key=order.idempotency_key,
            request_hash=order.request_hash,
            status=order.status,
            items=[
                StoredOrderItem(
                    id=item.id,
                    sku_id=item.sku_id,
                    product_id=item.product_id,
                    name=item.name,
                    sku_code=item.sku_code,
                    product_title=item.product_title,
                    sku_name=item.sku_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    image_url=item.image_url,
                )
                for item in order.items
            ],
            subtotal=order.subtotal,
            delivery_cost=order.delivery_cost,
            total=order.total,
            address_id=order.address_id,
            payment_method_id=order.payment_method_id,
            comment=order.comment,
            cancel_reason=order.cancel_reason,
            status_history=order.status_history,
            created_at=order.created_at,
            paid_at=order.paid_at,
            delivered_at=order.delivered_at,
        )
