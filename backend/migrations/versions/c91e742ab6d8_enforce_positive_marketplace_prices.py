"""enforce positive marketplace prices

Revision ID: c91e742ab6d8
Revises: f6a1c82d09b4
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c91e742ab6d8"
down_revision: Union[str, Sequence[str], None] = "f6a1c82d09b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reject zero and negative marketplace prices at the database layer."""

    op.drop_constraint(
        "ck_product_listings_current_price_non_negative",
        "product_listings",
        type_="check",
    )
    op.drop_constraint(
        "ck_product_listings_original_price_non_negative",
        "product_listings",
        type_="check",
    )
    op.drop_constraint(
        "ck_price_history_price_non_negative",
        "price_history",
        type_="check",
    )
    op.drop_constraint(
        "ck_price_history_original_price_non_negative",
        "price_history",
        type_="check",
    )

    op.create_check_constraint(
        "ck_product_listings_current_price_positive",
        "product_listings",
        "current_price > 0",
    )
    op.create_check_constraint(
        "ck_product_listings_original_price_positive",
        "product_listings",
        "original_price IS NULL OR original_price > 0",
    )
    op.create_check_constraint(
        "ck_price_history_price_positive",
        "price_history",
        "price > 0",
    )
    op.create_check_constraint(
        "ck_price_history_original_price_positive",
        "price_history",
        "original_price IS NULL OR original_price > 0",
    )


def downgrade() -> None:
    """Restore the former non-negative marketplace price constraints."""

    op.drop_constraint(
        "ck_price_history_original_price_positive",
        "price_history",
        type_="check",
    )
    op.drop_constraint(
        "ck_price_history_price_positive",
        "price_history",
        type_="check",
    )
    op.drop_constraint(
        "ck_product_listings_original_price_positive",
        "product_listings",
        type_="check",
    )
    op.drop_constraint(
        "ck_product_listings_current_price_positive",
        "product_listings",
        type_="check",
    )

    op.create_check_constraint(
        "ck_product_listings_current_price_non_negative",
        "product_listings",
        "current_price >= 0",
    )
    op.create_check_constraint(
        "ck_product_listings_original_price_non_negative",
        "product_listings",
        "original_price IS NULL OR original_price >= 0",
    )
    op.create_check_constraint(
        "ck_price_history_price_non_negative",
        "price_history",
        "price >= 0",
    )
    op.create_check_constraint(
        "ck_price_history_original_price_non_negative",
        "price_history",
        "original_price IS NULL OR original_price >= 0",
    )
