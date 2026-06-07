from typing import Final

from app.domain.entities.cart import CartIdentity
from app.domain.entities.subscription import StoredProductSubscription
from app.domain.exceptions import (
    InvalidNotifyOnException,
    ProductNotFoundException,
    SubscriptionAlreadyExistsException,
    UnauthorizedException,
)
from app.domain.repositories.subscription import ProductSubscriptionRepository
from app.services.favorite_service import FavoriteProductResolver

ALLOWED_SUBSCRIPTION_EVENTS: Final = frozenset(
    {"BACK_IN_STOCK", "PRICE_DROP"}
)


class ProductSubscriptionService:
    def __init__(
        self,
        repository: ProductSubscriptionRepository,
        b2b_client: object,
    ) -> None:
        self._repository = repository
        self._product_resolver = FavoriteProductResolver(b2b_client)

    async def subscribe(
        self,
        identity: CartIdentity,
        product_id: str,
        events: list[str],
    ) -> StoredProductSubscription:
        user_id = self._require_user_id(identity)

        existing = await self._repository.get(user_id, product_id)
        if existing is not None:
            raise SubscriptionAlreadyExistsException(
                "Subscription already exists"
            )

        self._validate_events(events)

        products = await self._product_resolver.load([product_id])
        if product_id not in products:
            raise ProductNotFoundException("Product not found")

        subscription, created = await self._repository.add(
            user_id,
            product_id,
            events,
        )
        if not created:
            raise SubscriptionAlreadyExistsException(
                "Subscription already exists"
            )
        return subscription

    async def unsubscribe(self, identity: CartIdentity, product_id: str) -> None:
        user_id = self._require_user_id(identity)
        await self._repository.delete(user_id, product_id)

    def _validate_events(self, events: list[str]) -> None:
        if not events or any(
            event not in ALLOWED_SUBSCRIPTION_EVENTS for event in events
        ):
            raise InvalidNotifyOnException("Invalid events")

    def _require_user_id(self, identity: CartIdentity) -> str:
        if not identity.is_authenticated or identity.user_id is None:
            raise UnauthorizedException("Authentication required")
        return identity.user_id
