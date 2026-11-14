"""add microwave ovens under home appliances

Revision ID: e8b4c2a6d913
Revises: d1a7e3f5c284
Create Date: 2026-10-27

Solo, grill, convection and built-in microwaves. Baking ovens, toaster
ovens and air fryers are other appliances and are not filed here.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e8b4c2a6d913"
down_revision: Union[str, Sequence[str], None] = "d1a7e3f5c284"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO categories (parent_id, name, slug, is_active)
        SELECT parent.id, 'Microwave Ovens', 'microwave-ovens', TRUE
        FROM categories AS parent
        WHERE parent.slug = 'home-appliances'
        ON CONFLICT (slug) DO UPDATE SET is_active = TRUE
        """
    )


def downgrade() -> None:
    # Products filed under it stay; the category is only switched off.
    op.execute("UPDATE categories SET is_active = false WHERE slug = 'microwave-ovens'")
