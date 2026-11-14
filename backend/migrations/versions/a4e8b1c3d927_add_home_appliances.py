"""add home appliances and the stores that sell them

Revision ID: a4e8b1c3d927
Revises: f3c9d6a2e814
Create Date: 2026-10-26

* Home Appliances is a top-level category beside Electronics. Air
  conditioners and televisions are its first children; further appliances
  arrive as rows here, not as code.
* Friends Home, Jalal Electronics and Telemart are appliance retailers. Each
  is a row in ``platforms``, and the two check constraints that name every
  code a crawl run or an unmatched listing may carry are widened.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a4e8b1c3d927"
down_revision: Union[str, Sequence[str], None] = "f3c9d6a2e814"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RUN_PLATFORMS = (
    "'daraz', 'priceoye', 'shophive', 'whatmobile', "
    "'friendshome', 'jalal', 'telemart'"
)
LISTING_PLATFORMS = (
    "'daraz', 'priceoye', 'shophive', 'friendshome', 'jalal', 'telemart'"
)


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO categories (name, slug, is_active)
        VALUES ('Home Appliances', 'home-appliances', TRUE)
        ON CONFLICT (slug) DO UPDATE SET is_active = TRUE
        """
    )
    op.execute(
        """
        INSERT INTO categories (parent_id, name, slug, is_active)
        SELECT parent.id, child.name, child.slug, TRUE
        FROM categories AS parent
        CROSS JOIN (
            VALUES
                ('Air Conditioners', 'air-conditioners'),
                ('Televisions', 'televisions')
        ) AS child(name, slug)
        WHERE parent.slug = 'home-appliances'
        ON CONFLICT (slug) DO UPDATE SET is_active = TRUE
        """
    )

    op.execute(
        """
        INSERT INTO platforms (name, code, base_url, is_active)
        SELECT store.name, store.code, store.base_url, TRUE
        FROM (
            VALUES
                ('Friends Home', 'friendshome', 'https://friendshome.pk'),
                ('Jalal Electronics', 'jalal', 'https://jalalelectronics.com'),
                ('Telemart', 'telemart', 'https://telemart.pk')
        ) AS store(name, code, base_url)
        WHERE NOT EXISTS (
            SELECT 1 FROM platforms
            WHERE platforms.code = store.code OR platforms.name = store.name
        )
        """
    )
    # A downgrade only switches the stores off; coming back up turns them on.
    op.execute(
        "UPDATE platforms SET is_active = TRUE "
        "WHERE code IN ('friendshome', 'jalal', 'telemart')"
    )

    op.drop_constraint(
        "ck_scrape_runs_platform_valid", "scrape_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_scrape_runs_platform_valid",
        "scrape_runs",
        f"platform IN ({RUN_PLATFORMS})",
    )
    op.drop_constraint(
        "ck_pending_product_matches_platform_valid",
        "pending_product_matches",
        type_="check",
    )
    op.create_check_constraint(
        "ck_pending_product_matches_platform_valid",
        "pending_product_matches",
        f"platform_code IN ({LISTING_PLATFORMS})",
    )


def downgrade() -> None:
    # As with Shophive, offers already collected stay; the stores are only
    # switched off, and rows the narrower constraints cannot hold go.
    new_stores = "('friendshome', 'jalal', 'telemart')"
    op.execute(f"DELETE FROM scrape_runs WHERE platform IN {new_stores}")
    op.execute(
        f"DELETE FROM pending_product_matches WHERE platform_code IN {new_stores}"
    )
    op.execute(f"UPDATE platforms SET is_active = false WHERE code IN {new_stores}")
    op.execute(
        """
        UPDATE categories SET is_active = false
        WHERE slug IN ('home-appliances', 'air-conditioners', 'televisions')
        """
    )

    op.drop_constraint(
        "ck_pending_product_matches_platform_valid",
        "pending_product_matches",
        type_="check",
    )
    op.create_check_constraint(
        "ck_pending_product_matches_platform_valid",
        "pending_product_matches",
        "platform_code IN ('daraz', 'priceoye', 'shophive')",
    )
    op.drop_constraint(
        "ck_scrape_runs_platform_valid", "scrape_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_scrape_runs_platform_valid",
        "scrape_runs",
        "platform IN ('daraz', 'priceoye', 'shophive', 'whatmobile')",
    )
