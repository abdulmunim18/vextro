import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.repositories.product_matching_repository import (
    ProductMatchCandidate,
    ProductMatchingRepository,
)
from app.schemas.product_matching import (
    ProductMatchRequest,
    ProductMatchResponse,
)
from app.services.cross_marketplace_matching import (
    cross_marketplace_product_key,
    normalized_product_identity,
)
from app.services.smartphone_normalization import (
    clean_marketplace_title,
    extract_memory_capacities,
    normalize_color,
)


MATCH_THRESHOLD = 75
AMBIGUITY_MARGIN = 8

MIN_NAME_IDENTITY_SCORE = 0.65
MIN_MODEL_IDENTITY_SCORE = 0.90

# Matching tiers. Only EXACT and HIGH are safe to attach automatically;
# MEDIUM and LOW are routed to the pending-match queue for an administrator.
TIER_EXACT = "EXACT"
TIER_HIGH = "HIGH"
TIER_MEDIUM = "MEDIUM"
TIER_LOW = "LOW"

HIGH_TIER_CONFIDENCE = 90

# Below this, two normalized brands are treated as genuinely different
# manufacturers and the candidate is eliminated rather than demoted.
MIN_BRAND_IDENTITY_SCORE = 0.85

# When both the marketplace title and the candidate variant carry a
# concrete colour, require this much fuzzy similarity before we treat
# them as the same variant. Below this the candidate is rejected the
# same way an incompatible RAM or storage does — otherwise a "Titan
# Blue" listing happily lands on a "Titan Red" variant of the same
# phone.
MIN_COLOR_IDENTITY_SCORE = 0.60


def _color_similarity(
    requested: str | None,
    candidate: str | None,
) -> float:
    """Return a colour-aware similarity in [0, 1].

    ``SequenceMatcher.ratio`` alone rates "Awesome Black" against
    "Black" at only ~0.56 because the character counts diverge, even
    though a human reads them as the same colour. Marketplaces emit
    exactly this pattern ("Awesome Pink", "Titanium Blue", "Phantom
    Black"), so we boost the score to 1.0 whenever one normalised
    string contains the other as a whole token, and fall back to the
    plain sequence ratio otherwise. Distinct hues like "Blue" vs
    "Red" stay well below the identity threshold and are rejected.
    """

    requested_normalised = _normalize_text(requested)
    candidate_normalised = _normalize_text(candidate)

    if not requested_normalised or not candidate_normalised:
        return 0.0

    if requested_normalised == candidate_normalised:
        return 1.0

    # A colour name is a hue plus marketing: "Awesome Black" is "Black",
    # but "Titanium Blue" is not "Titanium Black" and "Blue Black" is not
    # "Blue". Comparing characters rated those pairs ~0.8 alike and filed
    # every Titanium colour of a phone under one variant, so the words
    # that actually name the hue and its shade must agree exactly.
    requested_tokens = set(requested_normalised.split())
    candidate_tokens = set(candidate_normalised.split())
    requested_hues = _hue_tokens(requested_normalised)
    candidate_hues = _hue_tokens(candidate_normalised)

    if requested_hues and candidate_hues:
        if requested_hues != candidate_hues:
            return 0.0

        # The same hue under two different names ("Denim Blue" and
        # "Morning Blue") is two offers; one name merely adding marketing
        # to the other ("Awesome Black" and "Black") is one.
        requested_rest = requested_tokens - _HUE_SOURCE_WORDS
        candidate_rest = candidate_tokens - _HUE_SOURCE_WORDS

        return 1.0 if (
            requested_rest <= candidate_rest
            or candidate_rest <= requested_rest
        ) else 0.0

    # Names with no recognisable hue ("Sage", "Natural Titanium") are
    # only the same colour when they are the same name.
    return 0.0


_HUE_ALIASES = {"gray": "grey", "golden": "gold", "silvery": "silver"}

_HUE_WORDS = frozenset({
    # hues
    "black", "white", "blue", "red", "green", "gold", "silver", "grey",
    "pink", "purple", "yellow", "orange", "brown", "violet", "cyan",
    "beige", "cream", "bronze", "copper", "maroon", "teal", "turquoise",
    "navy", "indigo", "magenta", "olive", "lime", "mint", "peach",
    "coral", "rose", "lavender", "lilac", "graphite", "champagne",
    # shades that tell two offers of one phone apart
    "dark", "light", "deep", "sky", "midnight",
})


