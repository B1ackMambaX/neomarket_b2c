import uuid

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base, TimestampMixin


class CartItemModel(TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_cart_items_quantity_positive"),
        CheckConstraint(
            "(user_id IS NOT NULL AND session_id IS NULL) OR "
            "(user_id IS NULL AND session_id IS NOT NULL)",
            name="ck_cart_items_single_identity",
        ),
        UniqueConstraint("user_id", "sku_id", name="uq_cart_items_user_sku"),
        UniqueConstraint("session_id", "sku_id", name="uq_cart_items_session_sku"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
