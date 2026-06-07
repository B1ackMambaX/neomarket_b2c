from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.cart import resolve_cart_identity
from app.core.dependencies import get_db
from app.domain.entities.cart import CartIdentity
from app.domain.exceptions import UnauthorizedException
from app.infrastructure.database.repositories.favorite import (
    SQLAlchemyFavoriteRepository,
)
from app.infrastructure.database.repositories.subscription import (
    SQLAlchemyProductSubscriptionRepository,
)


async def resolve_favorites_identity(
    authorization: Annotated[str | None, Header()] = None,
    session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
) -> CartIdentity:
    if not authorization:
        raise UnauthorizedException("Authentication required")

    identity = await resolve_cart_identity(
        authorization=authorization,
        session_id=session_id,
    )
    if not identity.is_authenticated:
        raise UnauthorizedException("Authentication required")
    try:
        UUID(identity.user_id or "")
    except ValueError as exc:
        raise UnauthorizedException("Invalid access token") from exc
    return identity


async def get_favorites_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyFavoriteRepository:
    return SQLAlchemyFavoriteRepository(session)


async def get_product_subscriptions_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyProductSubscriptionRepository:
    return SQLAlchemyProductSubscriptionRepository(session)
