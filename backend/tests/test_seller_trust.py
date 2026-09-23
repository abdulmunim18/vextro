import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product_listing import ProductListing
from app.models.review_analysis import ReviewAnalysis
from app.models.seller_trust_analysis import SellerTrustAnalysis
from app.services.seller_trust_engine import VERSION, aggregate_seller_evidence
from tests.test_reviews import TEST_INGESTION_KEY, authenticated_headers, create_review_listing, ingestion_headers, unique


SCENARIOS = json.loads((Path(__file__).parent / "fixtures" / "seller_trust_scenarios.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def configure_review_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ingestion_api_key", TEST_INGESTION_KEY)


def artificial_rows(*, low: int, medium: int, high: int, verified: int = 0, known: int = 0, rating: int = 5):
    rows = []
    for index, (level, score) in enumerate([("low", 0)] * low + [("medium", 40)] * medium + [("high", 80)] * high):
        status = True if index < verified else False if index < known else None
        review = SimpleNamespace(id=index + 1, rating=rating, verified_purchase=status)
        analysis = SimpleNamespace(suspicion_level=level, suspicion_score=score, is_exact_duplicate=False, is_near_duplicate=False)
        rows.append((review, analysis))
    return rows


def test_stronger_and_weaker_artificial_evidence_have_distinct_scores() -> None:
    strong = SCENARIOS["stronger_evidence"]
    high = aggregate_seller_evidence(
        external_seller_id="stable-123", listing_count=4,
        rows=artificial_rows(low=strong["low"], medium=strong["medium"], high=strong["high"], verified=strong["verified_purchases"], known=strong["known_purchase_status"]),
    )
    assert high["trust_score"] == 82
    assert high["trust_level"] == "high"
    assert high["confidence_score"] == 100
    assert high["high_suspicion_percentage"] == 2.0
    assert high["average_review_suspicion_score"] == 4.8
    assert high["verified_purchase_ratio"] == 80.0

    weak = SCENARIOS["weaker_evidence"]
    low = aggregate_seller_evidence(
        external_seller_id="stable-456", listing_count=3,
        rows=artificial_rows(low=weak["low"], medium=weak["medium"], high=weak["high"]),
    )
    assert low["trust_score"] == 52
    assert low["trust_level"] == "low"
    assert low["confidence_score"] == 100
    assert low["high_suspicion_percentage"] == 35.0
    assert low["average_review_suspicion_score"] == 40.0
    assert low["verified_purchase_ratio"] is None


def test_insufficient_identity_volume_and_analysis_coverage() -> None:
    rows = artificial_rows(low=2, medium=0, high=0)
    two = aggregate_seller_evidence(external_seller_id="stable-id", listing_count=1, rows=rows)
    assert two["trust_score"] is None
    assert two["trust_level"] == "insufficient_data"
    assert two["confidence_level"] == "low"
    name_only = aggregate_seller_evidence(external_seller_id=None, listing_count=1, rows=artificial_rows(low=100, medium=0, high=0))
    assert name_only["trust_score"] is None
    partial = aggregate_seller_evidence(external_seller_id="stable-id", listing_count=3, rows=artificial_rows(low=20, medium=0, high=0) + [(SimpleNamespace(id=100 + index, rating=5, verified_purchase=None), None) for index in range(80)])
    assert partial["analysis_coverage_percentage"] == 20.0
    assert partial["trust_score"] is None
    assert "coverage" in partial["reasons"][0]


def test_high_ratings_null_verified_and_one_bad_review_do_not_destroy_trust() -> None:
    clean = aggregate_seller_evidence(external_seller_id="id", listing_count=1, rows=artificial_rows(low=100, medium=0, high=0, rating=5))
    assert clean["trust_level"] == "high"
    assert clean["verified_purchase_ratio"] is None
    one_bad = aggregate_seller_evidence(external_seller_id="id", listing_count=1, rows=artificial_rows(low=99, medium=0, high=1))
    assert one_bad["trust_level"] == "high"
    one_pair = aggregate_seller_evidence(external_seller_id="id", listing_count=1, rows=artificial_rows(low=98, medium=2, high=0))
    assert one_pair["trust_level"] == "high"
    assert clean["trust_score"] == 80


def make_listing(session: Session, first: ProductListing, *, seller_id: int | None):
    listing = ProductListing(
        platform_id=first.platform_id, product_variant_id=first.product_variant_id,
        seller_id=seller_id, external_id=unique("seller-trust-listing"),
        title="Sanitized Seller Trust Listing", product_url="https://priceoye.pk/test-seller-trust",
        current_price=Decimal("100000.00"), currency="PKR", review_count=0,
        is_available=True, raw_payload={},
    )
    session.add(listing)
    session.commit()
    return listing


def test_three_listing_ingestion_auto_analysis_persistence_api_and_staleness(client: TestClient, database_session: Session) -> None:
    product, first, seller = create_review_listing(database_session, platform_code="priceoye")
    # Marketplace rating, rating count, and verified-store status are not
    # authenticated inputs to v1 scoring.
    seller.rating = None
    seller.review_count = 0
    seller.is_verified = False
    database_session.commit()
    second = make_listing(database_session, first, seller_id=seller.id)
    third = make_listing(database_session, first, seller_id=seller.id)
    no_seller = make_listing(database_session, first, seller_id=None)
    auth = authenticated_headers(client)
    trust_url = f"/api/v1/sellers/{seller.id}/trust"
    assert client.get(trust_url).status_code == 401
    no_seller_result = client.get(f"/api/v1/products/{product.id}/listings/{no_seller.id}/seller-trust", headers=auth)
    assert no_seller_result.status_code == 200
    assert no_seller_result.json()["trust_score"] is None
    assert no_seller_result.json()["trust_level"] == "insufficient_data"

    texts = [
        "Battery life met my expectations during ordinary travel days.",
        "The display is easy to read and setup instructions were clear.",
        "Delivery arrived on time with secure packaging and no damage.",
        "Camera quality is reasonable indoors for the listed price range.",
        "The charger is compact enough to carry in my work bag.",
        "I tested the speakers and call quality over several afternoons.",
    ]
    for index, listing in enumerate((first, second, third)):
        batch = {
            "platform_code": "priceoye", "external_listing_id": listing.external_id,
            "source_url": "https://priceoye.pk/test-seller-trust",
            "reviews": [
                {
                    "external_review_id": f"trust-{listing.id}-{offset}",
                    "rating": 5 if (index * 2 + offset) % 2 == 0 else 4,
                    "review_text": texts[index * 2 + offset],
                    "reviewed_at": datetime(2026, 3, 1 + index * 2 + offset, tzinfo=timezone.utc).isoformat(),
                    "verified_purchase": False if index == 2 and offset == 1 else True,
                }
                for offset in range(2)
            ],
        }
        ingest = client.post("/api/v1/internal/acquisition/reviews", headers=ingestion_headers(), json=batch)
        assert ingest.status_code == 200, ingest.text
        assert ingest.json()["created_count"] == 2
    database_session.expire_all()
    saved = database_session.scalar(select(SellerTrustAnalysis).where(SellerTrustAnalysis.seller_id == seller.id))
    assert saved is not None
    assert saved.analysis_version == VERSION
    assert saved.trust_score == 84
    assert saved.trust_level == "high"
    assert saved.total_listings == 3
    assert saved.total_reviews == saved.analyzed_reviews == 6
    assert float(saved.analysis_coverage_percentage) == 100.0
    assert float(saved.verified_purchase_ratio) == 83.33
    assert saved.confidence_score == 60
    assert saved.confidence_level == "low"
    assert saved.created_at and saved.updated_at and saved.analyzed_at
    assert saved.signals["review_analysis_version"] == "review-risk-v1"
    assert saved.reasons

    read = client.get(trust_url, headers=auth)
    assert read.status_code == 200, read.text
    assert read.json()["trust_score"] == 84
    listing_read = client.get(f"/api/v1/products/{product.id}/listings/{first.id}/seller-trust", headers=auth)
    assert listing_read.status_code == 200
    assert listing_read.json()["seller_id"] == seller.id
    rerun = client.post(f"{trust_url}/recalculate", headers=auth)
    assert rerun.status_code == 200
    database_session.expire_all()
    assert database_session.scalar(select(func.count(SellerTrustAnalysis.id)).where(SellerTrustAnalysis.seller_id == seller.id)) == 1

    analyses = list(database_session.scalars(select(ReviewAnalysis).join(ReviewAnalysis.raw_review).where(ReviewAnalysis.raw_review.has(seller_id=seller.id)).limit(3)).all())
    for analysis in analyses:
        database_session.delete(analysis)
    database_session.commit()
    stale = client.get(trust_url, headers=auth)
    assert stale.status_code == 200
    assert stale.json()["trust_score"] is None
    partial = client.post(f"{trust_url}/recalculate", headers=auth)
    assert partial.status_code == 200
    assert partial.json()["analysis_coverage_percentage"] == 50.0
    assert partial.json()["trust_level"] == "insufficient_data"


def test_database_score_constraint_and_version_uniqueness(client: TestClient, database_session: Session) -> None:
    _product, _listing, seller = create_review_listing(database_session)
    auth = authenticated_headers(client)
    url = f"/api/v1/sellers/{seller.id}/trust/recalculate"
    assert client.post(url, headers=auth).status_code == 200
    assert client.post(url, headers=auth).status_code == 200
    database_session.expire_all()
    saved = database_session.scalar(select(SellerTrustAnalysis).where(SellerTrustAnalysis.seller_id == seller.id))
    assert saved is not None
    assert saved.trust_score is None
    assert saved.trust_level == "insufficient_data"
    assert database_session.scalar(select(func.count(SellerTrustAnalysis.id)).where(SellerTrustAnalysis.seller_id == seller.id)) == 1
    with pytest.raises(IntegrityError):
        database_session.execute(update(SellerTrustAnalysis).where(SellerTrustAnalysis.id == saved.id).values(trust_score=101, trust_level="high"))
        database_session.commit()
    database_session.rollback()
