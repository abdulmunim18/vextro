"""Deterministic opinion-risk v1: is a guide-site post a view of the phone?

A guide site's comment box is open to anyone, and much of what lands in it
is not about the phone at all: people selling their own handset, asking to
buy one, or pasting the same line repeatedly. The score says how little a
post can be trusted as an opinion of the phone. It describes the post, never
its author, and is not proof of anything.

Marketplace reviews are scored by ``review_risk_engine``; its text
comparison is reused here, but its rating and verified-purchase signals do
not exist for a post that carries neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from app.services.review_risk_engine import (
    MODERATE_SIMILARITY,
    STRONG_SIMILARITY,
    comparable,
    formatting_anomaly,
    normalize_comparison_text,
    similarity_text,
    text_similarity,
)


VERSION = "opinion-risk-v1"
WEIGHTS = {
    "contact_number_shared": 35,
    "trade_offer": 35,
    "used_phone_pitch": 10,
    "exact_duplicate": 40,
    "strong_near_duplicate": 25,
    "moderate_similarity": 12,
    "similar_post_burst": 15,
    "repeated_author_wording": 10,
    "abusive_language": 30,
    "excessive_formatting": 4,
    "too_short_to_judge": 3,
}
LEVEL_THRESHOLDS = {"medium": 30, "high": 60}
BURST_WINDOW = timedelta(hours=24)

KIND_ADVERT = "advert"
KIND_QUESTION = "question"
KIND_OPINION = "opinion"
KIND_ABUSIVE = "abusive"

# A visitor offering to sell, swap or source a handset, in the English and
# Roman Urdu spellings people use. "buy" alone is left out: "I want to buy
# this when it launches" is an ordinary remark about the phone.
TRADE_OFFER = re.compile(
    r"""
      \bwants?\s+t[ou]\s+(?:sell|sale|exchange)\b        # I want to sale
    | \b(?:sell|sale|seal|sel|exchange)\s+k[ae]?rn[aiey]\b  # sale krna, seal karna
    | \bfor\s*sale\b                                      # for sale, forsale
    | \bselling\b                                         # I am selling my
    | \b(?:sell|sale)\s+(?:now|this|my|it|urgently)\b
    | \bmobile\s+(?:sell|sale)\b
    | \b(?:pin|box|daba)\s*pack\s+available\b
    | \bcontact\s+(?:me|kr|kar|karo|karen|plz|please)\b
    | \brabta\s+k[aeiy]                                   # rabta kre, rabta kijye
    | \b(?:mujh|mojh)\s*s[ey]\s+(?:contact|rabta)\b
    | \bwh?ats?\s*'?app\s+(?:only|number|no|par|per)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# How a second-hand handset is described to a buyer.
