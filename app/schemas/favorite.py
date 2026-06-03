from datetime import datetime

from pydantic import BaseModel

from app.schemas.catalog import CatalogProductCard


class FavoriteMutationResponse(BaseModel):
    id: str
    product_id: str
    added_at: datetime | None = None


class FavoritesResponse(BaseModel):
    items: list[CatalogProductCard]
    total_count: int
    limit: int
    offset: int
