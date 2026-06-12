import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import httpx

from app.domain.entities.cart import CartIdentity
from app.domain.entities.order import (
    OrderLineInput,
    StatusHistoryEntry,
    StoredOrder,
    StoredOrderItem,
)
from app.domain.exceptions import (
    B2BUnavailableException,
    CancelNotAllowedException,
    IdempotencyConflictException,
    InvalidRequestException,
    NotFoundException,
    ReserveFailedException,
)
from app.domain.repositories.b2b_catalog import B2BCatalogClientProtocol
from app.domain.repositories.cart import CartRepository
from app.domain.repositories.order import OrderRepository
from app.schemas.order import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderResponse,
    PaginatedOrders,
)

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        cart_repository: CartRepository,
        b2b_client: B2BCatalogClientProtocol,
    ) -> None:
        self._orders = order_repository
        self._cart = cart_repository
        self._b2b_client = b2b_client

    async def create_order(
        self,
        *,
        buyer_id: str,
        request: OrderCreateRequest,
        idempotency_key: str,
    ) -> OrderResponse:
        request_hash = self._request_hash(request)
        existing = await self._orders.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictException(
                    "Idempotency-Key was already used with another request body"
                )
            return OrderResponse.from_entity(existing)

        lines = await self._resolve_lines(buyer_id, request)
        if not lines:
            raise InvalidRequestException("Order items cannot be empty")

        sku_payloads = await self._load_skus([line.sku_id for line in lines])
        product_ids = sorted(
            {
                sku["product_id"]
                for sku in sku_payloads.values()
                if sku is not None and sku.get("product_id")
            }
        )
        products = await self._load_products(product_ids)
        failed_items = self._validate_lines(lines, sku_payloads, products)
        if failed_items:
            raise ReserveFailedException(failed_items=failed_items)

        order_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        order_items = [
            self._build_item(line, sku_payloads[line.sku_id], products)
            for line in lines
        ]
        subtotal = sum(item.line_total for item in order_items)
        order = StoredOrder(
            id=order_id,
            number=f"NM-{now.year}-{order_id[:8].upper()}",
            buyer_id=buyer_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="PAID",
            items=order_items,
            subtotal=subtotal,
            delivery_cost=0,
            total=subtotal,
            address_id=request.address_id,
            payment_method_id=request.payment_method_id,
            comment=request.comment,
            status_history=[
                StatusHistoryEntry(
                    status="PAID",
                    changed_at=now.isoformat(),
                    reason="mock payment",
                )
            ],
            created_at=now,
            paid_at=now,
        )
        created, is_new = await self._orders.create_or_get_by_idempotency_key(order)
        if not is_new:
            if created.request_hash != request_hash:
                raise IdempotencyConflictException(
                    "Idempotency-Key was already used with another request body"
                )
            return OrderResponse.from_entity(created)

        try:
            await self._reserve(order_id, idempotency_key, lines)
        except Exception:
            await self._orders.delete(order_id)
            raise

        return OrderResponse.from_entity(created)

    async def list_orders(
        self,
        *,
        buyer_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
    ) -> PaginatedOrders:
        orders, total_count = await self._orders.list_for_buyer(
            buyer_id,
            limit=limit,
            offset=offset,
            status=status,
        )
        return PaginatedOrders(
            items=[OrderResponse.from_entity(order) for order in orders],
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    async def get_order(
        self,
        *,
        buyer_id: str,
        order_id: str,
    ) -> OrderResponse:
        order = await self._orders.get_by_id_for_buyer(order_id, buyer_id)
        if order is None:
            raise NotFoundException("Order not found")
        return OrderResponse.from_entity(order)

    async def cancel_order(
        self,
        *,
        buyer_id: str,
        order_id: str,
        request: OrderCancelRequest | None = None,
    ) -> OrderResponse:
        order = await self._orders.get_by_id_for_buyer(
            order_id,
            buyer_id,
            for_update=True,
        )
        if order is None:
            raise NotFoundException("Order not found")

        if order.status not in {"CREATED", "PAID"}:
            raise CancelNotAllowedException(order.status)

        reason = request.reason if request is not None else None
        pending_order = self._with_status(
            order,
            status="CANCEL_PENDING",
            reason=reason,
        )
        saved_pending = await self._orders.save(pending_order)

        try:
            await self._unreserve(saved_pending)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise
            logger.exception(
                "Failed to unreserve order %s (HTTP %s); marked cancel pending",
                order.id,
                exc.response.status_code,
            )
            return OrderResponse.from_entity(saved_pending)
        except httpx.TransportError:
            logger.exception(
                "Failed to unreserve order %s; marked cancel pending",
                order.id,
            )
            return OrderResponse.from_entity(saved_pending)

        cancelled_order = self._with_status(
            saved_pending,
            status="CANCELLED",
            reason=reason,
        )
        saved = await self._orders.save(cancelled_order)
        return OrderResponse.from_entity(saved)

    async def mark_delivered(
        self,
        *,
        order_id: str,
    ) -> OrderResponse:

        order = await self._orders.get_by_id(
            order_id,
            for_update=True,
        )

        if order is None:
            raise NotFoundException(
                "Order not found"
            )

        if order.status != "DELIVERING":
            raise InvalidRequestException(
                "Only DELIVERING order can be delivered"
            )

        delivered_order = self._with_status(
            order,
            status="DELIVERED",
            reason=None,
        )

        saved = await self._orders.save(
            delivered_order
        )

        await self._fulfill(
            saved
        )

        return OrderResponse.from_entity(
            saved
        )

    def _with_status(
        self,
        order: StoredOrder,
        *,
        status: str,
        reason: str | None,
    ) -> StoredOrder:
        now = datetime.now(timezone.utc)
        status_history = [
            *order.status_history,
            StatusHistoryEntry(
                status=status,
                changed_at=now.isoformat(),
                reason=reason,
            ),
        ]
        return replace(
            order,
            status=status,
            cancel_reason=reason,
            status_history=status_history,
            delivered_at=(
                now
                if status == "DELIVERED"
                else order.delivered_at
            ),
        )

    async def _resolve_lines(
        self,
        buyer_id: str,
        request: OrderCreateRequest,
    ) -> list[OrderLineInput]:
        if request.items_snapshot is not None:
            return [
                OrderLineInput(
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
                for item in request.items_snapshot
            ]

        cart_items = await self._cart.list_items(CartIdentity(user_id=buyer_id))
        return [
            OrderLineInput(sku_id=item.sku_id, quantity=item.quantity)
            for item in cart_items
        ]

    async def _load_skus(self, sku_ids: list[str]) -> dict[str, dict[str, Any] | None]:
        async def _fetch_one(sku_id: str) -> tuple[str, dict[str, Any] | None]:
            try:
                return sku_id, await self._b2b_client.get_public_sku(sku_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return sku_id, None
                raise B2BUnavailableException(
                    "Product service is temporarily unavailable"
                ) from exc
            except httpx.HTTPError as exc:
                raise B2BUnavailableException(
                    "Product service is temporarily unavailable"
                ) from exc

        return dict(await asyncio.gather(*[_fetch_one(sku_id) for sku_id in sku_ids]))

    async def _load_products(self, product_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not product_ids:
            return {}
        try:
            payload = await self._b2b_client.batch_public_products(product_ids)
        except httpx.HTTPError as exc:
            raise B2BUnavailableException(
                "Product service is temporarily unavailable"
            ) from exc

        items = payload if isinstance(payload, list) else payload.get("items", [])
        return {item["id"]: item for item in items}

    async def _reserve(
        self,
        order_id: str,
        idempotency_key: str,
        lines: list[OrderLineInput],
    ) -> None:
        try:
            await self._b2b_client.reserve_inventory(
                idempotency_key=idempotency_key,
                order_id=order_id,
                items=[
                    {"sku_id": line.sku_id, "quantity": line.quantity}
                    for line in lines
                ],
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                raise ReserveFailedException(
                    failed_items=self._failed_items_from_response(exc.response)
                ) from exc
            raise B2BUnavailableException(
                "Product service is temporarily unavailable"
            ) from exc
        except httpx.HTTPError as exc:
            raise B2BUnavailableException(
                "Product service is temporarily unavailable"
            ) from exc

    async def _unreserve(self, order: StoredOrder) -> None:
        await self._b2b_client.unreserve_inventory(
            order_id=order.id,
            items=[
                {"sku_id": item.sku_id, "quantity": item.quantity}
                for item in order.items
            ],
        )

    async def _fulfill(
        self,
        order: StoredOrder,
    ) -> None:

        try:
            await self._b2b_client.fulfill_inventory(
                order_id=order.id,
                items=[
                    {
                        "sku_id": item.sku_id,
                        "quantity": item.quantity,
                    }
                    for item in order.items
                ],
            )

        except httpx.HTTPStatusError as exc:

            logger.exception(
                "Failed to fulfill order %s (HTTP %s)",
                order.id,
                exc.response.status_code,
            )

        except httpx.HTTPError:

            logger.exception(
                "Failed to fulfill order %s",
                order.id,
            )

    def _validate_lines(
        self,
        lines: list[OrderLineInput],
        sku_payloads: dict[str, dict[str, Any] | None],
        products: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        failed_items: list[dict[str, Any]] = []
        for line in lines:
            sku = sku_payloads.get(line.sku_id)
            if sku is None:
                failed_items.append(
                    self._failed_item(line, available=0, reason="SKU_NOT_FOUND")
                )
                continue

            product = products.get(sku.get("product_id"))
            if product is None:
                failed_items.append(
                    self._failed_item(line, available=0, reason="PRODUCT_DELETED")
                )
                continue

            status = product.get("status")
            if status in {"BLOCKED", "HARD_BLOCKED"}:
                failed_items.append(
                    self._failed_item(line, available=0, reason="PRODUCT_BLOCKED")
                )
                continue

            available = int(sku.get("active_quantity") or 0)
            if available < line.quantity:
                failed_items.append(
                    self._failed_item(
                        line,
                        available=available,
                        reason="INSUFFICIENT_STOCK"
                        if available > 0
                        else "OUT_OF_STOCK",
                    )
                )

        return failed_items

    def _build_item(
        self,
        line: OrderLineInput,
        sku: dict[str, Any] | None,
        products: dict[str, dict[str, Any]],
    ) -> StoredOrderItem:
        if sku is None:
            raise InvalidRequestException("SKU payload missing after validation")
        product = products[sku["product_id"]]
        product_title = product.get("title") or product.get("name") or sku["product_id"]
        sku_name = sku.get("name") or line.sku_id
        unit_price = (
            line.unit_price
            if line.unit_price is not None
            else self._current_price(sku)
        )
        return StoredOrderItem(
            id=str(uuid.uuid4()),
            sku_id=line.sku_id,
            product_id=sku["product_id"],
            name=f"{product_title} {sku_name}".strip(),
            sku_code=sku.get("article"),
            product_title=product_title,
            sku_name=sku_name,
            quantity=line.quantity,
            unit_price=unit_price,
            line_total=unit_price * line.quantity,
            image_url=self._image_url(sku, product),
        )

    def _current_price(self, sku: dict[str, Any]) -> int:
        return max(int(sku.get("price") or 0) - int(sku.get("discount") or 0), 0)

    def _image_url(self, sku: dict[str, Any], product: dict[str, Any]) -> str | None:
        images = sku.get("images") or product.get("images") or []
        if not images:
            return None
        return images[0].get("url")

    def _failed_item(
        self,
        line: OrderLineInput,
        *,
        available: int,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "sku_id": line.sku_id,
            "requested": line.quantity,
            "available": available,
            "reason": reason,
        }

    def _failed_items_from_response(self, response: httpx.Response) -> list[dict]:
        try:
            payload = response.json()
        except ValueError:
            return []

        if isinstance(payload.get("failed_items"), list):
            return payload["failed_items"]
        details = payload.get("details")
        if isinstance(details, dict) and isinstance(details.get("failed_items"), list):
            return details["failed_items"]
        if isinstance(details, list):
            return details
        return []

    def _request_hash(self, request: OrderCreateRequest) -> str:
        body = request.model_dump(mode="json", exclude_none=True)
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
