"""create product subscriptions

Revision ID: 20260607_0004
Revises: 20260603_0003
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260607_0004"
down_revision: str | None = "20260603_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_subscriptions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("product_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column(
            "events",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_product_subscriptions_user_product",
        ),
    )


def downgrade() -> None:
    op.drop_table("product_subscriptions")
