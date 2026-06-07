from sqlalchemy import delete, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.favorite import StoredFavorite
from app.infrastructure.database.models.favorite import FavoriteModel


class SQLAlchemyFavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[StoredFavorite]:
        stmt = (
            select(FavoriteModel)
            .where(FavoriteModel.user_id == user_id)
            .order_by(desc(FavoriteModel.added_at))
            .limit(limit)
            .offset(offset)
        )
        favorites = (await self._session.scalars(stmt)).all()
        return [self._map_favorite(favorite) for favorite in favorites]

    async def add(
        self,
        user_id: str,
        product_id: str,
    ) -> tuple[StoredFavorite, bool]:
        existing = await self._get_for_user_product(user_id, product_id)
        if existing is not None:
            return self._map_favorite(existing), False

        favorite = FavoriteModel(user_id=user_id, product_id=product_id)
        self._session.add(favorite)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._get_for_user_product(user_id, product_id)
            if existing is None:
                raise
            return self._map_favorite(existing), False

        await self._session.refresh(favorite)
        return self._map_favorite(favorite), True

    async def delete(self, user_id: str, product_id: str) -> None:
        stmt = delete(FavoriteModel).where(
            FavoriteModel.user_id == user_id,
            FavoriteModel.product_id == product_id,
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def _get_for_user_product(
        self,
        user_id: str,
        product_id: str,
    ) -> FavoriteModel | None:
        stmt = select(FavoriteModel).where(
            FavoriteModel.user_id == user_id,
            FavoriteModel.product_id == product_id,
        )
        return await self._session.scalar(stmt)

    def _map_favorite(self, favorite: FavoriteModel) -> StoredFavorite:
        return StoredFavorite(
            id=favorite.id,
            user_id=favorite.user_id,
            product_id=favorite.product_id,
            added_at=favorite.added_at,
        )
