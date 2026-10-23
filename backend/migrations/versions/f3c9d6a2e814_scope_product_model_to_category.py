"""scope product names to their category and variants to their identity

Revision ID: f3c9d6a2e814
Revises: e7a4c2d91b56
Create Date: 2026-10-22

* A brand may sell a phone and a tablet under the same model name. The
  model stays unique per brand, now within one category.
* The RAM-and-storage variant rule is replaced by the identity rule added in
  e7a4c2d91b56, which includes RAM and storage. Under the old rule a Wi-Fi
  and a cellular tablet of one memory size and colour could not both exist.

Every existing product is a phone and every variant's identity is its RAM
and storage, so no existing row can conflict either way.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f3c9d6a2e814"
down_revision: Union[str, Sequence[str], None] = "e7a4c2d91b56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_product_variants_configuration",
        "product_variants",
        type_="unique",
    )
    op.drop_constraint(
        "uq_canonical_products_brand_model",
        "canonical_products",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_canonical_products_brand_category_model",
        "canonical_products",
        ["brand_id", "category_id", "model"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_canonical_products_brand_category_model",
        "canonical_products",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_canonical_products_brand_model",
        "canonical_products",
        ["brand_id", "model"],
    )
    op.create_unique_constraint(
        "uq_product_variants_configuration",
        "product_variants",
        ["canonical_product_id", "ram_gb", "storage_gb", "color", "condition"],
    )
