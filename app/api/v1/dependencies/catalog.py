from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.infrastructure.database.repositories.collection import (
    SQLAlchemyCollectionRepository,
)
from app.infrastructure.external.b2b_catalog_client import B2BCatalogClient


async def get_b2b_catalog_client() -> B2BCatalogClient:
    return B2BCatalogClient()


async def get_collections_repository(
    session: AsyncSession = Depends(get_db),
) -> SQLAlchemyCollectionRepository:
    return SQLAlchemyCollectionRepository(session)
