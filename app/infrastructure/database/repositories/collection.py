from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.collection import StoredCollection
from app.infrastructure.database.models.collection import CollectionModel


class SQLAlchemyCollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self, *, as_of: date) -> list[StoredCollection]:
        stmt = (
            select(CollectionModel)
            .options(selectinload(CollectionModel.products))
            .where(
                CollectionModel.is_active.is_(True),
                or_(
                    CollectionModel.start_date.is_(None),
                    CollectionModel.start_date <= as_of,
                ),
            )
            .order_by(CollectionModel.priority, CollectionModel.id)
        )
        collections = (await self._session.scalars(stmt)).all()
        return [self._map_collection(collection) for collection in collections]

    def _map_collection(self, collection: CollectionModel) -> StoredCollection:
        return StoredCollection(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            cover_image_url=collection.cover_image_url,
            target_url=collection.target_url,
            priority=collection.priority,
            is_active=collection.is_active,
            start_date=collection.start_date,
            product_ids=tuple(product.product_id for product in collection.products),
            created_at=collection.created_at,
        )
