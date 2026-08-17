from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from app.models.price_alert import PriceAlert
from app.models.user import User

from app.core.config import settings
from app.models.brand import Brand
from app.models.canonical_product import (
    CanonicalProduct,
)
from app.models.category import Category
from app.models.price_history import PriceHistory
from app.models.product_listing import (
    ProductListing,
)
from app.models.product_variant import (
    ProductVariant,
)
from app.models.seller import Seller


ENDPOINT = (
    "/api/v1/internal/acquisition/listings"
)

MATCH_ENDPOINT = (
    "/api/v1/internal/acquisition/match-product"
)

TEST_INGESTION_KEY = (
    "VextroTestIngestionKey2026Secure"
)

BASE_CAPTURE_TIME = datetime(
    2026,
    8,
    6,
    1,
    30,
    tzinfo=timezone.utc,
)


@pytest.fixture(autouse=True)
def configure_ingestion_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configure a predictable ingestion key for every test."""

    monkeypatch.setattr(
        settings,
        "ingestion_api_key",
        TEST_INGESTION_KEY,
    )


@pytest.fixture
def acquisition_context(
    database_session: Session,
) -> Generator[dict[str, object], None, None]:
    """Create one temporary active product variant."""

    unique_token = uuid4().hex[:10]

    category_id = database_session.scalar(
        select(Category.id).where(
            Category.slug == "mobile-phones",
        ),
    )

    brand_id = database_session.scalar(
        select(Brand.id).where(
            Brand.slug == "samsung",
        ),
    )

    assert category_id is not None
    assert brand_id is not None

    product = CanonicalProduct(
        category_id=category_id,
        brand_id=brand_id,
        name=(
            f"Acquisition Test Phone "
            f"{unique_token}"
        ),
        slug=(
            f"acquisition-test-phone-"
            f"{unique_token}"
        ),
        model=f"ACQ-{unique_token}",
        description=(
            "Temporary product used by "
            "acquisition integration tests."
        ),
        specifications={
            "test_record": True,
        },
        is_active=True,
    )

    database_session.add(product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=f"ACQ-SKU-{unique_token}",
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={
            "test_record": True,
        },
        is_active=True,
    )

    database_session.add(variant)
    database_session.commit()

    database_session.refresh(product)
    database_session.refresh(variant)

    context = {
        "token": unique_token,
        "product_id": product.id,
        "variant_id": variant.id,
        "external_id": (
            f"ACQ-LISTING-{unique_token}"
        ),
        "seller_external_id": (
            f"ACQ-SELLER-{unique_token}"
        ),
    }

    yield context

    database_session.rollback()

    listing_ids = list(
        database_session.scalars(
            select(ProductListing.id).where(
                ProductListing.product_variant_id
                == variant.id,
            ),
        ),
    )

    if listing_ids:
        database_session.execute(
            delete(PriceHistory)
            .where(
                PriceHistory.listing_id.in_(
                    listing_ids,
                ),
            )
            .execution_options(
                synchronize_session=False,
            ),
        )

        database_session.execute(
            delete(ProductListing)
            .where(
                ProductListing.id.in_(
                    listing_ids,
                ),
            )
            .execution_options(
                synchronize_session=False,
            ),
        )

    database_session.execute(
        delete(Seller)
        .where(
            Seller.external_seller_id
            == context["seller_external_id"],
        )
        .execution_options(
            synchronize_session=False,
        ),
    )

    database_session.execute(
        delete(ProductVariant)
        .where(
            ProductVariant.id
            == variant.id,
        )
        .execution_options(
            synchronize_session=False,
        ),
    )

    database_session.execute(
        delete(CanonicalProduct)
        .where(
            CanonicalProduct.id
            == product.id,
        )
        .execution_options(
            synchronize_session=False,
        ),
    )

    database_session.commit()

@pytest.fixture
def acquisition_alert_context(
    database_session: Session,
    acquisition_context: dict[str, object],
) -> Generator[dict[str, object], None, None]:
    """Create one active product-level alert for acquisition tests."""

    unique_token = str(
        acquisition_context["token"],
    )

    user = User(
        full_name="Acquisition Alert Test User",
        email=(
            f"acquisition-alert-{unique_token}"
            "@example.com"
        ),
        password_hash="automated-test-password-hash",
        is_active=True,
        is_verified=True,
    )

    database_session.add(user)
    database_session.flush()

    alert = PriceAlert(
        user_id=user.id,
        canonical_product_id=int(
            acquisition_context["product_id"],
        ),
        listing_id=None,
        target_price=Decimal("125000.00"),
        currency="PKR",
    )

    database_session.add(alert)
    database_session.commit()

    database_session.refresh(user)
    database_session.refresh(alert)

    context = {
        "user_id": user.id,
        "alert_id": alert.id,
    }

    yield context

    database_session.rollback()

    database_session.execute(
        delete(PriceAlert).where(
            PriceAlert.user_id == user.id,
        ),
    )

    database_session.execute(
        delete(User).where(
            User.id == user.id,
        ),
    )

    database_session.commit()



@pytest.fixture
def acquisition_alert_user(
    database_session: Session,
    acquisition_context: dict[str, object],
) -> Generator[dict[str, int], None, None]:
    """Create one temporary user for listing-level alert tests."""

    unique_token = str(
        acquisition_context["token"],
    )

    user = User(
        full_name="Acquisition Listing Alert User",
        email=(
            f"acquisition-listing-alert-{unique_token}"
            "@example.com"
        ),
        password_hash="automated-test-password-hash",
        is_active=True,
        is_verified=True,
    )

    database_session.add(user)
    database_session.commit()
    database_session.refresh(user)

    context = {
        "user_id": user.id,
    }

    yield context

    database_session.rollback()

    database_session.execute(
        delete(PriceAlert).where(
            PriceAlert.user_id == user.id,
        ),
    )

    database_session.execute(
        delete(User).where(
            User.id == user.id,
        ),
    )

    database_session.commit()


def ingestion_headers(
    key: str = TEST_INGESTION_KEY,
) -> dict[str, str]:
    """Return the internal API authentication header."""

    return {
        "X-Ingestion-Key": key,
    }


def serialize_timestamp(
    timestamp: datetime,
) -> str:
    """Return an ISO timestamp ending in Z."""

    return timestamp.isoformat().replace(
        "+00:00",
        "Z",
    )


def build_payload(
    context: dict[str, object],
    *,
    captured_at: datetime = BASE_CAPTURE_TIME,
    current_price: float = 124999.0,
) -> dict[str, object]:
    """Build one valid normalized acquisition payload."""

    token = str(context["token"])

    return {
        "platform_code": "daraz",
        "product_variant_id": int(
            context["variant_id"],
        ),
        "external_id": str(
            context["external_id"],
        ),
        "title": (
            "Samsung Acquisition Test Phone "
            "8GB 256GB"
        ),
        "product_url": (
            "https://www.daraz.pk/products/"
            f"acquisition-test-{token}"
        ),
        "current_price": current_price,
        "original_price": 129999.0,
        "currency": "PKR",
        "rating": 4.6,
        "review_count": 210,
        "warranty": "1 Year Brand Warranty",
        "is_available": True,
        "scraped_at": serialize_timestamp(
            captured_at,
        ),
        "seller": {
            "external_seller_id": str(
                context[
                    "seller_external_id"
                ],
            ),
            "name": (
                f"Acquisition Test Seller "
                f"{token}"
            ),
            "profile_url": (
                "https://www.daraz.pk/shop/"
                f"acquisition-test-{token}"
            ),
            "rating": 4.8,
            "review_count": 1250,
            "is_verified": True,
        },
        "raw_payload": {
            "source": "daraz",
            "collection_mode": "test",
        },
    }


def test_ingestion_rejects_invalid_key(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Reject requests containing the wrong secret."""

    response = client.post(
        ENDPOINT,
        headers=ingestion_headers(
            "wrong-ingestion-key",
        ),
        json=build_payload(
            acquisition_context,
        ),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid ingestion key."
    )


