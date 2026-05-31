from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.catalog import ImageRef


class CartItemAddRequest(BaseModel):
    sku_id: str
    quantity: int = Field(ge=1)


class CartItem(BaseModel):
    sku_id: str
    product_id: str
    name: str
    sku_code: str | None = None
    quantity: int = Field(ge=1)
    unit_price: int
    unit_price_at_add: int | None = None
    line_total: int
    available_quantity: int = Field(ge=0)
    is_available: bool
    image: ImageRef | None = None

    # Required by the canonical flow/task; absent from the current OpenAPI schema.
    unavailable_reason: str | None = None


class CartResponse(BaseModel):
    id: str | None = None
    items: list[CartItem]
    items_count: int
    subtotal: int
    is_valid: bool
    updated_at: datetime | None = None
