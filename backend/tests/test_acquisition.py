"""Integration tests for marketplace acquisition ingestion."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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