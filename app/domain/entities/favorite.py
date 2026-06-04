from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredFavorite:
    id: str
    user_id: str
    product_id: str
    added_at: datetime | None = None
