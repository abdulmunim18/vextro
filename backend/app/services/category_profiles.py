"""What makes a product, and a variant of it, in each catalogue category.

VEXTRO began with smartphones only, and phone rules (RAM, storage, 4G/5G)
were applied to everything. A category profile states, per category:

* which attributes tell two variants of one product apart (a phone's RAM
  and storage, a tablet's Wi-Fi or cellular model, a watch's case size);
* how those attributes are read from a marketplace title and its
  specification sheet.

Colour and condition are variant attributes in every category and stay in
their own columns, so they are not repeated here.

The slugs are the categories seeded by migration ``230caa8e6095``. A
listing names its category; one that names none is a smartphone, which is
what every listing was before categories existed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.smartphone_normalization import (
    BRAND_ALIASES,
    extract_memory_capacities,
    normalize_specifications,
)
from app.services.variant_identity import configuration_key


class UnknownCategoryError(ValueError):
    """A listing named a category VEXTRO has no profile for."""


Extractor = Callable[[str, dict[str, str], str], object | None]


@dataclass(frozen=True)
class IdentityAttribute:
    """One attribute that separates two variants of a product."""

    key: str
    label: str
    unit: str | None
    extract: Extractor


@dataclass(frozen=True)
class CategoryProfile:
    slug: str
    name: str
    identity: tuple[IdentityAttribute, ...]
    # Words that name a variant or the offer, not the product: "Wi-Fi" and
    # "11-inch" on a tablet, "44mm" and "GPS" on a watch, "1 Year Warranty".
    # They come off before a title becomes a product name or is compared
    # with one.
    variant_words: tuple[re.Pattern, ...] = ()
    # One model spelled two ways by two stores, written one way: "8th
    # Generation M4 Chip" and "M4 8th Gen", "SM-X400" and "X400".
    name_rewrites: tuple[
        tuple[re.Pattern, str | Callable[[re.Match], str]], ...
    ] = ()

    def product_title(self, title: str | None) -> str:
        """Return the title without the words that name a variant."""

        text = str(title or "")
        removed = 0
        for pattern, replacement in self.name_rewrites:
            text, count = pattern.subn(replacement, text)
            removed += count
        for pattern in self.variant_words:
            text, count = pattern.subn(" ", text)
            removed += count

        # "Wi-Fi + Cellular" leaves a lone "+"; brackets may be left empty.
        # A title that lost nothing (every phone title) is left as it was.
        if removed:
            text = re.sub(r"(?<!\S)[+&/,|-](?!\S)", " ", text)
            text = re.sub(r"\(\s*\)", " ", text)

        return " ".join(text.split())

    def identity_from(
        self,
        *,
        title: str | None,
        specifications: dict[str, object] | None = None,
        variant: str | None = None,
        stated: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return the identity attributes a listing states, by key.

        ``stated`` holds values the source sent as fields of their own (the
        crawler's ``ram_gb`` and ``storage_gb``); they outrank anything read
        from text, as they always have in the matcher. Attributes nobody
        states are left out rather than guessed, so an unstated value never
        contradicts a stated one.
        """

        normalized = normalize_specifications(specifications)
        text = " ".join(part for part in (variant or "", title or "") if part)
        values: dict[str, object] = {}

        for attribute in self.identity:
            value = (stated or {}).get(attribute.key)
            if value is None:
                value = attribute.extract(text, normalized, title or "")
            if value is not None:
                values[attribute.key] = value

        return values

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(attribute.key for attribute in self.identity)


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def _memory(text: str, specifications: dict[str, str], title: str) -> tuple[int | None, int | None]:
    """RAM and storage read the way the matcher has always read them.

    The specification sheet first, then the title's own figures
    ("6GB 128GB"). Kept identical so phones resolve exactly as before.
    """

    # Imported here: the matcher will itself depend on category profiles.
    from app.services.product_matching_service import _extract_memory_values

    ram_gb, storage_gb = extract_memory_capacities(
        specifications=specifications,
        title=title,
        variant=text,
    )
    title_ram, title_storage = _extract_memory_values(text)

    return ram_gb or title_ram, storage_gb or title_storage


def _ram_gb(text: str, specifications: dict[str, str], title: str) -> int | None:
    return _memory(text, specifications, title)[0]


def _storage_gb(text: str, specifications: dict[str, str], title: str) -> int | None:
    return _memory(text, specifications, title)[1]


