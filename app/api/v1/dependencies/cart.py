from typing import Annotated

from fastapi import Depends, Header
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.domain.entities.cart import CartIdentity
from app.domain.exceptions import MissingCartIdentityException, UnauthorizedException
from app.infrastructure.database.repositories.cart import SQLAlchemyCartRepository


async def resolve_cart_identity(
    authorization: Annotated[str | None, Header()] = None,
    session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
) -> CartIdentity:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise UnauthorizedException("Invalid authorization header")
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except JWTError as exc:
            raise UnauthorizedException("Invalid access token") from exc
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid access token")
        return CartIdentity(user_id=str(user_id))

    if session_id:
        return CartIdentity(session_id=session_id)

    raise MissingCartIdentityException("X-Session-Id or Authorization is required")


async def get_cart_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyCartRepository:
    return SQLAlchemyCartRepository(session)
