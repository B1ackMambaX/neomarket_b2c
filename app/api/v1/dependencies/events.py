from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.domain.exceptions import UnauthorizedException
from app.infrastructure.database.repositories.product_event import (
    SQLAlchemyProductEventRepository,
)


async def verify_b2b_service_key(
    service_key: Annotated[str | None, Header(alias="X-Service-Key")] = None,
) -> None:
    if not service_key or service_key != settings.B2B_TO_B2C_SERVICE_KEY:
        raise UnauthorizedException("Service key is required")


async def get_product_event_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyProductEventRepository:
    return SQLAlchemyProductEventRepository(session)
