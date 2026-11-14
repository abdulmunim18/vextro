"""add refrigerators and freezers under home appliances

Revision ID: c6f2d8a41b93
Revises: a4e8b1c3d927
Create Date: 2026-10-27

Fridges and freezers are one category: the stores sell them side by side
and both are named by a model code.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c6f2d8a41b93"
down_revision: Union[str, Sequence[str], None] = "a4e8b1c3d927"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO categories (parent_id, name, slug, is_active)
        SELECT parent.id, 'Refrigerators & Freezers', 'refrigerators', TRUE
        FROM categories AS parent
        WHERE parent.slug = 'home-appliances'
        ON CONFLICT (slug) DO UPDATE SET is_active = TRUE
        """
    )


def downgrade() -> None:
    # Products filed under it stay; the category is only switched off.
    op.execute("UPDATE categories SET is_active = false WHERE slug = 'refrigerators'")
