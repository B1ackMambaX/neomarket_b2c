import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.product_event import (
    ProductEventIdempotencyKeyModel,
)


class SQLAlchemyProductEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_idempotency_key(
        self,
        idempotency_key: str,
        event_type: str,
    ) -> bool:
        stmt = (
            insert(ProductEventIdempotencyKeyModel)
            .values(
                id=str(uuid.uuid4()),
                idempotency_key=idempotency_key,
                event_type=event_type,
            )
            .on_conflict_do_nothing(
                constraint="uq_product_event_idempotency_keys_key",
            )
            .returning(ProductEventIdempotencyKeyModel.id)
        )
        result = await self._session.scalar(stmt)
        await self._session.flush()
        return result is not None
