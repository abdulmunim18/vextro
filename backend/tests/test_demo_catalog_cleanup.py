"""Tests for the demo-data cleanup.

The hazard here is not leaving demo rows behind; it is deleting genuine
scraped data along with them. Because only demo products existed when
crawling began, real Daraz and PriceOye listings were matched onto demo
variants, so deleting a demo product would cascade into real listings,
real price history, real reviews and user alerts.
"""

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.price_alert import PriceAlert
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.raw_review import RawReview
from app.models.seller import Seller
from app.models.user import User
from app.services.review_normalization import build_review_fingerprint
from scripts.remove_demo_catalog import (
    DEMO_PRODUCT_SLUGS,
    is_demo_listing,
    is_test_listing,
    remove_demo_catalog,
)


CAPTURE_TIME = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def demo_catalog(
    database_session: Session,
) -> Generator[dict[str, int], None, None]:
    """Build a demo product that also carries one genuine scraped listing.

    This is the shape the real database is in: ``tecno-camon-30-demo`` holds
    thirteen real Daraz listings alongside its two seeded ones.
    """

    token = uuid4().hex[:8]

    category_id = database_session.scalar(
        select(Category.id).where(Category.slug == "mobile-phones")
    )
    brand_id = database_session.scalar(
        select(Brand.id).where(Brand.slug == "tecno")
    )
    daraz_id = database_session.scalar(
        select(Platform.id).where(Platform.code == "daraz")
    )

    assert category_id is not None
    assert daraz_id is not None

    # A demo product that later attracted a real listing, and one that
    # never did.
    mixed = CanonicalProduct(
        category_id=category_id,
        brand_id=brand_id,
        name="Tecno Camon 30",
        slug="tecno-camon-30-demo",
        model=f"CL6-{token}",
        description="Tecno Camon 30 demo product with a smooth display.",
        specifications={},
        is_active=True,
    )
    empty = CanonicalProduct(
        category_id=category_id,
        brand_id=brand_id,
        name="Infinix Note 40 Pro",
        slug="infinix-note-40-pro-demo",
        model=f"X6851-{token}",
        description="Infinix Note 40 Pro demo product with an AMOLED display.",
        specifications={},
        is_active=True,
    )
    database_session.add_all([mixed, empty])
    database_session.flush()

    mixed_variant = ProductVariant(
        canonical_product_id=mixed.id,
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    empty_variant = ProductVariant(
        canonical_product_id=empty.id,
        ram_gb=12,
        storage_gb=256,
        color="Blue",
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    seller = Seller(
        platform_id=daraz_id,
        external_seller_id="vextro-daraz-demo-seller",
        name="VEXTRO Demo Daraz Seller",
        review_count=0,
        is_verified=True,
        is_active=True,
    )
    database_session.add_all([mixed_variant, empty_variant, seller])
    database_session.flush()

    demo_listing = ProductListing(
        platform_id=daraz_id,
        product_variant_id=mixed_variant.id,
        seller_id=seller.id,
        external_id=f"daraz-demo-tecno-camon-30-{token}",
        title="Tecno Camon 30 8GB 256GB Official Warranty",
        product_url="https://www.daraz.pk/products/demo-tecno.html",
        current_price=Decimal("59999.00"),
        currency="PKR",
        review_count=0,
        is_available=True,
        raw_payload={"source": "vextro_demo_seed", "demo": True},
        first_seen_at=CAPTURE_TIME,
        last_seen_at=CAPTURE_TIME,
    )
    real_listing = ProductListing(
        platform_id=daraz_id,
        product_variant_id=mixed_variant.id,
        external_id=f"19681288{token[:2]}",
        title="Tecno Camon 30 5G 8GB/256GB",
        product_url="https://www.daraz.pk/products/real-tecno.html",
        current_price=Decimal("61499.00"),
        currency="PKR",
        review_count=0,
        is_available=True,
        raw_payload={"source": "daraz"},
        first_seen_at=CAPTURE_TIME,
        last_seen_at=CAPTURE_TIME,
    )
    empty_demo_listing = ProductListing(
        platform_id=daraz_id,
        product_variant_id=empty_variant.id,
        external_id=f"daraz-demo-infinix-note-40-pro-{token}",
        title="Infinix Note 40 Pro 12GB 256GB",
        product_url="https://www.daraz.pk/products/demo-infinix.html",
        current_price=Decimal("74999.00"),
        currency="PKR",
        review_count=0,
        is_available=True,
        raw_payload={"demo": True},
        first_seen_at=CAPTURE_TIME,
        last_seen_at=CAPTURE_TIME,
    )
    test_listing = ProductListing(
        platform_id=daraz_id,
        product_variant_id=mixed_variant.id,
        external_id=f"NOTIFICATION-E2E-{token}",
        title="Tecno Camon 30 end-to-end test listing",
        product_url="https://www.daraz.pk/products/e2e-tecno.html",
        current_price=Decimal("58000.00"),
        currency="PKR",
        review_count=0,
        is_available=True,
        raw_payload={},
        first_seen_at=CAPTURE_TIME,
        last_seen_at=CAPTURE_TIME,
    )
    database_session.add_all(
        [demo_listing, real_listing, empty_demo_listing, test_listing]
    )
    database_session.flush()

    # Seeded history, genuine history, a genuine review and demo imagery.
    database_session.add_all(
        [
            PriceHistory(
                listing_id=demo_listing.id,
                price=Decimal("64999.00"),
                currency="PKR",
                is_available=True,
                source="demo_seed",
                captured_at=CAPTURE_TIME,
            ),
            PriceHistory(
                listing_id=real_listing.id,
                price=Decimal("63999.00"),
                currency="PKR",
                is_available=True,
                source="scraper",
                captured_at=CAPTURE_TIME,
            ),
            # A demo-seeded point that landed on a genuine listing.
            PriceHistory(
                listing_id=real_listing.id,
                price=Decimal("69999.00"),
                currency="PKR",
                is_available=True,
                source="demo_seed",
                captured_at=CAPTURE_TIME,
            ),
            ProductImage(
                canonical_product_id=mixed.id,
                image_url="https://placehold.co/900x900/F5F7FB/3157D5",
                is_primary=True,
                sort_order=0,
            ),
            ProductImage(
                canonical_product_id=mixed.id,
                image_url="https://static-01.daraz.pk/p/real-tecno.png",
                is_primary=False,
                sort_order=1,
            ),
            RawReview(
                platform_id=daraz_id,
                product_listing_id=real_listing.id,
                review_fingerprint=build_review_fingerprint(
                    platform_code="daraz",
                    listing_external_id=real_listing.external_id,
                    external_review_id=f"real-review-{token}",
                    reviewer_external_id=None,
                    reviewer_display_name="Bushra",
                    rating=5,
                    review_text="Genuine scraped review.",
                    reviewed_at=CAPTURE_TIME,
                ),
                external_review_id=f"real-review-{token}",
                reviewer_display_name="Bushra",
                rating=5,
                review_text="Genuine scraped review.",
                reviewed_at=CAPTURE_TIME,
                source_url="https://www.daraz.pk/products/real-tecno.html",
                raw_metadata={},
            ),
        ]
    )
    database_session.commit()

    context = {
        "mixed_product_id": mixed.id,
        "empty_product_id": empty.id,
        "mixed_variant_id": mixed_variant.id,
        "empty_variant_id": empty_variant.id,
        "demo_listing_id": demo_listing.id,
        "real_listing_id": real_listing.id,
        "empty_demo_listing_id": empty_demo_listing.id,
        "test_listing_id": test_listing.id,
        "seller_id": seller.id,
        "token": token,
    }

    yield context

    _teardown(database_session, context)


def _teardown(
    database_session: Session,
    context: dict[str, int],
) -> None:
    """Remove whatever survived the test, children first."""

    database_session.rollback()

    product_ids = [
        context["mixed_product_id"],
        context["empty_product_id"],
    ]
    variant_ids = list(
        database_session.scalars(
            select(ProductVariant.id).where(
                ProductVariant.canonical_product_id.in_(product_ids)
            )
        )
    )
    listing_ids = (
        list(
            database_session.scalars(
                select(ProductListing.id).where(
                    ProductListing.product_variant_id.in_(variant_ids)
                )
            )
        )
        if variant_ids
        else []
    )

    if listing_ids:
        for model, column in (
            (RawReview, RawReview.product_listing_id),
            (PriceHistory, PriceHistory.listing_id),
            (ProductImage, ProductImage.listing_id),
            (PriceAlert, PriceAlert.listing_id),
        ):
            database_session.execute(
                delete(model)
                .where(column.in_(listing_ids))
                .execution_options(synchronize_session=False)
            )

        database_session.execute(
            delete(ProductListing)
            .where(ProductListing.id.in_(listing_ids))
            .execution_options(synchronize_session=False)
        )

    for model, column in (
        (ProductImage, ProductImage.canonical_product_id),
        (PriceAlert, PriceAlert.canonical_product_id),
    ):
        database_session.execute(
            delete(model)
            .where(column.in_(product_ids))
            .execution_options(synchronize_session=False)
        )

    if variant_ids:
        database_session.execute(
            delete(ProductVariant)
            .where(ProductVariant.id.in_(variant_ids))
            .execution_options(synchronize_session=False)
        )

    database_session.execute(
        delete(CanonicalProduct)
        .where(CanonicalProduct.id.in_(product_ids))
        .execution_options(synchronize_session=False)
    )
    database_session.execute(
        delete(Seller)
        .where(Seller.id == context["seller_id"])
        .execution_options(synchronize_session=False)
    )
    database_session.commit()


@pytest.fixture
def cleanup_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point the cleanup script at the test database."""

    from tests.conftest import TestingSessionLocal

    import scripts.remove_demo_catalog as cleanup

    monkeypatch.setattr(cleanup, "SessionLocal", TestingSessionLocal)


def test_demo_markers_are_recognised_without_guessing(
    database_session: Session,
    demo_catalog: dict[str, int],
) -> None:
    """Each demo listing is identified by a marker only the seeder writes."""

    demo = database_session.get(
        ProductListing,
        demo_catalog["demo_listing_id"],
    )
    real = database_session.get(
        ProductListing,
        demo_catalog["real_listing_id"],
    )
    end_to_end = database_session.get(
        ProductListing,
        demo_catalog["test_listing_id"],
    )

    assert is_demo_listing(demo) is True
    assert is_demo_listing(real) is False
    assert is_demo_listing(end_to_end) is False
    assert is_test_listing(end_to_end) is True
    assert is_test_listing(real) is False
    assert "tecno-camon-30-demo" in DEMO_PRODUCT_SLUGS


def test_a_dry_run_changes_nothing(
    database_session: Session,
    demo_catalog: dict[str, int],
    cleanup_session: None,
) -> None:
    """The default mode reports without committing."""

    report = remove_demo_catalog(apply_changes=False)

    assert report.listings_deleted == 2

    database_session.expire_all()

    assert (
        database_session.get(
            ProductListing,
            demo_catalog["demo_listing_id"],
        )
        is not None
    )


def test_cleanup_removes_demo_data_and_preserves_real_data(
    database_session: Session,
    demo_catalog: dict[str, int],
    cleanup_session: None,
) -> None:
    """Demo rows go; genuine listings, history and reviews stay."""

    report = remove_demo_catalog(apply_changes=True)

    database_session.expire_all()

    # Demo listings are gone.
    assert (
        database_session.get(
            ProductListing,
            demo_catalog["demo_listing_id"],
        )
        is None
    )
    assert (
        database_session.get(
            ProductListing,
            demo_catalog["empty_demo_listing_id"],
        )
        is None
    )
    assert report.listings_deleted == 2

    # The genuine listing, its scraped price point and its review survive.
    real_listing = database_session.get(
        ProductListing,
        demo_catalog["real_listing_id"],
    )
    assert real_listing is not None

    sources = sorted(
        database_session.scalars(
            select(PriceHistory.source).where(
                PriceHistory.listing_id == real_listing.id
            )
        )
    )
    assert sources == ["scraper"]

    assert (
        database_session.scalar(
            select(RawReview.id).where(
                RawReview.product_listing_id == real_listing.id
            )
        )
        is not None
    )

    # An empty demo product is deleted; one holding real data is kept and
    # de-branded instead.
    assert (
        database_session.get(
            CanonicalProduct,
            demo_catalog["empty_product_id"],
        )
        is None
    )

    mixed = database_session.get(
        CanonicalProduct,
        demo_catalog["mixed_product_id"],
    )
    assert mixed is not None
    assert mixed.slug == "tecno-camon-30"
    assert mixed.description is None

    # Placeholder imagery goes; real imagery stays.
    image_urls = list(
        database_session.scalars(
            select(ProductImage.image_url).where(
                ProductImage.canonical_product_id == mixed.id
            )
        )
    )
    assert image_urls == ["https://static-01.daraz.pk/p/real-tecno.png"]

    # The demo seller still has the genuine listing's platform but no
    # listings of its own, so it is removed.
    assert (
        database_session.get(Seller, demo_catalog["seller_id"]) is None
    )
    assert report.sellers_deleted == 1


def test_test_listings_are_only_removed_when_asked(
    database_session: Session,
    demo_catalog: dict[str, int],
    cleanup_session: None,
) -> None:
    """An end-to-end test artifact needs the explicit opt-in flag."""

    remove_demo_catalog(apply_changes=True)
    database_session.expire_all()

    assert (
        database_session.get(
            ProductListing,
            demo_catalog["test_listing_id"],
        )
        is not None
    )

    report = remove_demo_catalog(
        apply_changes=True,
        include_test_listings=True,
    )
    database_session.expire_all()

    assert report.test_listings_deleted == 1
    assert (
        database_session.get(
            ProductListing,
            demo_catalog["test_listing_id"],
        )
        is None
    )


def test_a_user_alert_protects_the_record_it_watches(
    database_session: Session,
    demo_catalog: dict[str, int],
    cleanup_session: None,
) -> None:
    """Deleting a watched demo product would cascade a user's alert away."""

    user = User(
        full_name="Demo Cleanup Watcher",
        email=f"cleanup-{demo_catalog['token']}@example.com",
        password_hash="automated-test-password-hash",
        is_active=True,
        is_verified=True,
    )
    database_session.add(user)
    database_session.flush()

    # ``price_alerts`` targets exactly one of a product or a listing.
    alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=demo_catalog["empty_product_id"],
        listing_id=None,
        target_price=Decimal("70000.00"),
        currency="PKR",
    )
    database_session.add(alert)
    database_session.commit()

    # Hold the id locally: the forced run deletes this row, and touching the
    # expired instance afterwards would try to refresh a row that is gone.
    alert_id = alert.id

    try:
        report = remove_demo_catalog(apply_changes=True)
        database_session.expire_all()

        # The demo listing goes, but the product the alert watches stays.
        assert (
            database_session.get(
                ProductListing,
                demo_catalog["empty_demo_listing_id"],
            )
            is None
        )

        product = database_session.get(
            CanonicalProduct,
            demo_catalog["empty_product_id"],
        )
        assert product is not None
        # The demo slug is kept so a later run can still find this product.
        assert product.slug == "infinix-note-40-pro-demo"
        assert database_session.get(PriceAlert, alert_id) is not None
        assert len(report.blocked_by_alerts) == 1
        assert "infinix-note-40-pro" in report.blocked_by_alerts[0]

        # The operator can still insist, and the report says what that costs.
        forced = remove_demo_catalog(
            apply_changes=True,
            force_drop_alerts=True,
        )
        database_session.expire_all()

        assert forced.products_deleted == 1
        assert (
            database_session.get(
                CanonicalProduct,
                demo_catalog["empty_product_id"],
            )
            is None
        )
        # The cascade took the alert with it, exactly as the report warned.
        assert (
            database_session.scalar(
                select(PriceAlert.id).where(PriceAlert.id == alert_id)
            )
            is None
        )
    finally:
        database_session.rollback()
        database_session.execute(
            delete(PriceAlert)
            .where(PriceAlert.user_id == user.id)
            .execution_options(synchronize_session=False)
        )
        database_session.execute(
            delete(User)
            .where(User.id == user.id)
            .execution_options(synchronize_session=False)
        )
        database_session.commit()
