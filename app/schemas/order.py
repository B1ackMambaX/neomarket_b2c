from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.entities.order import StoredOrder


class OrderItemSnapshot(BaseModel):
    sku_id: str
    quantity: int = Field(ge=1)
    unit_price: int = Field(ge=0)


class OrderCreateRequest(BaseModel):
    address_id: str
    payment_method_id: str
    comment: str | None = Field(default=None, max_length=1000)
    items_snapshot: list[OrderItemSnapshot] | None = None


class OrderCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class OrderItem(BaseModel):
    sku_id: str
    product_id: str
    name: str
    sku_code: str | None = None
    quantity: int = Field(ge=1)
    unit_price: int
    line_total: int
    image_url: str | None = None


class AddressResponse(BaseModel):
    id: str
    country: str = ""
    region: str | None = None
    city: str = ""
    street: str = ""
    building: str = ""
    apartment: str | None = None
    postal_code: str | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None
    is_default: bool = False
    comment: str | None = None
    created_at: datetime


class PaymentMethodResponse(BaseModel):
    id: str
    type: Literal["CARD", "SBP", "WALLET"] = "CARD"
    card_last4: str | None = None
    card_brand: Literal["VISA", "MASTERCARD", "MIR"] | None = None
    is_default: bool = False
    created_at: datetime


class OrderStatusHistoryItem(BaseModel):
    status: str
    changed_at: datetime | str
    reason: str | None = None


class OrderResponse(BaseModel):
    id: str
    number: str
    buyer_id: str
    status: Literal[
        "CREATED",
        "PAID",
        "ASSEMBLING",
        "DELIVERING",
        "DELIVERED",
        "CANCELLED",
        "CANCEL_PENDING",
    ]
    status_history: list[OrderStatusHistoryItem] = Field(default_factory=list)
    items: list[OrderItem]
    subtotal: int
    delivery_cost: int = 0
    total: int
    address: AddressResponse
    payment_method: PaymentMethodResponse
    comment: str | None = None
    cancel_reason: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
    delivered_at: datetime | None = None

    @classmethod
    def from_entity(cls, order: StoredOrder) -> "OrderResponse":
        created_at = order.created_at or datetime.now(timezone.utc)
        return cls(
            id=order.id,
            number=order.number,
            buyer_id=order.buyer_id,
            status=order.status,
            status_history=[
                OrderStatusHistoryItem(**entry) for entry in order.status_history
            ],
            items=[
                OrderItem(
                    sku_id=item.sku_id,
                    product_id=item.product_id,
                    name=item.name,
                    sku_code=item.sku_code,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    image_url=item.image_url,
                )
                for item in order.items
            ],
            subtotal=order.subtotal,
            delivery_cost=order.delivery_cost,
            total=order.total,
            address=AddressResponse(id=order.address_id, created_at=created_at),
            payment_method=PaymentMethodResponse(
                id=order.payment_method_id,
                created_at=created_at,
            ),
            comment=order.comment,
            cancel_reason=order.cancel_reason,
            created_at=created_at,
            paid_at=order.paid_at,
            delivered_at=order.delivered_at,
        )
