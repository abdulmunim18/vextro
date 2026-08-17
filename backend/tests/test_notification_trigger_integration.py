from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.notification import Notification
from app.models.platform import Platform
from app.models.price_alert import PriceAlert
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller
from app.models.user import User
from app.services.price_alert_service import (
    evaluate_price_alerts_for_capture,
)


def unique_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def test_price_alert_trigger_creates_one_in_app_notification(
    database_session: Session,
) -> None:
    """A qualifying capture triggers exactly one notification."""

    user = User(
        full_name="Notification Integration User",
        email=f"{unique_value('notify')}@example.com",
        password_hash="test-password-hash",
        is_active=True,
        is_verified=True,
    )

    category = Category(
        name=unique_value("Notification Category"),
        slug=unique_value("notification-category").lower(),
        is_active=True,
    )

    brand = Brand(
        name=unique_value("Notification Brand"),
        slug=unique_value("notification-brand").lower(),
        is_active=True,
    )

    platform_code = unique_value(
        "notification-platform"
    ).lower()

    platform = Platform(
        name=unique_value("Notification Platform"),
        code=platform_code,
        base_url=f"https://{platform_code}.example.com",
        is_active=True,
    )

    database_session.add_all(
        [
            user,
            category,
            brand,
            platform,
        ]
    )

    database_session.flush()

    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name="Notification Test Smartphone",
        slug=unique_value(
            "notification-test-smartphone"
        ).lower(),
        model=unique_value("NOTIFY-MODEL"),
        description="Notification integration test product.",
        specifications={
            "ram": "8 GB",
            "storage": "256 GB",
        },
        is_active=True,
    )

    database_session.add(product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=unique_value("NOTIFY-SKU"),
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        is_active=True,
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value(
            "notify-seller"
        ),
        name=unique_value("Notification Seller"),
        rating=Decimal("4.80"),
        review_count=200,
        is_verified=True,
        is_active=True,
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
        external_id=unique_value(
            "notify-listing"
        ),
        title="Notification Test Listing",
        product_url=(
            "https://example.com/"
            f"{unique_value('notification-product')}"
        ),
        current_price=Decimal("120000.00"),
        original_price=Decimal("125000.00"),
        currency="PKR",
        is_available=True,
    )

    database_session.add(listing)
    database_session.flush()

    alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product.id,
        target_price=Decimal("115000.00"),
        currency="PKR",
        is_active=True,
    )

    database_session.add(alert)
    database_session.flush()

    triggered_count = evaluate_price_alerts_for_capture(
        database_session,
        canonical_product_id=product.id,
        listing_id=listing.id,
        current_price=Decimal("114000.00"),
        currency="PKR",
    )

    assert triggered_count == 1

    database_session.refresh(alert)

    assert alert.is_triggered is True
    assert alert.triggered_at is not None
    assert alert.last_notified_at is not None
    assert alert.notification_count == 1

    notifications = list(
        database_session.scalars(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.price_alert_id == alert.id,
            )
        ).all()
    )

    assert len(notifications) == 1

    notification = notifications[0]

    assert notification.notification_type == "price_drop"
    assert notification.title == "Price target reached"
    assert notification.is_read is False
    assert notification.read_at is None
    assert notification.canonical_product_id == product.id
    assert notification.action_path == f"/products/{product.id}"
    assert product.name in notification.message
    assert "PKR 114,000.00" in notification.message
    assert "PKR 115,000.00" in notification.message

    second_trigger_count = evaluate_price_alerts_for_capture(
        database_session,
        canonical_product_id=product.id,
        listing_id=listing.id,
        current_price=Decimal("110000.00"),
        currency="PKR",
    )

    assert second_trigger_count == 0

    database_session.refresh(alert)

    assert alert.notification_count == 1

    notifications_after_second_capture = list(
        database_session.scalars(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.price_alert_id == alert.id,
            )
        ).all()
    )

    assert len(notifications_after_second_capture) == 1
