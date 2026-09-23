"""create versioned review analyses

Revision ID: f72a1e9c4b60
Revises: e54b8d2179a3
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f72a1e9c4b60"
down_revision: str | None = "e54b8d2179a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_analyses",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("raw_review_id", sa.BigInteger(), sa.ForeignKey("raw_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_version", sa.String(50), nullable=False),
        sa.Column("suspicion_score", sa.Integer(), nullable=False),
        sa.Column("suspicion_level", sa.String(10), nullable=False),
        sa.Column("duplicate_similarity_score", sa.Integer(), nullable=False),
        sa.Column("text_anomaly_score", sa.Integer(), nullable=False),
        sa.Column("rating_anomaly_score", sa.Integer(), nullable=False),
        sa.Column("temporal_anomaly_score", sa.Integer(), nullable=False),
        sa.Column("reviewer_anomaly_score", sa.Integer(), nullable=False),
        sa.Column("is_exact_duplicate", sa.Boolean(), nullable=False),
        sa.Column("is_near_duplicate", sa.Boolean(), nullable=False),
        sa.Column("signals", postgresql.JSONB(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("suspicion_score BETWEEN 0 AND 100", name="ck_review_analyses_score_range"),
        sa.CheckConstraint("suspicion_level IN ('low', 'medium', 'high')", name="ck_review_analyses_level"),
        sa.CheckConstraint("duplicate_similarity_score BETWEEN 0 AND 100", name="ck_review_analyses_similarity_range"),
        sa.UniqueConstraint("raw_review_id", "analysis_version", name="uq_review_analyses_review_version"),
    )
    op.create_index("ix_review_analyses_raw_review_id", "review_analyses", ["raw_review_id"])


def downgrade() -> None:
    op.drop_index("ix_review_analyses_raw_review_id", table_name="review_analyses")
    op.drop_table("review_analyses")
