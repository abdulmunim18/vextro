"""merge Module-6.3 warehouse indexes into the acquisition chain

Revision ID: d8f2b4c10e95
Revises: c72fd91e6a31
Create Date: 2026-09-15 15:00:00

Original intent was to add ``scrape_runs`` and warehouse performance
indexes as a sibling branch off ``f6a1c82d09b4``. In parallel, Member 2's
acquisition chain also introduced ``scrape_runs`` (via
``d82f3a91c4e7 create scrape monitoring tables``) with a richer schema
that the scraper's monitoring extension and the ORM model actually use.
Running both branches produced ``relation "scrape_runs" already exists``
on any fresh Alembic upgrade.

Resolution:
- This revision is re-chained after the acquisition head
  ``c72fd91e6a31`` so Alembic exposes a single head.
- The duplicate ``scrape_runs`` creation and its indexes are removed;
  ``d82f3a91c4e7`` remains the sole source of truth for that table.
- The two supplementary warehouse indexes on ``price_history`` and
  ``product_listings`` are preserved because they benefit read-heavy
  queries and do not conflict with any index the acquisition chain
  already created.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d8f2b4c10e95"
down_revision: Union[str, Sequence[str], None] = "c72fd91e6a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this idempotent for databases stamped from a
    # dump that already carried these indexes.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_history_listing_created "
        "ON price_history (listing_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_product_listings_variant_platform "
        "ON product_listings (product_variant_id, platform_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_listings_variant_platform")
    op.execute("DROP INDEX IF EXISTS ix_price_history_listing_created")
