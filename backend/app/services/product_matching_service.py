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
    OPTIONAL_BRAND_MARKERS,
    clean_product_display_name,
)


@dataclass(frozen=True)
class _ScoredCandidate:
    """One catalog variant scored against a marketplace item."""

    confidence: int
    name_score: float
    candidate: ProductMatchCandidate
    rejection_reason: str | None
    # Same phone by name, with no look-alike-model conflict.
    same_product: bool
    # Rejected for its colour and nothing else.
    color_only: bool


MATCH_THRESHOLD = 75
AMBIGUITY_MARGIN = 8

MIN_NAME_IDENTITY_SCORE = 0.65
MIN_MODEL_IDENTITY_SCORE = 0.90

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

    requested_tokens = set(requested_normalised.split())
    candidate_tokens = set(candidate_normalised.split())

    # Compare word by word. A whole-string ratio rewards a shared
    # prefix, which rates "Titanium Blue" against "Titanium Black" at
    # ~0.8 and would merge two different colours. Words are allowed a
    # little spelling drift ("Grey" / "Gray") but must otherwise agree.
    def _same_word(left: str, right: str) -> bool:
        return (
            left == right
            or SequenceMatcher(None, left, right).ratio() >= 0.75
        )

    shared = sum(
        1
        for requested_token in requested_tokens
        if any(
            _same_word(requested_token, candidate_token)
            for candidate_token in candidate_tokens
        )
    )
    smaller = min(len(requested_tokens), len(candidate_tokens))

    # One colour name fully contained in the other is the marketing
    # prefix case ("Awesome Black" is "Black").
    if smaller and shared >= smaller:
        return 1.0

    union = len(requested_tokens) + len(candidate_tokens) - shared
    return shared / union if union else 0.0


# Words that turn a phone name into a different phone. "iPhone 17" and
# "iPhone 17 Air" share almost every character, so plain similarity
# cannot separate them; these words must agree on both sides.
_MODEL_QUALIFIERS = frozenset(
    {
        "pro", "max", "plus", "ultra", "air", "mini", "lite", "neo",
        "fe", "se", "xl", "gt", "edge", "prime", "note", "fold",
        "flip", "turbo", "play", "go", "zoom",
    }
)

# Digit-bearing words that describe the offer rather than the model.
_NETWORK_TOKENS = frozenset({"5g", "4g", "3g", "2g", "lte"})
_SPEC_TOKEN = re.compile(
    r"^\d+(?:gb|tb|mb|mah|mp|hz|w|mm|inch|inches)$"
)


def _model_identity_conflict(
    title: str,
    product_name: str,
    *,
    strict_network: bool = False,
) -> str | None:
    """Explain why a title and a catalog name are different models.

    Returns ``None`` when nothing contradicts them being the same
    phone. The check is deliberately one-directional for model
    numbers (the catalog name's numbers must appear in the title)
    because marketplace titles carry many unrelated numbers such as
    screen size and camera megapixels.

    ``strict_network`` additionally requires the 4G/5G edition to
    agree. It is used for sources with consistent titles, where
    "Redmi 15C" and "Redmi 15C 5G" are separate product pages;
    free-text seller titles often drop the edition, so they are not
    held to it.
    """

    normalized_title = _normalize_text(title)
    name_tokens = _normalize_text(product_name).split()

    if not normalized_title or not name_tokens:
        return None

    if strict_network:
        title_networks = set(normalized_title.split()) & _NETWORK_TOKENS
        name_networks = set(name_tokens) & _NETWORK_TOKENS
        if title_networks != name_networks:
            return "network edition (4G/5G) differs"

    for token in name_tokens:
        if not any(character.isdigit() for character in token):
            continue
        if token in _NETWORK_TOKENS or _SPEC_TOKEN.match(token):
            continue

        # "60" may follow letters ("hot60") but must not be part of a
        # longer number or model code ("60i", "160").
        prefix_guard = (
            r"(?<![0-9])"
            if token[0].isdigit()
            else r"(?<![0-9a-z])"
        )
        if not re.search(
            prefix_guard + re.escape(token) + r"(?![0-9a-z])",
            normalized_title,
        ):
            return f"model number '{token}' is not in the title"

    title_tokens = set(normalized_title.split())
    name_qualifiers = {
        token for token in name_tokens if token in _MODEL_QUALIFIERS
    }
    missing = sorted(name_qualifiers - title_tokens)
    if missing:
        return f"catalog model is '{missing[0]}' but the title is not"

    # Only the leading brand/model part of the title is inspected for
    # extra qualifiers, so descriptive text further along the title
    # ("50MP Pro camera") cannot veto a genuine match.
    head_tokens = set(
        _normalize_text(
            clean_product_display_name(title) or title
        ).split()
    )
    extra = sorted(
        (head_tokens & _MODEL_QUALIFIERS) - set(name_tokens)
    )
    if extra:
        return f"title model is '{extra[0]}' but the catalog one is not"

    return None