# Every spelling that states a hue, aliases included.
_HUE_SOURCE_WORDS = _HUE_WORDS | frozenset(_HUE_ALIASES)


def _hue_tokens(normalised_colour: str) -> frozenset[str]:
    """Return the words of a colour name that state its hue and shade."""

    return frozenset(
        _HUE_ALIASES.get(token, token)
        for token in normalised_colour.split()
        if _HUE_ALIASES.get(token, token) in _HUE_WORDS
    )

def _normalize_text(value: str | None) -> str:
    """Normalize text for case-insensitive product matching."""

    if not value:
        return ""

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = normalized.encode(
        "ascii",
        "ignore",
    ).decode("ascii")

    normalized = normalized.lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split(),
    )


def _compact_text(value: str | None) -> str:
    """Normalize text and remove spaces."""

    return _normalize_text(
        value,
    ).replace(" ", "")


def _text_similarity(
    first: str | None,
    second: str | None,
) -> float:
    """Return similarity between two normalized text values."""

    normalized_first = _normalize_text(first)
    normalized_second = _normalize_text(second)

    if (
        not normalized_first
        or not normalized_second
    ):
        return 0.0

    if normalized_first == normalized_second:
        return 1.0

    return SequenceMatcher(
        None,
        normalized_first,
        normalized_second,
    ).ratio()


def _name_similarity(
    title: str,
    product_name: str,
) -> float:
    """Compare marketplace title with canonical product name."""

    normalized_title = _normalize_text(title)
    normalized_name = _normalize_text(
        product_name,
    )

    if (
        not normalized_title
        or not normalized_name
    ):
        return 0.0

    sequence_score = SequenceMatcher(
        None,
        normalized_title,
        normalized_name,
    ).ratio()

    title_tokens = set(
        normalized_title.split(),
    )

    name_tokens = set(
        normalized_name.split(),
    )

    if not name_tokens:
        token_score = 0.0
    else:
        token_score = (
            len(
                title_tokens.intersection(
                    name_tokens,
                )
            )
            / len(name_tokens)
        )

    if normalized_name in normalized_title:
        containment_score = 1.0
    else:
        containment_score = 0.0

    return max(
        sequence_score,
        token_score,
        containment_score,
    )


def _extract_memory_values(
    title: str,
) -> tuple[int | None, int | None]:
    """Extract likely RAM and storage values from a title."""

    normalized_title = _normalize_text(
        title,
    )

    explicit_ram_match = re.search(
        r"\b(\d{1,3})\s*gb\s*ram\b",
        normalized_title,
    )

    explicit_storage_match = re.search(
        r"\b(\d{1,4})\s*gb\s*"
        r"(?:storage|rom)\b",
        normalized_title,
    )

    ram_gb = (
        int(explicit_ram_match.group(1))
        if explicit_ram_match
        else None
    )

    storage_gb = (
        int(explicit_storage_match.group(1))
        if explicit_storage_match
        else None
    )

    capacity_matches = re.findall(
        r"\b(\d{1,4})\s*(gb|tb)\b",
        normalized_title,
    )

    capacities: list[int] = []

    for value, unit in capacity_matches:
        capacity = int(value)

        if unit == "tb":
            capacity *= 1024

        if capacity not in capacities:
            capacities.append(capacity)

    if ram_gb is None:
        likely_ram_values = [
            value
            for value in capacities
            if value <= 32
        ]

        if likely_ram_values:
            ram_gb = likely_ram_values[0]

    if storage_gb is None:
        likely_storage_values = [
            value
            for value in capacities
            if value >= 32
            and value != ram_gb
        ]

        if likely_storage_values:
            storage_gb = likely_storage_values[0]

    return (
        ram_gb,
        storage_gb,
    )


