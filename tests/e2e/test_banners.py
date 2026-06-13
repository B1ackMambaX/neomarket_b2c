from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.banners import get_banner_repository
from app.domain.entities.banner import StoredBanner
from app.domain.repositories.banner import BannerEventRecord
from app.main import app


class FakeBannerRepository:
    def __init__(self, banners: list[StoredBanner] | None = None) -> None:
        self.banners = banners or []
        self.exists_ids: set[str] = set()
        self.recorded_events: list[BannerEventRecord] = []
        self.list_calls: list[datetime] = []

    async def list_active(self, *, as_of: datetime) -> list[StoredBanner]:
        self.list_calls.append(as_of)
        visible = [
            banner
            for banner in self.banners
            if banner.is_active
            and (banner.start_at is None or banner.start_at <= as_of)
            and (banner.end_at is None or banner.end_at >= as_of)
        ]
        return sorted(visible, key=lambda banner: (banner.priority, banner.id))

    async def exists(self, banner_id: str) -> bool:
        if banner_id in self.exists_ids:
            return True
        return any(banner.id == banner_id for banner in self.banners)

    async def record_events(self, events: list[BannerEventRecord]) -> None:
        self.recorded_events.extend(events)


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_active_banners_returned_sorted_by_priority(client: AsyncClient):
    now = datetime.now(UTC)
    first_id = _uuid(1)
    second_id = _uuid(2)
    third_id = _uuid(3)
    repository = FakeBannerRepository(
        [
            _banner(
                1,
                title="Высокий приоритет",
                priority=5,
                start_at=now - timedelta(hours=1),
                end_at=now + timedelta(days=1),
            ),
            _banner(
                2,
                title="Низкий приоритет",
                priority=20,
                start_at=now - timedelta(hours=1),
                end_at=now + timedelta(days=1),
            ),
            _banner(
                3,
                title="Неактивный",
                priority=1,
                is_active=False,
                start_at=now - timedelta(hours=1),
                end_at=now + timedelta(days=1),
            ),
            _banner(
                4,
                title="Истёкший",
                priority=1,
                start_at=now - timedelta(days=2),
                end_at=now - timedelta(hours=1),
            ),
            _banner(
                5,
                title="Будущий",
                priority=1,
                start_at=now + timedelta(days=1),
                end_at=now + timedelta(days=2),
            ),
        ]
    )
    app.dependency_overrides[get_banner_repository] = lambda: repository

    response = await client.get("/api/v1/home/banners")

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert [item["id"] for item in body["items"]] == [first_id, second_id]
    assert [item["priority"] for item in body["items"]] == [5, 20]
    assert body["items"][0]["title"] == "Высокий приоритет"
    assert body["items"][1]["title"] == "Низкий приоритет"
    assert third_id not in {item["id"] for item in body["items"]}


@pytest.mark.asyncio
async def test_no_active_banners_returns_200_empty(client: AsyncClient):
    now = datetime.now(UTC)
    repository = FakeBannerRepository(
        [
            _banner(
                10,
                title="Неактивный",
                is_active=False,
                start_at=now - timedelta(hours=1),
                end_at=now + timedelta(days=1),
            ),
            _banner(
                11,
                title="Истёкший",
                start_at=now - timedelta(days=2),
                end_at=now - timedelta(hours=1),
            ),
        ]
    )
    app.dependency_overrides[get_banner_repository] = lambda: repository

    response = await client.get("/api/v1/home/banners")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total_count": 0}


@pytest.mark.asyncio
async def test_click_on_unknown_banner_returns_400(client: AsyncClient):
    repository = FakeBannerRepository()
    app.dependency_overrides[get_banner_repository] = lambda: repository

    response = await client.post(
        "/api/v1/banner-events",
        json={
            "events": [
                {
                    "banner_id": _uuid(999),
                    "event": "click",
                    "timestamp": "2026-06-13T12:00:00Z",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "BANNER_NOT_FOUND",
        "message": f"Banner {_uuid(999)} not found",
    }
    assert repository.recorded_events == []


def _banner(
    value: int,
    *,
    title: str,
    priority: int = 0,
    is_active: bool = True,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> StoredBanner:
    return StoredBanner(
        id=_uuid(value),
        title=title,
        image_url=f"https://cdn.neomarket.test/banners/{value}.jpg",
        link=f"/catalog?banner={value}",
        priority=priority,
        is_active=is_active,
        start_at=start_at,
        end_at=end_at,
    )


def _uuid(value: int) -> str:
    return f"00000000-0000-4000-8000-{value:012d}"
