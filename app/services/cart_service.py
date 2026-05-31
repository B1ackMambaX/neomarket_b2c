from datetime import datetime, timezone
from typing import Any

import httpx

from app.domain.entities.cart import CartIdentity
from app.domain.exceptions import (
    ConflictException,
    NotFoundException,
    UpstreamServiceUnavailableException,
    UnauthorizedException,
)
from app.domain.repositories.cart import CartRepository
from app.schemas.cart import (
    CartItem,
    CartItemAddRequest,
    CartItemQuantityUpdateRequest,
    CartResponse,
    CartValidationIssue,
    CartValidationResponse,
)
from app.schemas.catalog import ImageRef


class CartService:
    def __init__(self, repository: CartRepository, b2b_client: Any) -> None:
        self._repository = repository
        self._b2b_client = b2b_client

    async def get_cart(self, identity: CartIdentity) -> CartResponse:
        stored_items = await self._repository.list_items(identity)
        if not stored_items:
            return CartResponse(
                id=identity.response_id,
                items=[],
                items_count=0,
                subtotal=0,
                is_valid=True,
                updated_at=datetime.now(timezone.utc),
            )

        sku_payloads = await self._load_skus([item.sku_id for item in stored_items])
        product_ids = sorted(
            {
                sku["product_id"]
                for sku in sku_payloads.values()
                if sku is not None and sku.get("product_id")
            }
        )
        products = await self._load_products(product_ids)

        items = [
            self._map_item(
                sku_id=item.sku_id,
                quantity=item.quantity,
                sku=sku_payloads.get(item.sku_id),
                product=products.get(sku_payloads[item.sku_id]["product_id"])
                if sku_payloads.get(item.sku_id)
                else None,
            )
            for item in stored_items
        ]
        subtotal = sum(item.line_total for item in items)
        is_valid = all(
            item.is_available and item.quantity <= item.available_quantity
            for item in items
        )
        updated_at = max(
            (item.updated_at for item in stored_items if item.updated_at is not None),
            default=datetime.now(timezone.utc),
        )

        return CartResponse(
            id=identity.response_id,
            items=items,
            items_count=sum(item.quantity for item in items),
            subtotal=subtotal,
            is_valid=is_valid,
            updated_at=updated_at,
        )

    async def add_item(
        self,
        identity: CartIdentity,
        request: CartItemAddRequest,
    ) -> CartResponse:
        sku = await self._load_sku_for_add(request.sku_id)
        product = await self._load_product_for_add(sku.get("product_id"))
        existing = await self._repository.get_item(identity, request.sku_id)
        requested_total = request.quantity + (existing.quantity if existing else 0)

        if self._unavailable_reason(sku=sku, product=product) is not None:
            raise NotFoundException("SKU not found or product unavailable")
        if requested_total > int(sku.get("active_quantity") or 0):
            raise ConflictException("Insufficient stock")

        await self._repository.add_item(
            identity=identity,
            sku_id=request.sku_id,
            quantity=request.quantity,
        )
        return await self.get_cart(identity)

    async def update_item_quantity(
        self,
        identity: CartIdentity,
        sku_id: str,
        request: CartItemQuantityUpdateRequest,
    ) -> CartResponse:
        existing = await self._repository.get_item(identity, sku_id)
        if existing is None:
            raise NotFoundException("Cart item not found")

        sku = await self._load_sku_for_add(sku_id)
        product = await self._load_product_for_add(sku.get("product_id"))
        if self._unavailable_reason(sku=sku, product=product) is not None:
            raise NotFoundException("SKU not found or product unavailable")
        if request.quantity > int(sku.get("active_quantity") or 0):
            raise ConflictException("Insufficient stock")

        await self._repository.update_item_quantity(
            identity=identity,
            sku_id=sku_id,
            quantity=request.quantity,
        )
        return await self.get_cart(identity)

    async def delete_item(self, identity: CartIdentity, sku_id: str) -> CartResponse:
        existing = await self._repository.get_item(identity, sku_id)
        if existing is None:
            raise NotFoundException("Cart item not found")

        await self._repository.delete_item(identity, sku_id)
        return await self.get_cart(identity)

    async def clear(self, identity: CartIdentity) -> None:
        await self._repository.clear(identity)

    async def validate(self, identity: CartIdentity) -> CartValidationResponse:
        cart = await self.get_cart(identity)
        issues: list[CartValidationIssue] = []

        for item in cart.items:
            if not item.is_available:
                issues.append(
                    CartValidationIssue(
                        sku_id=item.sku_id,
                        type=self._validation_issue_type(item.unavailable_reason),
                        message=self._validation_message(item),
                        old_value=item.quantity,
                        new_value=item.available_quantity,
                    )
                )
                continue

            if item.quantity > item.available_quantity:
                issues.append(
                    CartValidationIssue(
                        sku_id=item.sku_id,
                        type="QUANTITY_REDUCED",
                        message="Requested quantity exceeds available stock",
                        old_value=item.quantity,
                        new_value=item.available_quantity,
                    )
                )

        return CartValidationResponse(
            is_valid=not issues,
            cart=cart,
            issues=issues,
        )

    async def merge_guest_cart(
        self,
        identity: CartIdentity,
        guest_session_id: str,
    ) -> CartResponse:
        if not identity.is_authenticated:
            raise UnauthorizedException("Authentication required")

        await self._repository.merge_guest_cart(identity, guest_session_id)
        return await self.get_cart(identity)

    async def _load_sku_for_add(self, sku_id: str) -> dict[str, Any]:
        try:
            return await self._b2b_client.get_public_sku(sku_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise NotFoundException("SKU not found or product unavailable") from exc
            raise UpstreamServiceUnavailableException(
                "Catalog upstream failed"
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceUnavailableException(
                "Catalog upstream unavailable"
            ) from exc

    async def _load_product_for_add(
        self,
        product_id: str | None,
    ) -> dict[str, Any] | None:
        if not product_id:
            return None
        return (await self._load_products([product_id])).get(product_id)

    async def _load_skus(self, sku_ids: list[str]) -> dict[str, dict[str, Any] | None]:
        result: dict[str, dict[str, Any] | None] = {}
        for sku_id in sku_ids:
            try:
                result[sku_id] = await self._b2b_client.get_public_sku(sku_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    result[sku_id] = None
                    continue
                raise UpstreamServiceUnavailableException(
                    "Catalog upstream failed"
                ) from exc
            except httpx.HTTPError as exc:
                raise UpstreamServiceUnavailableException(
                    "Catalog upstream unavailable"
                ) from exc
        return result

    async def _load_products(self, product_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not product_ids:
            return {}
        try:
            payload = await self._b2b_client.batch_public_products(product_ids)
        except httpx.HTTPError as exc:
            raise UpstreamServiceUnavailableException(
                "Catalog upstream unavailable"
            ) from exc

        items = payload.get("items", payload) if isinstance(payload, dict) else payload
        return {item["id"]: item for item in items}

    def _map_item(
        self,
        *,
        sku_id: str,
        quantity: int,
        sku: dict[str, Any] | None,
        product: dict[str, Any] | None,
    ) -> CartItem:
        product_id = (sku or {}).get("product_id") or (product or {}).get("id") or sku_id
        active_quantity = int((sku or {}).get("active_quantity") or 0)
        unit_price = self._current_price(sku)
        reason = self._unavailable_reason(sku=sku, product=product)
        is_available = reason is None
        line_total = unit_price * quantity if is_available else 0

        return CartItem(
            sku_id=sku_id,
            product_id=product_id,
            name=self._display_name(sku=sku, product=product, fallback=sku_id),
            sku_code=(sku or {}).get("article"),
            quantity=quantity,
            unit_price=unit_price,
            unit_price_at_add=None,
            line_total=line_total,
            available_quantity=active_quantity,
            is_available=is_available,
            image=self._image(sku=sku, product=product, entity_id=sku_id),
            unavailable_reason=reason,
        )

    def _current_price(self, sku: dict[str, Any] | None) -> int:
        if sku is None:
            return 0
        return max(int(sku.get("price") or 0) - int(sku.get("discount") or 0), 0)

    def _unavailable_reason(
        self,
        *,
        sku: dict[str, Any] | None,
        product: dict[str, Any] | None,
    ) -> str | None:
        if sku is None:
            return "PRODUCT_DELETED"
        if int(sku.get("active_quantity") or 0) == 0:
            return "OUT_OF_STOCK"
        if product is None:
            return "PRODUCT_DELETED"

        status = product.get("status")
        if status in {"BLOCKED", "HARD_BLOCKED"}:
            return "PRODUCT_BLOCKED"
        if status in {"CREATED", "ON_MODERATION"}:
            return "ON_MODERATION"
        return None

    def _validation_issue_type(self, reason: str | None) -> str:
        if reason == "OUT_OF_STOCK":
            return "OUT_OF_STOCK"
        if reason == "PRODUCT_BLOCKED":
            return "PRODUCT_BLOCKED"
        if reason in {"PRODUCT_DELETED", "PRODUCT_DELISTED", "ON_MODERATION"}:
            return "PRODUCT_DELETED"
        return "PRODUCT_DELETED"

    def _validation_message(self, item: CartItem) -> str:
        if item.unavailable_reason == "OUT_OF_STOCK":
            return "SKU is out of stock"
        if item.unavailable_reason == "PRODUCT_BLOCKED":
            return "Product is blocked"
        if item.unavailable_reason == "ON_MODERATION":
            return "Product is temporarily unavailable"
        return "Product is unavailable"

    def _display_name(
        self,
        *,
        sku: dict[str, Any] | None,
        product: dict[str, Any] | None,
        fallback: str,
    ) -> str:
        product_title = (product or {}).get("title") or (product or {}).get("name")
        sku_name = (sku or {}).get("name")
        if product_title and sku_name:
            return f"{product_title} {sku_name}"
        return product_title or sku_name or fallback

    def _image(
        self,
        *,
        sku: dict[str, Any] | None,
        product: dict[str, Any] | None,
        entity_id: str,
    ) -> ImageRef | None:
        images = (sku or {}).get("images") or (product or {}).get("images") or []
        if not images:
            return None
        image = images[0]
        return ImageRef(
            id=image.get("id") or f"{entity_id}:image:0",
            url=image["url"],
            alt=image.get("alt"),
            ordering=image.get("ordering", 0),
            is_main=image.get("is_main", True),
        )
