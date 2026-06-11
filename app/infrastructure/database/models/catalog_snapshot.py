from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class CatalogSnapshotModel(Base):
    __tablename__ = "catalog_snapshots"
    __table_args__ = (Index("ix_catalog_snapshots_category_id", "category_id"),)

    product_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    characteristics: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    min_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
