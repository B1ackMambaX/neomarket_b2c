import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.domain.entities.banner import StoredBanner
from app.domain.repositories.banner import BannerEventRecord
from app.infrastructure.database.models.banner import BannerEventModel, BannerModel


class SQLAlchemyBannerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self, *, as_of: datetime) -> list[StoredBanner]:
        stmt = (
            select(BannerModel)
            .where(
                BannerModel.is_active.is_(True),
                or_(
                    BannerModel.start_at.is_(None),
                    BannerModel.start_at <= as_of,
                ),
                or_(
                    BannerModel.end_at.is_(None),
                    BannerModel.end_at >= as_of,
                ),
            )
            .order_by(BannerModel.priority, BannerModel.id)
        )
        banners = (await self._session.scalars(stmt)).all()
        return [self._map_banner(banner) for banner in banners]

    async def exists(self, banner_id: str) -> bool:
        stmt = select(BannerModel.id).where(BannerModel.id == banner_id)
        return (await self._session.scalar(stmt)) is not None

    async def record_events(self, events: list[BannerEventRecord]) -> None:
        self._session.add_all(
            [
                BannerEventModel(
                    id=str(uuid.uuid4()),
                    banner_id=event.banner_id,
                    user_id=event.user_id,
                    event=event.event,
                    timestamp=event.timestamp,
                )
                for event in events
            ]
        )

    def _map_banner(self, banner: BannerModel) -> StoredBanner:
        return StoredBanner(
            id=banner.id,
            title=banner.title,
            image_url=banner.image_url,
            link=banner.link,
            priority=banner.priority,
            is_active=banner.is_active,
            start_at=banner.start_at,
            end_at=banner.end_at,
            created_at=banner.created_at,
        )
