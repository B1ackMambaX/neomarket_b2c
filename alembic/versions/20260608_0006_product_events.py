"""add cart unavailable_reason and product event idempotency keys

Revision ID: 20260608_0006
Revises: 20260607_0005
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0006"
down_revision: str | None = "20260607_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cart_items",
        sa.Column("unavailable_reason", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "product_event_idempotency_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_product_event_idempotency_keys_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("product_event_idempotency_keys")
    op.drop_column("cart_items", "unavailable_reason")
