"""add listing updated_at and scrape-run outcome counters

Revision ID: a1c4f7e92b08
Revises: d8f2b4c10e95
Create Date: 2026-10-03 12:00:00

``product_listings`` only recorded ``last_seen_at`` (the crawl saw this
listing) which is not the same question as "when did this row last change".
The product page needs both to explain a price to a shopper.

``scrape_runs`` counted items but not outcomes, so a run could not answer
whether a twelve-hour refresh actually moved any prices, created any
products or collected any reviews.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1c4f7e92b08"
down_revision: Union[str, Sequence[str], None] = "d8f2b4c10e95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RUN_COUNTERS = (
    "products_created",
    "listings_created",
    "listings_updated",
    "price_changes",
    "reviews_added",
)


def upgrade() -> None:
    op.add_column(
        "product_listings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Existing rows have never been "updated" beyond their last capture, so
    # seed the column from the timestamp that is already true for them.
    op.execute(
        "UPDATE product_listings SET updated_at = last_seen_at"
    )

    for counter in RUN_COUNTERS:
        op.add_column(
            "scrape_runs",
            sa.Column(
                counter,
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        op.create_check_constraint(
            f"ck_scrape_runs_{counter}_non_negative",
            "scrape_runs",
            f"{counter} >= 0",
        )

    op.add_column(
        "scrape_runs",
        sa.Column("error_summary", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scrape_runs", "error_summary")

    for counter in reversed(RUN_COUNTERS):
        op.drop_constraint(
            f"ck_scrape_runs_{counter}_non_negative",
            "scrape_runs",
            type_="check",
        )
        op.drop_column("scrape_runs", counter)

    op.drop_column("product_listings", "updated_at")
