from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class OrderLineInput:
    sku_id: str
    quantity: int
    unit_price: int | None = None


@dataclass(frozen=True)
class StoredOrderItem:
    id: str
    sku_id: str
    product_id: str
    name: str
    sku_code: str | None
    product_title: str
    sku_name: str
    quantity: int
    unit_price: int
    line_total: int
    image_url: str | None = None


@dataclass(frozen=True)
class StoredOrder:
    id: str
    number: str
    buyer_id: str
    idempotency_key: str
    request_hash: str
    status: str
    items: list[StoredOrderItem]
    subtotal: int
    delivery_cost: int
    total: int
    address_id: str
    payment_method_id: str
    comment: str | None = None
    cancel_reason: str | None = None
    status_history: list[dict[str, str | None]] = field(default_factory=list)
    created_at: datetime | None = None
    paid_at: datetime | None = None
    delivered_at: datetime | None = None
