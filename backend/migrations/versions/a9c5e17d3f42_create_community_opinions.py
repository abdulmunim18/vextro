"""create community opinions and allow guide-site scrape runs

Revision ID: a9c5e17d3f42
Revises: e4f3a2b1c0d9
Create Date: 2026-10-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a9c5e17d3f42"
down_revision: Union[str, Sequence[str], None] = "e4f3a2b1c0d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_community_ratings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("canonical_product_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_product_name", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("opinions_url", sa.Text(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("rating_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reference_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_product_id"], ["canonical_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_product_id", "source", name="uq_product_community_ratings_product_source"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 0 AND 5", name="ck_product_community_ratings_rating_range"),
        sa.CheckConstraint("rating_count >= 0", name="ck_product_community_ratings_count_non_negative"),
    )
    op.create_index(
        "ix_product_community_ratings_canonical_product_id",
        "product_community_ratings",
        ["canonical_product_id"],
    )

    op.create_table(
        "community_opinions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("canonical_product_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("opinion_fingerprint", sa.String(64), nullable=False),
        sa.Column("author_display_name", sa.String(120), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opinion_text", sa.Text(), nullable=False),
        sa.Column("contact_removed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_position", sa.Integer(), nullable=True),
        sa.Column("analysis_version", sa.String(50), nullable=True),
        sa.Column("suspicion_score", sa.Integer(), nullable=True),
        sa.Column("suspicion_level", sa.String(10), nullable=True),
        sa.Column("opinion_kind", sa.String(20), nullable=True),
        sa.Column("analysis_reasons", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_product_id"], ["canonical_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "opinion_fingerprint", name="uq_community_opinions_source_fingerprint"),
        sa.CheckConstraint("suspicion_score IS NULL OR suspicion_score BETWEEN 0 AND 100", name="ck_community_opinions_score_range"),
        sa.CheckConstraint("suspicion_level IS NULL OR suspicion_level IN ('low', 'medium', 'high')", name="ck_community_opinions_level"),
    )
    op.create_index(
        "ix_community_opinions_canonical_product_id",
        "community_opinions",
        ["canonical_product_id"],
    )

    # A guide site is crawled and monitored like a marketplace, though it
    # has no listings.
    op.drop_constraint("ck_scrape_runs_platform_valid", "scrape_runs", type_="check")
    op.create_check_constraint(
        "ck_scrape_runs_platform_valid",
        "scrape_runs",
        "platform IN ('daraz', 'priceoye', 'whatmobile')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM scrape_runs WHERE platform = 'whatmobile'")
    op.drop_constraint("ck_scrape_runs_platform_valid", "scrape_runs", type_="check")
    op.create_check_constraint(
        "ck_scrape_runs_platform_valid",
        "scrape_runs",
        "platform IN ('daraz', 'priceoye')",
    )
    op.drop_index("ix_community_opinions_canonical_product_id", table_name="community_opinions")
    op.drop_table("community_opinions")
    op.drop_index("ix_product_community_ratings_canonical_product_id", table_name="product_community_ratings")
    op.drop_table("product_community_ratings")
