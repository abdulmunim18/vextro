"""Conservative identity matching for titles from different marketplaces."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant


FEATURE_BOUNDARY = re.compile(
    r"\b(?:ram|rom|storage|memory|front camera|rear camera|back camera|"
    r"battery|display|screen|processor|chipset|pta approved|official pta|"
    r"warranty|dual sim|single sim|charger|charging|up to)\b",
    re.I,
)

LEADING_MARKETING_NOTE = re.compile(
    r"^\s*(?:\((?=[^)]*(?:official|pta|approved|warranty))[^)]*\)|"
    r"\[(?=[^]]*(?:official|pta|approved|warranty))[^]]*\])\s*",
    re.I,
)

MEMORY_VARIANT_NOTE = re.compile(
    r"\s*\((?=[^)]*(?:\d+\s*gb|ram|rom|storage))[^)]*\)\s*$",
    re.I,
)

CAPACITY_BOUNDARY = re.compile(
    r"\b(?:\d{1,3}\s*gb\s*[/+|]\s*\d{1,4}\s*gb|"
    r"\d{1,3}\s*/\s*\d{2,4}\s*gb|"
    r"\d{1,3}\s*\+\s*\d{1,3}\s*gb|"
    r"\d{1,4}\s*(?:gb|tb)(?=\s|ram|rom|[/+|,]|$))",
    re.I,
)

DISPLAY_SIZE_BOUNDARY = re.compile(
    r"\b\d{1,2}(?:\.\d{1,2})?\s*(?:inches|inch|\")",
    re.I,
)


OPTIONAL_BRAND_MARKERS = {
    "apple": {"apple"},
    "google": {"google"},
    "motorola": {"motorola", "moto"},
    "samsung": {"samsung", "galaxy"},
    "sony": {"sony"},
    "xiaomi": {"xiaomi"},
    "zte": {"zte"},
}


def clean_product_display_name(title: str | None) -> str:
    """Extract a concise brand/model label from a marketplace title."""

    if not title:
        return ""

    cleaned = " ".join(str(title).split())
    cleaned = LEADING_MARKETING_NOTE.sub("", cleaned)
    cleaned = MEMORY_VARIANT_NOTE.sub("", cleaned)

    boundaries = [
        match.start()
        for pattern in (
            FEATURE_BOUNDARY,
            CAPACITY_BOUNDARY,
            DISPLAY_SIZE_BOUNDARY,
        )
        if (match := pattern.search(cleaned)) is not None
    ]

    separator_match = re.search(r"\s+(?:\|{1,2}|-|=)\s+", cleaned)
    if separator_match:
        boundaries.append(separator_match.start())

    if boundaries:
        candidate = cleaned[:min(boundaries)].strip(" -|=,;:")
        if len(candidate.split()) >= 2:
            cleaned = candidate

    return cleaned.strip(" -|=,;:")


def normalized_product_identity(title: str | None) -> str:
    """Return a strict brand/model identity without offer-specific details."""

    if not title:
        return ""

    normalized = unicodedata.normalize(
        "NFKD",
        clean_product_display_name(title),
    )
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()

    boundary = FEATURE_BOUNDARY.search(normalized)
    if boundary:
        normalized = normalized[:boundary.start()]

    normalized = re.sub(
        r"\b(?:\d{1,3}\s*gb\s*[/+|]\s*\d{1,4}\s*gb|"
        r"\d{1,3}\s*/\s*\d{2,4}\s*gb|"
        r"\d{1,3}\s*\+\s*\d{1,3}\s*gb)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"\b\d{1,4}\s*(?:gb|tb)\b", " ", normalized)
    normalized = re.sub(r"\b(?:4g|5g)\b", " ", normalized)
    normalized = re.sub(
        r"\b(?:official|approved|new|sealed|box packed)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)

    return " ".join(normalized.split())


def cross_marketplace_product_key(
    title: str | None,
    brand_name: str | None,
) -> str:
    """Return a brand-scoped model key shared by marketplace title styles.

    The caller already constrains matches to one canonical brand, so optional
    manufacturer markers can be removed safely. Product-family terms such as
    iPhone, Redmi, Poco, Pixel and Xperia remain part of the key.
    """

    identity = normalized_product_identity(title)
    if not identity:
        return ""

    normalized_brand = normalized_product_identity(brand_name)
    brand_tokens = set(normalized_brand.split())
    brand_tokens.update(
        OPTIONAL_BRAND_MARKERS.get(normalized_brand, set())
    )

    model_tokens = [
        token for token in identity.split()
        if token not in brand_tokens
    ]
    return " ".join(model_tokens)


def find_cross_platform_canonical(
    database_session: Session,
    *,
    title: str,
    brand_id: int | None,
    incoming_platform_id: int,
) -> CanonicalProduct | None:
    """Return one unambiguous same-brand identity from another platform."""

    if brand_id is None:
        return None

    brand_name = database_session.query(Brand.name).filter(
        Brand.id == brand_id,
    ).scalar()
    identity = cross_marketplace_product_key(title, brand_name)
    if not identity:
        return None

    candidates = (
        database_session.query(CanonicalProduct)
        .join(
            ProductVariant,
            ProductVariant.canonical_product_id == CanonicalProduct.id,
        )
        .join(
            ProductListing,
            ProductListing.product_variant_id == ProductVariant.id,
        )
        .filter(
            CanonicalProduct.is_active.is_(True),
            CanonicalProduct.brand_id == brand_id,
            ProductListing.platform_id != incoming_platform_id,
        )
        .distinct()
        .all()
    )

    matches = [
        candidate
        for candidate in candidates
        if cross_marketplace_product_key(candidate.name, brand_name) == identity
        or cross_marketplace_product_key(candidate.model, brand_name) == identity
    ]

    if matches:
        # Multiple canonical rows with the same exact brand/model key are
        # duplicates, not competing fuzzy candidates. New listings attach to
        # the oldest stable row; the maintenance merge consolidates the rest.
        return min(matches, key=lambda candidate: candidate.id)

    return None
