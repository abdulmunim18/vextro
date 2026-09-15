"""Pure seller-trust-v1 aggregation over persisted review-risk results."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from statistics import pvariance

from app.models.raw_review import RawReview
from app.models.review_analysis import ReviewAnalysis
from app.services.review_risk_engine import VERSION as REVIEW_VERSION


VERSION = "seller-trust-v1"
BASE_SCORE = 80
HIGH_RATE_PENALTY = 40
AVERAGE_RISK_PENALTY = 35
MAX_REVIEW_PENALTY = 60
VERIFIED_BONUS = 5
MIN_ANALYZED_REVIEWS = 5
MIN_ANALYSIS_COVERAGE = 0.60
MIN_VERIFIED_KNOWN = 5
MIN_VERIFIED_COVERAGE = 0.50
HIGH_TRUST_THRESHOLD = 75
MODERATE_TRUST_THRESHOLD = 60


def confidence(analyzed: int, coverage: float) -> tuple[int, str]:
    volume = 50 if analyzed >= 50 else 35 if analyzed >= 20 else 20 if analyzed >= 10 else 10 if analyzed >= 5 else 0
    score = min(100, volume + round(50 * coverage))
    level = "high" if score >= 90 else "medium" if score >= 70 else "low"
    return score, level


def evidence_signature(external_seller_id: str | None, listing_count: int, rows: list[tuple[RawReview, ReviewAnalysis | None]]) -> str:
    """Detect stale persisted results even when review counts are unchanged."""
    payload = {
        "external_seller_id": external_seller_id,
        "listing_count": listing_count,
        "reviews": [
            [
                review.id, review.rating, review.verified_purchase,
                analysis.suspicion_score if analysis else None,
                analysis.suspicion_level if analysis else None,
                analysis.analyzed_at.isoformat() if analysis and getattr(analysis, "analyzed_at", None) else None,
            ]
            for review, analysis in rows
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def aggregate_seller_evidence(
    *, external_seller_id: str | None, listing_count: int,
    rows: list[tuple[RawReview, ReviewAnalysis | None]],
) -> dict[str, object]:
    total = len(rows)
    analyzed = [(review, analysis) for review, analysis in rows if analysis is not None]
    count = len(analyzed)
    coverage = count / total if total else 0.0
    confidence_score, confidence_level = confidence(count, coverage)
    levels = Counter(analysis.suspicion_level for _, analysis in analyzed)
    high_rate = levels["high"] / count if count else 0.0
    average_risk = sum(analysis.suspicion_score for _, analysis in analyzed) / count if count else None
    exact_count = sum(analysis.is_exact_duplicate for _, analysis in analyzed)
    near_count = sum(analysis.is_near_duplicate for _, analysis in analyzed)
    known_purchase = [review.verified_purchase for review, _ in rows if review.verified_purchase is not None]
    verified_ratio = sum(known_purchase) / len(known_purchase) if known_purchase else None
    rating_values = [review.rating for review, _ in rows]
    rating_average = sum(rating_values) / total if total else None
    rating_variance = pvariance(rating_values) if total else None
    ratings = Counter(rating_values)

    insufficient_reason = (
        "Stable marketplace seller identity is not available; name-only associations are not scored."
        if not external_seller_id else
        "No consistently seller-linked reviews are available."
        if total == 0 else
        f"Only {count} reviews have persisted {REVIEW_VERSION} analysis; at least {MIN_ANALYZED_REVIEWS} are required."
        if count < MIN_ANALYZED_REVIEWS else
        f"Only {round(coverage * 100, 1)}% of seller-linked reviews have persisted {REVIEW_VERSION} analysis; at least {round(MIN_ANALYSIS_COVERAGE * 100)}% coverage is required."
        if coverage < MIN_ANALYSIS_COVERAGE else None
    )
    weighted: dict[str, float] = {}
    reasons: list[str]
    if insufficient_reason:
        score = None
        level = "insufficient_data"
        reasons = [insufficient_reason]
    else:
        assert average_risk is not None
        high_penalty = HIGH_RATE_PENALTY * high_rate
        average_penalty = AVERAGE_RISK_PENALTY * average_risk / 100
        combined_penalty = min(MAX_REVIEW_PENALTY, high_penalty + average_penalty)
        weighted = {
            "base_score": BASE_SCORE,
            "high_suspicion_rate_penalty": round(-high_penalty, 2),
            "average_suspicion_penalty": round(-average_penalty, 2),
            "combined_review_penalty_cap": MAX_REVIEW_PENALTY,
        }
        bonus = 0.0
        if len(known_purchase) >= MIN_VERIFIED_KNOWN and len(known_purchase) / total >= MIN_VERIFIED_COVERAGE:
            bonus = VERIFIED_BONUS * (verified_ratio or 0)
            weighted["verified_purchase_bonus"] = round(bonus, 2)
        score = max(0, min(100, round(BASE_SCORE - combined_penalty + bonus)))
        level = "high" if score >= HIGH_TRUST_THRESHOLD else "moderate" if score >= MODERATE_TRUST_THRESHOLD else "low"
        reasons = [
            f"{levels['high']} of {count} analyzed reviews ({round(high_rate * 100, 1)}%) have high suspicion under {REVIEW_VERSION}.",
            f"Average persisted review suspicion is {round(average_risk, 1)}/100.",
            f"Evidence covers {count} of {total} seller-linked reviews across {listing_count} current listing(s); confidence is {confidence_level}.",
        ]
        if exact_count or near_count:
            reasons.append(f"{exact_count} analyzed reviews have exact-text duplication and {near_count} have strong near-duplicate wording (already included in review-risk scores).")
        if bonus:
            reasons.append(f"{round((verified_ratio or 0) * 100, 1)}% of {len(known_purchase)} reviews with known purchase status are verified; a limited bonus applies.")
        elif not known_purchase:
            reasons.append("Purchase verification status is unknown; no bonus or penalty applies.")
        else:
            reasons.append("Available purchase-verification evidence is too sparse for a scoring bonus; no penalty applies.")
    return {
        "analysis_version": VERSION,
        "trust_score": score, "trust_level": level,
        "confidence_score": confidence_score, "confidence_level": confidence_level,
        "total_listings": listing_count, "total_reviews": total, "analyzed_reviews": count,
        "high_suspicion_review_count": levels["high"],
        "medium_suspicion_review_count": levels["medium"],
        "low_suspicion_review_count": levels["low"],
        "analysis_coverage_percentage": round(coverage * 100, 2),
        "high_suspicion_percentage": round(high_rate * 100, 2),
        "average_review_suspicion_score": round(average_risk, 2) if average_risk is not None else None,
        "verified_purchase_ratio": round(verified_ratio * 100, 2) if verified_ratio is not None else None,
        "rating_average": round(rating_average, 2) if rating_average is not None else None,
        "rating_variance": round(rating_variance, 3) if rating_variance is not None else None,
        "signals": {
            "review_analysis_version": REVIEW_VERSION,
            "evidence_signature": evidence_signature(external_seller_id, listing_count, rows),
            "exact_duplicate_review_count": exact_count,
            "near_duplicate_review_count": near_count,
            "known_purchase_status_count": len(known_purchase),
            "verified_purchase_count": sum(known_purchase),
            "rating_distribution": {str(rating): ratings[rating] for rating in range(1, 6)},
            "score_components": weighted,
        },
        "reasons": reasons,
    }
