"""create seller trust analyses

Revision ID: a90c18f64d21
Revises: f72a1e9c4b60
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a90c18f64d21"
down_revision: str | None = "f72a1e9c4b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seller_trust_analyses",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("seller_id", sa.BigInteger(), sa.ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_version", sa.String(50), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=True),
        sa.Column("trust_level", sa.String(20), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("confidence_level", sa.String(10), nullable=False),
        sa.Column("total_listings", sa.Integer(), nullable=False),
        sa.Column("total_reviews", sa.Integer(), nullable=False),
        sa.Column("analyzed_reviews", sa.Integer(), nullable=False),
        sa.Column("high_suspicion_review_count", sa.Integer(), nullable=False),
        sa.Column("medium_suspicion_review_count", sa.Integer(), nullable=False),
        sa.Column("low_suspicion_review_count", sa.Integer(), nullable=False),
        sa.Column("analysis_coverage_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("high_suspicion_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("average_review_suspicion_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("verified_purchase_ratio", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_average", sa.Numeric(3, 2), nullable=True),
        sa.Column("rating_variance", sa.Numeric(5, 3), nullable=True),
        sa.Column("signals", postgresql.JSONB(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("seller_id", "analysis_version", name="uq_seller_trust_analyses_seller_version"),
        sa.CheckConstraint("(trust_level = 'insufficient_data' AND trust_score IS NULL) OR (trust_level IN ('low', 'moderate', 'high') AND trust_score BETWEEN 0 AND 100)", name="ck_seller_trust_score_level"),
        sa.CheckConstraint("confidence_score BETWEEN 0 AND 100", name="ck_seller_trust_confidence_range"),
        sa.CheckConstraint("confidence_level IN ('low', 'medium', 'high')", name="ck_seller_trust_confidence_level"),
        sa.CheckConstraint("total_listings >= 0 AND total_reviews >= 0 AND analyzed_reviews >= 0 AND analyzed_reviews <= total_reviews", name="ck_seller_trust_counts"),
        sa.CheckConstraint("analysis_coverage_percentage BETWEEN 0 AND 100", name="ck_seller_trust_coverage_range"),
        sa.CheckConstraint("high_suspicion_percentage BETWEEN 0 AND 100", name="ck_seller_trust_high_rate_range"),
    )
    op.create_index("ix_seller_trust_analyses_seller_id", "seller_trust_analyses", ["seller_id"])


def downgrade() -> None:
    op.drop_index("ix_seller_trust_analyses_seller_id", table_name="seller_trust_analyses")
    op.drop_table("seller_trust_analyses")
