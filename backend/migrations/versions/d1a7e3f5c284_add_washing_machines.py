"""add washing machines and dryers under home appliances

Revision ID: d1a7e3f5c284
Revises: c6f2d8a41b93
Create Date: 2026-10-27

Washing machines, washer-dryers and dryers are one category: the stores
sell them side by side and all are named by a model code.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d1a7e3f5c284"
down_revision: Union[str, Sequence[str], None] = "c6f2d8a41b93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO categories (parent_id, name, slug, is_active)
        SELECT parent.id, 'Washing Machines & Dryers', 'washing-machines', TRUE
        FROM categories AS parent
        WHERE parent.slug = 'home-appliances'
        ON CONFLICT (slug) DO UPDATE SET is_active = TRUE
        """
    )


def downgrade() -> None:
    # Products filed under it stay; the category is only switched off.
    op.execute("UPDATE categories SET is_active = false WHERE slug = 'washing-machines'")
