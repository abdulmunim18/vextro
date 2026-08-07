"""seed catalog reference data

Revision ID: 230caa8e6095
Revises: b17e73947d94
Create Date: 2026-07-30 01:10:37.917954

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "230caa8e6095"
down_revision: Union[str, Sequence[str], None] = "b17e73947d94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert initial VEXTRO categories and brands."""

    op.execute(
        sa.text(
            """
            INSERT INTO categories (
                name,
                slug,
                is_active
            )
            VALUES (
                'Electronics',
                'electronics',
                TRUE
            )
            ON CONFLICT (slug) DO NOTHING;
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO categories (
                parent_id,
                name,
                slug,
                is_active
            )
            SELECT
                parent.id,
                category_data.name,
                category_data.slug,
                TRUE
            FROM categories AS parent
            CROSS JOIN (
                VALUES
                    ('Mobile Phones', 'mobile-phones'),
                    ('Laptops', 'laptops'),
                    ('Tablets', 'tablets'),
                    ('Smart Watches', 'smart-watches'),
                    ('Audio and Earbuds', 'audio-and-earbuds'),
                    ('Power Banks', 'power-banks'),
                    ('Mobile Accessories', 'mobile-accessories')
            ) AS category_data(name, slug)
            WHERE parent.slug = 'electronics'
            ON CONFLICT (slug) DO NOTHING;
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO brands (
                name,
                slug,
                is_active
            )
            VALUES
                ('Apple', 'apple', TRUE),
                ('Samsung', 'samsung', TRUE),
                ('Xiaomi', 'xiaomi', TRUE),
                ('Oppo', 'oppo', TRUE),
                ('Vivo', 'vivo', TRUE),
                ('Infinix', 'infinix', TRUE),
                ('Tecno', 'tecno', TRUE),
                ('Realme', 'realme', TRUE),
                ('OnePlus', 'oneplus', TRUE),
                ('Huawei', 'huawei', TRUE),
                ('Honor', 'honor', TRUE),
                ('Nokia', 'nokia', TRUE),
                ('Dell', 'dell', TRUE),
                ('HP', 'hp', TRUE),
                ('Lenovo', 'lenovo', TRUE),
                ('Asus', 'asus', TRUE),
                ('Acer', 'acer', TRUE)
            ON CONFLICT (slug) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    """Remove initial VEXTRO categories and brands."""

    op.execute(
        sa.text(
            """
            DELETE FROM categories
            WHERE slug IN (
                'mobile-phones',
                'laptops',
                'tablets',
                'smart-watches',
                'audio-and-earbuds',
                'power-banks',
                'mobile-accessories'
            );
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM categories
            WHERE slug = 'electronics';
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM brands
            WHERE slug IN (
                'apple',
                'samsung',
                'xiaomi',
                'oppo',
                'vivo',
                'infinix',
                'tecno',
                'realme',
                'oneplus',
                'huawei',
                'honor',
                'nokia',
                'dell',
                'hp',
                'lenovo',
                'asus',
                'acer'
            );
            """
        )
    )