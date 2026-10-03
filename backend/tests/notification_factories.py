"""Shared fixtures and builders for module 6.14 notification tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, settings as base_settings
from app.models.brand import Brand
from app.models.business_product import BusinessProduct
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.competitor_watchlist import CompetitorWatchlist
from app.models.notification_preference import NotificationPreference
from app.models.organization import Organization
from app.models.platform import Platform
from app.models.price_alert import PriceAlert
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.repositories.push_subscription_repository import hash_endpoint


def unique_value(prefix: str) -> str:
    """Return a collision-free value for test records."""

    return f"{prefix}-{uuid4().hex[:12]}"


def notification_settings(**overrides) -> Settings:
    """Return settings with email and VAPID configured for tests.

    The values are obvious non-secrets used only to exercise the code
    paths; the SMTP and push transports are always monkeypatched.
    """

    configured = base_settings.model_copy(
        update={
            "smtp_host": "smtp.test.invalid",
            "smtp_port": 587,
            "smtp_username": "vextro-test",
            "smtp_password": "not-a-real-password",
            "smtp_from_email": "alerts@vextro.test",
            "smtp_from_name": "VEXTRO",
            "smtp_use_tls": True,
            "frontend_base_url": "http://localhost:5173",
            "vapid_public_key": "test-public-key",
            "vapid_private_key": "test-private-key",
            "vapid_subject": "mailto:alerts@vextro.test",
            "notification_delivery_max_attempts": 3,
            "digest_timezone": "Asia/Karachi",
            "digest_attach_sme_report": False,
            **overrides,
        }
    )

    return configured


def settings_without_email(**overrides) -> Settings:
    """Return settings where SMTP is deliberately not configured."""

    return notification_settings(
        smtp_host=None,
        smtp_from_email=None,
        smtp_username=None,
        **overrides,
    )


@dataclass
class ConsumerAlertFixture:
    """A consumer with one active price alert on a real listing."""

    user: User
    product: CanonicalProduct
    listing: ProductListing
    alert: PriceAlert
    preference: NotificationPreference


def create_user(
    database_session: Session,
    *,
    prefix: str = "notify",
    email: str | None = None,
) -> User:
    """Create one active, verified test user."""

    user = User(
        full_name=f"Test {prefix.title()}",
        email=(
            email
            if email is not None
            else f"{unique_value(prefix)}@example.com"
        ),
        password_hash="test-password-hash",
        is_active=True,
        is_verified=True,
    )

    database_session.add(user)
    database_session.flush()

    return user


def create_preference(
    database_session: Session,
    *,
    user_id: int,
    price_alert_email: bool = True,
    price_alert_push: bool = True,
    competitor_alert_email: bool = True,
    competitor_alert_push: bool = True,
    digest_frequency: str = "off",
) -> NotificationPreference:
    """Create an explicit preference row for one user."""

    preference = NotificationPreference(
        user_id=user_id,
        price_alert_email=price_alert_email,
        price_alert_push=price_alert_push,
        competitor_alert_email=competitor_alert_email,
        competitor_alert_push=competitor_alert_push,
        digest_frequency=digest_frequency,
    )

    database_session.add(preference)
    database_session.flush()

    return preference


def create_push_subscription(
    database_session: Session,
    *,
    user_id: int,
    endpoint: str | None = None,
) -> PushSubscription:
    """Create one active push subscription for a user."""

    resolved_endpoint = endpoint or (
        f"https://push.example.com/{unique_value('endpoint')}"
    )

    subscription = PushSubscription(
        user_id=user_id,
        endpoint=resolved_endpoint,
        endpoint_hash=hash_endpoint(resolved_endpoint),
        p256dh_key=unique_value("p256dh-key-value"),
        auth_key=unique_value("auth-key"),
        user_agent="pytest",
        is_active=True,
    )

    database_session.add(subscription)
    database_session.flush()

    return subscription


def create_listing(
    database_session: Session,
    *,
    current_price: Decimal = Decimal("120000.00"),
) -> tuple[CanonicalProduct, ProductListing, Platform]:
    """Create a product, variant and marketplace listing."""

    category = Category(
        name=unique_value("Notify Category"),
        slug=unique_value("notify-category").lower(),
        is_active=True,
    )

    brand = Brand(
        name=unique_value("Notify Brand"),
        slug=unique_value("notify-brand").lower(),
        is_active=True,
    )

    platform_code = unique_value("notify-platform").lower()

    platform = Platform(
        name=f"Daraz Test Marketplace {platform_code[-8:]}",
        code=platform_code,
        base_url=f"https://{platform_code}.example.com",
        is_active=True,
    )

    database_session.add_all([category, brand, platform])
    database_session.flush()

    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name="Samsung Galaxy A55",
        slug=unique_value("samsung-galaxy-a55").lower(),
        model=unique_value("SM-A556"),
        description="Notification delivery test product.",
        specifications={"ram": "8 GB"},
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

    database_session.add(variant)
    database_session.flush()

    listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        external_id=unique_value("notify-listing"),
        title="Samsung Galaxy A55 Listing",
        product_url=(
            f"https://example.com/{unique_value('listing')}"
        ),
        current_price=current_price,
        currency="PKR",
        is_available=True,
    )

    database_session.add(listing)
    database_session.flush()

    return product, listing, platform


def create_consumer_alert_fixture(
    database_session: Session,
    *,
    target_price: Decimal = Decimal("100000.00"),
    price_alert_email: bool = True,
    price_alert_push: bool = True,
    with_push_subscription: bool = True,
    user_email: str | None = None,
) -> ConsumerAlertFixture:
    """Create the standard consumer price-alert scenario."""

    user = create_user(
        database_session,
        prefix="consumer",
        email=user_email,
    )

    preference = create_preference(
        database_session,
        user_id=user.id,
        price_alert_email=price_alert_email,
        price_alert_push=price_alert_push,
    )

    if with_push_subscription:
        create_push_subscription(
            database_session,
            user_id=user.id,
        )

    product, listing, _platform = create_listing(
        database_session,
    )

    alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=product.id,
        target_price=target_price,
        currency="PKR",
        is_active=True,
    )

    database_session.add(alert)
    database_session.flush()
    database_session.commit()

    return ConsumerAlertFixture(
        user=user,
        product=product,
        listing=listing,
        alert=alert,
        preference=preference,
    )


@dataclass
class SmeRiskFixture:
    """An SME owner with one watched competitor listing."""

    owner: User
    organization: Organization
    business_product: BusinessProduct
    listing: ProductListing
    watchlist: CompetitorWatchlist
    preference: NotificationPreference


def create_sme_risk_fixture(
    database_session: Session,
    *,
    own_price: Decimal = Decimal("120000.00"),
    risk_threshold_percentage: Decimal = Decimal("5.00"),
    last_risk_level: str | None = "low",
    competitor_alert_email: bool = True,
    competitor_alert_push: bool = True,
    with_push_subscription: bool = True,
) -> SmeRiskFixture:
    """Create the standard SME competitor-risk scenario."""

    owner = create_user(
        database_session,
        prefix="sme-owner",
    )

    preference = create_preference(
        database_session,
        user_id=owner.id,
        competitor_alert_email=competitor_alert_email,
        competitor_alert_push=competitor_alert_push,
    )

    if with_push_subscription:
        create_push_subscription(
            database_session,
            user_id=owner.id,
        )

    organization = Organization(
        owner_user_id=owner.id,
        name=unique_value("Notify Traders"),
        slug=unique_value("notify-traders").lower(),
        industry="Retail",
        is_active=True,
    )

    database_session.add(organization)
    database_session.flush()

    product, listing, _platform = create_listing(
        database_session,
    )

    business_product = BusinessProduct(
        organization_id=organization.id,
        canonical_product_id=product.id,
        name="Samsung Galaxy A55 (our stock)",
        sku=unique_value("SME-SKU"),
        selling_price=own_price,
        currency="PKR",
        is_active=True,
    )

    database_session.add(business_product)
    database_session.flush()

    watchlist = CompetitorWatchlist(
        organization_id=organization.id,
        business_product_id=business_product.id,
        listing_id=listing.id,
        risk_threshold_percentage=risk_threshold_percentage,
        last_risk_level=last_risk_level,
        is_active=True,
    )

    database_session.add(watchlist)
    database_session.flush()
    database_session.commit()

    return SmeRiskFixture(
        owner=owner,
        organization=organization,
        business_product=business_product,
        listing=listing,
        watchlist=watchlist,
        preference=preference,
    )


class RecordingEmailTransport:
    """Capture email sends instead of contacting a real SMTP server."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.sent: list[tuple[str, object]] = []
        self.error = error

    def __call__(
        self,
        *,
        recipient: str,
        content: object,
        settings: object | None = None,
    ) -> None:
        if self.error is not None:
            raise self.error

        self.sent.append((recipient, content))

    @property
    def recipients(self) -> list[str]:
        """Return every address a message was delivered to."""

        return [recipient for recipient, _content in self.sent]


class RecordingPushTransport:
    """Capture Web Push sends instead of contacting a push endpoint."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.sent: list[tuple[str, object]] = []
        self.error = error

    def __call__(
        self,
        *,
        subscription,
        message,
        settings: object | None = None,
    ) -> None:
        if self.error is not None:
            raise self.error

        self.sent.append((subscription.endpoint, message))

    @property
    def endpoints(self) -> list[str]:
        """Return every endpoint a message was delivered to."""

        return [endpoint for endpoint, _message in self.sent]


__all__ = [
    "ConsumerAlertFixture",
    "RecordingEmailTransport",
    "RecordingPushTransport",
    "SmeRiskFixture",
    "create_consumer_alert_fixture",
    "create_listing",
    "create_preference",
    "create_push_subscription",
    "create_sme_risk_fixture",
    "create_user",
    "notification_settings",
    "replace",
    "settings_without_email",
    "unique_value",
]
