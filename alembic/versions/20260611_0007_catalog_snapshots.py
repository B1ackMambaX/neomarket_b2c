"""add catalog_snapshots for local facet computation

Revision ID: 20260611_0007
Revises: 20260608_0006
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260611_0007"
down_revision: str | None = "20260608_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_snapshots",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "characteristics",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("min_price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "has_stock", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index(
        "ix_catalog_snapshots_category_id",
        "catalog_snapshots",
        ["category_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_snapshots_category_id", table_name="catalog_snapshots")
    op.drop_table("catalog_snapshots")