_CELLULAR = re.compile(r"\b(?:cellular|lte|3g|4g|5g|sim)\b", re.I)
_WIFI_ONLY = re.compile(r"\bwi[\s-]?fi\b", re.I)


def _connectivity(text: str, specifications: dict[str, str], title: str) -> str | None:
    """"cellular" or "wifi": an iPad Wi-Fi and Cellular are two prices.

    A model that names neither states nothing; most such tablets are
    Wi-Fi only, but that is a guess, and a guess must not split or join
    variants.
    """

    stated = " ".join(
        [text]
        + [
            value
            for key, value in specifications.items()
            if any(word in key for word in ("network", "connectivity", "sim"))
        ]
    )

    if _CELLULAR.search(stated):
        return "cellular"
    if _WIFI_ONLY.search(stated):
        return "wifi"
    return None


_CASE_SIZE = re.compile(r"\b(\d{2})\s*mm\b", re.I)


def _case_size_mm(text: str, specifications: dict[str, str], title: str) -> int | None:
    """A watch's case size: the 41 mm and 45 mm models are priced apart."""

    for source in (text, specifications.get("case_size", ""), specifications.get("display", "")):
        match = _CASE_SIZE.search(str(source))
        if match and 20 <= int(match.group(1)) <= 60:
            return int(match.group(1))
    return None


_SCREEN_SIZE = re.compile(
    # Stores write inches as a word, a quote, a double prime or two
    # apostrophes: 11-inch, 13", 14.6″, 8.3''.
    r"\b(\d{1,2}(?:\.\d{1,2})?)\s*-?\s*(?:inches|inch|\"|''|”|″)",
    re.I,
)


def _screen_inches(text: str, specifications: dict[str, str], title: str) -> int | float | None:
    """A tablet's screen size as the title states it: 11 or 13 inches.

    The 11- and 13-inch iPad Pro are one model at two prices. Only the
    title is read: a specification sheet's 10.95 against another store's
    "11-inch" would part one tablet into two.
    """

    for match in _SCREEN_SIZE.finditer(text):
        size = float(match.group(1))
        if 7 <= size <= 15:
            return int(size) if size.is_integer() else round(size, 1)
    return None


# "1 Year Warranty", "(1 Year Brand Warranty)": the seller's promise, not
# the product's name.
_WARRANTY_WORDS = re.compile(
    r"\b\d{1,2}\s*(?:years?|yrs?|months?)\s+(?:of\s+)?"
    r"(?:brand\s+|official\s+|local\s+)?warranty\b",
    re.I,
)

# "(2025)", "2026": a tablet is named by its chip and generation ("iPad Air
# M4", "Tab S10 FE"); stores add the year in different places, and the
# phone name cleaner cuts a name at its first bracket ("iPad Pro (2025) M5"
# became "iPad Pro").
_MODEL_YEAR = re.compile(r"\(\s*20\d{2}\s*\)|\b20\d{2}\b")


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# A brand written in two words ("VGO TEL", "One Plus") is the brand's own
# name, not part of the model: written as the brand, so the name cleaner
# does not keep both ("VGOTEL VGO TEL V Tab 2").
_BRAND_SPELLINGS = tuple(
    (
        re.compile(
            r"\b" + r"[\s-]+".join(map(re.escape, re.split(r"[\s-]+", alias))) + r"\b",
            re.I,
        ),
        canonical,
    )
    for canonical, aliases in BRAND_ALIASES
    for alias in aliases
    if re.search(r"[\s-]", alias) and _compact(alias) == _compact(canonical)
)


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"


_STORAGE_SIZES = {16, 32, 64, 128, 256, 512, 1024}

