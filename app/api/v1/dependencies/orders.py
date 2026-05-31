from typing import Annotated

from fastapi import Depends, Header
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.domain.exceptions import UnauthorizedException
from app.infrastructure.database.repositories.order import SQLAlchemyOrderRepository


async def resolve_buyer_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise UnauthorizedException("Authentication required")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedException("Invalid authorization header")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise UnauthorizedException("Invalid access token") from exc

    buyer_id = payload.get("sub")
    if not buyer_id:
        raise UnauthorizedException("Invalid access token")
    return str(buyer_id)


async def get_order_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyOrderRepository:
    return SQLAlchemyOrderRepository(session)
