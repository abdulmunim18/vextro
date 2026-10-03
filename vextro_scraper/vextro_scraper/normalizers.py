"""Marketplace-specific text normalizers used by the smartphone spiders.

Daraz and PriceOye publish the same facts in different shapes. Daraz packs an
entire specification sheet into one unseparated string on each catalog item;
PriceOye publishes a JSON-LD ``Product`` block plus HTML tables. Turning both
into the same vocabulary is what makes product matching reliable, so the rules
live here rather than inside the spiders.
"""

import json
import re


# Daraz concatenates "<label><value>" pairs with no separator, grouped under
# section headers. Splitting on this vocabulary recovers the original pairs.
DARAZ_SPEC_SECTIONS = (
    "General Features",
    "Display",
    "Memory",
    "Performance",
    "Battery",
    "Camera",
    "Connectivity",
    "Design",
    "Other Features",
)

DARAZ_SPEC_LABELS = (
    "Release Date",
    "SIM Support",
    "Phone Dimensions",
    "Phone Weight",
    "Operating System",
    "Screen Size",
    "Screen Resolution",
    "Screen Type",
    "Screen Protection",
    "Internal Memory",
    "Card Slot",
    "RAM",
    "Processor",
    "GPU",
    "Front Camera",
    "Front Flash Light",
    "Front Video Recording",
    "Back Flash Light",
    "Back Camera",
    "Back Video Recording",
    "Bluetooth",
    "4G/LTE",
    "5G",
    "3G",
    "Radio",
    "WiFi",
    "NFC",
    "Type",
)


# Longest labels first so "Front Camera" is never split as "Type".
_DARAZ_TOKEN_PATTERN = re.compile(
    "|".join(
        re.escape(token)
        for token in sorted(
            DARAZ_SPEC_SECTIONS + DARAZ_SPEC_LABELS,
            key=len,
            reverse=True,
        )
    )
)

_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "--",
        "n/a",
        "na",
        "none",
        "null",
        "unknown",
        "not available",
        "no brand",
        "unbranded",
        "standard",
        "yes",
        "no",
    }
)

PRICE_PATTERN = re.compile(
    r"(?:rs\.?|pkr)?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)",
    re.I,
)


def optional_text(value, *, max_length=2000):
    """Return trimmed text, or ``None`` for marketplace placeholders."""

    if value is None:
        return None

    normalized = " ".join(str(value).split())

    if normalized.lower() in _PLACEHOLDER_VALUES:
        return None

    return normalized[:max_length]


def parse_price(value):
    """Return the first amount in a marketplace price string as a float.

    Daraz publishes ``"17499"`` and ``"Rs. 17,499"``; PriceOye publishes
    ``"Rs119,999"``. Returns ``None`` rather than a sentinel so the caller
    can treat a missing price as missing rather than as free.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        amount = float(value)
        return amount if amount > 0 else None

    match = PRICE_PATTERN.search(str(value))

    if match is None:
        return None

    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None

    return amount if amount > 0 else None


def parse_rating(value, *, maximum=5.0):
    """Return a marketplace rating inside ``0..maximum``, else ``None``."""

    text = optional_text(value, max_length=20)

    if text is None:
        return None

    try:
        rating = float(text)
    except ValueError:
        return None

    if rating <= 0 or rating > maximum:
        return None

    return round(rating, 2)


def parse_count(value):
    """Return a non-negative review/rating count, else ``None``."""

    text = optional_text(value, max_length=20)

    if text is None:
        return None

    digits = re.sub(r"[^\d]", "", text)

    if not digits:
        return None

    return int(digits)


def parse_daraz_specification_sheet(description):
    """Split one packed Daraz description string into label/value pairs.

    Daraz emits the whole sheet as
    ``"General FeaturesRelease Date05 Aug 2026SIM SupportDual Nano SIM..."``.
    Every section header and field label is known, so the text between one
    label and the next is that label's value.
    """

    if isinstance(description, (list, tuple)):
        description = " ".join(
            str(part) for part in description if part
        )

    text = optional_text(description, max_length=8000)

    if text is None:
        return {}

    matches = list(_DARAZ_TOKEN_PATTERN.finditer(text))

    if not matches:
        return {}

    specifications = {}

    for index, match in enumerate(matches):
        label = match.group(0)

        if label in DARAZ_SPEC_SECTIONS:
            continue

        value_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        value = optional_text(text[match.end():value_end], max_length=300)

        if value is None:
            continue

        # "Type" only appears inside the Battery section on Daraz sheets.
        if label == "Type":
            label = "Battery Capacity"

        specifications.setdefault(label, value)

    return specifications


def extract_json_ld_products(page_source):
    """Yield every ``schema.org/Product`` object embedded in a page.

    PriceOye's product pages carry a JSON-LD ``Product`` block holding the
    current offer price, availability and the aggregate rating. It is the
    marketplace's own machine-readable statement of those facts, so it beats
    scraping presentation markup.
    """

    products = []

    for raw_block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_source or "",
        re.S | re.I,
    ):
        try:
            parsed = json.loads(raw_block.strip())
        except (ValueError, TypeError):
            continue

        for candidate in parsed if isinstance(parsed, list) else [parsed]:
            if (
                isinstance(candidate, dict)
                and str(candidate.get("@type", "")).lower() == "product"
            ):
                products.append(candidate)

    return products


def json_ld_offer(product):
    """Return one ``Offer`` mapping from a JSON-LD product, if present."""

    offers = (product or {}).get("offers")

    if isinstance(offers, list):
        offers = next(
            (offer for offer in offers if isinstance(offer, dict)),
            None,
        )

    return offers if isinstance(offers, dict) else None


def json_ld_availability(product):
    """Return ``True``/``False`` for a JSON-LD availability, else ``None``."""

    offer = json_ld_offer(product)

    if offer is None:
        return None

    availability = optional_text(offer.get("availability"), max_length=120)

    if availability is None:
        return None

    normalized = availability.replace("\\/", "/").lower()

    if normalized.endswith("instock") or normalized.endswith("in stock"):
        return True

    if (
        "outofstock" in normalized
        or "soldout" in normalized
        or "discontinued" in normalized
    ):
        return False

    return None
