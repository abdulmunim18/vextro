from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


def unique_value(prefix: str) -> str:
    """Generate a unique test value."""

    return f"{prefix}-{uuid4().hex[:12]}"


def create_catalog_chain(
    database_session: Session,
) -> tuple[
    Category,
    Brand,
    Platform,
    CanonicalProduct,
    ProductVariant,
    Seller,
]:
    """Create the required records for a marketplace listing."""

    category = Category(
        name=unique_value("Mobile Phones"),
        slug=unique_value("mobile-phones"),
    )

    brand = Brand(
        name=unique_value("Test Brand"),
        slug=unique_value("test-brand"),
    )

    platform_code = unique_value("platform").lower()

    platform = Platform(
        name=unique_value("Test Platform"),
        code=platform_code,
        base_url=f"https://{platform_code}.example.com",
    )

    database_session.add_all(
        [
            category,
            brand,
            platform,
        ]
    )
    database_session.flush()

    canonical_product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=unique_value("Test Smartphone"),
        slug=unique_value("test-smartphone"),
        model=unique_value("MODEL"),
        description="Automated catalog test product.",
        specifications={
            "display": "6.5 inch",
            "battery": "5000 mAh",
        },
    )

    database_session.add(canonical_product)
    database_session.flush()

    product_variant = ProductVariant(
        canonical_product_id=canonical_product.id,
        sku=unique_value("SKU"),
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={
            "network": "5G",
        },
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value("seller"),
        name=unique_value("Test Seller"),
        profile_url="https://example.com/seller",
        rating=Decimal("4.50"),
        review_count=100,
        is_verified=True,
    )

    database_session.add_all(
        [
            product_variant,
            seller,
        ]
    )
    database_session.flush()

    return (
        category,
        brand,
        platform,
        canonical_product,
        product_variant,
        seller,
    )


def test_create_complete_marketplace_listing(
    database_session: Session,
) -> None:
    """Verify the complete product-to-listing relationship chain."""

    (
        category,
        brand,
        platform,
        canonical_product,
        product_variant,
        seller,
    ) = create_catalog_chain(database_session)

    listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=product_variant.id,
        seller_id=seller.id,
        external_id=unique_value("listing"),
        title="Test Smartphone 8GB 256GB",
        product_url="https://example.com/product",
        current_price=Decimal("199999.00"),
        original_price=Decimal("209999.00"),
        currency="PKR",
        rating=Decimal("4.40"),
        review_count=250,
        warranty="1 Year",
        is_available=True,
        raw_payload={
            "source": "automated-test",
        },
    )

    database_session.add(listing)
    database_session.commit()

    saved_listing = database_session.scalar(
        select(ProductListing)
        .options(
            selectinload(ProductListing.product_variant),
            selectinload(ProductListing.seller),
        )
        .where(ProductListing.id == listing.id)
    )

    assert saved_listing is not None
    assert saved_listing.platform_id == platform.id
    assert saved_listing.current_price == Decimal("199999.00")
    assert saved_listing.currency == "PKR"
    assert saved_listing.is_available is True

    assert saved_listing.product_variant.id == product_variant.id
    assert saved_listing.product_variant.canonical_product_id == (
        canonical_product.id
    )

    assert saved_listing.seller is not None
    assert saved_listing.seller.id == seller.id
    assert saved_listing.seller.platform_id == platform.id

    assert canonical_product.category_id == category.id
    assert canonical_product.brand_id == brand.id


def test_duplicate_listing_external_id_is_blocked(
    database_session: Session,
) -> None:
    """A marketplace external ID must be unique inside one platform."""

    (
        _category,
        _brand,
        platform,
        _canonical_product,
        product_variant,
        seller,
    ) = create_catalog_chain(database_session)

    external_id = unique_value("duplicate-listing")

    first_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=product_variant.id,
        seller_id=seller.id,
        external_id=external_id,
        title="First Test Listing",
        product_url="https://example.com/product-one",
        current_price=Decimal("100000.00"),
    )

    database_session.add(first_listing)
    database_session.commit()

    duplicate_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=product_variant.id,
        seller_id=seller.id,
        external_id=external_id,
        title="Duplicate Test Listing",
        product_url="https://example.com/product-two",
        current_price=Decimal("99000.00"),
    )

    database_session.add(duplicate_listing)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_negative_listing_price_is_blocked(
    database_session: Session,
) -> None:
    """Database constraints must reject negative listing prices."""

    (
        _category,
        _brand,
        platform,
        _canonical_product,
        product_variant,
        seller,
    ) = create_catalog_chain(database_session)

    invalid_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=product_variant.id,
        seller_id=seller.id,
        external_id=unique_value("negative-price"),
        title="Invalid Negative Price Listing",
        product_url="https://example.com/invalid-product",
        current_price=Decimal("-1.00"),
    )

    database_session.add(invalid_listing)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()