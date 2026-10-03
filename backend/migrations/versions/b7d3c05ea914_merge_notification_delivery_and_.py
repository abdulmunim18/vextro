"""merge notification delivery and smartphone sync heads

Revision ID: b7d3c05ea914
Revises: a1c4e7b20f31, a1c4f7e92b08
Create Date: 2026-10-03 19:38:53.232002

Two sibling revisions branched off ``d8f2b4c10e95`` in parallel:

* ``a1c4e7b20f31`` - notification delivery tables (Module 6.14)
* ``a1c4f7e92b08`` - ``product_listings.updated_at`` and the ``scrape_runs``
  outcome counters (smartphone price synchronisation)

They touch different tables and do not conflict, so this is a pure merge
point: it carries no DDL of its own and exists only to give Alembic a single
head again. Neither parent revision is modified.

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "b7d3c05ea914"
down_revision: Union[str, Sequence[str], None] = (
    "a1c4e7b20f31",
    "a1c4f7e92b08",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change: this revision only joins two branches."""


def downgrade() -> None:
    """No schema change: downgrading re-opens the two parent branches."""
