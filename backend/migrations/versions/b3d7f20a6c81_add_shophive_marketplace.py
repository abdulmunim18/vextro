"""add Shophive as a marketplace

Revision ID: b3d7f20a6c81
Revises: a9c5e17d3f42
Create Date: 2026-10-11

Shophive is a third source of offers. A marketplace is a row in
``platforms``; the two check constraints below also name every code a
crawl run or an unmatched listing may carry, so both are widened.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b3d7f20a6c81"
down_revision: Union[str, Sequence[str], None] = "a9c5e17d3f42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The scraper cannot deliver a listing for a marketplace that has no
    # row here. Daraz and PriceOye were added by a seed script; this one
    # arrives with the migration so no extra step is needed.
    op.execute(
        """
        INSERT INTO platforms (name, code, base_url, is_active)
        SELECT 'Shophive', 'shophive', 'https://www.shophive.com', true
        WHERE NOT EXISTS (
            SELECT 1 FROM platforms
            WHERE code = 'shophive' OR name = 'Shophive'
        )
        """
    )

    op.drop_constraint(
        "ck_scrape_runs_platform_valid", "scrape_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_scrape_runs_platform_valid",
        "scrape_runs",
        "platform IN ('daraz', 'priceoye', 'shophive', 'whatmobile')",
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


def downgrade() -> None:
    # Listings, their price history and the platform row are left in
    # place: removing a marketplace's offers is a decision, not a
    # side effect of stepping a migration back. Only the rows the
    # narrower constraints could not hold are removed.
    op.execute("DELETE FROM scrape_runs WHERE platform = 'shophive'")
    op.execute(
        "DELETE FROM pending_product_matches WHERE platform_code = 'shophive'"
    )
    op.execute(
        "UPDATE platforms SET is_active = false WHERE code = 'shophive'"
    )

    op.drop_constraint(
        "ck_pending_product_matches_platform_valid",
        "pending_product_matches",
        type_="check",
    )
    op.create_check_constraint(
        "ck_pending_product_matches_platform_valid",
        "pending_product_matches",
        "platform_code IN ('daraz', 'priceoye')",
    )

    op.drop_constraint(
        "ck_scrape_runs_platform_valid", "scrape_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_scrape_runs_platform_valid",
        "scrape_runs",
        "platform IN ('daraz', 'priceoye', 'whatmobile')",
    )
