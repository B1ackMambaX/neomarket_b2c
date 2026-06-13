from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies.banners import (
    get_banner_repository,
    resolve_optional_user_id,
)
from app.domain.repositories.banner import BannerRepository
from app.schemas.banner import BannerEventsRequest, BannersResponse
from app.services.banner_service import BannerService

router = APIRouter(tags=["Home"])


@router.get(
    "/home/banners",
    response_model=BannersResponse,
    summary="Активные баннеры главной страницы",
)
async def list_home_banners(
    repository: BannerRepository = Depends(get_banner_repository),
) -> BannersResponse:
    service = BannerService(repository)
    return await service.list_active_banners()


@router.post(
    "/banner-events",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Аналитика показов и кликов баннеров",
)
async def record_banner_events(
    request: BannerEventsRequest,
    user_id: str | None = Depends(resolve_optional_user_id),
    repository: BannerRepository = Depends(get_banner_repository),
) -> None:
    service = BannerService(repository)
    await service.record_events(request, user_id=user_id)
