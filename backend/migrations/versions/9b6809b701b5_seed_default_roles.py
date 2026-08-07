
"""Seed default application roles."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# Alembic identifiers
revision: str = '9b6809b701b5'
down_revision: str | None = "11f674572afe"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


roles_table = sa.table(
    "roles",
    sa.column("name", sa.String(length=50)),
    sa.column("description", sa.String(length=255)),
)


def upgrade() -> None:
    """Insert the default VEXTRO roles."""

    op.bulk_insert(
        roles_table,
        [
            {
                "name": "consumer",
                "description": "Uses product search, comparison, alerts and recommendations.",
            },
            {
                "name": "sme",
                "description": "Uses competitor, pricing, demand and inventory intelligence.",
            },
            {
                "name": "admin",
                "description": "Manages users, products, data collection and system operations.",
            },
        ],
    )


def downgrade() -> None:
    """Remove the default VEXTRO roles."""

    op.execute(
        sa.text(
            """
            DELETE FROM roles
            WHERE name IN ('consumer', 'sme', 'admin')
            """
        )
    )