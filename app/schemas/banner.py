from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BannerItem(BaseModel):
    id: UUID
    title: str
    image_url: str
    link: str
    priority: int


class BannersResponse(BaseModel):
    items: list[BannerItem]
    total_count: int


class BannerEventItem(BaseModel):
    banner_id: UUID
    event: Literal["impression", "click"]
    timestamp: datetime


class BannerEventsRequest(BaseModel):
    events: list[BannerEventItem] = Field(min_length=1)
