from datetime import UTC, datetime

from app.domain.exceptions import BannerNotFoundException, EmptyEventsException
from app.domain.repositories.banner import BannerEventRecord, BannerRepository
from app.schemas.banner import BannerEventsRequest, BannerItem, BannersResponse


class BannerService:
    def __init__(self, repository: BannerRepository) -> None:
        self._repository = repository

    async def list_active_banners(self) -> BannersResponse:
        banners = await self._repository.list_active(as_of=datetime.now(UTC))
        items = [
            BannerItem(
                id=banner.id,
                title=banner.title,
                image_url=banner.image_url,
                link=banner.link,
                priority=banner.priority,
            )
            for banner in banners
        ]
        return BannersResponse(items=items, total_count=len(items))

    async def record_events(
        self,
        request: BannerEventsRequest,
        *,
        user_id: str | None = None,
    ) -> None:
        if not request.events:
            raise EmptyEventsException("Events list must not be empty")

        unique_banner_ids = {str(event.banner_id) for event in request.events}
        for banner_id in unique_banner_ids:
            if not await self._repository.exists(banner_id):
                raise BannerNotFoundException(f"Banner {banner_id} not found")

        records = [
            BannerEventRecord(
                banner_id=str(event.banner_id),
                user_id=user_id,
                event=event.event,
                timestamp=event.timestamp,
            )
            for event in request.events
        ]
        await self._repository.record_events(records)