def _detect_unique_text_value(
    title: str,
    values: list[str | None],
) -> str | None:
    """Detect one unique catalog value inside a scraped title."""

    compact_title = _compact_text(title)

    detected: list[str] = []

    for value in values:
        if not value:
            continue

        compact_value = _compact_text(
            value,
        )

        if (
            compact_value
            and compact_value in compact_title
        ):
            normalized_value = _normalize_text(
                value,
            )

            if normalized_value not in [
                _normalize_text(item)
                for item in detected
            ]:
                detected.append(value)

    if len(detected) == 1:
        return detected[0]

    return None


_MODEL_NUMBER_TOKEN = re.compile(r"\b(?=[a-z0-9]*\d)[a-z0-9]{2,}\b")


def _model_number_tokens(value: str | None) -> set[str]:
    """Return the model-code tokens in a product name or marketplace title.

    ``normalized_product_identity`` first strips capacities, network
    generations and marketing words, so what remains with a digit in it is a
    model code: ``a55`` from "Galaxy A55", ``x6851`` from "Infinix X6851",
    ``40`` from "Note 40".
    """

    identity = normalized_product_identity(value)

    return set(_MODEL_NUMBER_TOKEN.findall(identity))


def _model_numbers_conflict(
    title: str | None,
    candidate: ProductMatchCandidate,
) -> bool:
    """Report whether two model codes describe different phones.

    Title similarity alone happily rates "Galaxy A55" and "Galaxy A35" as the
    same product, because one character in thirty differs. Model codes are
    the part that actually identifies the phone, so a disagreement between
    them vetoes the match however well the rest of the text reads. A shorter
    code that prefixes a longer one ("A55" against the catalog's "A556E") is
    the same phone written at different precision, not a conflict.
    """

    requested = _model_number_tokens(title)
    known = _model_number_tokens(candidate.model) | _model_number_tokens(
        candidate.product_name
    )

    if not requested or not known:
        return False

    if requested & known:
        return False

    return not any(
        requested_token.startswith(known_token)
        or known_token.startswith(requested_token)
        for requested_token in requested
        for known_token in known
    )


# Words that turn one phone into a different, separately priced phone.
_MODEL_QUALIFIERS = frozenset({
    "pro", "max", "plus", "ultra", "air", "mini", "lite", "neo", "fe",
    "se", "xl", "edge", "prime", "turbo", "play", "zoom", "classic",
    "power", "music", "eco", "fold", "flip", "note", "go", "hd",
})


def _same_model_code(first: str, second: str) -> bool:
    """Report whether two model codes name the same phone.

    "A55" and the catalog's "A556E" are one phone written at different
    precision. A single trailing character is a different model, though:
    "17e" is not "17" and "Q150s" is not "Q150".
    """

    if first == second:
        return True

    shorter, longer = sorted((first, second), key=len)

    return longer.startswith(shorter) and len(longer) - len(shorter) >= 2


def _model_identity_conflict(
    title: str | None,
    candidate: ProductMatchCandidate,
) -> bool:
    """Report whether a title names a look-alike rather than this phone.

    Character similarity rates "iPhone 17 Pro" and "iPhone 17 Pro Max",
    "Z Fold 4" and "Z Fold 5" or "Epic" and "EpicX" as the same product,
    because a word or a digit in twenty differs. Those are different
    phones with different prices, so the words that tell models apart are
    compared as words.
    """

    title_tokens = set(
        cross_marketplace_product_key(title, candidate.brand_name).split()
    )
    name_tokens = set(
        cross_marketplace_product_key(
            candidate.product_name,
            candidate.brand_name,
        ).split()
    )

    if not title_tokens or not name_tokens:
        return False

    # 1. A qualifier present on one side only: "Pro" against "Pro Max".
    if (title_tokens ^ name_tokens) & _MODEL_QUALIFIERS:
        return True

    # 2. Numbers that disagree: "Fold 4" against "Fold 5". A number only
    # one side states (a battery size in a seller's title) decides nothing.
    title_numbers = {token for token in title_tokens if any(
        character.isdigit() for character in token
    )}
    name_numbers = {token for token in name_tokens if any(
        character.isdigit() for character in token
    )}
    unmatched_title = {
        token for token in title_numbers
        if not any(_same_model_code(token, other) for other in name_numbers)
    }
    unmatched_name = {
        token for token in name_numbers
        if not any(_same_model_code(token, other) for other in title_numbers)
    }

    if unmatched_title and unmatched_name:
        return True

    # 3. Two bare model names of the same length must be the same words:
    # "Epic" against "EpicX". A longer seller title is left to scoring.
    if len(title_tokens) == len(name_tokens):
        return bool(
            (title_tokens - title_numbers) ^ (name_tokens - name_numbers)
        )

    return False


