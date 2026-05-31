import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.models.base import Base, TimestampMixin


class OrderModel(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
        Index("ix_orders_buyer_created_at", "buyer_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    buyer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    address_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payment_method_id: Mapped[str] = mapped_column(String(36), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_history: Mapped[list[dict[str, str | None]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    items: Mapped[list["OrderItemModel"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderItemModel.created_at",
    )


class OrderItemModel(TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order_id", "order_id"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    sku_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_title: Mapped[str] = mapped_column(String(512), nullable=False)
    sku_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    order: Mapped[OrderModel] = relationship(back_populates="items")
