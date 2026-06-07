from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class StoredCollection:
    id: str
    title: str
    description: str | None
    cover_image_url: str | None
    target_url: str | None
    priority: int
    is_active: bool
    start_date: date | None
    product_ids: tuple[str, ...]
    created_at: datetime | None = None
