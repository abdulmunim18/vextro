"""add on-demand scrape trigger

Revision ID: d84f2a19c630
Revises: b3d7f20a6c81
Create Date: 2026-10-14
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d84f2a19c630"
down_revision: Union[str, Sequence[str], None] = "b3d7f20a6c81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_scrape_runs_trigger_type_valid",
        "scrape_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_scrape_runs_trigger_type_valid",
        "scrape_runs",
        "trigger_type IN ('manual', 'on_demand', 'scheduler', 'test')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE scrape_runs SET trigger_type = 'manual' "
        "WHERE trigger_type = 'on_demand'"
    )
    op.drop_constraint(
        "ck_scrape_runs_trigger_type_valid",
        "scrape_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_scrape_runs_trigger_type_valid",
        "scrape_runs",
        "trigger_type IN ('manual', 'scheduler', 'test')",
    )
