"""create scrape monitoring tables

Revision ID: d82f3a91c4e7
Revises: c91e742ab6d8
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d82f3a91c4e7"
down_revision: Union[str, Sequence[str], None] = "c91e742ab6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("spider_name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "items_discovered",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_ingested",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_rejected",
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
        sa.Column(
            "error_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "trigger_type",
            sa.String(length=20),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "platform IN ('daraz', 'priceoye')",
            name="ck_scrape_runs_platform_valid",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'partial', 'failed')",
            name="ck_scrape_runs_status_valid",
        ),
        sa.CheckConstraint(
            "trigger_type IN ('manual', 'scheduler', 'test')",
            name="ck_scrape_runs_trigger_type_valid",
        ),
        sa.CheckConstraint(
            "items_discovered >= 0",
            name="ck_scrape_runs_discovered_non_negative",
        ),
        sa.CheckConstraint(
            "items_ingested >= 0",
            name="ck_scrape_runs_ingested_non_negative",
        ),
        sa.CheckConstraint(
            "items_rejected >= 0",
            name="ck_scrape_runs_rejected_non_negative",
        ),
        sa.CheckConstraint(
            "items_failed >= 0",
            name="ck_scrape_runs_failed_non_negative",
        ),
        sa.CheckConstraint(
            "error_count >= 0",
            name="ck_scrape_runs_error_count_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrape_runs_platform", "scrape_runs", ["platform"])
    op.create_index("ix_scrape_runs_started_at", "scrape_runs", ["started_at"])
    op.create_index("ix_scrape_runs_status", "scrape_runs", ["status"])

    op.create_table(
        "scrape_errors",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("scrape_run_id", sa.BigInteger(), nullable=False),
        sa.Column("external_listing_id", sa.String(length=150), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=False),
        sa.Column("error_stage", sa.String(length=30), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("raw_value", sa.String(length=500), nullable=True),
        sa.Column(
            "error_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "error_stage IN ("
            "'fetch', 'parse', 'validation', "
            "'matching', 'delivery', 'ingestion'"
            ")",
            name="ck_scrape_errors_stage_valid",
        ),
        sa.ForeignKeyConstraint(
            ["scrape_run_id"],
            ["scrape_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scrape_errors_scrape_run_id",
        "scrape_errors",
        ["scrape_run_id"],
    )
    op.create_index(
        "ix_scrape_errors_error_type",
        "scrape_errors",
        ["error_type"],
    )
    op.create_index(
        "ix_scrape_errors_created_at",
        "scrape_errors",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scrape_errors_created_at", table_name="scrape_errors")
    op.drop_index("ix_scrape_errors_error_type", table_name="scrape_errors")
    op.drop_index("ix_scrape_errors_scrape_run_id", table_name="scrape_errors")
    op.drop_table("scrape_errors")

    op.drop_index("ix_scrape_runs_status", table_name="scrape_runs")
    op.drop_index("ix_scrape_runs_started_at", table_name="scrape_runs")
    op.drop_index("ix_scrape_runs_platform", table_name="scrape_runs")
    op.drop_table("scrape_runs")
