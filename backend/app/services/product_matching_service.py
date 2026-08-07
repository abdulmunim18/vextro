import re
import unicodedata
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


MATCH_THRESHOLD = 75
AMBIGUITY_MARGIN = 8

MIN_NAME_IDENTITY_SCORE = 0.65
MIN_MODEL_IDENTITY_SCORE = 0.90

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

        requested_color = (
            payload.color
            or _detect_unique_text_value(
                payload.title,
                [
                    candidate.color
                    for candidate in candidates
                ],
            )
        )

        scored_candidates: list[
            tuple[
                int,
                float,
                ProductMatchCandidate,
                str | None,
            ]
        ] = []

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

            if requested_color:
                possible_score += 5.0

                color_score = _text_similarity(
                    requested_color,
                    candidate.color,
                )

                score += (
                    color_score
                    * 5.0
                )

            strong_product_identity = (
                name_score
                >= MIN_NAME_IDENTITY_SCORE
                or model_score
                >= MIN_MODEL_IDENTITY_SCORE
            )

            if not strong_product_identity:
                rejection_reason = (
                    rejection_reason
                    or (
                        "The product title or model "
                        "is not specific enough for "
                        "a safe automatic match."
                    )
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
                (
                    confidence,
                    name_score,
                    candidate,
                    rejection_reason,
                )
            )
        eligible_candidates = [
            item
            for item in scored_candidates
            if item[3] is None
        ]

        if not eligible_candidates:
            scored_candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                    -item[2].product_variant_id,
                ),
                reverse=True,
            )

            (
                best_confidence,
                _,
                best_candidate,
                rejection_reason,
            ) = scored_candidates[0]

            return ProductMatchResponse(
                matched=False,
                confidence=best_confidence,
                product_name=(
                    best_candidate.product_name
                ),
                brand_name=(
                    best_candidate.brand_name
                ),
                model=best_candidate.model,
                ram_gb=best_candidate.ram_gb,
                storage_gb=(
                    best_candidate.storage_gb
                ),
                color=best_candidate.color,
                reason=(
                    rejection_reason
                    or (
                        "No safe automatic product "
                        "variant match was found."
                    )
                ),
            )

        eligible_candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
                -item[2].product_variant_id,
            ),
            reverse=True,
        )

        best_confidence = (
            eligible_candidates[0][0]
        )

        best_candidate = (
            eligible_candidates[0][2]
        )

        second_confidence = (
            eligible_candidates[1][0]
            if len(eligible_candidates) > 1
            else None
        )
        if best_confidence < MATCH_THRESHOLD:
            return ProductMatchResponse(
                matched=False,
                confidence=best_confidence,
                product_name=(
                    best_candidate.product_name
                ),
                brand_name=(
                    best_candidate.brand_name
                ),
                model=best_candidate.model,
                ram_gb=best_candidate.ram_gb,
                storage_gb=(
                    best_candidate.storage_gb
                ),
                color=best_candidate.color,
                reason=(
                    "The best candidate did not "
                    "meet the automatic matching "
                    f"threshold of {MATCH_THRESHOLD}%."
                ),
            )

        if (
            second_confidence is not None
            and (
                best_confidence
                - second_confidence
            ) < AMBIGUITY_MARGIN
        ):
            return ProductMatchResponse(
                matched=False,
                confidence=best_confidence,
                product_name=(
                    best_candidate.product_name
                ),
                brand_name=(
                    best_candidate.brand_name
                ),
                model=best_candidate.model,
                ram_gb=best_candidate.ram_gb,
                storage_gb=(
                    best_candidate.storage_gb
                ),
                color=best_candidate.color,
                reason=(
                    "The best candidates are too "
                    "similar for a safe automatic "
                    "variant match."
                ),
            )

        return ProductMatchResponse(
            matched=True,
            confidence=best_confidence,
            product_variant_id=(
                best_candidate.product_variant_id
            ),
            canonical_product_id=(
                best_candidate.canonical_product_id
            ),
            product_name=(
                best_candidate.product_name
            ),
            brand_name=(
                best_candidate.brand_name
            ),
            model=best_candidate.model,
            ram_gb=best_candidate.ram_gb,
            storage_gb=(
                best_candidate.storage_gb
            ),
            color=best_candidate.color,
            reason=(
                "A sufficiently confident and "
                "unambiguous catalog variant "
                "match was found."
            ),
        )