@dataclass(frozen=True)
class _ScoredCandidate:
    """One catalog variant weighed against the scraped listing."""

    candidate: ProductMatchCandidate
    confidence: int
    name_score: float
    model_score: float
    confirmed_signals: int
    rejection_reason: str | None


def _confidence_tier(confidence: int) -> str:
    """Return the matching tier one confidence score belongs to."""

    if confidence >= 100:
        return TIER_EXACT

    if confidence >= HIGH_TIER_CONFIDENCE:
        return TIER_HIGH

    if confidence >= MATCH_THRESHOLD:
        return TIER_MEDIUM

    return TIER_LOW


def _ranking_key(item: _ScoredCandidate) -> tuple[int, int, float, float, int]:
    """Order candidates by confidence, then by confirmed hard signals.

    ``confirmed_signals`` breaks ties between variants of the same phone: the
    variant whose RAM, storage and colour were actually confirmed wins over a
    variant that merely failed to contradict the listing.
    """

    return (
        item.confidence,
        item.confirmed_signals,
        item.name_score,
        item.model_score,
        -item.candidate.product_variant_id,
    )


def _unmatched_response(
    item: _ScoredCandidate,
    reason: str,
) -> ProductMatchResponse:
    """Return an unmatched response that still suggests the best candidate."""

    return ProductMatchResponse(
        matched=False,
        confidence=item.confidence,
        match_tier=_confidence_tier(item.confidence),
        suggested_product_variant_id=(
            item.candidate.product_variant_id
        ),
        product_name=item.candidate.product_name,
        brand_name=item.candidate.brand_name,
        model=item.candidate.model,
        ram_gb=item.candidate.ram_gb,
        storage_gb=item.candidate.storage_gb,
        color=item.candidate.color,
        reason=reason,
    )


def _score_candidate(
    candidate: ProductMatchCandidate,
    *,
    title: str,
    requested_brand: str | None,
    requested_model: str | None,
    requested_ram: int | None,
    requested_storage: int | None,
    requested_color: str | None,
) -> _ScoredCandidate:
    """Weigh every available identity signal for one catalog variant."""

    score = 0.0
    possible_score = 35.0
    confirmed_signals = 0

    rejection_reason: str | None = None

    name_score = _name_similarity(title, candidate.product_name)
    score += name_score * 35.0

    model_score = 0.0

    if requested_brand:
        possible_score += 20.0

        brand_score = _text_similarity(
            requested_brand,
            candidate.brand_name,
        )
        score += brand_score * 20.0

        # A different manufacturer is never the same product, however well
        # the rest of the title happens to read.
        if (
            candidate.brand_name
            and brand_score < MIN_BRAND_IDENTITY_SCORE
        ):
            rejection_reason = (
                "The requested brand does not "
                "match this catalog product."
            )
        elif brand_score >= MIN_BRAND_IDENTITY_SCORE:
            confirmed_signals += 1

    if requested_model:
        possible_score += 20.0

        model_score = _text_similarity(
            requested_model,
            candidate.model,
        )
        score += model_score * 20.0

        if model_score >= MIN_MODEL_IDENTITY_SCORE:
            confirmed_signals += 1

    if requested_ram is not None:
        possible_score += 10.0

        if candidate.ram_gb == requested_ram:
            score += 10.0
            confirmed_signals += 1
        elif candidate.ram_gb is not None:
            rejection_reason = (
                "The requested RAM does not "
                "match this catalog variant."
            )

    if requested_storage is not None:
        possible_score += 10.0

        if candidate.storage_gb == requested_storage:
            score += 10.0
            confirmed_signals += 1
        elif candidate.storage_gb is not None:
            rejection_reason = (
                "The requested storage does "
                "not match this catalog variant."
            )

    if requested_color:
        possible_score += 5.0

        color_score = _color_similarity(
            requested_color,
            candidate.color,
        )
        score += color_score * 5.0

        # Colour identifies a variant, not a product. A "Titan Blue"
        # listing must not be filed under a "Titan Red" variant, so a
        # colour conflict still eliminates that candidate; the resolution
        # service then registers the missing colour as a new variant of the
        # same canonical product instead of queueing the whole listing.
        if candidate.color:
            if color_score >= MIN_COLOR_IDENTITY_SCORE:
                confirmed_signals += 1
            else:
                rejection_reason = (
                    "The requested colour does not "
                    "match this catalog variant."
                )

    if _model_numbers_conflict(title, candidate):
        rejection_reason = (
            "The requested model code does not "
            "match this catalog product."
        )

    if _model_identity_conflict(title, candidate):
        rejection_reason = (
            "The marketplace title names a different "
            "model of this product line."
        )

    strong_product_identity = (
        name_score >= MIN_NAME_IDENTITY_SCORE
        or model_score >= MIN_MODEL_IDENTITY_SCORE
    )

    if not strong_product_identity:
        rejection_reason = rejection_reason or (
            "The product title or model "
            "is not specific enough for "
            "a safe automatic match."
        )

    confidence = max(
        0,
        min(round((score / possible_score) * 100), 100),
    )

    return _ScoredCandidate(
        candidate=candidate,
        confidence=confidence,
        name_score=name_score,
        model_score=model_score,
        confirmed_signals=confirmed_signals,
        rejection_reason=rejection_reason,
    )


