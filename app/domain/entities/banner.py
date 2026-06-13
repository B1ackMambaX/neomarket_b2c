from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredBanner:
    id: str
    title: str
    image_url: str
    link: str
    priority: int
    is_active: bool
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime | None = None
