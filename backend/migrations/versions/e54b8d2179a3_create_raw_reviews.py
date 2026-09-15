"""create raw reviews

Revision ID: e54b8d2179a3
Revises: d82f3a91c4e7
Create Date: 2026-09-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e54b8d2179a3"
down_revision: str | None = "d82f3a91c4e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_reviews",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("platform_id", sa.BigInteger(), nullable=False),
        sa.Column("product_listing_id", sa.BigInteger(), nullable=False),
        sa.Column("seller_id", sa.BigInteger(), nullable=True),
        sa.Column("external_review_id", sa.String(length=150), nullable=True),
        sa.Column("review_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reviewer_external_id", sa.String(length=150), nullable=True),
        sa.Column("reviewer_display_name", sa.String(length=255), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_purchase", sa.Boolean(), nullable=True),
        sa.Column("helpful_count", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_raw_reviews_rating_range",
        ),
        sa.CheckConstraint(
            "helpful_count IS NULL OR helpful_count >= 0",
            name="ck_raw_reviews_helpful_count_non_negative",
        ),
        sa.CheckConstraint(
            "char_length(review_fingerprint) = 64",
            name="ck_raw_reviews_fingerprint_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"],
            ["platforms.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_listing_id"],
            ["product_listings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"],
            ["sellers.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform_id",
            "external_review_id",
            name="uq_raw_reviews_platform_external_id",
        ),
        sa.UniqueConstraint(
            "platform_id",
            "review_fingerprint",
            name="uq_raw_reviews_platform_fingerprint",
        ),
    )
    op.create_index(
        "ix_raw_reviews_platform_id",
        "raw_reviews",
        ["platform_id"],
    )
    op.create_index(
        "ix_raw_reviews_product_listing_id",
        "raw_reviews",
        ["product_listing_id"],
    )
    op.create_index(
        "ix_raw_reviews_seller_id",
        "raw_reviews",
        ["seller_id"],
    )
    op.create_index(
        "ix_raw_reviews_reviewed_at",
        "raw_reviews",
        ["reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_reviews_reviewed_at", table_name="raw_reviews")
    op.drop_index("ix_raw_reviews_seller_id", table_name="raw_reviews")
    op.drop_index(
        "ix_raw_reviews_product_listing_id",
        table_name="raw_reviews",
    )
    op.drop_index("ix_raw_reviews_platform_id", table_name="raw_reviews")
    op.drop_table("raw_reviews")
