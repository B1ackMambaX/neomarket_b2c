from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredProductSubscription:
    id: str
    user_id: str
    product_id: str
    events: tuple[str, ...]
    created_at: datetime | None = None