USED_PHONE_PITCH = re.compile(
    r"""
      \b10\s*/\s*10\b
    | \bpta\s+approved\b
    | \bfull\s+box\b
    | \b(?:pin|box|daba)\s*pack\b
    | \bnon\s*e?\s*ac+tive\b
    | \b(?:days?|weeks?|months?|mah|mha|manth)\s+(?:use|used|usd|uez)\b
    | \bunder\s+warranty\b
    | \bwarranty\b.{0,30}\bremaining\b
    | \bbrand\s+new\b
    | \bserious\s+(?:person|buyer)s?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Someone asking rather than telling: availability, or how the phone performs.
QUESTION = re.compile(
    r"""
      \?\s*$
    | \bk[au]?b\s+(?:tak|tk|aye|ay|a|i|l[ao]?unch|mil)\b     # kab aye ga, kb tak
    | \bwhen\s+(?:will|it|is)\b
    | \bkoi\s+(?:bata|bta)
    | \b(?:bata|bta)\s*(?:de|den|do|dy|sakta|skta)\b
    | \b(?:bataen|btaen|btay)\b
    | \bkes[ia]\s+h[aey]i?\b|\bkais[ia]\s+h[aey]i?\b      # kesi hai, kaisa ha
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Insults aimed at a person. Harsh words about the phone itself ("bakwas",
# "ghatya") are opinions and are deliberately not listed.
ABUSIVE_LANGUAGE = re.compile(
    r"""
      \billegal\s+(?:father|son|child)\b
    | \bharam(?:i|zad[aey]|khor)\b
    | \bkutt[aey]\b
    | \bkamin[aey]\b
    | \bb[ae]ghairat\b
    | \bbastards?\b
    | \bbitch(?:es)?\b
    | \bassholes?\b
    | \bfuck\w*
    | \b(?:bhen|behn|madar)\s*chod\w*
    | \bchutiy[aeo]\w*
    | \bgand[ou]\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class OpinionEvidence:
    """What the scorer is told about one post."""

    id: int
    text: str
    author: str | None = None
    posted_at: datetime | None = None
    contact_removed: bool = False


def classify(
    text: str,
    *,
    trade_offer: bool,
    contact_removed: bool,
    abusive: bool = False,
) -> str:
    """Name what a post is: abuse, an advert, a question or an opinion."""

    if abusive:
        return KIND_ABUSIVE

    if trade_offer or contact_removed:
        return KIND_ADVERT

    if QUESTION.search(text):
        return KIND_QUESTION

    return KIND_OPINION


def analyze_opinion(
    opinion: OpinionEvidence,
    peers: list[OpinionEvidence],
) -> dict[str, object]:
    """Score one post against the other posts about the same phone."""

    normalized = normalize_comparison_text(opinion.text)
    words = normalized.split()
    author = normalize_comparison_text(opinion.author)

    trade_offer = bool(TRADE_OFFER.search(normalized))
    used_phone_pitch = bool(USED_PHONE_PITCH.search(normalized))
    abusive = bool(ABUSIVE_LANGUAGE.search(normalized))

    comparisons: list[tuple[OpinionEvidence, float, bool]] = []
    for peer in peers:
        if peer.id == opinion.id:
            continue
        similarity = text_similarity(opinion.text, peer.text)
        if similarity < MODERATE_SIMILARITY:
            continue
        exact = (
            comparable(similarity_text(opinion.text))
            and normalized == normalize_comparison_text(peer.text)
        )
        comparisons.append((peer, similarity, exact))

    maximum_similarity = max((score for _, score, _ in comparisons), default=0.0)
    exact_count = sum(exact for _, _, exact in comparisons)
    burst_count = 0
    if opinion.posted_at is not None:
        burst_count = sum(
            score >= STRONG_SIMILARITY
            and peer.posted_at is not None
            and abs(peer.posted_at - opinion.posted_at) <= BURST_WINDOW
            for peer, score, _ in comparisons
        )
    repeated_author = bool(author) and any(
        score >= STRONG_SIMILARITY
        and normalize_comparison_text(peer.author) == author
        for peer, score, _ in comparisons
    )

    weighted: dict[str, int] = {}
    reasons: list[str] = []

    if opinion.contact_removed:
        weighted["contact_number_shared"] = WEIGHTS["contact_number_shared"]
        reasons.append(
            "The post gave a phone number to be contacted on (removed before storing)."
        )
    if trade_offer:
        weighted["trade_offer"] = WEIGHTS["trade_offer"]
        reasons.append(
            "The wording offers to sell, swap or source a handset rather than describe the phone."
        )
    if used_phone_pitch:
        weighted["used_phone_pitch"] = WEIGHTS["used_phone_pitch"]
        reasons.append(
            "It describes a second-hand handset the way a seller would (condition, box, warranty left)."
        )
    if abusive:
        weighted["abusive_language"] = WEIGHTS["abusive_language"]
        reasons.append("It insults a person instead of describing the phone.")
    if exact_count:
        weighted["exact_duplicate"] = WEIGHTS["exact_duplicate"]
        reasons.append(
            f"The same text appears in {exact_count} other post(s) about this phone."
        )
    elif maximum_similarity >= STRONG_SIMILARITY:
        weighted["strong_near_duplicate"] = WEIGHTS["strong_near_duplicate"]
        reasons.append(
            f"The text is {round(maximum_similarity * 100)}% similar to another post about this phone."
        )
    elif maximum_similarity >= MODERATE_SIMILARITY:
        weighted["moderate_similarity"] = WEIGHTS["moderate_similarity"]
        reasons.append(
            f"The text has moderate similarity ({round(maximum_similarity * 100)}%) to another post about this phone."
        )
    if burst_count >= 2:
        weighted["similar_post_burst"] = WEIGHTS["similar_post_burst"]
        reasons.append(
            f"At least {burst_count + 1} strongly similar posts were made within 24 hours."
        )
    if repeated_author:
        weighted["repeated_author_wording"] = WEIGHTS["repeated_author_wording"]
        reasons.append(
            "The same display name posted strongly similar wording about this phone."
        )
    if formatting_anomaly(opinion.text):
        weighted["excessive_formatting"] = WEIGHTS["excessive_formatting"]
        reasons.append(
            "Repeated wording or unusually emphatic capitals and punctuation (weak signal)."
        )
    if 0 < len(words) <= 2:
        weighted["too_short_to_judge"] = WEIGHTS["too_short_to_judge"]
        reasons.append("One or two words say little about the phone (weak signal).")
    if not reasons:
        reasons.append("No configured pattern was found; it reads as a view of the phone.")

    score = max(0, min(100, sum(weighted.values())))
    level = (
        "high"
        if score >= LEVEL_THRESHOLDS["high"]
        else "medium"
        if score >= LEVEL_THRESHOLDS["medium"]
        else "low"
    )

    return {
        "analysis_version": VERSION,
        "suspicion_score": score,
        "suspicion_level": level,
        "opinion_kind": classify(
            normalized,
            trade_offer=trade_offer,
            contact_removed=opinion.contact_removed,
            abusive=abusive,
        ),
        "applied_weights": weighted,
        "reasons": reasons,
    }


__all__ = [
    "KIND_ABUSIVE",
    "KIND_ADVERT",
    "KIND_OPINION",
    "KIND_QUESTION",
    "LEVEL_THRESHOLDS",
    "OpinionEvidence",
    "VERSION",
    "WEIGHTS",
    "analyze_opinion",
    "classify",
]
