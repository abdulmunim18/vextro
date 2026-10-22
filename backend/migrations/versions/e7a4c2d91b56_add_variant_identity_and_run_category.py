"""add a category-independent variant identity and a crawl run's category

Revision ID: e7a4c2d91b56
Revises: d84f2a19c630
Create Date: 2026-10-22

Additive only. The RAM and storage columns and their unique constraint stay
as they are; this adds the general form beside them so categories other
than smartphones can describe their variants.

* ``product_variants.configuration_key``: the variant's identity attributes
  as one string, unique per product, colour and condition.
* ``variant_attributes["identity"]``: the same attributes as data. Existing
  variants get their RAM and storage copied in.
* ``scrape_runs.category``: the catalogue category a run covered.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a4c2d91b56"
down_revision: Union[str, Sequence[str], None] = "d84f2a19c630"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column(
            "configuration_key",
            sa.String(length=255),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )

    # The same identity the application derives on every save: RAM and
    # storage in key order, nothing for a value that is not stated.
    op.execute(
        """
        UPDATE product_variants
        SET configuration_key = concat_ws(
                '|',
                'ram_gb=' || ram_gb,
                'storage_gb=' || storage_gb
            ),
            variant_attributes = CASE
                WHEN ram_gb IS NULL AND storage_gb IS NULL
                    THEN variant_attributes - 'identity'
                ELSE jsonb_set(
                    variant_attributes,
                    '{identity}',
                    jsonb_strip_nulls(
                        jsonb_build_object(
                            'ram_gb', ram_gb,
                            'storage_gb', storage_gb
                        )
                    )
                )
            END
        """
    )

    op.create_unique_constraint(
        "uq_product_variants_identity",
        "product_variants",
        ["canonical_product_id", "configuration_key", "color", "condition"],
    )

    op.add_column(
        "scrape_runs",
        sa.Column("category", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scrape_runs", "category")
    op.drop_constraint(
        "uq_product_variants_identity",
        "product_variants",
        type_="unique",
    )
    op.execute(
        "UPDATE product_variants SET variant_attributes = variant_attributes - 'identity'"
    )
    op.drop_column("product_variants", "configuration_key")
