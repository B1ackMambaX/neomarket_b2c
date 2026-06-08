from typing import Protocol


class ProductEventRepository(Protocol):
    async def register_idempotency_key(
        self,
        idempotency_key: str,
        event_type: str,
    ) -> bool:
        """Return True if key was registered, False if it already existed."""
        raise NotImplementedError
