from typing import Annotated

from fastapi import Depends, Header
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.infrastructure.database.repositories.banner import SQLAlchemyBannerRepository


async def get_banner_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyBannerRepository:
    return SQLAlchemyBannerRepository(session)


async def resolve_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None

    user_id = payload.get("sub")
    return str(user_id) if user_id else None
