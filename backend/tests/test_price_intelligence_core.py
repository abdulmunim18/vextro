from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from app.models.price_alert import PriceAlert
from app.models.user import User
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

def create_test_user(
    database_session: Session,
) -> User:
    """Create a user for price alert database tests."""

    user = User(
        full_name="Price Alert Test User",
        email=f"{unique_value('price-alert-user')}@example.com",
        password_hash="automated-test-password-hash",
        is_active=True,
        is_verified=True,
    )

    database_session.add(user)
    database_session.flush()

    return user


def get_product_id_for_listing(
    database_session: Session,
    listing: ProductListing,
) -> int:
    """Return the canonical product ID linked to a listing."""

    variant = database_session.get(
        ProductVariant,
        listing.product_variant_id,
    )

    assert variant is not None

    return variant.canonical_product_id
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
def test_create_product_and_listing_price_alerts(
    database_session: Session,
) -> None:
    """A user can create product-level and listing-level alerts."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    product_id = get_product_id_for_listing(
        database_session,
        listing,
    )

    product_alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product_id,
        target_price=Decimal("110000.00"),
        currency="PKR",
    )

    listing_alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("105000.00"),
        currency="PKR",
    )

    database_session.add_all(
        [
            product_alert,
            listing_alert,
        ]
    )
    database_session.commit()

    saved_alerts = list(
        database_session.scalars(
            select(PriceAlert).where(
                PriceAlert.user_id == user.id
            )
        ).all()
    )

    assert len(saved_alerts) == 2

    saved_product_alert = next(
        alert
        for alert in saved_alerts
        if alert.canonical_product_id is not None
    )

    saved_listing_alert = next(
        alert
        for alert in saved_alerts
        if alert.listing_id is not None
    )

    assert saved_product_alert.canonical_product_id == product_id
    assert saved_product_alert.listing_id is None
    assert saved_product_alert.target_price == Decimal("110000.00")

    assert saved_listing_alert.listing_id == listing.id
    assert saved_listing_alert.canonical_product_id is None
    assert saved_listing_alert.target_price == Decimal("105000.00")

    assert saved_product_alert.is_active is True
    assert saved_product_alert.is_triggered is False
    assert saved_product_alert.notification_count == 0


def test_price_alert_requires_exactly_one_target(
    database_session: Session,
) -> None:
    """An alert must target one product or one listing, never both or neither."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    product_id = get_product_id_for_listing(
        database_session,
        listing,
    )

    database_session.commit()

    alert_without_target = PriceAlert(
        user_id=user.id,
        target_price=Decimal("100000.00"),
        currency="PKR",
    )

    database_session.add(alert_without_target)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()

    alert_with_two_targets = PriceAlert(
        user_id=user.id,
        canonical_product_id=product_id,
        listing_id=listing.id,
        target_price=Decimal("100000.00"),
        currency="PKR",
    )

    database_session.add(alert_with_two_targets)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_price_alert_target_price_must_be_positive(
    database_session: Session,
) -> None:
    """Target price must be greater than zero."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    database_session.commit()

    invalid_alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("0.00"),
        currency="PKR",
    )

    database_session.add(invalid_alert)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_price_alert_currency_and_notification_count_are_validated(
    database_session: Session,
) -> None:
    """Currency length and notification count must remain valid."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    database_session.commit()

    invalid_currency_alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("100000.00"),
        currency="PK",
    )

    database_session.add(invalid_currency_alert)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()

    invalid_notification_alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("100000.00"),
        currency="PKR",
        notification_count=-1,
    )

    database_session.add(invalid_notification_alert)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_duplicate_active_product_alert_is_blocked(
    database_session: Session,
) -> None:
    """A user cannot have two active alerts for the same product."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    product_id = get_product_id_for_listing(
        database_session,
        listing,
    )

    database_session.commit()

    first_alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product_id,
        target_price=Decimal("110000.00"),
        currency="PKR",
        is_active=True,
    )

    database_session.add(first_alert)
    database_session.commit()

    duplicate_alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product_id,
        target_price=Decimal("100000.00"),
        currency="PKR",
        is_active=True,
    )

    database_session.add(duplicate_alert)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_duplicate_active_listing_alert_is_blocked(
    database_session: Session,
) -> None:
    """A user cannot have two active alerts for the same listing."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    database_session.commit()

    first_alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("110000.00"),
        currency="PKR",
        is_active=True,
    )

    database_session.add(first_alert)
    database_session.commit()

    duplicate_alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("100000.00"),
        currency="PKR",
        is_active=True,
    )

    database_session.add(duplicate_alert)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()


def test_inactive_alert_allows_new_active_alert(
    database_session: Session,
) -> None:
    """An inactive alert should not block a new active alert."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    product_id = get_product_id_for_listing(
        database_session,
        listing,
    )

    inactive_alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product_id,
        target_price=Decimal("115000.00"),
        currency="PKR",
        is_active=False,
    )

    active_alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product_id,
        target_price=Decimal("105000.00"),
        currency="PKR",
        is_active=True,
    )

    database_session.add_all(
        [
            inactive_alert,
            active_alert,
        ]
    )
    database_session.commit()

    saved_alerts = list(
        database_session.scalars(
            select(PriceAlert).where(
                PriceAlert.user_id == user.id,
                PriceAlert.canonical_product_id == product_id,
            )
        ).all()
    )

    assert len(saved_alerts) == 2
    assert sum(alert.is_active for alert in saved_alerts) == 1


def test_deleting_user_cascades_price_alerts(
    database_session: Session,
) -> None:
    """Deleting a user should remove all alerts owned by that user."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("100000.00"),
        currency="PKR",
    )

    database_session.add(alert)
    database_session.commit()

    alert_id = alert.id

    database_session.delete(user)
    database_session.commit()

    deleted_alert = database_session.scalar(
        select(PriceAlert).where(
            PriceAlert.id == alert_id
        )
    )

    assert deleted_alert is None


def test_deleting_listing_cascades_listing_alert(
    database_session: Session,
) -> None:
    """Deleting a listing should remove alerts targeting that listing."""

    user = create_test_user(database_session)
    listing = create_listing(database_session)

    alert = PriceAlert(
        user_id=user.id,
        listing_id=listing.id,
        target_price=Decimal("100000.00"),
        currency="PKR",
    )

    database_session.add(alert)
    database_session.commit()

    alert_id = alert.id

    database_session.delete(listing)
    database_session.commit()

    deleted_alert = database_session.scalar(
        select(PriceAlert).where(
            PriceAlert.id == alert_id
        )
    )

    assert deleted_alert is None