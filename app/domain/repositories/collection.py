from datetime import date
from typing import Protocol

from app.domain.entities.collection import StoredCollection


class CollectionRepository(Protocol):
    async def list_active(self, *, as_of: date) -> list[StoredCollection]:
        raise NotImplementedError
