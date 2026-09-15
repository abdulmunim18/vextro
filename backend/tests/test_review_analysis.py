import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review_analysis import ReviewAnalysis
from app.core.config import settings
from app.services.review_analysis_service import ReviewAnalysisService
from app.services.review_risk_engine import VERSION, analyze_review, normalize_comparison_text, text_similarity
from tests.test_reviews import TEST_INGESTION_KEY, authenticated_headers, create_review_listing, ingestion_headers


FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "review_risk_scenarios.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def configure_review_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ingestion_api_key", TEST_INGESTION_KEY)


def evidence(identifier: int, text: str | None, *, rating: int = 5, at: datetime | None = None, reviewer: str | None = None, verified: bool | None = None):
    return SimpleNamespace(id=identifier, review_text=text, rating=rating, reviewed_at=at, reviewer_external_id=reviewer, verified_purchase=verified)


def test_similarity_normalizes_unicode_case_and_spacing_without_changing_source() -> None:
    source = " ＥxCeLlEnT  phone\u00a0Battery timing is very good. "
    assert normalize_comparison_text(source) == "excellent phone battery timing is very good."
    assert text_similarity(FIXTURES["near_duplicate"][0], FIXTURES["near_duplicate"][1]) >= 0.85
    assert text_similarity(FIXTURES["normal"][0], FIXTURES["normal"][1]) < 0.75
    assert text_similarity("Good", "good") == 0


def test_exact_duplicate_across_distinct_reviews_and_verified_reduction() -> None:
    text = "Excellent product highly recommended for the battery life."
    plain = evidence(1, text)
    verified = evidence(2, "  EXCELLENT  product highly recommended for the battery life. ", verified=True)
    first = analyze_review(plain, [plain, verified])
    second = analyze_review(verified, [plain, verified])
    assert first["is_exact_duplicate"] is True
    assert first["suspicion_score"] == 40
    assert second["suspicion_score"] == 30
    assert second["signals"]["applied_weights"]["verified_purchase"] == -10


def test_rating_text_conflict_and_negation_guard() -> None:
    mismatch = evidence(1, FIXTURES["mismatch"][0], rating=1)
    result = analyze_review(mismatch, [mismatch])
    assert result["rating_anomaly_score"] == 15
    assert result["suspicion_level"] == "low"
    negated = evidence(2, "Not excellent and never perfect in actual daily use.", rating=1)
    assert analyze_review(negated, [negated])["rating_anomaly_score"] == 0


def test_false_positive_guards_and_missing_optional_fields() -> None:
    short = evidence(1, "Good", rating=5)
    assert analyze_review(short, [short])["suspicion_score"] == 3
    normal = evidence(2, FIXTURES["normal"][0], rating=5)
    assert analyze_review(normal, [normal])["suspicion_score"] == 0
    no_text = evidence(3, None, rating=5)
    assert analyze_review(no_text, [no_text])["suspicion_score"] == 0
    at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    same_day = [evidence(index, value, at=at + timedelta(hours=index)) for index, value in enumerate(FIXTURES["normal"], 1)]
    assert all(analyze_review(review, same_day)["temporal_anomaly_score"] == 0 for review in same_day)
    assert all(analyze_review(review, same_day)["suspicion_level"] == "low" for review in same_day)


def test_similarity_burst_and_reviewer_id_need_real_evidence() -> None:
    at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    peers = [evidence(index, text, at=at + timedelta(hours=index), reviewer="same-id") for index, text in enumerate(FIXTURES["near_duplicate"], 1)]
    result = analyze_review(peers[0], peers)
    assert result["temporal_anomaly_score"] == 15
    assert result["reviewer_anomaly_score"] == 10
    assert result["suspicion_level"] in ("medium", "high")
    anonymous = [evidence(index, text, at=at + timedelta(hours=index)) for index, text in enumerate(FIXTURES["near_duplicate"], 1)]
    assert analyze_review(anonymous[0], anonymous)["reviewer_anomaly_score"] == 0


