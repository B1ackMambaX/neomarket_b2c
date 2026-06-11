from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ProductEventType = Literal[
    "PRODUCT_CREATED",
    "PRODUCT_UPDATED",
    "PRODUCT_BLOCKED",
    "PRODUCT_DELETED",
    "SKU_OUT_OF_STOCK",
    "SKU_BACK_IN_STOCK",
]


class ProductData(BaseModel):
    title: str
    category_id: str | None = None
    characteristics: list[dict[str, Any]] = Field(default_factory=list)
    min_price: int = 0
    has_stock: bool = False


class ProductEventRequest(BaseModel):
    idempotency_key: str
    event: ProductEventType
    product_id: str
    sku_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    date: datetime
    product_data: ProductData | None = None


class ProductEventResponse(BaseModel):
    accepted: bool
