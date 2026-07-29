"""Seed default platforms.

Revision ID: b17e73947d94
Revises: ac131bd3099f
Create Date: 2026-07-30 01:01:24.891886
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "b17e73947d94"
down_revision: Union[str, Sequence[str], None] = "ac131bd3099f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


platforms_table = sa.table(
    "platforms",
    sa.column(
        "name",
        sa.String(length=100),
    ),
    sa.column(
        "code",
        sa.String(length=50),
    ),
    sa.column(
        "base_url",
        sa.String(length=500),
    ),
    sa.column(
        "is_active",
        sa.Boolean(),
    ),
)


def upgrade() -> None:
    """Insert the default VEXTRO marketplaces."""

    op.bulk_insert(
        platforms_table,
        [
            {
                "name": "Daraz",
                "code": "daraz",
                "base_url": "https://www.daraz.pk",
                "is_active": True,
            },
            {
                "name": "PriceOye",
                "code": "priceoye",
                "base_url": "https://priceoye.pk",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    """Remove the default VEXTRO marketplaces."""

    op.execute(
        sa.text(
            """
            DELETE FROM platforms
            WHERE code IN ('daraz', 'priceoye')
            """
        )
    )