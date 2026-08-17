"""create price forecasts

Revision ID: f6a1c82d09b4
Revises: c72e45140b90
Create Date: 2026-08-12 20:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a1c82d09b4"
down_revision: Union[str, Sequence[str], None] = "c72e45140b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_forecasts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("product_variant_id", sa.BigInteger(), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'PKR'"),
            nullable=False,
        ),
        sa.Column("training_observation_count", sa.Integer(), nullable=False),
        sa.Column("training_started_at", sa.DateTime(timezone=True)),
        sa.Column("training_ended_at", sa.DateTime(timezone=True)),
        sa.Column("mae", sa.Numeric(precision=14, scale=2)),
        sa.Column("rmse", sa.Numeric(precision=14, scale=2)),
        sa.Column("mape", sa.Numeric(precision=8, scale=2)),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column(
            "forecast_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("horizon_days > 0", name="ck_price_forecasts_horizon_positive"),
        sa.CheckConstraint("training_observation_count > 0", name="ck_price_forecasts_observations_positive"),
        sa.CheckConstraint("char_length(currency) = 3", name="ck_price_forecasts_currency_length"),
        sa.CheckConstraint("confidence IN ('low', 'medium', 'high')", name="ck_price_forecasts_confidence"),
        sa.CheckConstraint("mae IS NULL OR mae >= 0", name="ck_price_forecasts_mae_non_negative"),
        sa.CheckConstraint("rmse IS NULL OR rmse >= 0", name="ck_price_forecasts_rmse_non_negative"),
        sa.CheckConstraint("mape IS NULL OR mape >= 0", name="ck_price_forecasts_mape_non_negative"),
        sa.ForeignKeyConstraint(["product_variant_id"], ["product_variants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_price_forecasts_product_variant_id"),
        "price_forecasts",
        ["product_variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_price_forecasts_variant_active_generated",
        "price_forecasts",
        ["product_variant_id", "is_active", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_price_forecasts_variant_active_generated", table_name="price_forecasts")
    op.drop_index(op.f("ix_price_forecasts_product_variant_id"), table_name="price_forecasts")
    op.drop_table("price_forecasts")
