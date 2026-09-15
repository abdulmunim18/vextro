from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.raw_review import RawReview
from app.models.seller import Seller
from app.schemas.reviews import ReviewBatchInput, ReviewInput
from app.services.review_normalization import (
    build_review_fingerprint,
    normalize_review_text,
)


TEST_INGESTION_KEY = "VextroReviewTestKey2026Secure"
TEST_PASSWORD = "StrongPassword123!"


@pytest.fixture(autouse=True)
def configure_ingestion_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "ingestion_api_key",
        TEST_INGESTION_KEY,
    )


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def ingestion_headers(key: str = TEST_INGESTION_KEY) -> dict[str, str]:
    return {"X-Ingestion-Key": key}


def authenticated_headers(client: TestClient) -> dict[str, str]:
    email = f"{unique('review-user')}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Review Test User",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": "consumer",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def create_review_listing(
    database_session: Session,
    *,
    platform_code: str = "daraz",
) -> tuple[CanonicalProduct, ProductListing, Seller]:
    platform = database_session.scalar(
        select(Platform).where(Platform.code == platform_code)
    )
    assert platform is not None
    category = Category(
        name=unique("Review Category"),
        slug=unique("review-category").lower(),
    )
    brand = Brand(
        name=unique("Review Brand"),
        slug=unique("review-brand").lower(),
    )
    database_session.add_all([category, brand])
    database_session.flush()
    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=unique("Review Phone"),
        slug=unique("review-phone").lower(),
        model=unique("RVW"),
        specifications={},
        is_active=True,
    )
    database_session.add(product)
    database_session.flush()
    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=unique("REVIEW-SKU"),
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique("review-seller"),
        name=unique("Review Seller"),
        rating=Decimal("4.70"),
        review_count=100,
        is_verified=True,
        is_active=True,
    )
    database_session.add_all([variant, seller])
    database_session.flush()
    listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique("review-listing"),
        title="Review Test Listing",
        product_url="https://www.daraz.pk/products/review-test.html",
        current_price=Decimal("100000.00"),
        currency="PKR",
        rating=Decimal("4.00"),
        review_count=3,
        is_available=True,
        raw_payload={},
    )
    database_session.add(listing)
    database_session.commit()
    return product, listing, seller


def build_batch(listing: ProductListing) -> dict:
    return {
        "platform_code": "daraz",
        "external_listing_id": listing.external_id,
        "source_url": listing.product_url,
        "reviews": [
            {
                "external_review_id": "external-review-1",
                "reviewer_external_id": "buyer-1",
                "reviewer_display_name": "  Sanitized   Buyer  ",
                "rating": 5,
                "review_text": "<p>Excellent&nbsp;phone!</p>",
                "reviewed_at": "2026-03-01T00:00:00Z",
                "verified_purchase": True,
                "helpful_count": 2,
                "raw_metadata": {"source_page": 1},
            },
            {
                "external_review_id": "external-review-2",
                "rating": 4,
                "review_text": None,
                "reviewed_at": "2026-03-02",
                "verified_purchase": None,
            },
            {
                "reviewer_display_name": "Unicode Reviewer",
                "rating": 3,
                "review_text": "پیکنگ\u00a0اچھی تھی ❤️",
                "reviewed_at": "2026-03-03T00:00:00+05:00",
                "verified_purchase": False,
            },
        ],
    }


def test_review_validation_and_normalization_boundaries() -> None:
    valid = ReviewInput.model_validate(
        {
            "rating": 5,
            "review_text": " <b>Battery!!!</b>\u2003VERY BAD ",
            "reviewed_at": "2026-03-31",
            "verified_purchase": True,
            "helpful_count": 0,
        }
    )
    assert valid.review_text == "Battery!!! VERY BAD"
    assert valid.reviewed_at is not None
    assert valid.reviewed_at.tzinfo is not None

    for invalid_rating in (0, 6, -1, 4.5, "5", True):
        with pytest.raises(ValidationError):
            ReviewInput.model_validate({"rating": invalid_rating})

    with pytest.raises(ValidationError):
        ReviewInput.model_validate(
            {"rating": 5, "reviewed_at": "not-a-date"}
        )
    with pytest.raises(ValidationError):
        ReviewInput.model_validate(
            {"rating": 5, "review_text": "x" * 10_001}
        )
    with pytest.raises(ValidationError):
        ReviewInput.model_validate(
            {"rating": 5, "verified_purchase": "yes"}
        )
    with pytest.raises(ValidationError):
        ReviewInput.model_validate(
            {"rating": 5, "helpful_count": -1}
        )

    assert normalize_review_text(" \n\t ") is None


