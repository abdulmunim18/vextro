"""create scrape runs and warehouse performance indexes

Revision ID: d8f2b4c10e95
Revises: f6a1c82d09b4
Create Date: 2026-09-15 15:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8f2b4c10e95"
down_revision: Union[str, Sequence[str], None] = "f6a1c82d09b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create scrape_runs table
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'RUNNING'"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            sa.String(length=30),
            server_default=sa.text("'MANUAL'"),
            nullable=False,
        ),
        sa.Column(
            "items_scraped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_failed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Indexes for scrape_runs
    op.create_index(
        op.f("ix_scrape_runs_platform"),
        "scrape_runs",
        ["platform"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scrape_runs_status"),
        "scrape_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scrape_runs_started_at"),
        "scrape_runs",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "ix_scrape_runs_platform_status_started",
        "scrape_runs",
        ["platform", "status", "started_at"],
        unique=False,
    )

    # 3. Warehouse performance indexes on existing tables
    op.create_index(
        "ix_price_history_listing_created",
        "price_history",
        ["listing_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_product_listings_variant_platform",
        "product_listings",
        ["product_variant_id", "platform_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_product_listings_variant_platform", table_name="product_listings")

    op.drop_index("ix_price_history_listing_created", table_name="price_history")
    op.drop_index("ix_scrape_runs_platform_status_started", table_name="scrape_runs")
    op.drop_index(op.f("ix_scrape_runs_started_at"), table_name="scrape_runs")
    op.drop_index(op.f("ix_scrape_runs_status"), table_name="scrape_runs")
    op.drop_index(op.f("ix_scrape_runs_platform"), table_name="scrape_runs")
    op.drop_table("scrape_runs")