def test_combined_evidence_reaches_high_without_fraud_claim() -> None:
    at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    text = "Excellent product absolutely perfect for my daily use."
    peers = [
        evidence(index, text, rating=1, at=at + timedelta(hours=index), reviewer="marketplace-buyer-7")
        for index in range(3)
    ]
    result = analyze_review(peers[0], peers)
    assert result["suspicion_score"] == 80
    assert result["suspicion_level"] == "high"
    assert result["is_exact_duplicate"] is True
    assert result["temporal_anomaly_score"] == 15
    assert result["reviewer_anomaly_score"] == 10
    assert all("fake" not in reason.casefold() for reason in result["reasons"])


def test_database_ingestion_persistence_idempotency_and_aggregate_api(client: TestClient, database_session: Session) -> None:
    product, listing, _seller = create_review_listing(database_session, platform_code="priceoye")
    at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    texts = FIXTURES["near_duplicate"] + FIXTURES["mismatch"] + FIXTURES["normal"]
    payload = {
        "platform_code": "priceoye", "external_listing_id": listing.external_id,
        "source_url": "https://priceoye.pk/test-review-listing",
        "reviews": [
            {
                "external_review_id": f"risk-{index}-{listing.id}",
                "rating": (1 if index == 3 else 5 if index == 4 else 4),
                "review_text": text,
                "reviewed_at": (at + timedelta(hours=index)).isoformat(),
                "verified_purchase": True if index == 5 else None,
            }
            for index, text in enumerate(texts)
        ],
    }
    post = client.post("/api/v1/internal/acquisition/reviews", headers=ingestion_headers(), json=payload)
    assert post.status_code == 200, post.text
    assert post.json()["created_count"] == 10
    auth = authenticated_headers(client)
    summary_url = f"/api/v1/products/{product.id}/review-analysis"
    assert client.get(summary_url).status_code == 401
    first = client.get(summary_url, headers=auth, params={"listing_id": listing.id})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["analysis_version"] == VERSION
    assert body["total_reviews"] == body["analyzed_reviews"] == 10
    assert (body["low"], body["medium"], body["high"]) == (7, 3, 0)
    assert body["near_duplicate_count"] == 3
    assert body["average_suspicion_score"] == 15.0
    assert sum(item["rating_anomaly_score"] == 15 for item in body["reviews"]) == 2
    assert all(0 <= item["suspicion_score"] <= 100 for item in body["reviews"])
    assert all(item["reasons"] for item in body["reviews"])
    one = body["reviews"][0]
    individual = client.get(
        f"/api/v1/products/{product.id}/reviews/{one['review_id']}/analysis",
        headers=auth,
    )
    assert individual.status_code == 200
    assert individual.json()["suspicion_score"] == one["suspicion_score"]
    database_session.expire_all()
    listing_analysis_count = select(func.count(ReviewAnalysis.id)).where(
        ReviewAnalysis.raw_review.has(product_listing_id=listing.id)
    )
    assert database_session.scalar(listing_analysis_count) == 10

    again = client.post("/api/v1/internal/acquisition/reviews", headers=ingestion_headers(), json=payload)
    assert again.status_code == 200
    assert again.json()["duplicate_count"] == 10
    rerun = client.post(f"{summary_url}/run", headers=auth, params={"listing_id": listing.id})
    assert rerun.status_code == 200, rerun.text
    database_session.expire_all()
    assert database_session.scalar(listing_analysis_count) == 10
    assert rerun.json()["analyzed_reviews"] == 10
    ReviewAnalysisService().analyze_one(database_session, one["review_id"])
    database_session.commit()
    assert database_session.scalar(listing_analysis_count) == 10


def test_analysis_listing_scope_cannot_be_crossed(client: TestClient, database_session: Session) -> None:
    product, _listing, _seller = create_review_listing(database_session)
    _other_product, other_listing, _other_seller = create_review_listing(database_session, platform_code="priceoye")
    auth = authenticated_headers(client)
    path = f"/api/v1/products/{product.id}/review-analysis"
    assert client.get(path, headers=auth, params={"listing_id": other_listing.id}).status_code == 404
    assert client.post(f"{path}/run", headers=auth, params={"listing_id": other_listing.id}).status_code == 404
