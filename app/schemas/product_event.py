from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProductEventType = Literal[
    "PRODUCT_BLOCKED",
    "PRODUCT_HARD_BLOCKED",
    "PRODUCT_DELETED",
    "SKU_OUT_OF_STOCK",
    "SKU_BACK_IN_STOCK",
    "PRICE_CHANGED",
]


class ProductEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    reason: str | None = None
    sku_id: str | None = None
    available_quantity: int | None = Field(default=None, ge=0)
    old_price: int | None = Field(default=None, ge=0)
    new_price: int | None = Field(default=None, ge=0)


class ProductEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    event_type: ProductEventType
    occurred_at: datetime
    payload: ProductEventPayload

    @model_validator(mode="after")
    def validate_payload_for_event(self) -> "ProductEventRequest":
        payload = self.payload
        if self.event_type in {"SKU_OUT_OF_STOCK", "SKU_BACK_IN_STOCK"}:
            missing = []
            if payload.sku_id is None:
                missing.append("sku_id")
            if payload.available_quantity is None:
                missing.append("available_quantity")
            if missing:
                fields = ", ".join(missing)
                raise ValueError(f"{self.event_type} payload requires {fields}")
        elif self.event_type == "PRICE_CHANGED":
            missing = []
            if payload.sku_id is None:
                missing.append("sku_id")
            if payload.old_price is None:
                missing.append("old_price")
            if payload.new_price is None:
                missing.append("new_price")
            if missing:
                fields = ", ".join(missing)
                raise ValueError(f"{self.event_type} payload requires {fields}")
        return self


class ProductEventResponse(BaseModel):
    accepted: bool