def test_ingestion_rejects_unknown_variant(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Reject a product variant that does not exist."""

    payload = build_payload(
        acquisition_context,
    )

    payload["product_variant_id"] = (
        999999999
    )

    response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=payload,
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "The requested product variant "
        "was not found."
    )


def test_ingestion_creates_listing_seller_and_history(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
) -> None:
    """Create the seller, listing and first price capture."""

    payload = build_payload(
        acquisition_context,
    )

    response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=payload,
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["status"] == "created"
    assert response_data["listing_created"] is True
    assert response_data["seller_created"] is True

    assert (
        response_data["price_history_created"]
        is True
    )

    assert response_data["alerts_triggered"] == 0

    database_session.expire_all()

    listing = database_session.scalar(
        select(ProductListing).where(
            ProductListing.external_id
            == acquisition_context[
                "external_id"
            ],
        ),
    )

    assert listing is not None
    assert listing.current_price == Decimal(
        "124999.00",
    )
    assert listing.currency == "PKR"
    assert listing.is_available is True

    seller = database_session.scalar(
        select(Seller).where(
            Seller.external_seller_id
            == acquisition_context[
                "seller_external_id"
            ],
        ),
    )

    assert seller is not None
    assert seller.is_verified is True

    history_count = database_session.scalar(
        select(
            func.count(PriceHistory.id),
        ).where(
            PriceHistory.listing_id
            == listing.id,
        ),
    )

    assert history_count == 1


def test_ingestion_triggers_matching_price_alert_once(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
    acquisition_alert_context: dict[str, object],
) -> None:
    """Trigger a matching alert once when captured price reaches target."""

    first_payload = build_payload(
        acquisition_context,
        current_price=124999.0,
    )

    first_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=first_payload,
    )

    assert first_response.status_code == 201

    first_response_data = first_response.json()

    assert first_response_data["alerts_triggered"] == 1

    database_session.expire_all()

    alert = database_session.get(
        PriceAlert,
        int(acquisition_alert_context["alert_id"]),
    )

    assert alert is not None
    assert alert.is_active is True
    assert alert.is_triggered is True
    assert alert.triggered_at is not None
    assert alert.last_checked_at is not None
    assert alert.notification_count == 1
    assert alert.last_notified_at is not None

    second_payload = build_payload(
        acquisition_context,
        captured_at=(
            BASE_CAPTURE_TIME
            + timedelta(minutes=30)
        ),
        current_price=123999.0,
    )

    second_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=second_payload,
    )

    assert second_response.status_code == 200
    assert second_response.json()["status"] == "updated"

    second_response_data = second_response.json()

    assert second_response_data["alerts_triggered"] == 0

    database_session.expire_all()

    refreshed_alert = database_session.get(
        PriceAlert,
        int(acquisition_alert_context["alert_id"]),
    )

    assert refreshed_alert is not None
    assert refreshed_alert.is_triggered is True
    assert refreshed_alert.notification_count == 1


def test_ingestion_does_not_trigger_alert_above_target(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
    acquisition_alert_context: dict[str, object],
) -> None:
    """Keep an alert pending when captured price is above its target."""

    payload = build_payload(
        acquisition_context,
        current_price=126000.0,
    )

    response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=payload,
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["alerts_triggered"] == 0

    database_session.expire_all()

    alert = database_session.get(
        PriceAlert,
        int(acquisition_alert_context["alert_id"]),
    )

    assert alert is not None
    assert alert.is_active is True
    assert alert.is_triggered is False
    assert alert.triggered_at is None
    assert alert.last_checked_at is not None
    assert alert.notification_count == 0
    assert alert.last_notified_at is None




def test_ingestion_triggers_matching_listing_price_alert(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
    acquisition_alert_user: dict[str, int],
) -> None:
    """Trigger an alert attached to one specific marketplace listing."""

    first_payload = build_payload(
        acquisition_context,
        current_price=126000.0,
    )

    first_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=first_payload,
    )

    assert first_response.status_code == 201

    listing_id = int(
        first_response.json()["listing_id"],
    )

    alert = PriceAlert(
        user_id=acquisition_alert_user["user_id"],
        canonical_product_id=None,
        listing_id=listing_id,
        target_price=Decimal("125000.00"),
        currency="PKR",
    )

    database_session.add(alert)
    database_session.commit()
    database_session.refresh(alert)

    alert_id = alert.id

    second_payload = build_payload(
        acquisition_context,
        captured_at=(
            BASE_CAPTURE_TIME
            + timedelta(minutes=30)
        ),
        current_price=124000.0,
    )

    second_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=second_payload,
    )

    assert second_response.status_code == 200

    second_response_data = second_response.json()

    assert second_response_data["status"] == "updated"
    assert second_response_data["listing_id"] == listing_id
    assert second_response_data["alerts_triggered"] == 1

    database_session.expire_all()

    triggered_alert = database_session.get(
        PriceAlert,
        alert_id,
    )

    assert triggered_alert is not None
    assert triggered_alert.canonical_product_id is None
    assert triggered_alert.listing_id == listing_id
    assert triggered_alert.is_active is True
    assert triggered_alert.is_triggered is True
    assert triggered_alert.triggered_at is not None
    assert triggered_alert.last_checked_at is not None
    assert triggered_alert.notification_count == 1
    assert triggered_alert.last_notified_at is not None


def test_ingestion_detects_duplicate_capture(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
) -> None:
    """Do not save the same listing timestamp twice."""

    payload = build_payload(
        acquisition_context,
    )

    first_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=payload,
    )

    duplicate_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=payload,
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 200

    duplicate_data = duplicate_response.json()

    assert duplicate_data["status"] == "duplicate"

    assert (
        duplicate_data["listing_created"]
        is False
    )

    assert (
        duplicate_data["price_history_created"]
        is False
    )

    database_session.expire_all()

    listing = database_session.scalar(
        select(ProductListing).where(
            ProductListing.external_id
            == acquisition_context[
                "external_id"
            ],
        ),
    )

    assert listing is not None

    history_count = database_session.scalar(
        select(
            func.count(PriceHistory.id),
        ).where(
            PriceHistory.listing_id
            == listing.id,
        ),
    )

    assert history_count == 1


def test_ingestion_updates_existing_listing(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
) -> None:
    """Update a listing and save another price capture."""

    first_payload = build_payload(
        acquisition_context,
    )

    first_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=first_payload,
    )

    assert first_response.status_code == 201

    second_capture_time = (
        BASE_CAPTURE_TIME
        + timedelta(hours=12)
    )

    second_payload = build_payload(
        acquisition_context,
        captured_at=second_capture_time,
        current_price=119999.0,
    )

    second_payload["rating"] = 4.8
    second_payload["review_count"] = 250
    second_payload["is_available"] = False

    seller_data = second_payload["seller"]

    assert isinstance(seller_data, dict)

    seller_data["name"] = (
        "Updated Acquisition Test Seller"
    )

    update_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=second_payload,
    )

    assert update_response.status_code == 200

    update_data = update_response.json()

    assert update_data["status"] == "updated"

    assert (
        update_data["listing_created"]
        is False
    )

    assert (
        update_data["price_history_created"]
        is True
    )

    database_session.expire_all()

    listing = database_session.scalar(
        select(ProductListing).where(
            ProductListing.external_id
            == acquisition_context[
                "external_id"
            ],
        ),
    )

    assert listing is not None

    assert listing.current_price == Decimal(
        "119999.00",
    )

    assert listing.rating == Decimal("4.80")
    assert listing.review_count == 250
    assert listing.is_available is False

    history_count = database_session.scalar(
        select(
            func.count(PriceHistory.id),
        ).where(
            PriceHistory.listing_id
            == listing.id,
        ),
    )

    assert history_count == 2

    seller = database_session.scalar(
        select(Seller).where(
            Seller.external_seller_id
            == acquisition_context[
                "seller_external_id"
            ],
        ),
    )

    assert seller is not None

    assert seller.name == (
        "Updated Acquisition Test Seller"
    )

def test_product_match_returns_correct_variant(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Match a specific marketplace title to the expected variant."""

    token = str(
        acquisition_context["token"]
    )

    response = client.post(
        MATCH_ENDPOINT,
        headers=ingestion_headers(),
        json={
            "title": (
                f"Acquisition Test Phone "
                f"{token} "
                "8GB 256GB Black"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["matched"] is True

    assert (
        body["product_variant_id"]
        == acquisition_context["variant_id"]
    )

    assert (
        body["canonical_product_id"]
        == acquisition_context["product_id"]
    )

    assert body["confidence"] >= 75

    assert body["product_name"] == (
        f"Acquisition Test Phone {token}"
    )

    assert body["brand_name"] == "Samsung"
    assert body["model"] == f"ACQ-{token}"

    assert body["ram_gb"] == 8
    assert body["storage_gb"] == 256
    assert body["color"] == "Black"


def test_product_match_rejects_unknown_product(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Do not automatically match an unrelated marketplace product."""

    response = client.post(
        MATCH_ENDPOINT,
        headers=ingestion_headers(),
        json={
            "title": (
                "Random Ultra Phone XYZ "
                "24GB 2TB Neon Green"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["matched"] is False
    assert body["product_variant_id"] is None
    assert body["canonical_product_id"] is None
    assert body["reason"]


def test_product_match_rejects_wrong_storage(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Reject a strong product match when storage is incompatible."""

    token = str(
        acquisition_context["token"]
    )

    response = client.post(
        MATCH_ENDPOINT,
        headers=ingestion_headers(),
        json={
            "title": (
                f"Acquisition Test Phone "
                f"{token} "
                "8GB 128GB Black"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["matched"] is False
    assert body["product_variant_id"] is None
    assert body["canonical_product_id"] is None

    assert "storage" in (
        body["reason"].lower()
    )


def test_product_match_rejects_vague_title(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Reject titles without enough product identity."""

    response = client.post(
        MATCH_ENDPOINT,
        headers=ingestion_headers(),
        json={
            "title": (
                "Samsung smartphone 256GB"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["matched"] is False
    assert body["product_variant_id"] is None
    assert body["canonical_product_id"] is None

    assert (
        "specific enough"
        in body["reason"].lower()
    )


def test_product_match_rejects_invalid_ingestion_key(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Protect the internal product matching endpoint."""

    token = str(
        acquisition_context["token"]
    )

    response = client.post(
        MATCH_ENDPOINT,
        headers=ingestion_headers(
            "wrong-ingestion-key",
        ),
        json={
            "title": (
                f"Acquisition Test Phone "
                f"{token} "
                "8GB 256GB Black"
            ),
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Invalid ingestion key.",
    }


def test_product_match_to_ingestion_to_price_intelligence_e2e(
    client: TestClient,
    acquisition_context: dict[str, object],
) -> None:
    """Complete marketplace matching and acquisition pipeline."""

    token = str(
        acquisition_context["token"]
    )

    marketplace_title = (
        f"Samsung Acquisition Test Phone "
        f"{token} "
        f"ACQ-{token} "
        "8GB RAM 256GB Black"
    )

    # Step 1: Resolve the scraper title to a VEXTRO variant.
    match_response = client.post(
        MATCH_ENDPOINT,
        headers=ingestion_headers(),
        json={
            "title": marketplace_title,
        },
    )

    assert match_response.status_code == 200

    match_body = match_response.json()

    assert match_body["matched"] is True

    matched_variant_id = (
        match_body["product_variant_id"]
    )

    matched_product_id = (
        match_body["canonical_product_id"]
    )

    assert matched_variant_id == (
        acquisition_context["variant_id"]
    )

    assert matched_product_id == (
        acquisition_context["product_id"]
    )

    # Step 2: Pass the matcher result into acquisition ingestion.
    ingestion_payload = build_payload(
        acquisition_context,
        current_price=124999.0,
    )

    ingestion_payload[
        "product_variant_id"
    ] = matched_variant_id

    ingestion_payload["title"] = (
        marketplace_title
    )

    ingestion_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=ingestion_payload,
    )

    assert ingestion_response.status_code == 201

    ingestion_body = ingestion_response.json()

    assert ingestion_body["status"] == "created"

    assert (
        ingestion_body["listing_created"]
        is True
    )

    assert (
        ingestion_body["price_history_created"]
        is True
    )

    assert ingestion_body["listing_id"] is not None

    assert (
        ingestion_body["price_history_id"]
        is not None
    )

    listing_id = ingestion_body["listing_id"]

    # Step 3: Verify the ingested price through
    # the consumer Price Intelligence API.
    price_response = client.get(
        (
            f"/api/v1/products/"
            f"{matched_product_id}/price-history"
        )
    )

    assert price_response.status_code == 200

    price_body = price_response.json()

    assert (
        price_body["product_id"]
        == matched_product_id
    )

    assert price_body["total_listings"] == 1
    assert price_body["total_points"] == 1

    assert len(price_body["listings"]) == 1

    listing = price_body["listings"][0]

    assert listing["listing_id"] == listing_id

    summary = listing["summary"]

    assert Decimal(
        str(summary["current_price"])
    ) == Decimal("124999.00")

    assert Decimal(
        str(summary["lowest_price"])
    ) == Decimal("124999.00")

    assert Decimal(
        str(summary["highest_price"])
    ) == Decimal("124999.00")

    assert Decimal(
        str(summary["average_price"])
    ) == Decimal("124999.00")

    assert len(listing["points"]) == 1

    assert Decimal(
        str(listing["points"][0]["price"])
    ) == Decimal("124999.00")

    # Step 4: Simulate a later scraper run with a changed price.
    second_capture_time = (
        BASE_CAPTURE_TIME
        + timedelta(hours=12)
    )

    second_payload = build_payload(
        acquisition_context,
        captured_at=second_capture_time,
        current_price=119999.0,
    )

    # The scraper must keep using the ID returned by matching.
    second_payload[
        "product_variant_id"
    ] = matched_variant_id

    second_payload["title"] = (
        marketplace_title
    )

    update_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=second_payload,
    )

    assert update_response.status_code == 200

    update_body = update_response.json()

    assert update_body["status"] == "updated"

    assert (
        update_body["listing_created"]
        is False
    )

    assert (
        update_body["price_history_created"]
        is True
    )

    assert (
        update_body["listing_id"]
        == listing_id
    )

    # Step 5: Price Intelligence must now expose both captures.
    updated_price_response = client.get(
        (
            f"/api/v1/products/"
            f"{matched_product_id}/price-history"
        )
    )

    assert updated_price_response.status_code == 200

    updated_price_body = (
        updated_price_response.json()
    )

    assert (
        updated_price_body["total_listings"]
        == 1
    )

    assert (
        updated_price_body["total_points"]
        == 2
    )

    updated_listing = (
        updated_price_body["listings"][0]
    )

    assert (
        updated_listing["listing_id"]
        == listing_id
    )

    updated_summary = (
        updated_listing["summary"]
    )

    assert Decimal(
        str(updated_summary["current_price"])
    ) == Decimal("119999.00")

    assert Decimal(
        str(updated_summary["lowest_price"])
    ) == Decimal("119999.00")

    assert Decimal(
        str(updated_summary["highest_price"])
    ) == Decimal("124999.00")

    assert Decimal(
        str(updated_summary["average_price"])
    ) == Decimal("122499.00")

    returned_prices = [
        Decimal(str(point["price"]))
        for point in updated_listing["points"]
    ]

    assert returned_prices == [
        Decimal("124999.00"),
        Decimal("119999.00"),
    ]

    # Step 6: Sending the same capture again must be idempotent.
    duplicate_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=second_payload,
    )

    assert duplicate_response.status_code == 200

    duplicate_body = (
        duplicate_response.json()
    )

    assert (
        duplicate_body["status"]
        == "duplicate"
    )

    assert (
        duplicate_body["listing_created"]
        is False
    )

    assert (
        duplicate_body["price_history_created"]
        is False
    )

    assert (
        duplicate_body["listing_id"]
        == listing_id
    )

    # Step 7: Duplicate ingestion must not create a third point.
    final_price_response = client.get(
        (
            f"/api/v1/products/"
            f"{matched_product_id}/price-history"
        )
    )

    assert final_price_response.status_code == 200

    final_price_body = (
        final_price_response.json()
    )

    assert (
        final_price_body["total_points"]
        == 2
    )

    assert (
        len(
            final_price_body[
                "listings"
            ][0]["points"]
        )
        == 2
    )