def test_review_batch_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ReviewBatchInput.model_validate(
            {
                "platform_code": "daraz",
                "external_listing_id": "listing",
                "source_url": "https://www.daraz.pk/product",
                "reviews": [{"rating": 5}] * 101,
            }
        )


def test_fallback_fingerprint_is_stable() -> None:
    review = ReviewInput.model_validate(
        {
            "rating": 5,
            "reviewer_display_name": "Same Reviewer",
            "review_text": "Same text",
            "reviewed_at": "2026-03-01",
        }
    )
    kwargs = {
        "platform_code": "priceoye",
        "listing_external_id": "same-listing",
        "external_review_id": None,
        "reviewer_external_id": review.reviewer_external_id,
        "reviewer_display_name": review.reviewer_display_name,
        "rating": review.rating,
        "review_text": review.review_text,
        "reviewed_at": review.reviewed_at,
    }
    assert build_review_fingerprint(**kwargs) == build_review_fingerprint(
        **kwargs
    )
    assert len(build_review_fingerprint(**kwargs)) == 64


@pytest.mark.parametrize(
    "headers",
    [{}, ingestion_headers("wrong-key")],
)
def test_review_ingestion_requires_key(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/internal/acquisition/reviews",
        headers=headers,
        json={
            "platform_code": "daraz",
            "external_listing_id": "missing",
            "source_url": "https://www.daraz.pk/product",
            "reviews": [{"rating": 5}],
        },
    )
    assert response.status_code == 401


def test_unknown_listing_is_rejected_without_orphan(
    client: TestClient,
    database_session: Session,
) -> None:
    before = database_session.scalar(select(func.count(RawReview.id)))
    response = client.post(
        "/api/v1/internal/acquisition/reviews",
        headers=ingestion_headers(),
        json={
            "platform_code": "daraz",
            "external_listing_id": unique("missing"),
            "source_url": "https://www.daraz.pk/product",
            "reviews": [{"rating": 5}],
        },
    )
    assert response.status_code == 404
    database_session.expire_all()
    after = database_session.scalar(select(func.count(RawReview.id)))
    assert after == before


def test_review_end_to_end_deduplication_association_and_read_api(
    client: TestClient,
    database_session: Session,
) -> None:
    product, listing, seller = create_review_listing(database_session)
    payload = build_batch(listing)

    first = client.post(
        "/api/v1/internal/acquisition/reviews",
        headers=ingestion_headers(),
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["created_count"] == 3
    assert first.json()["duplicate_count"] == 0
    assert first.json()["seller_id"] == seller.id

    second = client.post(
        "/api/v1/internal/acquisition/reviews",
        headers=ingestion_headers(),
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["created_count"] == 0
    assert second.json()["duplicate_count"] == 3

    database_session.expire_all()
    saved = list(
        database_session.scalars(
            select(RawReview)
            .where(RawReview.product_listing_id == listing.id)
            .order_by(RawReview.id)
        ).all()
    )
    assert len(saved) == 3
    assert all(review.seller_id == seller.id for review in saved)
    assert all(review.platform_id == listing.platform_id for review in saved)
    assert saved[0].review_text == "Excellent phone!"
    assert saved[1].review_text is None

    auth = authenticated_headers(client)
    first_page = client.get(
        f"/api/v1/products/{product.id}/reviews",
        headers=auth,
        params={"page": 1, "page_size": 2},
    )
    assert first_page.status_code == 200
    body = first_page.json()
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert body["average_rating"] == 4.0
    assert body["rating_distribution"] == {
        "1": 0,
        "2": 0,
        "3": 1,
        "4": 1,
        "5": 1,
    }
    assert len(body["items"]) == 2
    assert all(item["seller_id"] == seller.id for item in body["items"])

    second_page = client.get(
        f"/api/v1/products/{product.id}/reviews",
        headers=auth,
        params={"page": 2, "page_size": 2},
    )
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1


def test_review_read_api_requires_application_authentication(
    client: TestClient,
    database_session: Session,
) -> None:
    product, _listing, _seller = create_review_listing(database_session)
    response = client.get(f"/api/v1/products/{product.id}/reviews")
    assert response.status_code == 401


def test_review_read_rejects_listing_from_another_product(
    client: TestClient,
    database_session: Session,
) -> None:
    first_product, _first_listing, _seller = create_review_listing(
        database_session
    )
    _other_product, other_listing, _other_seller = create_review_listing(
        database_session,
        platform_code="priceoye",
    )
    response = client.get(
        f"/api/v1/products/{first_product.id}/reviews",
        headers=authenticated_headers(client),
        params={"listing_id": other_listing.id},
    )
    assert response.status_code == 404
