from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CartIdentity:
    user_id: str | None = None
    session_id: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def response_id(self) -> str:
        return self.user_id or self.session_id or ""


@dataclass(frozen=True)
class StoredCartItem:
    id: str
    sku_id: str
    quantity: int
    updated_at: datetime | None = None
    unavailable_reason: str | None = None