def _names_same_product(
    title: str,
    product_name: str,
    brand_names: tuple[str | None, ...],
    *,
    exact: bool,
) -> bool:
    """Decide whether a title names the catalog product, word by word.

    Character similarity cannot do this job: "Digit D1" and "Digit
    Nova" share most of their letters through the brand, and so do
    "QMobile QCrystal" and "QMobile QHero". What identifies a phone is
    the words left after the brand is set aside, so every one of those
    words in the catalog name must appear in the title.

    ``exact`` is for sources with clean model-only titles: the title
    may not carry any extra model word either, which keeps "Sego Smart
    20 HD" apart from "Sego Smart 20". Free-text seller titles always
    carry extra words (specs, colours), so they are only held to the
    first rule.
    """

    normalized_title = _normalize_text(title)
    title_tokens = normalized_title.split()
    name_tokens = _normalize_text(product_name).split()
    if not title_tokens or not name_tokens:
        return False

    brand_tokens: set[str] = set()
    for brand_name in brand_names:
        normalized_brand = _normalize_text(brand_name)
        if not normalized_brand:
            continue
        brand_tokens.update(normalized_brand.split())
        # Brand written as one word in one place and two in another
        # ("XMobile" / "X Mobile").
        brand_tokens.add(normalized_brand.replace(" ", ""))
        brand_tokens.update(
            OPTIONAL_BRAND_MARKERS.get(
                normalized_brand.replace(" ", ""), set()
            )
        )

    def _model_words(tokens: list[str]) -> list[str]:
        return [
            token
            for token in tokens
            if token not in brand_tokens
            and token not in _NETWORK_TOKENS
        ]

    name_words = _model_words(name_tokens)
    if not name_words:
        # A name that is only a brand identifies no particular phone.
        return False

    title_token_set = set(title_tokens)

    def _in_title(word: str) -> bool:
        if word in title_token_set:
            return True
        if any(character.isdigit() for character in word):
            prefix_guard = (
                r"(?<![0-9])" if word[0].isdigit() else r"(?<![0-9a-z])"
            )
            return bool(
                re.search(
                    prefix_guard + re.escape(word) + r"(?![0-9a-z])",
                    normalized_title,
                )
            )
        return False

    if not all(_in_title(word) for word in name_words):
        # Sellers also run a model together ("Hot60 Pro"); accept that
        # only for multi-word names, as one unbroken run.
        if len(name_words) < 2 or (
            "".join(name_words)
            not in normalized_title.replace(" ", "")
        ):
            return False

    if exact:
        extra_words = set(_model_words(title_tokens)) - set(name_words)
        if extra_words:
            return False

    return True


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

    def match_product(
        self,
        database_session: Session,
        payload: ProductMatchRequest,
    ) -> ProductMatchResponse:
        """Return the best safe product variant match."""

        if payload.platform_code and payload.external_id:
            manual_match = self.repository.get_manual_match(
                database_session,
                platform_code=payload.platform_code,
                external_id=payload.external_id,
            )
            if manual_match is not None:
                return ProductMatchResponse(
                    matched=True,
                    confidence=100,
                    product_variant_id=manual_match.product_variant_id,
                    canonical_product_id=manual_match.canonical_product_id,
                    product_name=manual_match.product_name,
                    brand_name=manual_match.brand_name,
                    model=manual_match.model,
                    ram_gb=manual_match.ram_gb,
                    storage_gb=manual_match.storage_gb,
                    color=manual_match.color,
                    reason="Administrator-approved marketplace mapping reused.",
                )

            # A marketplace id we have already ingested is the same
            # offer on every later crawl. Reusing its mapping keeps
            # prices and stock refreshing even when the seller rewords
            # the title into something the scorer finds ambiguous.
            listing_match = self.repository.get_listing_match(
                database_session,
                platform_code=payload.platform_code,
                external_id=payload.external_id,
            )
            if listing_match is not None:
                return self._matched_response(
                    listing_match,
                    confidence=100,
                    reason="Existing marketplace listing mapping reused.",
                )

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

        # An empty catalog is handled after scoring, where a structured
        # source may still add the product.
        requested_ram = payload.ram_gb
        requested_storage = payload.storage_gb

        extracted_ram, extracted_storage = (
            _extract_memory_values(
                payload.title,
            )
        )

        if requested_ram is None:
            requested_ram = extracted_ram

        if requested_storage is None:
            requested_storage = (
                extracted_storage
            )

        requested_brand = (
            payload.brand
            or _detect_unique_text_value(
                payload.title,
                [
                    candidate.brand_name
                    for candidate in candidates
                ],
            )
        )

        requested_model = (
            payload.model
            or _detect_unique_text_value(
                payload.title,
                [
                    candidate.model
                    for candidate in candidates
                ],
            )
        )

        # Scrapers (particularly the pre-refactor Daraz spider) still
        # emit marketplace placeholders like ``"N/A"`` or ``"Standard"``
        # when they cannot read the real colour. Treating those as a
        # real colour request would mis-trigger the colour-rejection
        # path below and the auto-create path with it, so collapse
        # them to ``None`` here and let the title fallback try to find
        # a real one.
        raw_color = (
            str(payload.color).strip()
            if payload.color is not None
            else None
        )
        if raw_color and raw_color.lower() in {
            "n/a",
            "na",
            "none",
            "standard",
            "unknown",
            "default",
            "-",
            "--",
        }:
            raw_color = None

        requested_color = (
            raw_color
            or _detect_unique_text_value(
                payload.title,
                [
                    candidate.color
                    for candidate in candidates
                ],
            )
        )

        scored_candidates: list[_ScoredCandidate] = []

        for candidate in candidates:
            score = 0.0
            possible_score = 35.0

            rejection_reason: str | None = None

            name_score = _name_similarity(
                payload.title,
                candidate.product_name,
            )

            score += (
                name_score
                * 35.0
            )

            model_score = 0.0

            if requested_brand:
                possible_score += 20.0

                brand_score = _text_similarity(
                    requested_brand,
                    candidate.brand_name,
                )

                score += (
                    brand_score
                    * 20.0
                )

            if requested_model:
                possible_score += 20.0

                model_score = _text_similarity(
                    requested_model,
                    candidate.model,
                )

                score += (
                    model_score
                    * 20.0
                )

            if requested_ram is not None:
                possible_score += 10.0

                if (
                    candidate.ram_gb
                    == requested_ram
                ):
                    score += 10.0

                elif candidate.ram_gb is not None:
                    rejection_reason = (
                        "The requested RAM does not "
                        "match this catalog variant."
                    )

            if requested_storage is not None:
                possible_score += 10.0

                if (
                    candidate.storage_gb
                    == requested_storage
                ):
                    score += 10.0

                elif (
                    candidate.storage_gb
                    is not None
                ):
                    rejection_reason = (
                        "The requested storage does "
                        "not match this catalog variant."
                    )

            color_only_rejection = False

            if requested_color:
                possible_score += 5.0

                color_score = _color_similarity(
                    requested_color,
                    candidate.color,
                )

                score += (
                    color_score
                    * 5.0
                )

                # Only reject when the candidate itself asserts a
                # colour and it does not match. A candidate with no
                # colour recorded is left to lose points, not to be
                # eliminated, so a colourful listing can still adopt
                # a generic variant when nothing more specific exists.
                if (
                    candidate.color
                    and color_score
                    < MIN_COLOR_IDENTITY_SCORE
                    and rejection_reason is None
                ):
                    color_only_rejection = True
                    rejection_reason = (
                        "The requested colour does not "
                        "match this catalog variant."
                    )

            # Identity is decided on words, not character similarity.
            # A structured source's title is the bare model name, so it
            # must equal the catalog name; a seller's free-text title
            # only has to contain it (or the catalog's model string).
            names_same_product = _names_same_product(
                payload.title,
                candidate.product_name,
                (candidate.brand_name, requested_brand),
                exact=payload.allow_catalog_create,
            )
            strong_product_identity = names_same_product or (
                not payload.allow_catalog_create
                and model_score >= MIN_MODEL_IDENTITY_SCORE
            )

            # A look-alike model ("iPhone 17 Air" for an "iPhone 17"
            # title) outranks every other reason: no amount of RAM,
            # storage or colour agreement makes it the same phone.
            model_conflict = _model_identity_conflict(
                payload.title,
                candidate.product_name,
                strict_network=payload.allow_catalog_create,
            )

            if not strong_product_identity:
                color_only_rejection = False
                rejection_reason = (
                    rejection_reason
                    or (
                        "The product title or model "
                        "is not specific enough for "
                        "a safe automatic match."
                    )
                )

            elif model_conflict is not None:
                color_only_rejection = False
                rejection_reason = (
                    "The marketplace title names a different "
                    f"model ({model_conflict})."
                )

            confidence = round(
                (
                    score
                    / possible_score
                )
                * 100
            )

            confidence = max(
                0,
                min(
                    confidence,
                    100,
                ),
            )

            scored_candidates.append(
                _ScoredCandidate(
                    confidence=confidence,
                    name_score=name_score,
                    candidate=candidate,
                    rejection_reason=rejection_reason,
                    same_product=(
                        strong_product_identity
                        and model_conflict is None
                    ),
                    color_only=color_only_rejection,
                )
            )

        def _rank(item: _ScoredCandidate) -> tuple[int, float, int]:
            return (
                item.confidence,
                item.name_score,
                -item.candidate.product_variant_id,
            )

        scored_candidates.sort(key=_rank, reverse=True)

        eligible_candidates = [
            item
            for item in scored_candidates
            if item.rejection_reason is None
        ]

        best = (
            eligible_candidates[0]
            if eligible_candidates
            else None
        )
        runner_up = (
            eligible_candidates[1]
            if len(eligible_candidates) > 1
            else None
        )

        if best is not None and best.confidence >= MATCH_THRESHOLD and (
            runner_up is None
            or best.confidence - runner_up.confidence >= AMBIGUITY_MARGIN
        ):
            return self._matched_response(
                best.candidate,
                confidence=best.confidence,
                reason=(
                    "A sufficiently confident and "
                    "unambiguous catalog variant "
                    "match was found."
                ),
            )

        # A confident match that ties only with other configurations of
        # the SAME phone is not really ambiguous about the product. A
        # title that names no colour cannot choose between a phone's
        # colour variants, but it does not need to: place it on the
        # configuration the title actually states (colour unknown).
        if best is not None and best.confidence >= MATCH_THRESHOLD:
            contenders = [
                item
                for item in eligible_candidates
                if best.confidence - item.confidence < AMBIGUITY_MARGIN
            ]
            if all(
                item.candidate.canonical_product_id
                == best.candidate.canonical_product_id
                for item in contenders
            ):
                variant = self.repository.get_or_create_variant(
                    database_session,
                    reference_candidate=best.candidate,
                    ram_gb=requested_ram,
                    storage_gb=requested_storage,
                    color=requested_color,
                )
                database_session.commit()
                return self._matched_response(
                    variant,
                    confidence=best.confidence,
                    reason=(
                        "Matched the catalog product; the title did "
                        "not single out one configuration, so the "
                        "listing was placed on the configuration it "
                        "states."
                    ),
                )

        # No single confident answer from scoring alone. Before parking
        # the item for manual review, try the two safe ways to resolve
        # it automatically.
        #
        # 1. The only thing wrong with the strongest candidate is its
        #    colour: add the missing colour beside it. Marketplaces
        #    list every colour of a phone on one page, so a single
        #    crawl legitimately discovers several new colours at once.
        if best is None:
            color_only = [
                item for item in scored_candidates if item.color_only
            ]
            if color_only:
                auto_created = self._maybe_auto_create_color_sibling(
                    database_session,
                    best_candidate=color_only[0].candidate,
                    best_name_score=color_only[0].name_score,
                    rejection_reason=color_only[0].rejection_reason,
                    requested_color=requested_color,
                    requested_ram=requested_ram,
                    requested_storage=requested_storage,
                )
                if auto_created is not None:
                    # The matcher endpoint does not own a transaction
                    # boundary, so persist the new variant before the
                    # caller ingests a listing against it.
                    database_session.commit()
                    return self._matched_response(
                        auto_created,
                        confidence=color_only[0].confidence,
                        reason=(
                            "Auto-created a colour variant "
                            f"'{auto_created.color}' from the strongest "
                            "catalog match because the marketplace "
                            "reported a colour the catalog did not yet "
                            "track."
                        ),
                    )

        # 2. The source states brand, model, RAM, storage and colour as
        #    separate fields, so the configuration is known rather than
        #    inferred: place it on the matching product, or add the
        #    product when the catalog has never seen this phone.
        structured = self._resolve_structured_source(
            database_session,
            payload=payload,
            scored_candidates=scored_candidates,
            requested_brand=requested_brand,
            requested_ram=requested_ram,
            requested_storage=requested_storage,
            requested_color=requested_color,
        )
        if structured is not None:
            return structured

        if best is None:
            if not scored_candidates:
                return ProductMatchResponse(
                    matched=False,
                    confidence=0,
                    reason=(
                        "No active product variants "
                        "are available for matching."
                    ),
                )
            top = scored_candidates[0]
            return self._unmatched_response(
                top.candidate,
                confidence=top.confidence,
                reason=(
                    top.rejection_reason
                    or (
                        "No safe automatic product "
                        "variant match was found."
                    )
                ),
            )

        if best.confidence < MATCH_THRESHOLD:
            return self._unmatched_response(
                best.candidate,
                confidence=best.confidence,
                reason=(
                    "The best candidate did not "
                    "meet the automatic matching "
                    f"threshold of {MATCH_THRESHOLD}%."
                ),
            )

        return self._unmatched_response(
            best.candidate,
            confidence=best.confidence,
            reason=(
                "The best candidates are too "
                "similar for a safe automatic "
                "variant match."
            ),
        )

    @staticmethod
    def _matched_response(
        candidate: ProductMatchCandidate,
        *,
        confidence: int,
        reason: str,
    ) -> ProductMatchResponse:
        return ProductMatchResponse(
            matched=True,
            confidence=confidence,
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

    @staticmethod
    def _unmatched_response(
        candidate: ProductMatchCandidate,
        *,
        confidence: int,
        reason: str,
    ) -> ProductMatchResponse:
        return ProductMatchResponse(
            matched=False,
            confidence=confidence,
            suggested_product_variant_id=candidate.product_variant_id,
            product_name=candidate.product_name,
            brand_name=candidate.brand_name,
            model=candidate.model,
            ram_gb=candidate.ram_gb,
            storage_gb=candidate.storage_gb,
            color=candidate.color,
            reason=reason,
        )

    def _resolve_structured_source(
        self,
        database_session: Session,
        *,
        payload: ProductMatchRequest,
        scored_candidates: list["_ScoredCandidate"],
        requested_brand: str | None,
        requested_ram: int | None,
        requested_storage: int | None,
        requested_color: str | None,
    ) -> ProductMatchResponse | None:
        """Place a structured-source item without manual review.

        Only runs for requests that opt in with ``allow_catalog_create``
        and identify themselves with a marketplace id. Returns ``None``
        to let the caller fall through to the usual pending-review
        response.
        """

        if not (
            payload.allow_catalog_create
            and payload.platform_code
            and payload.external_id
        ):
            return None

        same_product = [
            item for item in scored_candidates if item.same_product
        ]

        if same_product:
            reference = same_product[0]
            variant = self.repository.get_or_create_variant(
                database_session,
                reference_candidate=reference.candidate,
                ram_gb=requested_ram,
                storage_gb=requested_storage,
                color=requested_color,
            )
            database_session.commit()
            return self._matched_response(
                variant,
                confidence=max(reference.confidence, MATCH_THRESHOLD),
                reason=(
                    "Matched the catalog product by name and placed "
                    "the listing on its exact configuration, as "
                    "stated by the marketplace."
                ),
            )

        display_name = (
            clean_product_display_name(payload.title)
            or payload.title
        )
        variant = self.repository.create_catalog_product(
            database_session,
            platform_code=payload.platform_code,
            external_id=payload.external_id,
            name=display_name,
            brand_name=requested_brand,
            specifications=payload.specifications,
            ram_gb=requested_ram,
            storage_gb=requested_storage,
            color=requested_color,
        )
        database_session.commit()
        return self._matched_response(
            variant,
            confidence=100,
            reason=(
                "Added a new product to the catalog because the "
                "marketplace lists a phone the catalog did not have."
            ),
        )

    def _maybe_auto_create_color_sibling(
        self,
        database_session: Session,
        *,
        best_candidate: ProductMatchCandidate,
        best_name_score: float,
        rejection_reason: str | None,
        requested_color: str | None,
        requested_ram: int | None,
        requested_storage: int | None,
    ) -> ProductMatchCandidate | None:
        """Clone the strongest match into a new colour when it is safe.

        Returns the new (or newly reused) ``ProductMatchCandidate`` on
        success, or ``None`` when any of the safety checks fail.

        Rules:
        - The rejection must call out a colour mismatch; any other
          rejection (ram/storage/name identity) is a real catalog gap
          that an administrator should resolve, not something to
          paper over by creating variants.
        - The product-identity signal (name score) must clear the
          same threshold a normal match would need, so we never
          create a variant for a title that is only vaguely similar.
        - RAM and storage must match the reference variant whenever
          both sides state them.
        - The requested colour must be a clean non-empty string of
          at least two characters, so marketplace values like ``N/A``
          or ``'-'`` never leak into the catalog as colour names.
        """

        if rejection_reason is None:
            return None
        reason_lower = rejection_reason.lower()
        if "colour" not in reason_lower and "color" not in reason_lower:
            return None

        if best_name_score < MIN_NAME_IDENTITY_SCORE:
            return None

        cleaned_color = (requested_color or "").strip()
        if len(cleaned_color) < 2 or cleaned_color.lower() in {
            "n/a", "na", "none", "standard", "unknown",
        }:
            return None

        # Mismatched RAM or storage are only a hard veto when both
        # sides actually report a value. Catalog seeds for brand-new
        # phones often leave RAM/storage NULL on the first imported
        # variant; we would rather clone that generic row with the
        # requested colour than wedge every scrape into pending.
        if (
            requested_ram is not None
            and best_candidate.ram_gb is not None
            and best_candidate.ram_gb != requested_ram
        ):
            return None
        if (
            requested_storage is not None
            and best_candidate.storage_gb is not None
            and best_candidate.storage_gb != requested_storage
        ):
            return None

        return self.repository.create_color_sibling_variant(
            database_session,
            reference_candidate=best_candidate,
            color=cleaned_color,
        )
