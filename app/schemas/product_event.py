from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ProductEventType = Literal["PRODUCT_BLOCKED", "PRODUCT_DELETED", "SKU_OUT_OF_STOCK"]


class ProductEventRequest(BaseModel):
    idempotency_key: str
    event: ProductEventType
    product_id: str
    sku_ids: list[str] = Field(min_length=1)
    reason: str | None = None
    date: datetime


class ProductEventResponse(BaseModel):
    accepted: bool
