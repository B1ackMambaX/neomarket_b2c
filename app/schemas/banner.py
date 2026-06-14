from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BannerItem(BaseModel):
    id: UUID
    title: str
    image_url: str
    link: str
    ordering: int
    active_from: datetime | None = None
    active_to: datetime | None = None


class BannerEventItem(BaseModel):
    banner_id: UUID
    event: Literal["impression", "click"]
    timestamp: datetime


class BannerEventsRequest(BaseModel):
    events: list[BannerEventItem] = Field(min_length=1)
