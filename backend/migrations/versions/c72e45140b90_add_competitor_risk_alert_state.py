"""add competitor risk alert state

Revision ID: c72e45140b90
Revises: b41fd6201a8e
Create Date: 2026-08-12 12:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c72e45140b90"
down_revision: Union[str, Sequence[str], None] = "b41fd6201a8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "competitor_watchlists",
        sa.Column(
            "risk_threshold_percentage",
            sa.Numeric(precision=5, scale=2),
            server_default=sa.text("5.00"),
            nullable=False,
        ),
    )
    op.add_column(
        "competitor_watchlists",
        sa.Column("last_risk_level", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "competitor_watchlists",
        sa.Column(
            "last_alerted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("competitor_watchlists", "last_alerted_at")
    op.drop_column("competitor_watchlists", "last_risk_level")
    op.drop_column(
        "competitor_watchlists",
        "risk_threshold_percentage",
    )