_TABLET_NAME_REWRITES = (
    # "Redmi Pad 2 8/256": memory without units. Left in, its "8" reads as
    # the model number of the "Pad 8". The listing states it separately.
    (
        re.compile(r"(?<![\d.])(\d{1,2})\s*(?:GB)?\s*[/+]\s*(\d{2,4})\s*(?:GB|TB)?(?![\d.])", re.I),
        lambda match: (
            " " if int(match.group(2)) in _STORAGE_SIZES else match.group(0)
        ),
    ),
    # "iPad 11 (A16)", "Tab M10 HD (2nd Gen)": the bracket holds the model,
    # and the name cleaner cuts a name at its first bracket. What else a
    # bracket holds (a year, a warranty) is removed on its own below.
    (re.compile(r"\(([^()]*)\)"), r" \1 "),
    *_BRAND_SPELLINGS,
    (re.compile(r"\bgeneration\b", re.I), "Gen"),
    # "12Th Gen" from title-cased titles.
    (
        re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b", re.I),
        lambda match: match.group(1) + match.group(2).lower(),
    ),
    # Apple counts iPad generations; "iPad Air 7" is Shophive's "iPad Air
    # 7th Gen". A figure followed by a unit is a screen size and is left.
    (
        re.compile(
            r"\b(iPad(?:\s+(?:Air|Mini))?)\s+(\d{1,2})"
            r"(?![\d.])(?!\s*(?:inch|\"|''|”|″|st\b|nd\b|rd\b|th\b))",
            re.I,
        ),
        lambda match: f"{match.group(1)} {_ordinal(int(match.group(2)))} Gen",
    ),
    # Samsung names every tablet "Galaxy Tab"; stores drop or move it
    # ("Samsung S11 Ultra", "Samsung Galaxy A11 Tab").
    (
        re.compile(r"\bSamsung\s+(?:Galaxy\s+)?(?:Tab\s+)?(?=[AS]\d)", re.I),
        "Samsung Galaxy Tab ",
    ),
    (re.compile(r"(\bTab\b.*?)\s+\bTab\b", re.I), r"\1"),
    (re.compile(r"\bchip\b", re.I), " "),
    # The category's own noun says nothing about the model.
    (re.compile(r"\btablets?\b", re.I), " "),
    # Samsung's "SM-" model prefix, written by some stores only.
    (re.compile(r"\bSM-(?=[a-z]\d)", re.I), ""),
    # A Shophive typo on its Redmi Pad 2 listings.
    (re.compile(r"\bSSD\b"), " "),
)


RAM = IdentityAttribute("ram_gb", "RAM", "GB", _ram_gb)
STORAGE = IdentityAttribute("storage_gb", "Storage", "GB", _storage_gb)
CONNECTIVITY = IdentityAttribute("connectivity", "Connectivity", None, _connectivity)
CASE_SIZE = IdentityAttribute("case_size_mm", "Case size", "mm", _case_size_mm)
SCREEN_SIZE = IdentityAttribute("screen_in", "Screen", "inch", _screen_inches)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

DEFAULT_CATEGORY = "mobile-phones"

PROFILES: dict[str, CategoryProfile] = {
    profile.slug: profile
    for profile in (
        CategoryProfile("mobile-phones", "Mobile Phones", (RAM, STORAGE)),
        CategoryProfile(
            "tablets",
            "Tablets",
            (RAM, STORAGE, CONNECTIVITY, SCREEN_SIZE),
            variant_words=(
                re.compile(r"\bwi[\s-]?fi(?:\s+only)?\b", re.I),
                re.compile(r"\b(?:cellular|lte|3g|4g|5g)\b", re.I),
                _SCREEN_SIZE,
                _WARRANTY_WORDS,
                _MODEL_YEAR,
            ),
            name_rewrites=_TABLET_NAME_REWRITES,
        ),
        CategoryProfile(
            "smart-watches",
            "Smart Watches",
            (CASE_SIZE, CONNECTIVITY),
            variant_words=(
                re.compile(r"\b\d{2}\s*mm\b", re.I),
                re.compile(r"\b(?:gps|cellular|lte|4g)\b", re.I),
            ),
        ),
        # Earbuds come in colours only; the model name is the product.
        CategoryProfile("audio-and-earbuds", "Audio and Earbuds", ()),
    )
}

# Older names for a category, as some sources and records spell them.
ALIASES = {"smartphones": "mobile-phones"}


def profile_for(slug: str | None) -> CategoryProfile:
    """Return the profile for a category slug; no slug means a smartphone."""

    if not slug:
        return PROFILES[DEFAULT_CATEGORY]

    normalized = ALIASES.get(slug.strip().lower(), slug.strip().lower())

    try:
        return PROFILES[normalized]
    except KeyError:
        raise UnknownCategoryError(
            f"No category profile for {slug!r}; known: {', '.join(sorted(PROFILES))}."
        ) from None


__all__ = [
    "ALIASES",
    "DEFAULT_CATEGORY",
    "PROFILES",
    "CategoryProfile",
    "IdentityAttribute",
    "UnknownCategoryError",
    "configuration_key",
    "profile_for",
]
