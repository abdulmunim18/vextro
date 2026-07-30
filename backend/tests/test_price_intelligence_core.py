from datetime import datetime, timezone
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
from app.models.price_history import PriceHistory
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


def unique_value(prefix: str) -> str:
    """Generate a unique value for database tests."""

    return f"{prefix}-{uuid4().hex[:12]}"


def create_listing(
    database_session: Session,
) -> ProductListing:
    """Create the complete catalog chain required by a listing."""

    category = Category(
        name=unique_value("Price Category"),
        slug=unique_value("price-category").lower(),
    )

    brand = Brand(
        name=unique_value("Price Brand"),
        slug=unique_value("price-brand").lower(),
    )

    platform_code = unique_value("price-platform").lower()

    platform = Platform(
        name=unique_value("Price Platform"),
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

    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=unique_value("Price Test Product"),
        slug=unique_value("price-test-product").lower(),
        model=unique_value("PRICE-MODEL"),
        description="Product used for price history tests.",
    )

    database_session.add(product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=unique_value("PRICE-SKU"),
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value("price-seller"),
        name=unique_value("Price Seller"),
        rating=Decimal("4.50"),
        review_count=100,
        is_verified=True,
    )

    database_session.add_all(
        [
            variant,
            seller,
        ]
    )
    database_session.flush()

    listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("price-listing"),
        title="Price History Test Listing",
        product_url="https://example.com/price-history-product",
        current_price=Decimal("125000.00"),
        original_price=Decimal("130000.00"),
        currency="PKR",
        is_available=True,
    )

    database_session.add(listing)
    database_session.flush()

    return listing


def test_create_and_order_price_history(
    database_session: Session,
) -> None:
    """Price snapshots should be ordered by capture time."""

    listing = create_listing(database_session)

    newer_snapshot = PriceHistory(
        listing_id=listing.id,
        price=Decimal("120000.00"),
        original_price=Decimal("130000.00"),
        currency="PKR",
        source="automated-test",
        captured_at=datetime(
            2026,
            1,
            2,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    older_snapshot = PriceHistory(
        listing_id=listing.id,
        price=Decimal("125000.00"),
        original_price=Decimal("130000.00"),
        currency="PKR",
        source="automated-test",
        captured_at=datetime(
            2026,
            1,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    database_session.add_all(
        [
            newer_snapshot,
            older_snapshot,
        ]
    )
    database_session.commit()

    saved_listing = database_session.scalar(
        select(ProductListing)
        .options(selectinload(ProductListing.price_history))
        .where(ProductListing.id == listing.id)
    )

    assert saved_listing is not None
    assert len(saved_listing.price_history) == 2

    assert saved_listing.price_history[0].price == Decimal("125000.00")
    assert saved_listing.price_history[1].price == Decimal("120000.00")


def test_negative_price_history_price_is_blocked(
    database_session: Session,
) -> None:
    """A historical price cannot be negative."""

    listing = create_listing(database_session)

    invalid_snapshot = PriceHistory(
        listing_id=listing.id,
        price=Decimal("-1.00"),
        currency="PKR",
    )

    database_session.add(invalid_snapshot)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_invalid_price_history_currency_is_blocked(
    database_session: Session,
) -> None:
    """Currency must contain exactly three characters."""

    listing = create_listing(database_session)

    invalid_snapshot = PriceHistory(
        listing_id=listing.id,
        price=Decimal("100000.00"),
        currency="PK",
    )

    database_session.add(invalid_snapshot)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_deleting_listing_cascades_price_history(
    database_session: Session,
) -> None:
    """Deleting a listing should delete its historical snapshots."""

    listing = create_listing(database_session)

    snapshot = PriceHistory(
        listing_id=listing.id,
        price=Decimal("100000.00"),
        currency="PKR",
    )

    database_session.add(snapshot)
    database_session.commit()

    snapshot_id = snapshot.id

    database_session.delete(listing)
    database_session.commit()

    deleted_snapshot = database_session.scalar(
        select(PriceHistory).where(
            PriceHistory.id == snapshot_id
        )
    )

    assert deleted_snapshot is None