from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities.banner import StoredBanner


@dataclass(frozen=True)
class BannerEventRecord:
    banner_id: str
    user_id: str | None
    event: str
    timestamp: datetime


class BannerRepository(Protocol):
    async def list_active(self, *, as_of: datetime) -> list[StoredBanner]:
        raise NotImplementedError

    async def exists(self, banner_id: str) -> bool:
        raise NotImplementedError

    async def record_events(self, events: list[BannerEventRecord]) -> None:
        raise NotImplementedError
