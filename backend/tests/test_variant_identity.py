"""A variant's identity and configuration key are kept in step on every save."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.product_variant import ProductVariant
from app.services.variant_identity import configuration_key, variant_identity


@pytest.fixture
def product(database_session: Session):
    category = database_session.scalar(select(Category).where(Category.slug == "mobile-phones"))
    brand = database_session.scalar(select(Brand).where(Brand.name == "Samsung"))
    token = uuid4().hex[:8]
    item = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=f"Samsung Identity {token}",
        slug=f"samsung-identity-{token}",
        model=f"Identity {token}",
        specifications={},
    )
    database_session.add(item)
    database_session.commit()

    yield item

    database_session.rollback()
    for variant in database_session.scalars(
        select(ProductVariant).where(ProductVariant.canonical_product_id == item.id)
    ):
        database_session.delete(variant)
    database_session.delete(item)
    database_session.commit()


def add(session, product, **fields):
    variant = ProductVariant(canonical_product_id=product.id, **fields)
    session.add(variant)
    session.commit()
    session.refresh(variant)
    return variant


# --------------------------------------------------------------------------
# Pure functions
# --------------------------------------------------------------------------


def test_the_memory_columns_outrank_a_stale_stored_identity():
    assert variant_identity({"identity": {"ram_gb": 4, "storage_gb": 64}}, ram_gb=8, storage_gb=256) == {
        "ram_gb": 8,
        "storage_gb": 256,
    }


def test_other_identity_attributes_are_kept_beside_the_memory_columns():
    assert variant_identity({"identity": {"connectivity": "cellular"}}, ram_gb=8, storage_gb=None) == {
        "connectivity": "cellular",
        "ram_gb": 8,
    }


def test_a_key_lists_attributes_in_a_fixed_order():
    assert configuration_key({"storage_gb": 256, "ram_gb": 8}) == "ram_gb=8|storage_gb=256"


# --------------------------------------------------------------------------
# On save
# --------------------------------------------------------------------------


def test_a_phone_variant_gets_its_identity_from_the_memory_columns(database_session, product):
    variant = add(database_session, product, ram_gb=8, storage_gb=256, color="Black", variant_attributes={"source_platform": "priceoye"})

    assert variant.configuration_key == "ram_gb=8|storage_gb=256"
    assert variant.variant_attributes == {
        "source_platform": "priceoye",
        "identity": {"ram_gb": 8, "storage_gb": 256},
    }


def test_a_variant_without_identity_attributes_has_the_empty_key(database_session, product):
    variant = add(database_session, product, color="Black", variant_attributes={})

    assert variant.configuration_key == ""
    assert "identity" not in variant.variant_attributes


def test_a_tablet_style_identity_is_stored_and_keyed(database_session, product):
    variant = add(
        database_session,
        product,
        ram_gb=8,
        storage_gb=128,
        color="Grey",
        variant_attributes={"identity": {"connectivity": "cellular"}},
    )

    assert variant.configuration_key == "connectivity=cellular|ram_gb=8|storage_gb=128"


def test_editing_a_variant_recomputes_its_key(database_session, product):
    variant = add(database_session, product, ram_gb=8, storage_gb=128, color="Blue", variant_attributes={})

    variant.storage_gb = 256
    database_session.commit()
    database_session.refresh(variant)

    assert variant.configuration_key == "ram_gb=8|storage_gb=256"
    assert variant.variant_attributes["identity"] == {"ram_gb": 8, "storage_gb": 256}


def test_two_variants_with_one_identity_and_colour_are_refused(database_session, product):
    add(database_session, product, color="Green", variant_attributes={"identity": {"case_size_mm": 44}})

    with pytest.raises(IntegrityError):
        add(database_session, product, color="Green", variant_attributes={"identity": {"case_size_mm": 44}})
    database_session.rollback()

    other_size = add(database_session, product, color="Green", variant_attributes={"identity": {"case_size_mm": 40}})
    assert other_size.configuration_key == "case_size_mm=40"
