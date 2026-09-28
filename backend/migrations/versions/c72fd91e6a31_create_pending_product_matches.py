"""create pending product matches

Revision ID: c72fd91e6a31
Revises: a90c18f64d21
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c72fd91e6a31"
down_revision: str | None = "a90c18f64d21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_product_matches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("platform_code", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("match_payload", postgresql.JSONB(), nullable=False),
        sa.Column("listing_payload", postgresql.JSONB(), nullable=False),
        sa.Column("match_confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("match_reason", sa.String(length=500), nullable=False),
        sa.Column("suggested_product_variant_id", sa.BigInteger(), nullable=True),
        sa.Column("assigned_product_variant_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("resolved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replay_result", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("platform_code IN ('daraz', 'priceoye')", name="ck_pending_product_matches_platform_valid"),
        sa.CheckConstraint("status IN ('pending', 'resolved', 'replayed', 'dismissed')", name="ck_pending_product_matches_status_valid"),
        sa.CheckConstraint("match_confidence BETWEEN 0 AND 100", name="ck_pending_product_matches_confidence_range"),
        sa.ForeignKeyConstraint(["assigned_product_variant_id"], ["product_variants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["suggested_product_variant_id"], ["product_variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform_code", "external_id", name="uq_pending_product_matches_platform_external_id"),
    )
    op.create_index("ix_pending_product_matches_platform_code", "pending_product_matches", ["platform_code"])
    op.create_index("ix_pending_product_matches_status", "pending_product_matches", ["status"])
    op.create_index("ix_pending_product_matches_assigned_product_variant_id", "pending_product_matches", ["assigned_product_variant_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_product_matches_assigned_product_variant_id", table_name="pending_product_matches")
    op.drop_index("ix_pending_product_matches_status", table_name="pending_product_matches")
    op.drop_index("ix_pending_product_matches_platform_code", table_name="pending_product_matches")
    op.drop_table("pending_product_matches")