class ProductMatchingService:
    """Match marketplace product data to active VEXTRO variants."""

    def __init__(
        self,
        repository: ProductMatchingRepository | None = None,
    ) -> None:
        self.repository = (
            repository
            or ProductMatchingRepository()
        )

    @staticmethod
    def _exact_response(
        candidate: ProductMatchCandidate,
        reason: str,
    ) -> ProductMatchResponse:
        """Return a settled, highest-confidence match response."""

        return ProductMatchResponse(
            matched=True,
            confidence=100,
            match_tier=TIER_EXACT,
            product_variant_id=candidate.product_variant_id,
            canonical_product_id=candidate.canonical_product_id,
            product_name=candidate.product_name,
            brand_name=candidate.brand_name,
            model=candidate.model,
            ram_gb=candidate.ram_gb,
            storage_gb=candidate.storage_gb,
            color=candidate.color,
            reason=reason,
        )

    def resolve_exact_identity(
        self,
        database_session: Session,
        payload: ProductMatchRequest,
    ) -> ProductMatchResponse | None:
        """Resolve the identity signals that need no scoring at all.

        Ordered by authority: an administrator's decision, the marketplace
        listing VEXTRO already stores, then an exact SKU code.
        """

        if payload.platform_code and payload.external_id:
            manual_match = self.repository.get_manual_match(
                database_session,
                platform_code=payload.platform_code,
                external_id=payload.external_id,
            )
            if manual_match is not None:
                return self._exact_response(
                    manual_match,
                    "Administrator-approved marketplace mapping reused.",
                )

            listing_match = self.repository.get_listing_match(
                database_session,
                platform_code=payload.platform_code,
                external_id=payload.external_id,
            )
            if listing_match is not None:
                return self._exact_response(
                    listing_match,
                    "Existing marketplace listing mapping reused.",
                )

        if payload.sku:
            sku_match = self.repository.get_sku_match(
                database_session,
                sku=payload.sku,
            )
            if sku_match is not None:
                return self._exact_response(
                    sku_match,
                    "Exact marketplace SKU code matched a catalog variant.",
                )

        return None

    def match_product(
        self,
        database_session: Session,
        payload: ProductMatchRequest,
    ) -> ProductMatchResponse:
        """Return the best safe product variant match."""

        exact_match = self.resolve_exact_identity(
            database_session,
            payload,
        )
        if exact_match is not None:
            return exact_match

        candidates = (
            self.repository.list_match_candidates(
                database_session,
                brand=payload.brand,
            )
        )

        if (
            not candidates
            and payload.brand
        ):
            candidates = (
                self.repository.list_match_candidates(
                    database_session,
                )
            )

        if not candidates:
            return ProductMatchResponse(
                matched=False,
                confidence=0,
                reason=(
                    "No active product variants "
                    "are available for matching."
                ),
            )

        # Every signal below is read out of the title, so the seller's own
        # store name comes off first. "Carrefour Samsung Galaxy A07" is the
        # same phone as "Samsung Galaxy A07" and must score as such.
        title = clean_marketplace_title(
            payload.title,
            payload.seller_name,
        )

        requested_ram = payload.ram_gb
        requested_storage = payload.storage_gb

        # Memory is the signal that separates one variant from another, so
        # take it from the best source available: the explicit request, then
        # the normalized specification sheet, then the title. Reading only
        # the title let an 8/256 listing attach to an 8/128 variant whenever
        # the marketplace kept the configuration out of the product name.
        specification_ram, specification_storage = (
            extract_memory_capacities(
                specifications=payload.specifications,
                title=title,
            )
        )

        extracted_ram, extracted_storage = (
            _extract_memory_values(
                title,
            )
        )

        if requested_ram is None:
            requested_ram = specification_ram or extracted_ram

        if requested_storage is None:
            requested_storage = (
                specification_storage or extracted_storage
            )

        requested_brand = (
            payload.brand
            or _detect_unique_text_value(
                title,
                [
                    candidate.brand_name
                    for candidate in candidates
                ],
            )
        )

        requested_model = (
            payload.model
            or _detect_unique_text_value(
                title,
                [
                    candidate.model
                    for candidate in candidates
                ],
            )
        )

        requested_color = (
            normalize_color(payload.color)
            or _detect_unique_text_value(
                title,
                [
                    candidate.color
                    for candidate in candidates
                ],
            )
        )

        scored_candidates: list[_ScoredCandidate] = [
            _score_candidate(
                candidate,
                title=title,
                requested_brand=requested_brand,
                requested_model=requested_model,
                requested_ram=requested_ram,
                requested_storage=requested_storage,
                requested_color=requested_color,
            )
            for candidate in candidates
        ]

        eligible_candidates = [
            item
            for item in scored_candidates
            if item.rejection_reason is None
        ]

        if not eligible_candidates:
            best = max(scored_candidates, key=_ranking_key)

            return _unmatched_response(
                best,
                best.rejection_reason
                or (
                    "No safe automatic product "
                    "variant match was found."
                ),
            )

        eligible_candidates.sort(key=_ranking_key, reverse=True)

        best = eligible_candidates[0]

        if best.confidence < MATCH_THRESHOLD:
            return _unmatched_response(
                best,
                (
                    "The best candidate did not "
                    "meet the automatic matching "
                    f"threshold of {MATCH_THRESHOLD}%."
                ),
            )

        # Ambiguity is only dangerous across different real-world products.
        # Several variants of one phone scoring alike simply means the
        # listing did not spell out its configuration, and the ranking key
        # already prefers the variant whose RAM, storage and colour were
        # confirmed. Rejecting those froze existing listings mid-refresh.
        competing = next(
            (
                item
                for item in eligible_candidates[1:]
                if item.candidate.canonical_product_id
                != best.candidate.canonical_product_id
            ),
            None,
        )

        if (
            competing is not None
            and (best.confidence - competing.confidence) < AMBIGUITY_MARGIN
        ):
            return _unmatched_response(
                best,
                (
                    "The best candidates are too "
                    "similar for a safe automatic "
                    "variant match."
                ),
            )

        return ProductMatchResponse(
            matched=True,
            confidence=best.confidence,
            match_tier=_confidence_tier(best.confidence),
            product_variant_id=(
                best.candidate.product_variant_id
            ),
            canonical_product_id=(
                best.candidate.canonical_product_id
            ),
            product_name=best.candidate.product_name,
            brand_name=best.candidate.brand_name,
            model=best.candidate.model,
            ram_gb=best.candidate.ram_gb,
            storage_gb=best.candidate.storage_gb,
            color=best.candidate.color,
            reason=(
                "A sufficiently confident and "
                "unambiguous catalog variant "
                "match was found."
            ),
        )
