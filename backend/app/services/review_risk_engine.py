"""Deterministic review-risk v1 feature extraction and explainable scoring.

Scores describe suspicious characteristics, never proof of review fraud.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import re
import unicodedata

from app.models.raw_review import RawReview


VERSION = "review-risk-v1"
WEIGHTS = {
    "exact_duplicate": 40,
    "strong_near_duplicate": 25,
    "moderate_similarity": 12,
    "rating_text_conflict": 15,
    "similar_review_burst": 15,
    "repeated_reviewer_wording": 10,
    "short_extreme_rating": 3,
    "excessive_formatting": 4,
    "extreme_rating_context": 3,
    "verified_purchase": -10,
}
LEVEL_THRESHOLDS = {"medium": 30, "high": 60}
STRONG_SIMILARITY = 0.85
MODERATE_SIMILARITY = 0.75
MIN_COMPARABLE_CHARS = 20
MIN_COMPARABLE_WORDS = 4
BURST_WINDOW = timedelta(hours=24)
POSITIVE_WORDS = frozenset({"excellent", "amazing", "perfect", "fantastic", "great", "wonderful", "superb"})
NEGATIVE_WORDS = frozenset({"terrible", "awful", "useless", "broken", "horrible", "worst", "defective"})
NEGATIONS = frozenset({"not", "never", "no"})


def normalize_comparison_text(value: str | None) -> str:
    """Unicode/case/space normalization, without changing stored evidence."""
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def similarity_text(value: str | None) -> str:
    normalized = normalize_comparison_text(value)
    return " ".join(
        "".join(" " if unicodedata.category(char).startswith("P") else char for char in normalized).split()
    )


def comparable(value: str) -> bool:
    return len(value) >= MIN_COMPARABLE_CHARS and len(value.split()) >= MIN_COMPARABLE_WORDS


def ngrams(value: str) -> set[str]:
    return {value[index:index + 3] for index in range(len(value) - 2)}


def text_similarity(left: str | None, right: str | None) -> float:
    a, b = similarity_text(left), similarity_text(right)
    if not comparable(a) or not comparable(b):
        return 0.0
    if a == b:
        return 1.0
    a_grams, b_grams = ngrams(a), ngrams(b)
    return 2 * len(a_grams & b_grams) / (len(a_grams) + len(b_grams))


def polarity_conflict(rating: int, text: str | None) -> bool:
    if rating not in (1, 2, 4, 5) or not text:
        return False
    words = re.findall(r"[a-z]+", normalize_comparison_text(text))
    positive = 0
    negative = 0
    for index, word in enumerate(words):
        if word not in POSITIVE_WORDS | NEGATIVE_WORDS:
            continue
        if any(token in NEGATIONS for token in words[max(0, index - 2):index]):
            continue
        positive += word in POSITIVE_WORDS
        negative += word in NEGATIVE_WORDS
    return (rating <= 2 and positive >= 2 and negative == 0) or (rating >= 4 and negative >= 2 and positive == 0)


def formatting_anomaly(text: str | None) -> bool:
    if not text:
        return False
    letters = [char for char in text if char.isalpha()]
    upper_ratio = sum(char.isupper() for char in letters) / len(letters) if letters else 0
    repeated_punctuation = bool(re.search(r"[!?]{4,}", text))
    words = re.findall(r"\w+", normalize_comparison_text(text))
    repeated_word = any(words[index] == words[index + 1] == words[index + 2] for index in range(len(words) - 2))
    return (len(letters) >= 12 and upper_ratio >= 0.8 and repeated_punctuation) or repeated_word


def analyze_review(review: RawReview, peers: list[RawReview]) -> dict[str, object]:
    """Analyze one review against reviews from its own marketplace listing."""
    normalized = normalize_comparison_text(review.review_text)
    words = normalized.split()
    comparisons: list[tuple[RawReview, float, bool]] = []
    for peer in peers:
        if peer.id == review.id:
            continue
        peer_normalized = normalize_comparison_text(peer.review_text)
        exact = comparable(similarity_text(review.review_text)) and normalized == peer_normalized
        similarity = text_similarity(review.review_text, peer.review_text)
        if similarity >= MODERATE_SIMILARITY:
            comparisons.append((peer, similarity, exact))

    maximum_similarity = max((score for _, score, _ in comparisons), default=0.0)
    exact_count = sum(exact for _, _, exact in comparisons)
    strong_count = sum(score >= STRONG_SIMILARITY for _, score, _ in comparisons)
    burst_count = 0
    if review.reviewed_at is not None:
        burst_count = sum(
            score >= STRONG_SIMILARITY
            and peer.reviewed_at is not None
            and abs(peer.reviewed_at - review.reviewed_at) <= BURST_WINDOW
            for peer, score, _ in comparisons
        )
    repeated_reviewer = bool(review.reviewer_external_id) and any(
        score >= STRONG_SIMILARITY
        and peer.reviewer_external_id == review.reviewer_external_id
        for peer, score, _ in comparisons
    )
    rating_conflict = polarity_conflict(review.rating, review.review_text)
    short_extreme = len(words) <= 2 and review.rating in (1, 5) and bool(words)
    formatting = formatting_anomaly(review.review_text)
    ratings = Counter(peer.rating for peer in peers)
    extreme_context = (
        len(peers) >= 10
        and max(ratings[1], ratings[5]) / len(peers) >= 0.9
        and maximum_similarity >= MODERATE_SIMILARITY
    )

    weighted: dict[str, int] = {}
    reasons: list[str] = []
    if exact_count:
        weighted["exact_duplicate"] = WEIGHTS["exact_duplicate"]
        reasons.append(f"Normalized review text exactly matches {exact_count} other listing review(s).")
    elif maximum_similarity >= STRONG_SIMILARITY:
        weighted["strong_near_duplicate"] = WEIGHTS["strong_near_duplicate"]
        reasons.append(f"Review text is {round(maximum_similarity * 100)}% similar to another listing review.")
    elif maximum_similarity >= MODERATE_SIMILARITY:
        weighted["moderate_similarity"] = WEIGHTS["moderate_similarity"]
        reasons.append(f"Review text has moderate similarity ({round(maximum_similarity * 100)}%) to another listing review.")
    if rating_conflict:
        weighted["rating_text_conflict"] = WEIGHTS["rating_text_conflict"]
        reasons.append("Rating conflicts with multiple unnegated words in the limited text-polarity lexicon.")
    if burst_count >= 2:
        weighted["similar_review_burst"] = WEIGHTS["similar_review_burst"]
        reasons.append(f"At least {burst_count + 1} strongly similar reviews have timestamps within 24 hours.")
    if repeated_reviewer:
        weighted["repeated_reviewer_wording"] = WEIGHTS["repeated_reviewer_wording"]
        reasons.append("The same marketplace reviewer ID occurs with strongly similar wording on this listing.")
    if short_extreme:
        weighted["short_extreme_rating"] = WEIGHTS["short_extreme_rating"]
        reasons.append("An extreme rating has only one or two words of supporting text (weak signal).")
    if formatting:
        weighted["excessive_formatting"] = WEIGHTS["excessive_formatting"]
        reasons.append("Review contains repeated wording or unusually emphatic capitalization and punctuation (weak signal).")
    if extreme_context:
        weighted["extreme_rating_context"] = WEIGHTS["extreme_rating_context"]
        reasons.append("Listing rating distribution is highly concentrated alongside similar wording (weak context).")
    if review.verified_purchase is True:
        weighted["verified_purchase"] = WEIGHTS["verified_purchase"]
        reasons.append("Marketplace reports verified purchase; suspicion score reduced.")
    if not reasons:
        reasons.append("No configured suspicious-review pattern was detected from available evidence.")

    score = max(0, min(100, sum(weighted.values())))
    level = "high" if score >= LEVEL_THRESHOLDS["high"] else "medium" if score >= LEVEL_THRESHOLDS["medium"] else "low"
    return {
        "analysis_version": VERSION,
        "suspicion_score": score,
        "suspicion_level": level,
        "duplicate_similarity_score": round(maximum_similarity * 100),
        "text_anomaly_score": weighted.get("short_extreme_rating", 0) + weighted.get("excessive_formatting", 0),
        "rating_anomaly_score": weighted.get("rating_text_conflict", 0) + weighted.get("extreme_rating_context", 0),
        "temporal_anomaly_score": weighted.get("similar_review_burst", 0),
        "reviewer_anomaly_score": weighted.get("repeated_reviewer_wording", 0),
        "is_exact_duplicate": exact_count > 0,
        "is_near_duplicate": exact_count == 0 and maximum_similarity >= STRONG_SIMILARITY,
        "signals": {
            "character_count": len(normalized), "word_count": len(words),
            "exact_match_count": exact_count, "strong_similarity_count": strong_count,
            "similar_burst_peer_count": burst_count, "listing_review_count": len(peers),
            "listing_rating_distribution": {str(rating): ratings[rating] for rating in range(1, 6)},
            "verified_purchase": review.verified_purchase,
            "applied_weights": weighted,
        },
        "reasons": reasons,
    }
